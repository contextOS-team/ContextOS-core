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

from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import OAuthToken, WorkspaceIntegration
from src.services.oauth_common import OAuthStateError, sign_oauth_state, verify_oauth_state
from src.services.vault import delete_token, read_token, store_token, token_name

# Slack OAuth V2 endpoints
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Bot scopes for reading channel messages and user info
SLACK_BOT_SCOPES = "channels:read,channels:history,groups:read,groups:history,users:read"


class SlackOAuthError(Exception):
    """Raised when a Slack OAuth operation fails."""


def _sign_state(workspace_id: UUID, secret: str) -> str:
    """Create a signed state parameter. Delegates to shared utility."""
    return sign_oauth_state(workspace_id, secret)


def _verify_state(state: str, secret: str) -> UUID:
    """Verify a signed state parameter. Wraps shared utility with provider error."""
    try:
        return verify_oauth_state(state, secret)
    except OAuthStateError as e:
        raise SlackOAuthError(str(e)) from e


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
    query = "&".join(f"{k}={v}" for k, v in params.items())
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
    bot_token_name = token_name("slack", workspace_id, "bot_access")
    await store_token(session, bot_token_name, access_token_value)

    # Upsert OAuthToken record (stores Vault secret name, NOT actual token)
    # Query WITHOUT deleted_at filter — a soft-deleted row still holds the
    # unique constraint slot, so we must reuse it on reconnect.
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "slack",
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.access_token = bot_token_name
        oauth_token.refresh_token = None  # Slack bot tokens have no refresh
        oauth_token.token_expires_at = None  # Slack bot tokens don't expire
        oauth_token.scopes = SLACK_BOT_SCOPES.split(",")
        oauth_token.deleted_at = None  # un-soft-delete on reconnect
    else:
        oauth_token = OAuthToken(
            workspace_id=workspace_id,
            user_id=user_id,
            provider="slack",
            access_token=bot_token_name,
            refresh_token=None,
            token_expires_at=None,
            scopes=SLACK_BOT_SCOPES.split(","),
        )
        session.add(oauth_token)

    # Upsert WorkspaceIntegration
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "connected"
        integration.external_id = team_id
        integration.config = {**integration.config, "external_name": team_name} if team_name else integration.config
        integration.connected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        integration.deleted_at = None
    else:
        integration = WorkspaceIntegration(
            workspace_id=workspace_id,
            provider="slack",
            status="connected",
            external_id=team_id,
            config={"external_name": team_name} if team_name else {},
            connected_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(integration)

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
    # Soft-delete OAuthToken
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "slack",
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Delete Vault secret
    bot_token_name_val = token_name("slack", workspace_id, "bot_access")
    await delete_token(session, bot_token_name_val)

    # Mark integration as disconnected
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "disconnected"

    await session.commit()


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
    bot_token_name_val = token_name("slack", workspace_id, "bot_access")
    token_value = await read_token(session, bot_token_name_val)

    if not token_value:
        raise SlackOAuthError("No Slack bot token found for this workspace")

    return token_value
