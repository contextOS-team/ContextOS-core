"""Telegram bot token management service.

Handles bot token validation (via getMe), secure storage in Supabase Vault,
webhook registration (setWebhook/deleteWebhook), and integration record management.
"""

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from sqlmodel import select

from src.models.integration import Provider, WorkspaceIntegration
from src.services.oauth_common import upsert_oauth_token, upsert_workspace_integration
from src.services.vault import delete_token, read_token, store_token, token_name

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramError(Exception):
    """Raised when a Telegram API call fails."""

    pass


async def telegram_api_call(bot_token: str, method: str, **params) -> dict:
    """Make a Telegram Bot API call.

    Args:
        bot_token: The bot token for authentication.
        method: API method name (e.g. "getMe", "setWebhook").
        **params: JSON body parameters.

    Returns:
        The "result" field from the Telegram API response.

    Raises:
        TelegramError: If the API call fails.
    """
    url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/{method}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=params)
        data = resp.json()

    if not data.get("ok"):
        description = data.get("description", "Unknown error")
        raise TelegramError(f"Telegram API error: {description}")

    return data.get("result", {})


async def connect_telegram_bot(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    bot_token: str,
    settings,
) -> dict:
    """Validate bot token, store in Vault, set webhook, and create integration records.

    Args:
        session: Async database session.
        workspace_id: Workspace to connect the bot to.
        user_id: User performing the connection.
        bot_token: Telegram bot token from BotFather.
        settings: Application settings (for BACKEND_URL, TELEGRAM_WEBHOOK_SECRET).

    Returns:
        Bot info dict from Telegram getMe API.

    Raises:
        TelegramError: If token is invalid or webhook setup fails.
    """
    # Validate token via getMe
    try:
        bot_info = await telegram_api_call(bot_token, "getMe")
    except TelegramError:
        raise
    except Exception as e:
        raise TelegramError(f"Failed to validate bot token: {e}")

    # Store token in Vault
    vault_name = token_name(Provider.TELEGRAM.value, workspace_id, "bot_token")
    await store_token(session, vault_name, bot_token)

    # Set webhook — needs a public HTTPS URL (use TELEGRAM_WEBHOOK_BASE_URL in dev)
    base_url = settings.TELEGRAM_WEBHOOK_BASE_URL or settings.BACKEND_URL
    webhook_url = f"{base_url}/api/telegram/webhook/{workspace_id}"
    if webhook_url.startswith("https://"):
        await telegram_api_call(
            bot_token,
            "setWebhook",
            url=webhook_url,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
            allowed_updates=["message", "edited_message"],
        )
    else:
        logger.warning("Skipping Telegram webhook setup — no HTTPS URL available")

    # Create integration records
    await upsert_oauth_token(
        session,
        workspace_id,
        user_id,
        Provider.TELEGRAM,
        access_token_name=vault_name,
    )
    await upsert_workspace_integration(
        session,
        workspace_id,
        Provider.TELEGRAM,
        external_id=str(bot_info.get("id", "")),
        config={
            "bot_username": bot_info.get("username"),
            "external_name": f"@{bot_info.get('username', '')}",
        },
    )

    await session.commit()
    logger.info(
        "Connected Telegram bot @%s for workspace %s",
        bot_info.get("username"),
        workspace_id,
    )
    return bot_info


async def disconnect_telegram_bot(
    session: AsyncSession,
    workspace_id: UUID,
) -> None:
    """Remove webhook, delete token from Vault, and mark integration as disconnected.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
    """
    vault_name = token_name(Provider.TELEGRAM.value, workspace_id, "bot_token")
    bot_token = await read_token(session, vault_name)

    # Unregister webhook if we still have the token
    if bot_token:
        try:
            await telegram_api_call(bot_token, "deleteWebhook")
        except TelegramError:
            logger.warning(
                "Failed to delete webhook for workspace %s (token may be revoked)",
                workspace_id,
            )

    # Remove token from Vault
    await delete_token(session, vault_name)

    # Mark integration as disconnected
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.TELEGRAM,
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()
    if integration:
        integration.status = "disconnected"

    await session.commit()
    logger.info("Disconnected Telegram bot for workspace %s", workspace_id)
