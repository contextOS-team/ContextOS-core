"""Tests for decision-specific graph endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.dependencies import UserContext
from src.models.graph_node import GraphNode
from src.routers.graph import get_decision, get_decisions

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


def _decision(name: str, date: str) -> GraphNode:
    return GraphNode(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        entity_type="Decision",
        name=name,
        fingerprint=f"decision:{name}",
        source_type="messages_digest",
        properties={"date": date, "source": "slack"},
    )


@pytest.mark.asyncio
async def test_get_decisions_returns_all_decisions_sorted_by_date(
    mock_settings,
) -> None:
    """The Decisions page needs all decisions, not the graph top-node subset."""
    session = AsyncMock()
    older_suggested = _decision(
        "Use a Bottom Sheet for menu visuals in the RD-752 release",
        "2026-05-04",
    )
    recent = _decision("Branch names must contain exactly one dash", "2026-05-22")
    oldest_suggested = _decision(
        "Add a new button to the interface as part of the task implementation.",
        "2026-04-22",
    )
    session.execute.return_value = _result_all([
        older_suggested,
        recent,
        oldest_suggested,
    ])

    connected = AsyncMock(return_value={"slack"})
    with patch("src.routers.graph._get_connected_providers", new=connected):
        rows = await get_decisions(user=_user(), session=session, limit=100)

    assert [row.name for row in rows] == [
        "Branch names must contain exactly one dash",
        "Use a Bottom Sheet for menu visuals in the RD-752 release",
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
