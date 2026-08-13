"""Tests for the agent-facing Decision Context API (v1)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_auth import MachinePrincipal, get_api_principal
from src.db import get_session
from src.models.decision import Decision

WS = uuid.uuid4()


def _decision(**over) -> Decision:
    values = dict(
        id=uuid.uuid4(),
        workspace_id=WS,
        statement="Use the GitLab group registry for @region packages",
        rationale="Central config",
        status="active",
        producer="missed_decision",
        consequentiality_score=0.92,
    )
    values.update(over)
    return Decision(**values)


def _client(session, principal: MachinePrincipal | None = None) -> TestClient:
    from src.routers.decision_context_api import router

    app = FastAPI()
    app.include_router(router)

    async def _session_override():
        yield session

    async def _principal_override():
        return principal or MachinePrincipal(
            workspace_id=WS, key_id=uuid.uuid4(), scopes=["decisions:read"]
        )

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_api_principal] = _principal_override
    return TestClient(app)


def _list_session(decisions: list[Decision]) -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = [(d, 3) for d in decisions]
    session.execute = AsyncMock(return_value=result)
    return session


def test_get_current_decisions_envelope_and_provenance():
    resp = _client(_list_session([_decision()])).get("/api/v1/decisions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == "1"
    d = body["data"]["decisions"][0]
    assert d["verification"] == "reviewed"  # missed_decision producer
    assert d["consequentiality_score"] == 0.92
    assert d["evidence_count"] == 3


def test_auto_saved_producer_marked_lower_trust():
    session = _list_session([_decision(producer="digest")])
    d = _client(session).get("/api/v1/decisions").json()["data"]["decisions"][0]
    assert d["verification"] == "auto_saved"


def test_tentative_status_marked_unreviewed():
    # tentative status overrides an otherwise-reviewed producer.
    session = _list_session(
        [_decision(status="tentative", producer="missed_decision")]
    )
    d = _client(session).get("/api/v1/decisions").json()["data"]["decisions"][0]
    assert d["verification"] == "unreviewed"


def test_get_decision_404_cross_workspace():
    other = _decision(workspace_id=uuid.uuid4())
    session = MagicMock()
    session.get = AsyncMock(return_value=other)
    resp = _client(session).get(f"/api/v1/decisions/{other.id}")
    assert resp.status_code == 404


def test_constraints_returns_relevant_active_decisions():
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_decision()]
    session.execute = AsyncMock(return_value=result)
    resp = _client(session).get("/api/v1/constraints", params={"action": "publish npm"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["action"] == "publish npm"
    assert len(body["data"]["constraints"]) == 1
