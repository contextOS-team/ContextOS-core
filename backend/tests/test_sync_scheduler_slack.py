"""Tests for Phase 39 Slack DM polling wired into run_polling_fallback.

Covers 4 behaviors:
- A: per-workspace iteration — each connected Slack workspace is polled once
     per cycle with the workspace_id argument.
- B: exception isolation — a crash in one workspace's poll does not prevent
     other workspaces from being polled in the same cycle; logger.exception
     is invoked with the failing workspace id.
- C: provider scope — poll_user_messages is NOT called for Notion/GitHub/
     Telegram workspaces.
- D: coexistence with existing duties — reason="dms_disabled" does not block
     Notion reconcile, code index freshness, or daily digest emission.

All tests patch ``src.services.sync_scheduler.poll_user_messages`` (the
locally-bound module attribute) per the Plan 39-04 import placement rule.
Patching ``src.services.slack_messages.poll_user_messages`` would NOT be
visible to the scheduler because sync_scheduler imports the symbol at module
top — the scheduler holds its own reference, not a lookup into slack_messages.
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.models.integration import Provider


class _CancelAfterFirstCycle:
    """Callable that raises CancelledError after N sleeps.

    Used to exit ``run_polling_fallback``'s infinite loop cleanly after one
    iteration has completed all its per-provider work.
    """

    def __init__(self, after: int = 1) -> None:
        self.after = after
        self.count = 0

    async def __call__(self, *_args: object, **_kwargs: object) -> None:
        self.count += 1
        if self.count >= self.after:
            raise asyncio.CancelledError()


def _patch_workspaces(
    monkeypatch: pytest.MonkeyPatch,
    ws_by_provider: dict[Provider, list[UUID]],
) -> None:
    """Patch sync_scheduler.async_session for the current batched-query contract.

    CURRENT contract (src/services/sync_scheduler.py:331-352): run_polling_fallback
    NO LONGER calls _get_connected_workspaces(provider) per provider. It opens a
    single ``async with async_session() as session`` and runs ONE batched
    ``select(WorkspaceIntegration.workspace_id, WorkspaceIntegration.provider)``,
    building workspaces_by_provider from ``result.fetchall()`` rows of
    ``(workspace_id, provider)``. The Slack-poll branch also opens its own
    ``async with async_session() as session`` before calling poll_user_messages
    (which is mocked, so that session's execute is never used).

    This fake async_session serves both: any execute() returns a result whose
    .fetchall() yields the flattened (ws_id, provider) rows.
    """
    from src.services import sync_scheduler

    rows = [
        (ws_id, provider)
        for provider, ws_ids in ws_by_provider.items()
        for ws_id in ws_ids
    ]

    result = MagicMock()
    result.fetchall.return_value = rows

    @contextlib.asynccontextmanager
    async def _fake_async_session():
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        yield session

    monkeypatch.setattr(sync_scheduler, "async_session", _fake_async_session)


async def _run_one_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run run_polling_fallback until the first sleep, then cancel."""
    from src.services import sync_scheduler

    sleep_stub = _CancelAfterFirstCycle(after=1)
    monkeypatch.setattr(sync_scheduler.asyncio, "sleep", sleep_stub)

    with pytest.raises(asyncio.CancelledError):
        await sync_scheduler.run_polling_fallback()


class TestSlackPollingIntegration:
    """Slack DM polling integrated into the 15-minute scheduler loop."""

    @pytest.mark.asyncio
    async def test_A_polls_each_connected_slack_workspace_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.services import sync_scheduler

        ws_a = uuid4()
        ws_b = uuid4()

        _patch_workspaces(monkeypatch, {Provider.SLACK: [ws_a, ws_b]})
        monkeypatch.setattr(
            sync_scheduler, "_expire_stale_generations", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            sync_scheduler, "reconcile_notion", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            sync_scheduler,
            "_check_code_index_freshness",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            sync_scheduler, "_emit_daily_digest", AsyncMock(return_value=None)
        )

        poll_mock = AsyncMock(
            return_value={"ingested": 0, "skipped": 0, "reason": "dms_disabled"}
        )
        # IMPORTANT: patch the LOCALLY-BOUND name in sync_scheduler, not the
        # origin in slack_messages.
        monkeypatch.setattr(
            "src.services.sync_scheduler.poll_user_messages", poll_mock
        )

        await _run_one_cycle(monkeypatch)

        assert poll_mock.await_count == 2
        called_ws_ids = {call.args[1] for call in poll_mock.await_args_list}
        assert called_ws_ids == {ws_a, ws_b}

    @pytest.mark.asyncio
    async def test_B_exception_in_one_workspace_does_not_block_others(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from src.services import sync_scheduler

        ws_a = uuid4()
        ws_b = uuid4()

        _patch_workspaces(monkeypatch, {Provider.SLACK: [ws_a, ws_b]})
        monkeypatch.setattr(
            sync_scheduler, "_expire_stale_generations", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            sync_scheduler, "reconcile_notion", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            sync_scheduler,
            "_check_code_index_freshness",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            sync_scheduler, "_emit_daily_digest", AsyncMock(return_value=None)
        )

        async def _poll(_session: object, ws_id: UUID) -> dict:
            if ws_id == ws_a:
                raise RuntimeError("slack api boom")
            return {"ingested": 1, "skipped": 0, "reason": None}

        poll_mock = AsyncMock(side_effect=_poll)
        monkeypatch.setattr(
            "src.services.sync_scheduler.poll_user_messages", poll_mock
        )

        caplog.set_level("ERROR", logger="src.services.sync_scheduler")
        await _run_one_cycle(monkeypatch)

        # Both workspaces were attempted
        assert poll_mock.await_count == 2
        # ws_a's failure was logged with exception()
        logged_messages = [rec.getMessage() for rec in caplog.records]
        assert any(str(ws_a) in msg for msg in logged_messages), (
            f"Expected exception log to reference {ws_a}; got {logged_messages}"
        )

    @pytest.mark.asyncio
    async def test_C_does_not_poll_non_slack_providers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.services import sync_scheduler

        notion_ws = uuid4()
        github_ws = uuid4()
        telegram_ws = uuid4()

        _patch_workspaces(
            monkeypatch,
            {
                Provider.NOTION: [notion_ws],
                Provider.GITHUB: [github_ws],
                Provider.TELEGRAM: [telegram_ws],
                Provider.SLACK: [],
            },
        )
        monkeypatch.setattr(
            sync_scheduler, "_expire_stale_generations", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            sync_scheduler, "reconcile_notion", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            sync_scheduler,
            "_check_code_index_freshness",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            sync_scheduler, "_emit_daily_digest", AsyncMock(return_value=None)
        )

        poll_mock = AsyncMock(
            return_value={"ingested": 0, "skipped": 0, "reason": "dms_disabled"}
        )
        monkeypatch.setattr(
            "src.services.sync_scheduler.poll_user_messages", poll_mock
        )

        await _run_one_cycle(monkeypatch)

        # Zero Slack workspaces → zero poll calls
        assert poll_mock.await_count == 0

    @pytest.mark.asyncio
    async def test_D_dms_disabled_does_not_block_other_duties(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.services import sync_scheduler

        slack_ws = uuid4()
        notion_ws = uuid4()
        github_ws = uuid4()
        telegram_ws = uuid4()

        _patch_workspaces(
            monkeypatch,
            {
                Provider.SLACK: [slack_ws],
                Provider.NOTION: [notion_ws],
                Provider.GITHUB: [github_ws],
                Provider.TELEGRAM: [telegram_ws],
            },
        )
        expire_mock = AsyncMock(return_value=None)
        reconcile_mock = AsyncMock(return_value=None)
        code_index_mock = AsyncMock(return_value=None)
        digest_mock = AsyncMock(return_value=None)
        monkeypatch.setattr(sync_scheduler, "_expire_stale_generations", expire_mock)
        monkeypatch.setattr(sync_scheduler, "reconcile_notion", reconcile_mock)
        monkeypatch.setattr(
            sync_scheduler, "_check_code_index_freshness", code_index_mock
        )
        monkeypatch.setattr(sync_scheduler, "_emit_daily_digest", digest_mock)

        poll_mock = AsyncMock(
            return_value={"ingested": 0, "skipped": 0, "reason": "dms_disabled"}
        )
        monkeypatch.setattr(
            "src.services.sync_scheduler.poll_user_messages", poll_mock
        )

        await _run_one_cycle(monkeypatch)

        # Slack polling happened
        assert poll_mock.await_count == 1
        # And the existing duties also ran on their respective workspaces
        reconcile_mock.assert_awaited_once_with(notion_ws)
        code_index_mock.assert_awaited_once_with(github_ws)
        # Daily digests iterate through (Slack, Telegram)
        digest_call_args = {call.args for call in digest_mock.await_args_list}
        assert (slack_ws, "slack") in digest_call_args
        assert (telegram_ws, "telegram") in digest_call_args
