"""Telegram integration endpoints.

Phase 40 (shared-bot model):
- POST /api/telegram/pairing-code (authenticated): mint a 16-char base64url
  pairing code for the user's workspace; returns {code, deep_link, expires_at}.
- POST /api/telegram/webhook (no path param): global webhook for the shared
  @ContextOSBot. Dispatches by update shape -- my_chat_member -> bookkeeping,
  /start@bot <code> in groups -> claim_chat (BEFORE ingestion path),
  private/unmapped chats -> dropped silently, mapped chats -> existing
  process_telegram_update. Workspace is resolved from chat_id -- never a
  path-param.

The Phase-26 routes (/connect, /disconnect, /sync, /sync/status, and
/webhook/{workspace_id}) were removed in Plan 40-03 alongside the
per-workspace Telethon sync path.
"""

import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import async_session, get_session
from src.dependencies import UserContext, get_current_user
from src.models.telegram import TelegramChatWorkspace
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

    If the workspace already has at least one active chat mapping
    (`removed_at IS NULL`), responds 409 with `chat_count` so the UI can
    surface "already connected" instead of opening Telegram. Prevents the
    multi-engineer onboarding case where a teammate already paired the
    workspace and a second engineer's pairing UI would otherwise hang
    on "Waiting…" until the 15-min TTL expired.
    """
    count_stmt = select(func.count()).select_from(TelegramChatWorkspace).where(
        TelegramChatWorkspace.workspace_id == user.workspace_id,
        TelegramChatWorkspace.removed_at.is_(None),
    )
    chat_count = (await session.execute(count_stmt)).scalar_one()
    if chat_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "already_connected",
                "message": "Workspace already has Telegram chat(s) paired",
                "chat_count": chat_count,
            },
        )

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
