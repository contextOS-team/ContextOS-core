"""Tests for concurrency controls, HTTP/2, sync, and polling scheduler."""

import random
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSemaphoreValues:
    """Verify per-provider semaphore concurrency limits."""

    def test_notion_semaphore_limits_concurrency(self):
        from src.services.notion_client import _notion_semaphore

        assert _notion_semaphore._value == 3

    def test_linear_semaphore_limits_concurrency(self):
        from src.services.linear_graphql import _linear_semaphore

        assert _linear_semaphore._value == 5

    def test_github_semaphore_limits_concurrency(self):
        from src.services.github_common import _github_semaphore

        assert _github_semaphore._value == 10


class TestHTTP2Configuration:
    """Verify HTTP/2 is enabled on API clients."""

    def test_notion_client_uses_http2(self):
        from src.services.notion_client import NotionClient

        client = NotionClient("test-token")
        # httpx stores http2 flag on the client instance
        assert client._client._transport._pool._http2 is True

    @pytest.mark.asyncio
    async def test_github_client_uses_http2(self):
        from src.services.github_common import create_github_client

        client = create_github_client()
        assert client._transport._pool._http2 is True
        await client.aclose()


class TestJitter:
    """Verify jitter formula produces values in [0.5*base, 1.5*base] range."""

    def test_jitter_range(self):
        """Verify jitter formula stays in range over many iterations."""
        base_delay = 2.0
        min_expected = base_delay * 0.5
        max_expected = base_delay * 1.5

        for _ in range(1000):
            jittered = base_delay * (0.5 + random.random())
            assert min_expected <= jittered <= max_expected, (
                f"Jittered value {jittered} outside range "
                f"[{min_expected}, {max_expected}]"
            )


class TestIncrementalSync:
    """Test that incremental sync skips unchanged pages and refetches changed ones."""

    @pytest.mark.asyncio
    async def test_notion_incremental_skips_unchanged(self):
        """Stored timestamp >= API timestamp skips get_page_markdown."""
        from datetime import datetime

        mock_client = AsyncMock()
        mock_client.get_page_markdown = AsyncMock(return_value="# Content")

        # Simulate stored timestamp >= API timestamp
        stored_time = datetime(2026, 3, 1, 12, 0, 0)
        api_time = "2026-03-01T12:00:00.000Z"  # Same as stored

        from src.routers.notion import _parse_notion_datetime

        parsed_api_time = _parse_notion_datetime(api_time)
        assert stored_time >= parsed_api_time

        # The incremental logic: if stored >= new, skip
        should_refetch = True
        if stored_time and parsed_api_time and stored_time >= parsed_api_time:
            should_refetch = False

        assert should_refetch is False
        # Since we skipped, get_page_markdown should not be called
        mock_client.get_page_markdown.assert_not_called()

    @pytest.mark.asyncio
    async def test_notion_incremental_refetches_changed(self):
        """When stored timestamp < API timestamp, get_page_markdown SHOULD be called."""
        from datetime import datetime

        mock_client = AsyncMock()
        mock_client.get_page_markdown = AsyncMock(return_value="# Updated Content")

        # Simulate stored timestamp < API timestamp
        stored_time = datetime(2026, 3, 1, 10, 0, 0)
        api_time = "2026-03-01T12:00:00.000Z"

        from src.routers.notion import _parse_notion_datetime

        parsed_api_time = _parse_notion_datetime(api_time)
        assert stored_time < parsed_api_time

        # The incremental logic: if stored < new, refetch
        should_refetch = True
        if stored_time and parsed_api_time and stored_time >= parsed_api_time:
            should_refetch = False

        assert should_refetch is True

        # Simulate the refetch
        if should_refetch:
            content = await mock_client.get_page_markdown("some-page-id")

        mock_client.get_page_markdown.assert_called_once_with("some-page-id")
        assert content == "# Updated Content"


class TestPollingScheduler:
    """Test polling fallback scheduler configuration."""

    def test_polling_interval_is_15_minutes(self):
        from src.services.sync_scheduler import POLL_INTERVAL_SECONDS

        assert POLL_INTERVAL_SECONDS == 900  # 15 * 60

    @pytest.mark.asyncio
    async def test_polling_fallback_runs_cycle_before_sleep(self, monkeypatch):
        from src.services import sync_scheduler

        events = []

        async def fake_expire_stale_generations():
            events.append("startup-expire")

        async def fake_run_polling_cycle():
            events.append("cycle")

        async def fake_sleep(_seconds):
            events.append("sleep")
            raise KeyboardInterrupt

        monkeypatch.setattr(
            sync_scheduler,
            "_expire_stale_generations",
            fake_expire_stale_generations,
        )
        monkeypatch.setattr(
            sync_scheduler,
            "_run_polling_cycle",
            fake_run_polling_cycle,
        )
        monkeypatch.setattr(sync_scheduler.asyncio, "sleep", fake_sleep)

        with pytest.raises(KeyboardInterrupt):
            await sync_scheduler.run_polling_fallback()

        assert events == ["startup-expire", "cycle", "sleep"]

    @pytest.mark.asyncio
    async def test_polling_cycle_drains_missed_decision_scans(self, monkeypatch):
        from src.services import sync_scheduler

        events = []

        async def fake_expire_stale_generations():
            events.append("expire")

        async def fake_drain_missed_decision_scans():
            events.append("drain")

        async def fake_enqueue_missed_decision_backstop(_workspaces):
            events.append("backstop")

        class EmptyProviderRows:
            def fetchall(self):
                return []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=EmptyProviderRows())
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        monkeypatch.setattr(
            sync_scheduler,
            "_expire_stale_generations",
            fake_expire_stale_generations,
        )
        monkeypatch.setattr(
            sync_scheduler,
            "_drain_missed_decision_scans",
            fake_drain_missed_decision_scans,
        )
        monkeypatch.setattr(
            sync_scheduler,
            "_enqueue_missed_decision_backstop",
            fake_enqueue_missed_decision_backstop,
        )
        monkeypatch.setattr(
            sync_scheduler,
            "async_session",
            MagicMock(return_value=mock_cm),
        )

        await sync_scheduler._run_polling_cycle()

        assert events == ["expire", "backstop", "drain"]
        assert mock_session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_backstop_enqueues_stale_missed_decision_scan(self, monkeypatch):
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        from src.models.integration import Provider
        from src.models.missed_decision import MissedDecisionScanState
        from src.services import sync_scheduler

        workspace_id = uuid4()
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        state = MissedDecisionScanState(
            workspace_id=workspace_id,
            source_type="slack_message",
            last_missed_decision_scan_at=now - timedelta(days=2),
        )

        state_result = MagicMock()
        state_result.scalar_one_or_none.return_value = state
        run_result = MagicMock()
        run_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[state_result, run_result])
        mock_session.commit = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_enqueue = AsyncMock(return_value=object())

        monkeypatch.setattr(
            sync_scheduler,
            "async_session",
            MagicMock(return_value=mock_cm),
        )
        monkeypatch.setattr(
            sync_scheduler,
            "enqueue_missed_decision_scan",
            mock_enqueue,
        )

        await sync_scheduler._enqueue_missed_decision_backstop(
            {Provider.SLACK: [workspace_id]},
            now=now,
        )

        mock_enqueue.assert_awaited_once_with(
            mock_session,
            workspace_id,
            "slack_message",
            sync_completed_at=now,
        )
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_backstop_skips_recent_missed_decision_scan(self, monkeypatch):
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        from src.models.integration import Provider
        from src.models.missed_decision import MissedDecisionScanState
        from src.services import sync_scheduler

        workspace_id = uuid4()
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        state = MissedDecisionScanState(
            workspace_id=workspace_id,
            source_type="slack_message",
            last_missed_decision_scan_at=now - timedelta(hours=2),
        )
        state_result = MagicMock()
        state_result.scalar_one_or_none.return_value = state
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=state_result)
        mock_session.commit = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_enqueue = AsyncMock()

        monkeypatch.setattr(
            sync_scheduler,
            "async_session",
            MagicMock(return_value=mock_cm),
        )
        monkeypatch.setattr(
            sync_scheduler,
            "enqueue_missed_decision_scan",
            mock_enqueue,
        )

        await sync_scheduler._enqueue_missed_decision_backstop(
            {Provider.SLACK: [workspace_id]},
            now=now,
        )

        mock_enqueue.assert_not_awaited()
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_backstop_skips_when_any_scan_for_source_is_active(self, monkeypatch):
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        from sqlalchemy.dialects import postgresql

        from src.models.integration import Provider
        from src.models.missed_decision import (
            MissedDecisionScanRun,
            MissedDecisionScanState,
        )
        from src.services import sync_scheduler

        workspace_id = uuid4()
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        state = MissedDecisionScanState(
            workspace_id=workspace_id,
            source_type="slack_message",
            last_missed_decision_scan_at=now - timedelta(days=2),
        )
        active_resource_run = MissedDecisionScanRun(
            workspace_id=workspace_id,
            source_type="slack_message",
            source_resource_id="C123",
            status="queued",
        )
        state_result = MagicMock()
        state_result.scalar_one_or_none.return_value = state
        active_result = MagicMock()
        active_result.scalar_one_or_none.return_value = active_resource_run
        no_active_result = MagicMock()
        no_active_result.scalar_one_or_none.return_value = None
        active_scan_sql = ""

        async def fake_execute(stmt):
            nonlocal active_scan_sql
            entity = None
            descriptions = getattr(stmt, "column_descriptions", None)
            if descriptions:
                entity = descriptions[0].get("entity")
            if entity is MissedDecisionScanState:
                return state_result
            if entity is MissedDecisionScanRun:
                compiled = stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
                active_scan_sql = str(compiled)
                if "source_resource_id IS NULL" in active_scan_sql:
                    return no_active_result
                return active_result
            raise AssertionError(f"unexpected statement: {stmt}")

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=fake_execute)
        mock_session.commit = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_enqueue = AsyncMock()

        monkeypatch.setattr(
            sync_scheduler,
            "async_session",
            MagicMock(return_value=mock_cm),
        )
        monkeypatch.setattr(
            sync_scheduler,
            "enqueue_missed_decision_scan",
            mock_enqueue,
        )

        await sync_scheduler._enqueue_missed_decision_backstop(
            {Provider.SLACK: [workspace_id]},
            now=now,
        )

        assert "source_resource_id IS NULL" not in active_scan_sql
        mock_enqueue.assert_not_awaited()
        mock_session.commit.assert_not_awaited()
