"""API key generation, hashing, listing, and revocation."""

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.api_key import ApiKey


def generate_api_key() -> tuple[str, str, str]:
    """Generate a random API key.

    Returns:
        Tuple of (full_key, prefix, hash) where:
        - full_key: cos_{random_hex} (shown once at creation)
        - prefix: cos_{first_8_chars} (stored for display)
        - hash: SHA-256 hex digest of full_key (stored for validation)
    """
    raw = secrets.token_hex(32)
    full_key = f"cos_{raw}"
    prefix = f"cos_{raw[:8]}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


async def create_api_key(
    session: AsyncSession,
    workspace_id: UUID,
    created_by: UUID,
    name: str,
) -> tuple[ApiKey, str]:
    """Create a new API key for a workspace.

    Returns:
        Tuple of (ApiKey model, full_key). The full key is only
        available at creation time and must be shown to the user once.
    """
    full_key, prefix, key_hash = generate_api_key()

    api_key = ApiKey(
        workspace_id=workspace_id,
        created_by=created_by,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return api_key, full_key


async def list_api_keys(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[ApiKey]:
    """Return all non-revoked API keys for a workspace, newest first."""
    stmt = (
        select(ApiKey)
        .where(
            ApiKey.workspace_id == workspace_id,
            ApiKey.revoked_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(ApiKey.created_at.desc())  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def revoke_api_key(
    session: AsyncSession,
    workspace_id: UUID,
    key_id: UUID,
) -> ApiKey | None:
    """Soft-revoke an API key by setting revoked_at.

    Returns None if the key is not found, already revoked,
    or belongs to a different workspace.
    """
    stmt = select(ApiKey).where(
        ApiKey.id == key_id,
        ApiKey.workspace_id == workspace_id,
        ApiKey.revoked_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        return None

    api_key.revoked_at = datetime.now(timezone.utc)
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return api_key
