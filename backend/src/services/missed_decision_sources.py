"""Source-window loaders for missed-decision scans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.meeting import MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.telegram import TelegramMessage


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
    records: list[MissedDecisionSourceRecord] = []
    for row in rows:
        timestamp = row.slack_created_at or row.created_at or start
        records.append(
            MissedDecisionSourceRecord(
                workspace_id=workspace_id,
                source_type="slack_message",
                source_id=row.id,
                text=row.text,
                source_link=_source_link(
                    "slack_message",
                    workspace_id,
                    row.id,
                    timestamp,
                    None,
                ),
                source_created_at=timestamp,
                metadata={
                    "channel_id": row.channel_id,
                    "channel_name": row.channel_name,
                    "slack_ts": row.slack_ts,
                    "thread_ts": row.thread_ts,
                },
            )
        )
    return records


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
                source_link=build_internal_source_reference(
                    "telegram_message",
                    workspace_id,
                    row.id,
                    timestamp,
                ),
                source_created_at=timestamp,
                metadata={
                    "chat_id": row.chat_id,
                    "chat_title": row.chat_title,
                    "message_id": row.message_id,
                },
            )
        )
    return records


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
                metadata={"notion_id": row.notion_id, "title": row.title},
            )
        )
    return records


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
                source_link=build_internal_source_reference(
                    "fathom_transcript",
                    workspace_id,
                    row.id,
                    timestamp,
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
