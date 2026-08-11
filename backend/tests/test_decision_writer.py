"""Unit tests for the canonical decision write path (decision_writer)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.decision import Decision, DecisionEvidence, DecisionVersion
from src.models.suggestion import Suggestion
from src.services import decision_writer as dw
from src.services.decision_relations import RelationVerdict
from src.services.decision_writer import (
    ConsequentialityVerdict,
    DecisionDraft,
    EvidenceRef,
    WriteOutcome,
    change_status,
    create_decision,
)

WS = uuid.uuid4()


def _draft(**overrides) -> DecisionDraft:
    defaults = dict(
        statement="Postpone the auth migration until Q1",
        rationale="Team capacity",
        producer="missed_decision",
        evidence=[
            EvidenceRef(
                source_type="slack_message",
                source_id=uuid.uuid4(),
                quote="let's push auth migration to Q1",
                source_link="https://slack.example/msg",
            )
        ],
    )
    defaults.update(overrides)
    return DecisionDraft(**defaults)


def _session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


def _added(session: MagicMock, model: type) -> list:
    return [
        c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], model)
    ]


_GOOD = ConsequentialityVerdict(
    is_decision=True, consequential=True, score=0.9, reason="clear commitment"
)
_JUNK = ConsequentialityVerdict(
    is_decision=False, consequential=False, score=0.1, reason="status update"
)


@pytest.mark.asyncio
async def test_rejects_non_consequential_and_writes_nothing():
    session = _session()
    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_JUNK)),
        patch.object(dw, "_find_similar_active", AsyncMock(return_value=[])),
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.REJECTED_NOT_CONSEQUENTIAL
    assert result.decision_id is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_merges_as_evidence_instead_of_creating():
    session = _session()
    existing_id = uuid.uuid4()
    existing = Decision(
        id=existing_id, workspace_id=WS, statement="Auth migration moved to Q1",
        producer="missed_decision", status="active",
    )
    session.get.return_value = existing
    version_result = MagicMock()
    version_result.scalar_one.return_value = 1
    session.execute.return_value = version_result

    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_GOOD)),
        patch.object(
            dw,
            "_find_similar_active",
            AsyncMock(return_value=[(existing_id, "Auth migration moved to Q1", 0.8)]),
        ),
        patch.object(
            dw,
            "classify_decision_relation",
            AsyncMock(
                return_value=RelationVerdict(
                    relation="SAME", confidence=0.9, rationale="same decision"
                )
            ),
        ),
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.MERGED_AS_EVIDENCE
    assert result.decision_id == existing_id
    assert len(_added(session, DecisionEvidence)) == 1
    versions = _added(session, DecisionVersion)
    assert len(versions) == 1 and versions[0].change_type == "evidence_added"
    assert not _added(session, Decision)


@pytest.mark.asyncio
async def test_creates_decision_with_version_evidence_and_mirror_node():
    session = _session()
    node_id = uuid.uuid4()

    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_GOOD)),
        patch.object(dw, "_find_similar_active", AsyncMock(return_value=[])),
        patch.object(dw, "upsert_node", AsyncMock(return_value=node_id)) as mock_node,
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.CREATED
    decisions = _added(session, Decision)
    assert len(decisions) == 1
    d = decisions[0]
    assert d.status == "active"
    assert d.consequentiality_score == 0.9
    assert d.graph_node_id == node_id
    versions = _added(session, DecisionVersion)
    assert len(versions) == 1 and versions[0].version == 1
    assert versions[0].change_type == "created"
    assert len(_added(session, DecisionEvidence)) == 1
    mock_node.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_failure_degrades_to_tentative_not_rejection():
    session = _session()
    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=None)),
        patch.object(dw, "_find_similar_active", AsyncMock(return_value=[])),
        patch.object(dw, "upsert_node", AsyncMock(return_value=uuid.uuid4())),
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.CREATED
    assert _added(session, Decision)[0].status == "tentative"


@pytest.mark.asyncio
async def test_report_mode_stores_score_but_never_rejects():
    session = _session()
    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_JUNK)),
        patch.object(dw, "_find_similar_active", AsyncMock(return_value=[])),
        patch.object(dw, "upsert_node", AsyncMock(return_value=uuid.uuid4())),
    ):
        result = await create_decision(
            session, WS, _draft(producer="import"), actor="import", gate_mode="report"
        )

    assert result.outcome is WriteOutcome.CREATED
    d = _added(session, Decision)[0]
    assert d.consequentiality_score == 0.1


@pytest.mark.asyncio
async def test_change_status_snapshots_before_write_and_links_supersession():
    session = _session()
    decision_id = uuid.uuid4()
    superseding_id = uuid.uuid4()
    decision = Decision(
        id=decision_id, workspace_id=WS, statement="Ship self-hosted in Q4",
        producer="missed_decision", status="active", graph_node_id=None,
    )
    session.get.return_value = decision
    version_result = MagicMock()
    version_result.scalar_one.return_value = 3
    session.execute.return_value = version_result

    await change_status(
        session, WS, decision_id, "superseded",
        reason="replaced by Q1 plan", actor="test", superseded_by=superseding_id,
    )

    versions = _added(session, DecisionVersion)
    assert len(versions) == 1
    assert versions[0].version == 4
    assert versions[0].snapshot["status"] == "active"  # BEFORE-write snapshot
    assert versions[0].change_type == "superseded"
    assert decision.status == "superseded"
    assert decision.valid_until is not None
    edges = _added(session, dw.DecisionEdge)
    assert len(edges) == 1
    assert edges[0].from_decision == superseding_id
    assert edges[0].edge_type == "supersedes"


@pytest.mark.asyncio
async def test_change_status_rejects_invalid_status():
    session = _session()
    with pytest.raises(ValueError):
        await change_status(
            session, WS, uuid.uuid4(), "cancelled", reason="", actor="t"
        )


def _verdict(relation: str, confidence: float = 0.9) -> RelationVerdict:
    return RelationVerdict(relation=relation, confidence=confidence, rationale="r")


@pytest.mark.asyncio
async def test_supersedes_creates_decision_with_edge_and_proposal():
    session = _session()
    old_id = uuid.uuid4()
    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_GOOD)),
        patch.object(
            dw,
            "_find_similar_active",
            AsyncMock(return_value=[(old_id, "Ship in Q4", 0.6)]),
        ),
        patch.object(
            dw,
            "classify_decision_relation",
            AsyncMock(return_value=_verdict("SUPERSEDES")),
        ),
        patch.object(dw, "upsert_node", AsyncMock(return_value=uuid.uuid4())),
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.CREATED
    assert result.relation == "SUPERSEDES"
    assert result.related_decision_id == old_id
    edges = _added(session, dw.DecisionEdge)
    assert len(edges) == 1
    assert edges[0].edge_type == "supersedes"
    assert edges[0].to_decision == old_id
    suggestions = _added(session, Suggestion)
    assert len(suggestions) == 1
    assert suggestions[0].type == "decision_relation"
    assert suggestions[0].evidence["relation"] == "SUPERSEDES"


@pytest.mark.asyncio
async def test_refines_creates_edge_without_proposal():
    session = _session()
    old_id = uuid.uuid4()
    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_GOOD)),
        patch.object(
            dw,
            "_find_similar_active",
            AsyncMock(return_value=[(old_id, "Postgres everywhere", 0.5)]),
        ),
        patch.object(
            dw,
            "classify_decision_relation",
            AsyncMock(return_value=_verdict("REFINES")),
        ),
        patch.object(dw, "upsert_node", AsyncMock(return_value=uuid.uuid4())),
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.CREATED
    assert result.relation == "REFINES"
    assert len(_added(session, dw.DecisionEdge)) == 1
    assert _added(session, Suggestion) == []


@pytest.mark.asyncio
async def test_low_confidence_relation_falls_through_to_plain_create():
    session = _session()
    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_GOOD)),
        patch.object(
            dw,
            "_find_similar_active",
            AsyncMock(return_value=[(uuid.uuid4(), "Vaguely similar", 0.4)]),
        ),
        patch.object(
            dw,
            "classify_decision_relation",
            AsyncMock(return_value=_verdict("SUPERSEDES", confidence=0.4)),
        ),
        patch.object(dw, "upsert_node", AsyncMock(return_value=uuid.uuid4())),
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.CREATED
    assert result.relation is None
    assert _added(session, dw.DecisionEdge) == []
    assert _added(session, Suggestion) == []


@pytest.mark.asyncio
async def test_classifier_failure_treated_as_unrelated():
    session = _session()
    with (
        patch.object(dw, "_assess_consequentiality", AsyncMock(return_value=_GOOD)),
        patch.object(
            dw,
            "_find_similar_active",
            AsyncMock(return_value=[(uuid.uuid4(), "Similar", 0.5)]),
        ),
        patch.object(
            dw, "classify_decision_relation", AsyncMock(return_value=None)
        ),
        patch.object(dw, "upsert_node", AsyncMock(return_value=uuid.uuid4())),
    ):
        result = await create_decision(session, WS, _draft(), actor="test")

    assert result.outcome is WriteOutcome.CREATED
    assert len(_added(session, Decision)) == 1
