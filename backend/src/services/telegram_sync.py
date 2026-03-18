"""Telegram message history sync service.

Two-tier approach:
1. **Bot API (getUpdates)** — Zero config, always available. Before setting the
   webhook, drains pending updates via getUpdates. Limited to unconfirmed
   messages only (typically up to 100 recent ones).
2. **Telethon (MTProto)** — Full history fetch. Requires TELEGRAM_API_ID and
   TELEGRAM_API_HASH from https://my.telegram.org. Fetches up to 30 days of
   chat history from all groups the bot is in.

The connect flow calls drain_pending_updates() automatically.
The /sync endpoint triggers run_telegram_history_sync() which uses Telethon
if available, otherwise falls back to getUpdates drain.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import get_settings
from src.db import async_session
from src.models.integration import Provider
from src.models.telegram import TelegramMessage
from src.services.embedding import queue_embedding_generation
from src.services.embedding_worker import enqueue_embedding_job
from src.services.sync_adapter import (
    SyncRunLogger,
    emit_activity,
    get_or_create_cursor,
    update_cursor_status,
)
from src.services.telegram_bot import telegram_api_call
from src.services.vault import read_token, token_name

logger = logging.getLogger(__name__)

# Backfill window for first Telethon sync
BACKFILL_DAYS = 30
# Messages per flush batch
FLUSH_BATCH_SIZE = 100
# Max messages per chat to prevent runaway syncs
MAX_MESSAGES_PER_CHAT = 1000
# Delay between chat syncs to respect rate limits
RATE_LIMIT_DELAY = 0.3


def _is_telethon_available() -> bool:
    """Check if Telethon and MTProto credentials are configured."""
    settings = get_settings()
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        return False
    try:
        import telethon  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Tier 1: Bot API getUpdates — zero config, always works
# ---------------------------------------------------------------------------

async def drain_pending_updates(
    bot_token: str,
    workspace_id: UUID,
    session: AsyncSession,
) -> int:
    """Drain pending updates via Bot API getUpdates before webhook is set.

    Calls getUpdates in a loop to retrieve all unconfirmed messages the bot
    has received. These are messages Telegram queued but hasn't delivered
    via webhook yet (e.g. messages received while webhook was down).

    This requires NO extra credentials — just the bot token.

    Args:
        bot_token: The bot token for API calls.
        workspace_id: Workspace to store messages in.
        session: Async database session.

    Returns:
        Number of messages ingested.
    """
    total = 0
    offset = 0

    for _ in range(20):  # Safety limit: max 20 iterations (2000 updates)
        try:
            updates = await telegram_api_call(
                bot_token, "getUpdates",
                offset=offset, limit=100, timeout=1,
            )
        except Exception:
            logger.debug("getUpdates call failed, stopping drain", exc_info=True)
            break

        if not updates:
            break

        msg_ids: list[UUID] = []
        for update in updates:
            # Advance offset to acknowledge this update
            offset = update["update_id"] + 1

            message = update.get("message") or update.get("edited_message")
            if not message or not message.get("text"):
                continue

            from_user = message.get("from", {})
            if from_user.get("is_bot", False):
                continue

            msg_uuid = await _upsert_telegram_message(
                session, workspace_id, message
            )
            if msg_uuid:
                msg_ids.append(msg_uuid)
                total += 1

        if msg_ids:
            await session.flush()
            await queue_embedding_generation(
                session, workspace_id, "telegram_message", msg_ids,
            )
            await session.commit()

    if total > 0:
        logger.info(
            "Drained %d pending Telegram updates for workspace %s",
            total, workspace_id,
        )

    return total


# ---------------------------------------------------------------------------
# Tier 2: Telethon (MTProto) — full history, requires api_id/api_hash
# ---------------------------------------------------------------------------

async def run_telegram_history_sync(workspace_id: UUID) -> None:
    """Background task: drain pending Telegram messages for a workspace.

    Uses Bot API getUpdates to capture any pending messages. Telegram bots
    cannot fetch message history (GetHistoryRequest is restricted), so this
    only captures undelivered updates. Real-time messages arrive via webhook.

    Args:
        workspace_id: Workspace to sync Telegram messages for.
    """
    await _run_bot_api_sync(workspace_id)


async def _run_bot_api_sync(workspace_id: UUID) -> None:
    """Fallback sync using Bot API getUpdates (no extra credentials)."""
    async with async_session() as session:
        try:
            await update_cursor_status(
                session, workspace_id, "telegram", "default",
                sync_status="syncing",
            )
            await session.commit()

            vault_name = token_name(
                Provider.TELEGRAM.value, workspace_id, "bot_token"
            )
            bot_token = await read_token(session, vault_name)
            if not bot_token:
                raise ValueError("Bot token not found in vault")

            # Temporarily delete webhook so getUpdates works
            try:
                await telegram_api_call(bot_token, "deleteWebhook")
            except Exception:
                logger.debug("deleteWebhook failed before drain", exc_info=True)

            total = await drain_pending_updates(bot_token, workspace_id, session)

            # Re-set webhook
            settings = get_settings()
            base_url = settings.TELEGRAM_WEBHOOK_BASE_URL or settings.BACKEND_URL
            webhook_url = f"{base_url}/api/telegram/webhook/{workspace_id}"
            if webhook_url.startswith("https://"):
                await telegram_api_call(
                    bot_token, "setWebhook",
                    url=webhook_url,
                    secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
                    allowed_updates=["message", "edited_message"],
                )

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            await update_cursor_status(
                session, workspace_id, "telegram", "default",
                sync_status="complete",
                records_synced=total,
                cursor_value=now.isoformat(),
            )
            await session.commit()

            logger.info(
                "Bot API sync complete for workspace %s: %d messages",
                workspace_id, total,
            )

        except Exception as e:
            logger.exception("Bot API telegram sync failed ws=%s", workspace_id)
            try:
                await session.rollback()
                await update_cursor_status(
                    session, workspace_id, "telegram", "default",
                    sync_status="error",
                    error_message=str(e)[:200],
                )
                await session.commit()
            except Exception:
                pass


async def _run_telethon_sync(workspace_id: UUID) -> None:
    """Full history sync via Telethon MTProto."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    settings = get_settings()
    _sync_t0 = time.monotonic()

    async with SyncRunLogger("telegram", workspace_id) as srl:
        async with async_session() as session:
            try:
                await update_cursor_status(
                    session, workspace_id, "telegram", "default",
                    sync_status="syncing",
                )
                await emit_activity(
                    session, workspace_id, "sync_started",
                    metadata={"integration": "telegram"},
                )
                await session.commit()

                vault_name = token_name(
                    Provider.TELEGRAM.value, workspace_id, "bot_token"
                )
                bot_token = await read_token(session, vault_name)
                if not bot_token:
                    raise ValueError("Bot token not found in vault")

                # Step 1: Discover chats via Bot API + DB (bots can't use getDialogs)
                srl.info("Discovering chats via Bot API and DB records")
                chats_from_updates = await _discover_chats_from_updates(bot_token)
                chats_from_db = await _discover_chats_from_db(session, workspace_id)
                all_chats = {**chats_from_db, **chats_from_updates}
                srl.info(f"Found {len(all_chats)} chats to sync")

                if not all_chats:
                    await _restore_webhook(bot_token, workspace_id, settings)
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    await update_cursor_status(
                        session, workspace_id, "telegram", "default",
                        sync_status="complete", records_synced=0,
                        cursor_value=now.isoformat(),
                    )
                    await session.commit()
                    srl.info("No chats found to sync")
                    return

                # Re-set webhook (getUpdates discovery disabled it)
                await _restore_webhook(bot_token, workspace_id, settings)

                # Step 2: Fetch history per chat via Telethon
                client = TelegramClient(
                    StringSession(),
                    int(settings.TELEGRAM_API_ID),
                    settings.TELEGRAM_API_HASH,
                )
                await client.start(bot_token=bot_token)

                try:
                    sync_result = await _sync_known_chats(
                        client, session, workspace_id, all_chats, srl
                    )
                finally:
                    await client.disconnect()

                total_synced = sync_result["total_synced"]

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                await update_cursor_status(
                    session, workspace_id, "telegram", "default",
                    sync_status="complete",
                    records_synced=total_synced,
                    cursor_value=now.isoformat(),
                )
                await emit_activity(
                    session, workspace_id, "sync_completed",
                    metadata={
                        "integration": "telegram",
                        "messages_synced": total_synced,
                    },
                )
                await session.commit()

                elapsed = time.monotonic() - _sync_t0
                srl.info(f"Telegram history sync complete: {total_synced} messages in {elapsed:.1f}s")

            except Exception as e:
                srl.exception("Telegram history sync failed")
                try:
                    await session.rollback()
                    await update_cursor_status(
                        session, workspace_id, "telegram", "default",
                        sync_status="error",
                        error_message=str(e)[:200],
                    )
                    await session.commit()
                except Exception:
                    logger.warning(
                        "Failed to persist error status for telegram sync ws=%s",
                        workspace_id,
                    )


async def _discover_chats_from_updates(bot_token: str) -> dict[int, str]:
    """Discover chat IDs via Bot API getUpdates (works for bots)."""
    chats: dict[int, str] = {}
    try:
        await telegram_api_call(bot_token, "deleteWebhook")
    except Exception:
        logger.debug("deleteWebhook failed during chat discovery", exc_info=True)

    offset = 0
    for _ in range(20):
        try:
            updates = await telegram_api_call(
                bot_token, "getUpdates", offset=offset, limit=100, timeout=1,
            )
        except Exception:
            break
        if not updates:
            break
        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("edited_message")
            if message and message.get("chat"):
                chat = message["chat"]
                chats[chat["id"]] = chat.get("title") or chat.get("first_name") or str(chat["id"])
    return chats


async def _discover_chats_from_db(session: AsyncSession, workspace_id: UUID) -> dict[int, str]:
    """Discover chats from previously stored telegram messages."""
    stmt = (
        select(TelegramMessage.chat_id, TelegramMessage.chat_title)
        .where(
            TelegramMessage.workspace_id == workspace_id,
            TelegramMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .distinct(TelegramMessage.chat_id)
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] or str(row[0]) for row in result.all()}


async def _restore_webhook(bot_token: str, workspace_id: UUID, settings) -> None:
    """Re-register the webhook after getUpdates discovery."""
    base_url = settings.TELEGRAM_WEBHOOK_BASE_URL or settings.BACKEND_URL
    webhook_url = f"{base_url}/api/telegram/webhook/{workspace_id}"
    if webhook_url.startswith("https://"):
        try:
            await telegram_api_call(
                bot_token, "setWebhook",
                url=webhook_url,
                secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
                allowed_updates=["message", "edited_message"],
            )
        except Exception:
            logger.warning("Failed to restore webhook after sync", exc_info=True)


async def _sync_known_chats(
    client,
    session: AsyncSession,
    workspace_id: UUID,
    chats: dict[int, str],
    srl: SyncRunLogger,
) -> dict:
    """Fetch history for known chat IDs using Telethon iter_messages.

    Returns a dict with total_synced, channels_active, top_channels, sync_hours.
    """
    cursor = await get_or_create_cursor(session, workspace_id, "telegram", "default")
    if cursor.cursor_value:
        cutoff = datetime.fromisoformat(cursor.cursor_value).replace(tzinfo=timezone.utc)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)

    total_synced = 0
    all_msg_ids: list[UUID] = []
    chat_counts: dict[str, int] = {}

    for chat_id, chat_title in chats.items():
        try:
            chat_msg_ids, chat_count = await _sync_single_chat(
                client, session, workspace_id, chat_id, chat_title, cutoff
            )
            all_msg_ids.extend(chat_msg_ids)
            total_synced += chat_count

            if chat_count > 0:
                chat_counts[chat_title] = chat_count
                srl.info(f"Synced {chat_count} messages from {chat_title}")
        except Exception as e:
            logger.warning("Failed to sync chat %s (%d): %s", chat_title, chat_id, e, exc_info=True)
            srl.warning(f"Failed to sync chat {chat_title} ({chat_id}): {e}")

        await asyncio.sleep(RATE_LIMIT_DELAY)

    if all_msg_ids:
        await enqueue_embedding_job(workspace_id, "telegram_message", all_msg_ids)

    top_channels = sorted(chat_counts, key=chat_counts.get, reverse=True)  # type: ignore[arg-type]
    sync_hours = max(1, int((datetime.now(timezone.utc) - cutoff).total_seconds() / 3600))

    return {
        "total_synced": total_synced,
        "channels_active": len(chat_counts),
        "top_channels": top_channels[:5],
        "sync_hours": sync_hours,
    }


async def _sync_single_chat(
    client,
    session: AsyncSession,
    workspace_id: UUID,
    chat_id: int,
    chat_title: str,
    cutoff: datetime,
) -> tuple[list[UUID], int]:
    """Sync message history for a single chat via Telethon iter_messages."""
    chat_type = "group"  # Default

    msg_ids: list[UUID] = []
    count = 0

    # Resolve the entity first — Telethon needs this for some chat ID formats
    try:
        entity = await client.get_entity(chat_id)
    except Exception:
        logger.warning("Could not resolve entity for chat %d, trying direct", chat_id, exc_info=True)
        entity = chat_id

    async for message in client.iter_messages(
        entity, limit=MAX_MESSAGES_PER_CHAT, reverse=False,
    ):
        msg_date = message.date
        if msg_date and msg_date.replace(tzinfo=timezone.utc) < cutoff:
            break

        if not message.text:
            continue
        sender = message.sender
        if sender and getattr(sender, "bot", False):
            continue

        from_user_id = getattr(sender, "id", None) if sender else None
        from_username = getattr(sender, "username", None) if sender else None
        from_first_name = getattr(sender, "first_name", None) if sender else None

        reply_to_msg_id = (
            message.reply_to.reply_to_msg_id
            if message.reply_to and hasattr(message.reply_to, "reply_to_msg_id")
            else None
        )

        stmt = pg_insert(TelegramMessage).values(
            workspace_id=workspace_id,
            message_id=message.id,
            chat_id=chat_id,
            chat_title=chat_title if chat_type != "private" else None,
            chat_type=chat_type,
            from_user_id=from_user_id,
            from_username=from_username,
            from_first_name=from_first_name,
            text=message.text,
            reply_to_message_id=reply_to_msg_id,
            is_reply=reply_to_msg_id is not None,
            telegram_date=msg_date.replace(tzinfo=None) if msg_date else None,
            raw_data={},
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_tg_msg",
            set_={"text": stmt.excluded.text},
        ).returning(TelegramMessage.__table__.c.id)

        result = await session.execute(stmt)
        msg_uuid = result.scalar_one()
        msg_ids.append(msg_uuid)
        count += 1

        if count % FLUSH_BATCH_SIZE == 0:
            await session.flush()

    if count > 0:
        await session.flush()

    return msg_ids, count


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

async def _upsert_telegram_message(
    session: AsyncSession,
    workspace_id: UUID,
    message: dict,
) -> UUID | None:
    """Upsert a single Telegram message from a Bot API update payload.

    Returns the message UUID, or None if the message was filtered out.
    """
    chat = message.get("chat", {})
    from_user = message.get("from") or message.get("sender_chat", {})

    message_id = message.get("message_id")
    chat_id = chat.get("id")
    if not message_id or not chat_id:
        return None

    telegram_date = None
    if message.get("date"):
        telegram_date = datetime.utcfromtimestamp(message["date"])

    reply_to = message.get("reply_to_message")
    reply_to_message_id = reply_to.get("message_id") if reply_to else None

    stmt = pg_insert(TelegramMessage).values(
        workspace_id=workspace_id,
        message_id=message_id,
        chat_id=chat_id,
        chat_title=chat.get("title"),
        chat_type=chat.get("type"),
        from_user_id=from_user.get("id"),
        from_username=from_user.get("username"),
        from_first_name=from_user.get("first_name"),
        text=message["text"],
        reply_to_message_id=reply_to_message_id,
        is_reply=reply_to_message_id is not None,
        telegram_date=telegram_date,
        raw_data={"update": message},
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_tg_msg",
        set_={
            "text": stmt.excluded.text,
            "raw_data": stmt.excluded.raw_data,
        },
    ).returning(TelegramMessage.__table__.c.id)

    result = await session.execute(stmt)
    return result.scalar_one()
