"""Tests for context page API endpoints.

Covers:
- GET /api/context/{ticket_identifier} — retrieve context page
- POST /api/context/{ticket_identifier}/generate — trigger generation (202)
- GET /api/context/?q=... — semantic search
- 404 handling when context page not found
- Authentication required on all endpoints
"""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from tests.conftest import TEST_WORKSPACE_ID, TEST_USER_ID, TEST_EMAIL


@pytest.fixture()
def mock_context_page() -> MagicMock:
    """Create a mock ContextPage record."""
    from datetime import datetime, timezone

    page = MagicMock()
    page.id = uuid4()
    page.ticket_identifier = "CON-16"
    page.title = "Context: Implement context synthesis"
    page.content = "# Summary\n\nThis ticket is about building the context page pipeline."
    page.summary = "This ticket is about building the context page pipeline."
    page.status = "ready"
    page.sources = [{"type": "slack_message", "id": str(uuid4()), "title": "Slack msg", "relevance_score": 0.9}]
    page.generated_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    page.generation_model = "gemini-3-flash-preview"
    page.generation_tokens_used = 1500
    page.created_at = datetime(2026, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
    page.updated_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    return page


# ---------------------------------------------------------------------------
# GET /api/context/{ticket_identifier}
# ---------------------------------------------------------------------------


def test_get_context_page_success(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
    mock_context_page: MagicMock,
) -> None:
    """GET /api/context/CON-16 returns the context page."""
    # Mock: workspace membership lookup for auth
    mock_membership = MagicMock()
    mock_membership.scalar_one_or_none.return_value = TEST_WORKSPACE_ID

    # Mock: context page lookup
    mock_page_result = MagicMock()
    mock_page_result.scalar_one_or_none.return_value = mock_context_page

    mock_session.execute.side_effect = [
        mock_membership,
        mock_page_result,
    ]

    response = client.get("/api/context/CON-16", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["ticket_identifier"] == "CON-16"
    assert data["status"] == "ready"
    assert data["generation_model"] == "gemini-3-flash-preview"
    assert len(data["sources"]) == 1


def test_get_context_page_not_found(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/context/CON-99 returns 404 when no page exists."""
    mock_membership = MagicMock()
    mock_membership.scalar_one_or_none.return_value = TEST_WORKSPACE_ID

    mock_page_result = MagicMock()
    mock_page_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_membership,
        mock_page_result,
    ]

    response = client.get("/api/context/CON-99", headers=valid_auth_header)

    assert response.status_code == 404
    assert "CON-99" in response.json()["detail"]


def test_get_context_page_requires_auth(
    client: TestClient,
) -> None:
    """GET /api/context/CON-16 without auth returns 403."""
    response = client.get("/api/context/CON-16")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/context/{ticket_identifier}/generate
# ---------------------------------------------------------------------------


def test_trigger_generation_returns_202(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """POST /api/context/CON-16/generate returns 202 Accepted."""
    mock_membership = MagicMock()
    mock_membership.scalar_one_or_none.return_value = TEST_WORKSPACE_ID

    mock_session.execute.return_value = mock_membership

    with patch("src.routers.context._generate_in_background"):
        response = client.post(
            "/api/context/CON-16/generate", headers=valid_auth_header
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["ticket_identifier"] == "CON-16"


def test_trigger_generation_requires_auth(
    client: TestClient,
) -> None:
    """POST /api/context/CON-16/generate without auth returns 403."""
    response = client.post("/api/context/CON-16/generate")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/context/?q=...  (search)
# ---------------------------------------------------------------------------


def test_search_context_success(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/context/?q=auth returns search results."""
    mock_membership = MagicMock()
    mock_membership.scalar_one_or_none.return_value = TEST_WORKSPACE_ID

    # Mock match_embeddings results
    result_id = uuid4()
    source_id = uuid4()
    mock_search_result = MagicMock()
    mock_search_result.fetchall.return_value = [
        (result_id, "linear_ticket", source_id, 0.87, {}),
    ]

    mock_session.execute.side_effect = [
        mock_membership,
        mock_search_result,
    ]

    with patch(
        "src.services.embedding.generate_embedding",
        new_callable=AsyncMock,
        return_value=[0.1] * 768,
    ):
        response = client.get(
            "/api/context/?q=authentication", headers=valid_auth_header
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "authentication"
    assert data["count"] == 1
    assert data["results"][0]["source_type"] == "linear_ticket"


def test_search_requires_auth(
    client: TestClient,
) -> None:
    """GET /api/context/?q=test without auth returns 403."""
    response = client.get("/api/context/?q=test")
    assert response.status_code in (401, 403)


def test_search_requires_query(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/context/ without q parameter returns 422."""
    mock_membership = MagicMock()
    mock_membership.scalar_one_or_none.return_value = TEST_WORKSPACE_ID

    mock_session.execute.return_value = mock_membership

    response = client.get("/api/context/", headers=valid_auth_header)
    assert response.status_code == 422
