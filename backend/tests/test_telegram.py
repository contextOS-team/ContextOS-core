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


# ===========================================================================
# Phase 40: Telegram Shared-Bot model tests
# ===========================================================================


class TestTelegramChatWorkspaceModel:
    """Phase 40: Verify TelegramChatWorkspace model shape (chat_id BIGINT PK)."""

    def test_imports_alongside_telegram_message(self):
        # Both classes must coexist without SQLAlchemy mapper conflicts.
        from src.models.telegram import (  # noqa: F401
            TelegramChatWorkspace,
            TelegramMessage,
            TelegramPairingCode,
        )

    def test_chat_id_is_biginteger_pk(self):
        from sqlalchemy import BigInteger
        from src.models.telegram import TelegramChatWorkspace

        col = TelegramChatWorkspace.__table__.c.chat_id
        assert isinstance(col.type, BigInteger), (
            f"chat_id column type is {type(col.type).__name__}, expected BigInteger. "
            "Telegram supergroup IDs exceed int32 range."
        )
        assert col.primary_key is True, "chat_id must be PRIMARY KEY for sticky first-claim-wins"

    def test_workspace_id_is_uuid_not_null(self):
        from src.models.telegram import TelegramChatWorkspace

        col = TelegramChatWorkspace.__table__.c.workspace_id
        assert col.nullable is False, "workspace_id must be NOT NULL"

    def test_table_name(self):
        from src.models.telegram import TelegramChatWorkspace

        assert TelegramChatWorkspace.__tablename__ == "telegram_chat_workspace"

    def test_has_paired_at_paired_by_removed_at_columns(self):
        from src.models.telegram import TelegramChatWorkspace

        cols = TelegramChatWorkspace.__table__.c
        assert "paired_at" in cols
        assert "paired_by" in cols
        assert "removed_at" in cols
        assert "chat_title" in cols
        assert "chat_type" in cols


class TestTelegramPairingCodeModel:
    """Phase 40: Verify TelegramPairingCode model shape (code TEXT PK)."""

    def test_code_is_text_pk(self):
        from src.models.telegram import TelegramPairingCode

        col = TelegramPairingCode.__table__.c.code
        assert col.primary_key is True, "code must be PRIMARY KEY"

    def test_table_name(self):
        from src.models.telegram import TelegramPairingCode

        assert TelegramPairingCode.__tablename__ == "telegram_pairing_codes"

    def test_workspace_id_not_null(self):
        from src.models.telegram import TelegramPairingCode

        col = TelegramPairingCode.__table__.c.workspace_id
        assert col.nullable is False, "workspace_id must be NOT NULL"

    def test_expires_at_not_null(self):
        from src.models.telegram import TelegramPairingCode

        col = TelegramPairingCode.__table__.c.expires_at
        assert col.nullable is False, "expires_at must be NOT NULL for TTL semantics"


class TestPhase40Migration:
    """Phase 40: Verify migration 00039 file exists and contains the expected DDL."""

    def test_migration_file_exists(self):
        from pathlib import Path

        path = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase"
            / "migrations"
            / "00039_telegram_shared_bot.sql"
        )
        assert path.exists(), f"Expected migration at {path}"

    def test_migration_creates_both_tables(self):
        from pathlib import Path

        path = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase"
            / "migrations"
            / "00039_telegram_shared_bot.sql"
        )
        text = path.read_text()
        assert "CREATE TABLE IF NOT EXISTS public.telegram_chat_workspace" in text
        assert "CREATE TABLE IF NOT EXISTS public.telegram_pairing_codes" in text

    def test_migration_uses_bigint_chat_id(self):
        from pathlib import Path

        path = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase"
            / "migrations"
            / "00039_telegram_shared_bot.sql"
        )
        text = path.read_text()
        # chat_id must be BIGINT PRIMARY KEY (Pitfall 9 — supergroups overflow INT32)
        assert "chat_id      BIGINT PRIMARY KEY" in text or "chat_id BIGINT PRIMARY KEY" in text

    def test_migration_enables_rls_with_workspace_member_select(self):
        from pathlib import Path

        path = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase"
            / "migrations"
            / "00039_telegram_shared_bot.sql"
        )
        text = path.read_text()
        assert "ALTER TABLE public.telegram_chat_workspace ENABLE ROW LEVEL SECURITY" in text
        assert "ALTER TABLE public.telegram_pairing_codes ENABLE ROW LEVEL SECURITY" in text
        # workspace_member_select policy mirrors 00030_telegram_messages.sql
        assert text.count('CREATE POLICY "workspace_member_select"') >= 2

    def test_migration_purges_legacy_telegram_oauth_rows(self):
        from pathlib import Path

        path = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase"
            / "migrations"
            / "00039_telegram_shared_bot.sql"
        )
        text = path.read_text()
        assert "DELETE FROM public.oauth_tokens WHERE provider = 'telegram'" in text
        assert "DELETE FROM public.workspace_integrations WHERE provider = 'telegram'" in text


# ===========================================================================
# Phase 40: POST /api/telegram/pairing-code endpoint
# ===========================================================================


def _make_auth_header() -> dict[str, str]:
    """Build a valid JWT bearer header for the test user."""
    import jwt as pyjwt
    from tests.conftest import TEST_EMAIL, TEST_JWT_SECRET

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


@pytest.fixture()
def phase40_app(telegram_settings):
    """App fixture with /pairing-code endpoint dependencies overridden.

    Overrides get_current_user (so we don't need a real workspace_member row)
    and get_session (so the route handler gets an AsyncMock).
    """
    from src.db import get_session as get_session_dep
    from src.dependencies import UserContext, get_current_user
    from src.main import app as fastapi_app

    src.config._settings = telegram_settings
    mock_session = AsyncMock()

    async def _mock_get_session():
        yield mock_session

    async def _mock_get_current_user():
        return UserContext(
            user_id=UUID(TEST_USER_ID),
            email="test@example.com",
            workspace_id=UUID(TEST_WORKSPACE_ID),
        )

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session
    fastapi_app.dependency_overrides[get_current_user] = _mock_get_current_user
    yield fastapi_app, mock_session
    fastapi_app.dependency_overrides.clear()


class TestPairingCodeEndpoint:
    """POST /api/telegram/pairing-code (authenticated)."""

    def test_returns_401_without_jwt(self, client):
        resp = client.post("/api/telegram/pairing-code")
        assert resp.status_code in (401, 403)  # FastAPI HTTPBearer returns 403 when no header

    def test_returns_code_deep_link_expires_at(self, phase40_app):
        from datetime import datetime, timezone

        app, _ = phase40_app
        client = TestClient(app, raise_server_exceptions=False)
        fixed_expires = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with patch(
            "src.routers.telegram.generate_pairing_code", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = {
                "code": "abcdef0123456789",
                "deep_link": "https://t.me/ContextOSBot?startgroup=abcdef0123456789",
                "expires_at": fixed_expires,
            }
            resp = client.post("/api/telegram/pairing-code", headers=_make_auth_header())

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == "abcdef0123456789"
        assert body["deep_link"].endswith("?startgroup=abcdef0123456789")
        # expires_at must be ISO 8601 string (JSON-serializable)
        assert isinstance(body["expires_at"], str)
        # Round-trip parse confirms ISO 8601
        from datetime import datetime as dt
        dt.fromisoformat(body["expires_at"])

    def test_calls_service_with_user_workspace_and_user_id(self, phase40_app):
        from datetime import datetime, timezone

        app, _ = phase40_app
        client = TestClient(app, raise_server_exceptions=False)
        with patch(
            "src.routers.telegram.generate_pairing_code", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = {
                "code": "x" * 16,
                "deep_link": "https://t.me/ContextOSBot?startgroup=" + "x" * 16,
                "expires_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            }
            resp = client.post("/api/telegram/pairing-code", headers=_make_auth_header())

        assert resp.status_code == 200
        # Inspect the call: workspace_id and user_id come from UserContext
        call = mock_gen.call_args
        # Positional: (session, workspace_id, user_id)
        args = call.args
        assert len(args) >= 3
        assert str(args[1]) == TEST_WORKSPACE_ID
        assert str(args[2]) == TEST_USER_ID


# ===========================================================================
# Phase 40: POST /api/telegram/webhook (global, no path param)
# ===========================================================================


def _global_webhook_url() -> str:
    return "/api/telegram/webhook"


class TestGlobalWebhookEndpoint:
    """Global /api/telegram/webhook (no path param) -- secret check + 200 path."""

    def test_rejects_missing_secret(self, client):
        update = _make_telegram_update()
        resp = client.post(_global_webhook_url(), json=update)
        assert resp.status_code == 403

    def test_rejects_wrong_secret(self, client):
        update = _make_telegram_update()
        resp = client.post(
            _global_webhook_url(),
            json=update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )
        assert resp.status_code == 403

    def test_accepts_valid_secret_returns_ok(self, client):
        """Valid secret -> 200 and {ok: true} immediately, processing in BG."""
        update = _make_telegram_update(is_bot=True)
        with patch(
            "src.routers.telegram.process_telegram_update", new_callable=AsyncMock
        ), patch(
            "src.routers.telegram.claim_chat", new_callable=AsyncMock
        ), patch(
            "src.routers.telegram.handle_my_chat_member", new_callable=AsyncMock
        ), patch(
            "src.routers.telegram.resolve_workspace_for_chat", new_callable=AsyncMock
        ):
            resp = client.post(
                _global_webhook_url(),
                json=update,
                headers={"X-Telegram-Bot-Api-Secret-Token": TELEGRAM_WEBHOOK_SECRET},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


class TestGlobalWebhookDispatcher:
    """Verify dispatcher routing -- pairing path BEFORE ingestion (Pitfall 2)."""

    @pytest.mark.asyncio
    async def test_my_chat_member_routed_to_handler(self):
        """Updates with `my_chat_member` go to handle_my_chat_member ONLY."""
        from src.routers.telegram import _dispatch_global_update

        payload = {
            "update_id": 1,
            "my_chat_member": {
                "chat": {"id": -1001234567890},
                "new_chat_member": {"status": "kicked"},
            },
        }

        with patch(
            "src.routers.telegram.handle_my_chat_member", new_callable=AsyncMock
        ) as mock_handle, patch(
            "src.routers.telegram.claim_chat", new_callable=AsyncMock
        ) as mock_claim, patch(
            "src.routers.telegram.process_telegram_update", new_callable=AsyncMock
        ) as mock_process, patch(
            "src.routers.telegram.async_session"
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await _dispatch_global_update(payload)

        mock_handle.assert_awaited_once()
        mock_claim.assert_not_called()
        mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_command_in_group_routed_to_claim_BEFORE_ingestion(self):
        """CRITICAL: `/start@bot <code>` in a group MUST hit claim_chat and
        MUST NOT reach process_telegram_update (Pitfall 2 -- pairing message
        otherwise gets ingested as content)."""
        from src.routers.telegram import _dispatch_global_update

        payload = {
            "update_id": 1,
            "message": {
                "message_id": 99,
                "from": {"id": 5, "is_bot": False, "first_name": "T"},
                "chat": {"id": -1001234567890, "type": "supergroup", "title": "Eng"},
                "date": int(time.time()),
                "text": "/start@ContextOSBot abc123",
            },
        }

        with patch(
            "src.routers.telegram.claim_chat", new_callable=AsyncMock
        ) as mock_claim, patch(
            "src.routers.telegram.process_telegram_update", new_callable=AsyncMock
        ) as mock_process, patch(
            "src.routers.telegram.handle_my_chat_member", new_callable=AsyncMock
        ) as mock_handle, patch(
            "src.routers.telegram.resolve_workspace_for_chat", new_callable=AsyncMock
        ) as mock_resolve, patch(
            "src.routers.telegram.async_session"
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await _dispatch_global_update(payload)

        mock_claim.assert_awaited_once()
        mock_process.assert_not_called()
        mock_handle.assert_not_called()
        # Pairing path does NOT need workspace resolution
        mock_resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_private_chat_dropped_silently(self):
        """chat.type == 'private' -> drop, no claim, no ingestion."""
        from src.routers.telegram import _dispatch_global_update

        payload = {
            "update_id": 1,
            "message": {
                "message_id": 99,
                "from": {"id": 5, "is_bot": False},
                "chat": {"id": 5, "type": "private", "title": "DM"},
                "date": int(time.time()),
                "text": "hello bot",
            },
        }
        with patch(
            "src.routers.telegram.claim_chat", new_callable=AsyncMock
        ) as mock_claim, patch(
            "src.routers.telegram.process_telegram_update", new_callable=AsyncMock
        ) as mock_process, patch(
            "src.routers.telegram.resolve_workspace_for_chat", new_callable=AsyncMock
        ) as mock_resolve, patch(
            "src.routers.telegram.async_session"
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await _dispatch_global_update(payload)

        mock_claim.assert_not_called()
        mock_process.assert_not_called()
        mock_resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_unmapped_chat_dropped_silently(self):
        """Group message in a chat with no telegram_chat_workspace mapping
        -> log + drop, ingestion is NOT called."""
        from src.routers.telegram import _dispatch_global_update

        payload = {
            "update_id": 1,
            "message": {
                "message_id": 99,
                "from": {"id": 5, "is_bot": False},
                "chat": {"id": -1009999999999, "type": "supergroup", "title": "?"},
                "date": int(time.time()),
                "text": "hello there",
            },
        }
        with patch(
            "src.routers.telegram.resolve_workspace_for_chat",
            new_callable=AsyncMock,
        ) as mock_resolve, patch(
            "src.routers.telegram.process_telegram_update", new_callable=AsyncMock
        ) as mock_process, patch(
            "src.routers.telegram.claim_chat", new_callable=AsyncMock
        ) as mock_claim, patch(
            "src.routers.telegram.async_session"
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resolve.return_value = None
            await _dispatch_global_update(payload)

        mock_resolve.assert_awaited_once()
        mock_process.assert_not_called()
        mock_claim.assert_not_called()

    @pytest.mark.asyncio
    async def test_mapped_chat_routed_to_process_telegram_update(self):
        """Group message in a mapped chat -> process_telegram_update with
        the resolved workspace_id (NOT a path-param workspace)."""
        from src.routers.telegram import _dispatch_global_update

        ws = UUID("33333333-3333-3333-3333-333333333333")
        payload = {
            "update_id": 1,
            "message": {
                "message_id": 99,
                "from": {"id": 5, "is_bot": False, "first_name": "T"},
                "chat": {"id": -1001234567890, "type": "supergroup", "title": "Eng"},
                "date": int(time.time()),
                "text": "real engineering content",
            },
        }
        with patch(
            "src.routers.telegram.resolve_workspace_for_chat",
            new_callable=AsyncMock,
        ) as mock_resolve, patch(
            "src.routers.telegram.process_telegram_update", new_callable=AsyncMock
        ) as mock_process, patch(
            "src.routers.telegram.claim_chat", new_callable=AsyncMock
        ) as mock_claim, patch(
            "src.routers.telegram.async_session"
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resolve.return_value = ws
            await _dispatch_global_update(payload)

        mock_resolve.assert_awaited_once()
        mock_process.assert_awaited_once()
        mock_claim.assert_not_called()
        # Verify the workspace_id arg (process_telegram_update(session, ws, payload))
        call = mock_process.call_args
        assert call.args[1] == ws
        assert call.args[2] == payload

    @pytest.mark.asyncio
    async def test_dispatcher_exception_does_not_crash(self):
        """If something inside the dispatcher raises, it logs and rolls back
        but does NOT bubble up (the webhook itself already returned 200)."""
        from src.routers.telegram import _dispatch_global_update

        payload = {
            "update_id": 1,
            "message": {
                "message_id": 99,
                "from": {"id": 5, "is_bot": False},
                "chat": {"id": -1001234567890, "type": "supergroup"},
                "date": int(time.time()),
                "text": "hi",
            },
        }
        with patch(
            "src.routers.telegram.resolve_workspace_for_chat",
            new_callable=AsyncMock,
        ) as mock_resolve, patch(
            "src.routers.telegram.async_session"
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resolve.side_effect = RuntimeError("DB exploded")
            # Must NOT raise
            await _dispatch_global_update(payload)

    @pytest.mark.asyncio
    async def test_edited_message_in_mapped_chat_routed_to_ingestion(self):
        """edited_message updates also go through the dispatcher."""
        from src.routers.telegram import _dispatch_global_update

        ws = UUID("44444444-4444-4444-4444-444444444444")
        payload = {
            "update_id": 1,
            "edited_message": {
                "message_id": 99,
                "from": {"id": 5, "is_bot": False, "first_name": "T"},
                "chat": {"id": -1001234567890, "type": "supergroup", "title": "Eng"},
                "date": int(time.time()),
                "text": "edited content",
            },
        }
        with patch(
            "src.routers.telegram.resolve_workspace_for_chat",
            new_callable=AsyncMock,
        ) as mock_resolve, patch(
            "src.routers.telegram.process_telegram_update", new_callable=AsyncMock
        ) as mock_process, patch(
            "src.routers.telegram.async_session"
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resolve.return_value = ws
            await _dispatch_global_update(payload)

        mock_process.assert_awaited_once()
