"""Tests for the health check endpoints.

/api/health is a pure liveness probe (process is up, no external
dependencies) and intentionally returns only {"status": "ok"} — the DB /
Vault / external-API checks moved to the deep readiness probe at
/api/health/ready.
"""

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    """GET /api/health should return 200 OK with a minimal liveness body."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    # Liveness must NOT touch the DB — it is dependency-free by design, so
    # there is deliberately no "db" key here (that lives on /ready).
    assert "db" not in data


def test_health_no_auth_required(client: TestClient) -> None:
    """GET /api/health should work without any Authorization header."""
    response = client.get("/api/health", headers={})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready_reports_dependency_checks(client: TestClient) -> None:
    """GET /api/health/ready should return per-dependency check results.

    With the mocked session the DB check won't be "ok", but the deep
    probe must still respond and surface an overall status plus the
    individual dependency checks.
    """
    response = client.get("/api/health/ready")
    # The endpoint always responds 200 and carries health in the body
    # (status: "healthy" | "unhealthy") so probes read the JSON, not just
    # the HTTP code.
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "unhealthy")
    assert "database" in data["checks"]
