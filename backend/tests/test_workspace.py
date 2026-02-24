"""Tests for workspace endpoints and service layer."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from fastapi.testclient import TestClient

from tests.conftest import TEST_WORKSPACE_ID


# ---------------------------------------------------------------------------
# Endpoint tests for GET /api/workspaces/current
# ---------------------------------------------------------------------------


def test_workspaces_current_returns_401_without_token(client: TestClient) -> None:
    """GET /api/workspaces/current without auth returns 401/403."""
    response = client.get("/api/workspaces/current")
    assert response.status_code in (401, 403)


def test_workspaces_current_returns_401_with_invalid_token(client: TestClient) -> None:
    """GET /api/workspaces/current with invalid token returns 401."""
    response = client.get(
        "/api/workspaces/current",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Unit tests for workspace service functions
# ---------------------------------------------------------------------------


async def test_get_workspace_by_id(mock_settings) -> None:
    """get_workspace_by_id returns workspace when found."""
    from src.models.workspace import Workspace
    from src.services.workspace import get_workspace_by_id

    # Create a mock workspace
    mock_workspace = Workspace(
        id=UUID(TEST_WORKSPACE_ID),
        name="Test Workspace",
        slug="test-workspace",
    )

    # Mock the session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_workspace
    mock_session.execute.return_value = mock_result

    result = await get_workspace_by_id(mock_session, UUID(TEST_WORKSPACE_ID))

    assert result is not None
    assert result.id == UUID(TEST_WORKSPACE_ID)
    assert result.name == "Test Workspace"
    assert result.slug == "test-workspace"
    mock_session.execute.assert_called_once()


async def test_get_workspace_by_id_returns_none_when_not_found(mock_settings) -> None:
    """get_workspace_by_id returns None when workspace does not exist."""
    from src.services.workspace import get_workspace_by_id

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await get_workspace_by_id(mock_session, UUID(TEST_WORKSPACE_ID))

    assert result is None
    mock_session.execute.assert_called_once()


async def test_get_user_workspace(mock_settings) -> None:
    """get_user_workspace returns workspace for a user via membership join."""
    from src.models.workspace import Workspace
    from src.services.workspace import get_user_workspace

    mock_workspace = Workspace(
        id=UUID(TEST_WORKSPACE_ID),
        name="Test Workspace",
        slug="test-workspace",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_workspace
    mock_session.execute.return_value = mock_result

    user_id = UUID("11111111-1111-1111-1111-111111111111")
    result = await get_user_workspace(mock_session, user_id)

    assert result is not None
    assert result.id == UUID(TEST_WORKSPACE_ID)
    mock_session.execute.assert_called_once()
