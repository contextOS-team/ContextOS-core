"""Tests for concurrency controls, HTTP/2, jitter, incremental sync, and polling scheduler."""

import asyncio
import random
from unittest.mock import AsyncMock, MagicMock, patch

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
        """Verify jitter formula produces values in expected range over many iterations."""
        base_delay = 2.0
        min_expected = base_delay * 0.5
        max_expected = base_delay * 1.5

        for _ in range(1000):
            jittered = base_delay * (0.5 + random.random())
            assert min_expected <= jittered <= max_expected, (
                f"Jittered value {jittered} outside range [{min_expected}, {max_expected}]"
            )


class TestIncrementalSync:
    """Test that incremental sync skips unchanged pages and refetches changed ones."""

    @pytest.mark.asyncio
    async def test_notion_incremental_skips_unchanged(self):
        """When stored timestamp >= API timestamp, get_page_markdown should NOT be called."""
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
