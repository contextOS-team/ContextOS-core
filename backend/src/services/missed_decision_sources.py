"""Source-window loaders for missed-decision scans."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.meeting import MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.telegram import TelegramMessage
from src.services.slack_events import resolve_slack_permalink, slack_archive_url
from src.services.slack_text import (
    clean_slack_name,
    replace_slack_user_mentions,
    resolve_slack_user_names,
    slack_user_ids_in_text,
)


@dataclass(frozen=True)
class MissedDecisionSourceRecord:
    """Normalized source row passed into missed-decision extraction."""

    workspace_id: UUID
    source_type: str
    source_id: UUID
    text: str
    source_link: str
    source_created_at: datetime
    metadata: dict


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def build_internal_source_reference(
    source_type: str,
    workspace_id: UUID,
    source_id: UUID,
    source_timestamp: datetime,
) -> str:
    """Build an app-resolvable fallback source reference."""
    return (
        "/dashboard/source-reference"
        f"?source_type={quote(source_type)}"
        f"&source_id={quote(str(source_id))}"
        f"&workspace_id={quote(str(workspace_id))}"
        f"&source_timestamp={_iso(source_timestamp)}"
    )


def _source_link(
    source_type: str,
    workspace_id: UUID,
    source_id: UUID,
    timestamp: datetime,
    external: str | None,
) -> str:
    if external:
        return external
    return build_internal_source_reference(
        source_type,
        workspace_id,
        source_id,
        timestamp,
    )


def _telegram_source_link(row: TelegramMessage) -> str | None:
    raw = row.raw_data or {}
    message = raw.get("message") if isinstance(raw, dict) else None
    for container in (message, raw):
        if not isinstance(container, dict):
            continue
        for key in ("link", "url", "message_link", "permalink"):
            value = container.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
    chat = message.get("chat") if isinstance(message, dict) else None
    username = chat.get("username") if isinstance(chat, dict) else None
    if username:
        return f"https://t.me/{username}/{row.message_id}"

    chat_id = str(row.chat_id)
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{row.message_id}"
    return None


def _fathom_source_link(row: MeetingTranscript) -> str | None:
    raw = row.raw_data or {}
    for key in (
        "url",
        "share_url",
        "recording_url",
        "recording_share_url",
        "meeting_url",
        "summary_url",
    ):
        value = raw.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


async def _slack_source_links(
    session: AsyncSession,
    workspace_id: UUID,
    rows: list[SlackMessage],
) -> dict[UUID, str | None]:
    if not rows:
        return {}

    token: str | None = None
    try:
        from src.services.slack_oauth import SlackOAuthError, get_bot_token

        token = await get_bot_token(session, workspace_id)
    except (SlackOAuthError, RuntimeError):
        token = None

    resolved = await asyncio.gather(
        *(
            resolve_slack_permalink(
                session,
                workspace_id,
                row.channel_id,
                row.slack_ts,
                token=token,
            )
            for row in rows
            if token and row.channel_id and row.slack_ts
        ),
        return_exceptions=True,
    )
    resolved_iter = iter(resolved)
    links: dict[UUID, str | None] = {}
    for row in rows:
        permalink: str | None = None
        if token and row.channel_id and row.slack_ts:
            maybe_permalink = next(resolved_iter, None)
            if isinstance(maybe_permalink, str):
                permalink = maybe_permalink
        links[row.id] = permalink or slack_archive_url(row.channel_id, row.slack_ts)
    return links


def _apply_cursor(
    stmt,
    timestamp_column,
    id_column,
    *,
    after_source_created_at: datetime | None,
    after_source_id: UUID | None,
):
    if after_source_created_at is None or after_source_id is None:
        return stmt
    return stmt.where(
        or_(
            timestamp_column > after_source_created_at,
            and_(
                timestamp_column == after_source_created_at,
                id_column > after_source_id,
            ),
        )
    )


def _has_text(*columns):
    return or_(*(and_(column.is_not(None), column != "") for column in columns))


async def _count_rows(session: AsyncSession, stmt) -> int:
    result = await session.execute(stmt)
    value = result.scalar_one()
    return int(value or 0)


async def _load_slack(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
    after_source_created_at: datetime | None,
    after_source_id: UUID | None,
    limit: int,
) -> list[MissedDecisionSourceRecord]:
    stmt = select(SlackMessage).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        SlackMessage.slack_created_at >= start,  # type: ignore[operator]
        SlackMessage.slack_created_at <= end,  # type: ignore[operator]
        _has_text(SlackMessage.text),
    )
    if source_resource_id:
        stmt = stmt.where(SlackMessage.channel_id == source_resource_id)
    stmt = _apply_cursor(
        stmt,
        SlackMessage.slack_created_at,
        SlackMessage.id,
        after_source_created_at=after_source_created_at,
        after_source_id=after_source_id,
    )
    stmt = stmt.order_by(  # type: ignore[union-attr]
        SlackMessage.slack_created_at.asc(),
        SlackMessage.id.asc(),
    ).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    source_links = await _slack_source_links(session, workspace_id, list(rows))
    user_ids: set[str] = set()
    known_user_names: dict[str, str | None] = {}
    for row in rows:
        user_ids.update(slack_user_ids_in_text(row.text))
        if row.user_id and row.user_name:
            known_user_names[row.user_id] = row.user_name
    user_names = await resolve_slack_user_names(
        session,
        workspace_id,
        user_ids,
        known_user_names=known_user_names,
    )
    records: list[MissedDecisionSourceRecord] = []
    for row in rows:
        timestamp = row.slack_created_at or row.created_at or start
        text = replace_slack_user_mentions(row.text, user_names)
        records.append(
            MissedDecisionSourceRecord(
                workspace_id=workspace_id,
                source_type="slack_message",
                source_id=row.id,
                text=text,
                source_link=_source_link(
                    "slack_message",
                    workspace_id,
                    row.id,
                    timestamp,
                    source_links.get(row.id),
                ),
                source_created_at=timestamp,
                metadata={
                    "channel_id": row.channel_id,
                    "channel_name": row.channel_name,
                    "user_name": clean_slack_name(row.user_name)
                    or (user_names.get(row.user_id) if row.user_id else None),
                    "slack_user_names": user_names,
                    "slack_ts": row.slack_ts,
                    "thread_ts": row.thread_ts,
                },
            )
        )
    return records


async def _count_slack(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
) -> int:
    stmt = select(func.count()).select_from(SlackMessage).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        SlackMessage.slack_created_at >= start,  # type: ignore[operator]
        SlackMessage.slack_created_at <= end,  # type: ignore[operator]
        _has_text(SlackMessage.text),
    )
    if source_resource_id:
        stmt = stmt.where(SlackMessage.channel_id == source_resource_id)
    return await _count_rows(session, stmt)


async def _load_telegram(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
    after_source_created_at: datetime | None,
    after_source_id: UUID | None,
    limit: int,
) -> list[MissedDecisionSourceRecord]:
    stmt = select(TelegramMessage).where(
        TelegramMessage.workspace_id == workspace_id,
        TelegramMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        TelegramMessage.telegram_date >= start,  # type: ignore[operator]
        TelegramMessage.telegram_date <= end,  # type: ignore[operator]
        _has_text(TelegramMessage.text),
    )
    if source_resource_id:
        stmt = stmt.where(TelegramMessage.chat_id == int(source_resource_id))
    stmt = _apply_cursor(
        stmt,
        TelegramMessage.telegram_date,
        TelegramMessage.id,
        after_source_created_at=after_source_created_at,
        after_source_id=after_source_id,
    )
    stmt = stmt.order_by(  # type: ignore[union-attr]
        TelegramMessage.telegram_date.asc(),
        TelegramMessage.id.asc(),
    ).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    records: list[MissedDecisionSourceRecord] = []
    for row in rows:
        timestamp = row.telegram_date or row.created_at or start
        records.append(
            MissedDecisionSourceRecord(
                workspace_id=workspace_id,
                source_type="telegram_message",
                source_id=row.id,
                text=row.text,
                source_link=_source_link(
                    "telegram_message",
                    workspace_id,
                    row.id,
                    timestamp,
                    _telegram_source_link(row),
                ),
                source_created_at=timestamp,
                metadata={
                    "chat_id": row.chat_id,
                    "chat_title": row.chat_title,
                    "from_first_name": row.from_first_name,
                    "from_username": row.from_username,
                    "message_id": row.message_id,
                },
            )
        )
    return records


async def _count_telegram(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
) -> int:
    stmt = select(func.count()).select_from(TelegramMessage).where(
        TelegramMessage.workspace_id == workspace_id,
        TelegramMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        TelegramMessage.telegram_date >= start,  # type: ignore[operator]
        TelegramMessage.telegram_date <= end,  # type: ignore[operator]
        _has_text(TelegramMessage.text),
    )
    if source_resource_id:
        stmt = stmt.where(TelegramMessage.chat_id == int(source_resource_id))
    return await _count_rows(session, stmt)


async def _load_notion(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
    after_source_created_at: datetime | None,
    after_source_id: UUID | None,
    limit: int,
) -> list[MissedDecisionSourceRecord]:
    stmt = select(NotionPage).where(
        NotionPage.workspace_id == workspace_id,
        NotionPage.deleted_at.is_(None),  # type: ignore[union-attr]
        NotionPage.notion_updated_at >= start,  # type: ignore[operator]
        NotionPage.notion_updated_at <= end,  # type: ignore[operator]
        _has_text(NotionPage.content, NotionPage.title),
    )
    if source_resource_id:
        stmt = stmt.where(NotionPage.notion_id == source_resource_id)
    stmt = _apply_cursor(
        stmt,
        NotionPage.notion_updated_at,
        NotionPage.id,
        after_source_created_at=after_source_created_at,
        after_source_id=after_source_id,
    )
    stmt = stmt.order_by(  # type: ignore[union-attr]
        NotionPage.notion_updated_at.asc(),
        NotionPage.id.asc(),
    ).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    records: list[MissedDecisionSourceRecord] = []
    for row in rows:
        text = row.content or row.title
        if not text:
            continue
        timestamp = row.notion_updated_at or row.updated_at or row.created_at or start
        records.append(
            MissedDecisionSourceRecord(
                workspace_id=workspace_id,
                source_type="notion_page",
                source_id=row.id,
                text=text,
                source_link=_source_link(
                    "notion_page",
                    workspace_id,
                    row.id,
                    timestamp,
                    row.url,
                ),
                source_created_at=timestamp,
                metadata={
                    "notion_id": row.notion_id,
                    "title": row.title,
                    "source_context": row.title or row.url,
                },
            )
        )
    return records


async def _count_notion(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
) -> int:
    stmt = select(func.count()).select_from(NotionPage).where(
        NotionPage.workspace_id == workspace_id,
        NotionPage.deleted_at.is_(None),  # type: ignore[union-attr]
        NotionPage.notion_updated_at >= start,  # type: ignore[operator]
        NotionPage.notion_updated_at <= end,  # type: ignore[operator]
        _has_text(NotionPage.content, NotionPage.title),
    )
    if source_resource_id:
        stmt = stmt.where(NotionPage.notion_id == source_resource_id)
    return await _count_rows(session, stmt)


async def _load_meetings(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
    after_source_created_at: datetime | None,
    after_source_id: UUID | None,
    limit: int,
) -> list[MissedDecisionSourceRecord]:
    stmt = select(MeetingTranscript).where(
        MeetingTranscript.workspace_id == workspace_id,
        MeetingTranscript.deleted_at.is_(None),  # type: ignore[union-attr]
        MeetingTranscript.source == "fathom",
        MeetingTranscript.meeting_date >= start,  # type: ignore[operator]
        MeetingTranscript.meeting_date <= end,  # type: ignore[operator]
        _has_text(MeetingTranscript.transcript, MeetingTranscript.summary),
    )
    if source_resource_id:
        stmt = stmt.where(MeetingTranscript.id == UUID(source_resource_id))
    stmt = _apply_cursor(
        stmt,
        MeetingTranscript.meeting_date,
        MeetingTranscript.id,
        after_source_created_at=after_source_created_at,
        after_source_id=after_source_id,
    )
    stmt = stmt.order_by(  # type: ignore[union-attr]
        MeetingTranscript.meeting_date.asc(),
        MeetingTranscript.id.asc(),
    ).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    records: list[MissedDecisionSourceRecord] = []
    for row in rows:
        text = row.transcript or row.summary
        if not text:
            continue
        timestamp = row.meeting_date or row.created_at or start
        records.append(
            MissedDecisionSourceRecord(
                workspace_id=workspace_id,
                source_type="fathom_transcript",
                source_id=row.id,
                text=text,
                source_link=_source_link(
                    "fathom_transcript",
                    workspace_id,
                    row.id,
                    timestamp,
                    _fathom_source_link(row),
                ),
                source_created_at=timestamp,
                metadata={
                    "title": row.title,
                    "participants": row.participants or [],
                    "fathom_id": (row.raw_data or {}).get("fathom_id"),
                },
            )
        )
    return records


async def _count_meetings(
    session: AsyncSession,
    workspace_id: UUID,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None,
) -> int:
    stmt = select(func.count()).select_from(MeetingTranscript).where(
        MeetingTranscript.workspace_id == workspace_id,
        MeetingTranscript.deleted_at.is_(None),  # type: ignore[union-attr]
        MeetingTranscript.source == "fathom",
        MeetingTranscript.meeting_date >= start,  # type: ignore[operator]
        MeetingTranscript.meeting_date <= end,  # type: ignore[operator]
        _has_text(MeetingTranscript.transcript, MeetingTranscript.summary),
    )
    if source_resource_id:
        stmt = stmt.where(MeetingTranscript.id == UUID(source_resource_id))
    return await _count_rows(session, stmt)


async def load_source_window(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None = None,
    after_source_created_at: datetime | None = None,
    after_source_id: UUID | None = None,
    limit: int = 100,
) -> list[MissedDecisionSourceRecord]:
    """Load normalized source records for a scan window."""
    if source_type == "slack_message":
        return await _load_slack(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
            after_source_created_at=after_source_created_at,
            after_source_id=after_source_id,
            limit=limit,
        )
    if source_type == "telegram_message":
        return await _load_telegram(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
            after_source_created_at=after_source_created_at,
            after_source_id=after_source_id,
            limit=limit,
        )
    if source_type == "notion_page":
        return await _load_notion(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
            after_source_created_at=after_source_created_at,
            after_source_id=after_source_id,
            limit=limit,
        )
    if source_type in {"fathom_transcript", "meeting_transcript"}:
        return await _load_meetings(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
            after_source_created_at=after_source_created_at,
            after_source_id=after_source_id,
            limit=limit,
        )
    return []


async def count_source_window(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    start: datetime,
    end: datetime,
    *,
    source_resource_id: str | None = None,
) -> int:
    """Count source records for a scan window using the loader predicates."""
    if source_type == "slack_message":
        return await _count_slack(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
        )
    if source_type == "telegram_message":
        return await _count_telegram(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
        )
    if source_type == "notion_page":
        return await _count_notion(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
        )
    if source_type in {"fathom_transcript", "meeting_transcript"}:
        return await _count_meetings(
            session,
            workspace_id,
            start,
            end,
            source_resource_id=source_resource_id,
        )
    return 0
