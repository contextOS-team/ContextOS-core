"""Slack OAuth2 V2 lifecycle service.

Handles authorization URL generation, code exchange, disconnect, and
bot token retrieval. All token values are stored encrypted in Supabase
Vault -- never in plain text in the DB.

Mirrors the Linear OAuth pattern from linear_oauth.py but adapted for
Slack's OAuth V2 flow:
- Bot tokens do NOT expire and have NO refresh tokens.
- Token exchange uses oauth.v2.access endpoint.
- Team info (id, name) comes from the token exchange response.
"""

from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.models.integration import Provider
from src.services.oauth_common import (
    disconnect_provider,
    upsert_oauth_token,
    upsert_workspace_integration,
)
from src.services.vault import read_token, store_token, token_name

# Slack OAuth V2 endpoints
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Bot scopes for reading channel messages and user info
SLACK_BOT_SCOPES = "channels:read,channels:history,groups:read,groups:history,users:read"


class SlackOAuthError(Exception):
    """Raised when a Slack OAuth operation fails."""



def build_auth_url(state: str, settings: Settings) -> str:
    """Construct the Slack OAuth V2 authorization URL.

    Args:
        state: Pre-signed state parameter (use _sign_state to create).
        settings: Application settings with Slack OAuth config.

    Returns:
        Full authorization URL to redirect the user to.
    """
    params = {
        "client_id": settings.SLACK_CLIENT_ID,
        "redirect_uri": settings.slack_redirect_uri,
        "scope": SLACK_BOT_SCOPES,
        "user_scope": "",
        "state": state,
    }
    query = urlencode(params)
    return f"{SLACK_AUTHORIZE_URL}?{query}"


async def exchange_code(
    code: str,
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: Settings,
) -> dict:
    """Exchange an authorization code for a Slack bot token.

    Stores the bot token encrypted in Vault, creates/updates OAuthToken
    and WorkspaceIntegration records.

    Slack bot tokens do NOT expire and do NOT have refresh tokens.

    Args:
        code: Authorization code from Slack callback.
        session: Async database session.
        workspace_id: Workspace to associate the integration with.
        user_id: User who initiated the OAuth flow.
        settings: Application settings.

    Returns:
        Dict with team info: {"id": str, "name": str}

    Raises:
        SlackOAuthError: If code exchange fails.
    """
    # Exchange code for bot token via Slack's oauth.v2.access
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SLACK_TOKEN_URL,
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.slack_redirect_uri,
            },
        )

    if response.status_code != 200:
        raise SlackOAuthError(f"Token exchange HTTP error: {response.text}")

    data = response.json()

    # Slack API returns ok: true/false in the response body
    if not data.get("ok"):
        error = data.get("error", "unknown_error")
        raise SlackOAuthError(f"Slack token exchange failed: {error}")

    # Extract bot token and team info
    access_token_value = data["access_token"]
    team_id = data.get("team", {}).get("id", "")
    team_name = data.get("team", {}).get("name", "")

    # Store bot token in Vault (encrypted at rest)
    bot_token_name = token_name(Provider.SLACK, workspace_id, "bot_access")
    await store_token(session, bot_token_name, access_token_value)

    await upsert_oauth_token(
        session, workspace_id, user_id, Provider.SLACK,
        access_token_name=bot_token_name,
        token_expires_at=None,
        scopes=SLACK_BOT_SCOPES.split(","),
    )

    await upsert_workspace_integration(
        session, workspace_id, Provider.SLACK,
        external_id=team_id,
        config={"external_name": team_name} if team_name else None,
    )

    await session.commit()

    return {"id": team_id, "name": team_name}


async def disconnect(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    """Disconnect Slack integration.

    Soft-deletes the OAuthToken, deletes Vault secrets, and marks
    WorkspaceIntegration as disconnected. Existing message data is preserved.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
        user_id: User who initiated the disconnect.
    """
    bot_token_name_val = token_name(Provider.SLACK, workspace_id, "bot_access")
    await disconnect_provider(
        session, workspace_id, user_id, Provider.SLACK,
        vault_token_names=[bot_token_name_val],
    )


async def get_bot_token(
    session: AsyncSession,
    workspace_id: UUID,
) -> str:
    """Read the Slack bot token from Vault.

    Slack bot tokens do not expire, so no refresh logic is needed.
    Simply reads the encrypted token from Vault.

    Args:
        session: Async database session.
        workspace_id: Workspace to get the bot token for.

    Returns:
        The decrypted bot token string.

    Raises:
        SlackOAuthError: If no bot token is found.
    """
    bot_token_name_val = token_name(Provider.SLACK, workspace_id, "bot_access")
    token_value = await read_token(session, bot_token_name_val)

    if not token_value:
        raise SlackOAuthError("No Slack bot token found for this workspace")

    return token_value
