"""Tests for missed-decision review lifecycle actions and endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.missed_decision import MissedDecisionCandidate
from src.services.missed_decision_actions import (
    CandidateNotFoundError,
    InvalidCandidateTransitionError,
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
        "source_link": "/dashboard/source-reference?source_type=slack_message&source_id=abc&workspace_id=def&source_timestamp=2026-05-25T09:00:00Z",
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
