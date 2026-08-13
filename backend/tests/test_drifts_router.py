"""Tests for the drift review lifecycle endpoints."""

import uuid
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.decision_drift import Drift

WS = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _drift(**overrides) -> Drift:
    values = dict(
        id=uuid.uuid4(),
        workspace_id=WS,
        decision_id=uuid.uuid4(),
        summary="Auth tickets still target Q3",
        severity="high",
        verifier_verdict={"is_meaningful_drift": True},
    )
    values.update(overrides)
    return Drift(**values)


def _client(session) -> TestClient:
    from src.routers.drifts import router

    app = FastAPI()
    app.include_router(router)

    async def _session_override():
        yield session

    async def _user_override():
        return UserContext(user_id=USER, email="t@example.com", workspace_id=WS)

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override
    return TestClient(app)


def _session(drift: Drift | None) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=drift)
    session.commit = AsyncMock()
    return session


def test_confirm_sets_verdict_and_timestamp():
    drift = _drift()
    resp = _client(_session(drift)).post(
        f"/api/drifts/{drift.id}/confirm", json={}
    )
    assert resp.status_code == 200
    assert drift.confirmed_at is not None
    assert drift.feedback_verdict == "confirmed"
    assert resp.json()["lifecycle"] == "confirmed"


def test_dismiss_records_false_positive_and_closes():
    drift = _drift()
    resp = _client(_session(drift)).post(
        f"/api/drifts/{drift.id}/dismiss", json={"feedback_verdict": "false_positive"}
    )
    assert resp.status_code == 200
    assert drift.feedback_verdict == "false_positive"
    assert drift.resolved_at is not None


def test_resolve_requires_valid_resolution_type():
    drift = _drift()
    resp = _client(_session(drift)).post(
        f"/api/drifts/{drift.id}/resolve", json={"resolution_type": "nonsense"}
    )
    assert resp.status_code == 422


def test_resolve_sets_resolution_and_lifecycle():
    drift = _drift()
    resp = _client(_session(drift)).post(
        f"/api/drifts/{drift.id}/resolve", json={"resolution_type": "jira_updated"}
    )
    assert resp.status_code == 200
    assert drift.resolution_type == "jira_updated"
    assert drift.resolved_at is not None
    assert resp.json()["lifecycle"] == "resolved"


def test_verify_rejects_unresolved_drift():
    drift = _drift()  # not resolved
    resp = _client(_session(drift)).post(f"/api/drifts/{drift.id}/verify")
    assert resp.status_code == 409


def test_verify_marks_verified_when_resolved():
    from datetime import UTC, datetime

    drift = _drift(resolved_at=datetime.now(UTC), resolution_type="doc_updated")
    resp = _client(_session(drift)).post(f"/api/drifts/{drift.id}/verify")
    assert resp.status_code == 200
    assert drift.verified_at is not None
    assert resp.json()["lifecycle"] == "verified"


def test_drift_not_found_returns_404():
    resp = _client(_session(None)).post(f"/api/drifts/{uuid.uuid4()}/confirm", json={})
    assert resp.status_code == 404


def test_cross_workspace_drift_is_404():
    other = _drift(workspace_id=uuid.uuid4())
    resp = _client(_session(other)).post(f"/api/drifts/{other.id}/confirm", json={})
    assert resp.status_code == 404
