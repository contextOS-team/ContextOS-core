"""Linear OAuth2 lifecycle service.

Handles authorization URL generation, code exchange, token refresh with
advisory lock race condition prevention, and disconnect. All token values
are stored encrypted in Supabase Vault -- never in plain text in the DB.

Uses raw httpx + GraphQL per project decision (no Linear SDK).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import OAuthToken, WorkspaceIntegration
from src.services.oauth_common import OAuthStateError, sign_oauth_state, verify_oauth_state
from src.services.vault import delete_token, read_token, store_token, token_name

# Linear OAuth endpoints
LINEAR_AUTHORIZE_URL = "https://linear.app/oauth/authorize"
LINEAR_TOKEN_URL = "https://api.linear.app/oauth/token"
LINEAR_API_URL = "https://api.linear.app/graphql"


class OAuthError(Exception):
    """Raised when an OAuth operation fails."""


def _sign_state(workspace_id: UUID, secret: str) -> str:
    """Create a signed state parameter. Delegates to shared utility."""
    return sign_oauth_state(workspace_id, secret)


def _verify_state(state: str, secret: str) -> UUID:
    """Verify a signed state parameter. Wraps shared utility with provider error."""
    try:
        return verify_oauth_state(state, secret)
    except OAuthStateError as e:
        raise OAuthError(str(e)) from e


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
    query = "&".join(f"{k}={v}" for k, v in params.items())
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
    access_name = token_name("linear", workspace_id, "access")
    await store_token(session, access_name, access_token_value)

    refresh_name = token_name("linear", workspace_id, "refresh")
    if refresh_token_value:
        await store_token(session, refresh_name, refresh_token_value)

    # Upsert OAuthToken record (stores Vault secret names, NOT actual tokens)
    # Query WITHOUT deleted_at filter — a soft-deleted row still holds the
    # unique constraint slot, so we must reuse it on reconnect.
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "linear",
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.access_token = access_name
        oauth_token.refresh_token = refresh_name if refresh_token_value else None
        oauth_token.token_expires_at = token_expires_at
        oauth_token.scopes = ["read", "write"]
        oauth_token.deleted_at = None  # un-soft-delete on reconnect
    else:
        oauth_token = OAuthToken(
            workspace_id=workspace_id,
            user_id=user_id,
            provider="linear",
            access_token=access_name,
            refresh_token=refresh_name if refresh_token_value else None,
            token_expires_at=token_expires_at,
            scopes=["read", "write"],
        )
        session.add(oauth_token)

    # Fetch Linear organization info
    org_info = await _fetch_organization(access_token_value)

    # Upsert WorkspaceIntegration
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "linear",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "connected"
        integration.external_id = org_info.get("id")
        integration.connected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        integration.deleted_at = None
    else:
        integration = WorkspaceIntegration(
            workspace_id=workspace_id,
            provider="linear",
            status="connected",
            external_id=org_info.get("id"),
            connected_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(integration)

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
        OAuthToken.provider == "linear",
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise OAuthError("No OAuth token found for this workspace")

    # If token is still valid, return current access token
    if oauth_token.token_expires_at and oauth_token.token_expires_at > datetime.now(timezone.utc).replace(tzinfo=None):
        access_name = token_name("linear", workspace_id, "access")
        current_token = await read_token(session, access_name)
        if current_token:
            return current_token

    # Read refresh token from Vault
    refresh_name = token_name("linear", workspace_id, "refresh")
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
    access_name = token_name("linear", workspace_id, "access")
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
        OAuthToken.provider == "linear",
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise OAuthError("No Linear integration found for this workspace")

    # Check if token is still valid (with 5 min buffer)
    if oauth_token.token_expires_at:
        buffer = timedelta(minutes=5)
        if oauth_token.token_expires_at > (datetime.now(timezone.utc).replace(tzinfo=None) + buffer):
            # Token still valid, read from Vault
            access_name = token_name("linear", workspace_id, "access")
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
    # Soft-delete OAuthToken
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "linear",
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Delete Vault secrets
    access_name = token_name("linear", workspace_id, "access")
    refresh_name = token_name("linear", workspace_id, "refresh")
    await delete_token(session, access_name)
    await delete_token(session, refresh_name)

    # Mark integration as disconnected
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "linear",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "disconnected"

    await session.commit()


async def _mark_integration_error(session: AsyncSession, workspace_id: UUID) -> None:
    """Mark the Linear workspace integration status as 'error'.

    Called when token refresh fails.
    """
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "linear",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "error"
        await session.commit()
