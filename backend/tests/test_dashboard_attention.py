"""Tests for dashboard attention aggregation."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.services.dashboard_attention import (
    _is_terminal_provider_state,
    get_attention_items,
)
from tests.conftest import TEST_WORKSPACE_ID


def _context_page(
    *,
    status: str = "ready",
    sources: list[dict] | None = None,
    ticket_identifier: str = "RD-786",
) -> MagicMock:
    page = MagicMock()
    page.id = uuid4()
    page.ticket_identifier = ticket_identifier
    page.title = "Context: Done Jira ticket"
    page.status = status
    page.sources = [] if sources is None else sources
    page.updated_at = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)
    return page


def _empty_scalars_result() -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


def _session_for_context_rows(
    rows: list[tuple[MagicMock, str | None, str | None]],
) -> AsyncMock:
    session = AsyncMock()
    context_result = MagicMock()
    context_result.all.return_value = rows
    session.execute.side_effect = [
        context_result,
        _empty_scalars_result(),
        _empty_scalars_result(),
    ]
    return session


def test_is_terminal_ticket_status_normalizes_common_done_states() -> None:
    assert _is_terminal_provider_state(None, "done") is True
    assert _is_terminal_provider_state("completed", None) is True
    assert _is_terminal_provider_state("canceled", None) is True
    assert _is_terminal_provider_state(None, "Done") is True
    assert _is_terminal_provider_state(None, None) is False
    assert _is_terminal_provider_state("started", "indeterminate") is False


@pytest.mark.asyncio
async def test_attention_skips_jira_context_when_status_category_is_done() -> None:
    session = _session_for_context_rows([(_context_page(), None, "done")])

    items = await get_attention_items(session, UUID(TEST_WORKSPACE_ID))

    assert items == []


@pytest.mark.asyncio
async def test_attention_skips_jira_context_when_status_category_is_completed() -> None:
    session = _session_for_context_rows([(_context_page(), None, "completed")])

    items = await get_attention_items(session, UUID(TEST_WORKSPACE_ID))

    assert items == []


@pytest.mark.asyncio
async def test_attention_skips_completed_linear_context_with_no_sources() -> None:
    session = _session_for_context_rows(
        [(_context_page(ticket_identifier="ENG-42"), "completed", None)]
    )

    items = await get_attention_items(session, UUID(TEST_WORKSPACE_ID))

    assert items == []


@pytest.mark.asyncio
async def test_attention_keeps_active_context_with_no_sources() -> None:
    page = _context_page()
    session = _session_for_context_rows([(page, "started", "indeterminate")])

    items = await get_attention_items(session, UUID(TEST_WORKSPACE_ID))

    assert items == [
        {
            "type": "no_sources",
            "id": str(page.id),
            "title": "Context: Done Jira ticket",
            "ticket_identifier": "RD-786",
            "status": "ready",
        }
    ]
