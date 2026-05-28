"""Tests for missed-decision review lifecycle actions and endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.audit_log import AuditLog
from src.models.missed_decision import MissedDecisionCandidate, MissedDecisionScanRun
from src.services.missed_decision_actions import (
    CandidateNotFoundError,
    InvalidCandidateTransitionError,
    auto_confirm_candidate,
    confirm_candidate,
    defer_candidate,
    ignore_duplicate_candidate,
    list_review_candidates,
    reject_candidate,
)
from tests.conftest import TEST_EMAIL, TEST_USER_ID, TEST_WORKSPACE_ID

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
        "source_type": "slack_message",
        "source_id": uuid4(),
        "source_resource_id": "C123",
        "source_quote": "We decided to keep the review rail bounded.",
        "inferred_decision": "Keep the review rail bounded",
        "inferred_rationale": "Confirmed decisions remain primary.",
        "source_link": (
            "/dashboard/source-reference?source_type=slack_message"
            "&source_id=abc&workspace_id=def"
            "&source_timestamp=2026-05-25T09:00:00Z"
        ),
        "confidence": "high",
        "quote_fingerprint": "quote-fp",
        "decision_fingerprint": "decision-fp",
        "lifecycle_status": "surfaced",
        "match_status": "no_match",
        "people": ["Daulet"],
        "affected_systems": ["dashboard"],
        "action_hints": [{"kind": "ticket", "title": "Document it"}],
        "evidence": {"source": "slack"},
    }
    values.update(overrides)
    return MissedDecisionCandidate(**values)


def _scan_run(**overrides) -> MissedDecisionScanRun:
    values = {
        "id": uuid4(),
        "workspace_id": WORKSPACE_ID,
        "source_type": "slack_message",
        "source_resource_id": "C123",
        "status": "running",
        "sources_scanned": 4,
        "sources_total": 10,
        "candidates_created": 2,
        "started_at": datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
        "completed_at": None,
        "error_message": None,
        "created_at": datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return MissedDecisionScanRun(**values)


@pytest.mark.asyncio
async def test_actions_load_candidates_by_workspace() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([]))

    with pytest.raises(CandidateNotFoundError):
        await reject_candidate(session, WORKSPACE_ID, USER_ID, uuid4())


@pytest.mark.asyncio
async def test_surfaced_candidate_legal_transitions() -> None:
    candidate = _candidate()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))
    session.flush = AsyncMock()

    with patch(
        "src.services.missed_decision_actions.resolve_suggestion",
        new=AsyncMock(),
    ):
        rejected = await reject_candidate(session, WORKSPACE_ID, USER_ID, candidate.id)

    assert rejected.lifecycle_status == "rejected"
    assert rejected.resolved_at is not None
    assert rejected.evidence["review_actions"][-1]["action"] == "reject"

    candidate = _candidate()
    session.execute = AsyncMock(return_value=_result([candidate]))
    with patch(
        "src.services.missed_decision_actions.snooze_suggestion",
        new=AsyncMock(),
    ):
        deferred = await defer_candidate(
            session,
            WORKSPACE_ID,
            USER_ID,
            candidate.id,
            snoozed_until=datetime.now(UTC) + timedelta(days=3),
        )

    assert deferred.lifecycle_status == "deferred"
    assert deferred.evidence["review_actions"][-1]["action"] == "defer"


@pytest.mark.asyncio
async def test_terminal_candidates_cannot_be_confirmed_again() -> None:
    candidate = _candidate(lifecycle_status="confirmed")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))

    with pytest.raises(InvalidCandidateTransitionError):
        await confirm_candidate(session, WORKSPACE_ID, USER_ID, candidate.id)


@pytest.mark.asyncio
async def test_confirmed_decision_preserves_action_hint_grounding_metadata() -> None:
    candidate = _candidate()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))
    session.flush = AsyncMock()

    with (
        patch(
            "src.services.missed_decision_actions.upsert_node",
            new=AsyncMock(return_value=uuid4()),
        ) as upsert_node,
        patch(
            "src.services.missed_decision_actions.upsert_edge",
            new=AsyncMock(),
        ) as upsert_edge,
        patch(
            "src.services.missed_decision_actions.resolve_suggestion",
            new=AsyncMock(),
        ),
    ):
        await confirm_candidate(session, WORKSPACE_ID, USER_ID, candidate.id)

    props = upsert_node.await_args.kwargs["properties"]
    assert props["source_quote"] == candidate.source_quote
    assert props["source_link"] == candidate.source_link
    assert props["candidate_id"] == str(candidate.id)
    assert props["grounding_explanation"]["no_write_boundary"] == (
        "phase_46_metadata_only"
    )
    assert props["action_hints"] == candidate.action_hints
    assert props["action_hint_grounding"][0]["grounding_state"] == "source_backed"
    assert props["action_hint_grounding"][0]["source_type"] == candidate.source_type
    assert props["action_hint_grounding"][0]["source_id"] == str(candidate.source_id)
    assert props["action_hint_grounding"][0]["no_write_boundary"] == (
        "phase_46_metadata_only"
    )
    assert upsert_edge.await_args.kwargs["relationship_type"] == "evidenced_by"


@pytest.mark.asyncio
async def test_confirm_succeeds_when_evidence_edge_write_fails() -> None:
    candidate = _candidate()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))
    session.flush = AsyncMock()

    class Savepoint:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    session.begin_nested = MagicMock(return_value=Savepoint())

    decision_node_id = uuid4()
    with (
        patch(
            "src.services.missed_decision_actions.upsert_node",
            new=AsyncMock(return_value=decision_node_id),
        ),
        patch(
            "src.services.missed_decision_actions.upsert_edge",
            new=AsyncMock(side_effect=RuntimeError("edge type unavailable")),
        ),
        patch(
            "src.services.missed_decision_actions.resolve_suggestion",
            new=AsyncMock(),
        ),
    ):
        result = await confirm_candidate(session, WORKSPACE_ID, USER_ID, candidate.id)

    assert result.decision_node_id == decision_node_id
    assert candidate.lifecycle_status == "confirmed"


@pytest.mark.asyncio
async def test_auto_confirm_candidate_records_system_action_and_audit() -> None:
    candidate = _candidate(
        suggestion_id=None,
        lifecycle_status="detected",
        confidence="very_high",
    )
    decision_node_id = uuid4()
    session = AsyncMock()
    session.flush = AsyncMock()

    with (
        patch(
            "src.services.missed_decision_actions.upsert_node",
            new=AsyncMock(return_value=decision_node_id),
        ) as upsert_node,
        patch(
            "src.services.missed_decision_actions.upsert_edge",
            new=AsyncMock(return_value=uuid4()),
        ),
        patch(
            "src.services.missed_decision_actions.log_audit_event",
            new=AsyncMock(),
        ) as audit,
        patch(
            "src.services.missed_decision_actions.resolve_suggestion",
            new=AsyncMock(),
        ) as resolve,
    ):
        result = await auto_confirm_candidate(session, candidate)

    assert result.decision_node_id == decision_node_id
    assert candidate.lifecycle_status == "confirmed"
    assert candidate.resolved_at is not None
    assert candidate.matched_entity_type == "graph_node"
    assert candidate.matched_entity_id == decision_node_id
    action = candidate.evidence["review_actions"][-1]
    assert action["action"] == "auto_confirm"
    assert action["actor_type"] == "system"
    assert "actor_user_id" not in action
    assert action["autosave_policy_version"] == "conservative_v1"
    props = upsert_node.await_args.kwargs["properties"]
    assert props["autosave_policy_version"] == "conservative_v1"
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["user_id"] is None
    assert audit.await_args.kwargs["details"]["autosave_policy_version"] == (
        "conservative_v1"
    )
    resolve.assert_not_awaited()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_confirm_candidate_uses_source_metadata_for_attribution() -> None:
    candidate = _candidate(
        suggestion_id=None,
        lifecycle_status="detected",
        confidence="very_high",
        people=[],
        evidence={
            "source_metadata": {
                "from_first_name": "Daulet",
                "from_username": "dxulet",
                "chat_title": "contextOS team",
            }
        },
    )
    session = AsyncMock()
    session.flush = AsyncMock()

    with (
        patch(
            "src.services.missed_decision_actions.upsert_node",
            new=AsyncMock(return_value=uuid4()),
        ) as upsert_node,
        patch(
            "src.services.missed_decision_actions.upsert_edge",
            new=AsyncMock(return_value=uuid4()),
        ),
        patch(
            "src.services.missed_decision_actions.log_audit_event",
            new=AsyncMock(),
        ),
    ):
        await auto_confirm_candidate(session, candidate)

    props = upsert_node.await_args.kwargs["properties"]
    assert props["author_name"] == "Daulet"
    assert props["person_name"] == "Daulet"
    assert props["participants"] == ["Daulet"]
    assert props["source_context"] == "contextOS team"


def test_graph_edge_migration_allows_missed_decision_evidence_relationships() -> None:
    initial_schema = Path("../supabase/migrations/00027_graph_tables.sql").read_text()
    patch_schema = Path(
        "../supabase/migrations/00044_graph_edge_missed_decision_evidence_relationships.sql"
    ).read_text()

    for relationship_type in ("has_evidence", "evidenced_by"):
        assert f"'{relationship_type}'" in initial_schema
        assert f"'{relationship_type}'" in patch_schema


def test_audit_log_user_id_does_not_reference_unmapped_users_table() -> None:
    assert not AuditLog.__table__.c.user_id.foreign_keys


def test_audit_log_ip_address_uses_postgres_inet_type() -> None:
    assert AuditLog.__table__.c.ip_address.type.__class__.__name__ == "INET"


@pytest.mark.asyncio
async def test_ignore_duplicate_suppresses_and_resolves_suggestion() -> None:
    candidate = _candidate(match_status="strong_match")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))
    session.flush = AsyncMock()

    with patch(
        "src.services.missed_decision_actions.resolve_suggestion",
        new=AsyncMock(),
    ) as resolve:
        ignored = await ignore_duplicate_candidate(
            session,
            WORKSPACE_ID,
            USER_ID,
            candidate.id,
        )

    assert ignored.lifecycle_status == "suppressed"
    assert ignored.suppression_reason == "duplicate_no_new_evidence"
    resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_review_candidates_returns_open_workspace_candidates() -> None:
    candidate = _candidate(confidence="very_high")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))

    rows = await list_review_candidates(session, WORKSPACE_ID, limit=5)

    assert rows == [candidate]


def _client(session: AsyncMock, user: UserContext | None = None) -> TestClient:
    from src.routers.missed_decisions import router

    app = FastAPI()
    app.include_router(router)

    async def _session_override():
        yield session

    async def _user_override():
        if user is None:
            return UserContext(
                user_id=USER_ID,
                email=TEST_EMAIL,
                workspace_id=WORKSPACE_ID,
            )
        return user

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override
    return TestClient(app)


def test_review_endpoint_returns_candidate_payload() -> None:
    candidate = _candidate()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))

    response = _client(session).get("/api/missed-decisions/review")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(candidate.id)
    assert body[0]["source_quote"] == candidate.source_quote
    assert "confirm" in body[0]["legal_actions"]


def test_scans_endpoint_returns_latest_workspace_scan_per_source() -> None:
    now = datetime.now(UTC)
    latest_slack = _scan_run(
        id=uuid4(),
        source_type="slack_message",
        sources_scanned=4,
        sources_total=10,
        candidates_created=2,
        created_at=datetime(2026, 5, 25, 9, 5, tzinfo=UTC),
    )
    older_slack = _scan_run(
        id=uuid4(),
        source_type="slack_message",
        sources_scanned=10,
        sources_total=10,
        candidates_created=0,
        created_at=datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
    )
    failed_notion = _scan_run(
        id=uuid4(),
        source_type="notion_page",
        status="failed",
        sources_scanned=1,
        sources_total=None,
        candidates_created=0,
        error_message="Extractor paused after provider timeout",
        completed_at=now,
        created_at=datetime(2026, 5, 25, 8, 0, tzinfo=UTC),
    )
    stale_failed_telegram = _scan_run(
        id=uuid4(),
        source_type="telegram_message",
        status="failed",
        completed_at=now - timedelta(minutes=20),
        created_at=datetime(2026, 5, 25, 8, 0, tzinfo=UTC),
    )
    other_workspace = _scan_run(workspace_id=uuid4(), source_type="telegram_message")
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_result([
            latest_slack,
            older_slack,
            failed_notion,
            stale_failed_telegram,
            other_workspace,
        ])
    )

    response = _client(session).get("/api/missed-decisions/scans")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [
        str(latest_slack.id),
        str(failed_notion.id),
    ]
    assert body[0] == {
        "id": str(latest_slack.id),
        "source_type": "slack_message",
        "status": "running",
        "sources_scanned": 4,
        "sources_total": 10,
        "progress_percent": 40,
        "candidates_created": 2,
        "started_at": "2026-05-25T09:00:00Z",
        "completed_at": None,
        "error_message": None,
    }
    assert body[1]["status"] == "failed"
    assert body[1]["progress_percent"] is None
    assert body[1]["error_message"] == "Extractor paused after provider timeout"


def test_confirm_endpoint_returns_decision_node_id() -> None:
    candidate = _candidate()
    decision_node_id = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result([candidate]))
    session.commit = AsyncMock()

    with patch(
        "src.services.missed_decision_actions.upsert_node",
        new=AsyncMock(return_value=decision_node_id),
    ), patch(
        "src.services.missed_decision_actions.upsert_edge",
        new=AsyncMock(return_value=uuid4()),
    ), patch(
        "src.services.missed_decision_actions.resolve_suggestion",
        new=AsyncMock(),
    ):
        response = _client(session).post(
            f"/api/missed-decisions/{candidate.id}/confirm"
        )

    assert response.status_code == 200
    assert response.json()["decision_node_id"] == str(decision_node_id)
    assert candidate.lifecycle_status == "confirmed"


def test_unauthenticated_review_requires_auth() -> None:
    from src.routers.missed_decisions import router

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/missed-decisions/review")

    assert response.status_code in (401, 403)
