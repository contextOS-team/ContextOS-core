"""Tests for POST /api/context/{ticket_identifier}/generate endpoint.

Covers backward compatibility (no body), the new linear_issue_id body,
and the sync-then-generate flow in the background task.
"""

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
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
    mock_session.execute.return_value = mock_result


class TestTriggerGeneration:
    """Tests for the POST endpoint itself (returns 202)."""

    def test_no_body_returns_202(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        """Backward compat: POST with no body still works."""
        _mock_membership(mock_session)

        with patch("src.routers.context._generate_in_background"):
            response = client.post(
                "/api/context/ENG-42/generate",
                headers=valid_auth_header,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["ticket_identifier"] == "ENG-42"
        assert data["status"] == "accepted"

    def test_empty_json_body_returns_202(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        """Frontend sends {} when no linearIssueId — should work."""
        _mock_membership(mock_session)

        with patch("src.routers.context._generate_in_background"):
            response = client.post(
                "/api/context/ENG-42/generate",
                headers=valid_auth_header,
                json={},
            )

        assert response.status_code == 202

    def test_with_linear_issue_id_returns_202(
        self,
        client: TestClient,
        valid_auth_header: dict,
        mock_session: AsyncMock,
    ) -> None:
        _mock_membership(mock_session)

        with patch("src.routers.context._generate_in_background"):
            response = client.post(
                "/api/context/ENG-42/generate",
                headers=valid_auth_header,
                json={"linear_issue_id": "abc-123-uuid"},
            )

        assert response.status_code == 202

    def test_requires_auth(self, client: TestClient) -> None:
        response = client.post("/api/context/ENG-42/generate")
        assert response.status_code in (401, 403)


class TestGenerateInBackground:
    """Tests for the _generate_in_background function directly."""

    @staticmethod
    def _make_session_ctx(mock_session):
        """Create a proper async context manager mock for async_session()."""
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    @pytest.mark.asyncio
    async def test_syncs_ticket_when_missing(self, mock_settings) -> None:
        """When ticket not in DB and linear_issue_id provided, syncs first."""
        from src.routers.context import _generate_in_background

        mock_session = AsyncMock()
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_ticket_result

        ctx = self._make_session_ctx(mock_session)

        with patch(
            "src.services.linear_oauth.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ), patch(
            "src.services.linear_sync.sync_single_ticket",
            new_callable=AsyncMock,
        ) as mock_sync, patch(
            "src.routers.context.generate_context_page",
            new_callable=AsyncMock,
        ) as mock_generate, patch(
            "src.routers.context.async_session",
            return_value=ctx,
        ):
            await _generate_in_background(
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID("11111111-1111-1111-1111-111111111111"),
                ticket_identifier="ENG-42",
                linear_issue_id="abc-123-uuid",
                jira_issue_id=None,
                settings=mock_settings,
            )

        mock_sync.assert_awaited_once_with(
            mock_session, UUID(TEST_WORKSPACE_ID), "fake-token", "abc-123-uuid"
        )
        mock_generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_sync_when_ticket_exists(self, mock_settings) -> None:
        """When ticket exists locally, goes straight to generation."""
        from src.routers.context import _generate_in_background

        mock_session = AsyncMock()
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalar_one_or_none.return_value = MagicMock()
        mock_session.execute.return_value = mock_ticket_result

        ctx = self._make_session_ctx(mock_session)

        with patch(
            "src.services.linear_sync.sync_single_ticket",
            new_callable=AsyncMock,
        ) as mock_sync, patch(
            "src.routers.context.generate_context_page",
            new_callable=AsyncMock,
        ), patch(
            "src.routers.context.async_session",
            return_value=ctx,
        ):
            await _generate_in_background(
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID("11111111-1111-1111-1111-111111111111"),
                ticket_identifier="ENG-42",
                linear_issue_id="abc-123-uuid",
                jira_issue_id=None,
                settings=mock_settings,
            )

        mock_sync.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_sync_when_no_linear_issue_id(self, mock_settings) -> None:
        """When no linear_issue_id provided, does not attempt sync."""
        from src.routers.context import _generate_in_background

        mock_session = AsyncMock()
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_ticket_result

        ctx = self._make_session_ctx(mock_session)

        with patch(
            "src.services.linear_sync.sync_single_ticket",
            new_callable=AsyncMock,
        ) as mock_sync, patch(
            "src.routers.context.generate_context_page",
            new_callable=AsyncMock,
        ), patch(
            "src.routers.context.async_session",
            return_value=ctx,
        ):
            await _generate_in_background(
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID("11111111-1111-1111-1111-111111111111"),
                ticket_identifier="ENG-42",
                linear_issue_id=None,
                jira_issue_id=None,
                settings=mock_settings,
            )

        mock_sync.assert_not_awaited()
