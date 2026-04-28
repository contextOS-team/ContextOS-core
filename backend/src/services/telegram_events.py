"""Telegram webhook event processing service.

Processes incoming Telegram updates: filters non-text/bot/short messages,
extracts message data, and upserts TelegramMessage records with ON CONFLICT
support for edited messages.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.telegram import TelegramMessage
from src.services import embedding

logger = logging.getLogger(__name__)


def _should_filter_telegram(update: dict) -> bool:
    """Determine if a Telegram update should be filtered out.

    Returns True (filter) for:
    - Updates without message or edited_message
    - Messages without text (photos, stickers, etc.)
    - Messages from bots
    """
    message = update.get("message") or update.get("edited_message")
    if not message:
        return True

    text = message.get("text")
    if not text:
        return True

    from_user = message.get("from", {})
    if from_user.get("is_bot", False):
        return True

    return False


async def process_telegram_update(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Process a single Telegram webhook update.

    Filters non-relevant updates, extracts message data, and upserts
    into telegram_messages table. Queues embedding generation for new/updated messages.

    Args:
        session: Async database session.
        workspace_id: Workspace this update belongs to.
        payload: Raw Telegram update payload.
    """
    if _should_filter_telegram(payload):
        return

    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return

    chat = message.get("chat", {})
    # Handle channel posts where "from" may be absent
    from_user = message.get("from") or message.get("sender_chat", {})

    message_id = message["message_id"]
    chat_id = chat["id"]

    # Parse telegram_date
    telegram_date = None
    if message.get("date"):
        telegram_date = datetime.utcfromtimestamp(message["date"])

    # Check if this is a reply
    reply_to = message.get("reply_to_message")
    reply_to_message_id = reply_to.get("message_id") if reply_to else None

    # Build insert statement with ON CONFLICT for upsert (edited messages)
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
        raw_data=payload,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_tg_msg",
        set_={
            "text": stmt.excluded.text,
            "raw_data": stmt.excluded.raw_data,
        },
    )

    stmt = stmt.returning(TelegramMessage.__table__.c.id)
    result = await session.execute(stmt)
    msg_uuid = result.scalar_one()

    # Queue embedding generation
    await embedding.queue_embedding_generation(
        session, workspace_id, "telegram_message", [msg_uuid]
    )

    await session.commit()

    # Feed the message into the knowledge graph so Telegram can act as a
    # bridge in community detection and surface in graph traversal.
    # Fail-silent — graph extraction must never block message ingestion.
    try:
        from src.services.graph_extractor import extract_and_populate_graph

        chat_label = chat.get("title") or chat.get("type") or str(chat_id)
        await extract_and_populate_graph(
            session=session,
            workspace_id=workspace_id,
            content=message["text"],
            source_type="telegram_message",
            source_id=msg_uuid,
            source_name=f"Telegram message in {chat_label}",
            source_external_id=f"{chat_id}:{message_id}",
        )
        await session.commit()
    except Exception:
        logger.warning(
            "Graph extraction failed for Telegram message %s/%s (non-blocking)",
            chat_id, message_id, exc_info=True,
        )

    logger.info(
        "Processed Telegram message %d from chat %d for workspace %s",
        message_id,
        chat_id,
        workspace_id,
    )
