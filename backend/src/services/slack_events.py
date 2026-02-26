"""Slack Events API message processor.

Handles real-time Slack messages via the Events API:
- HMAC-SHA256 signature verification (reuses pattern from Linear webhook)
- Message filtering (bots, short messages, system messages)
- Thread relationship tracking (parent_ts, is_thread_reply)
- Message edit and delete handling
- Upsert via on_conflict_do_update for idempotent ingestion

Per user decisions:
- Filter out: bot messages, messages under 10 characters, system messages
- Store file-sharing messages' text but do not download attached files
- On message edit: overwrite stored text with latest version
- On message delete: soft-delete (set deleted_at)
- Store Slack user ID + display name at ingestion time
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import Provider, WorkspaceIntegration
from src.models.slack import SlackMessage
from src.services import embedding

logger = logging.getLogger(__name__)

# Subtypes that are system messages (filtered out)
SYSTEM_SUBTYPES = frozenset({
    "bot_message",
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
})

# Maximum age (seconds) for timestamp replay protection
_MAX_TIMESTAMP_AGE_SECONDS = 300  # 5 minutes


def verify_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify Slack request signature using HMAC-SHA256.

    Slack format: v0={hmac_sha256(signing_secret, "v0:{timestamp}:{body}")}

    Args:
        signing_secret: The Slack app signing secret.
        timestamp: X-Slack-Request-Timestamp header value.
        body: Raw request body bytes.
        signature: X-Slack-Signature header value.

    Returns:
        True if signature is valid and timestamp is within 5 minutes.
    """
    # Replay protection: reject timestamps older than 5 minutes
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - ts) > _MAX_TIMESTAMP_AGE_SECONDS:
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def process_event(
    event_payload: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Process a Slack event callback payload.

    Dispatches based on event type and subtype:
    - message (no subtype or file_share): store new message
    - message_changed: overwrite text
    - message_deleted: soft-delete

    Args:
        event_payload: The event object from the Slack event callback.
        workspace_id: The workspace this event belongs to.
        session: Async database session.
    """
    event = event_payload.get("event", {})
    event_type = event.get("type")

    if event_type != "message":
        logger.debug("Ignoring non-message event type: %s", event_type)
        return

    subtype = event.get("subtype")

    if subtype == "message_changed":
        await _handle_message_edit(event, workspace_id, session)
    elif subtype == "message_deleted":
        await _handle_message_delete(event, workspace_id, session)
    elif subtype is None or subtype == "file_share":
        await _handle_message(event, workspace_id, session)
    else:
        logger.debug("Ignoring message subtype: %s", subtype)


def _should_filter(event: dict) -> bool:
    """Determine if a message should be filtered out.

    Filters:
    - Messages with bot_id (bot messages)
    - System message subtypes (channel_join, channel_leave, etc.)
    - Messages with text shorter than 10 characters

    Args:
        event: The Slack event dict.

    Returns:
        True if the message should be filtered out (not stored).
    """
    # Filter bot messages
    if event.get("bot_id"):
        return True

    # Filter system message subtypes
    subtype = event.get("subtype")
    if subtype in SYSTEM_SUBTYPES:
        return True

    # Filter short messages (< 10 characters)
    text = event.get("text", "")
    if len(text) < 10:
        return True

    return False


async def _is_channel_monitored(
    session: AsyncSession,
    workspace_id: UUID,
    channel_id: str,
) -> bool:
    """Check if a channel is in the workspace's monitored channels list.

    Reads selected_channels from workspace_integrations.config JSONB.
    If no selected_channels is configured, returns True (monitor all by default).

    Args:
        session: Async database session.
        workspace_id: Workspace to check.
        channel_id: Slack channel ID to check.

    Returns:
        True if the channel is monitored (or no filter configured).
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.SLACK,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return True  # No config means monitor all channels

    selected_channels = integration.config.get("selected_channels")
    if selected_channels is None:
        return True  # No channel filter set

    return channel_id in selected_channels


async def _handle_message(
    event: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a new message event.

    Applies filtering rules, checks channel monitoring, determines thread
    relationships, and upserts the SlackMessage record.

    Args:
        event: The Slack message event dict.
        workspace_id: The workspace this message belongs to.
        session: Async database session.
    """
    if _should_filter(event):
        return

    channel_id = event.get("channel", "")

    if not await _is_channel_monitored(session, workspace_id, channel_id):
        return

    slack_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts")

    # Determine thread relationship
    is_thread_reply = False
    parent_ts = None
    if thread_ts and thread_ts != slack_ts:
        # This is a thread reply
        is_thread_reply = True
        parent_ts = thread_ts
    elif thread_ts and thread_ts == slack_ts:
        # This is a thread parent (has thread_ts equal to its own ts)
        pass  # thread_ts is set, is_thread_reply stays False

    # Convert Slack timestamp to datetime
    slack_created_at = _ts_to_datetime(slack_ts)

    # Upsert using PostgreSQL INSERT ... ON CONFLICT DO UPDATE
    values = {
        "workspace_id": workspace_id,
        "slack_ts": slack_ts,
        "channel_id": channel_id,
        "channel_name": None,  # Can be enriched later
        "user_id": event.get("user"),
        "user_name": None,  # Can be enriched later via users.info
        "text": event.get("text", ""),
        "thread_ts": thread_ts,
        "parent_ts": parent_ts,
        "is_thread_reply": is_thread_reply,
        "slack_created_at": slack_created_at,
        "raw_data": event,
    }

    stmt = pg_insert(SlackMessage).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_slack_msg",
        set_={
            "text": stmt.excluded.text,
            "user_id": stmt.excluded.user_id,
            "thread_ts": stmt.excluded.thread_ts,
            "parent_ts": stmt.excluded.parent_ts,
            "is_thread_reply": stmt.excluded.is_thread_reply,
            "raw_data": stmt.excluded.raw_data,
        },
    )

    result = await session.execute(stmt)
    await session.commit()

    # Queue embedding generation (Phase 4 stub)
    # Get the message ID for embedding -- query it back
    msg_stmt = select(SlackMessage.id).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.channel_id == channel_id,
        SlackMessage.slack_ts == slack_ts,
    )
    msg_result = await session.execute(msg_stmt)
    message_id = msg_result.scalar_one_or_none()

    if message_id:
        await embedding.queue_embedding_generation(
            session, workspace_id, "slack_message", [message_id]
        )


async def _handle_message_edit(
    event: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a message_changed event.

    Overwrites stored text with the latest version. Per user decision:
    overwrite stored text, do not keep edit history.

    Args:
        event: The Slack message_changed event dict.
        workspace_id: The workspace this message belongs to.
        session: Async database session.
    """
    message = event.get("message", {})
    channel_id = event.get("channel", "")
    slack_ts = message.get("ts", "")

    if not slack_ts:
        return

    stmt = select(SlackMessage).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.channel_id == channel_id,
        SlackMessage.slack_ts == slack_ts,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if not existing:
        logger.debug("Edit for unknown message %s in channel %s", slack_ts, channel_id)
        return

    new_text = message.get("text", existing.text)
    old_text = existing.text

    existing.text = new_text
    existing.raw_data = message

    await session.commit()

    # Re-embed if text changed
    if new_text != old_text:
        await embedding.queue_embedding_generation(
            session, workspace_id, "slack_message", [existing.id]
        )


async def _handle_message_delete(
    event: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a message_deleted event.

    Soft-deletes the message by setting deleted_at. Per user decision:
    context generation skips deleted messages.

    Args:
        event: The Slack message_deleted event dict.
        workspace_id: The workspace this message belongs to.
        session: Async database session.
    """
    previous_message = event.get("previous_message", {})
    channel_id = event.get("channel", "")
    slack_ts = previous_message.get("ts", "")

    if not slack_ts:
        return

    stmt = select(SlackMessage).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.channel_id == channel_id,
        SlackMessage.slack_ts == slack_ts,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        logger.info(
            "Soft-deleted Slack message %s (ts=%s, channel=%s)",
            existing.id,
            slack_ts,
            channel_id,
        )


def _ts_to_datetime(slack_ts: str) -> datetime | None:
    """Convert a Slack timestamp string to a datetime.

    Slack timestamps are Unix epoch seconds with microsecond decimal
    (e.g., "1234567890.123456").

    Args:
        slack_ts: Slack timestamp string.

    Returns:
        datetime in UTC, or None if conversion fails.
    """
    try:
        epoch = float(slack_ts)
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None
