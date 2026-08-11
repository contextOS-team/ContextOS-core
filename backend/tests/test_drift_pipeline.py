"""Unit tests for the drift pipeline: inference, checker, verifier, engine."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.decision import Decision
from src.models.decision_drift import ArtifactObservation, Drift, ExpectedConsequence
from src.models.suggestion import Suggestion
from src.services import drift_engine as de
from src.services import impact_inference as ii
from src.services.impact_inference import (
    ConsequenceDraft,
    ImpactInferenceResult,
    infer_expected_consequences,
)
from src.services.skeptical_verifier import VerifierVerdict

WS = uuid.uuid4()


def _decision(**overrides) -> Decision:
    values = dict(
        id=uuid.uuid4(),
        workspace_id=WS,
        statement="Postpone the auth migration until Q1",
        rationale="Capacity",
        status="active",
        producer="missed_decision",
        consequentiality_score=0.9,
    )
    values.update(overrides)
    return Decision(**values)


def _consequence(decision: Decision, **overrides) -> ExpectedConsequence:
    values = dict(
        id=uuid.uuid4(),
        workspace_id=WS,
        decision_id=decision.id,
        target_type="linear",
        target_query="auth migration",
        expected_state="Auth migration tickets no longer target Q3",
        importance="high",
        status="pending",
    )
    values.update(overrides)
    return ExpectedConsequence(**values)


def _observation(consequence: ExpectedConsequence, consistent) -> ArtifactObservation:
    return ArtifactObservation(
        id=uuid.uuid4(),
        workspace_id=WS,
        expected_consequence_id=consequence.id,
        checker="linear",
        observed_state="Tickets still target Q3",
        consistent=consistent,
        evidence=[{"source_type": "linear_ticket", "source_id": "x", "excerpt": "Q3"}],
    )


def _session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


def _added(session: MagicMock, model: type) -> list:
    return [
        c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], model)
    ]


def _empty_result() -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


@pytest.mark.asyncio
async def test_impact_inference_persists_capped_validated_rows():
    session = _session()
    session.execute.return_value = _empty_result()
    decision = _decision()
    drafts = [
        ConsequenceDraft(
            target_type="linear",
            target_query="auth migration",
            expected_state="no Q3 target",
            rationale="r",
            importance="high",
            confidence=0.9,
        ),
        ConsequenceDraft(
            target_type="bogus_type",
            target_query="q",
            expected_state="s",
            rationale="r",
            importance="urgent",
            confidence=1.7,
        ),
    ]
    client = MagicMock()
    client.generate_json = AsyncMock(
        return_value=ImpactInferenceResult(consequences=drafts)
    )
    with patch.object(ii, "get_llm_client", return_value=client):
        rows = await infer_expected_consequences(session, decision)

    assert len(rows) == 2
    assert rows[1].target_type == "other"  # unknown type coerced
    assert rows[1].importance == "medium"  # unknown importance coerced
    assert rows[1].confidence == 1.0  # clamped
    assert len(_added(session, ExpectedConsequence)) == 2


@pytest.mark.asyncio
async def test_impact_inference_is_idempotent_per_decision():
    session = _session()
    existing = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    session.execute.return_value = result
    client = MagicMock()
    client.generate_json = AsyncMock()
    with patch.object(ii, "get_llm_client", return_value=client):
        rows = await infer_expected_consequences(session, _decision())

    assert rows == [existing]
    client.generate_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_creates_drift_for_surviving_finding():
    session = _session()
    decision = _decision(graph_node_id=uuid.uuid4())
    consequence = _consequence(decision)
    pending_result = MagicMock()
    pending_result.all.return_value = [(consequence, decision)]
    session.execute.return_value = pending_result

    verdict = VerifierVerdict(
        is_meaningful_drift=True,
        kill_reason=None,
        severity="high",
        summary="Auth tickets still target Q3 despite the Q1 postponement",
        confidence=0.9,
    )
    with (
        patch.object(de, "decisions_needing_inference", AsyncMock(return_value=[])),
        patch.object(
            de,
            "check_consequence",
            AsyncMock(return_value=_observation(consequence, consistent=False)),
        ),
        patch.object(de, "verify_drift", AsyncMock(return_value=verdict)),
        patch.object(de, "_has_open_drift", AsyncMock(return_value=False)),
    ):
        stats = await de.scan_workspace_for_drift(session, WS)

    assert stats.inconsistent_found == 1
    assert stats.drifts_created == 1
    drifts = _added(session, Drift)
    assert len(drifts) == 1
    assert drifts[0].severity == "high"
    suggestions = _added(session, Suggestion)
    assert len(suggestions) == 1
    assert suggestions[0].type == "decision_drift"


@pytest.mark.asyncio
async def test_engine_verifier_kill_creates_no_drift():
    session = _session()
    decision = _decision()
    consequence = _consequence(decision)
    pending_result = MagicMock()
    pending_result.all.return_value = [(consequence, decision)]
    session.execute.return_value = pending_result

    kill = VerifierVerdict(
        is_meaningful_drift=False,
        kill_reason="semantic wording difference, not real drift",
        severity="low",
        summary="not meaningful",
        confidence=0.8,
    )
    with (
        patch.object(de, "decisions_needing_inference", AsyncMock(return_value=[])),
        patch.object(
            de,
            "check_consequence",
            AsyncMock(return_value=_observation(consequence, consistent=False)),
        ),
        patch.object(de, "verify_drift", AsyncMock(return_value=kill)),
    ):
        stats = await de.scan_workspace_for_drift(session, WS)

    assert stats.killed_by_verifier == 1
    assert stats.drifts_created == 0
    assert _added(session, Drift) == []
    assert stats.kill_reasons == ["semantic wording difference, not real drift"]


@pytest.mark.asyncio
async def test_engine_consistent_observation_never_reaches_verifier():
    session = _session()
    decision = _decision()
    consequence = _consequence(decision)
    pending_result = MagicMock()
    pending_result.all.return_value = [(consequence, decision)]
    session.execute.return_value = pending_result

    with (
        patch.object(de, "decisions_needing_inference", AsyncMock(return_value=[])),
        patch.object(
            de,
            "check_consequence",
            AsyncMock(return_value=_observation(consequence, consistent=True)),
        ),
        patch.object(de, "verify_drift", AsyncMock()) as verify,
    ):
        stats = await de.scan_workspace_for_drift(session, WS)

    verify.assert_not_awaited()
    assert stats.inconsistent_found == 0
    assert stats.drifts_created == 0


@pytest.mark.asyncio
async def test_engine_unverifiable_finding_is_dropped_not_surfaced():
    session = _session()
    decision = _decision()
    consequence = _consequence(decision)
    pending_result = MagicMock()
    pending_result.all.return_value = [(consequence, decision)]
    session.execute.return_value = pending_result

    with (
        patch.object(de, "decisions_needing_inference", AsyncMock(return_value=[])),
        patch.object(
            de,
            "check_consequence",
            AsyncMock(return_value=_observation(consequence, consistent=False)),
        ),
        patch.object(de, "verify_drift", AsyncMock(return_value=None)),
    ):
        stats = await de.scan_workspace_for_drift(session, WS)

    assert stats.drifts_created == 0
    assert _added(session, Drift) == []
