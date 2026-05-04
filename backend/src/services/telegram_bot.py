"""Telegram Bot API helper.

Phase 40 reduces this module to the single primitive the dispatcher and
pairing service still need: a thin async wrapper around the Bot API
HTTP endpoint that raises on `ok: false` responses.

The Phase-26 helpers (`connect_telegram_bot`, `disconnect_telegram_bot`)
that handled per-workspace BotFather tokens, Vault storage, and
setWebhook/deleteWebhook calls were removed in Plan 40-03 along with the
routes that drove them.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramError(Exception):
    """Raised when a Telegram API call fails."""

    pass


async def telegram_api_call(bot_token: str, method: str, **params) -> dict:
    """Make a Telegram Bot API call.

    Args:
        bot_token: The bot token for authentication.
        method: API method name (e.g. "getMe", "sendMessage").
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
