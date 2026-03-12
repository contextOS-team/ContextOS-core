"""API key generation, hashing, listing, and revocation.

SEC-04: New keys use per-key salt for SHA-256 hashing. Existing keys
with NULL salt verify using the legacy unsalted hash path.
"""

import hashlib
import os
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.api_key import ApiKey


def _hash_key(key: str, salt: str | None = None) -> str:
    """Hash an API key with optional salt.

    Args:
        key: The full API key string.
        salt: Per-key salt (hex string). If None, uses unsalted hash.

    Returns:
        SHA-256 hex digest.
    """
    if salt:
        return hashlib.sha256((salt + key).encode()).hexdigest()
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str, str]:
    """Generate a random API key with per-key salt.

    Returns:
        Tuple of (full_key, prefix, hash, salt) where:
        - full_key: cos_{random_hex} (shown once at creation)
        - prefix: cos_{first_8_chars} (stored for display)
        - hash: SHA-256 hex digest of salt + full_key (stored for validation)
        - salt: Random 16-byte hex salt (stored alongside hash)
    """
    raw = secrets.token_hex(32)
    full_key = f"cos_{raw}"
    prefix = f"cos_{raw[:8]}"
    salt = os.urandom(16).hex()
    key_hash = _hash_key(full_key, salt)
    return full_key, prefix, key_hash, salt


def verify_api_key(full_key: str, stored_hash: str, salt: str | None = None) -> bool:
    """Verify an API key against its stored hash.

    Handles both salted (new) and unsalted (legacy) keys based on
    whether salt is present.

    Args:
        full_key: The full API key to verify.
        stored_hash: The stored SHA-256 hash.
        salt: Per-key salt (None for legacy unsalted keys).

    Returns:
        True if the key matches.
    """
    computed = _hash_key(full_key, salt)
    return secrets.compare_digest(computed, stored_hash)


async def create_api_key(
    session: AsyncSession,
    workspace_id: UUID,
    created_by: UUID,
    name: str,
) -> tuple[ApiKey, str]:
    """Create a new API key for a workspace.

    SEC-04: New keys are hashed with a per-key random salt.

    Returns:
        Tuple of (ApiKey model, full_key). The full key is only
        available at creation time and must be shown to the user once.
    """
    full_key, prefix, key_hash, salt = generate_api_key()

    api_key = ApiKey(
        workspace_id=workspace_id,
        created_by=created_by,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        salt=salt,
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
