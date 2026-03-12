"""Slack huddle transcript ingestion service.

Provides poll-based ingestion of Slack huddle meeting transcripts.
Huddle AI notes are stored as canvases attached to huddle threads.
This service:
- Scans selected channels for ended huddle messages
- Retrieves canvas content (AI-generated notes) from huddle threads
- Creates MeetingTranscript records with source='slack_huddle'
- Deduplicates by huddle_room_id stored in raw_data
- Queues embedding generation for transcripts with content

Follows the proven Fathom poll pattern from services/fathom.py.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import Provider, WorkspaceIntegration
from src.models.meeting import MeetingTranscript
from src.services import embedding
from src.services.slack_oauth import get_bot_token

logger = logging.getLogger(__name__)

# Slack Web API base URL
SLACK_API_BASE = "https://slack.com/api"


async def poll_huddle_transcripts(
    session: AsyncSession,
    workspace_id: UUID,
) -> dict:
    """Poll Slack channels for new huddle transcripts.

    Scans selected channels for ended huddle messages, retrieves AI-generated
    canvas notes, and creates MeetingTranscript records. Deduplicates by
    huddle_room_id stored in raw_data.

    Args:
        session: Async database session.
        workspace_id: Workspace to poll for.

    Returns:
        Dict with poll results: ingested count, skipped count.
    """
    bot_token = await get_bot_token(session, workspace_id)

    # Get selected channels and channel name map from integration config
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if not integration or not integration.config:
        return {"ingested": 0, "skipped": 0}

    config = integration.config
    selected_channel_ids = config.get("selected_channels", [])
    available_channels = config.get("available_channels", [])
    channel_name_map = {ch["id"]: ch["name"] for ch in available_channels}

    if not selected_channel_ids:
        return {"ingested": 0, "skipped": 0}

    # Get last poll timestamp
    oldest = config.get("last_huddle_poll_at")

    ingested_count = 0
    skipped_count = 0

    # User name cache for this poll run
    user_name_cache: dict[str, str] = {}

    async with httpx.AsyncClient() as client:
        for channel_id in selected_channel_ids:
            try:
                huddle_messages = await _find_huddle_messages(
                    client, bot_token, channel_id, oldest
                )
            except Exception:
                logger.exception(
                    "Error scanning channel %s for huddles", channel_id
                )
                continue

            for msg in huddle_messages:
                room = msg["room"]
                room_id = room["id"]

                # Dedup check: query MeetingTranscript by huddle_room_id
                dedup_stmt = select(MeetingTranscript).where(
                    MeetingTranscript.workspace_id == workspace_id,
                    MeetingTranscript.source == "slack_huddle",
                    MeetingTranscript.raw_data["huddle_room_id"].as_string() == room_id,
                )
                dedup_result = await session.execute(dedup_stmt)
                existing = dedup_result.scalar_one_or_none()

                if existing:
                    skipped_count += 1
                    continue

                # Get canvas content from huddle thread
                canvas_thread_ts = room.get("canvas_thread_ts")
                canvas_content = await _get_huddle_canvas_content(
                    client, bot_token, channel_id, canvas_thread_ts
                )

                # Resolve participant names
                participant_ids = room.get("participant_history", [])
                participants = await _resolve_user_names(
                    client, bot_token, participant_ids, user_name_cache
                )

                # Calculate duration
                date_start = room.get("date_start", 0)
                date_end = room.get("date_end", 0)
                duration_minutes = int((date_end - date_start) / 60) if date_end > date_start else None

                # Meeting date from start timestamp
                meeting_date = (
                    datetime.fromtimestamp(date_start, tz=timezone.utc)
                    if date_start
                    else None
                )

                # Channel name for title
                channel_name = channel_name_map.get(channel_id, channel_id)

                # Create MeetingTranscript record
                transcript_text = canvas_content or "No AI notes available for this huddle."

                meeting = MeetingTranscript(
                    workspace_id=workspace_id,
                    source="slack_huddle",
                    title=f"Huddle in #{channel_name}",
                    transcript=transcript_text,
                    summary=None,
                    participants=participants if participants else None,
                    meeting_date=meeting_date,
                    duration_minutes=duration_minutes,
                    raw_data={
                        "huddle_room_id": room_id,
                        "channel_id": channel_id,
                        "canvas_thread_ts": canvas_thread_ts,
                        **room,
                    },
                )
                session.add(meeting)
                await session.flush()

                # Queue embedding only if canvas content is present
                if canvas_content:
                    await embedding.queue_embedding_generation(
                        session, workspace_id, "meeting_transcript", [meeting.id]
                    )

                ingested_count += 1
                logger.info(
                    "Ingested Slack huddle transcript: %s in #%s",
                    room_id, channel_name,
                )

        await session.commit()

    # Update last_huddle_poll_at in integration config
    int_stmt2 = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    int_result2 = await session.execute(int_stmt2)
    integration2 = int_result2.scalar_one_or_none()

    if integration2:
        updated_config = dict(integration2.config) if integration2.config else {}
        updated_config["last_huddle_poll_at"] = (
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )
        integration2.config = updated_config
        await session.commit()

    return {
        "ingested": ingested_count,
        "skipped": skipped_count,
    }


async def _find_huddle_messages(
    client: httpx.AsyncClient,
    bot_token: str,
    channel_id: str,
    oldest: str | None,
) -> list[dict]:
    """Find ended huddle messages in a channel's history.

    Paginates through conversations.history and filters for messages
    with room.call_family=='huddle' and room.has_ended==True.

    Args:
        client: httpx async client.
        bot_token: Slack bot token for API auth.
        channel_id: Slack channel ID to scan.
        oldest: ISO timestamp for incremental polling (or None for full scan).

    Returns:
        List of huddle message dicts.
    """
    huddle_messages: list[dict] = []
    cursor: str | None = None

    while True:
        params: dict = {
            "channel": channel_id,
            "limit": "200",
        }
        if oldest:
            params["oldest"] = oldest
        if cursor:
            params["cursor"] = cursor

        response = await client.get(
            f"{SLACK_API_BASE}/conversations.history",
            params=params,
            headers={"Authorization": f"Bearer {bot_token}"},
        )

        # Handle rate limiting
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "1"))
            logger.warning(
                "Slack rate limited, retrying after %d seconds", retry_after
            )
            await asyncio.sleep(retry_after)
            continue

        if response.status_code != 200:
            logger.error(
                "Slack API HTTP error %d for channel %s: %s",
                response.status_code, channel_id, response.text,
            )
            break

        data = response.json()

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            # Handle missing scope gracefully
            if error in ("missing_scope", "not_authed", "invalid_auth"):
                logger.warning(
                    "Slack API error for channel %s: %s (re-authorization may be needed)",
                    channel_id, error,
                )
                break
            logger.error("Slack conversations.history error: %s", error)
            break

        messages = data.get("messages", [])

        for msg in messages:
            room = msg.get("room")
            if not room:
                continue
            if room.get("call_family") != "huddle":
                continue
            if not room.get("has_ended"):
                continue
            huddle_messages.append(msg)

        # Pagination
        has_more = data.get("has_more", False)
        next_cursor = data.get("response_metadata", {}).get("next_cursor", "")

        if has_more and next_cursor:
            cursor = next_cursor
        else:
            break

    return huddle_messages


async def _get_huddle_canvas_content(
    client: httpx.AsyncClient,
    bot_token: str,
    channel_id: str,
    canvas_thread_ts: str | None,
) -> str | None:
    """Retrieve canvas content from a huddle thread.

    Scans thread replies for canvas files, retrieves file info,
    and downloads the canvas content.

    Args:
        client: httpx async client.
        bot_token: Slack bot token for API auth.
        channel_id: Channel where the huddle occurred.
        canvas_thread_ts: Thread timestamp for the huddle canvas.

    Returns:
        Canvas content as string, or None if no canvas found.
    """
    if not canvas_thread_ts:
        return None

    headers = {"Authorization": f"Bearer {bot_token}"}

    # Get thread replies
    response = await client.get(
        f"{SLACK_API_BASE}/conversations.replies",
        params={"channel": channel_id, "ts": canvas_thread_ts},
        headers=headers,
    )

    if response.status_code != 200:
        logger.warning(
            "Failed to get thread replies for %s/%s: HTTP %d",
            channel_id, canvas_thread_ts, response.status_code,
        )
        return None

    data = response.json()
    if not data.get("ok"):
        return None

    messages = data.get("messages", [])

    # Find canvas file in thread messages
    for msg in messages:
        files = msg.get("files", [])
        for file_info in files:
            filetype = file_info.get("filetype", "")
            mimetype = file_info.get("mimetype", "")

            if filetype == "canvas" or mimetype.startswith("application/vnd.slack"):
                file_id = file_info.get("id")
                url_private = file_info.get("url_private")

                if not file_id:
                    continue

                # Get file info for download URL
                file_resp = await client.get(
                    f"{SLACK_API_BASE}/files.info",
                    params={"file": file_id},
                    headers=headers,
                )

                if file_resp.status_code != 200:
                    continue

                file_data = file_resp.json()
                if not file_data.get("ok"):
                    continue

                # Try content from files.info response first
                content = file_data.get("content")
                if content:
                    return content

                # Fall back to downloading from url_private
                download_url = (
                    file_data.get("file", {}).get("url_private")
                    or url_private
                )
                if not download_url:
                    continue

                download_resp = await client.get(
                    download_url,
                    headers=headers,
                )

                if download_resp.status_code == 200:
                    return download_resp.text

    return None


async def _resolve_user_names(
    client: httpx.AsyncClient,
    bot_token: str,
    user_ids: list[str],
    cache: dict[str, str],
) -> list[str]:
    """Resolve Slack user IDs to display names.

    Uses users.info API to look up each user. Results are cached
    within the poll call to avoid redundant API calls.

    Args:
        client: httpx async client.
        bot_token: Slack bot token for API auth.
        user_ids: List of Slack user IDs.
        cache: Mutable cache dict shared across the poll run.

    Returns:
        List of display names (or user IDs if lookup fails).
    """
    names: list[str] = []
    headers = {"Authorization": f"Bearer {bot_token}"}

    for user_id in user_ids:
        if user_id in cache:
            names.append(cache[user_id])
            continue

        try:
            response = await client.get(
                f"{SLACK_API_BASE}/users.info",
                params={"user": user_id},
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    user = data["user"]
                    # Prefer real_name, fall back to display_name, then user_id
                    name = (
                        user.get("real_name")
                        or user.get("profile", {}).get("display_name")
                        or user_id
                    )
                    cache[user_id] = name
                    names.append(name)
                    continue
        except Exception:
            logger.exception("Failed to resolve user %s", user_id)

        # Fallback to user ID
        cache[user_id] = user_id
        names.append(user_id)

    return names
