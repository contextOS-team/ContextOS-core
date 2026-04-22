"""Tests for Slack user-token DM/group-DM polling service.

Covers 10 behaviors (split across Task 1 and Task 2 of Plan 39-02):

Task 1 (TestEnumerate):
- A: dms_disabled short-circuit -- zero HTTP calls when include_dms is False/missing
- B: needs_reauth -- SlackOAuthError from get_user_token returns reason="needs_reauth"
- C: enumerate DMs only -- users.conversations called with types=im,mpim, no channels
- D: incremental polling -- last_user_poll_at used as oldest; backfill window when
     first-time DM opt-in and dms_backfill_done is falsy

Task 2 (TestPolling + TestUpsert):
- E: backfill cap -- 100 messages per conversation cap, no further pagination
- F: upsert + embedding + graph parity -- pg_insert on uq_slack_msg, SET drift guard
- G: 429 retry -- honor Retry-After header, single retry
- H: 401 handling -- invalid_auth logs and short-circuits remaining conversations
- I: updates last_user_poll_at; flips dms_backfill_done=True on first backfill
- J: dedup via upsert -- webhook-path overlap counted as skipped, not ingested
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from tests.conftest import TEST_WORKSPACE_ID

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_dm_list_response(
    ids: list[str],
    has_more: bool = False,
    next_cursor: str | None = None,
) -> dict:
    """Build a Slack users.conversations response payload."""
    channels = []
    for cid in ids:
        # Use the id prefix convention: "D..." = im, "G..." = mpim
        is_mpim = cid.startswith("G")
        channels.append(
            {
                "id": cid,
                "is_im": not is_mpim,
                "is_mpim": is_mpim,
                "is_archived": False,
            }
        )
    payload: dict = {"ok": True, "channels": channels, "has_more": has_more}
    if next_cursor:
        payload["response_metadata"] = {"next_cursor": next_cursor}
    return payload


def _make_history_response(
    messages: list[dict],
    has_more: bool = False,
    next_cursor: str | None = None,
) -> dict:
    """Build a Slack conversations.history response payload."""
    payload: dict = {"ok": True, "messages": messages, "has_more": has_more}
    if next_cursor:
        payload["response_metadata"] = {"next_cursor": next_cursor}
    return payload


def _make_message(
    ts: str,
    user: str = "U001",
    text: str = "hello",
    thread_ts: str | None = None,
    bot_id: str | None = None,
    subtype: str | None = None,
) -> dict:
    """Build a single Slack message event dict."""
    msg: dict = {"type": "message", "ts": ts, "user": user, "text": text}
    if thread_ts:
        msg["thread_ts"] = thread_ts
    if bot_id:
        msg["bot_id"] = bot_id
    if subtype:
        msg["subtype"] = subtype
    return msg


def _make_http_resp(
    json_data: dict | None = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build a mocked httpx Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    resp.text = str(json_data) if json_data else ""
    return resp


# ---------------------------------------------------------------------------
# Autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_queue_embedding():
    """Patch the embedding queue to avoid side-effects in unit tests."""
    with patch(
        "src.services.slack_messages.embedding.queue_embedding_generation",
        new_callable=AsyncMock,
    ) as m:
        yield m


@pytest.fixture(autouse=True)
def _patch_graph_extractor():
    """Patch graph extraction to avoid DB side effects."""
    with patch(
        "src.services.slack_messages.extract_and_populate_graph",
        new_callable=AsyncMock,
    ) as m:
        yield m


def _mock_integration(config: dict | None) -> MagicMock:
    """Build a mocked WorkspaceIntegration row for session.execute chains."""
    integration = MagicMock()
    integration.config = dict(config) if config else {}
    integration.status = "connected"
    return integration


def _mock_session_with_integration(integration: MagicMock | None) -> AsyncMock:
    """Build a mock AsyncSession whose first execute returns the integration."""
    session = AsyncMock()
    int_result = MagicMock()
    int_result.scalar_one_or_none.return_value = integration
    session.execute = AsyncMock(return_value=int_result)
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Task 1 -- Tests A, B, C, D
# ---------------------------------------------------------------------------


class TestEnumerate:
    """Skeleton behaviors: short-circuit guards + DM enumeration shape."""

    @pytest.mark.asyncio
    async def test_A_dms_disabled_short_circuits(self) -> None:
        """Test A: include_dms=False returns dms_disabled and makes no HTTP calls."""
        from src.services.slack_messages import poll_user_messages

        integration = _mock_integration({"include_dms": False})
        session = _mock_session_with_integration(integration)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
            ) as mock_get_token,
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            result = await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        assert result == {"ingested": 0, "skipped": 0, "reason": "dms_disabled"}
        mock_get_token.assert_not_called()
        mock_httpx.assert_not_called()

    @pytest.mark.asyncio
    async def test_A_missing_include_dms_treated_as_disabled(self) -> None:
        """Test A (variant): missing include_dms key -> dms_disabled, no HTTP calls."""
        from src.services.slack_messages import poll_user_messages

        integration = _mock_integration({})  # no include_dms at all
        session = _mock_session_with_integration(integration)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
            ) as mock_get_token,
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            result = await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        assert result["reason"] == "dms_disabled"
        mock_get_token.assert_not_called()
        mock_httpx.assert_not_called()

    @pytest.mark.asyncio
    async def test_B_needs_reauth_when_token_missing(self) -> None:
        """Test B: get_user_token raising SlackOAuthError -> reason=needs_reauth."""
        from src.services.slack_messages import poll_user_messages
        from src.services.slack_oauth import SlackOAuthError

        integration = _mock_integration({"include_dms": True})
        session = _mock_session_with_integration(integration)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                side_effect=SlackOAuthError("no token"),
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            result = await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        assert result == {"ingested": 0, "skipped": 0, "reason": "needs_reauth"}
        mock_httpx.assert_not_called()

    @pytest.mark.asyncio
    async def test_C_enumerates_only_im_and_mpim(self) -> None:
        """Test C: users.conversations is called exactly once with types=im,mpim.

        The returned 2 DMs + 1 mpim are iterated; no public/private channel calls.
        """
        from src.services.slack_messages import poll_user_messages

        integration = _mock_integration({"include_dms": True})
        session = _mock_session_with_integration(integration)

        dm_list = _make_dm_list_response(["D001", "D002", "G001"])
        # Each of 3 convs gets an empty history fetch
        empty_hist = _make_history_response([])

        mock_client = AsyncMock()
        captured_calls: list[tuple[str, dict]] = []

        async def _fake_get(url: str, params: dict | None = None, headers=None):
            captured_calls.append((url, dict(params or {})))
            if "users.conversations" in url:
                return _make_http_resp(dm_list)
            # conversations.history
            return _make_http_resp(empty_hist)

        mock_client.get = AsyncMock(side_effect=_fake_get)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                return_value="xoxp-token",
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        # Exactly one users.conversations call
        conv_calls = [c for c in captured_calls if "users.conversations" in c[0]]
        assert len(conv_calls) == 1
        types_param = conv_calls[0][1].get("types", "")
        assert "im" in types_param and "mpim" in types_param
        # Must NOT enumerate public or private channels
        assert "public_channel" not in types_param
        assert "private_channel" not in types_param

        # Iterated all 3 DM conversations
        hist_calls = [c for c in captured_calls if "conversations.history" in c[0]]
        hist_channels = {c[1].get("channel") for c in hist_calls}
        assert hist_channels == {"D001", "D002", "G001"}

    @pytest.mark.asyncio
    async def test_D_incremental_uses_last_user_poll_at(self) -> None:
        """Test D (steady state): last_user_poll_at -> oldest on history call."""
        from src.services.slack_messages import poll_user_messages

        last_poll = "2026-04-20T10:00:00"
        integration = _mock_integration(
            {"include_dms": True, "last_user_poll_at": last_poll}
        )
        session = _mock_session_with_integration(integration)

        mock_client = AsyncMock()
        captured_oldests: list[str | None] = []

        async def _fake_get(url: str, params: dict | None = None, headers=None):
            if "users.conversations" in url:
                return _make_http_resp(_make_dm_list_response(["D001"]))
            captured_oldests.append((params or {}).get("oldest"))
            return _make_http_resp(_make_history_response([]))

        mock_client.get = AsyncMock(side_effect=_fake_get)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                return_value="xoxp-token",
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        assert len(captured_oldests) == 1
        # last_user_poll_at is written as naive UTC (see poll_user_messages).
        # _compute_oldest coerces it to UTC before converting to a Slack ts
        # float-string -- otherwise .timestamp() would treat the naive value
        # as local time and produce a TZ-offset bug.
        from datetime import datetime

        expected = (
            f"{datetime.fromisoformat(last_poll).replace(tzinfo=UTC).timestamp():.6f}"
        )
        assert captured_oldests[0] == expected

    @pytest.mark.asyncio
    async def test_D_backfill_uses_seven_day_window(self) -> None:
        """Test D (backfill): first-time DM opt-in uses oldest = now-7d."""
        from datetime import datetime, timedelta

        from src.services.slack_messages import poll_user_messages

        integration = _mock_integration(
            {
                "include_dms": True,
                "dms_first_enabled_at": "2026-04-21T10:00:00",
                # dms_backfill_done absent/falsy -> backfill path
            }
        )
        session = _mock_session_with_integration(integration)

        mock_client = AsyncMock()
        captured_oldests: list[str | None] = []

        async def _fake_get(url: str, params: dict | None = None, headers=None):
            if "users.conversations" in url:
                return _make_http_resp(_make_dm_list_response(["D001"]))
            captured_oldests.append((params or {}).get("oldest"))
            return _make_http_resp(_make_history_response([]))

        mock_client.get = AsyncMock(side_effect=_fake_get)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                return_value="xoxp-token",
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        assert len(captured_oldests) == 1
        oldest_val = captured_oldests[0]
        assert oldest_val is not None
        oldest_float = float(oldest_val)
        now = datetime.now(UTC)
        expected_low = (now - timedelta(days=7, minutes=5)).timestamp()
        expected_high = (now - timedelta(days=7) + timedelta(minutes=5)).timestamp()
        assert expected_low <= oldest_float <= expected_high


# ---------------------------------------------------------------------------
# Task 2 -- placeholders (populated in Task 2)
# ---------------------------------------------------------------------------


class TestPolling:
    """Polling behaviors: backfill cap, 429 retry, 401 handling, bookkeeping."""

    @pytest.mark.asyncio
    async def test_E_backfill_cap_stops_pagination(self, _patch_queue_embedding) -> None:
        """Test E: backfill mode caps each conversation at 100 messages.

        When has_more=True and the first page returns 100 messages, the
        poller does NOT paginate further for that conversation.
        """
        from src.services.slack_messages import (
            BACKFILL_MESSAGES_PER_CONVERSATION_CAP,
            poll_user_messages,
        )

        integration = _mock_integration(
            {
                "include_dms": True,
                "dms_first_enabled_at": "2026-04-21T10:00:00",
                # no dms_backfill_done -> backfill path
            }
        )
        session = _mock_session_with_integration(integration)
        # Make _upsert_messages trivially skip everything by patching it to
        # avoid the DB. Task 2 test F verifies the upsert path itself.
        mock_client = AsyncMock()
        history_calls: list[dict] = []

        full_page = _make_history_response(
            [
                _make_message(f"170000{i:04d}.000001", text=f"m{i}")
                for i in range(BACKFILL_MESSAGES_PER_CONVERSATION_CAP)
            ],
            has_more=True,
            next_cursor="next_page",
        )

        async def _fake_get(url: str, params: dict | None = None, headers=None):
            if "users.conversations" in url:
                return _make_http_resp(_make_dm_list_response(["D001"]))
            history_calls.append(dict(params or {}))
            return _make_http_resp(full_page)

        mock_client.get = AsyncMock(side_effect=_fake_get)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                return_value="xoxp-token",
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
            patch(
                "src.services.slack_messages._upsert_messages",
                new_callable=AsyncMock,
                return_value=(100, 0),
            ),
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        # Only ONE history call for D001 -- pagination stopped after cap hit.
        assert len(history_calls) == 1

    @pytest.mark.asyncio
    async def test_G_rate_limit_retry_honors_retry_after(
        self, monkeypatch
    ) -> None:
        """Test G: 429 response sleeps Retry-After seconds and retries once."""
        import src.services.slack_messages as mod
        from src.services.slack_messages import poll_user_messages

        sleep_calls: list[float] = []

        async def _fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

        integration = _mock_integration({"include_dms": True})
        session = _mock_session_with_integration(integration)

        rate_limited_resp = _make_http_resp(
            {}, status_code=429, headers={"Retry-After": "2"}
        )

        conv_ok = _make_http_resp(_make_dm_list_response(["D001"]))
        hist_ok = _make_http_resp(_make_history_response([]))

        mock_client = AsyncMock()
        # First call (users.conversations) -> 429; retry succeeds.
        # Then history call succeeds immediately.
        mock_client.get = AsyncMock(
            side_effect=[rate_limited_resp, conv_ok, hist_ok]
        )

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                return_value="xoxp-token",
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        # Slept exactly 2 seconds (from Retry-After).
        assert 2 in sleep_calls
        # Three total GETs: 429'd conv, retry conv, history for D001.
        assert mock_client.get.await_count == 3

    @pytest.mark.asyncio
    async def test_H_invalid_auth_short_circuits_remaining(self) -> None:
        """Test H: invalid_auth during history aborts remaining conversations."""
        from src.services.slack_messages import poll_user_messages

        integration = _mock_integration({"include_dms": True})
        session = _mock_session_with_integration(integration)

        mock_client = AsyncMock()
        history_calls: list[dict] = []

        async def _fake_get(url: str, params: dict | None = None, headers=None):
            if "users.conversations" in url:
                return _make_http_resp(
                    _make_dm_list_response(["D001", "D002"])
                )
            history_calls.append(dict(params or {}))
            # First history call fails with invalid_auth.
            return _make_http_resp({"ok": False, "error": "invalid_auth"})

        mock_client.get = AsyncMock(side_effect=_fake_get)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                return_value="xoxp-token",
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))

        # Only the first history call happened; D002 was never fetched.
        assert len(history_calls) == 1
        assert result["reason"] == "needs_reauth"
        # Integration config was NOT updated (no commit of last_user_poll_at).
        assert "last_user_poll_at" not in integration.config

    @pytest.mark.asyncio
    async def test_I_updates_last_user_poll_at_on_success(self) -> None:
        """Test I: success path updates last_user_poll_at and flips dms_backfill_done."""
        from datetime import datetime, timedelta

        from src.services.slack_messages import poll_user_messages

        integration = _mock_integration(
            {
                "include_dms": True,
                "dms_first_enabled_at": "2026-04-21T10:00:00",
                # dms_backfill_done absent -> first backfill
            }
        )
        session = _mock_session_with_integration(integration)

        mock_client = AsyncMock()

        async def _fake_get(url: str, params: dict | None = None, headers=None):
            if "users.conversations" in url:
                return _make_http_resp(_make_dm_list_response(["D001"]))
            return _make_http_resp(
                _make_history_response(
                    [_make_message("1700000000.000001", text="hi")]
                )
            )

        mock_client.get = AsyncMock(side_effect=_fake_get)

        with (
            patch(
                "src.services.slack_messages.get_user_token",
                new_callable=AsyncMock,
                return_value="xoxp-token",
            ),
            patch(
                "src.services.slack_messages.httpx.AsyncClient"
            ) as mock_httpx,
            patch(
                "src.services.slack_messages._upsert_messages",
                new_callable=AsyncMock,
                return_value=(1, 0),
            ),
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            before = datetime.now(UTC).replace(tzinfo=None)
            result = await poll_user_messages(session, UUID(TEST_WORKSPACE_ID))
            after = datetime.now(UTC).replace(tzinfo=None)

        assert result["ingested"] == 1
        assert result["reason"] is None

        # last_user_poll_at set to a naive-UTC ISO string within the call window.
        last = integration.config.get("last_user_poll_at")
        assert last is not None
        last_dt = datetime.fromisoformat(last)
        assert (before - timedelta(seconds=2)) <= last_dt <= (after + timedelta(seconds=2))

        # dms_backfill_done flipped True after first backfill.
        assert integration.config.get("dms_backfill_done") is True


class TestUpsert:
    """Upsert + embedding + graph parity + dedup."""

    @pytest.mark.asyncio
    async def test_F_upsert_parity_with_slack_events(
        self,
        _patch_queue_embedding,
        _patch_graph_extractor,
    ) -> None:
        """Test F: polled message triggers pg_insert.on_conflict_do_update(uq_slack_msg),
        one embedding call, one graph-extraction call; filtered messages are NOT
        upserted or embedded; SET-clause source inspection guards SLACK-USR-04 drift.
        """
        import inspect

        import src.services.slack_messages as mod
        from src.services.slack_messages import _upsert_messages

        # --- 1) SET-clause drift guard -------------------------------------
        src_code = inspect.getsource(mod._upsert_messages)
        for field in (
            "text",
            "user_id",
            "thread_ts",
            "parent_ts",
            "is_thread_reply",
            "raw_data",
        ):
            assert f'"{field}"' in src_code, f"SET clause missing field: {field}"

        # --- 2) Upsert path executes exactly once for one message ---------
        workspace_id = UUID(TEST_WORKSPACE_ID)
        conv_id = "D001"

        # Seed a filtered bot message alongside a real one; only the real
        # one should hit the upsert path.
        real_msg = _make_message(
            "1700000000.000001", user="U001", text="hi there"
        )
        bot_msg = _make_message(
            "1700000000.000002", user="U002", text="bot noise", bot_id="B999"
        )

        # Mock session with two execute branches:
        #  - SELECT existing slack_ts (dedup pre-count) -> empty result
        #  - INSERT ... RETURNING id -> returns a fresh UUID
        from uuid import uuid4

        inserted_id = uuid4()
        session = AsyncMock()
        existing_result = MagicMock()
        existing_result.all.return_value = []  # no prior rows

        insert_result = MagicMock()
        insert_result.scalar_one.return_value = inserted_id

        session.execute = AsyncMock(
            side_effect=[existing_result, insert_result]
        )
        session.commit = AsyncMock()

        ingested, skipped = await _upsert_messages(
            session, workspace_id, conv_id, [real_msg, bot_msg]
        )

        assert ingested == 1
        # bot_msg is filter-skipped; real_msg inserted.
        assert skipped == 1

        # Embedding queued exactly once for the real message.
        _patch_queue_embedding.assert_awaited_once()
        queue_call = _patch_queue_embedding.await_args
        assert queue_call.args[1] == workspace_id
        assert queue_call.args[2] == "slack_message"
        assert queue_call.args[3] == [inserted_id]

        # Graph extraction called exactly once with source_type=slack_message.
        _patch_graph_extractor.assert_awaited_once()
        graph_kwargs = _patch_graph_extractor.await_args.kwargs
        assert graph_kwargs["source_type"] == "slack_message"
        assert graph_kwargs["source_id"] == inserted_id
        assert graph_kwargs["workspace_id"] == workspace_id

    @pytest.mark.asyncio
    async def test_J_dedup_via_upsert_counts_as_skipped(
        self,
        _patch_queue_embedding,
        _patch_graph_extractor,
    ) -> None:
        """Test J: message ts already present -> counted as skipped, not ingested."""
        from uuid import uuid4

        from src.services.slack_messages import _upsert_messages

        workspace_id = UUID(TEST_WORKSPACE_ID)
        conv_id = "D001"
        msg = _make_message("1700000000.000001", user="U001", text="already seen")

        existing_result = MagicMock()
        # Pre-existing row: the dedup SELECT returns a 1-tuple row with the ts.
        existing_result.all.return_value = [(msg["ts"],)]

        insert_result = MagicMock()
        insert_result.scalar_one.return_value = uuid4()

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[existing_result, insert_result]
        )
        session.commit = AsyncMock()

        ingested, skipped = await _upsert_messages(
            session, workspace_id, conv_id, [msg]
        )

        assert ingested == 0
        assert skipped == 1
