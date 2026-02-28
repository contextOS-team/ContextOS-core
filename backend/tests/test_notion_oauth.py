"""Tests for Notion OAuth endpoints.

Covers:
- GET /api/notion/connect returns authorization URL
- GET /api/notion/callback success + invalid state
- POST /api/notion/disconnect
- GET /api/notion/status (connected + disconnected)
"""

import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings, get_settings
from tests.conftest import (
    TEST_EMAIL,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    _make_test_settings,
)

# Test Notion OAuth config values
NOTION_CLIENT_ID = "test-notion-client-id"
NOTION_CLIENT_SECRET = "test-notion-client-secret"


@pytest.fixture()
def notion_settings() -> Settings:
    """Create test settings with Notion OAuth config."""
    return _make_test_settings(
        NOTION_CLIENT_ID=NOTION_CLIENT_ID,
        NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
    )


@pytest.fixture()
def notion_app(notion_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with Notion settings and mocked session."""
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
    """Provide a TestClient for the app with Notion config."""
    with TestClient(notion_app) as c:
        yield c


def _make_auth_header() -> dict[str, str]:
    """Create a valid auth header for tests."""
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


# ---------- /api/notion/connect ----------


class TestConnect:
    """Tests for GET /api/notion/connect."""

    def test_connect_returns_authorization_url(
        self, notion_client, mock_session, notion_settings
    ):
        """GET /api/notion/connect returns 200 with authorization_url containing client_id."""
        # Mock the workspace membership lookup that get_current_user does
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
        mock_session.execute.return_value = mock_result

        response = notion_client.get(
            "/api/notion/connect", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        url = data["authorization_url"]
        assert "api.notion.com" in url
        assert f"client_id={NOTION_CLIENT_ID}" in url
        assert "state=" in url


# ---------- /api/notion/callback ----------


class TestCallback:
    """Tests for GET /api/notion/callback."""

    def test_callback_success(self, notion_client, mock_session, notion_settings):
        """GET /api/notion/callback with valid state exchanges code and redirects."""
        workspace_id = UUID(TEST_WORKSPACE_ID)
        user_id = UUID(TEST_USER_ID)

        with (
            patch(
                "src.routers.notion.verify_state_or_raise",
                return_value=workspace_id,
            ),
            patch(
                "src.routers.notion.exchange_code",
                new_callable=AsyncMock,
                return_value={
                    "workspace_id": "ws-123",
                    "workspace_name": "Test Workspace",
                },
            ),
        ):
            # Mock WorkspaceMember query to return user_id
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = user_id
            mock_session.execute.return_value = mock_result

            response = notion_client.get(
                "/api/notion/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "notion=connected" in location

    def test_callback_invalid_state(self, notion_client, mock_session, notion_settings):
        """GET /api/notion/callback with invalid state redirects with error."""
        from src.services.notion_oauth import NotionOAuthError

        with patch(
            "src.routers.notion.verify_state_or_raise",
            side_effect=NotionOAuthError("Invalid state"),
        ):
            response = notion_client.get(
                "/api/notion/callback?code=test_code&state=bad_state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "notion=error" in location
        assert "reason=invalid_state" in location


# ---------- /api/notion/disconnect ----------


class TestDisconnect:
    """Tests for POST /api/notion/disconnect."""

    def test_disconnect_success(self, notion_client, mock_session, notion_settings):
        """POST /api/notion/disconnect returns disconnected status."""
        # Mock workspace membership lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
        mock_session.execute.return_value = mock_result

        with patch(
            "src.routers.notion.disconnect",
            new_callable=AsyncMock,
        ):
            response = notion_client.post(
                "/api/notion/disconnect", headers=_make_auth_header()
            )

        assert response.status_code == 200
        assert response.json() == {"status": "disconnected"}


# ---------- /api/notion/status ----------


class TestStatus:
    """Tests for GET /api/notion/status."""

    def test_status_disconnected(self, notion_client, mock_session, notion_settings):
        """GET /api/notion/status returns disconnected when no integration exists."""
        # First call: workspace membership lookup
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Second call: WorkspaceIntegration query returns None
        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = None

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            return mock_integration_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        response = notion_client.get(
            "/api/notion/status", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["status"] == "disconnected"

    def test_status_connected(self, notion_client, mock_session, notion_settings):
        """GET /api/notion/status returns connected with workspace info."""
        # First call: workspace membership lookup
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Second call: WorkspaceIntegration query
        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.config = {"external_name": "Test Workspace"}

        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = mock_integration

        # Third call: page count
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 5

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            elif call_count == 2:
                return mock_integration_result
            return mock_count_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        response = notion_client.get(
            "/api/notion/status", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["workspace_name"] == "Test Workspace"
        assert data["pages_count"] == 5
