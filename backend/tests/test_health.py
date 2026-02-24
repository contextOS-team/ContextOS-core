"""Tests for the health check endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    """GET /api/health should return 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    # DB will be "disconnected" in tests since we use a mock session,
    # but the endpoint itself should still respond.
    assert "db" in data


def test_health_no_auth_required(client: TestClient) -> None:
    """GET /api/health should work without any Authorization header."""
    # Explicitly send no auth header
    response = client.get("/api/health", headers={})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
