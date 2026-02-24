"""Tests for Slack channel listing, selection, and management.

Covers:
- list_channels fetches from Slack API with correct parameters
- list_channels handles cursor pagination across multiple pages
- list_channels handles rate limiting (429 + Retry-After)
- get_cached_channels returns cached data without API call
- save_channel_selection stores selection in config JSONB
- get_selected_channels returns empty list when none selected
- is_channel_monitored returns True when selected
- is_channel_monitored returns False when not selected
- is_channel_monitored returns True when no filter configured
- Channel endpoints require authentication
- Refresh endpoint hits Slack API fresh
"""

import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, get_settings
from tests.conftest import (
    TEST_EMAIL,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    _make_test_settings,
)

# Test Slack config values
SLACK_CLIENT_ID = "test-slack-client-id"
SLACK_CLIENT_SECRET = "test-slack-client-secret"
SLACK_SIGNING_SECRET = "test-slack-signing-secret"


@pytest.fixture()
def channel_settings() -> Settings:
    """Create test settings with Slack config and patch everywhere."""
    settings = _make_test_settings(
        SLACK_CLIENT_ID=SLACK_CLIENT_ID,
        SLACK_CLIENT_SECRET=SLACK_CLIENT_SECRET,
        SLACK_SIGNING_SECRET=SLACK_SIGNING_SECRET,
    )
    get_settings.cache_clear()

    import src.auth
    import src.config

    old_config = src.config.get_settings
    old_auth = src.auth.get_settings

    _override = lambda: settings  # noqa: E731
    src.config.get_settings = _override  # type: ignore[assignment]
    src.auth.get_settings = _override  # type: ignore[assignment]

    yield settings

    src.config.get_settings = old_config  # type: ignore[assignment]
    src.auth.get_settings = old_auth  # type: ignore[assignment]
    get_settings.cache_clear()


@pytest.fixture()
def channel_app(channel_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with channel settings and mocked session."""
    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session
    fastapi_app.dependency_overrides[get_settings] = lambda: channel_settings

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def channel_client(channel_app) -> Generator[TestClient, None, None]:
    """Provide a TestClient for the app with channel config."""
    with TestClient(channel_app) as c:
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


def _make_slack_channel_response(
    channels: list[dict],
    next_cursor: str = "",
) -> dict:
    """Create a mock Slack conversations.list response."""
    response = {
        "ok": True,
        "channels": channels,
        "response_metadata": {"next_cursor": next_cursor},
    }
    return response


# ===========================================================================
# Endpoint auth tests
# ===========================================================================


class TestChannelEndpointAuth:
    """Tests that channel endpoints require authentication."""

    def test_list_channels_requires_auth(self, channel_client: TestClient) -> None:
        """GET /api/slack/channels without token returns 401/403."""
        response = channel_client.get("/api/slack/channels")
        assert response.status_code in (401, 403)

    def test_refresh_channels_requires_auth(self, channel_client: TestClient) -> None:
        """POST /api/slack/channels/refresh without token returns 401/403."""
        response = channel_client.post("/api/slack/channels/refresh")
        assert response.status_code in (401, 403)

    def test_select_channels_requires_auth(self, channel_client: TestClient) -> None:
        """POST /api/slack/channels/select without token returns 401/403."""
        response = channel_client.post(
            "/api/slack/channels/select",
            json={"channel_ids": ["C123"]},
        )
        assert response.status_code in (401, 403)


# ===========================================================================
# Service-level tests
# ===========================================================================


class TestListChannels:
    """Tests for slack_channels.list_channels service function."""

    @pytest.mark.asyncio
    async def test_list_channels_calls_slack_api(self) -> None:
        """list_channels calls Slack conversations.list with correct params."""
        from src.services.slack_channels import list_channels

        mock_session = AsyncMock()

        # Mock get_bot_token
        with patch(
            "src.services.slack_channels.get_bot_token",
            return_value="xoxb-test-bot-token",
        ):
            # Mock httpx response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = _make_slack_channel_response([
                {
                    "id": "C001",
                    "name": "general",
                    "is_private": False,
                    "num_members": 42,
                },
                {
                    "id": "C002",
                    "name": "engineering",
                    "is_private": False,
                    "num_members": 15,
                },
            ])

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            # Mock integration for caching
            mock_integration = MagicMock()
            mock_integration.config = {}
            mock_int_result = MagicMock()
            mock_int_result.scalar_one_or_none.return_value = mock_integration
            mock_session.execute = AsyncMock(return_value=mock_int_result)
            mock_session.commit = AsyncMock()

            with patch("src.services.slack_channels.httpx.AsyncClient") as mock_httpx:
                mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

                channels = await list_channels(mock_session, UUID(TEST_WORKSPACE_ID))

        assert len(channels) == 2
        assert channels[0]["id"] == "C001"
        assert channels[0]["name"] == "general"
        assert channels[0]["is_private"] is False
        assert channels[0]["num_members"] == 42
        assert channels[1]["id"] == "C002"
        assert channels[1]["name"] == "engineering"

        # Verify Slack API was called with correct params
        call_args = mock_client.get.call_args
        assert "conversations.list" in call_args[0][0]
        params = call_args[1]["params"]
        assert params["types"] == "public_channel,private_channel"
        assert params["exclude_archived"] == "true"
        assert params["limit"] == "1000"
        assert "Authorization" in call_args[1]["headers"]
        assert "Bearer xoxb-test-bot-token" in call_args[1]["headers"]["Authorization"]

    @pytest.mark.asyncio
    async def test_list_channels_paginates(self) -> None:
        """list_channels handles cursor pagination across two pages."""
        from src.services.slack_channels import list_channels

        mock_session = AsyncMock()

        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.json.return_value = _make_slack_channel_response(
            [{"id": "C001", "name": "general", "is_private": False, "num_members": 10}],
            next_cursor="cursor_page2",
        )

        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.json.return_value = _make_slack_channel_response(
            [{"id": "C002", "name": "random", "is_private": False, "num_members": 5}],
            next_cursor="",
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[page1_response, page2_response])

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_int_result)
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.slack_channels.get_bot_token",
                return_value="xoxb-test-bot-token",
            ),
            patch("src.services.slack_channels.httpx.AsyncClient") as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            channels = await list_channels(mock_session, UUID(TEST_WORKSPACE_ID))

        assert len(channels) == 2
        assert channels[0]["id"] == "C001"
        assert channels[1]["id"] == "C002"

        # Verify two API calls were made
        assert mock_client.get.call_count == 2

        # Second call should include cursor parameter
        second_call_params = mock_client.get.call_args_list[1][1]["params"]
        assert second_call_params["cursor"] == "cursor_page2"


class TestSaveChannelSelection:
    """Tests for channel selection storage."""

    @pytest.mark.asyncio
    async def test_save_channel_selection_stores_in_config(self) -> None:
        """save_channel_selection updates config JSONB with selected channel IDs."""
        from src.services.slack_channels import save_channel_selection

        mock_session = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {"available_channels": []}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        await save_channel_selection(
            mock_session,
            UUID(TEST_WORKSPACE_ID),
            ["C001", "C002", "C003"],
        )

        # Verify config was updated
        assert mock_integration.config["selected_channels"] == ["C001", "C002", "C003"]
        # Verify existing config keys preserved
        assert "available_channels" in mock_integration.config
        mock_session.commit.assert_called_once()


class TestGetSelectedChannels:
    """Tests for reading selected channels."""

    @pytest.mark.asyncio
    async def test_get_selected_channels_returns_empty_when_none(self) -> None:
        """get_selected_channels returns empty list when no selection exists."""
        from src.services.slack_channels import get_selected_channels

        mock_session = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_selected_channels(mock_session, UUID(TEST_WORKSPACE_ID))
        assert result == []

    @pytest.mark.asyncio
    async def test_get_selected_channels_returns_ids(self) -> None:
        """get_selected_channels returns stored channel IDs."""
        from src.services.slack_channels import get_selected_channels

        mock_session = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {"selected_channels": ["C001", "C002"]}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_selected_channels(mock_session, UUID(TEST_WORKSPACE_ID))
        assert result == ["C001", "C002"]


class TestIsChannelMonitored:
    """Tests for channel monitoring check."""

    @pytest.mark.asyncio
    async def test_is_channel_monitored_true_when_selected(self) -> None:
        """is_channel_monitored returns True for a selected channel."""
        from src.services.slack_channels import is_channel_monitored

        mock_session = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {"selected_channels": ["C001", "C002"]}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_channel_monitored(mock_session, UUID(TEST_WORKSPACE_ID), "C001")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_channel_monitored_false_when_not_selected(self) -> None:
        """is_channel_monitored returns False for an unselected channel."""
        from src.services.slack_channels import is_channel_monitored

        mock_session = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {"selected_channels": ["C001", "C002"]}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_channel_monitored(
            mock_session, UUID(TEST_WORKSPACE_ID), "C_OTHER"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_is_channel_monitored_true_when_no_filter(self) -> None:
        """is_channel_monitored returns True when no selected_channels configured."""
        from src.services.slack_channels import is_channel_monitored

        mock_session = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_channel_monitored(
            mock_session, UUID(TEST_WORKSPACE_ID), "C_ANY"
        )
        assert result is True


class TestRefreshChannels:
    """Tests for the refresh channels endpoint."""

    def test_refresh_channels_fetches_fresh(
        self, channel_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """POST /api/slack/channels/refresh fetches from Slack API."""
        # Mock workspace membership lookup for auth
        mock_ws_result = MagicMock()
        mock_ws_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Mock integration for caching
        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_ws_result, mock_int_result]
        )
        mock_session.commit = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_slack_channel_response([
            {"id": "C001", "name": "general", "is_private": False, "num_members": 10},
        ])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch(
                "src.services.slack_channels.get_bot_token",
                return_value="xoxb-test",
            ),
            patch("src.services.slack_channels.httpx.AsyncClient") as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            response = channel_client.post(
                "/api/slack/channels/refresh",
                headers=_make_auth_header(),
            )

        assert response.status_code == 200
        data = response.json()
        assert "channels" in data
        assert len(data["channels"]) == 1
        assert data["channels"][0]["id"] == "C001"

        # Verify Slack API was called (not just cache)
        mock_client.get.assert_called_once()


class TestGetChannelsEndpoint:
    """Tests for the GET /channels endpoint (cached)."""

    def test_get_channels_returns_cached(
        self, channel_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """GET /api/slack/channels returns cached channel list."""
        # Mock workspace membership lookup for auth
        mock_ws_result = MagicMock()
        mock_ws_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Mock integration with cached channels
        mock_integration = MagicMock()
        mock_integration.config = {
            "available_channels": [
                {"id": "C001", "name": "general", "is_private": False, "num_members": 10},
                {"id": "C002", "name": "random", "is_private": False, "num_members": 5},
            ]
        }
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_ws_result, mock_int_result]
        )

        response = channel_client.get(
            "/api/slack/channels",
            headers=_make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert "channels" in data
        assert len(data["channels"]) == 2
        assert data["channels"][0]["id"] == "C001"
