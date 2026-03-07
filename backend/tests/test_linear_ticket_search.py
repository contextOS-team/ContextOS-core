"""Tests for GET /api/linear/tickets/search endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_WORKSPACE_ID


@pytest.fixture(autouse=True)
def _patch_embedding():
    with patch(
        "src.services.embedding.queue_embedding_generation", new_callable=AsyncMock
    ):
        yield


def _mock_membership(mock_session: AsyncMock) -> None:
    """Set up mock_session to return a valid workspace membership."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
    mock_session.execute.return_value = mock_result


FAKE_NODES = [
    {
        "id": "abc-123",
        "identifier": "ENG-42",
        "title": "Implement notifications",
        "state": {"name": "In Progress", "type": "started"},
        "assignee": {"name": "Alice"},
        "team": {"key": "ENG", "name": "Engineering"},
        "priority": 2,
        "updatedAt": "2026-03-01T00:00:00Z",
    },
    {
        "id": "def-456",
        "identifier": "ENG-43",
        "title": "Fix login bug",
        "state": {"name": "Todo", "type": "unstarted"},
        "assignee": None,
        "team": {"key": "ENG", "name": "Engineering"},
        "priority": 1,
        "updatedAt": "2026-03-02T00:00:00Z",
    },
]


class TestSearchTicketsWithQuery:
    """Tests for search with a query string (issueSearch path)."""

    def test_returns_matching_tickets(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "issueSearch": {
                    "nodes": FAKE_NODES,
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search?q=notifications",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["has_next_page"] is False
        assert data["end_cursor"] is None
        assert data["tickets"][0]["identifier"] == "ENG-42"
        assert data["tickets"][0]["title"] == "Implement notifications"
        assert data["tickets"][0]["state"] == "In Progress"
        assert data["tickets"][0]["assignee"] == "Alice"
        # Verify search query was used (not assigned issues)
        call_args = mock_client.query.call_args
        assert "issueSearch" in call_args[0][0]

    def test_null_assignee_handled(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "issueSearch": {
                    "nodes": [FAKE_NODES[1]],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search?q=login",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        assert response.json()["tickets"][0]["assignee"] is None


class TestSearchTicketsNoQuery:
    """Tests for empty query (viewer.assignedIssues path)."""

    def test_returns_assigned_issues(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "viewer": {
                    "assignedIssues": {
                        "nodes": FAKE_NODES,
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-abc"},
                    }
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["has_next_page"] is True
        assert data["end_cursor"] == "cursor-abc"
        # Verify assigned issues query was used
        call_args = mock_client.query.call_args
        assert "assignedIssues" in call_args[0][0]

    def test_empty_result(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "viewer": {
                    "assignedIssues": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        assert response.json() == {
            "tickets": [],
            "count": 0,
            "has_next_page": False,
            "end_cursor": None,
        }


class TestSearchTicketsErrors:
    """Tests for error handling."""

    def test_disconnected_linear_returns_400(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        _mock_membership(mock_session)

        from src.services.linear_oauth import OAuthError

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            side_effect=OAuthError("not connected"),
        ):
            response = client.get(
                "/api/linear/tickets/search",
                headers=valid_auth_header,
            )

        assert response.status_code == 400
        assert "not connected" in response.json()["detail"]

    def test_linear_api_error_returns_502(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        _mock_membership(mock_session)

        from src.services.linear_graphql import LinearAPIError

        mock_client = AsyncMock()
        mock_client.query.side_effect = LinearAPIError(
            "Rate limited", status_code=429
        )

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search?q=test",
                headers=valid_auth_header,
            )

        assert response.status_code == 502
        assert "Rate limited" in response.json()["detail"]
        # Verify client was still closed despite error
        mock_client.close.assert_awaited_once()

    def test_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/linear/tickets/search")
        assert response.status_code in (401, 403)


class TestSearchTicketsPagination:
    """Tests for cursor-based pagination."""

    def test_after_cursor_forwarded_to_graphql(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        """Verify the 'after' query param is passed through to the GraphQL variables."""
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "viewer": {
                    "assignedIssues": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search?after=cursor-xyz",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        call_args = mock_client.query.call_args
        variables = call_args[0][1]
        assert variables["after"] == "cursor-xyz"

    def test_after_cursor_forwarded_with_search_query(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        """Verify 'after' works together with a search query (issueSearch path)."""
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "issueSearch": {
                    "nodes": [FAKE_NODES[0]],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search?q=notif&after=cursor-page2",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        call_args = mock_client.query.call_args
        variables = call_args[0][1]
        assert variables["after"] == "cursor-page2"
        assert variables["query"] == "notif"
        assert "issueSearch" in call_args[0][0]

    def test_no_after_param_omits_cursor_from_variables(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        """When no 'after' param is sent, cursor should not appear in variables."""
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "viewer": {
                    "assignedIssues": {
                        "nodes": FAKE_NODES,
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        call_args = mock_client.query.call_args
        variables = call_args[0][1]
        assert "after" not in variables

    def test_pageinfo_missing_defaults_gracefully(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        """If Linear omits pageInfo, defaults to no next page."""
        _mock_membership(mock_session)

        mock_client = AsyncMock()
        mock_client.query.return_value = {
            "data": {
                "viewer": {
                    "assignedIssues": {
                        "nodes": FAKE_NODES,
                    }
                }
            }
        }

        with patch(
            "src.routers.linear.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.routers.linear.LinearGraphQLClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/api/linear/tickets/search",
                headers=valid_auth_header,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["has_next_page"] is False
        assert data["end_cursor"] is None
