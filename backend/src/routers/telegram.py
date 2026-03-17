"""Telegram integration endpoints.

Provides connect, disconnect, sync, and webhook endpoints for managing
the Telegram bot integration. The webhook endpoint receives updates
directly from Telegram (no auth) and verifies via secret_token header.
"""

import hmac
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.sync_adapter import emit_activity, get_cursor_status
from src.services.telegram_bot import TelegramError, connect_telegram_bot, disconnect_telegram_bot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/connect")
async def connect(
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Connect Telegram bot integration with a bot token.

    Validates the token by calling Telegram getMe API, stores it in Vault,
    and registers the webhook. Automatically triggers history sync in background
    (Telethon for full history if configured, otherwise Bot API getUpdates drain).
    Accepts JSON body: {"bot_token": "..."}
    """
    body = await request.json()
    # SECURITY: bot_token must never be logged
    bot_token = body.get("bot_token", "")

    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bot_token is required",
        )

    try:
        result = await connect_telegram_bot(
            session, user.workspace_id, user.user_id, bot_token, get_settings()
        )
        await emit_activity(
            session, user.workspace_id, "integration_connected",
            metadata={"integration": "telegram"},
            actor_id=user.user_id,
        )

        # Always trigger history sync — uses Telethon if configured,
        # otherwise falls back to Bot API getUpdates drain
        background_tasks.add_task(
            _run_history_sync_background, user.workspace_id
        )

        return {"status": "connected", "bot_username": result.get("username")}
    except TelegramError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/sync", status_code=202)
async def start_sync(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger Telegram message history sync.

    Uses Telethon (MTProto) for full history if TELEGRAM_API_ID and
    TELEGRAM_API_HASH are configured. Otherwise falls back to Bot API
    getUpdates drain (limited to pending messages only).

    Returns 202 immediately; sync runs in background.
    """
    # Check if already syncing
    cursor_status = await get_cursor_status(session, user.workspace_id, "telegram")
    if cursor_status.get("sync_status") == "syncing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram sync already in progress",
        )

    background_tasks.add_task(_run_history_sync_background, user.workspace_id)
    return {"status": "sync_started"}


@router.get("/sync/status")
async def sync_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get current Telegram sync status."""
    return await get_cursor_status(session, user.workspace_id, "telegram")


@router.post("/disconnect")
async def disconnect(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect Telegram bot integration.

    Removes the webhook, deletes the bot token from Vault,
    and marks the integration as disconnected.
    """
    await disconnect_telegram_bot(session, user.workspace_id)
    await emit_activity(
        session, user.workspace_id, "integration_disconnected",
        metadata={"integration": "telegram"},
        actor_id=user.user_id,
    )
    return {"status": "disconnected"}


@router.post("/webhook/{workspace_id}")
async def webhook(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Receive Telegram webhook updates.

    This endpoint is called directly by Telegram servers -- no JWT auth.
    Authenticates via X-Telegram-Bot-Api-Secret-Token header instead.
    Dispatches processing to a background task for fast 200 response.
    """
    settings = get_settings()

    # Verify secret token header
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(
        secret_header, settings.TELEGRAM_WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret token",
        )

    payload = await request.json()

    background_tasks.add_task(_process_update_background, payload, workspace_id)
    return {"ok": True}


async def _run_history_sync_background(workspace_id: uuid.UUID) -> None:
    """Run Telegram history sync in background task."""
    from src.services.telegram_sync import run_telegram_history_sync

    try:
        await run_telegram_history_sync(workspace_id)
    except Exception:
        logger.exception(
            "telegram_history_sync_error workspace=%s", workspace_id
        )


async def _process_update_background(payload: dict, workspace_id: str | uuid.UUID) -> None:
    """Process a Telegram update in the background.

    Creates its own database session for isolation (same pattern as
    Fathom _poll_background).
    """
    from src.db import async_session
    from src.services.telegram_events import process_telegram_update

    ws_uuid = workspace_id if isinstance(workspace_id, uuid.UUID) else uuid.UUID(workspace_id)
    async with async_session() as session:
        try:
            await process_telegram_update(session, ws_uuid, payload)
        except Exception:
            logger.exception(
                "telegram_bg_error workspace=%s payload_keys=%s",
                workspace_id,
                list(payload.keys()),
            )
            await session.rollback()
