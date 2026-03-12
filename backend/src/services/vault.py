"""Vault service for encrypted token storage via Supabase Vault.

Wraps the SQL functions defined in 00003_vault_token_functions.sql to
provide a simple Python API for storing, reading, and deleting encrypted
secrets in the Vault.

Includes a health check function for deployment readiness probes.
"""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def token_name(provider: str, workspace_id: UUID, token_type: str) -> str:
    """Generate a Vault secret name following the naming convention.

    Format: oauth_{provider}_{workspace_id}_{token_type}
    Example: oauth_linear_<uuid>_access
    """
    p = provider.value if hasattr(provider, "value") else provider
    return f"oauth_{p}_{workspace_id}_{token_type}"


async def store_token(session: AsyncSession, name: str, value: str) -> str:
    """Store or update an encrypted token in Supabase Vault.

    Args:
        session: Async database session.
        name: Secret name (use token_name() to generate).
        value: Plain-text token value to encrypt and store.

    Returns:
        The UUID of the stored secret as a string.
    """
    result = await session.execute(
        text("SELECT public.store_vault_secret(:name, :value)"),
        {"name": name, "value": value},
    )
    secret_id = result.scalar_one()
    return str(secret_id)


async def read_token(session: AsyncSession, name: str) -> str | None:
    """Read a decrypted token from Supabase Vault.

    Args:
        session: Async database session.
        name: Secret name to look up.

    Returns:
        The decrypted token value, or None if not found.
    """
    result = await session.execute(
        text("SELECT public.read_vault_secret(:name)"),
        {"name": name},
    )
    return result.scalar_one_or_none()


async def delete_token(session: AsyncSession, name: str) -> None:
    """Delete a token from Supabase Vault.

    Args:
        session: Async database session.
        name: Secret name to delete.
    """
    await session.execute(
        text("SELECT public.delete_vault_secret(:name)"),
        {"name": name},
    )


async def check_vault_health(session: AsyncSession) -> bool:
    """Check Vault connectivity by storing, reading, and deleting a test secret.

    This is used by the deep health endpoint to verify that the Vault
    encryption infrastructure is operational.

    Args:
        session: Async database session.

    Returns:
        True if Vault is healthy, False on any error.
    """
    test_name = "_health_check_probe"
    test_value = "vault_health_ok"
    try:
        await store_token(session, test_name, test_value)
        read_back = await read_token(session, test_name)
        await delete_token(session, test_name)
        return read_back == test_value
    except Exception:
        logger.warning("Vault health check failed", exc_info=True)
        return False
