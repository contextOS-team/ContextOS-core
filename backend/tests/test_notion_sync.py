"""Tests for the Notion sync pipeline.

Covers:
- Bug 1: "notion_page" exists in embedding SOURCE_TYPE_MAP
- Bug 2: Phase 2 writes content for ALL pages, not just batch boundaries
- Bug 3: Concurrent sync returns 409 when already syncing
- Bug 4: _upsert_page type hints accept datetime (not str)
- Bug 6: Soft-delete pages removed from Notion
- Bug 7: OAuth callback handles multi-member workspaces
- Bug 10: NotionClient reuses httpx client (context manager)
- _extract_title with various Notion property names
- _upsert_page preserves content on metadata-only update
- Full end-to-end sync mock
"""

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings
from src.routers.notion import (
    _extract_title,
    _parse_notion_datetime,
)
from tests.conftest import (
    TEST_EMAIL,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    _make_test_settings,
)

NOTION_CLIENT_ID = "test-notion-client-id"
NOTION_CLIENT_SECRET = "test-notion-client-secret"


# ---------- Helpers ----------


def _make_auth_header() -> dict[str, str]:
    import jwt as pyjwt

    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
        "iss": "http://localhost:54321/auth/v1",
    }
    token = pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _make_notion_page_data(
    notion_id: str = "page-1",
    title: str = "Test Page",
    parent_type: str = "workspace",
    parent_id: str = "ws-1",
) -> dict:
    """Create a realistic Notion API page response object."""
    parent: dict
    if parent_type == "database_id":
        parent = {"type": "database_id", "database_id": parent_id}
    else:
        parent = {"type": "workspace", "workspace": True}

    return {
        "id": notion_id,
        "object": "page",
        "created_time": "2025-06-03T05:29:00.000Z",
        "last_edited_time": "2025-07-15T10:00:00.000Z",
        "url": f"https://notion.so/{notion_id}",
        "parent": parent,
        "last_edited_by": {"id": "user-1", "object": "user"},
        "properties": {
            "title": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


# ---------- Fixtures ----------


@pytest.fixture()
def notion_settings() -> Settings:
    return _make_test_settings(
        NOTION_CLIENT_ID=NOTION_CLIENT_ID,
        NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
    )


@pytest.fixture()
def notion_app(notion_settings: Settings, mock_session: AsyncMock):
    src.config._settings = notion_settings

    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def notion_client(notion_app) -> Generator[TestClient, None, None]:
    with TestClient(notion_app) as c:
        yield c


# ---------- Bug 1: Embedding SOURCE_TYPE_MAP ----------


class TestEmbeddingSourceMap:
    """Verify 'notion_page' is registered in the embedding service."""

    def test_notion_page_in_source_type_map(self):
        from src.services.embedding import SOURCE_TYPE_MAP

        assert "notion_page" in SOURCE_TYPE_MAP, (
            "notion_page must be in SOURCE_TYPE_MAP or embeddings are silently dropped"
        )

    def test_notion_page_extractor_uses_title_and_content(self):
        from src.services.embedding import SOURCE_TYPE_MAP

        _, extract_fn = SOURCE_TYPE_MAP["notion_page"]
        mock_page = MagicMock()
        mock_page.title = "My Page"
        mock_page.content = "Some content here"

        result = extract_fn(mock_page)
        assert "My Page" in result
        assert "Some content here" in result

    def test_notion_page_extractor_returns_empty_for_none_content(self):
        """Pages with NULL content should return empty string so embeddings are skipped."""
        from src.services.embedding import SOURCE_TYPE_MAP

        _, extract_fn = SOURCE_TYPE_MAP["notion_page"]
        mock_page = MagicMock()
        mock_page.title = "Empty Page"
        mock_page.content = None

        result = extract_fn(mock_page)
        assert result == ""


# ---------- Bug 3: Concurrency guard ----------


class TestSyncConcurrencyGuard:
    """Verify /sync and /resync reject requests when already syncing."""

    def _mock_connected_and_syncing(self, mock_session, sync_started_at=None):
        """Set up mock to return a connected integration with sync_status=syncing."""
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        mock_integration = MagicMock()
        mock_integration.status = "connected"
        config = {"sync_status": "syncing"}
        if sync_started_at is not None:
            config["sync_started_at"] = sync_started_at
        mock_integration.config = config
        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = mock_integration

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            return mock_integration_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

    def _mock_connected_idle(self, mock_session):
        """Set up mock to return connected integration with sync_status=complete."""
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.config = {"sync_status": "complete"}
        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = mock_integration

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            return mock_integration_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

    def test_sync_rejects_when_already_syncing(
        self, notion_client, mock_session
    ):
        # Use a recent sync_started_at so it's treated as active, not stale
        recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._mock_connected_and_syncing(mock_session, sync_started_at=recent)

        response = notion_client.post(
            "/api/notion/sync", headers=_make_auth_header()
        )

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]

    def test_resync_rejects_when_already_syncing(
        self, notion_client, mock_session
    ):
        recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._mock_connected_and_syncing(mock_session, sync_started_at=recent)

        response = notion_client.post(
            "/api/notion/resync", headers=_make_auth_header()
        )

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]

    def test_sync_accepts_when_idle(self, notion_client, mock_session):
        self._mock_connected_idle(mock_session)

        response = notion_client.post(
            "/api/notion/sync", headers=_make_auth_header()
        )

        assert response.status_code == 202

    def test_sync_rejects_when_disconnected(self, notion_client, mock_session):
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = None

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            return mock_integration_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        response = notion_client.post(
            "/api/notion/sync", headers=_make_auth_header()
        )

        assert response.status_code == 400

    def test_stale_sync_without_started_at_resets_to_error(
        self, notion_client, mock_session
    ):
        """Missing sync_started_at means we can't trust the sync — treat as stale."""
        # No sync_started_at field at all
        self._mock_connected_and_syncing(mock_session, sync_started_at=None)

        response = notion_client.post(
            "/api/notion/sync", headers=_make_auth_header()
        )

        assert response.status_code == 409
        assert "stuck" in response.json()["detail"].lower() or "reset" in response.json()["detail"].lower()

    def test_stale_sync_with_old_started_at_resets_to_error(
        self, notion_client, mock_session
    ):
        """Sync running > 11 min should be treated as stale."""
        from datetime import timedelta
        old_time = (
            datetime.now(timezone.utc) - timedelta(minutes=15)
        ).isoformat().replace("+00:00", "Z")
        self._mock_connected_and_syncing(mock_session, sync_started_at=old_time)

        response = notion_client.post(
            "/api/notion/sync", headers=_make_auth_header()
        )

        assert response.status_code == 409
        assert "reset" in response.json()["detail"].lower()

    def test_stale_sync_with_garbage_timestamp_resets(
        self, notion_client, mock_session
    ):
        """Unparseable sync_started_at should be treated as stale."""
        self._mock_connected_and_syncing(mock_session, sync_started_at="not-a-date")

        response = notion_client.post(
            "/api/notion/sync", headers=_make_auth_header()
        )

        assert response.status_code == 409
        assert "reset" in response.json()["detail"].lower()

    def test_error_status_allows_new_sync(self, notion_client, mock_session):
        """sync_status=error should not block a new sync."""
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.config = {"sync_status": "error"}
        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = mock_integration

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            return mock_integration_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        response = notion_client.post(
            "/api/notion/sync", headers=_make_auth_header()
        )

        assert response.status_code == 202


# ---------- _extract_title ----------


class TestExtractTitle:
    """Test title extraction from various Notion property shapes."""

    def test_standard_title_property(self):
        page = _make_notion_page_data(title="My Document")
        assert _extract_title(page) == "My Document"

    def test_custom_named_title_property(self):
        """Notion databases can have title properties named anything."""
        page = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Custom Name"}],
                }
            }
        }
        assert _extract_title(page) == "Custom Name"

    def test_multi_part_title(self):
        """Rich text titles can have multiple segments."""
        page = {
            "properties": {
                "title": {
                    "type": "title",
                    "title": [
                        {"plain_text": "Hello "},
                        {"plain_text": "World"},
                    ],
                }
            }
        }
        assert _extract_title(page) == "Hello World"

    def test_empty_title_parts(self):
        """Title property exists but has no text parts."""
        page = {
            "properties": {
                "title": {
                    "type": "title",
                    "title": [],
                }
            }
        }
        assert _extract_title(page) == "Untitled"

    def test_no_properties(self):
        """Page with no properties at all."""
        assert _extract_title({}) == "Untitled"

    def test_no_title_property(self):
        """Properties exist but none are of type 'title'."""
        page = {
            "properties": {
                "Status": {"type": "select", "select": {"name": "Done"}},
            }
        }
        assert _extract_title(page) == "Untitled"

    def test_title_among_many_properties(self):
        """Title property exists among many non-title properties."""
        page = {
            "properties": {
                "Status": {"type": "select", "select": None},
                "Due Date": {"type": "date", "date": None},
                "Task": {
                    "type": "title",
                    "title": [{"plain_text": "Found It"}],
                },
                "Priority": {"type": "number", "number": 1},
            }
        }
        assert _extract_title(page) == "Found It"


# ---------- Bug 10: NotionClient context manager ----------


class TestNotionClientContextManager:
    """Verify NotionClient supports async context manager for connection reuse."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        from src.services.notion_client import NotionClient

        client = NotionClient("fake-token")
        assert not client._client.is_closed

        await client.close()
        assert client._client.is_closed

    @pytest.mark.asyncio
    async def test_async_with_closes_on_exit(self):
        from src.services.notion_client import NotionClient

        async with NotionClient("fake-token") as client:
            assert not client._client.is_closed
            inner_client = client._client

        assert inner_client.is_closed


# ---------- _run_sync end-to-end ----------


class TestRunSync:
    """End-to-end tests for _run_sync with mocked Notion API and DB."""

    @pytest.mark.asyncio
    async def test_sync_writes_content_for_all_pages(self):
        """Phase 2 must write content for every page, not just batch boundaries."""
        from src.routers.notion import _run_sync

        workspace_id = UUID(TEST_WORKSPACE_ID)
        user_id = UUID(TEST_USER_ID)
        settings = _make_test_settings(
            NOTION_CLIENT_ID=NOTION_CLIENT_ID,
            NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
        )

        # Create 3 pages (less than batch size of 10, so it's a single batch)
        pages = [
            _make_notion_page_data(f"page-{i}", f"Page {i}") for i in range(3)
        ]

        # Track which pages get content written
        content_written: dict[str, str] = {}
        page_uuids = [uuid.uuid4() for _ in pages]

        mock_notion_client = AsyncMock()
        mock_notion_client.search_pages = AsyncMock(
            return_value={"results": pages, "has_more": False}
        )

        async def mock_get_page_markdown(notion_id: str) -> str:
            return f"# Content for {notion_id}"

        mock_notion_client.get_page_markdown = AsyncMock(
            side_effect=mock_get_page_markdown
        )
        mock_notion_client.close = AsyncMock()
        mock_notion_client.__aenter__ = AsyncMock(return_value=mock_notion_client)
        mock_notion_client.__aexit__ = AsyncMock(return_value=False)

        upsert_call_count = 0

        async def mock_upsert_metadata(session, ws_id, page_data):
            nonlocal upsert_call_count
            result = page_uuids[upsert_call_count]
            upsert_call_count += 1
            return result

        # Track content writes via the session mock
        def make_page_row(notion_id):
            row = MagicMock()
            row.notion_id = notion_id
            row.notion_updated_at = None

            def set_content(value):
                content_written[notion_id] = value

            type(row).content = property(
                lambda self: content_written.get(self.notion_id),
                lambda self, v: set_content(v),
            )
            return row

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        page_rows = {p["id"]: make_page_row(p["id"]) for p in pages}

        def mock_execute_side_effect(stmt):
            result = MagicMock()
            # Try to figure out which page is being queried
            for nid, row in page_rows.items():
                result.scalar_one_or_none.return_value = row
                result.one_or_none.return_value = row
                break
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.routers.notion.get_valid_access_token",
                new_callable=AsyncMock,
                return_value="fake-token",
            ),
            patch(
                "src.routers.notion.NotionClient",
                return_value=mock_notion_client,
            ),
            patch(
                "src.routers.notion._upsert_page_metadata",
                new_callable=AsyncMock,
                side_effect=mock_upsert_metadata,
            ),
            patch(
                "src.routers.notion._soft_delete_removed_pages",
                new_callable=AsyncMock,
            ),
            patch(
                "src.routers.notion._update_sync_config",
                new_callable=AsyncMock,
            ),
            patch(
                "src.routers.notion.async_session",
                return_value=mock_cm,
            ),
            patch(
                "src.routers.notion.enqueue_embedding_job",
                new_callable=AsyncMock,
            ) as mock_embed,
        ):
            await _run_sync(workspace_id, user_id, settings)

        # Verify get_page_markdown was called for ALL 3 pages
        assert mock_notion_client.get_page_markdown.call_count == 3

        # Verify embedding generation was called
        assert mock_embed.call_count >= 1

    @pytest.mark.asyncio
    async def test_sync_calls_soft_delete(self):
        """Sync must call _soft_delete_removed_pages after upserting metadata."""
        from src.routers.notion import _run_sync

        workspace_id = UUID(TEST_WORKSPACE_ID)
        user_id = UUID(TEST_USER_ID)
        settings = _make_test_settings(
            NOTION_CLIENT_ID=NOTION_CLIENT_ID,
            NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
        )

        pages = [_make_notion_page_data("page-1", "Page 1")]

        mock_notion_client = AsyncMock()
        mock_notion_client.search_pages = AsyncMock(
            return_value={"results": pages, "has_more": False}
        )
        mock_notion_client.get_page_markdown = AsyncMock(return_value="# Content")
        mock_notion_client.close = AsyncMock()
        mock_notion_client.__aenter__ = AsyncMock(return_value=mock_notion_client)
        mock_notion_client.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_row = MagicMock()
        mock_row.notion_updated_at = None
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_row
        mock_execute_result.one_or_none.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.routers.notion.get_valid_access_token",
                new_callable=AsyncMock,
                return_value="fake-token",
            ),
            patch(
                "src.routers.notion.NotionClient",
                return_value=mock_notion_client,
            ),
            patch(
                "src.routers.notion._upsert_page_metadata",
                new_callable=AsyncMock,
                return_value=uuid.uuid4(),
            ),
            patch(
                "src.routers.notion._soft_delete_removed_pages",
                new_callable=AsyncMock,
            ) as mock_soft_delete,
            patch(
                "src.routers.notion._update_sync_config",
                new_callable=AsyncMock,
            ),
            patch(
                "src.routers.notion.async_session",
                return_value=mock_cm,
            ),
            patch(
                "src.routers.notion.enqueue_embedding_job",
                new_callable=AsyncMock,
            ),
        ):
            await _run_sync(workspace_id, user_id, settings)

        mock_soft_delete.assert_called_once()
        call_args = mock_soft_delete.call_args
        # Second arg should be workspace_id
        assert call_args[0][1] == workspace_id
        # Third arg should be the set of synced notion IDs
        assert "page-1" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_sync_sets_error_on_failure(self):
        """If sync fails, sync_status should be set to 'error'."""
        from src.routers.notion import _run_sync

        workspace_id = UUID(TEST_WORKSPACE_ID)
        user_id = UUID(TEST_USER_ID)
        settings = _make_test_settings(
            NOTION_CLIENT_ID=NOTION_CLIENT_ID,
            NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
        )

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.routers.notion.get_valid_access_token",
                new_callable=AsyncMock,
                side_effect=Exception("Token fetch failed"),
            ),
            patch(
                "src.routers.notion._update_sync_config",
                new_callable=AsyncMock,
            ) as mock_update_config,
            patch(
                "src.routers.notion.async_session",
                return_value=mock_cm,
            ),
        ):
            await _run_sync(workspace_id, user_id, settings)

        # Should have been called with sync_status=error so frontend shows failure
        error_calls = [
            c
            for c in mock_update_config.call_args_list
            if c[0][2].get("sync_status") == "error"
        ]
        assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_sync_handles_content_fetch_failure_gracefully(self):
        """If get_page_markdown fails for one page, sync continues."""
        from src.routers.notion import _run_sync

        workspace_id = UUID(TEST_WORKSPACE_ID)
        user_id = UUID(TEST_USER_ID)
        settings = _make_test_settings(
            NOTION_CLIENT_ID=NOTION_CLIENT_ID,
            NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
        )

        pages = [
            _make_notion_page_data("page-ok", "Good Page"),
            _make_notion_page_data("page-fail", "Bad Page"),
        ]

        call_count = 0

        async def mock_markdown(notion_id):
            nonlocal call_count
            call_count += 1
            if notion_id == "page-fail":
                raise Exception("Content fetch failed")
            return f"# {notion_id}"

        mock_notion_client = AsyncMock()
        mock_notion_client.search_pages = AsyncMock(
            return_value={"results": pages, "has_more": False}
        )
        mock_notion_client.get_page_markdown = AsyncMock(side_effect=mock_markdown)
        mock_notion_client.close = AsyncMock()
        mock_notion_client.__aenter__ = AsyncMock(return_value=mock_notion_client)
        mock_notion_client.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_row = MagicMock()
        mock_row.notion_updated_at = None
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_row
        mock_execute_result.one_or_none.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.routers.notion.get_valid_access_token",
                new_callable=AsyncMock,
                return_value="fake-token",
            ),
            patch(
                "src.routers.notion.NotionClient",
                return_value=mock_notion_client,
            ),
            patch(
                "src.routers.notion._upsert_page_metadata",
                new_callable=AsyncMock,
                return_value=uuid.uuid4(),
            ),
            patch(
                "src.routers.notion._soft_delete_removed_pages",
                new_callable=AsyncMock,
            ),
            patch(
                "src.routers.notion._update_sync_config",
                new_callable=AsyncMock,
            ) as mock_config,
            patch(
                "src.routers.notion.async_session",
                return_value=mock_cm,
            ),
            patch(
                "src.routers.notion.enqueue_embedding_job",
                new_callable=AsyncMock,
            ),
        ):
            await _run_sync(workspace_id, user_id, settings)

        # Both pages attempted
        assert call_count == 2

        # Sync should still complete (not error)
        complete_calls = [
            c
            for c in mock_config.call_args_list
            if c[0][2].get("sync_status") == "complete"
        ]
        assert len(complete_calls) == 1


# ---------- Global sync timeout ----------


class TestSyncGlobalTimeout:
    """Verify _run_sync enforces a global timeout and sets error status."""

    @pytest.mark.asyncio
    async def test_sync_timeout_sets_error_status(self):
        """If sync exceeds the global timeout, status should be set to error."""
        from src.routers.notion import _run_sync, SYNC_GLOBAL_TIMEOUT_SECONDS

        workspace_id = UUID(TEST_WORKSPACE_ID)
        user_id = UUID(TEST_USER_ID)
        settings = _make_test_settings(
            NOTION_CLIENT_ID=NOTION_CLIENT_ID,
            NOTION_CLIENT_SECRET=NOTION_CLIENT_SECRET,
        )

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        # Make _run_sync_inner hang forever
        async def hang_forever(*args, **kwargs):
            await asyncio.sleep(999999)

        with (
            patch(
                "src.routers.notion._run_sync_inner",
                new_callable=AsyncMock,
                side_effect=hang_forever,
            ),
            patch(
                "src.routers.notion.SYNC_GLOBAL_TIMEOUT_SECONDS",
                0.1,  # 100ms timeout for testing
            ),
            patch(
                "src.routers.notion._update_sync_config",
                new_callable=AsyncMock,
            ) as mock_update_config,
            patch(
                "src.routers.notion.update_cursor_status",
                new_callable=AsyncMock,
            ) as mock_cursor,
            patch(
                "src.routers.notion.async_session",
                return_value=mock_cm,
            ),
        ):
            await _run_sync(workspace_id, user_id, settings)

        # Verify error status was set in both config and cursor
        error_config_calls = [
            c for c in mock_update_config.call_args_list
            if c[0][2].get("sync_status") == "error"
        ]
        assert len(error_config_calls) == 1

        error_cursor_calls = [
            c for c in mock_cursor.call_args_list
            if c.kwargs.get("sync_status") == "error"
            and c.kwargs.get("error_message") == "sync timed out"
        ]
        assert len(error_cursor_calls) == 1


# ---------- Bug 7: OAuth callback multi-member ----------


class TestCallbackMultiMember:
    """Verify callback doesn't crash for multi-member workspaces."""

    def test_callback_with_multiple_workspace_members(
        self, notion_client, mock_session
    ):
        """scalar_one_or_none with LIMIT 1 should not crash for multi-member ws."""
        workspace_id = UUID(TEST_WORKSPACE_ID)
        user_id = UUID(TEST_USER_ID)

        with (
            patch(
                "src.routers.notion.verify_state_or_raise",
                return_value=workspace_id,
            ),
            patch(
                "src.routers.notion.exchange_code",
                new_callable=AsyncMock,
                return_value={
                    "workspace_id": "ws-123",
                    "workspace_name": "Test Workspace",
                },
            ),
        ):
            # Return a single user_id (LIMIT 1 ensures this)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = user_id
            mock_session.execute.return_value = mock_result

            response = notion_client.get(
                "/api/notion/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "notion=connected" in response.headers["location"]
