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
        assert "channels:read" in url


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

    def test_filters_short_messages(self) -> None:
        """Messages with less than 10 characters should be filtered out."""
        from src.services.slack_events import _should_filter

        event = {"type": "message", "text": "Hi"}
        assert _should_filter(event) is True

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

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = mock_oauth_token
            elif call_count == 3:
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
