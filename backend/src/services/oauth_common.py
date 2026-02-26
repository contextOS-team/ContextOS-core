"""Shared OAuth state parameter utilities.

Provides HMAC-SHA256 state signing and verification used by all OAuth
providers (Linear, Slack, GitHub). Extracted to eliminate code triplication.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

# Proactive token refresh buffer — tokens are refreshed when they
# expire within this window. Used by Linear and GitHub token flows.
TOKEN_REFRESH_BUFFER = timedelta(minutes=5)


class OAuthStateError(ValueError):
    """Raised when OAuth state parameter is invalid or tampered."""


def sign_oauth_state(workspace_id: UUID, secret: str) -> str:
    """Create a signed state parameter encoding workspace_id.

    Uses HMAC-SHA256 to prevent CSRF. Format: {workspace_id}:{signature}

    Args:
        workspace_id: Workspace UUID to encode.
        secret: Client secret for HMAC signing.

    Returns:
        Signed state string: "{workspace_id}:{hmac_signature}"
    """
    message = str(workspace_id)
    signature = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{message}:{signature}"


def verify_oauth_state(state: str, secret: str) -> UUID:
    """Verify and extract workspace_id from a signed state parameter.

    Args:
        state: Signed state string from OAuth callback.
        secret: Client secret for HMAC verification.

    Returns:
        The extracted workspace UUID.

    Raises:
        OAuthStateError: If the state format or signature is invalid.
    """
    try:
        workspace_str, signature = state.rsplit(":", 1)
    except ValueError as e:
        raise OAuthStateError("Invalid state parameter format") from e

    expected = hmac.new(
        secret.encode(), workspace_str.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise OAuthStateError("Invalid state signature")

    return UUID(workspace_str)


logger = logging.getLogger(__name__)


def verify_state_or_raise(state: str, secret: str, error_cls: type[Exception]) -> UUID:
    """Verify OAuth state and raise provider-specific error on failure.

    Replaces the identical _verify_state wrappers in each OAuth service.

    Args:
        state: Signed state string from OAuth callback.
        secret: Client secret for HMAC verification.
        error_cls: Provider-specific exception class to raise.

    Returns:
        The extracted workspace UUID.

    Raises:
        error_cls: If the state format or signature is invalid.
    """
    try:
        return verify_oauth_state(state, secret)
    except OAuthStateError as e:
        raise error_cls(str(e)) from e


async def upsert_oauth_token(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    provider: str,
    access_token_name: str,
    refresh_token_name: str | None = None,
    token_expires_at=None,
    scopes: list[str] | None = None,
    metadata: dict | None = None,
):
    """Upsert an OAuthToken record with soft-delete reuse.

    Queries WITHOUT deleted_at filter to reuse soft-deleted rows
    (they still hold the unique constraint slot). Un-soft-deletes
    on reconnect.

    Args:
        session: Async database session.
        workspace_id: Workspace UUID.
        user_id: User UUID.
        provider: Provider string (use Provider enum).
        access_token_name: Vault secret name for access token.
        refresh_token_name: Vault secret name for refresh token.
        token_expires_at: Token expiry datetime (naive UTC).
        scopes: OAuth scopes list.
        metadata: Additional metadata dict.

    Returns:
        The upserted OAuthToken record.
    """
    from src.models.integration import OAuthToken

    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == provider,
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.access_token = access_token_name
        oauth_token.refresh_token = refresh_token_name
        oauth_token.token_expires_at = token_expires_at
        if scopes is not None:
            oauth_token.scopes = scopes
        if metadata is not None:
            oauth_token.metadata_ = metadata
        oauth_token.deleted_at = None  # un-soft-delete on reconnect
    else:
        kwargs = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "provider": provider,
            "access_token": access_token_name,
            "refresh_token": refresh_token_name,
            "token_expires_at": token_expires_at,
        }
        if scopes is not None:
            kwargs["scopes"] = scopes
        if metadata is not None:
            kwargs["metadata_"] = metadata
        oauth_token = OAuthToken(**kwargs)
        session.add(oauth_token)

    return oauth_token


async def upsert_workspace_integration(
    session: AsyncSession,
    workspace_id: UUID,
    provider: str,
    external_id: str | None = None,
    config: dict | None = None,
):
    """Upsert a WorkspaceIntegration record.

    Merges new config keys into existing config ({**existing, **new}).
    Un-soft-deletes on reconnect.

    Args:
        session: Async database session.
        workspace_id: Workspace UUID.
        provider: Provider string (use Provider enum).
        external_id: External identifier (org id, team id, etc.).
        config: Config dict to merge into existing config.

    Returns:
        The upserted WorkspaceIntegration record.
    """
    from src.models.integration import WorkspaceIntegration

    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == provider,
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if integration:
        integration.status = "connected"
        if external_id is not None:
            integration.external_id = external_id
        if config is not None:
            integration.config = {**integration.config, **config}
        integration.connected_at = now
        integration.deleted_at = None
    else:
        integration = WorkspaceIntegration(
            workspace_id=workspace_id,
            provider=provider,
            status="connected",
            external_id=external_id,
            config=config or {},
            connected_at=now,
        )
        session.add(integration)

    return integration


async def disconnect_provider(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    provider: str,
    vault_token_names: list[str],
):
    """Shared disconnect flow for OAuth providers.

    Soft-deletes OAuthToken, deletes vault secrets, marks integration
    as disconnected, and commits.

    Args:
        session: Async database session.
        workspace_id: Workspace UUID.
        user_id: User UUID.
        provider: Provider string (use Provider enum).
        vault_token_names: List of vault secret names to delete.
    """
    from src.models.integration import OAuthToken, WorkspaceIntegration
    from src.services.vault import delete_token

    # Soft-delete OAuthToken
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == provider,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Delete Vault secrets
    for name in vault_token_names:
        await delete_token(session, name)

    # Mark integration as disconnected
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == provider,
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "disconnected"

    await session.commit()
