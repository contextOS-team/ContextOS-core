"""FastAPI dependency injection for authentication and workspace scoping."""

from time import monotonic
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.auth import JWTError, decode_supabase_jwt
from src.config import get_settings
from src.db import get_session
from src.models.user import Profile, WorkspaceMember
from src.observability.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer()

# Workspace membership cache (PERF-01)
# ----------------------------------------------------------------------
# Production Supabase is in Singapore (~280ms RTT from Nuremberg). The
# workspace_members lookup runs on every authenticated request, so we
# cache the resolved workspace_id in Redis to skip the round-trip on hits.
#
# Invalidation: workspace_members rows are written exclusively by Postgres
# triggers (see supabase/migrations 00002, 00012, 00018, 00038); no
# application-level INSERT/UPDATE/DELETE exists today. The 5-minute TTL
# is the safety bound for trigger bugs and for the day teammate invites
# / workspace switching land — those paths must call
# _invalidate_workspace_cache(user_id) to drop the stale entry.
_WORKSPACE_CACHE_TTL_SECONDS = 300
_WORKSPACE_CACHE_KEY_PREFIX = "userctx:workspace:"

# Module-level Redis client. Lazily connected on first use; if Redis is
# unreachable we mark it unavailable for a short window and retry later
# rather than latching the failure for the lifetime of the worker.
_redis_client: aioredis.Redis | None = None
_REDIS_RETRY_COOLDOWN_SECONDS = 30.0
_redis_retry_after: float = 0.0


def _workspace_cache_key(user_id: UUID) -> str:
    return f"{_WORKSPACE_CACHE_KEY_PREFIX}{user_id}"


async def _get_redis() -> aioredis.Redis | None:
    """Return a connected Redis client, or None if unreachable.

    On connection failure we set a short cooldown (default 30s) instead of
    latching unavailability for the worker lifetime, so a transient Redis
    blip during deploy doesn't permanently drop us into DB-fallback mode.
    """
    global _redis_client, _redis_retry_after

    if _redis_client is not None:
        return _redis_client

    now = monotonic()
    if now < _redis_retry_after:
        return None

    try:
        settings = get_settings()
        if not settings.REDIS_URL:
            _redis_retry_after = now + _REDIS_RETRY_COOLDOWN_SECONDS
            return None
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        logger.warning("workspace_cache_redis_connect_failed", exc_info=True)
        _redis_retry_after = now + _REDIS_RETRY_COOLDOWN_SECONDS
        return None


async def _cache_get_workspace(user_id: UUID) -> UUID | None:
    """Fetch cached workspace_id for user. Returns None on miss or error."""
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(_workspace_cache_key(user_id))
    except Exception:
        logger.warning("workspace_cache_get_failed", exc_info=True)
        return None
    if raw is None:
        return None
    try:
        return UUID(raw)
    except ValueError:
        # Corrupt entry -- treat as miss; will be overwritten on next set.
        return None


async def _cache_set_workspace(user_id: UUID, workspace_id: UUID) -> None:
    """Store workspace_id for user with TTL. Best-effort; swallows errors."""
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.set(
            _workspace_cache_key(user_id),
            str(workspace_id),
            ex=_WORKSPACE_CACHE_TTL_SECONDS,
        )
    except Exception:
        logger.warning("workspace_cache_set_failed", exc_info=True)


async def _invalidate_workspace_cache(user_id: UUID) -> None:
    """Drop the cached workspace_id for a user.

    Call this whenever application code creates, soft-deletes, or
    reassigns a workspace_members row for ``user_id``. Currently no
    such write path exists (see module docstring above), but the helper
    is kept exported for future use.
    """
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.delete(_workspace_cache_key(user_id))
    except Exception:
        logger.warning("workspace_cache_delete_failed", exc_info=True)


class UserContext(BaseModel):
    """Authenticated user context injected into route handlers."""

    user_id: UUID
    email: str
    workspace_id: UUID


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> UserContext:
    """Decode JWT, look up user profile and workspace membership.

    Returns UserContext with user_id, email, workspace_id.
    Raises 401 if token is invalid or user not found.
    """
    try:
        payload = decode_supabase_jwt(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # PERF-01: Try Redis cache first to skip the ~280ms Singapore round-trip.
    cached = await _cache_get_workspace(payload.sub)
    if cached is not None:
        return UserContext(
            user_id=payload.sub,
            email=payload.email or "",
            workspace_id=cached,
        )

    # Look up the user's workspace membership
    # REL-02: ORDER BY + LIMIT 1 ensures deterministic result for single-workspace assumption
    stmt = (
        select(WorkspaceMember.workspace_id)
        .where(
            WorkspaceMember.user_id == payload.sub,
            WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(WorkspaceMember.created_at.asc())  # type: ignore[union-attr]
        .limit(1)
    )
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    await _cache_set_workspace(payload.sub, membership)

    return UserContext(
        user_id=payload.sub,
        email=payload.email or "",
        workspace_id=membership,
    )


async def get_current_workspace(
    user: UserContext = Depends(get_current_user),
) -> UUID:
    """Extract just the workspace_id for workspace-scoped queries."""
    return user.workspace_id
