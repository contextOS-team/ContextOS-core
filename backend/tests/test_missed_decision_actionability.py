"""Tests for missed-decision actionability routing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.integration import WorkspaceIntegration
from src.models.jira import JiraIssue
from src.models.missed_decision import MissedDecisionCandidate
from src.models.sync import SyncCursor
from src.models.ticket import LinearTicket
from src.services.missed_decision_actionability import (
    ACTION_ATTACH_EVIDENCE,
    ACTION_DRAFT_TICKET,
    ACTION_HOLD_FOR_REPROCESS,
    ACTION_SAVE_DECISION_RECEIPT,
    ACTION_SUPPRESS_ALREADY_BACKED,
    ACTIONABILITY_ACTIONABLE,
    ACTIONABILITY_ALREADY_BACKED,
    ACTIONABILITY_POSSIBLE_MATCH,
    ACTIONABILITY_STALE_SEARCH,
    WRITE_POLICY_AUTO_INTERNAL,
    WRITE_POLICY_DRAFT_EXTERNAL,
    WRITE_POLICY_REVIEW_REQUIRED,
    verify_candidate_actionability,
)
from src.services.missed_decision_dedupe import DedupeClassification


def _result(values):
    result = MagicMock()
    result.scalar_one_or_none.return_value = values[0] if values else None
    result.scalars.return_value.all.return_value = values
    return result


def _candidate(**overrides) -> MissedDecisionCandidate:
    source_time = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    workspace_id = uuid4()
    source_id = uuid4()
    values = {
        "workspace_id": workspace_id,
        "source_type": "slack_message",
        "source_id": source_id,
        "source_resource_id": "C123",
        "source_quote": "We decided billing rollout must have a deployment checklist.",
        "inferred_decision": "Billing rollout must have a deployment checklist",
        "inferred_rationale": "The release needs an explicit operational gate.",
        "source_link": (
            "/dashboard/source-reference?source_type=slack_message"
            f"&source_id={source_id}&workspace_id={workspace_id}"
            "&source_timestamp=2026-05-25T09%3A00%3A00%2B00%3A00"
        ),
        "confidence": "high",
        "quote_fingerprint": "quote-fp",
        "decision_fingerprint": "decision-fp",
        "people": ["Daulet"],
        "affected_systems": ["billing"],
        "action_hints": [],
        "evidence": {
            "source_created_at": source_time.isoformat(),
            "source_metadata": {"channel_name": "release"},
            "review_context": {
                "expected_artifact_type": "deployment_checklist",
                "expected_artifact": (
                    "Deployment checklist should document the billing rollout gate."
                ),
                "affected_object": "billing rollout",
                "searched_sources": ["Decision memory"],
            },
            "quality_gate": {"passed": True},
        },
    }
    values.update(overrides)
    return MissedDecisionCandidate(**values)


def _classification(**overrides) -> DedupeClassification:
    values = {
        "match_status": "no_match",
        "lifecycle_status": "detected",
        "should_publish_suggestion": True,
    }
    values.update(overrides)
    return DedupeClassification(**values)


@pytest.mark.asyncio
async def test_clear_ticket_gap_gets_single_draft_ticket_action() -> None:
    candidate = _candidate(
        evidence={
            "source_created_at": "2026-05-25T09:00:00+00:00",
            "source_metadata": {"channel_name": "release"},
            "review_context": {
                "expected_artifact_type": "jira_ticket",
                "expected_artifact": (
                    "Jira ticket should track the billing rollout gate."
                ),
                "affected_object": "billing rollout",
                "searched_sources": ["Decision memory"],
            },
            "quality_gate": {"passed": True},
        }
    )
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _result([]),  # integrations
            _result([]),  # sync cursors
            _result([]),  # linear tickets
            _result([]),  # linear comments
            _result([]),  # jira issues
            _result([]),  # jira comments
            _result([]),  # github prs
            _result([]),  # github reviews
            _result([]),  # gitlab mrs
            _result([]),  # gitlab reviews
            _result([]),  # notion pages
        ]
    )

    result = await verify_candidate_actionability(
        session,
        candidate,
        _classification(),
    )

    assert result.status == ACTIONABILITY_ACTIONABLE
    assert result.next_action.kind == ACTION_DRAFT_TICKET
    assert result.next_action.write_policy == WRITE_POLICY_DRAFT_EXTERNAL
    assert result.next_action.title.startswith("Track decision:")
    assert candidate.action_hints == [result.next_action.to_hint()]
    assert candidate.evidence["actionability"]["status"] == ACTIONABILITY_ACTIONABLE
    assert candidate.evidence["review_context"]["missing_artifact_status"] == (
        ACTIONABILITY_ACTIONABLE
    )


@pytest.mark.asyncio
async def test_safe_internal_memory_gap_gets_auto_internal_receipt_action() -> None:
    candidate = _candidate(
        confidence="very_high",
        source_quote="We decided to keep Decision Receipts before action prompts.",
        inferred_decision="Keep Decision Receipts before action prompts",
        inferred_rationale="Automation needs durable source provenance first.",
        affected_systems=["decision memory"],
        evidence={
            "source_created_at": "2026-05-25T09:00:00+00:00",
            "source_metadata": {"channel_name": "product"},
            "review_context": {
                "expected_artifact_type": "decision_receipt",
                "expected_artifact": "Decision Receipt should preserve this rule.",
                "affected_object": "Decision Receipts",
            },
            "quality_gate": {"passed": True},
        },
    )
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_result([]), _result([])])

    result = await verify_candidate_actionability(
        session,
        candidate,
        _classification(),
    )

    assert result.status == ACTIONABILITY_ACTIONABLE
    assert result.next_action.kind == ACTION_SAVE_DECISION_RECEIPT
    assert result.next_action.write_policy == WRITE_POLICY_AUTO_INTERNAL


@pytest.mark.asyncio
async def test_strong_match_suppresses_already_backed_candidate() -> None:
    matched_id = uuid4()
    candidate = _candidate()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_result([]), _result([])])

    result = await verify_candidate_actionability(
        session,
        candidate,
        _classification(
            match_status="strong_match",
            lifecycle_status="linked",
            should_publish_suggestion=False,
            matched_entity_type="graph_node",
            matched_entity_id=matched_id,
            matched_title="Billing rollout checklist",
            matched_href="https://jira.example/browse/BILL-1",
            match_reason="Strong Ticket match on decision wording.",
            suppression_reason="already_backed_by_artifact",
        ),
    )

    assert result.status == ACTIONABILITY_ALREADY_BACKED
    assert result.next_action.kind == ACTION_SUPPRESS_ALREADY_BACKED
    assert result.artifact_matches[0].entity_id == matched_id
    assert candidate.suppression_reason == "already_backed_by_artifact"


@pytest.mark.asyncio
async def test_weak_decision_match_is_actionable_attach_evidence() -> None:
    matched_id = uuid4()
    candidate = _candidate()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_result([]), _result([])])

    result = await verify_candidate_actionability(
        session,
        candidate,
        _classification(
            match_status="weak_match",
            lifecycle_status="detected",
            should_publish_suggestion=True,
            matched_entity_type="graph_node",
            matched_entity_id=matched_id,
            matched_title="Billing rollout guardrail",
            matched_href=f"/dashboard/decisions/{matched_id}",
            match_reason="Possible Decision match based on overlapping terms.",
        ),
    )

    assert result.status == ACTIONABILITY_ACTIONABLE
    assert result.next_action.kind == ACTION_ATTACH_EVIDENCE
    assert result.next_action.write_policy == WRITE_POLICY_REVIEW_REQUIRED
    assert result.next_action.target_entity_id == str(matched_id)


@pytest.mark.asyncio
async def test_weak_non_decision_match_blocks_auto_save() -> None:
    matched_id = uuid4()
    candidate = _candidate(confidence="very_high")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_result([]), _result([])])

    result = await verify_candidate_actionability(
        session,
        candidate,
        _classification(
            match_status="weak_match",
            lifecycle_status="detected",
            should_publish_suggestion=True,
            matched_entity_type="suggestion",
            matched_entity_id=matched_id,
            matched_title="Similar ticket gap",
            match_reason="Possible existing suggestion.",
        ),
    )

    assert result.status == ACTIONABILITY_POSSIBLE_MATCH
    assert result.next_action.kind == ACTION_HOLD_FOR_REPROCESS
    assert result.next_action.write_policy == WRITE_POLICY_REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_connected_stale_provider_routes_to_stale_search() -> None:
    source_time = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    candidate = _candidate(
        evidence={
            "source_created_at": source_time.isoformat(),
            "source_metadata": {"channel_name": "release"},
            "review_context": {
                "expected_artifact_type": "jira_ticket",
                "expected_artifact": (
                    "Jira ticket should track the billing rollout gate."
                ),
                "affected_object": "billing rollout",
            },
            "quality_gate": {"passed": True},
        }
    )
    stale_sync = (source_time - timedelta(hours=2)).replace(tzinfo=None)
    integration = WorkspaceIntegration(
        workspace_id=candidate.workspace_id,
        provider="jira",
        status="connected",
        config={"last_sync_at": stale_sync.isoformat()},
    )
    cursor = SyncCursor(
        workspace_id=candidate.workspace_id,
        provider="jira",
        resource_type="issues",
        last_sync_at=stale_sync,
    )
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_result([integration]), _result([cursor])])

    result = await verify_candidate_actionability(
        session,
        candidate,
        _classification(),
    )

    assert result.status == ACTIONABILITY_STALE_SEARCH
    assert result.next_action.kind == ACTION_HOLD_FOR_REPROCESS
    assert result.stale_providers == ["jira"]
    assert "jira" in candidate.evidence["actionability"]["stale_providers"]


@pytest.mark.asyncio
async def test_fresh_local_artifact_match_suppresses_existing_ticket() -> None:
    candidate = _candidate(
        inferred_decision="Billing rollout must have a deployment checklist",
        evidence={
            "source_created_at": "2026-05-25T09:00:00+00:00",
            "source_metadata": {"channel_name": "release"},
            "review_context": {
                "expected_artifact_type": "linear_ticket",
                "expected_artifact": (
                    "Linear ticket should track the billing rollout gate."
                ),
                "affected_object": "billing rollout",
            },
            "quality_gate": {"passed": True},
        },
    )
    linear = LinearTicket(
        id=uuid4(),
        workspace_id=candidate.workspace_id,
        linear_id="lin-1",
        identifier="BILL-1",
        title="Billing rollout must have a deployment checklist",
        description="The release needs an explicit operational gate.",
        status="Open",
    )
    jira = JiraIssue(
        id=uuid4(),
        workspace_id=candidate.workspace_id,
        jira_id="jira-1",
        jira_key="BILL-2",
        summary="Unrelated billing cleanup",
        description="No rollout gate here.",
    )
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _result([]),
            _result([]),
            _result([linear]),
            _result([]),
            _result([jira]),
            _result([]),
            _result([]),
            _result([]),
            _result([]),
            _result([]),
            _result([]),
        ]
    )

    result = await verify_candidate_actionability(
        session,
        candidate,
        _classification(),
    )

    assert result.status == ACTIONABILITY_ALREADY_BACKED
    assert result.next_action.kind == ACTION_SUPPRESS_ALREADY_BACKED
    assert result.artifact_matches[0].entity_type == "linear_ticket"
    assert result.artifact_matches[0].entity_id == linear.id
