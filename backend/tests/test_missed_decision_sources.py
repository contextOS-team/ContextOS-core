"""Tests for source-window loading semantics used by missed-decision scans."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.models.meeting import MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.telegram import TelegramMessage
from src.services.missed_decision_sources import load_source_window


class _ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _ResultRows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarRows:
        return _ScalarRows(self._rows)


class _TextFilterAwareSession:
    """Fake SQL session that models whether text filtering happened before LIMIT."""

    def __init__(
        self,
        rows: list[object],
        *,
        text_filter_fragments: tuple[str, ...],
        has_text: Callable[[object], bool],
    ) -> None:
        self.rows = rows
        self.text_filter_fragments = text_filter_fragments
        self.has_text = has_text
        self.sql = ""

    async def execute(self, stmt) -> _ResultRows:
        compiled = stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        self.sql = str(compiled)
        filters_before_limit = all(
            fragment in self.sql for fragment in self.text_filter_fragments
        )
        rows = [row for row in self.rows if self.has_text(row)]
        if not filters_before_limit:
            rows = self.rows
        return _ResultRows(rows[:2])


def test_source_loader_timestamp_columns_are_timezone_aware() -> None:
    columns = {
        "meeting_transcripts.meeting_date": MeetingTranscript.__table__.c.meeting_date,
        "notion_pages.notion_updated_at": NotionPage.__table__.c.notion_updated_at,
        "slack_messages.slack_created_at": SlackMessage.__table__.c.slack_created_at,
        "telegram_messages.telegram_date": TelegramMessage.__table__.c.telegram_date,
    }

    for name, column in columns.items():
        assert column.type.timezone, name


@pytest.mark.asyncio
async def test_notion_loader_filters_empty_pages_before_batch_limit() -> None:
    workspace_id = uuid4()
    start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    valid = NotionPage(
        workspace_id=workspace_id,
        notion_id="notion-valid",
        title="Use source-backed scans",
        content=None,
        notion_updated_at=start + timedelta(minutes=2),
    )
    rows = [
        NotionPage(
            workspace_id=workspace_id,
            notion_id="notion-empty-1",
            title="",
            content=None,
            notion_updated_at=start,
        ),
        NotionPage(
            workspace_id=workspace_id,
            notion_id="notion-empty-2",
            title="",
            content="",
            notion_updated_at=start + timedelta(minutes=1),
        ),
        valid,
    ]
    session = _TextFilterAwareSession(
        rows,
        text_filter_fragments=(
            "notion_pages.content IS NOT NULL",
            "notion_pages.title IS NOT NULL",
        ),
        has_text=lambda row: bool(row.content or row.title),
    )

    records = await load_source_window(
        session,  # type: ignore[arg-type]
        workspace_id,
        "notion_page",
        start,
        start + timedelta(hours=1),
        limit=2,
    )

    assert [record.source_id for record in records] == [valid.id]
    assert records[0].text == "Use source-backed scans"
    assert "LIMIT 2" in session.sql


@pytest.mark.asyncio
async def test_fathom_loader_filters_empty_transcripts_before_batch_limit() -> None:
    workspace_id = uuid4()
    start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    valid = MeetingTranscript(
        workspace_id=workspace_id,
        source="fathom",
        title="Architecture review",
        transcript="We decided to keep scanner checkpoints source-backed.",
        summary=None,
        meeting_date=start + timedelta(minutes=2),
    )
    rows = [
        MeetingTranscript(
            workspace_id=workspace_id,
            source="fathom",
            title="Empty transcript 1",
            transcript="",
            summary=None,
            meeting_date=start,
        ),
        MeetingTranscript(
            workspace_id=workspace_id,
            source="fathom",
            title="Empty transcript 2",
            transcript="",
            summary="",
            meeting_date=start + timedelta(minutes=1),
        ),
        valid,
    ]
    session = _TextFilterAwareSession(
        rows,
        text_filter_fragments=(
            "meeting_transcripts.transcript IS NOT NULL",
            "meeting_transcripts.summary IS NOT NULL",
        ),
        has_text=lambda row: bool(row.transcript or row.summary),
    )

    records = await load_source_window(
        session,  # type: ignore[arg-type]
        workspace_id,
        "fathom_transcript",
        start,
        start + timedelta(hours=1),
        limit=2,
    )

    assert [record.source_id for record in records] == [valid.id]
    assert records[0].text == "We decided to keep scanner checkpoints source-backed."
    assert "LIMIT 2" in session.sql
