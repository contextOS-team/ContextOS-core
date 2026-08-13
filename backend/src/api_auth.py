"""API-key authentication for the agent-facing Decision Context API.

Separate from the human JWT path (dependencies.get_current_user): agents have
no email and no single-workspace-per-user assumption. A MachinePrincipal
carries only what a scoped, workspace-bound key grants.

Lookup is by key_prefix (indexed in 00049), because the per-key salt (00022)
makes hash lookup impossible — the salt lives in the row you're trying to find.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.models.api_key import ApiKey
from src.services.api_key import verify_api_key

# auto_error=False so routes can also accept it optionally; we raise 401 below.
bearer = HTTPBearer(auto_error=False)


class MachinePrincipal(BaseModel):
    workspace_id: UUID
    key_id: UUID
    scopes: list[str]


def _prefix_of(full_key: str) -> str:
    # cos_{8 hex}... — the prefix stored at creation is cos_ + first 8 chars.
    raw = full_key[len("cos_") :] if full_key.startswith("cos_") else full_key
    return f"cos_{raw[:8]}"


async def get_api_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> MachinePrincipal:
    if credentials is None or not credentials.credentials.startswith("cos_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    full_key = credentials.credentials
    rows = (
        (
            await session.execute(
                select(ApiKey).where(
                    ApiKey.key_prefix == _prefix_of(full_key),
                    ApiKey.revoked_at.is_(None),  # type: ignore[union-attr]
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for key in rows:
        if not verify_api_key(full_key, key.key_hash, key.salt):
            continue
        if key.expires_at is not None and key.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired"
            )
        # Best-effort last_used_at stamp; never block auth on it.
        try:
            await session.execute(
                sa_text("UPDATE api_keys SET last_used_at = now() WHERE id = :id"),
                {"id": str(key.id)},
            )
            await session.commit()
        except Exception:
            await session.rollback()
        return MachinePrincipal(
            workspace_id=key.workspace_id, key_id=key.id, scopes=key.scopes
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_scope(scope: str):
    """Dependency factory: enforce a scope on the authenticated principal."""

    async def _checker(
        principal: MachinePrincipal = Depends(get_api_principal),
    ) -> MachinePrincipal:
        if scope not in principal.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: {scope}",
            )
        return principal

    return _checker
