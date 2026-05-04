"""Tests for the Phase 40 Telegram pairing service.

Covers:
- generate_pairing_code: 16-char base64url + dedup + 15-min TTL + deep_link shape
- claim_chat: CLAIMED, NOOP (same workspace), ALREADY_CLAIMED_BY_OTHER, INVALID_CODE,
  IGNORE_PRIVATE; code-burn semantics for each branch
- handle_my_chat_member: soft-delete on left/kicked, INFO log on every event
- resolve_workspace_for_chat: returns ws when active, None when removed_at set
- _send_reply_safe: failure does NOT roll back (Pitfall 6)

These are pure unit tests against an in-memory AsyncMock session that simulates
the SQL behavior we care about (DELETE…RETURNING redemption, ON CONFLICT DO
NOTHING insert). No real DB and no real Telegram API call.
"""

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

import src.config
from src.config import Settings
from src.services.telegram_pairing import (
    ClaimResult,
    claim_chat,
    generate_pairing_code,
    handle_my_chat_member,
    resolve_workspace_for_chat,
)
from src.services.telegram_bot import TelegramError
from tests.conftest import _make_test_settings

WORKSPACE_A = UUID("11111111-1111-1111-1111-111111111111")
WORKSPACE_B = UUID("22222222-2222-2222-2222-222222222222")
USER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture(autouse=True)
def _patch_settings():
    src.config._settings = _make_test_settings(
        TELEGRAM_BOT_TOKEN_GLOBAL="test-bot-token",
        TELEGRAM_BOT_USERNAME="ContextOSBot",
    )
    yield
    src.config._settings = None


@pytest.fixture()
def mock_send_reply():
    """Patch the _send_reply_safe helper so claim_chat tests don't hit network."""
    with patch(
        "src.services.telegram_pairing._send_reply_safe", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture()
def mock_emit_activity():
    """Patch emit_activity at the call site in telegram_pairing module."""
    with patch(
        "src.services.telegram_pairing.emit_activity", new_callable=AsyncMock
    ) as mock:
        yield mock


def _make_session() -> AsyncMock:
    """Build an AsyncMock that mimics AsyncSession.

    Tests configure `session.execute.side_effect` per-test to simulate
    SQL outcomes (peek code row, redeem code row, insert rowcount, etc.).
    """
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    return session


def _make_group_message(
    text: str = "/start@ContextOSBot ABC123",
    chat_id: int = -1001234567890,
    chat_type: str = "supergroup",
    chat_title: str = "Engineering Team",
) -> dict:
    return {
        "message_id": 1,
        "from": {"id": 99887766, "is_bot": False, "first_name": "Tester"},
        "chat": {"id": chat_id, "type": chat_type, "title": chat_title},
        "text": text,
    }


# ===========================================================================
# generate_pairing_code
# ===========================================================================


class TestGeneratePairingCode:
    @pytest.mark.asyncio
    async def test_returns_16_char_base64url_code(self):
        session = _make_session()
        result = await generate_pairing_code(session, WORKSPACE_A, USER_A)
        code = result["code"]
        assert isinstance(code, str)
        assert len(code) == 16, f"Expected 16-char base64url code, got {len(code)}: {code!r}"
        assert re.fullmatch(r"[A-Za-z0-9_-]{16}", code) is not None, (
            f"Code {code!r} does not match base64url alphabet"
        )

    @pytest.mark.asyncio
    async def test_returns_deep_link_with_bot_username(self):
        session = _make_session()
        result = await generate_pairing_code(session, WORKSPACE_A, USER_A)
        code = result["code"]
        assert result["deep_link"] == f"https://t.me/ContextOSBot?startgroup={code}"

    @pytest.mark.asyncio
    async def test_expires_at_is_15_minutes_from_now(self):
        session = _make_session()
        before = datetime.now(timezone.utc)
        result = await generate_pairing_code(session, WORKSPACE_A, USER_A)
        after = datetime.now(timezone.utc)
        # 15 minutes ± a small fudge for clock drift between two `datetime.now`
        delta_low = (result["expires_at"] - before).total_seconds()
        delta_high = (result["expires_at"] - after).total_seconds()
        assert 14 * 60 <= delta_low <= 15 * 60 + 1
        assert 14 * 60 - 1 <= delta_high <= 15 * 60

    @pytest.mark.asyncio
    async def test_deletes_unexpired_codes_for_workspace_before_insert(self):
        """One-active-code-per-workspace invariant (Pitfall 5).

        We assert the DELETE statement runs BEFORE the INSERT (session.add)
        and that the DELETE targets the correct workspace_id.
        """
        session = _make_session()
        call_log: list[str] = []
        session.execute = AsyncMock(side_effect=lambda stmt: call_log.append("execute"))
        session.add = MagicMock(side_effect=lambda obj: call_log.append("add"))

        await generate_pairing_code(session, WORKSPACE_A, USER_A)

        # First a DELETE (execute), THEN an INSERT (session.add).
        assert call_log == ["execute", "add"], (
            f"Expected DELETE-then-INSERT order, got: {call_log}"
        )
        # Inspect the DELETE statement passed to execute
        delete_stmt = session.execute.call_args_list[0][0][0]
        compiled = str(delete_stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "DELETE" in compiled.upper()
        assert "telegram_pairing_codes" in compiled

    @pytest.mark.asyncio
    async def test_commits_transaction(self):
        session = _make_session()
        await generate_pairing_code(session, WORKSPACE_A, USER_A)
        session.commit.assert_awaited_once()


# ===========================================================================
# resolve_workspace_for_chat
# ===========================================================================


class TestResolveWorkspaceForChat:
    @pytest.mark.asyncio
    async def test_returns_workspace_id_when_active(self):
        session = _make_session()
        session.scalar = AsyncMock(return_value=WORKSPACE_A)
        result = await resolve_workspace_for_chat(session, -1001234567890)
        assert result == WORKSPACE_A
        # Verify the SELECT filters on chat_id and removed_at IS NULL
        stmt = session.scalar.call_args[0][0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "telegram_chat_workspace" in compiled
        assert "removed_at IS NULL" in compiled

    @pytest.mark.asyncio
    async def test_returns_none_when_no_mapping(self):
        session = _make_session()
        session.scalar = AsyncMock(return_value=None)
        result = await resolve_workspace_for_chat(session, -1009999999999)
        assert result is None


# ===========================================================================
# claim_chat
# ===========================================================================


class TestClaimChatBranches:
    """Behavior matrix for each ClaimResult branch."""

    @pytest.mark.asyncio
    async def test_private_chat_returns_ignore(self, mock_send_reply, mock_emit_activity):
        session = _make_session()
        message = _make_group_message(chat_type="private")
        result = await claim_chat(session, message)
        assert result == ClaimResult.IGNORE_PRIVATE
        # Should NOT touch the DB
        session.execute.assert_not_called()
        # Should NOT send a reply (we silently drop private DMs)
        mock_send_reply.assert_not_called()
        # Should NOT emit activity
        mock_emit_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_group_chat_returns_ignore(self, mock_send_reply, mock_emit_activity):
        """Channel/private/anything-else is ignored (groups + supergroups only)."""
        session = _make_session()
        message = _make_group_message(chat_type="channel")
        result = await claim_chat(session, message)
        assert result == ClaimResult.IGNORE_PRIVATE
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_or_expired_code_returns_invalid(
        self, mock_send_reply, mock_emit_activity
    ):
        """Code lookup returns no row -> INVALID_CODE; no DB changes; in-chat reply sent."""
        session = _make_session()
        # Peek query returns no row
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=None)
        # resolve_workspace returns None as well
        session.scalar = AsyncMock(return_value=None)
        session.execute = AsyncMock(return_value=peek_result)

        message = _make_group_message(text="/start@ContextOSBot bogus")
        result = await claim_chat(session, message)

        assert result == ClaimResult.INVALID_CODE
        mock_send_reply.assert_awaited_once()
        # No emit, no commit (no changes were made)
        mock_emit_activity.assert_not_called()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_cross_workspace_claim_does_not_burn_code(
        self, mock_send_reply, mock_emit_activity
    ):
        """Code belongs to workspace A; chat is already mapped to workspace B.
        Reply 'already paired'; do NOT delete the code; do NOT modify mapping.
        """
        session = _make_session()

        # Peek code -> belongs to workspace A
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        session.execute = AsyncMock(return_value=peek_result)
        # resolve_workspace_for_chat -> existing chat mapped to workspace B (different)
        session.scalar = AsyncMock(return_value=WORKSPACE_B)

        message = _make_group_message(text="/start@ContextOSBot ABCDEF")
        result = await claim_chat(session, message)

        assert result == ClaimResult.ALREADY_CLAIMED_BY_OTHER
        # Only one execute call (the peek). No DELETE/INSERT.
        assert session.execute.await_count == 1
        # No commit (no changes). Reply sent. Activity NOT emitted.
        session.commit.assert_not_called()
        mock_send_reply.assert_awaited_once()
        mock_emit_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_workspace_re_claim_is_noop(
        self, mock_send_reply, mock_emit_activity
    ):
        """Code's workspace == existing mapping's workspace -> NOOP, no burn, no reply."""
        session = _make_session()
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        session.execute = AsyncMock(return_value=peek_result)
        session.scalar = AsyncMock(return_value=WORKSPACE_A)  # same workspace

        message = _make_group_message(text="/start@ContextOSBot ABCDEF")
        result = await claim_chat(session, message)

        assert result == ClaimResult.NOOP
        # Only the peek. No DELETE, no INSERT.
        assert session.execute.await_count == 1
        session.commit.assert_not_called()
        mock_send_reply.assert_not_called()
        mock_emit_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_fresh_claim_burns_code_inserts_mapping_emits_activity(
        self, mock_send_reply, mock_emit_activity
    ):
        """Code valid, chat unmapped -> CLAIMED with side effects."""
        session = _make_session()
        # First execute: peek code (returns row)
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        # Second execute: redeem (DELETE...RETURNING returns row)
        redeem_result = MagicMock()
        redeem_result.first = MagicMock(return_value=(WORKSPACE_A,))
        # Third execute: INSERT...ON CONFLICT...RETURNING (returns row -- inserted)
        insert_result = MagicMock()
        insert_result.first = MagicMock(return_value=(-1001234567890,))

        session.execute = AsyncMock(side_effect=[peek_result, redeem_result, insert_result])
        # Chat is unmapped
        session.scalar = AsyncMock(return_value=None)

        message = _make_group_message(text="/start@ContextOSBot VALIDCODE000000")
        result = await claim_chat(session, message)

        assert result == ClaimResult.CLAIMED
        assert session.execute.await_count == 3
        session.commit.assert_awaited()
        mock_send_reply.assert_awaited_once()
        mock_emit_activity.assert_awaited_once()
        # Activity event should be 'integration_connected'
        args, kwargs = mock_emit_activity.call_args
        assert "integration_connected" in args or kwargs.get("event_type") == "integration_connected"
        # And should reference workspace A
        # (positional signature: session, workspace_id, event_type)
        assert args[1] == WORKSPACE_A or kwargs.get("workspace_id") == WORKSPACE_A

    @pytest.mark.asyncio
    async def test_repair_after_kick_updates_soft_deleted_row(
        self, mock_send_reply, mock_emit_activity
    ):
        """Bot was kicked (removed_at IS NOT NULL); same workspace re-pairs.
        ON CONFLICT DO UPDATE WHERE removed_at IS NOT NULL re-claims the slot
        and RETURNING yields a row -- result is CLAIMED, not race conflict.
        """
        session = _make_session()
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        redeem_result = MagicMock()
        redeem_result.first = MagicMock(return_value=(WORKSPACE_A,))
        # ON CONFLICT DO UPDATE matched the soft-deleted row -- RETURNING yields
        insert_result = MagicMock()
        insert_result.first = MagicMock(return_value=(-1001234567890,))

        session.execute = AsyncMock(side_effect=[peek_result, redeem_result, insert_result])
        # resolve_workspace_for_chat filters removed_at IS NULL -> None for kicked
        session.scalar = AsyncMock(return_value=None)

        message = _make_group_message(text="/start@ContextOSBot REPAIR0000")
        result = await claim_chat(session, message)

        assert result == ClaimResult.CLAIMED
        session.commit.assert_awaited()
        mock_send_reply.assert_awaited_once()
        mock_emit_activity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_race_insert_active_row_returns_already_claimed(
        self, mock_send_reply, mock_emit_activity
    ):
        """A parallel claim from another workspace inserted an active row
        between our resolve_workspace_for_chat and our ON CONFLICT DO UPDATE.
        The UPDATE's WHERE removed_at IS NOT NULL filters that row out, so
        RETURNING yields nothing -> ALREADY_CLAIMED_BY_OTHER.
        """
        session = _make_session()
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        redeem_result = MagicMock()
        redeem_result.first = MagicMock(return_value=(WORKSPACE_A,))
        insert_result = MagicMock()
        insert_result.first = MagicMock(return_value=None)  # active row blocked the update

        session.execute = AsyncMock(side_effect=[peek_result, redeem_result, insert_result])
        session.scalar = AsyncMock(return_value=None)

        message = _make_group_message(text="/start@ContextOSBot RACECONF00")
        result = await claim_chat(session, message)

        assert result == ClaimResult.ALREADY_CLAIMED_BY_OTHER
        session.commit.assert_awaited()
        mock_send_reply.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_race_redeem_returns_no_row_marks_invalid(
        self, mock_send_reply, mock_emit_activity
    ):
        """Peek saw the code, but a concurrent redeemer burned it before our DELETE.
        Treat as INVALID_CODE; no INSERT runs.
        """
        session = _make_session()
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        redeem_result = MagicMock()
        redeem_result.first = MagicMock(return_value=None)  # race -> nothing to delete

        session.execute = AsyncMock(side_effect=[peek_result, redeem_result])
        session.scalar = AsyncMock(return_value=None)

        message = _make_group_message(text="/start@ContextOSBot RACE123")
        result = await claim_chat(session, message)

        assert result == ClaimResult.INVALID_CODE
        # Only peek and redeem; no INSERT
        assert session.execute.await_count == 2
        session.commit.assert_not_called()
        mock_send_reply.assert_awaited_once()
        mock_emit_activity.assert_not_called()


class TestClaimChatTokenization:
    """Tokenize `/start[@bot] <code>` correctly."""

    @pytest.mark.asyncio
    async def test_no_payload_returns_invalid(self, mock_send_reply, mock_emit_activity):
        """`/start` with no payload yields empty code -> INVALID_CODE."""
        session = _make_session()
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=peek_result)
        session.scalar = AsyncMock(return_value=None)

        message = _make_group_message(text="/start@ContextOSBot")
        result = await claim_chat(session, message)
        assert result == ClaimResult.INVALID_CODE

    @pytest.mark.asyncio
    async def test_start_without_bot_username_works(
        self, mock_send_reply, mock_emit_activity
    ):
        """Plain `/start <code>` (no @bot suffix) is also valid."""
        session = _make_session()
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        redeem_result = MagicMock()
        redeem_result.first = MagicMock(return_value=(WORKSPACE_A,))
        insert_result = MagicMock()
        insert_result.rowcount = 1

        session.execute = AsyncMock(side_effect=[peek_result, redeem_result, insert_result])
        session.scalar = AsyncMock(return_value=None)

        message = _make_group_message(text="/start CODE12345")
        result = await claim_chat(session, message)
        assert result == ClaimResult.CLAIMED


class TestSendReplySafety:
    """Pitfall 6: reply send failure must NOT roll back the claim."""

    @pytest.mark.asyncio
    async def test_send_reply_failure_does_not_rollback(self, mock_emit_activity):
        """If telegram_api_call raises, the claim is still committed."""
        session = _make_session()
        peek_result = MagicMock()
        peek_result.first = MagicMock(return_value=(WORKSPACE_A, USER_A))
        redeem_result = MagicMock()
        redeem_result.first = MagicMock(return_value=(WORKSPACE_A,))
        insert_result = MagicMock()
        insert_result.rowcount = 1
        session.execute = AsyncMock(side_effect=[peek_result, redeem_result, insert_result])
        session.scalar = AsyncMock(return_value=None)

        # Real _send_reply_safe path: patch telegram_api_call to raise.
        with patch(
            "src.services.telegram_pairing.telegram_api_call", new_callable=AsyncMock
        ) as mock_api:
            mock_api.side_effect = TelegramError("Forbidden: bot was muted")
            message = _make_group_message(text="/start@ContextOSBot CODE")
            # Should NOT raise -- _send_reply_safe swallows it
            result = await claim_chat(session, message)

        assert result == ClaimResult.CLAIMED
        # Commit happened, no rollback was triggered by the reply error.
        session.commit.assert_awaited()
        session.rollback.assert_not_called()


# ===========================================================================
# handle_my_chat_member
# ===========================================================================


class TestHandleMyChatMember:
    @pytest.mark.asyncio
    async def test_left_status_soft_deletes_mapping(self, mock_emit_activity):
        session = _make_session()
        session.scalar = AsyncMock(return_value=WORKSPACE_A)  # workspace lookup
        update_result = MagicMock()
        update_result.rowcount = 1
        session.execute = AsyncMock(return_value=update_result)

        update = {
            "chat": {"id": -1001234567890},
            "new_chat_member": {"status": "left"},
        }
        await handle_my_chat_member(session, update)

        # An UPDATE statement was executed
        session.execute.assert_awaited()
        session.commit.assert_awaited()
        # integration_disconnected activity emitted
        mock_emit_activity.assert_awaited_once()
        args, kwargs = mock_emit_activity.call_args
        assert "integration_disconnected" in args or kwargs.get("event_type") == "integration_disconnected"

    @pytest.mark.asyncio
    async def test_kicked_status_soft_deletes_mapping(self, mock_emit_activity):
        session = _make_session()
        session.scalar = AsyncMock(return_value=WORKSPACE_A)
        update_result = MagicMock()
        update_result.rowcount = 1
        session.execute = AsyncMock(return_value=update_result)

        update = {
            "chat": {"id": -1001234567890},
            "new_chat_member": {"status": "kicked"},
        }
        await handle_my_chat_member(session, update)

        session.execute.assert_awaited()
        mock_emit_activity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_member_status_logs_only_no_db_change(self, mock_emit_activity):
        """Bot was added/promoted -> log only, no UPDATE, no activity."""
        session = _make_session()
        update = {
            "chat": {"id": -1001234567890},
            "new_chat_member": {"status": "member"},
        }
        await handle_my_chat_member(session, update)
        session.execute.assert_not_called()
        mock_emit_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_administrator_status_logs_only(self, mock_emit_activity):
        session = _make_session()
        update = {
            "chat": {"id": -1001234567890},
            "new_chat_member": {"status": "administrator"},
        }
        await handle_my_chat_member(session, update)
        session.execute.assert_not_called()
        mock_emit_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_left_with_no_existing_mapping_skips_activity(self, mock_emit_activity):
        """If resolve_workspace_for_chat returns None, no activity is emitted
        (UPDATE still runs but matches 0 rows).
        """
        session = _make_session()
        session.scalar = AsyncMock(return_value=None)  # no mapping
        update_result = MagicMock()
        update_result.rowcount = 0
        session.execute = AsyncMock(return_value=update_result)

        update = {
            "chat": {"id": -1009999999999},
            "new_chat_member": {"status": "left"},
        }
        await handle_my_chat_member(session, update)

        # No activity since we couldn't resolve a workspace
        mock_emit_activity.assert_not_called()
