"""Phase 40: Pairing-code lifecycle and chat-claim logic for the shared @ContextOSBot.

Replaces the Phase-26 connect_telegram_bot/disconnect_telegram_bot flow.

The shared bot has one webhook URL (`/api/telegram/webhook`); workspace
resolution happens via `chat_id` lookup in `telegram_chat_workspace`.
This service owns:

- `generate_pairing_code(session, workspace_id, user_id)`: mint a 16-char
  base64url code (~96 bits entropy), TTL = 15 minutes. Deletes any
  unexpired prior codes for the workspace before INSERT (one-active-code
  invariant; Pitfall 5).
- `claim_chat(session, message)`: parse `/start[@bot] <code>` from a
  group/supergroup message, atomically redeem the code (DELETE…RETURNING),
  insert the chat→workspace mapping (ON CONFLICT DO NOTHING), and reply
  in chat. Cross-workspace and same-workspace re-claim are no-ops that
  do NOT burn the code.
- `handle_my_chat_member(session, update)`: soft-delete the mapping when
  the bot is `left`/`kicked`. Always logs at INFO for visibility (per CONTEXT).
- `resolve_workspace_for_chat(session, chat_id)`: SELECT workspace_id
  from active mappings only (`removed_at IS NULL`).
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.telegram import TelegramChatWorkspace, TelegramPairingCode
from src.services.sync_adapter import emit_activity
from src.services.telegram_bot import TelegramError, telegram_api_call

logger = logging.getLogger(__name__)

# Pairing-code TTL (matches CONTEXT-locked 15-minute window)
PAIRING_TTL_MINUTES = 15

# Default dashboard URL surfaced in bot replies. The settings module does not
# yet expose a frontend URL field, so we hardcode here. Callers wanting to
# override at deploy time can wire a settings field in a follow-up.
_DASHBOARD_URL_DEFAULT = "https://contextos.pro/dashboard/settings?tab=integrations"


class ClaimResult(str, Enum):
    """Outcome of a `/start@bot <code>` claim attempt."""

    CLAIMED = "claimed"
    NOOP = "noop"
    ALREADY_CLAIMED_BY_OTHER = "already_claimed_by_other"
    INVALID_CODE = "invalid_code"
    IGNORE_PRIVATE = "ignore_private"


# ---------------------------------------------------------------------------
# Pairing code lifecycle
# ---------------------------------------------------------------------------


async def generate_pairing_code(
    session: AsyncSession, workspace_id: UUID, user_id: UUID
) -> dict[str, Any]:
    """Mint a fresh 16-char base64url pairing code for a workspace.

    Deletes any unexpired prior codes for this workspace BEFORE inserting the
    new one -- enforces the "one-active-code-per-workspace" invariant
    (Pitfall 5: a sibling user's regenerate must invalidate the prior code).

    Returns:
        dict with keys ``code``, ``deep_link``, ``expires_at`` (timezone-aware UTC).
    """
    # 1. DELETE unexpired codes for this workspace (single transaction).
    await session.execute(
        delete(TelegramPairingCode).where(
            TelegramPairingCode.workspace_id == workspace_id,
            TelegramPairingCode.expires_at > func.now(),
        )
    )

    # 2. INSERT a new code. secrets.token_urlsafe(12) -> 16 base64url chars.
    code = secrets.token_urlsafe(12)
    expires_at = datetime.now(UTC) + timedelta(minutes=PAIRING_TTL_MINUTES)
    session.add(
        TelegramPairingCode(
            code=code,
            workspace_id=workspace_id,
            created_by=user_id,
            expires_at=expires_at,
        )
    )
    await session.commit()

    settings = get_settings()
    if not settings.TELEGRAM_BOT_USERNAME:
        raise RuntimeError(
            "TELEGRAM_BOT_USERNAME is not configured; cannot build pairing deep link"
        )
    return {
        "code": code,
        "deep_link": f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?startgroup={code}",
        "expires_at": expires_at,
    }


async def resolve_workspace_for_chat(
    session: AsyncSession, chat_id: int
) -> UUID | None:
    """Return workspace_id for an active chat mapping, or None.

    Active = `removed_at IS NULL`. Soft-deleted mappings (kicked/left)
    are NOT returned -- they exist to preserve historical telegram_messages
    rows but should never resolve incoming updates.
    """
    return await session.scalar(
        select(TelegramChatWorkspace.workspace_id).where(
            TelegramChatWorkspace.chat_id == chat_id,
            TelegramChatWorkspace.removed_at.is_(None),  # type: ignore[union-attr]
        )
    )


# ---------------------------------------------------------------------------
# Chat-claim handler
# ---------------------------------------------------------------------------


def _parse_start_payload(text: str) -> str:
    """Extract the payload from `/start[@<bot>] <payload>` text.

    Returns an empty string if the message has no payload.
    """
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


async def claim_chat(session: AsyncSession, message: dict[str, Any]) -> ClaimResult:
    """Process a `/start[@bot] <code>` message in a group or supergroup.

    Flow (check-before-redeem; see PLAN behavior contract):
      1. If chat.type not in ('group', 'supergroup') -> IGNORE_PRIVATE.
      2. Peek the code (no delete) to learn its workspace.
      3. Look up the chat's existing workspace mapping.
      4. If chat is mapped to a DIFFERENT workspace from the code's owner,
         reply 'already paired' and DO NOT burn the code.
      5. If chat is mapped to the SAME workspace as the code's owner,
         return NOOP (idempotent re-claim) and DO NOT burn the code.
      6. Otherwise (chat unmapped): atomically DELETE…RETURNING the code,
         INSERT the mapping ON CONFLICT DO NOTHING, emit activity event,
         commit, send confirmation reply (fail-safe).

    Send-reply failures NEVER roll back the claim (Pitfall 6).
    """
    chat = message.get("chat", {}) or {}
    chat_type = chat.get("type")
    if chat_type not in ("group", "supergroup"):
        return ClaimResult.IGNORE_PRIVATE

    chat_id = chat.get("id")
    if chat_id is None:
        return ClaimResult.IGNORE_PRIVATE
    chat_title = chat.get("title")

    text = message.get("text", "") or ""
    code = _parse_start_payload(text)

    # Step 1: peek the code to learn its workspace WITHOUT burning it.
    peek_stmt = select(
        TelegramPairingCode.workspace_id, TelegramPairingCode.created_by
    ).where(
        TelegramPairingCode.code == code,
        TelegramPairingCode.expires_at > func.now(),
    )
    peek_result = await session.execute(peek_stmt)
    code_record = peek_result.first()

    # Step 2: look up the chat's existing mapping.
    existing_ws = await resolve_workspace_for_chat(session, chat_id)

    if code_record is None:
        # Either invalid, expired, or already burned. Reply once.
        logger.info(
            "telegram_claim_invalid chat_id=%s code_present=%s",
            chat_id,
            bool(code),
        )
        await _send_reply_safe(chat_id, _reply_text(ClaimResult.INVALID_CODE))
        return ClaimResult.INVALID_CODE

    claimer_ws, created_by = code_record

    # Cross-workspace claim attempt -- reject without burning the code.
    if existing_ws is not None and existing_ws != claimer_ws:
        logger.info(
            "telegram_claim_cross_workspace chat_id=%s claimer_ws=%s existing_ws=%s",
            chat_id,
            claimer_ws,
            existing_ws,
        )
        await _send_reply_safe(
            chat_id, _reply_text(ClaimResult.ALREADY_CLAIMED_BY_OTHER)
        )
        return ClaimResult.ALREADY_CLAIMED_BY_OTHER

    # Same-workspace re-claim -- idempotent NOOP, do not burn the code.
    if existing_ws is not None and existing_ws == claimer_ws:
        logger.info(
            "telegram_claim_noop chat_id=%s workspace=%s", chat_id, claimer_ws
        )
        return ClaimResult.NOOP

    # Step 3: fresh claim. Atomically burn the code.
    redeem_stmt = (
        delete(TelegramPairingCode)
        .where(
            TelegramPairingCode.code == code,
            TelegramPairingCode.expires_at > func.now(),
        )
        .returning(TelegramPairingCode.workspace_id)
    )
    redeem_result = await session.execute(redeem_stmt)
    burned = redeem_result.first()
    if burned is None:
        # Race: someone else burned it between peek and delete. Treat as invalid.
        logger.info("telegram_claim_race_lost chat_id=%s", chat_id)
        await _send_reply_safe(chat_id, _reply_text(ClaimResult.INVALID_CODE))
        return ClaimResult.INVALID_CODE

    # Step 4: insert mapping. The PK is chat_id, so a previously-kicked chat
    # leaves a soft-deleted row (removed_at IS NOT NULL) which would block a
    # plain INSERT. ON CONFLICT (chat_id) DO UPDATE ... WHERE removed_at IS
    # NOT NULL re-claims the slot for any workspace once the bot has left;
    # an active mapping (removed_at IS NULL) is left untouched and the
    # statement returns no row, which we treat as a race-loss conflict.
    insert_stmt = (
        pg_insert(TelegramChatWorkspace)
        .values(
            chat_id=chat_id,
            workspace_id=claimer_ws,
            chat_title=chat_title,
            chat_type=chat_type,
            paired_by=created_by,
        )
        .on_conflict_do_update(
            index_elements=["chat_id"],
            set_={
                "workspace_id": claimer_ws,
                "chat_title": chat_title,
                "chat_type": chat_type,
                "paired_by": created_by,
                "paired_at": func.now(),
                "removed_at": None,
            },
            where=TelegramChatWorkspace.removed_at.is_not(None),
        )
        .returning(TelegramChatWorkspace.chat_id)
    )
    insert_result = await session.execute(insert_stmt)
    inserted = insert_result.first() is not None

    # Emit activity event before commit so it lands in the same transaction
    # (emit_activity uses begin_nested + fail-silent under the hood).
    await emit_activity(
        session,
        claimer_ws,
        "integration_connected",
        metadata={
            "integration": "telegram",
            "chat_title": chat_title,
            "chat_id": chat_id,
        },
        actor_id=created_by,
    )
    await session.commit()

    if inserted:
        logger.info(
            "telegram_claim_success chat_id=%s workspace=%s", chat_id, claimer_ws
        )
        await _send_reply_safe(
            chat_id,
            _reply_text(ClaimResult.CLAIMED, chat_title=chat_title),
        )
        return ClaimResult.CLAIMED

    # Race: chat became mapped between our resolve_workspace_for_chat and
    # INSERT. Code is already burned (best-effort message to the group).
    logger.warning(
        "telegram_claim_insert_conflict chat_id=%s workspace=%s "
        "(code burned but mapping already existed)",
        chat_id,
        claimer_ws,
    )
    await _send_reply_safe(
        chat_id, _reply_text(ClaimResult.ALREADY_CLAIMED_BY_OTHER)
    )
    return ClaimResult.ALREADY_CLAIMED_BY_OTHER


# ---------------------------------------------------------------------------
# my_chat_member handler
# ---------------------------------------------------------------------------


async def handle_my_chat_member(
    session: AsyncSession, update: dict[str, Any]
) -> None:
    """Bookkeeping for ChatMemberUpdated events on the bot's own status.

    On `left`/`kicked`: soft-delete the mapping (set `removed_at = now()`)
    and emit `integration_disconnected` activity for the workspace that
    owned it. Other statuses (`member`, `administrator`, `restricted`,
    `creator`) are logged but do not change DB state.

    Per CONTEXT, every my_chat_member event is logged at INFO level for
    visibility (helps debug "bot was muted in group X" reports).
    """
    chat = update.get("chat", {}) or {}
    chat_id = chat.get("id")
    new_member = update.get("new_chat_member", {}) or {}
    new_status = new_member.get("status")

    logger.info(
        "telegram_my_chat_member chat_id=%s new_status=%s", chat_id, new_status
    )

    if new_status not in ("left", "kicked"):
        return
    if chat_id is None:
        return

    # Resolve workspace BEFORE soft-deleting so we can emit the disconnect event.
    ws_id = await resolve_workspace_for_chat(session, chat_id)

    await session.execute(
        sa_update(TelegramChatWorkspace)
        .where(TelegramChatWorkspace.chat_id == chat_id)
        .values(removed_at=func.now())
    )
    await session.commit()

    if ws_id is not None:
        await emit_activity(
            session,
            ws_id,
            "integration_disconnected",
            metadata={
                "integration": "telegram",
                "chat_id": chat_id,
                "reason": new_status,
            },
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Bot reply helpers (fail-safe)
# ---------------------------------------------------------------------------


async def _send_reply_safe(chat_id: int, text: str) -> None:
    """Send a Telegram reply; swallow any error (Pitfall 6).

    The Realtime UI flip is the user-visible acknowledgement; the bot reply is
    a courtesy. Failure here MUST NOT poison the surrounding DB transaction.
    """
    if not text:
        return
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN_GLOBAL:
        logger.warning(
            "telegram_reply_skipped chat_id=%s reason=no_global_token", chat_id
        )
        return
    try:
        await telegram_api_call(
            settings.TELEGRAM_BOT_TOKEN_GLOBAL,
            "sendMessage",
            chat_id=chat_id,
            text=text,
            disable_web_page_preview=True,
        )
    except TelegramError:
        logger.warning(
            "telegram_reply_failed chat_id=%s (TelegramError)", chat_id, exc_info=True
        )
    except Exception:
        logger.exception("telegram_reply_failed chat_id=%s", chat_id)


def _reply_text(
    result: ClaimResult, *, chat_title: str | None = None
) -> str:
    """Render the in-chat reply text for a given claim outcome.

    Wording is Claude's discretion per CONTEXT. Kept short and link-driven.
    Returns "" for outcomes that should not produce a reply (NOOP, IGNORE_PRIVATE).
    """
    dashboard_url = _DASHBOARD_URL_DEFAULT
    if result == ClaimResult.CLAIMED:
        title_suffix = f" to {chat_title}" if chat_title else ""
        return (
            f"ContextOS connected{title_suffix}. Messages here will be indexed "
            f"for context generation. Manage at {dashboard_url}."
        )
    if result == ClaimResult.INVALID_CODE:
        return (
            f"This pairing link expired or was already used. "
            f"Generate a new one at {dashboard_url}."
        )
    if result == ClaimResult.ALREADY_CLAIMED_BY_OTHER:
        return "This chat is already paired with another ContextOS workspace."
    return ""
