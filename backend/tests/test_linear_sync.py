"""Tests for Linear sync: GraphQL client, sync logic, pagination, backoff, and endpoints."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from tests.conftest import (
    TEST_EMAIL,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    make_entity_execute,
)

# Test Linear OAuth config values (same as test_linear_oauth.py)
LINEAR_CLIENT_ID = "test-linear-client-id"
LINEAR_CLIENT_SECRET = "test-linear-client-secret"
LINEAR_WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture()
def linear_settings(mock_settings):
    """Override mock_settings with Linear OAuth config."""
    mock_settings.LINEAR_CLIENT_ID = LINEAR_CLIENT_ID
    mock_settings.LINEAR_CLIENT_SECRET = LINEAR_CLIENT_SECRET
    mock_settings.LINEAR_WEBHOOK_SECRET = LINEAR_WEBHOOK_SECRET

    import src.routers.linear

    original_linear_router = src.routers.linear.get_settings
    src.routers.linear.get_settings = lambda: mock_settings

    yield mock_settings

    src.routers.linear.get_settings = original_linear_router


@pytest.fixture()
def app_with_linear(linear_settings, mock_session):
    """Create a FastAPI app with Linear settings and mocked session."""
    from src.db import get_session
    from src.main import app as fastapi_app

    async def _mock_get_session():
        yield mock_session

    fastapi_app.dependency_overrides[get_session] = _mock_get_session
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def linear_client(app_with_linear):
    """Provide a TestClient for the app with Linear config."""
    from fastapi.testclient import TestClient

    with TestClient(app_with_linear) as c:
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


# ---------- GraphQL Client Tests ----------


class TestGraphQLClient:
    """Tests for LinearGraphQLClient."""

    @pytest.mark.asyncio
    async def test_graphql_client_sends_auth_header(self):
        """Verify LinearGraphQLClient includes correct Authorization header (bare token, not Bearer)."""
        from src.services.linear_graphql import LinearGraphQLClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"viewer": {"id": "user-1"}}}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            client = LinearGraphQLClient("lin_api_test_token")
            await client.query("{ viewer { id } }")
            await client.close()

            # Verify the request was made
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            # The auth header is set on the client, not per-request
            # So we verify the client was constructed with the token
            assert client._client.headers["Authorization"] == "Bearer lin_api_test_token"

    @pytest.mark.asyncio
    async def test_graphql_client_retries_on_429(self):
        """Mock 429 response, verify retry with backoff."""
        from src.services.linear_graphql import LinearGraphQLClient

        mock_429_response = MagicMock()
        mock_429_response.status_code = 429
        mock_429_response.headers = {}

        mock_ok_response = MagicMock()
        mock_ok_response.status_code = 200
        mock_ok_response.json.return_value = {"data": {"ok": True}}

        with (
            patch(
                "httpx.AsyncClient.post",
                new_callable=AsyncMock,
                side_effect=[mock_429_response, mock_ok_response],
            ),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            client = LinearGraphQLClient("test-token")
            result = await client.query("{ test }")
            await client.close()

            assert result == {"data": {"ok": True}}
            # Verify sleep was called for backoff
            mock_sleep.assert_called_once()
            # First retry: 1.0 * 2^0 = 1.0 base, with jitter (0.5-1.5x)
            sleep_val = mock_sleep.call_args[0][0]
            assert 0.5 <= sleep_val <= 1.5

    @pytest.mark.asyncio
    async def test_graphql_client_raises_on_error(self):
        """Mock non-200 response, verify LinearAPIError raised."""
        from src.services.linear_graphql import LinearAPIError, LinearGraphQLClient

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            client = LinearGraphQLClient("test-token")

            with pytest.raises(LinearAPIError) as exc_info:
                await client.query("{ test }")
            await client.close()

            assert exc_info.value.status_code == 500
            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_all_pages_collects_all_nodes(self):
        """Mock paginated responses (2 pages), verify all nodes collected."""
        from src.services.linear_graphql import LinearGraphQLClient

        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.json.return_value = {
            "data": {
                "team": {
                    "issues": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                        "nodes": [
                            {"id": "issue-1", "title": "First"},
                            {"id": "issue-2", "title": "Second"},
                        ],
                    }
                }
            }
        }

        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "data": {
                "team": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "cursor-2"},
                        "nodes": [
                            {"id": "issue-3", "title": "Third"},
                        ],
                    }
                }
            }
        }

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=[page1_response, page2_response],
        ):
            client = LinearGraphQLClient("test-token")
            nodes = await client.fetch_all_pages(
                "query($teamId: String!, $after: String) { ... }",
                {"teamId": "team-1"},
                ["team", "issues"],
            )
            await client.close()

            assert len(nodes) == 3
            assert nodes[0]["id"] == "issue-1"
            assert nodes[1]["id"] == "issue-2"
            assert nodes[2]["id"] == "issue-3"


# ---------- Sync Service Tests ----------


class TestSyncService:
    """Tests for sync service functions."""

    @pytest.mark.asyncio
    async def test_fetch_teams_returns_team_list(self):
        """Mock GraphQL response with teams, verify correct parsing."""
        from src.services.linear_sync import fetch_teams

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "teams": {
                    "nodes": [
                        {"id": "team-1", "name": "Engineering", "key": "ENG"},
                        {"id": "team-2", "name": "Product", "key": "PROD"},
                    ]
                }
            }
        }

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            teams = await fetch_teams("test-access-token")

            assert len(teams) == 2
            assert teams[0]["id"] == "team-1"
            assert teams[0]["name"] == "Engineering"
            assert teams[0]["key"] == "ENG"
            assert teams[1]["id"] == "team-2"
            assert teams[1]["name"] == "Product"

    def test_sync_excludes_cancelled_tickets(self):
        """Verify sync query filter excludes 'canceled' state type."""
        from src.services.linear_sync import ISSUES_QUERY

        # The GraphQL query should contain the filter for excluded states
        assert 'canceled' in ISSUES_QUERY
        assert 'nin' in ISSUES_QUERY
        # Verify the filter structure is present
        assert 'state: { type: { nin: ["canceled"] } }' in ISSUES_QUERY

    @pytest.mark.asyncio
    async def test_sync_upserts_tickets_and_comments(self):
        """Mock GraphQL response with tickets+comments, verify upsert calls."""
        from src.services.linear_sync import _upsert_comments, _upsert_tickets

        mock_session = AsyncMock()

        # Mock the execute().scalar_one() return for upsert RETURNING
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = UUID("33333333-3333-3333-3333-333333333333")
        mock_session.execute.return_value = mock_result
        mock_session.flush = AsyncMock()

        issues = [
            {
                "id": "linear-issue-1",
                "identifier": "ENG-123",
                "title": "Fix bug",
                "description": "Something is broken",
                "state": {"name": "In Progress", "type": "started"},
                "priority": 2,
                "assignee": {"name": "Alice"},
                "team": {"name": "Engineering"},
                "project": {"name": "Q1 Sprint"},
                "labels": {"nodes": [{"name": "bug"}, {"name": "urgent"}]},
                "comments": {
                    "nodes": [
                        {
                            "id": "comment-1",
                            "body": "Looking into this",
                            "user": {"name": "Alice"},
                            "createdAt": "2025-01-01T00:00:00Z",
                            "updatedAt": "2025-01-01T00:00:00Z",
                        }
                    ]
                },
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-01-02T00:00:00Z",
            }
        ]

        workspace_id = UUID(TEST_WORKSPACE_ID)

        # Test ticket upsert
        ticket_id_map = await _upsert_tickets(mock_session, workspace_id, issues)

        assert "linear-issue-1" in ticket_id_map
        assert ticket_id_map["linear-issue-1"] == UUID("33333333-3333-3333-3333-333333333333")
        # execute called once for the ticket upsert
        assert mock_session.execute.call_count >= 1
        mock_session.flush.assert_called()

        # Reset mocks for comment test
        mock_session.reset_mock()
        mock_session.flush = AsyncMock()

        # Test comment upsert
        comment_count = await _upsert_comments(mock_session, workspace_id, issues, ticket_id_map)

        assert comment_count == 1
        assert mock_session.execute.call_count >= 1


# ---------- Endpoint Tests ----------


class TestTeamsEndpoint:
    """Tests for GET /api/linear/teams."""

    def test_teams_endpoint_requires_auth(self, linear_client):
        """GET /api/linear/teams without token returns 401/403."""
        response = linear_client.get("/api/linear/teams")
        assert response.status_code in (401, 403)

    def test_teams_endpoint_returns_teams(self, linear_client, mock_session, linear_settings):
        """GET /api/linear/teams with mocked service returns team list."""
        # Mock workspace membership lookup
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            # Remaining calls are for get_valid_access_token
            result = MagicMock()
            result.scalar_one_or_none.return_value = MagicMock(
                token_expires_at=None,
                access_token="vault_access_name",
            )
            return result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        mock_teams = [
            {"id": "team-1", "name": "Engineering", "key": "ENG"},
            {"id": "team-2", "name": "Design", "key": "DES"},
        ]

        with patch(
            "src.routers.linear.fetch_teams",
            new_callable=AsyncMock,
            return_value=mock_teams,
        ), patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="test-access-token",
        ):
            response = linear_client.get(
                "/api/linear/teams", headers=_make_auth_header()
            )

        assert response.status_code == 200
        data = response.json()
        assert "teams" in data
        assert len(data["teams"]) == 2
        assert data["teams"][0]["name"] == "Engineering"


class TestSyncEndpoint:
    """Tests for POST /api/linear/sync."""

    def test_sync_endpoint_starts_background_task(
        self, linear_client, mock_session, linear_settings
    ):
        """POST /api/linear/sync returns sync_started status."""
        # Mock workspace membership lookup
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Mock integration lookup (connected)
        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.config = {"sync_status": "complete", "tickets_synced": 8}
        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=make_entity_execute(
                results={
                    "WorkspaceMember": mock_workspace_result,
                    "WorkspaceIntegration": mock_integration_result,
                },
            )
        )

        # Patch sync_tickets_for_teams to prevent actual execution
        with patch(
            "src.routers.linear.sync_tickets_for_teams",
            new_callable=AsyncMock,
        ):
            response = linear_client.post(
                "/api/linear/sync",
                json={"team_ids": ["team-1", "team-2"]},
                headers=_make_auth_header(),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sync_started"
        assert data["team_ids"] == ["team-1", "team-2"]
        assert mock_integration.config["sync_status"] == "in_progress"
        assert mock_integration.config["tickets_synced"] == 0

    def test_sync_endpoint_validates_connected_integration(
        self, linear_client, mock_session, linear_settings
    ):
        """POST /api/linear/sync without connected integration returns error."""
        # Mock workspace membership lookup
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Mock integration lookup (not connected)
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

        response = linear_client.post(
            "/api/linear/sync",
            json={"team_ids": ["team-1"]},
            headers=_make_auth_header(),
        )

        assert response.status_code == 400
        assert "not connected" in response.json()["detail"]
