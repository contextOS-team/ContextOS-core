"""Tests for _check_code_index_freshness polling branches.

Covers all branch outcomes:
1. Skip when status is "indexing" (already running)
2. Skip when last index is still fresh (within interval)
3. Enqueue when last index is stale (past interval)
4. Enqueue when last index timestamp is missing (never indexed)
5. Enqueue when timestamp is invalid/malformed
6. Skip when no integration or no config exists
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

WORKSPACE_ID = uuid4()


def _make_integration(config: dict | None) -> MagicMock:
    """Create a mock WorkspaceIntegration with the given config."""
    integration = MagicMock()
    integration.config = config
    return integration


def _mock_session_returning(integration):
    """Set up the mock async session context for _check_code_index_freshness."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = integration
    mock_session.execute.return_value = mock_result
    return mock_session


@pytest.mark.asyncio
async def test_skip_when_already_indexing():
    """Should skip enqueue when code_index_status is 'indexing'."""
    integration = _make_integration({
        "code_index_status": "indexing",
        "code_index_last_at": "2020-01-01T00:00:00",
    })
    mock_session = _mock_session_returning(integration)

    with (
        patch("src.services.sync_scheduler.async_session") as mock_ctx,
        patch(
            "src.services.code_index_worker.enqueue_workspace_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.sync_scheduler import _check_code_index_freshness
        await _check_code_index_freshness(WORKSPACE_ID)

    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_skip_when_still_fresh():
    """Should skip enqueue when last index was within CODE_INDEX_INTERVAL_SECONDS."""
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(minutes=30)).isoformat()

    integration = _make_integration({
        "code_index_status": "idle",
        "code_index_last_at": recent,
    })
    mock_session = _mock_session_returning(integration)

    with (
        patch("src.services.sync_scheduler.async_session") as mock_ctx,
        patch(
            "src.services.code_index_worker.enqueue_workspace_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.sync_scheduler import _check_code_index_freshness
        await _check_code_index_freshness(WORKSPACE_ID)

    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_when_stale():
    """Should enqueue when last index is older than CODE_INDEX_INTERVAL_SECONDS."""
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(hours=2)).isoformat()

    integration = _make_integration({
        "code_index_status": "idle",
        "code_index_last_at": stale,
    })
    mock_session = _mock_session_returning(integration)

    with (
        patch("src.services.sync_scheduler.async_session") as mock_ctx,
        patch(
            "src.services.code_index_worker.enqueue_workspace_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.sync_scheduler import _check_code_index_freshness
        await _check_code_index_freshness(WORKSPACE_ID)

    mock_enqueue.assert_called_once_with(WORKSPACE_ID)


@pytest.mark.asyncio
async def test_enqueue_when_never_indexed():
    """Should enqueue when code_index_last_at is missing (never indexed)."""
    integration = _make_integration({
        "code_index_status": "idle",
    })
    mock_session = _mock_session_returning(integration)

    with (
        patch("src.services.sync_scheduler.async_session") as mock_ctx,
        patch(
            "src.services.code_index_worker.enqueue_workspace_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.sync_scheduler import _check_code_index_freshness
        await _check_code_index_freshness(WORKSPACE_ID)

    mock_enqueue.assert_called_once_with(WORKSPACE_ID)


@pytest.mark.asyncio
async def test_enqueue_when_invalid_timestamp():
    """Should enqueue when code_index_last_at has an invalid format."""
    integration = _make_integration({
        "code_index_status": "idle",
        "code_index_last_at": "not-a-timestamp",
    })
    mock_session = _mock_session_returning(integration)

    with (
        patch("src.services.sync_scheduler.async_session") as mock_ctx,
        patch(
            "src.services.code_index_worker.enqueue_workspace_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.sync_scheduler import _check_code_index_freshness
        await _check_code_index_freshness(WORKSPACE_ID)

    mock_enqueue.assert_called_once_with(WORKSPACE_ID)


@pytest.mark.asyncio
async def test_skip_when_no_integration():
    """Should skip when no GitHub integration exists."""
    mock_session = _mock_session_returning(None)

    with (
        patch("src.services.sync_scheduler.async_session") as mock_ctx,
        patch(
            "src.services.code_index_worker.enqueue_workspace_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.sync_scheduler import _check_code_index_freshness
        await _check_code_index_freshness(WORKSPACE_ID)

    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_skip_when_no_config():
    """Should skip when integration has no config."""
    integration = _make_integration(None)
    mock_session = _mock_session_returning(integration)

    with (
        patch("src.services.sync_scheduler.async_session") as mock_ctx,
        patch(
            "src.services.code_index_worker.enqueue_workspace_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.sync_scheduler import _check_code_index_freshness
        await _check_code_index_freshness(WORKSPACE_ID)

    mock_enqueue.assert_not_called()
