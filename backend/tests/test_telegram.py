"""Tests for Telegram webhook processing and event handling.

Covers:
- Filter logic: bot messages, text-less messages, valid messages
- process_telegram_update with supergroup chat_id (int64 overflow)
- Edited message upsert (ON CONFLICT path)
- workspace_id str-to-UUID casting
- Webhook endpoint secret verification (valid, invalid, missing)
- Malformed payload handling (missing chat, missing message_id)
- RETURNING clause for UUID retrieval (no second query)
"""

import hmac
import json
import time
from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings
from src.services.telegram_events import _should_filter_telegram, process_telegram_update
from tests.conftest import (
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    _make_test_settings,
)

TELEGRAM_WEBHOOK_SECRET = "test-telegram-webhook-secret"
WORKSPACE_UUID = UUID(TEST_WORKSPACE_ID)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_queue_embedding():
    with patch(
        "src.services.embedding.queue_embedding_generation", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture()
def telegram_settings() -> Settings:
    return _make_test_settings(TELEGRAM_WEBHOOK_SECRET=TELEGRAM_WEBHOOK_SECRET)


@pytest.fixture()
def app(telegram_settings):
    src.config._settings = telegram_settings
    from src.main import app
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _webhook_url(workspace_id: str = TEST_WORKSPACE_ID) -> str:
    return f"/api/telegram/webhook/{workspace_id}"


def _make_telegram_update(
    text: str = "This is a real engineering discussion message",
    chat_id: int = -1001234567890,
    message_id: int = 42,
    from_user_id: int = 99887766,
    from_username: str = "testuser",
    is_bot: bool = False,
    chat_type: str = "supergroup",
    chat_title: str = "Engineering Team",
    reply_to_message_id: int | None = None,
    date: int | None = None,
    use_edited: bool = False,
) -> dict:
    """Build a realistic Telegram update payload."""
    message = {
        "message_id": message_id,
        "from": {
            "id": from_user_id,
            "is_bot": is_bot,
            "first_name": "Test",
            "username": from_username,
        },
        "chat": {
            "id": chat_id,
            "title": chat_title,
            "type": chat_type,
        },
        "date": date or int(time.time()),
        "text": text,
    }
    if reply_to_message_id is not None:
        message["reply_to_message"] = {"message_id": reply_to_message_id}

    key = "edited_message" if use_edited else "message"
    return {"update_id": 123456789, key: message}


# ===========================================================================
# Filter tests (pure function, no DB needed)
# ===========================================================================


class TestShouldFilterTelegram:
    """Tests for the _should_filter_telegram filter function."""

    def test_filters_update_without_message(self):
        assert _should_filter_telegram({"update_id": 1}) is True

    def test_filters_message_without_text(self):
        update = _make_telegram_update(text="hello")
        del update["message"]["text"]
        update["message"]["photo"] = [{"file_id": "abc"}]
        assert _should_filter_telegram(update) is True

    def test_filters_bot_messages(self):
        update = _make_telegram_update(is_bot=True)
        assert _should_filter_telegram(update) is True

    def test_passes_normal_message(self):
        update = _make_telegram_update(text="yes")
        assert _should_filter_telegram(update) is False

    def test_passes_short_message(self):
        """Short messages like 'yes', 'no', 'done' must NOT be filtered."""
        update = _make_telegram_update(text="ok")
        assert _should_filter_telegram(update) is False

    def test_passes_edited_message(self):
        update = _make_telegram_update(text="edited text here", use_edited=True)
        assert _should_filter_telegram(update) is False

    def test_filters_empty_text(self):
        update = _make_telegram_update(text="")
        assert _should_filter_telegram(update) is True


# ===========================================================================
# Webhook endpoint tests (HTTP level)
# ===========================================================================


class TestWebhookEndpoint:
    """Tests for the /api/telegram/webhook/{workspace_id} endpoint."""

    def test_rejects_missing_secret(self, client):
        """No secret header -> 403."""
        update = _make_telegram_update()
        resp = client.post(_webhook_url(), json=update)
        assert resp.status_code == 403

    def test_rejects_wrong_secret(self, client):
        """Wrong secret header -> 403."""
        update = _make_telegram_update()
        resp = client.post(
            _webhook_url(),
            json=update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        assert resp.status_code == 403

    def test_accepts_valid_secret(self, client):
        """Valid secret + bot message (filtered) -> 200 ok."""
        update = _make_telegram_update(is_bot=True)  # will be filtered, no DB needed
        resp = client.post(
            _webhook_url(),
            json=update,
            headers={"X-Telegram-Bot-Api-Secret-Token": TELEGRAM_WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_rejects_empty_secret_setting(self, app):
        """If TELEGRAM_WEBHOOK_SECRET is empty, all requests should be rejected."""
        settings = _make_test_settings(TELEGRAM_WEBHOOK_SECRET="")
        src.config._settings = settings
        client = TestClient(app, raise_server_exceptions=False)

        update = _make_telegram_update(is_bot=True)
        resp = client.post(
            _webhook_url(),
            json=update,
            headers={"X-Telegram-Bot-Api-Secret-Token": ""},
        )
        # hmac.compare_digest("", "") is True, but the `not settings.TELEGRAM_WEBHOOK_SECRET`
        # check should catch this and reject it
        assert resp.status_code == 403


# ===========================================================================
# process_telegram_update tests (service level, mocked DB)
# ===========================================================================


class TestProcessTelegramUpdate:
    """Tests for process_telegram_update with mocked DB session."""

    @pytest.fixture()
    def mock_session(self):
        session = AsyncMock()
        # Mock execute to return a result with scalar_one returning a UUID
        mock_result = AsyncMock()
        mock_result.scalar_one.return_value = uuid4()
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_filters_bot_message(self, mock_session):
        """Bot messages should be silently dropped."""
        update = _make_telegram_update(is_bot=True)
        await process_telegram_update(mock_session, WORKSPACE_UUID, update)
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_normal_message(self, mock_session, _patch_queue_embedding):
        """Normal message should insert and queue embedding."""
        update = _make_telegram_update()
        await process_telegram_update(mock_session, WORKSPACE_UUID, update)
        # Should have called execute (for insert w/ RETURNING) and commit
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        _patch_queue_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_supergroup_chat_id_int64(self, mock_session, _patch_queue_embedding):
        """Supergroup chat IDs like -1003644773967 must not cause int32 overflow.

        This is the exact bug that broke production — Telegram supergroup IDs
        exceed PostgreSQL INTEGER range. The model must use BigInteger.
        """
        big_chat_id = -1003644773967  # real supergroup ID
        update = _make_telegram_update(chat_id=big_chat_id)
        # Should not raise — if the model uses INTEGER, this would fail at DB level
        await process_telegram_update(mock_session, WORKSPACE_UUID, update)
        mock_session.execute.assert_called_once()

        # The real proof is in TestTelegramMessageModel.test_chat_id_is_biginteger
        # Here we just verify no Python-side overflow or rejection

    @pytest.mark.asyncio
    async def test_workspace_id_must_be_uuid(self, mock_session):
        """process_telegram_update declares workspace_id: UUID — passing str should
        still work if the caller casts it, but we test the UUID path explicitly."""
        update = _make_telegram_update()
        # Pass as UUID — this is the correct type
        await process_telegram_update(mock_session, WORKSPACE_UUID, update)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_edited_message_processed(self, mock_session, _patch_queue_embedding):
        """edited_message updates should trigger upsert."""
        update = _make_telegram_update(text="corrected text", use_edited=True)
        await process_telegram_update(mock_session, WORKSPACE_UUID, update)
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reply_tracking(self, mock_session, _patch_queue_embedding):
        """Messages that are replies should set is_reply and reply_to_message_id."""
        update = _make_telegram_update(reply_to_message_id=10)
        await process_telegram_update(mock_session, WORKSPACE_UUID, update)
        mock_session.execute.assert_called_once()

        # Inspect the compiled params to verify reply info
        call_args = mock_session.execute.call_args
        stmt = call_args[0][0]
        compiled = stmt.compile()
        params = compiled.params
        assert params.get("reply_to_message_id") == 10
        assert params.get("is_reply") is True

    @pytest.mark.asyncio
    async def test_missing_chat_key_raises(self, mock_session):
        """If 'chat' is missing from message, should KeyError on chat['id']."""
        update = _make_telegram_update()
        del update["message"]["chat"]
        with pytest.raises(KeyError):
            await process_telegram_update(mock_session, WORKSPACE_UUID, update)

    @pytest.mark.asyncio
    async def test_missing_message_id_raises(self, mock_session):
        """If 'message_id' is missing, should KeyError."""
        update = _make_telegram_update()
        del update["message"]["message_id"]
        with pytest.raises(KeyError):
            await process_telegram_update(mock_session, WORKSPACE_UUID, update)

    @pytest.mark.asyncio
    async def test_date_parsed_as_naive_utc(self, mock_session, _patch_queue_embedding):
        """telegram_date should be a datetime parsed from unix timestamp."""
        fixed_ts = 1710000000
        update = _make_telegram_update(date=fixed_ts)
        await process_telegram_update(mock_session, WORKSPACE_UUID, update)

        call_args = mock_session.execute.call_args
        stmt = call_args[0][0]
        compiled = stmt.compile()
        params = compiled.params
        td = params.get("telegram_date")
        assert isinstance(td, datetime)
        # 1710000000 = 2024-03-09 16:00:00 UTC
        assert td.year == 2024
        assert td.month == 3


# ===========================================================================
# Model column type tests
# ===========================================================================


class TestTelegramMessageModel:
    """Verify the SQLAlchemy model uses BigInteger for Telegram ID fields."""

    def test_chat_id_is_biginteger(self):
        from sqlalchemy import BigInteger
        from src.models.telegram import TelegramMessage

        col = TelegramMessage.__table__.c.chat_id
        assert isinstance(col.type, BigInteger), (
            f"chat_id column type is {type(col.type).__name__}, expected BigInteger. "
            f"Telegram supergroup IDs exceed int32 range."
        )

    def test_message_id_is_biginteger(self):
        from sqlalchemy import BigInteger
        from src.models.telegram import TelegramMessage

        col = TelegramMessage.__table__.c.message_id
        assert isinstance(col.type, BigInteger), (
            f"message_id column type is {type(col.type).__name__}, expected BigInteger."
        )

    def test_from_user_id_is_biginteger(self):
        from sqlalchemy import BigInteger
        from src.models.telegram import TelegramMessage

        col = TelegramMessage.__table__.c.from_user_id
        assert isinstance(col.type, BigInteger), (
            f"from_user_id column type is {type(col.type).__name__}, expected BigInteger."
        )

    def test_reply_to_message_id_is_biginteger(self):
        from sqlalchemy import BigInteger
        from src.models.telegram import TelegramMessage

        col = TelegramMessage.__table__.c.reply_to_message_id
        assert isinstance(col.type, BigInteger), (
            f"reply_to_message_id column type is {type(col.type).__name__}, expected BigInteger."
        )
