"""Integration tests for the daily message digest pipeline.

Tests the full generate_digest flow: message fetching, structured LLM
extraction (mocked), graph wiring, activity event emission, and dedup.
Uses the real local database for message and activity_events queries.
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
    DIGEST_COOLDOWN_HOURS,
    MAX_MESSAGE_LENGTH,
    DigestExtraction,
    ExtractedActionItem,
    ExtractedDecision,
    ExtractedTopic,
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
    async with async_session() as session:
        await session.execute(
            text("DELETE FROM activity_events WHERE workspace_id = :ws"),
            {"ws": WS_ID},
        )
        await session.execute(
            text("DELETE FROM telegram_messages WHERE workspace_id = :ws"),
            {"ws": WS_ID},
        )
        await session.execute(
            text("DELETE FROM graph_edges WHERE workspace_id = :ws"),
            {"ws": WS_ID},
        )
        await session.execute(
            text("DELETE FROM graph_nodes WHERE workspace_id = :ws"),
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


def _mock_extraction(**overrides) -> DigestExtraction:
    """Build a DigestExtraction with sensible defaults."""
    defaults = {
        "summary": "- Team discussed feature implementation\n- No blockers",
        "decisions": [],
        "action_items": [],
        "topics": [],
    }
    defaults.update(overrides)
    return DigestExtraction(**defaults)


def _make_mock_llm(extraction: DigestExtraction | None = None, fail: bool = False):
    """Create a mock LLM client that returns a DigestExtraction from generate_json."""
    mock_client = AsyncMock()
    if fail:
        mock_client.generate_json = AsyncMock(side_effect=RuntimeError("API down"))
    else:
        mock_client.generate_json = AsyncMock(return_value=extraction or _mock_extraction())
    return mock_client


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
    """Messages exist → LLM called → event with summary and structured data."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=5, chat_title="engineering")

            extraction = _mock_extraction(
                decisions=[
                    ExtractedDecision(
                        title="Use Pydantic for validation",
                        rationale="Type safety and schema enforcement",
                        participants=["Alice", "Bob"],
                    )
                ],
                action_items=[
                    ExtractedActionItem(description="Write migration", assignee="Alice")
                ],
                topics=[
                    ExtractedTopic(title="Schema design", ticket_refs=["ENG-123"])
                ],
            )
            mock_client = _make_mock_llm(extraction)

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
            assert "summary" in result
            assert len(result["decisions"]) == 1
            assert result["decisions"][0]["title"] == "Use Pydantic for validation"
            assert result["action_items"][0]["assignee"] == "Alice"
            assert result["topics"][0]["ticket_refs"] == ["ENG-123"]

            # Verify event in DB
            row = await session.execute(
                text(
                    "SELECT metadata FROM activity_events "
                    "WHERE workspace_id = :ws AND event_type = 'messages_digest' "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"ws": WS_ID},
            )
            event = row.scalar_one()
            assert event["message_count"] == 5
            assert len(event["decisions"]) == 1
    finally:
        await _cleanup()


async def test_llm_failure_omits_summary():
    """LLM throws → event emitted without summary or structured fields."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=3, chat_title="general")

            mock_client = _make_mock_llm(fail=True)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                result = await generate_digest(
                    session, WS_ID, "telegram", skip_dedup=True,
                )
                await session.commit()

            assert result is not None
            assert result["message_count"] == 3
            assert "summary" not in result
            assert "decisions" not in result
    finally:
        await _cleanup()


async def test_deduplication_prevents_second_digest():
    """Second call within cooldown returns None."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=3, chat_title="team")

            mock_client = _make_mock_llm()

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                result1 = await generate_digest(session, WS_ID, "telegram")
                await session.commit()
                assert result1 is not None

                result2 = await generate_digest(session, WS_ID, "telegram")
                assert result2 is None

            assert mock_client.generate_json.call_count == 1
    finally:
        await _cleanup()


async def test_skip_dedup_forces_generation():
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=2, chat_title="team")

            mock_client = _make_mock_llm()

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                r1 = await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()
                r2 = await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            assert r1 is not None
            assert r2 is not None
            assert mock_client.generate_json.call_count == 2
    finally:
        await _cleanup()


async def test_multiple_channels_tracked():
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=5, chat_title="frontend", chat_id=111)
            await _insert_telegram_messages(session, count=3, chat_title="backend", chat_id=222)

            mock_client = _make_mock_llm()

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
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await session.execute(
                text(
                    "INSERT INTO activity_events (workspace_id, event_type, metadata) "
                    "VALUES (:ws, 'messages_digest', CAST(:meta AS jsonb))"
                ),
                {"ws": WS_ID, "meta": json.dumps({"integration": "telegram"})},
            )
            await session.commit()

            is_blocked = await _has_recent_digest(session, WS_ID, "slack")
            assert is_blocked is False
    finally:
        await _cleanup()


async def test_prompt_contains_message_content():
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=2, chat_title="verify-channel")

            mock_client = _make_mock_llm()

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            call_args = mock_client.generate_json.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            assert "verify-channel" in prompt
            assert "Test message" in prompt
    finally:
        await _cleanup()


async def _insert_person_node(session, name: str) -> str:
    """Insert a Person graph node and return its ID as string."""
    import hashlib
    fp = hashlib.sha256(f"Person:{name}".encode()).hexdigest()
    r = await session.execute(
        text(
            "INSERT INTO graph_nodes (id, workspace_id, entity_type, name, fingerprint, properties) "
            "VALUES (gen_random_uuid(), :ws, 'Person', :name, :fp, '{}') "
            "ON CONFLICT (workspace_id, fingerprint) WHERE deleted_at IS NULL "
            "DO UPDATE SET name = :name "
            "RETURNING id"
        ),
        {"ws": WS_ID, "name": name, "fp": fp},
    )
    node_id = r.scalar_one()
    await session.commit()
    return str(node_id)


async def test_graph_decision_node_with_person_edge():
    """Decision with a matching participant creates a decided_in edge."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            # Create a Person node that the LLM participant name will match
            person_id = await _insert_person_node(session, "Alice Smith")
            await _insert_telegram_messages(session, count=3, chat_title="team")

            extraction = _mock_extraction(
                decisions=[
                    ExtractedDecision(
                        title="Adopt microservices",
                        rationale="Scalability needs",
                        participants=["Alice"],  # Should match "Alice Smith" by first name
                    ),
                ],
            )
            mock_client = _make_mock_llm(extraction)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            # Verify Decision node
            node_row = await session.execute(
                text(
                    "SELECT id, name, properties FROM graph_nodes "
                    "WHERE workspace_id = :ws AND entity_type = 'Decision'"
                ),
                {"ws": WS_ID},
            )
            decision = node_row.first()
            assert decision is not None
            assert decision.name == "Adopt microservices"
            assert decision.properties["rationale"] == "Scalability needs"

            # Verify decided_in edge exists
            edge_row = await session.execute(
                text(
                    "SELECT source_node_id, target_node_id, relationship_type "
                    "FROM graph_edges "
                    "WHERE workspace_id = :ws AND relationship_type = 'decided_in'"
                ),
                {"ws": WS_ID},
            )
            edge = edge_row.first()
            assert edge is not None
            assert str(edge.source_node_id) == person_id
            assert str(edge.target_node_id) == str(decision.id)
    finally:
        await _cleanup()


async def test_graph_ambiguous_name_skips_edge():
    """When two Person nodes share a first name, no decided_in edge is created."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_person_node(session, "Alice Smith")
            await _insert_person_node(session, "Alice Chen")
            await _insert_telegram_messages(session, count=2, chat_title="team")

            extraction = _mock_extraction(
                decisions=[
                    ExtractedDecision(
                        title="Use Redis",
                        rationale="Speed",
                        participants=["Alice"],  # Ambiguous — two Alices
                    ),
                ],
            )
            mock_client = _make_mock_llm(extraction)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            # Decision node should exist
            node_row = await session.execute(
                text(
                    "SELECT count(*) FROM graph_nodes "
                    "WHERE workspace_id = :ws AND entity_type = 'Decision'"
                ),
                {"ws": WS_ID},
            )
            assert node_row.scalar_one() == 1

            # But NO decided_in edge (ambiguous match skipped)
            edge_row = await session.execute(
                text(
                    "SELECT count(*) FROM graph_edges "
                    "WHERE workspace_id = :ws AND relationship_type = 'decided_in'"
                ),
                {"ws": WS_ID},
            )
            assert edge_row.scalar_one() == 0
    finally:
        await _cleanup()


async def test_graph_ticket_nodes_from_topics_no_decision_edges():
    """Ticket refs create nodes but do NOT get cross-linked to decisions."""
    await _setup_workspace()
    await _cleanup()
    try:
        async with async_session() as session:
            await _insert_telegram_messages(session, count=2, chat_title="eng")

            extraction = _mock_extraction(
                decisions=[
                    ExtractedDecision(title="Use Postgres", rationale="Reliability", participants=[]),
                ],
                topics=[
                    ExtractedTopic(title="Sprint planning", ticket_refs=["ENG-123", "CON-45"]),
                ],
            )
            mock_client = _make_mock_llm(extraction)

            with patch("src.services.digest.get_llm_client", return_value=mock_client):
                await generate_digest(session, WS_ID, "telegram", skip_dedup=True)
                await session.commit()

            # 2 Ticket nodes created
            ticket_count = await session.execute(
                text(
                    "SELECT count(*) FROM graph_nodes "
                    "WHERE workspace_id = :ws AND entity_type = 'Ticket'"
                ),
                {"ws": WS_ID},
            )
            assert ticket_count.scalar_one() == 2

            # Zero references edges (no cartesian product)
            edge_count = await session.execute(
                text(
                    "SELECT count(*) FROM graph_edges "
                    "WHERE workspace_id = :ws AND relationship_type = 'references'"
                ),
                {"ws": WS_ID},
            )
            assert edge_count.scalar_one() == 0
    finally:
        await _cleanup()


async def test_unknown_integration_returns_none():
    async with async_session() as session:
        result = await generate_digest(session, WS_ID, "whatsapp", skip_dedup=True)
    assert result is None
