"""Slack Events API message processor.

Handles real-time Slack messages via the Events API:
- HMAC-SHA256 signature verification (reuses pattern from Linear webhook)
- Message filtering (bots, short messages, system messages)
- Thread relationship tracking (parent_ts, is_thread_reply)
- Message edit and delete handling
- Upsert via on_conflict_do_update for idempotent ingestion

Per user decisions:
- Filter out: bot messages, system messages (channel_join/leave/topic/etc.)
- Short messages ("done", "no", "approved") are retained as of Phase 39
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

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import Provider, WorkspaceIntegration
from src.models.slack import SlackMessage
from src.services import embedding
from src.services.graph_extractor import extract_and_populate_graph

logger = logging.getLogger(__name__)

_SLACK_API_BASE = "https://slack.com/api"

# Process-local caches keyed by (workspace_id, slack_id) so we don't hit
# users.info / conversations.info on every event. Channel and user names
# rarely change and cache hits dominate after the first message per channel/user.
_CHANNEL_NAME_CACHE: dict[tuple[UUID, str], str] = {}
_USER_NAME_CACHE: dict[tuple[UUID, str], str] = {}
_CACHE_MAX_ENTRIES = 5000  # bounded to keep memory predictable

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

    Filters retained:
    - Messages with bot_id (bot messages)
    - System message subtypes (channel_join, channel_leave, etc.)

    Phase 39: the <10-character length filter was removed -- short messages
    such as "done", "no", "approved" carry meaningful signal. This applies
    to both the channel webhook path and the DM polling path (both call
    this helper), per the Phase 39 CONTEXT.md decision.

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

    user_id = event.get("user")

    # Resolve human-readable names so synthesis citations read
    # "(Slack: #engineering by Дулат Орманов)" instead of
    # "(Slack: #unknown by Unknown)". Both lookups are cached per process
    # and fail-silent — name resolution is never allowed to block message
    # ingestion.
    channel_name = await _resolve_channel_name(session, workspace_id, channel_id)
    user_name = await _resolve_user_name(session, workspace_id, user_id) if user_id else None

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
        "channel_name": channel_name,
        "user_id": user_id,
        "user_name": user_name,
        "text": event.get("text", ""),
        "thread_ts": thread_ts,
        "parent_ts": parent_ts,
        "is_thread_reply": is_thread_reply,
        "slack_created_at": slack_created_at,
        "raw_data": event,
    }

    stmt = pg_insert(SlackMessage).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "channel_id", "slack_ts"],
        set_={
            "text": stmt.excluded.text,
            "user_id": stmt.excluded.user_id,
            "user_name": stmt.excluded.user_name,
            "channel_name": stmt.excluded.channel_name,
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

        # Graph extraction for Slack messages
        try:
            await extract_and_populate_graph(
                session=session,
                workspace_id=workspace_id,
                content=event.get("text", ""),
                source_type="slack_message",
                source_id=message_id,
                source_name=f"Slack message in #{channel_id}",
                source_external_id=slack_ts,
            )
        except Exception:
            logger.warning(
                "Graph extraction failed for Slack message ts=%s", slack_ts, exc_info=True
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
        # slack_messages.slack_created_at is TIMESTAMP WITHOUT TIME ZONE;
        # return naive UTC to match column type.
        return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError, OSError):
        return None


def _cache_set_bounded(cache: dict, key, value: str) -> None:
    """Insert into cache and evict the oldest key if at the size cap."""
    if len(cache) >= _CACHE_MAX_ENTRIES:
        try:
            oldest = next(iter(cache))
            cache.pop(oldest, None)
        except StopIteration:
            pass
    cache[key] = value


async def _resolve_channel_name(
    session: AsyncSession,
    workspace_id: UUID,
    channel_id: str,
) -> str | None:
    """Resolve a Slack channel ID to its `#name`.

    Caches per (workspace, channel) to avoid hitting conversations.info on
    every event. Returns None on any failure so the caller falls back
    cleanly. Never raises.
    """
    if not channel_id:
        return None
    key = (workspace_id, channel_id)
    cached = _CHANNEL_NAME_CACHE.get(key)
    if cached is not None:
        return cached

    try:
        from src.services.slack_oauth import get_bot_token

        bot_token = await get_bot_token(session, workspace_id)
        if not bot_token:
            return None

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{_SLACK_API_BASE}/conversations.info",
                params={"channel": channel_id},
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    raw = data.get("channel", {}).get("name") or channel_id
                    name = f"#{raw}" if not raw.startswith("#") else raw
                    _cache_set_bounded(_CHANNEL_NAME_CACHE, key, name)
                    return name
    except Exception:
        logger.debug(
            "Failed to resolve channel name for %s (non-blocking)",
            channel_id, exc_info=True,
        )
    return None


async def _resolve_user_name(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: str,
) -> str | None:
    """Resolve a Slack user ID to a display name.

    Prefers real_name, falls back to display_name, then None. Cached per
    (workspace, user). Fail-silent.
    """
    if not user_id:
        return None
    key = (workspace_id, user_id)
    cached = _USER_NAME_CACHE.get(key)
    if cached is not None:
        return cached

    try:
        from src.services.slack_oauth import get_bot_token

        bot_token = await get_bot_token(session, workspace_id)
        if not bot_token:
            return None

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{_SLACK_API_BASE}/users.info",
                params={"user": user_id},
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    user = data.get("user", {})
                    name = (
                        user.get("real_name")
                        or user.get("profile", {}).get("display_name")
                        or None
                    )
                    if name:
                        _cache_set_bounded(_USER_NAME_CACHE, key, name)
                    return name
    except Exception:
        logger.debug(
            "Failed to resolve user name for %s (non-blocking)",
            user_id, exc_info=True,
        )
    return None
