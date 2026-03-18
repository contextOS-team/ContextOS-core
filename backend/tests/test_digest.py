"""Integration tests for the daily message digest pipeline.

Tests the full generate_digest flow: message fetching, LLM summarization
(mocked), activity event emission, and deduplication. Uses the real local
database for message and activity_events queries.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import src.config
from src.db import async_session, engine
from src.services.digest import (
    MAX_MESSAGE_LENGTH,
    _has_recent_digest,
    _sanitize_message_text,
    generate_digest,
)

# Stable test workspace ID
WS_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _ensure_db_config():
    """Override the autouse _reset_settings to preserve real DB config."""
    src.config._settings = None
    src.config.get_settings()
    yield
    src.config._settings = None


async def _setup_workspace():
    """Ensure the test workspace exists."""
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO workspaces (id, name, slug) "
                "VALUES (:ws, 'digest-test', 'digest-test-ws') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"ws": WS_ID},
        )
        await session.commit()


async def _cleanup():
    """Remove all test data and dispose engine pool for event loop hygiene."""
    async with async_session() as session:
        await session.execute(
            text("DELETE FROM activity_events WHERE workspace_id = :ws"),
            {"ws": WS_ID},
        )
        await session.execute(
            text("DELETE FROM telegram_messages WHERE workspace_id = :ws"),
            {"ws": WS_ID},
        )
        await session.commit()
    await engine.dispose()


async def _insert_telegram_messages(
    session: AsyncSession,
    count: int,
    chat_title: str = "test-chat",
    chat_id: int = 12345,
    minutes_ago_start: int = 60,
) -> None:
    """Insert test Telegram messages."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(count):
        msg_time = now - timedelta(minutes=minutes_ago_start - i)
        await session.execute(
            text(
                "INSERT INTO telegram_messages "
                "(id, workspace_id, message_id, chat_id, chat_title, "
                "chat_type, from_first_name, text, created_at) "
                "VALUES (:id, :ws, :msg_id, :chat_id, :chat_title, "
                "'group', :name, :text, :created_at)"
            ),
            {
                "id": uuid.uuid4(),
                "ws": WS_ID,
                "msg_id": 1000 + i,
                "chat_id": chat_id,
                "chat_title": chat_title,
                "name": f"User{i % 3}",
                "text": f"Test message {i}: discussing feature implementation",
                "created_at": msg_time,
            },
        )
    await session.commit()


# ============================================================
# Unit tests (no DB)
# ============================================================


class TestSanitizeMessageText:
    def test_strips_null_bytes(self):
        assert _sanitize_message_text("hello\x00world") == "helloworld"

    def test_keeps_newlines_and_tabs(self):
        assert _sanitize_message_text("line1\nline2\ttab") == "line1\nline2\ttab"

    def test_caps_at_max_length(self):
        long_text = "x" * (MAX_MESSAGE_LENGTH + 100)
        assert len(_sanitize_message_text(long_text)) == MAX_MESSAGE_LENGTH

    def test_empty_string(self):
        assert _sanitize_message_text("") == ""


# ============================================================
# Integration tests (real DB, mocked LLM)
# ============================================================


async def test_no_messages_returns_none():
    """No messages in DB → returns None, LLM never called."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            with patch("src.services.digest.get_llm_client") as mock_llm:
                result = await generate_digest(
                    session, WS_ID, "telegram", skip_dedup=True,
                )
        assert result is None
        mock_llm.assert_not_called()
    finally:
        await _cleanup()


async def test_emits_event_with_summary():
    """Messages exist → LLM called → activity event created with summary."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=5, chat_title="engineering")

            mock_response = AsyncMock()
            mock_response.text = "- Team discussed feature implementation\n- No blockers"
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                result = await generate_digest(
                    session, WS_ID, "telegram", skip_dedup=True,
                )
                await session.commit()

            assert result is not None
            assert result["integration"] == "telegram"
            assert result["message_count"] == 5
            assert result["channels_active"] == 1
            assert result["top_channels"] == ["engineering"]
            assert result["summary"] == "- Team discussed feature implementation\n- No blockers"

            # Verify the activity event was actually inserted
            row = await session.execute(
                text(
                    "SELECT metadata FROM activity_events "
                    "WHERE workspace_id = :ws AND event_type = 'messages_digest' "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"ws": WS_ID},
            )
            event = row.scalar_one()
            assert event["summary"] == "- Team discussed feature implementation\n- No blockers"
            assert event["message_count"] == 5
    finally:
        await _cleanup()


async def test_llm_failure_omits_summary():
    """LLM throws → event emitted without summary field, not with fake fallback."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=3, chat_title="general")

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=RuntimeError("API down"))

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                result = await generate_digest(
                    session, WS_ID, "telegram", skip_dedup=True,
                )
                await session.commit()

            assert result is not None
            assert result["message_count"] == 3
            assert "summary" not in result
    finally:
        await _cleanup()


async def test_deduplication_prevents_second_digest():
    """Second call within cooldown returns None."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=3, chat_title="team")

            mock_response = AsyncMock()
            mock_response.text = "- Summary"
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                result1 = await generate_digest(session, WS_ID, "telegram")
                await session.commit()
                assert result1 is not None

                result2 = await generate_digest(session, WS_ID, "telegram")
                assert result2 is None

            # LLM called exactly once
            assert mock_client.generate.call_count == 1
    finally:
        await _cleanup()


async def test_skip_dedup_forces_generation():
    """skip_dedup=True bypasses the cooldown check."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=2, chat_title="team")

            mock_response = AsyncMock()
            mock_response.text = "- Summary"
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                r1 = await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()
                r2 = await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            assert r1 is not None
            assert r2 is not None
            assert mock_client.generate.call_count == 2
    finally:
        await _cleanup()


async def test_multiple_channels_tracked():
    """Messages from multiple chats are counted separately."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=5, chat_title="frontend", chat_id=111)
            await _insert_telegram_messages(session, count=3, chat_title="backend", chat_id=222)

            mock_response = AsyncMock()
            mock_response.text = "- Summary"
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                result = await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            assert result is not None
            assert result["message_count"] == 8
            assert result["channels_active"] == 2
            assert result["top_channels"][0] == "frontend"
    finally:
        await _cleanup()


async def test_old_messages_excluded():
    """Messages older than the hours window are not included."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(
                session, count=5, chat_title="old-chat",
                minutes_ago_start=48 * 60,
            )

            with patch("src.services.digest.get_llm_client") as mock_llm:
                result = await generate_digest(
                    session, WS_ID, "telegram", hours=24, skip_dedup=True,
                )

            assert result is None
            mock_llm.assert_not_called()
    finally:
        await _cleanup()


async def test_dedup_does_not_cross_integrations():
    """A telegram digest does not block a slack digest."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            # Insert a telegram digest
            await session.execute(
                text(
                    "INSERT INTO activity_events (workspace_id, event_type, metadata) "
                    "VALUES (:ws, 'messages_digest', CAST(:meta AS jsonb))"
                ),
                {"ws": WS_ID, "meta": json.dumps({"integration": "telegram"})},
            )
            await session.commit()

            # Slack should not be blocked
            is_blocked = await _has_recent_digest(session, WS_ID, "slack")
            assert is_blocked is False
    finally:
        await _cleanup()


async def test_prompt_contains_message_content():
    """Verify the LLM prompt includes actual message text."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=2, chat_title="verify-channel")

            mock_response = AsyncMock()
            mock_response.text = "- Summary"
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            call_args = mock_client.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            assert "verify-channel" in prompt
            assert "Test message" in prompt
            assert "discussing feature implementation" in prompt
    finally:
        await _cleanup()


async def test_unknown_integration_returns_none():
    async with async_session() as session:
        result = await generate_digest(session, WS_ID, "whatsapp", skip_dedup=True)
    assert result is None
