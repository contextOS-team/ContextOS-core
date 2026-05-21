"""Tests for sync_adapter protocol, state helpers, and SyncRunLogger.

Covers:
- get_or_create_cursor: creates new cursor, returns existing
- update_cursor_status: syncing, complete (sets last_sync_at), error (records message)
- get_cursor_status: returns idle for missing cursor
- SyncRunLogger: generates unique run_id
- SyncAdapter protocol conformance for Notion, Linear, GitHub services
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.sync import SyncCursor
from src.services.sync_adapter import (
    SyncAdapter,
    SyncRunLogger,
    get_cursor_status,
    get_or_create_cursor,
    mark_sync_requested,
    update_cursor_status,
)


# ---------- Helpers ----------


def _make_mock_session(cursor_to_return=None):
    """Create a mock async session that returns the given cursor on execute."""
    session = AsyncMock()
    session.add = MagicMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = cursor_to_return
    session.execute = AsyncMock(return_value=mock_result)
    session.flush = AsyncMock()

    return session


# ---------- get_or_create_cursor ----------


class TestGetOrCreateCursor:
    """Tests for get_or_create_cursor helper."""

    @pytest.mark.asyncio
    async def test_creates_new_cursor(self):
        """First call creates a cursor when none exists."""
        session = _make_mock_session(cursor_to_return=None)
        workspace_id = uuid.uuid4()

        cursor = await get_or_create_cursor(
            session, workspace_id, "notion", "default"
        )

        assert cursor is not None
        assert cursor.provider == "notion"
        assert cursor.workspace_id == workspace_id
        assert cursor.resource_type == "default"
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_existing_cursor(self):
        """Second call returns the same cursor without creating a new one."""
        existing_cursor = SyncCursor(
            workspace_id=uuid.uuid4(),
            provider="notion",
            resource_type="default",
            sync_status="idle",
        )
        session = _make_mock_session(cursor_to_return=existing_cursor)

        cursor = await get_or_create_cursor(
            session, existing_cursor.workspace_id, "notion", "default"
        )

        assert cursor is existing_cursor
        session.add.assert_not_called()


# ---------- update_cursor_status ----------


class TestMarkSyncRequested:
    """Tests for integration config sync-request state."""

    def test_sets_in_progress_and_resets_progress_counter(self):
        integration = MagicMock()
        integration.config = {
            "sync_status": "complete",
            "tickets_synced": 12,
            "synced_teams": ["team-1"],
        }

        mark_sync_requested(integration, "tickets_synced")

        assert integration.config == {
            "sync_status": "in_progress",
            "tickets_synced": 0,
            "synced_teams": ["team-1"],
        }


class TestUpdateCursorStatus:
    """Tests for update_cursor_status helper."""

    @pytest.mark.asyncio
    async def test_syncing_status(self):
        """Sets status to syncing and clears error_message."""
        existing_cursor = SyncCursor(
            workspace_id=uuid.uuid4(),
            provider="linear",
            resource_type="default",
            sync_status="idle",
            error_message="old error",
        )
        session = _make_mock_session(cursor_to_return=existing_cursor)

        await update_cursor_status(
            session, existing_cursor.workspace_id, "linear", "default",
            sync_status="syncing",
        )

        assert existing_cursor.sync_status == "syncing"
        assert existing_cursor.error_message is None

    @pytest.mark.asyncio
    async def test_complete_sets_last_sync_at(self):
        """Complete status sets last_sync_at timestamp and clears error."""
        existing_cursor = SyncCursor(
            workspace_id=uuid.uuid4(),
            provider="notion",
            resource_type="default",
            sync_status="syncing",
        )
        session = _make_mock_session(cursor_to_return=existing_cursor)

        await update_cursor_status(
            session, existing_cursor.workspace_id, "notion", "default",
            sync_status="complete",
            records_synced=42,
        )

        assert existing_cursor.sync_status == "complete"
        assert existing_cursor.records_synced == 42
        assert existing_cursor.last_sync_at is not None
        assert isinstance(existing_cursor.last_sync_at, datetime)
        assert existing_cursor.error_message is None

    @pytest.mark.asyncio
    async def test_error_records_message(self):
        """Error status stores the error message."""
        existing_cursor = SyncCursor(
            workspace_id=uuid.uuid4(),
            provider="github",
            resource_type="org/repo",
            sync_status="syncing",
        )
        session = _make_mock_session(cursor_to_return=existing_cursor)

        await update_cursor_status(
            session, existing_cursor.workspace_id, "github", "org/repo",
            sync_status="error",
            error_message="rate limited",
        )

        assert existing_cursor.sync_status == "error"
        assert existing_cursor.error_message == "rate limited"


# ---------- get_cursor_status ----------


class TestGetCursorStatus:
    """Tests for get_cursor_status helper."""

    @pytest.mark.asyncio
    async def test_returns_idle_for_missing(self):
        """No cursor returns idle status dict."""
        session = _make_mock_session(cursor_to_return=None)
        workspace_id = uuid.uuid4()

        status = await get_cursor_status(
            session, workspace_id, "notion", "default"
        )

        assert status["sync_status"] == "idle"
        assert status["records_synced"] == 0
        assert status["last_sync_at"] is None
        assert status["error_message"] is None


# ---------- SyncRunLogger ----------


class TestSyncRunLogger:
    """Tests for SyncRunLogger context manager."""

    @pytest.mark.asyncio
    async def test_generates_unique_run_id(self):
        """Each SyncRunLogger instance gets a unique run_id."""
        workspace_id = uuid.uuid4()
        srl1 = SyncRunLogger("notion", workspace_id)
        srl2 = SyncRunLogger("notion", workspace_id)

        assert srl1.run_id != srl2.run_id
        assert len(srl1.run_id) == 36  # UUID format
        assert srl1.provider == "notion"
        assert srl1.workspace_id == str(workspace_id)

    @pytest.mark.asyncio
    async def test_context_manager_sets_run_id(self):
        """Entering context sets the run_id, exiting clears it."""
        from src.services.sync_adapter import _sync_run_id_var

        workspace_id = uuid.uuid4()
        srl = SyncRunLogger("linear", workspace_id)

        async with srl:
            assert _sync_run_id_var.get() == srl.run_id

        assert _sync_run_id_var.get() == ""


# ---------- SyncAdapter protocol conformance ----------


class TestSyncAdapterConformance:
    """Verify all sync services conform to the SyncAdapter protocol."""

    def test_notion_sync_service_conforms(self):
        """NotionSyncService satisfies SyncAdapter protocol."""
        from src.services.notion_sync import NotionSyncService

        service = NotionSyncService()
        assert isinstance(service, SyncAdapter)
        assert service.provider == "notion"

    def test_linear_sync_service_conforms(self):
        """LinearSyncService satisfies SyncAdapter protocol."""
        from src.services.linear_sync import LinearSyncService

        service = LinearSyncService()
        assert isinstance(service, SyncAdapter)
        assert service.provider == "linear"

    def test_github_sync_service_conforms(self):
        """GitHubSyncService satisfies SyncAdapter protocol."""
        from src.services.github_sync import GitHubSyncService

        service = GitHubSyncService()
        assert isinstance(service, SyncAdapter)
        assert service.provider == "github"
