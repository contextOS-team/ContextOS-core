"""Tests for missed-decision promotion into decision memory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.models.graph_node import GraphNode
from src.models.missed_decision import MissedDecisionCandidate
from src.services.missed_decision_actions import (
    add_candidate_as_evidence,
    confirm_candidate,
    promote_candidate_to_decision,
)
from tests.conftest import TEST_USER_ID, TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)
USER_ID = UUID(TEST_USER_ID)


def _result(values):
    result = MagicMock()
    result.scalar_one_or_none.return_value = values[0] if values else None
    result.scalars.return_value.all.return_value = values
    return result


def _candidate(**overrides) -> MissedDecisionCandidate:
    values = {
        "id": uuid4(),
        "workspace_id": WORKSPACE_ID,
        "scan_run_id": uuid4(),
        "suggestion_id": uuid4(),
        "source_type": "fathom_transcript",
        "source_id": uuid4(),
        "source_quote": "We decided to preserve Decision Receipts before actions.",
        "inferred_decision": "Preserve Decision Receipts before actions",
        "inferred_rationale": "Actions need provenance before automation.",
        "source_link": (
            "/dashboard/source-reference?source_type=fathom_transcript"
            "&source_id=abc&workspace_id=def"
            "&source_timestamp=2026-05-25T09:00:00Z"
        ),
        "confidence": "very_high",
        "quote_fingerprint": "quote-fp",
        "decision_fingerprint": "decision-fp",
        "lifecycle_status": "surfaced",
        "match_status": "no_match",
        "people": ["Daulet"],
        "affected_systems": ["actions"],
        "action_hints": [{"kind": "linear", "title": "Create follow-up ticket"}],
        "evidence": {"source": "fathom"},
    }
    values.update(overrides)
    return MissedDecisionCandidate(**values)


@pytest.mark.asyncio
async def test_promote_candidate_to_decision_preserves_source_trail() -> None:
    candidate = _candidate()
    session = AsyncMock()
    decision_node_id = uuid4()

    with patch(
        "src.services.missed_decision_actions.upsert_node",
        new=AsyncMock(return_value=decision_node_id),
    ) as upsert_node, patch(
        "src.services.missed_decision_actions.upsert_edge",
        new=AsyncMock(return_value=uuid4()),
    ) as upsert_edge:
        result = await promote_candidate_to_decision(session, candidate)

    assert result == decision_node_id
    call = upsert_node.await_args
    assert call.kwargs["entity_type"] == "Decision"
    assert call.kwargs["name"] == candidate.inferred_decision
    props = call.kwargs["properties"]
    assert props["description"] == candidate.inferred_decision
    assert props["rationale"] == candidate.inferred_rationale
    assert props["source_quote"] == candidate.source_quote
    assert props["source_link"] == candidate.source_link
    assert props["confidence"] == candidate.confidence
    assert props["participants"] == candidate.people
    assert props["affected_systems"] == candidate.affected_systems
    assert props["candidate_id"] == str(candidate.id)
    assert props["scan_run_id"] == str(candidate.scan_run_id)
    assert props["action_hints"] == candidate.action_hints
    upsert_edge.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_promotes_before_resolving_suggestion() -> None:
    candidate = _candidate()
    decision_node_id = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))
    session.flush = AsyncMock()
    calls: list[str] = []

    async def fake_upsert_node(*_args, **_kwargs):
        calls.append("promote")
        return decision_node_id

    async def fake_resolve(*_args, **_kwargs):
        calls.append("resolve")

    with patch(
        "src.services.missed_decision_actions.upsert_node",
        new=fake_upsert_node,
    ), patch(
        "src.services.missed_decision_actions.upsert_edge",
        new=AsyncMock(return_value=uuid4()),
    ), patch(
        "src.services.missed_decision_actions.resolve_suggestion",
        new=fake_resolve,
    ):
        confirmed = await confirm_candidate(
            session,
            WORKSPACE_ID,
            USER_ID,
            candidate.id,
        )

    assert confirmed.decision_node_id == decision_node_id
    assert candidate.lifecycle_status == "confirmed"
    assert candidate.matched_entity_type == "graph_node"
    assert calls == ["promote", "resolve"]


@pytest.mark.asyncio
async def test_add_evidence_links_candidate_to_existing_decision() -> None:
    existing_decision = GraphNode(
        id=uuid4(),
        workspace_id=WORKSPACE_ID,
        entity_type="Decision",
        name="Preserve Decision Receipts before actions",
        fingerprint="decision",
        properties={"evidence": []},
    )
    candidate = _candidate(
        match_status="weak_match",
        matched_entity_type="graph_node",
        matched_entity_id=existing_decision.id,
    )
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_result([candidate]), _result([existing_decision])]
    )
    session.flush = AsyncMock()

    with patch(
        "src.services.missed_decision_actions.resolve_suggestion",
        new=AsyncMock(),
    ), patch(
        "src.services.missed_decision_actions.upsert_edge",
        new=AsyncMock(return_value=uuid4()),
    ):
        linked = await add_candidate_as_evidence(
            session,
            WORKSPACE_ID,
            USER_ID,
            candidate.id,
        )

    assert linked.lifecycle_status == "linked"
    assert existing_decision.properties["missed_decision_evidence"][0][
        "source_quote"
    ] == candidate.source_quote


@pytest.mark.asyncio
async def test_action_hints_remain_inert_metadata() -> None:
    candidate = _candidate()
    session = AsyncMock()
    decision_node_id = uuid4()

    with patch(
        "src.services.missed_decision_actions.upsert_node",
        new=AsyncMock(return_value=decision_node_id),
    ) as upsert_node, patch(
        "src.services.missed_decision_actions.upsert_edge",
        new=AsyncMock(return_value=uuid4()),
    ):
        await promote_candidate_to_decision(session, candidate)

    props = upsert_node.await_args.kwargs["properties"]
    assert props["action_hints"] == candidate.action_hints
