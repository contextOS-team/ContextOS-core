"""Jira OAuth 2.0 (3LO) lifecycle service.

Handles authorization URL generation, code exchange with cloudId resolution,
token refresh with advisory lock race condition prevention, and disconnect.
All token values are stored encrypted in Supabase Vault.

Uses Atlassian's OAuth 2.0 (3LO) flow via auth.atlassian.com.
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

# Jira/Atlassian OAuth endpoints
JIRA_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
JIRA_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
JIRA_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

# Scopes required for Jira integration
JIRA_SCOPES = "read:jira-work write:jira-work read:jira-user manage:jira-webhook offline_access"


class JiraOAuthError(Exception):
    """Raised when a Jira OAuth operation fails."""


def build_auth_url(state: str, settings: Settings) -> str:
    """Construct the Jira OAuth 2.0 (3LO) authorization URL.

    Args:
        state: Pre-signed state parameter (use sign_oauth_state to create).
        settings: Application settings with Jira OAuth config.

    Returns:
        Full authorization URL to redirect the user to.
    """
    params = {
        "audience": "api.atlassian.com",
        "client_id": settings.JIRA_CLIENT_ID,
        "scope": JIRA_SCOPES,
        "redirect_uri": settings.jira_redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    query = urlencode(params)
    return f"{JIRA_AUTHORIZE_URL}?{query}"


async def exchange_code(
    code: str,
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: Settings,
) -> dict:
    """Exchange an authorization code for access and refresh tokens.

    Stores tokens encrypted in Vault, creates/updates OAuthToken and
    WorkspaceIntegration records, and fetches Jira cloud ID.

    IMPORTANT: Jira token exchange uses JSON body (NOT form data).

    Args:
        code: Authorization code from Jira callback.
        session: Async database session.
        workspace_id: Workspace to associate the integration with.
        user_id: User who initiated the OAuth flow.
        settings: Application settings.

    Returns:
        Dict with cloud resource info: {"cloud_id": str, "site_name": str}

    Raises:
        JiraOAuthError: If code exchange or resource fetch fails.
    """
    # Exchange code for tokens -- Jira requires JSON body, not form data
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            JIRA_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "client_id": settings.JIRA_CLIENT_ID,
                "client_secret": settings.JIRA_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.jira_redirect_uri,
            },
        )

    if response.status_code != 200:
        raise JiraOAuthError(f"Token exchange failed: {response.text}")

    token_data = response.json()
    access_token_value = token_data["access_token"]
    refresh_token_value = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    # Calculate token expiry (naive UTC)
    token_expires_at = None
    if expires_in:
        token_expires_at = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None, microsecond=0)
            + timedelta(seconds=expires_in)
        )

    # Fetch accessible resources to get cloud_id
    cloud_info = await _fetch_accessible_resources(access_token_value)

    # Store tokens in Vault (encrypted at rest)
    access_name = token_name(Provider.JIRA, workspace_id, "access")
    await store_token(session, access_name, access_token_value)

    refresh_name = token_name(Provider.JIRA, workspace_id, "refresh")
    if refresh_token_value:
        await store_token(session, refresh_name, refresh_token_value)

    # Upsert OAuthToken record (stores Vault secret names, NOT actual tokens)
    await upsert_oauth_token(
        session, workspace_id, user_id, Provider.JIRA,
        access_token_name=access_name,
        refresh_token_name=refresh_name if refresh_token_value else None,
        token_expires_at=token_expires_at,
        scopes=JIRA_SCOPES.split(),
    )

    # Upsert WorkspaceIntegration with cloud_id in config
    cloud_id = cloud_info["cloud_id"]
    site_name = cloud_info.get("site_name", "")
    await upsert_workspace_integration(
        session, workspace_id, Provider.JIRA,
        external_id=cloud_id,
        config={"cloud_id": cloud_id, "external_name": site_name},
    )

    await session.commit()

    return cloud_info


async def _fetch_accessible_resources(access_token: str) -> dict:
    """Fetch Jira accessible resources to get the cloud ID.

    The accessible-resources endpoint returns the list of Jira sites
    the user has access to. We use the first one.

    Args:
        access_token: Valid Jira access token.

    Returns:
        Dict with cloud_id and site_name.

    Raises:
        JiraOAuthError: If the request fails or no resources are found.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            JIRA_ACCESSIBLE_RESOURCES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise JiraOAuthError(f"Failed to fetch accessible resources: {response.text}")

    resources = response.json()
    if not resources:
        raise JiraOAuthError("No accessible Jira resources found")

    # Use the first accessible resource
    resource = resources[0]
    return {
        "cloud_id": resource["id"],
        "site_name": resource.get("name", ""),
        "site_url": resource.get("url", ""),
    }


async def refresh_access_token(
    session: AsyncSession,
    workspace_id: UUID,
    settings: Settings,
) -> str:
    """Refresh the Jira access token with advisory lock for race prevention.

    Only one refresh can run at a time per workspace, enforced via
    pg_advisory_xact_lock. If another process already refreshed, the
    current valid token is returned instead.

    IMPORTANT: Jira uses rotating refresh tokens -- the NEW refresh token
    must be stored on each refresh.

    Args:
        session: Async database session.
        workspace_id: Workspace whose token to refresh.
        settings: Application settings.

    Returns:
        The new (or still-valid) access token.

    Raises:
        JiraOAuthError: If refresh fails (also marks integration status as 'error').
    """
    # Acquire advisory lock to prevent concurrent refreshes
    lock_key = f"jira_refresh_{workspace_id}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": lock_key},
    )

    # Re-check token expiry (another process may have already refreshed)
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.provider == Provider.JIRA,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise JiraOAuthError("No OAuth token found for this workspace")

    # If token is still valid, return current access token
    if oauth_token.token_expires_at and oauth_token.token_expires_at > datetime.now(timezone.utc):
        access_name = token_name(Provider.JIRA, workspace_id, "access")
        current_token = await read_token(session, access_name)
        if current_token:
            return current_token

    # Read refresh token from Vault
    refresh_name = token_name(Provider.JIRA, workspace_id, "refresh")
    refresh_token_value = await read_token(session, refresh_name)

    if not refresh_token_value:
        await _mark_integration_error(session, workspace_id)
        raise JiraOAuthError("No refresh token available")

    # Call Jira token refresh endpoint -- JSON body (not form data)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                JIRA_TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "client_id": settings.JIRA_CLIENT_ID,
                    "client_secret": settings.JIRA_CLIENT_SECRET,
                    "refresh_token": refresh_token_value,
                },
            )

        if response.status_code != 200:
            await _mark_integration_error(session, workspace_id)
            raise JiraOAuthError(f"Token refresh failed: {response.text}")

        token_data = response.json()
    except httpx.HTTPError as e:
        await _mark_integration_error(session, workspace_id)
        raise JiraOAuthError(f"Token refresh HTTP error: {e}") from e

    new_access_token = token_data["access_token"]
    new_refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    # Store new tokens in Vault (rotating refresh token!)
    access_name = token_name(Provider.JIRA, workspace_id, "access")
    await store_token(session, access_name, new_access_token)

    if new_refresh_token:
        await store_token(session, refresh_name, new_refresh_token)

    # Update token expiry in DB
    if expires_in:
        oauth_token.token_expires_at = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None, microsecond=0)
            + timedelta(seconds=expires_in)
        )

    await session.commit()

    return new_access_token


async def get_valid_token(
    session: AsyncSession,
    workspace_id: UUID,
    settings: Settings,
) -> tuple[str, str]:
    """Get a valid access token and cloud_id, refreshing if expired.

    This is the main entry point for code that needs a Jira access token.
    It reads the current token, checks expiry, and refreshes if needed.

    Args:
        session: Async database session.
        workspace_id: Workspace to get token for.
        settings: Application settings.

    Returns:
        Tuple of (access_token, cloud_id).

    Raises:
        JiraOAuthError: If no token exists or refresh fails.
    """
    # Get cloud_id from WorkspaceIntegration config
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.JIRA,
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if not integration or not integration.config:
        raise JiraOAuthError("No Jira integration found for this workspace")

    cloud_id = integration.config.get("cloud_id")
    if not cloud_id:
        raise JiraOAuthError("No Jira cloud_id found in integration config")

    # Check if token is still valid
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.provider == Provider.JIRA,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise JiraOAuthError("No Jira OAuth token found for this workspace")

    # Check if token is still valid (with 5 min buffer)
    if oauth_token.token_expires_at:
        expires_at = (
            oauth_token.token_expires_at.replace(tzinfo=None)
            if oauth_token.token_expires_at.tzinfo
            else oauth_token.token_expires_at
        )
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expires_at > (now_utc + TOKEN_REFRESH_BUFFER):
            access_name = token_name(Provider.JIRA, workspace_id, "access")
            current_token = await read_token(session, access_name)
            if current_token:
                return current_token, cloud_id

    # Token expired or expiring soon, refresh it
    new_token = await refresh_access_token(session, workspace_id, settings)
    return new_token, cloud_id


async def disconnect(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    """Disconnect Jira integration.

    Soft-deletes the OAuthToken, deletes Vault secrets, and marks
    WorkspaceIntegration as disconnected. Existing issue data is preserved.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
        user_id: User who initiated the disconnect.
    """
    access_name = token_name(Provider.JIRA, workspace_id, "access")
    refresh_name = token_name(Provider.JIRA, workspace_id, "refresh")
    await disconnect_provider(
        session, workspace_id, user_id, Provider.JIRA,
        vault_token_names=[access_name, refresh_name],
    )


async def _mark_integration_error(session: AsyncSession, workspace_id: UUID) -> None:
    """Mark the Jira workspace integration status as 'error'.

    Called when token refresh fails.
    """
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.JIRA,
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "error"
        await session.commit()
