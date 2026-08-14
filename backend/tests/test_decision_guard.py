"""Tests for the advisory Decision Guard (check_action)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.decision import Decision
from src.models.decision_guard import GuardVerdict
from src.services import decision_guard as dg
from src.services.decision_guard import (
    STATUS_NO_CONFLICT,
    STATUS_POTENTIAL,
    STATUS_REQUIRES_REVIEW,
    GuardAssessment,
    check_action,
)

WS = uuid.uuid4()


def _decision(statement: str, **over) -> Decision:
    values = dict(
        id=uuid.uuid4(),
        workspace_id=WS,
        statement=statement,
        status="active",
        producer="missed_decision",
        consequentiality_score=0.9,
    )
    values.update(over)
    return Decision(**values)


def _session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


def _added(session, model):
    return [
        c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], model)
    ]


@pytest.mark.asyncio
async def test_no_relevant_decisions_is_no_known_conflict():
    session = _session()
    with patch.object(dg, "_relevant_decisions", AsyncMock(return_value=[])):
        result = await check_action(session, WS, "rename a helper", actor="test")
    assert result.status == STATUS_NO_CONFLICT
    assert result.decisions == []
    # verdict still persisted (eval set)
    verdicts = _added(session, GuardVerdict)
    assert len(verdicts) == 1 and verdicts[0].status == STATUS_NO_CONFLICT


@pytest.mark.asyncio
async def test_potential_conflict_surfaces_driving_decisions():
    session = _session()
    decision = _decision("PostgreSQL is the only production datastore")
    with (
        patch.object(dg, "_relevant_decisions", AsyncMock(return_value=[decision])),
        patch.object(dg, "_active_exceptions", AsyncMock(return_value={})),
        patch.object(
            dg,
            "get_llm_client",
            return_value=_llm(
                GuardAssessment(
                    status="potential_conflict",
                    rationale="adds a new datastore",
                    confidence=0.9,
                )
            ),
        ),
    ):
        result = await check_action(session, WS, "add MongoDB", actor="test")
    assert result.status == STATUS_POTENTIAL
    assert result.decisions[0]["statement"].startswith("PostgreSQL")
    verdict = _added(session, GuardVerdict)[0]
    assert verdict.considered_decision_ids == [str(decision.id)]


@pytest.mark.asyncio
async def test_exception_makes_conflict_no_known_conflict_input():
    session = _session()
    decision = _decision("PostgreSQL is the only production datastore")
    with (
        patch.object(dg, "_relevant_decisions", AsyncMock(return_value=[decision])),
        patch.object(
            dg,
            "_active_exceptions",
            AsyncMock(
                return_value={str(decision.id): ["analytics — approved"]}
            ),
        ),
        patch.object(
            dg,
            "get_llm_client",
            return_value=_llm(
                GuardAssessment(
                    status="no_known_conflict",
                    rationale="sanctioned by exception",
                    confidence=0.8,
                )
            ),
        ),
    ):
        result = await check_action(
            session, WS, "add MongoDB for analytics", actor="t"
        )
    assert result.status == STATUS_NO_CONFLICT
    assert result.decisions[0]["has_exception"] is True


@pytest.mark.asyncio
async def test_llm_failure_degrades_to_requires_review():
    session = _session()
    decision = _decision("Frontend standardized on React")
    failing = MagicMock()
    failing.generate_json = AsyncMock(side_effect=RuntimeError("llm down"))
    with (
        patch.object(dg, "_relevant_decisions", AsyncMock(return_value=[decision])),
        patch.object(dg, "_active_exceptions", AsyncMock(return_value={})),
        patch.object(dg, "get_llm_client", return_value=failing),
    ):
        result = await check_action(session, WS, "build in Vue", actor="test")
    assert result.status == STATUS_REQUIRES_REVIEW
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_invalid_llm_status_coerced_to_requires_review():
    session = _session()
    decision = _decision("Redis is the approved cache")
    with (
        patch.object(dg, "_relevant_decisions", AsyncMock(return_value=[decision])),
        patch.object(dg, "_active_exceptions", AsyncMock(return_value={})),
        patch.object(
            dg,
            "get_llm_client",
            return_value=_llm(
                GuardAssessment(status="ALLOWED", rationale="x", confidence=1.0)
            ),
        ),
    ):
        result = await check_action(session, WS, "swap cache", actor="test")
    assert result.status == STATUS_REQUIRES_REVIEW


def _llm(assessment: GuardAssessment) -> MagicMock:
    client = MagicMock()
    client.generate_json = AsyncMock(return_value=assessment)
    return client
