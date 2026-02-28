"""Tests for Notion pages endpoint and datetime parsing.

Covers:
- _parse_notion_datetime: actual Notion API formats, None, edge cases
- GET /api/notion/pages: paginated response, empty state, auth, query params
"""

import time
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings
from src.routers.notion import _parse_notion_datetime
from tests.conftest import (
    TEST_EMAIL,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    _make_test_settings,
)

NOTION_CLIENT_ID = "test-notion-client-id"
NOTION_CLIENT_SECRET = "test-notion-client-secret"


# ---------- _parse_notion_datetime ----------


class TestParseNotionDatetime:
    """Tests for the ISO 8601 datetime parser used during sync."""

    def test_standard_notion_format(self):
        """Notion returns '2025-06-03T05:29:00.000Z' — the actual format from the API."""
        result = _parse_notion_datetime("2025-06-03T05:29:00.000Z")
        assert result == datetime(2025, 6, 3, 5, 29, 0)
        assert result.tzinfo is None

    def test_no_fractional_seconds(self):
        """Some Notion timestamps omit fractional seconds."""
        result = _parse_notion_datetime("2025-06-03T05:29:00Z")
        assert result == datetime(2025, 6, 3, 5, 29, 0)

    def test_none_returns_none(self):
        result = _parse_notion_datetime(None)
        assert result is None

    def test_empty_string_returns_none(self):
        result = _parse_notion_datetime("")
        assert result is None

    def test_result_is_naive_utc(self):
        """Ensure timezone info is stripped (DB column is TIMESTAMP WITHOUT TIME ZONE)."""
        result = _parse_notion_datetime("2026-01-15T12:00:00.000Z")
        assert result is not None
        assert result.tzinfo is None


# ---------- Fixtures for /api/notion/pages ----------


@pytest.fixture()
def notion_settings() -> Settings:
    return _make_test_settings(
        NOTION_CLIENT_ID=NOTION_CLIENT_ID,
        NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
    )


@pytest.fixture()
def notion_app(notion_settings: Settings, mock_session: AsyncMock):
    src.config._settings = notion_settings

    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def notion_client(notion_app) -> Generator[TestClient, None, None]:
    with TestClient(notion_app) as c:
        yield c


def _make_auth_header() -> dict[str, str]:
    import jwt as pyjwt

    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
        "iss": "http://localhost:54321/auth/v1",
    }
    token = pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _make_mock_page_row(
    title: str = "Test Page",
    page_type: str = "page",
    url: str = "https://notion.so/test",
) -> MagicMock:
    """Create a mock row matching the SELECT columns in list_pages."""
    row = MagicMock()
    row.id = uuid.uuid4()
    row.notion_id = f"notion-{uuid.uuid4().hex[:8]}"
    row.title = title
    row.page_type = page_type
    row.url = url
    return row


def _mock_paginated_session(mock_session, total: int, rows: list):
    """Set up mock_session.execute to return (workspace, count, rows) in order.

    The endpoint makes 3 DB calls:
    1. get_current_user workspace lookup -> scalar_one_or_none
    2. COUNT(*) query -> scalar_one
    3. SELECT ... LIMIT/OFFSET -> .all()
    """
    mock_workspace_result = MagicMock()
    mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = total

    mock_rows_result = MagicMock()
    mock_rows_result.all.return_value = rows

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_workspace_result
        if call_count == 2:
            return mock_count_result
        return mock_rows_result

    mock_session.execute = AsyncMock(side_effect=side_effect)


# ---------- GET /api/notion/pages ----------


class TestListPages:
    """Tests for GET /api/notion/pages."""

    def test_returns_paginated_pages(self, notion_client, mock_session):
        """Endpoint returns page list with pagination metadata."""
        page1 = _make_mock_page_row(title="Design Doc", page_type="page")
        page2 = _make_mock_page_row(title="Sprint DB", page_type="database_entry")
        _mock_paginated_session(mock_session, total=2, rows=[page1, page2])

        response = notion_client.get(
            "/api/notion/pages", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()

        # Pagination metadata
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 10

        # Page items
        assert len(data["pages"]) == 2
        expected_keys = {"id", "notion_id", "title", "page_type", "url"}
        for page in data["pages"]:
            assert set(page.keys()) == expected_keys

        assert data["pages"][0]["title"] == "Design Doc"
        assert data["pages"][1]["page_type"] == "database_entry"

    def test_returns_empty_list_when_no_pages(self, notion_client, mock_session):
        """Endpoint returns empty pages list with total=0."""
        _mock_paginated_session(mock_session, total=0, rows=[])

        response = notion_client.get(
            "/api/notion/pages", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pages"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_custom_page_and_size(self, notion_client, mock_session):
        """Endpoint respects page and page_size query params."""
        page1 = _make_mock_page_row(title="Page on second page")
        _mock_paginated_session(mock_session, total=25, rows=[page1])

        response = notion_client.get(
            "/api/notion/pages?page=2&page_size=10",
            headers=_make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total"] == 25

    def test_page_size_capped_at_max(self, notion_client, mock_session):
        """Endpoint rejects page_size above the maximum (100)."""
        _mock_paginated_session(mock_session, total=0, rows=[])

        response = notion_client.get(
            "/api/notion/pages?page_size=500",
            headers=_make_auth_header(),
        )
        assert response.status_code == 422

    def test_page_clamped_to_last_valid(self, notion_client, mock_session):
        """Requesting page beyond total clamps to the last valid page."""
        page1 = _make_mock_page_row(title="Only Page")
        _mock_paginated_session(mock_session, total=1, rows=[page1])

        response = notion_client.get(
            "/api/notion/pages?page=9999",
            headers=_make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["total"] == 1

    def test_unauthenticated_returns_401(self, notion_client):
        """Endpoint rejects requests without a valid auth token."""
        response = notion_client.get("/api/notion/pages")
        assert response.status_code in (401, 403)
