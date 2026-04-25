"""Unit tests for graph_scheduler service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.graph_scheduler import (
    seconds_until_next_03_utc,
    fetch_workspaces_with_graph_nodes,
    backfill_missing_workspaces,
)


class TestSecondsUntilNext03Utc:
    def test_returns_positive_seconds(self):
        s = seconds_until_next_03_utc()
        assert 0 < s <= 24 * 3600

    def test_at_03_returns_24h(self):
        # Mock datetime.now to be exactly 03:00:00 UTC
        with patch("src.services.graph_scheduler.datetime") as dt:
            now = datetime(2026, 4, 25, 3, 0, 0, tzinfo=timezone.utc)
            dt.now.return_value = now
            dt.timezone = timezone
            s = seconds_until_next_03_utc()
            assert s == 24 * 3600

    def test_before_03_returns_less_than_3h(self):
        with patch("src.services.graph_scheduler.datetime") as dt:
            now = datetime(2026, 4, 25, 1, 0, 0, tzinfo=timezone.utc)
            dt.now.return_value = now
            dt.timezone = timezone
            s = seconds_until_next_03_utc()
            assert s == 2 * 3600  # exactly 2h until 03:00


class TestBackfillMissingWorkspaces:
    @pytest.mark.asyncio
    async def test_skips_workspaces_with_existing_communities(self):
        ws1, ws2 = uuid.uuid4(), uuid.uuid4()

        async def fake_workspaces_with_nodes():
            return [ws1, ws2]

        async def fake_workspaces_with_communities():
            return {ws1}  # ws1 already done

        rebuilds: list[uuid.UUID] = []
        async def fake_rebuild(ws_id):
            rebuilds.append(ws_id)

        with patch(
            "src.services.graph_scheduler.fetch_workspaces_with_graph_nodes",
            new=AsyncMock(side_effect=fake_workspaces_with_nodes),
        ), patch(
            "src.services.graph_scheduler._fetch_workspaces_with_communities",
            new=AsyncMock(side_effect=fake_workspaces_with_communities),
        ), patch(
            "src.services.graph_scheduler._rebuild_for_workspace",
            new=AsyncMock(side_effect=fake_rebuild),
        ):
            await backfill_missing_workspaces()

        assert rebuilds == [ws2]
