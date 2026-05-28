"""Tests for source-window loading semantics used by missed-decision scans."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.models.meeting import MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.telegram import TelegramMessage
from src.services import missed_decision_sources
from src.services.missed_decision_sources import count_source_window, load_source_window


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


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _CountingSession:
    def __init__(self, value: int) -> None:
        self.value = value
        self.sql = ""

    async def execute(self, stmt) -> _ScalarResult:
        compiled = stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        self.sql = str(compiled)
        return _ScalarResult(self.value)


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
    assert records[0].metadata["source_context"] == "Use source-backed scans"
    assert "LIMIT 2" in session.sql


@pytest.mark.asyncio
async def test_slack_loader_includes_author_attribution_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    message = SlackMessage(
        workspace_id=workspace_id,
        slack_ts="1716637200.000100",
        channel_id="C123",
        channel_name="product",
        user_id="U123",
        user_name="Daulet",
        text="We decided to auto-save clear missed decisions.",
        slack_created_at=start,
    )
    session = _TextFilterAwareSession(
        [message],
        text_filter_fragments=("slack_messages.text IS NOT NULL",),
        has_text=lambda row: bool(row.text),
    )
    monkeypatch.setattr(
        missed_decision_sources,
        "_slack_source_links",
        AsyncMock(return_value={message.id: None}),
    )

    records = await load_source_window(
        session,  # type: ignore[arg-type]
        workspace_id,
        "slack_message",
        start - timedelta(minutes=1),
        start + timedelta(minutes=1),
        limit=2,
    )

    assert records[0].metadata["channel_name"] == "product"
    assert records[0].metadata["user_name"] == "Daulet"


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


@pytest.mark.asyncio
async def test_telegram_loader_uses_provider_message_links() -> None:
    workspace_id = uuid4()
    start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    message = TelegramMessage(
        workspace_id=workspace_id,
        chat_id=-1003644773967,
        chat_title="contextOS team",
        chat_type="supergroup",
        message_id=1356,
        text="We decided to show real Telegram source links.",
        telegram_date=start,
        raw_data={
            "message": {
                "chat": {
                    "id": -1003644773967,
                    "type": "supergroup",
                    "title": "contextOS team",
                },
                "message_id": 1356,
            }
        },
    )
    session = _TextFilterAwareSession(
        [message],
        text_filter_fragments=("telegram_messages.text IS NOT NULL",),
        has_text=lambda row: bool(row.text),
    )

    records = await load_source_window(
        session,  # type: ignore[arg-type]
        workspace_id,
        "telegram_message",
        start - timedelta(minutes=1),
        start + timedelta(minutes=1),
        limit=2,
    )

    assert records[0].source_link == "https://t.me/c/3644773967/1356"


@pytest.mark.asyncio
async def test_telegram_loader_includes_author_attribution_metadata() -> None:
    workspace_id = uuid4()
    start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    message = TelegramMessage(
        workspace_id=workspace_id,
        chat_id=-1003644773967,
        chat_title="contextOS team",
        chat_type="supergroup",
        message_id=1357,
        from_username="dxulet",
        from_first_name="Daulet",
        text="We decided to show real Telegram attribution.",
        telegram_date=start,
    )
    session = _TextFilterAwareSession(
        [message],
        text_filter_fragments=("telegram_messages.text IS NOT NULL",),
        has_text=lambda row: bool(row.text),
    )

    records = await load_source_window(
        session,  # type: ignore[arg-type]
        workspace_id,
        "telegram_message",
        start - timedelta(minutes=1),
        start + timedelta(minutes=1),
        limit=2,
    )

    assert records[0].metadata["from_first_name"] == "Daulet"
    assert records[0].metadata["from_username"] == "dxulet"
    assert records[0].metadata["chat_title"] == "contextOS team"


@pytest.mark.asyncio
async def test_source_counter_uses_same_slack_window_filters() -> None:
    workspace_id = uuid4()
    start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    session = _CountingSession(7)

    count = await count_source_window(
        session,  # type: ignore[arg-type]
        workspace_id,
        "slack_message",
        start,
        start + timedelta(hours=1),
        source_resource_id="C123",
    )

    assert count == 7
    assert "count" in session.sql.lower()
    assert "slack_messages.workspace_id" in session.sql
    assert "slack_messages.slack_created_at >=" in session.sql
    assert "slack_messages.slack_created_at <=" in session.sql
    assert "slack_messages.channel_id = 'C123'" in session.sql
    assert "slack_messages.text IS NOT NULL" in session.sql
