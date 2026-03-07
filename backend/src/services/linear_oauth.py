"""Linear OAuth2 lifecycle service.

Handles authorization URL generation, code exchange, token refresh with
advisory lock race condition prevention, and disconnect. All token values
are stored encrypted in Supabase Vault -- never in plain text in the DB.

Uses raw httpx + GraphQL per project decision (no Linear SDK).
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import OAuthToken, Provider, WorkspaceIntegration
from src.services.oauth_common import (
    TOKEN_REFRESH_BUFFER,
    disconnect_provider,
    upsert_oauth_token,
    upsert_workspace_integration,
)
from src.services.vault import read_token, store_token, token_name

# Linear OAuth endpoints
LINEAR_AUTHORIZE_URL = "https://linear.app/oauth/authorize"
LINEAR_TOKEN_URL = "https://api.linear.app/oauth/token"
LINEAR_API_URL = "https://api.linear.app/graphql"


class OAuthError(Exception):
    """Raised when an OAuth operation fails."""



def build_auth_url(state: str, settings: Settings) -> str:
    """Construct the Linear OAuth authorization URL.

    Args:
        state: Pre-signed state parameter (use _sign_state to create).
        settings: Application settings with Linear OAuth config.

    Returns:
        Full authorization URL to redirect the user to.
    """
    params = {
        "client_id": settings.LINEAR_CLIENT_ID,
        "redirect_uri": settings.linear_redirect_uri,
        "response_type": "code",
        "scope": "read,write",
        "state": state,
    }
    query = urlencode(params)
    return f"{LINEAR_AUTHORIZE_URL}?{query}"


async def exchange_code(
    code: str,
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: Settings,
) -> dict:
    """Exchange an authorization code for access and refresh tokens.

    Stores tokens encrypted in Vault, creates/updates OAuthToken and
    WorkspaceIntegration records, and fetches Linear organization info.

    Args:
        code: Authorization code from Linear callback.
        session: Async database session.
        workspace_id: Workspace to associate the integration with.
        user_id: User who initiated the OAuth flow.
        settings: Application settings.

    Returns:
        Dict with organization info: {"id": str, "name": str}

    Raises:
        OAuthError: If code exchange or organization fetch fails.
    """
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LINEAR_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.linear_redirect_uri,
                "client_id": settings.LINEAR_CLIENT_ID,
                "client_secret": settings.LINEAR_CLIENT_SECRET,
            },
        )

    if response.status_code != 200:
        raise OAuthError(f"Token exchange failed: {response.text}")

    token_data = response.json()
    access_token_value = token_data["access_token"]
    refresh_token_value = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    # Calculate token expiry (naive UTC — matches TIMESTAMP WITHOUT TIME ZONE column)
    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None).replace(microsecond=0) + timedelta(seconds=expires_in)

    # Store tokens in Vault (encrypted at rest)
    access_name = token_name(Provider.LINEAR, workspace_id, "access")
    await store_token(session, access_name, access_token_value)

    refresh_name = token_name(Provider.LINEAR, workspace_id, "refresh")
    if refresh_token_value:
        await store_token(session, refresh_name, refresh_token_value)

    # Upsert OAuthToken record (stores Vault secret names, NOT actual tokens)
    await upsert_oauth_token(
        session, workspace_id, user_id, Provider.LINEAR,
        access_token_name=access_name,
        refresh_token_name=refresh_name if refresh_token_value else None,
        token_expires_at=token_expires_at,
        scopes=["read", "write"],
    )

    # Fetch Linear organization info
    org_info = await _fetch_organization(access_token_value)

    # Upsert WorkspaceIntegration
    org_name = org_info.get("name")
    await upsert_workspace_integration(
        session, workspace_id, Provider.LINEAR,
        external_id=org_info.get("id"),
        config={"external_name": org_name} if org_name else None,
    )

    await session.commit()

    return org_info


async def _fetch_organization(access_token: str) -> dict:
    """Fetch Linear organization info via GraphQL.

    Args:
        access_token: Valid Linear access token.

    Returns:
        Dict with organization id and name.

    Raises:
        OAuthError: If the GraphQL query fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LINEAR_API_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"query": "{ organization { id name } }"},
        )

    if response.status_code != 200:
        raise OAuthError(f"Failed to fetch organization: {response.text}")

    data = response.json()
    if "errors" in data:
        raise OAuthError(f"GraphQL error: {data['errors']}")

    return data["data"]["organization"]


async def refresh_access_token(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: Settings,
) -> str:
    """Refresh the Linear access token with advisory lock for race prevention.

    Only one refresh can run at a time per workspace, enforced via
    pg_advisory_xact_lock. If another process already refreshed, the
    current valid token is returned instead.

    Args:
        session: Async database session.
        workspace_id: Workspace whose token to refresh.
        user_id: User who owns the token.
        settings: Application settings.

    Returns:
        The new (or still-valid) access token.

    Raises:
        OAuthError: If refresh fails (also marks integration status as 'error').
    """
    # Acquire advisory lock to prevent concurrent refreshes for same workspace
    lock_key = f"linear_refresh_{workspace_id}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": lock_key},
    )

    # Re-check token expiry (another process may have already refreshed)
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == Provider.LINEAR,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise OAuthError("No OAuth token found for this workspace")

    # If token is still valid, return current access token
    if oauth_token.token_expires_at and oauth_token.token_expires_at > datetime.now(timezone.utc):
        access_name = token_name(Provider.LINEAR, workspace_id, "access")
        current_token = await read_token(session, access_name)
        if current_token:
            return current_token

    # Read refresh token from Vault
    refresh_name = token_name(Provider.LINEAR, workspace_id, "refresh")
    refresh_token_value = await read_token(session, refresh_name)

    if not refresh_token_value:
        await _mark_integration_error(session, workspace_id)
        raise OAuthError("No refresh token available")

    # Call Linear token refresh endpoint
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LINEAR_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token_value,
                    "client_id": settings.LINEAR_CLIENT_ID,
                    "client_secret": settings.LINEAR_CLIENT_SECRET,
                },
            )

        if response.status_code != 200:
            await _mark_integration_error(session, workspace_id)
            raise OAuthError(f"Token refresh failed: {response.text}")

        token_data = response.json()
    except httpx.HTTPError as e:
        await _mark_integration_error(session, workspace_id)
        raise OAuthError(f"Token refresh HTTP error: {e}") from e

    new_access_token = token_data["access_token"]
    new_refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    # Store new tokens in Vault
    access_name = token_name(Provider.LINEAR, workspace_id, "access")
    await store_token(session, access_name, new_access_token)

    if new_refresh_token:
        await store_token(session, refresh_name, new_refresh_token)

    # Update token expiry in DB
    if expires_in:
        oauth_token.token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None).replace(microsecond=0) + timedelta(seconds=expires_in)

    await session.commit()

    return new_access_token


async def get_valid_access_token(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: Settings,
) -> str:
    """Get a valid access token, refreshing if expired.

    This is the main entry point for code that needs a Linear access token.
    It reads the current token, checks expiry, and refreshes if needed.

    Args:
        session: Async database session.
        workspace_id: Workspace to get token for.
        user_id: User who owns the token.
        settings: Application settings.

    Returns:
        A valid access token string.

    Raises:
        OAuthError: If no token exists or refresh fails.
    """
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == Provider.LINEAR,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise OAuthError("No Linear integration found for this workspace")

    # Check if token is still valid (with 5 min buffer)
    if oauth_token.token_expires_at:
        expires_at = oauth_token.token_expires_at.replace(tzinfo=None) if oauth_token.token_expires_at.tzinfo else oauth_token.token_expires_at
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expires_at > (now_utc + TOKEN_REFRESH_BUFFER):
            # Token still valid, read from Vault
            access_name = token_name(Provider.LINEAR, workspace_id, "access")
            current_token = await read_token(session, access_name)
            if current_token:
                return current_token

    # Token expired or expiring soon, refresh it
    return await refresh_access_token(session, workspace_id, user_id, settings)


async def disconnect(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    """Disconnect Linear integration.

    Soft-deletes the OAuthToken, deletes Vault secrets, and marks
    WorkspaceIntegration as disconnected. Existing ticket data is preserved.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
        user_id: User who initiated the disconnect.
    """
    access_name = token_name(Provider.LINEAR, workspace_id, "access")
    refresh_name = token_name(Provider.LINEAR, workspace_id, "refresh")
    await disconnect_provider(
        session, workspace_id, user_id, Provider.LINEAR,
        vault_token_names=[access_name, refresh_name],
    )


async def _mark_integration_error(session: AsyncSession, workspace_id: UUID) -> None:
    """Mark the Linear workspace integration status as 'error'.

    Called when token refresh fails.
    """
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.LINEAR,
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "error"
        await session.commit()
