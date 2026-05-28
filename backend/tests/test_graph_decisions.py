"""Tests for decision-specific graph endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.dependencies import UserContext
from src.models.graph_node import GraphNode
from src.models.telegram import TelegramMessage
from src.routers.graph import _get_connected_providers, get_decision, get_decisions

WORKSPACE_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def _user() -> UserContext:
    return UserContext(
        user_id=USER_ID,
        email="test@example.com",
        workspace_id=WORKSPACE_ID,
    )


def _result_all(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _result_one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _decision(
    name: str,
    date: str,
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> GraphNode:
    node = GraphNode(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        entity_type="Decision",
        name=name,
        fingerprint=f"decision:{name}",
        source_type="messages_digest",
        properties={"date": date, "source": "slack"},
    )
    node.created_at = created_at or datetime(2026, 5, 20, 11, 0, 0)
    node.updated_at = updated_at or datetime(2026, 5, 20, 11, 30, 0)
    return node


@pytest.mark.asyncio
async def test_get_decisions_returns_all_decisions_sorted_by_capture_recency(
    mock_settings,
) -> None:
    """New captures stay visible even when their source date is older."""
    session = AsyncMock()
    captured_old_source = _decision(
        "Captured old source decision",
        "2026-05-16",
        created_at=datetime(2026, 5, 21, 9, 0, 0),
    )
    older_suggested = _decision(
        "Use a Bottom Sheet for menu visuals in the RD-752 release",
        "2026-05-04",
        created_at=datetime(2026, 5, 19, 9, 0, 0),
    )
    recent = _decision(
        "Branch names must contain exactly one dash",
        "2026-05-22",
        created_at=datetime(2026, 5, 18, 9, 0, 0),
    )
    oldest_suggested = _decision(
        "Add a new button to the interface as part of the task implementation.",
        "2026-04-22",
        created_at=datetime(2026, 5, 17, 9, 0, 0),
    )
    session.execute.return_value = _result_all([
        older_suggested,
        recent,
        oldest_suggested,
        captured_old_source,
    ])

    connected = AsyncMock(return_value={"slack"})
    with patch("src.routers.graph._get_connected_providers", new=connected):
        rows = await get_decisions(user=_user(), session=session, limit=100)

    assert [row.name for row in rows] == [
        "Captured old source decision",
        "Use a Bottom Sheet for menu visuals in the RD-752 release",
        "Branch names must contain exactly one dash",
        "Add a new button to the interface as part of the task implementation.",
    ]


@pytest.mark.asyncio
async def test_get_decision_returns_edge_less_digest_decision(mock_settings) -> None:
    """Suggestion-linked digest decisions must be fetchable by ID directly."""
    session = AsyncMock()
    decision = _decision(
        "Add a new button to the interface as part of the task implementation.",
        "2026-04-22",
    )
    session.execute.return_value = _result_one(decision)

    connected = AsyncMock(return_value={"slack"})
    with patch("src.routers.graph._get_connected_providers", new=connected):
        row = await get_decision(decision_id=decision.id, user=_user(), session=session)

    assert row.id == str(decision.id)
    assert row.created_at == "2026-05-20T11:00:00"
    assert row.updated_at == "2026-05-20T11:30:00"
    assert (
        row.name
        == "Add a new button to the interface as part of the task implementation."
    )


@pytest.mark.asyncio
async def test_get_decision_raises_404_for_missing_decision(mock_settings) -> None:
    session = AsyncMock()
    session.execute.return_value = _result_one(None)

    with pytest.raises(HTTPException) as error:
        await get_decision(decision_id=uuid4(), user=_user(), session=session)

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_connected_providers_include_active_telegram_chat_mapping(
    mock_settings,
) -> None:
    session = AsyncMock()
    active_chat = MagicMock()
    active_chat.chat_id = -100123
    session.execute = AsyncMock(
        side_effect=[
            _result_all([]),
            _result_one(active_chat.chat_id),
        ]
    )

    providers = await _get_connected_providers(session, WORKSPACE_ID)

    assert "telegram" in providers


@pytest.mark.asyncio
async def test_get_decisions_keeps_fathom_transcript_decisions_visible(
    mock_settings,
) -> None:
    session = AsyncMock()
    decision = _decision("Use Fathom-sourced rollout decision", "2026-05-28")
    decision.source_type = "fathom_transcript"
    session.execute.return_value = _result_all([decision])

    connected = AsyncMock(return_value={"fathom"})
    with patch("src.routers.graph._get_connected_providers", new=connected):
        rows = await get_decisions(user=_user(), session=session, limit=100)

    assert [row.name for row in rows] == ["Use Fathom-sourced rollout decision"]


@pytest.mark.asyncio
async def test_get_decisions_hydrates_missing_telegram_attribution(
    mock_settings,
) -> None:
    session = AsyncMock()
    message = TelegramMessage(
        workspace_id=WORKSPACE_ID,
        chat_id=-1003644773967,
        chat_title="contextOS team",
        chat_type="supergroup",
        message_id=1356,
        from_first_name="Daulet",
        from_username="dxulet",
        text="supabase login",
        telegram_date=datetime(2026, 5, 25, 13, 22, 59),
    )
    decision = GraphNode(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        entity_type="Decision",
        name="Apply Supabase migrations",
        fingerprint="decision:apply-supabase-migrations",
        source_type="telegram_message",
        source_id=message.id,
        properties={
            "source_quote": "supabase login",
            "source_type": "telegram_message",
            "source_id": str(message.id),
            "participants": [],
        },
    )
    decision.created_at = datetime(2026, 5, 28, 11, 4, 35)
    session.execute = AsyncMock(
        side_effect=[
            _result_all([decision]),
            _result_all([message]),
        ]
    )

    connected = AsyncMock(return_value={"telegram"})
    with patch("src.routers.graph._get_connected_providers", new=connected):
        rows = await get_decisions(user=_user(), session=session, limit=100)

    assert rows[0].properties["author_name"] == "Daulet"
    assert rows[0].properties["person_name"] == "Daulet"
    assert rows[0].properties["participants"] == ["Daulet"]
    assert rows[0].properties["source_context"] == "contextOS team"
    assert rows[0].properties["date"] == "2026-05-25T13:22:59"
