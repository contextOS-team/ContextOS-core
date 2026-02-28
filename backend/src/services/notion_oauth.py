"""Notion OAuth2 lifecycle service.

Handles authorization URL generation, code exchange with refresh token,
token refresh, disconnect, and access token retrieval. All token values
stored encrypted in Supabase Vault.

Notion OAuth differences from other providers:
- Token exchange uses HTTP Basic Auth (base64(client_id:client_secret))
- Response includes workspace_id, workspace_name, and bot_id
- Access tokens are refreshable (unlike Slack bot tokens)
- Authorization URL uses owner=user parameter
"""

import base64
import logging
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import src.config as config_module
from src.models.integration import OAuthToken, Provider
from src.services.oauth_common import (
    disconnect_provider,
    upsert_oauth_token,
    upsert_workspace_integration,
)
from src.services.vault import read_token, store_token, token_name

logger = logging.getLogger(__name__)

# Notion OAuth endpoints
NOTION_AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"


class NotionOAuthError(Exception):
    """Raised when a Notion OAuth operation fails."""


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    """Build HTTP Basic Auth header value from client credentials."""
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def build_auth_url(state: str, settings) -> str:
    """Construct the Notion OAuth authorization URL.

    Args:
        state: Pre-signed state parameter (use sign_oauth_state to create).
        settings: Application settings with Notion OAuth config.

    Returns:
        Full authorization URL to redirect the user to.
    """
    params = {
        "client_id": settings.NOTION_CLIENT_ID,
        "redirect_uri": settings.notion_redirect_uri,
        "response_type": "code",
        "owner": "user",
        "state": state,
    }
    query = urlencode(params)
    return f"{NOTION_AUTHORIZE_URL}?{query}"


async def exchange_code(
    code: str,
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings,
) -> dict:
    """Exchange an authorization code for Notion access and refresh tokens.

    Stores tokens encrypted in Vault, creates/updates OAuthToken and
    WorkspaceIntegration records.

    Notion token exchange uses HTTP Basic Auth (base64 of client_id:client_secret)
    and returns workspace info (workspace_id, workspace_name, bot_id).

    Notion tokens do NOT have a fixed expiry (long-lived but refreshable).

    Args:
        code: Authorization code from Notion callback.
        session: Async database session.
        workspace_id: Workspace to associate the integration with.
        user_id: User who initiated the OAuth flow.
        settings: Application settings.

    Returns:
        Dict with workspace info: {"workspace_id": str, "workspace_name": str}

    Raises:
        NotionOAuthError: If code exchange fails.
    """
    auth_header = _basic_auth_header(settings.NOTION_CLIENT_ID, settings.NOTION_CLIENT_SECRET)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            NOTION_TOKEN_URL,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.notion_redirect_uri,
            },
        )

    if response.status_code != 200:
        raise NotionOAuthError(f"Token exchange failed: {response.text}")

    data = response.json()

    access_token_value = data.get("access_token")
    refresh_token_value = data.get("refresh_token")
    notion_ws_id = data.get("workspace_id", "")
    ws_name = data.get("workspace_name", "")
    bot_id = data.get("bot_id", "")

    if not access_token_value:
        raise NotionOAuthError("No access_token in Notion token response")

    # Store tokens in Vault (encrypted at rest)
    access_name = token_name(Provider.NOTION, workspace_id, "access")
    await store_token(session, access_name, access_token_value)

    refresh_name = token_name(Provider.NOTION, workspace_id, "refresh")
    if refresh_token_value:
        await store_token(session, refresh_name, refresh_token_value)

    # Upsert OAuthToken record (stores Vault secret names, NOT actual tokens)
    # Notion tokens are long-lived with no fixed expiry
    await upsert_oauth_token(
        session,
        workspace_id,
        user_id,
        Provider.NOTION,
        access_token_name=access_name,
        refresh_token_name=refresh_name if refresh_token_value else None,
        token_expires_at=None,
        metadata={"bot_id": bot_id},
    )

    # Upsert WorkspaceIntegration
    await upsert_workspace_integration(
        session,
        workspace_id,
        Provider.NOTION,
        external_id=notion_ws_id,
        config={"external_name": ws_name} if ws_name else None,
    )

    await session.commit()

    return {"workspace_id": notion_ws_id, "workspace_name": ws_name}


async def refresh_access_token(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings,
) -> str:
    """Refresh the Notion access token using the stored refresh token.

    Reads the refresh token from Vault, exchanges it for a new access token
    via Notion's token endpoint (using HTTP Basic Auth), and updates Vault
    with the new tokens.

    Args:
        session: Async database session.
        workspace_id: Workspace whose token to refresh.
        user_id: User who owns the token.
        settings: Application settings.

    Returns:
        The new access token value.

    Raises:
        NotionOAuthError: If no refresh token exists or refresh fails.
    """
    # Read refresh token from Vault
    refresh_name = token_name(Provider.NOTION, workspace_id, "refresh")
    refresh_token_value = await read_token(session, refresh_name)

    if not refresh_token_value:
        raise NotionOAuthError("No Notion refresh token available")

    auth_header = _basic_auth_header(settings.NOTION_CLIENT_ID, settings.NOTION_CLIENT_SECRET)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                NOTION_TOKEN_URL,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                },
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token_value,
                },
            )

        if response.status_code != 200:
            raise NotionOAuthError(f"Token refresh failed: {response.text}")

        data = response.json()
    except httpx.HTTPError as e:
        raise NotionOAuthError(f"Token refresh HTTP error: {e}") from e

    new_access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token")

    if not new_access_token:
        raise NotionOAuthError("No access_token in refresh response")

    # Store new tokens in Vault (overwrite)
    access_name = token_name(Provider.NOTION, workspace_id, "access")
    await store_token(session, access_name, new_access_token)

    if new_refresh_token:
        await store_token(session, refresh_name, new_refresh_token)

    # Update OAuthToken record
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == Provider.NOTION,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.access_token = access_name
        if new_refresh_token:
            oauth_token.refresh_token = refresh_name

    await session.commit()

    return new_access_token


async def get_valid_access_token(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings,
) -> str:
    """Get a valid Notion access token.

    Notion tokens are long-lived, so this simply reads from Vault.
    If the token fails during API calls, the caller can trigger refresh.

    Args:
        session: Async database session.
        workspace_id: Workspace to get token for.
        user_id: User who owns the token.
        settings: Application settings.

    Returns:
        A valid access token string.

    Raises:
        NotionOAuthError: If no token exists.
    """
    access_name = token_name(Provider.NOTION, workspace_id, "access")
    token_value = await read_token(session, access_name)

    if not token_value:
        raise NotionOAuthError("No Notion access token found for this workspace")

    return token_value


async def disconnect(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    """Disconnect Notion integration.

    Soft-deletes the OAuthToken, deletes Vault secrets, and marks
    WorkspaceIntegration as disconnected. Existing page data is preserved.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
        user_id: User who initiated the disconnect.
    """
    access_name = token_name(Provider.NOTION, workspace_id, "access")
    refresh_name = token_name(Provider.NOTION, workspace_id, "refresh")
    await disconnect_provider(
        session,
        workspace_id,
        user_id,
        Provider.NOTION,
        vault_token_names=[access_name, refresh_name],
    )
