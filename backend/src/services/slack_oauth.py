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

import logging
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import Provider, WorkspaceIntegration
from src.services.oauth_common import (
    disconnect_provider,
    upsert_oauth_token,
    upsert_workspace_integration,
)
from src.services.vault import read_token, store_token, token_name

logger = logging.getLogger(__name__)

# Slack OAuth V2 endpoints
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Bot scopes for reading channel messages, user info, user emails, and canvas/file access
SLACK_BOT_SCOPES = "channels:read,channels:history,groups:read,groups:history,users:read,users:read.email,canvases:read,files:read"

# User scopes -- DM-only per Phase 39 CONTEXT.md lock.
# Channels and groups remain on the bot token via the Events API webhook.
# DO NOT add channels:* or groups:* here -- any expansion requires a new phase.
SLACK_USER_SCOPES = "im:read,im:history,mpim:read,mpim:history,users:read,users:read.email"


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
        "user_scope": SLACK_USER_SCOPES,
        "state": state,
    }
    query = urlencode(params)
    return f"{SLACK_AUTHORIZE_URL}?{query}"


def _extract_tokens(data: dict) -> tuple[str, str | None, str | None, dict]:  # type: ignore[type-arg]
    """Extract bot token, optional user token, optional Slack user id, and team dict.

    Slack's oauth.v2.access response shape:
        {
          "ok": true,
          "access_token": "xoxb-...",        # bot token
          "team": {"id": "T...", "name": "..."},
          "authed_user": {                   # only present when user_scope was requested
            "id": "U...",
            "access_token": "xoxp-...",
            "scope": "..."
          }
        }
    """
    bot = data["access_token"]
    authed = data.get("authed_user") or {}
    return (bot, authed.get("access_token"), authed.get("id"), data.get("team") or {})


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

    # Extract bot token, optional user token, and team info
    bot_token_value, user_token_value, slack_user_id, team = _extract_tokens(data)
    team_id = team.get("id", "")
    team_name = team.get("name", "")

    # Store bot token in Vault (encrypted at rest)
    bot_token_name = token_name(Provider.SLACK, workspace_id, "bot_access")
    await store_token(session, bot_token_name, bot_token_value)

    # Store user token when present. Pre-Phase-39 installs that re-auth without
    # granting user scopes will receive no authed_user.access_token -- keep
    # working but log so we can detect workspaces that still need re-auth.
    if user_token_value:
        user_token_name_v = token_name(Provider.SLACK, workspace_id, "user_access")
        await store_token(session, user_token_name_v, user_token_value)
    else:
        logger.warning(
            "Slack OAuth response missing authed_user.access_token for workspace %s "
            "(user_scope likely empty at authorize time)",
            workspace_id,
        )

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

    # Merge slack_user_id into integration.config without clobbering existing keys
    # (upsert_workspace_integration already merges external_name; re-query and
    # patch so we don't need to change the shared helper's signature).
    if slack_user_id:
        int_stmt = select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.provider == Provider.SLACK,
        )
        int_result = await session.execute(int_stmt)
        integration = int_result.scalar_one_or_none()
        if integration is not None:
            updated_config = dict(integration.config) if integration.config else {}
            updated_config["slack_user_id"] = slack_user_id
            integration.config = updated_config

    await session.commit()

    # Seed Slack roster for identity resolution (fail-silent)
    try:
        from src.services.identity_resolution import fetch_slack_roster, seed_roster

        members = await fetch_slack_roster(session, workspace_id)
        seeded = await seed_roster(session, workspace_id, "slack", members)
        logger.info(
            "Slack roster seeding: %d members for workspace %s",
            seeded,
            workspace_id,
        )
    except Exception:
        logger.warning(
            "Slack roster seeding failed for workspace %s (non-blocking)",
            workspace_id,
            exc_info=True,
        )

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
    user_token_name_v = token_name(Provider.SLACK, workspace_id, "user_access")
    await disconnect_provider(
        session, workspace_id, user_id, Provider.SLACK,
        vault_token_names=[bot_token_name_val, user_token_name_v],
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

    # Fallback: try legacy name format from before the Provider enum fix.
    # Tokens stored before the fix used f"{Provider.SLACK}" which in Python 3.12
    # produces "Provider.SLACK" instead of "slack".
    if not token_value:
        legacy_name = f"oauth_Provider.SLACK_{workspace_id}_bot_access"
        token_value = await read_token(session, legacy_name)
        if token_value:
            # Migrate: store under the correct name and delete the legacy one
            await store_token(session, bot_token_name_val, token_value)
            from src.services.vault import delete_token
            await delete_token(session, legacy_name)
            await session.commit()
            logger.info("Migrated Slack bot token from legacy vault name for workspace %s", workspace_id)

    if not token_value:
        raise SlackOAuthError("No Slack bot token found for this workspace")

    return token_value


async def get_user_token(
    session: AsyncSession,
    workspace_id: UUID,
) -> str:
    """Read the Slack user token from Vault.

    User tokens are new in Phase 39 and have no legacy name fallback.
    Workspaces that connected before Phase 39 will not have a user token
    stored; callers should check `/api/slack/status.needs_reauth` first.

    Args:
        session: Async database session.
        workspace_id: Workspace to get the user token for.

    Returns:
        The decrypted user token string.

    Raises:
        SlackOAuthError: If no user token is found.
    """
    user_token_name_v = token_name(Provider.SLACK, workspace_id, "user_access")
    token_value = await read_token(session, user_token_name_v)

    if not token_value:
        raise SlackOAuthError("No Slack user token found for this workspace")

    return token_value
