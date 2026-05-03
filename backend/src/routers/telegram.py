"""Telegram integration endpoints.

Provides connect, disconnect, sync, and webhook endpoints for managing
the Telegram bot integration. The webhook endpoint receives updates
directly from Telegram (no auth) and verifies via secret_token header.

Phase 40 additions (this plan):
- POST /api/telegram/pairing-code (authenticated): mint a 16-char base64url
  pairing code for the user's workspace; returns {code, deep_link, expires_at}.
- POST /api/telegram/webhook (no path param): global webhook for the shared
  @ContextOSBot. Dispatches by update shape -- my_chat_member -> bookkeeping,
  /start@bot <code> in groups -> claim_chat (BEFORE ingestion path),
  private/unmapped chats -> dropped silently, mapped chats -> existing
  process_telegram_update. Workspace is resolved from chat_id -- never a
  path-param.

The legacy /webhook/{workspace_id}, /connect, /disconnect, /sync, /sync/status
routes remain in place during this plan so it stays independently mergeable.
Plan 03 deletes them in the cutover commit.
"""

import hmac
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import async_session, get_session
from src.dependencies import UserContext, get_current_user
from src.services.sync_adapter import emit_activity, get_cursor_status
from src.services.telegram_bot import (
    TelegramError,
    connect_telegram_bot,
    disconnect_telegram_bot,
)
from src.services.telegram_events import process_telegram_update
from src.services.telegram_pairing import (
    claim_chat,
    generate_pairing_code,
    handle_my_chat_member,
    resolve_workspace_for_chat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


# ---------------------------------------------------------------------------
# Phase 40: pairing-code endpoint (authenticated, mints a fresh code)
# ---------------------------------------------------------------------------


@router.post("/pairing-code")
async def create_pairing_code(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mint a 16-char base64url pairing code (~15min TTL) for the user's workspace.

    Deletes any unexpired prior codes for this workspace before insert
    (one-active-code-per-workspace invariant; Pitfall 5). Returns:
        {code, deep_link, expires_at (ISO 8601 string)}
    """
    result = await generate_pairing_code(session, user.workspace_id, user.user_id)
    # Coerce datetime -> ISO 8601 string for JSON serialization.
    return {
        "code": result["code"],
        "deep_link": result["deep_link"],
        "expires_at": result["expires_at"].isoformat(),
    }


# ---------------------------------------------------------------------------
# Phase 40: global webhook (no path param) + dispatcher
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def webhook_global(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Global Telegram webhook -- receives every update for the shared bot.

    Dispatches by update shape:
      - my_chat_member -> handle_my_chat_member (bookkeeping)
      - message.text starts with /start in group/supergroup -> claim_chat
        (CRITICAL: BEFORE the ingestion path; Pitfall 2)
      - private chat -> drop silently (DMs are out of scope)
      - else -> resolve workspace_id by chat_id, then process_telegram_update.
        Unmapped chats are dropped silently with INFO log.

    Workspace is NEVER read from a path param (Phase-26 model removed).
    The 200 response is sent before processing starts -- exceptions in the
    background task are logged but never bubble up to Telegram.
    """
    settings = get_settings()
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(
        secret_header, settings.TELEGRAM_WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token"
        )

    payload = await request.json()
    background_tasks.add_task(_dispatch_global_update, payload)
    return {"ok": True}


async def _dispatch_global_update(payload: dict) -> None:
    """Background dispatcher for the global webhook (one DB session per call).

    Branch order is load-bearing -- claim_chat MUST run BEFORE
    process_telegram_update for /start@bot <code> messages, otherwise the
    pairing message gets ingested as content (Pitfall 2).
    """
    async with async_session() as session:
        try:
            # 1) my_chat_member (added/kicked/left/promoted)
            if "my_chat_member" in payload:
                await handle_my_chat_member(session, payload["my_chat_member"])
                return

            message = payload.get("message") or payload.get("edited_message")
            if not message:
                return

            chat = message.get("chat", {}) or {}
            chat_id = chat.get("id")
            chat_type = chat.get("type")
            text = message.get("text", "") or ""

            # 2) Private chats are out of scope (DMs are deferred per ROADMAP).
            if chat_type == "private":
                logger.info("telegram_private_chat_ignored chat_id=%s", chat_id)
                return

            # 3) CRITICAL: pairing claim BEFORE ingestion (Pitfall 2).
            if text.startswith("/start") and chat_type in ("group", "supergroup"):
                await claim_chat(session, message)
                return

            # 4) Resolve workspace from chat mapping; drop unmapped silently.
            ws_id = await resolve_workspace_for_chat(session, chat_id)
            if ws_id is None:
                logger.info("telegram_unmapped_chat chat_id=%s", chat_id)
                return

            await process_telegram_update(session, ws_id, payload)
        except Exception:
            logger.exception(
                "telegram_dispatch_error payload_keys=%s", list(payload.keys())
            )
            try:
                await session.rollback()
            except Exception:
                logger.exception("telegram_dispatch_rollback_failed")


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
