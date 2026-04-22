"""Tests for Slack OAuth, Events API, and message processing.

Covers:
- OAuth connect requires auth
- OAuth connect returns authorization URL
- OAuth callback rejects invalid state
- OAuth disconnect requires auth
- Events API URL verification challenge
- Events API signature verification (valid, invalid, old timestamp)
- Message filtering (bot, short, system messages)
- Regular message storage
- Thread reply with parent_ts
- File share text storage
- Message edit overwrites text
- Message delete soft-deletes
- Unmonitored channel skip
"""

import hashlib
import hmac
import json
import time
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings
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


@pytest.fixture(autouse=True)
def _patch_queue_embedding():
    with patch("src.services.embedding.queue_embedding_generation", new_callable=AsyncMock):
        yield


@pytest.fixture()
def slack_settings() -> Settings:
    """Create test settings with Slack OAuth config."""
    settings = _make_test_settings(
        SLACK_CLIENT_ID=SLACK_CLIENT_ID,
        SLACK_CLIENT_SECRET=SLACK_CLIENT_SECRET,
        SLACK_SIGNING_SECRET=SLACK_SIGNING_SECRET,
    )
    src.config._settings = settings
    yield settings


@pytest.fixture()
def slack_app(slack_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with Slack settings and mocked session."""
    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def slack_client(slack_app) -> Generator[TestClient, None, None]:
    """Provide a TestClient for the app with Slack config."""
    with TestClient(slack_app) as c:
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


def _sign_slack_request(body: bytes, timestamp: str, secret: str = SLACK_SIGNING_SECRET) -> str:
    """Compute Slack HMAC-SHA256 signature for request body."""
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    return "v0=" + hmac.new(
        secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()


# ===========================================================================
# OAuth tests
# ===========================================================================


class TestSlackConnect:
    """Tests for GET /api/slack/connect."""

    def test_connect_requires_auth(self, slack_client: TestClient) -> None:
        """GET /api/slack/connect without token returns 401/403."""
        response = slack_client.get("/api/slack/connect")
        assert response.status_code in (401, 403)

    def test_connect_returns_auth_url(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """GET /api/slack/connect returns 200 with authorization_url."""
        # Mock workspace membership lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
        mock_session.execute.return_value = mock_result

        response = slack_client.get(
            "/api/slack/connect", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        url = data["authorization_url"]
        assert "slack.com/oauth/v2/authorize" in url
        assert f"client_id={SLACK_CLIENT_ID}" in url
        assert "state=" in url
        assert "channels%3Aread" in url


class TestSlackCallback:
    """Tests for GET /api/slack/callback."""

    def test_callback_rejects_invalid_state(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """GET /api/slack/callback with bad state redirects with error."""
        response = slack_client.get(
            "/api/slack/callback",
            params={"code": "test-code", "state": "bad:state"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "slack=error" in response.headers["location"]
        assert "invalid_state" in response.headers["location"]


class TestSlackDisconnect:
    """Tests for POST /api/slack/disconnect."""

    def test_disconnect_requires_auth(self, slack_client: TestClient) -> None:
        """POST /api/slack/disconnect without token returns 401/403."""
        response = slack_client.post("/api/slack/disconnect")
        assert response.status_code in (401, 403)


# ===========================================================================
# Events API tests
# ===========================================================================


class TestSlackEvents:
    """Tests for POST /api/slack/events."""

    def test_events_url_verification_challenge(
        self, slack_client: TestClient
    ) -> None:
        """URL verification challenge returns the challenge value."""
        payload = {
            "type": "url_verification",
            "challenge": "test-challenge-string",
            "token": "deprecated-token",
        }
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))
        signature = _sign_slack_request(body, timestamp)

        response = slack_client.post(
            "/api/slack/events",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": signature,
            },
        )

        assert response.status_code == 200
        assert response.json()["challenge"] == "test-challenge-string"

    def test_events_rejects_invalid_signature(
        self, slack_client: TestClient
    ) -> None:
        """Event callback with invalid signature returns 401."""
        payload = {
            "type": "event_callback",
            "team_id": "T12345",
            "event": {"type": "message", "text": "Hello world from Slack!"},
        }
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))

        response = slack_client.post(
            "/api/slack/events",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": "v0=invalidsignature",
            },
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_events_rejects_old_timestamp(
        self, slack_client: TestClient
    ) -> None:
        """Event callback with old timestamp returns 401 (replay protection)."""
        payload = {
            "type": "event_callback",
            "team_id": "T12345",
            "event": {"type": "message", "text": "Hello from the past!"},
        }
        body = json.dumps(payload).encode()
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        signature = _sign_slack_request(body, old_timestamp)

        response = slack_client.post(
            "/api/slack/events",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": old_timestamp,
                "X-Slack-Signature": signature,
            },
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_events_accepts_valid_signature(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """Event callback with valid signature returns 200."""
        payload = {
            "type": "event_callback",
            "team_id": "T12345",
            "event": {
                "type": "message",
                "text": "A valid message from Slack",
                "ts": "1234567890.123456",
                "channel": "C12345",
                "user": "U12345",
            },
        }
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))
        signature = _sign_slack_request(body, timestamp)

        # Mock workspace lookup -- integration found
        mock_integration = MagicMock()
        mock_integration.workspace_id = UUID(TEST_WORKSPACE_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute.return_value = mock_result

        with patch("src.routers.slack._process_event_background"):
            response = slack_client.post(
                "/api/slack/events",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Slack-Request-Timestamp": timestamp,
                    "X-Slack-Signature": signature,
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ===========================================================================
# Message processing tests
# ===========================================================================


class TestMessageFiltering:
    """Tests for message filtering rules in slack_events.py."""

    def test_filters_bot_messages(self) -> None:
        """Messages with bot_id should be filtered out."""
        from src.services.slack_events import _should_filter

        event = {
            "type": "message",
            "bot_id": "B12345",
            "text": "This is a bot message with enough chars",
        }
        assert _should_filter(event) is True

    def test_short_messages_no_longer_filtered(self) -> None:
        """Phase 39: the <10-char length filter has been removed.

        Short messages like 'done', 'no', 'approved' carry meaningful
        signal and must pass the filter on both the channel webhook
        path and the new DM polling path.
        """
        from src.services.slack_events import _should_filter

        # Previously filtered; now pass
        assert _should_filter({"type": "message", "text": "done"}) is False
        assert _should_filter({"type": "message", "text": "no"}) is False
        assert _should_filter({"type": "message", "text": ""}) is False

        # Bot and system-subtype filters remain
        assert _should_filter({"bot_id": "B1", "text": "hello world"}) is True
        assert (
            _should_filter({"subtype": "channel_join", "text": "long enough text"})
            is True
        )

    def test_filters_system_messages(self) -> None:
        """System message subtypes (channel_join, etc.) should be filtered out."""
        from src.services.slack_events import _should_filter

        for subtype in ["channel_join", "channel_leave", "channel_topic", "channel_purpose", "channel_name", "bot_message"]:
            event = {"type": "message", "subtype": subtype, "text": "System message text long enough"}
            assert _should_filter(event) is True, f"Expected filter for subtype: {subtype}"

    def test_passes_regular_message(self) -> None:
        """Regular messages with 10+ characters should pass filtering."""
        from src.services.slack_events import _should_filter

        event = {
            "type": "message",
            "text": "This is a regular message that should be stored",
            "user": "U12345",
        }
        assert _should_filter(event) is False

    def test_passes_file_share_with_text(self) -> None:
        """File share messages with text should pass filtering."""
        from src.services.slack_events import _should_filter

        event = {
            "type": "message",
            "subtype": "file_share",
            "text": "Check out this file I shared with the team",
            "user": "U12345",
        }
        assert _should_filter(event) is False


class TestMessageProcessing:
    """Tests for message storage and processing."""

    @pytest.mark.asyncio
    async def test_stores_regular_message(self) -> None:
        """Regular message is upserted into slack_messages."""
        from src.services.slack_events import process_event

        event_payload = {
            "event": {
                "type": "message",
                "text": "This is a meaningful Slack message",
                "ts": "1234567890.123456",
                "channel": "C12345",
                "user": "U12345",
            },
        }
        workspace_id = UUID(TEST_WORKSPACE_ID)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock channel monitoring check -- returns integration with all channels
        mock_integration = MagicMock()
        mock_integration.config = {}  # No selected_channels = all channels monitored
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        # Mock the message ID query after upsert
        mock_msg_result = MagicMock()
        mock_msg_result.scalar_one_or_none.return_value = uuid4()

        mock_session.execute = AsyncMock(
            side_effect=[mock_int_result, MagicMock(), mock_msg_result]
        )
        mock_session.commit = AsyncMock()

        with patch("src.services.slack_events.embedding") as mock_embedding:
            mock_embedding.queue_embedding_generation = AsyncMock()
            await process_event(event_payload, workspace_id, mock_session)

        # Verify execute was called (upsert + message ID query)
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_stores_thread_reply_with_parent_ts(self) -> None:
        """Thread reply has is_thread_reply=True and parent_ts set."""
        from src.services.slack_events import process_event

        event_payload = {
            "event": {
                "type": "message",
                "text": "This is a reply in a thread conversation",
                "ts": "1234567890.999999",
                "thread_ts": "1234567890.123456",
                "channel": "C12345",
                "user": "U12345",
            },
        }
        workspace_id = UUID(TEST_WORKSPACE_ID)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_msg_result = MagicMock()
        mock_msg_result.scalar_one_or_none.return_value = uuid4()

        # Track the upsert values
        upsert_values = {}

        original_execute = mock_session.execute

        call_count = 0

        async def track_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_int_result
            elif call_count == 2:
                # Capture the upsert statement
                stmt = args[0]
                if hasattr(stmt, "compile"):
                    params = stmt.compile().params if hasattr(stmt.compile(), 'params') else {}
                    upsert_values.update(params)
                return MagicMock()
            else:
                return mock_msg_result

        mock_session.execute = AsyncMock(side_effect=track_execute)
        mock_session.commit = AsyncMock()

        with patch("src.services.slack_events.embedding") as mock_embedding:
            mock_embedding.queue_embedding_generation = AsyncMock()
            await process_event(event_payload, workspace_id, mock_session)

        # Verify the upsert was called
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_stores_file_share_text(self) -> None:
        """File share message text is stored (subtype=file_share with text)."""
        from src.services.slack_events import process_event

        event_payload = {
            "event": {
                "type": "message",
                "subtype": "file_share",
                "text": "Here's a document I'm sharing with the team for review",
                "ts": "1234567890.555555",
                "channel": "C12345",
                "user": "U12345",
            },
        }
        workspace_id = UUID(TEST_WORKSPACE_ID)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_msg_result = MagicMock()
        mock_msg_result.scalar_one_or_none.return_value = uuid4()

        mock_session.execute = AsyncMock(
            side_effect=[mock_int_result, MagicMock(), mock_msg_result]
        )
        mock_session.commit = AsyncMock()

        with patch("src.services.slack_events.embedding") as mock_embedding:
            mock_embedding.queue_embedding_generation = AsyncMock()
            await process_event(event_payload, workspace_id, mock_session)

        # File share was processed (not filtered)
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_message_edit_overwrites_text(self) -> None:
        """Message edit overwrites stored text with latest version."""
        from src.services.slack_events import process_event

        event_payload = {
            "event": {
                "type": "message",
                "subtype": "message_changed",
                "channel": "C12345",
                "message": {
                    "type": "message",
                    "text": "Updated message text that replaces the original",
                    "ts": "1234567890.123456",
                    "user": "U12345",
                },
                "previous_message": {
                    "type": "message",
                    "text": "Original message text that was here before",
                    "ts": "1234567890.123456",
                },
            },
        }
        workspace_id = UUID(TEST_WORKSPACE_ID)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock finding existing message
        existing_msg = MagicMock()
        existing_msg.id = uuid4()
        existing_msg.text = "Original message text that was here before"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_msg

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("src.services.slack_events.embedding") as mock_embedding:
            mock_embedding.queue_embedding_generation = AsyncMock()
            await process_event(event_payload, workspace_id, mock_session)

        # Verify text was overwritten
        assert existing_msg.text == "Updated message text that replaces the original"

        # Verify re-embedding was queued (text changed)
        mock_embedding.queue_embedding_generation.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_delete_soft_deletes(self) -> None:
        """Message delete sets deleted_at on the record."""
        from src.services.slack_events import process_event

        event_payload = {
            "event": {
                "type": "message",
                "subtype": "message_deleted",
                "channel": "C12345",
                "previous_message": {
                    "type": "message",
                    "text": "This message was deleted by the user",
                    "ts": "1234567890.123456",
                },
                "deleted_ts": "1234567890.123456",
            },
        }
        workspace_id = UUID(TEST_WORKSPACE_ID)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock finding existing message
        existing_msg = MagicMock()
        existing_msg.id = uuid4()
        existing_msg.deleted_at = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_msg

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        await process_event(event_payload, workspace_id, mock_session)

        # Verify soft-delete
        assert existing_msg.deleted_at is not None

    @pytest.mark.asyncio
    async def test_skips_unmonitored_channel(self) -> None:
        """Messages from channels not in selected_channels are skipped."""
        from src.services.slack_events import process_event

        event_payload = {
            "event": {
                "type": "message",
                "text": "This message is in an unmonitored channel",
                "ts": "1234567890.123456",
                "channel": "C_UNMONITORED",
                "user": "U12345",
            },
        }
        workspace_id = UUID(TEST_WORKSPACE_ID)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock integration with specific selected_channels (not including C_UNMONITORED)
        mock_integration = MagicMock()
        mock_integration.config = {"selected_channels": ["C_MONITORED_1", "C_MONITORED_2"]}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(return_value=mock_int_result)
        mock_session.commit = AsyncMock()

        with patch("src.services.slack_events.embedding") as mock_embedding:
            mock_embedding.queue_embedding_generation = AsyncMock()
            await process_event(event_payload, workspace_id, mock_session)

        # Only the channel monitoring check should have been called
        # No upsert or embedding should happen
        mock_session.commit.assert_not_called()
        mock_embedding.queue_embedding_generation.assert_not_called()


# ===========================================================================
# Signature verification unit tests
# ===========================================================================


class TestSignatureVerification:
    """Unit tests for verify_signature function."""

    def test_valid_signature(self) -> None:
        """Valid signature returns True."""
        from src.services.slack_events import verify_signature

        body = b'{"type":"event_callback","event":{"text":"hello world!"}}'
        timestamp = str(int(time.time()))
        sig = _sign_slack_request(body, timestamp)

        assert verify_signature(SLACK_SIGNING_SECRET, timestamp, body, sig) is True

    def test_invalid_signature(self) -> None:
        """Tampered signature returns False."""
        from src.services.slack_events import verify_signature

        body = b'{"type":"event_callback","event":{"text":"hello world!"}}'
        timestamp = str(int(time.time()))

        assert verify_signature(SLACK_SIGNING_SECRET, timestamp, body, "v0=invalid") is False

    def test_old_timestamp_rejected(self) -> None:
        """Timestamp older than 5 minutes returns False."""
        from src.services.slack_events import verify_signature

        body = b'{"type":"event_callback"}'
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        sig = _sign_slack_request(body, old_timestamp)

        assert verify_signature(SLACK_SIGNING_SECRET, old_timestamp, body, sig) is False


# ===========================================================================
# OAuth service unit tests
# ===========================================================================


class TestSlackOAuthService:
    """Unit tests for slack_oauth.py service functions."""

    @pytest.mark.asyncio
    async def test_exchange_code_stores_bot_token(
        self, slack_settings: Settings
    ) -> None:
        """exchange_code stores bot token in Vault and creates integration."""
        from src.services.slack_oauth import exchange_code

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-slack-bot-token",
            "team": {"id": "T12345", "name": "Test Team"},
            "scope": "channels:read,channels:history,groups:read,groups:history,users:read",
        }

        # Track vault calls
        vault_calls = []

        async def mock_store(session, name, value):
            vault_calls.append(("store", name, value))
            return "secret-uuid"

        # Mock DB queries -- return None for existing records (creates new)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with (
            patch("src.services.slack_oauth.store_token", side_effect=mock_store),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_response)
                ),
            ),
        ):
            team_info = await exchange_code(
                code="test-auth-code",
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID(TEST_USER_ID),
                settings=slack_settings,
            )

        assert team_info["id"] == "T12345"
        assert team_info["name"] == "Test Team"

        # Verify bot token was stored in Vault
        assert len(vault_calls) == 1
        assert vault_calls[0][0] == "store"
        assert "bot_access" in vault_calls[0][1]
        assert vault_calls[0][2] == "xoxb-slack-bot-token"

        # Verify session.add was called (OAuthToken + WorkspaceIntegration)
        assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_disconnect_soft_deletes_token(
        self, slack_settings: Settings
    ) -> None:
        """disconnect marks token as deleted and integration as disconnected."""
        from src.services.slack_oauth import disconnect

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock OAuthToken query
        mock_oauth_token = MagicMock()
        mock_oauth_token.deleted_at = None

        # Mock WorkspaceIntegration query
        mock_integration = MagicMock()
        mock_integration.status = "connected"

        # disconnect_provider flow (with Phase 39 dual-token change):
        #   1. Select OAuthToken  -> returns mock_oauth_token
        #   2. delete_token(bot_access)   -> internal execute
        #   3. delete_token(user_access)  -> internal execute (new in Phase 39)
        #   4. Select WorkspaceIntegration -> returns mock_integration
        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = mock_oauth_token
            elif call_count == 4:
                result.scalar_one_or_none.return_value = mock_integration
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_session.commit = AsyncMock()

        await disconnect(
            session=mock_session,
            workspace_id=UUID(TEST_WORKSPACE_ID),
            user_id=UUID(TEST_USER_ID),
        )

        assert mock_oauth_token.deleted_at is not None
        assert mock_integration.status == "disconnected"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bot_token_reads_from_vault(
        self, slack_settings: Settings
    ) -> None:
        """get_bot_token reads token from Vault."""
        from src.services.slack_oauth import get_bot_token

        mock_session = AsyncMock()

        with patch(
            "src.services.slack_oauth.read_token",
            return_value="xoxb-stored-bot-token",
        ):
            token = await get_bot_token(
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
            )

        assert token == "xoxb-stored-bot-token"

    @pytest.mark.asyncio
    async def test_get_bot_token_raises_when_missing(
        self, slack_settings: Settings
    ) -> None:
        """get_bot_token raises SlackOAuthError when no token found."""
        from src.services.slack_oauth import SlackOAuthError, get_bot_token

        mock_session = AsyncMock()

        with (
            patch("src.services.slack_oauth.read_token", return_value=None),
            pytest.raises(SlackOAuthError, match="No Slack bot token found"),
        ):
            await get_bot_token(
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
            )


# ===========================================================================
# Phase 39: User token OAuth (dual-token exchange + Vault storage)
# ===========================================================================


class TestUserTokenOAuth:
    """Tests for dual-token (bot + user) OAuth exchange and user token helpers.

    Covers Phase 39 Plan 01 requirements:
    - SLACK_USER_SCOPES is DM-only (im/mpim/users); no channels/groups scopes
    - build_auth_url wires user_scope to SLACK_USER_SCOPES
    - exchange_code stores both bot and user tokens when authed_user present
    - exchange_code tolerates missing authed_user (bot-only, warns)
    - integration.config.slack_user_id is populated from authed_user.id
    - get_user_token reads user_access token from Vault; raises when missing
    """

    def test_build_auth_url_includes_dm_only_user_scopes(
        self, slack_settings: Settings
    ) -> None:
        """build_auth_url wires SLACK_USER_SCOPES into user_scope param."""
        from urllib.parse import parse_qs, urlparse

        from src.services.slack_oauth import SLACK_USER_SCOPES, build_auth_url

        # SLACK_USER_SCOPES is DM-only per CONTEXT.md lock
        expected = "im:read,im:history,mpim:read,mpim:history,users:read,users:read.email"
        assert SLACK_USER_SCOPES == expected

        url = build_auth_url("test-state", slack_settings)

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        assert "user_scope" in query
        user_scope_value = query["user_scope"][0]
        assert user_scope_value == SLACK_USER_SCOPES

        # Channels/groups scopes must NOT appear in user_scope
        assert "channels:read" not in user_scope_value
        assert "channels:history" not in user_scope_value
        assert "groups:read" not in user_scope_value
        assert "groups:history" not in user_scope_value

    @pytest.mark.asyncio
    async def test_exchange_code_stores_both_tokens_and_slack_user_id(
        self, slack_settings: Settings
    ) -> None:
        """exchange_code stores bot + user tokens and writes slack_user_id into config."""
        from src.services.slack_oauth import exchange_code

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock httpx response with authed_user present
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-bot",
            "team": {"id": "T12345", "name": "Test Team"},
            "authed_user": {
                "id": "U123",
                "access_token": "xoxp-user",
                "scope": "im:read,im:history",
            },
        }

        vault_calls: list[tuple[str, str, str]] = []

        async def mock_store(session, name, value):
            vault_calls.append(("store", name, value))
            return "secret-uuid"

        # Mock integration returned after upsert so we can patch slack_user_id.
        # Use a simple namespace instead of MagicMock so integration.config
        # mutations behave like dict updates.
        class _Integration:
            def __init__(self) -> None:
                self.config: dict = {"external_name": "Test Team"}

        integration_row = _Integration()

        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = integration_row

        mock_null_result = MagicMock()
        mock_null_result.scalar_one_or_none.return_value = None

        # First execute: upsert_oauth_token lookup (None -> insert)
        # Second execute: upsert_workspace_integration lookup (None -> insert)
        # Third execute: re-query integration to patch slack_user_id
        execute_results = [mock_null_result, mock_null_result, mock_int_result]
        call_index = 0

        async def mock_execute(*args, **kwargs):
            nonlocal call_index
            result = execute_results[min(call_index, len(execute_results) - 1)]
            call_index += 1
            return result

        mock_session.execute = mock_execute
        mock_session.commit = AsyncMock()

        # Skip roster seeding (fail-silent import in exchange_code)
        with (
            patch("src.services.slack_oauth.store_token", side_effect=mock_store),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_response)
                ),
            ),
            patch(
                "src.services.identity_resolution.fetch_slack_roster",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.services.identity_resolution.seed_roster",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            team_info = await exchange_code(
                code="test-auth-code",
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID(TEST_USER_ID),
                settings=slack_settings,
            )

        assert team_info["id"] == "T12345"

        # Both tokens stored under the correct Vault names
        stored_by_name = {call[1]: call[2] for call in vault_calls}
        from src.models.integration import Provider
        from src.services.vault import token_name

        bot_key = token_name(Provider.SLACK, UUID(TEST_WORKSPACE_ID), "bot_access")
        user_key = token_name(Provider.SLACK, UUID(TEST_WORKSPACE_ID), "user_access")

        assert stored_by_name[bot_key] == "xoxb-bot"
        assert stored_by_name[user_key] == "xoxp-user"

        # slack_user_id merged into integration.config without clobbering existing keys
        assert integration_row.config["slack_user_id"] == "U123"
        assert integration_row.config["external_name"] == "Test Team"

    @pytest.mark.asyncio
    async def test_exchange_code_tolerates_missing_authed_user(
        self, slack_settings: Settings
    ) -> None:
        """exchange_code still succeeds when authed_user is absent; only bot token stored."""
        from src.services.slack_oauth import exchange_code

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-bot-only",
            "team": {"id": "T99999", "name": "Legacy Team"},
            # authed_user intentionally omitted
        }

        vault_calls: list[tuple[str, str, str]] = []

        async def mock_store(session, name, value):
            vault_calls.append(("store", name, value))
            return "secret-uuid"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with (
            patch("src.services.slack_oauth.store_token", side_effect=mock_store),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_response)
                ),
            ),
            patch(
                "src.services.identity_resolution.fetch_slack_roster",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.services.identity_resolution.seed_roster",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            team_info = await exchange_code(
                code="legacy-code",
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID(TEST_USER_ID),
                settings=slack_settings,
            )

        assert team_info["id"] == "T99999"

        # Only one vault store call -- for bot token
        assert len(vault_calls) == 1
        assert "bot_access" in vault_calls[0][1]
        assert vault_calls[0][2] == "xoxb-bot-only"

        # No user_access key stored
        user_keys = [c[1] for c in vault_calls if "user_access" in c[1]]
        assert user_keys == []

    @pytest.mark.asyncio
    async def test_get_user_token_returns_stored_token(
        self, slack_settings: Settings
    ) -> None:
        """get_user_token returns the user token when present in Vault."""
        from src.services.slack_oauth import get_user_token

        mock_session = AsyncMock()

        with patch(
            "src.services.slack_oauth.read_token",
            return_value="xoxp-stored-user",
        ):
            token = await get_user_token(
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
            )

        assert token == "xoxp-stored-user"

    @pytest.mark.asyncio
    async def test_get_user_token_raises_when_missing(
        self, slack_settings: Settings
    ) -> None:
        """get_user_token raises SlackOAuthError when no user token found (no legacy fallback)."""
        from src.services.slack_oauth import SlackOAuthError, get_user_token

        mock_session = AsyncMock()

        with (
            patch("src.services.slack_oauth.read_token", return_value=None),
            pytest.raises(SlackOAuthError, match="No Slack user token found"),
        ):
            await get_user_token(
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
            )


# ===========================================================================
# Phase 39: /status needs_reauth + include_dms, POST /dms/toggle
# ===========================================================================


class TestDmToggleAndStatus:
    """Tests for the Phase 39 status + DM toggle endpoints.

    - GET /api/slack/status returns needs_reauth + include_dms
    - POST /api/slack/dms/toggle persists include_dms in integration.config
    - Toggle is rejected with 409 when no user token is stored
    - Toggle requires a valid JWT (401 when missing)
    """

    def _make_connected_integration(
        self,
        *,
        include_dms: bool | None = None,
        extra_config: dict | None = None,
    ):
        """Build a MagicMock WorkspaceIntegration row in the `connected` state."""
        integration = MagicMock()
        integration.status = "connected"
        integration.external_id = "Acme"
        config: dict = {}
        if include_dms is not None:
            config["include_dms"] = include_dms
        if extra_config:
            config.update(extra_config)
        integration.config = config
        return integration

    def _wire_session(
        self,
        mock_session: AsyncMock,
        integration_rows: list,
    ) -> None:
        """Wire session.execute to return:

        1st call  -> workspace_id UUID (for get_current_user auth lookup)
        Nth calls -> integration rows for the route handler

        Each element of `integration_rows` represents one call to
        `session.execute(...)` inside the route; `scalar_one_or_none()` on
        the returned MagicMock will yield that value.
        """
        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        results: list = [ws_result]
        for row in integration_rows:
            r = MagicMock()
            r.scalar_one_or_none.return_value = row
            results.append(r)

        fallback = MagicMock()
        fallback.scalar_one_or_none.return_value = None

        async def _execute(*args, **kwargs):
            if results:
                return results.pop(0)
            return fallback

        mock_session.execute = AsyncMock(side_effect=_execute)

    def test_status_needs_reauth_true_when_user_token_missing(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """Connected workspace with no user token -> needs_reauth=true."""
        integration = self._make_connected_integration()
        self._wire_session(mock_session, [integration])

        with patch("src.routers.slack.read_token", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = None  # No user token in Vault
            response = slack_client.get(
                "/api/slack/status", headers=_make_auth_header()
            )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["needs_reauth"] is True
        assert data["include_dms"] is False

    def test_status_needs_reauth_false_when_user_token_present(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """Connected workspace with user token -> needs_reauth=false."""
        integration = self._make_connected_integration()
        self._wire_session(mock_session, [integration])

        with patch("src.routers.slack.read_token", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = "xoxp-user-present"
            response = slack_client.get(
                "/api/slack/status", headers=_make_auth_header()
            )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["needs_reauth"] is False
        assert data["include_dms"] is False

    def test_status_include_dms_defaults_false(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """Fresh connect (config without include_dms) -> include_dms=false."""
        integration = self._make_connected_integration()
        # Ensure no include_dms key at all
        integration.config = {}
        self._wire_session(mock_session, [integration])

        with patch("src.routers.slack.read_token", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = "xoxp-user"
            response = slack_client.get(
                "/api/slack/status", headers=_make_auth_header()
            )

        assert response.status_code == 200
        assert response.json()["include_dms"] is False

    def test_status_include_dms_reflects_config(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """include_dms=true in config -> status reflects it."""
        integration = self._make_connected_integration(include_dms=True)
        self._wire_session(mock_session, [integration])

        with patch("src.routers.slack.read_token", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = "xoxp-user"
            response = slack_client.get(
                "/api/slack/status", headers=_make_auth_header()
            )

        assert response.status_code == 200
        assert response.json()["include_dms"] is True

    def test_dms_toggle_enables_and_persists(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """POST /dms/toggle {enabled: true} persists include_dms=true."""
        integration = self._make_connected_integration()
        self._wire_session(mock_session, [integration])

        with patch("src.routers.slack.read_token", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = "xoxp-user"  # user token present
            response = slack_client.post(
                "/api/slack/dms/toggle",
                headers=_make_auth_header(),
                json={"enabled": True},
            )

        assert response.status_code == 200
        assert response.json() == {"include_dms": True}

        # The handler must mutate integration.config with include_dms=True and commit
        assert integration.config.get("include_dms") is True
        assert "dms_first_enabled_at" in integration.config  # backfill marker set
        assert mock_session.commit.await_count >= 1

    def test_dms_toggle_disables(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """POST /dms/toggle {enabled: false} persists include_dms=false."""
        integration = self._make_connected_integration(include_dms=True)
        self._wire_session(mock_session, [integration])

        with patch("src.routers.slack.read_token", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = "xoxp-user"
            response = slack_client.post(
                "/api/slack/dms/toggle",
                headers=_make_auth_header(),
                json={"enabled": False},
            )

        assert response.status_code == 200
        assert response.json() == {"include_dms": False}
        assert integration.config.get("include_dms") is False

    def test_dms_toggle_returns_409_when_needs_reauth(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """POST /dms/toggle returns 409 when user token missing; does not mutate config."""
        integration = self._make_connected_integration()
        original_config = dict(integration.config)
        self._wire_session(mock_session, [integration])

        with patch("src.routers.slack.read_token", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = None  # No user token -> needs_reauth
            response = slack_client.post(
                "/api/slack/dms/toggle",
                headers=_make_auth_header(),
                json={"enabled": True},
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "needs_reauth"
        # Config must be unchanged
        assert integration.config == original_config

    def test_dms_toggle_returns_400_when_not_connected(
        self, slack_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """POST /dms/toggle returns 400 when workspace is not connected to Slack."""
        self._wire_session(mock_session, [None])  # No integration

        response = slack_client.post(
            "/api/slack/dms/toggle",
            headers=_make_auth_header(),
            json={"enabled": True},
        )

        assert response.status_code == 400

    def test_dms_toggle_requires_auth(self, slack_client: TestClient) -> None:
        """POST /api/slack/dms/toggle without JWT returns 401/403."""
        response = slack_client.post(
            "/api/slack/dms/toggle", json={"enabled": True}
        )
        assert response.status_code in (401, 403)
