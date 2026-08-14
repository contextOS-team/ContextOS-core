"""Tests for the Coverage Audit aggregation and endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.coverage_report import compute_coverage

WS = uuid.uuid4()


def _scalar_result(value: int) -> MagicMock:
    r = MagicMock()
    r.scalar.return_value = value
    return r


def _rows_result(rows: list) -> MagicMock:
    r = MagicMock()
    r.fetchall.return_value = rows
    return r


@pytest.mark.asyncio
async def test_compute_coverage_assembles_headline_and_uncertain_math():
    session = MagicMock()
    # order: reconstructed, drifted, aligned, drifts_total, confirmed,
    # resolved, actioned, breakdown
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(27),  # reconstructed
            _scalar_result(2),   # drifted
            _scalar_result(21),  # aligned
            _scalar_result(3),   # drifts_total
            _scalar_result(2),   # confirmed
            _scalar_result(1),   # resolved
            _scalar_result(1),   # actioned
            _rows_result([("jira_updated", 1)]),  # breakdown
        ]
    )
    report = await compute_coverage(session, WS, window_days=30)

    assert report["window_days"] == 30
    d = report["decisions"]
    assert d["reconstructed"] == 27
    assert d["aligned"] == 21
    assert d["drifted"] == 2
    assert d["uncertain"] == 4  # 27 - 21 - 2
    dr = report["drifts"]
    assert dr["total"] == 3
    assert dr["resolved"] == 1
    assert dr["actioned"] == 1
    assert dr["resolution_breakdown"] == {"jira_updated": 1}


@pytest.mark.asyncio
async def test_uncertain_never_negative():
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(5),   # reconstructed
            _scalar_result(4),   # drifted
            _scalar_result(4),   # aligned  (4+4 > 5)
            _scalar_result(0),
            _scalar_result(0),
            _scalar_result(0),
            _scalar_result(0),
            _rows_result([]),
        ]
    )
    report = await compute_coverage(session, WS, window_days=90)
    assert report["decisions"]["uncertain"] == 0


def test_coverage_endpoint_returns_report():
    from src.routers.reports import router

    app = FastAPI()
    app.include_router(router)

    async def _session_override():
        yield MagicMock()

    async def _user_override():
        return UserContext(user_id=uuid.uuid4(), email="t@x.com", workspace_id=WS)

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override

    fake = {"window_days": 60, "decisions": {"reconstructed": 3}, "drifts": {}}
    with patch(
        "src.routers.reports.compute_coverage", AsyncMock(return_value=fake)
    ):
        resp = TestClient(app).get("/api/reports/coverage?window_days=60")
    assert resp.status_code == 200
    assert resp.json()["window_days"] == 60


def test_coverage_endpoint_validates_window():
    from src.routers.reports import router

    app = FastAPI()
    app.include_router(router)

    async def _session_override():
        yield MagicMock()

    async def _user_override():
        return UserContext(user_id=uuid.uuid4(), email="t@x.com", workspace_id=WS)

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = _user_override
    resp = TestClient(app).get("/api/reports/coverage?window_days=999")
    assert resp.status_code == 422
