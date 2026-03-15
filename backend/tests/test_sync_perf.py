"""Tests for Phase 31 concurrent sync and indexing optimizations.

Covers: concurrent note/review fetching, incremental cursors, commit persistence,
embedding scoping, timeout isolation, concurrent code indexing, and provider-filtered
index status.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import UUID

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WS_UUID = UUID(TEST_WORKSPACE_ID)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mr_data(iid: int, gitlab_id: int, project_id: int = 100) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "id": gitlab_id,
        "iid": iid,
        "title": f"MR !{iid}",
        "description": None,
        "state": "opened",
        "draft": False,
        "author": {"username": "dev", "id": 1},
        "source_branch": f"feat/mr-{iid}",
        "target_branch": "main",
        "reviewers": [],
        "references": {"full": f"group/project!{iid}"},
        "web_url": f"https://gitlab.com/group/project/-/merge_requests/{iid}",
        "created_at": (now - timedelta(days=5)).isoformat() + "Z",
        "updated_at": now.isoformat() + "Z",
        "merged_at": None,
    }


def _make_note_data(note_id: int, body: str = "Looks good") -> dict:
    return {
        "id": note_id,
        "system": False,
        "body": body,
        "author": {"username": "reviewer"},
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


def _mock_httpx_client(mr_data_list, note_data_list=None):
    """Create a mock httpx client that returns MR list + notes."""
    if note_data_list is None:
        note_data_list = []

    mr_response = MagicMock()
    mr_response.status_code = 200
    mr_response.headers = {}
    mr_response.json.return_value = mr_data_list

    note_response = MagicMock()
    note_response.status_code = 200
    note_response.headers = {}
    note_response.json.return_value = note_data_list

    async def mock_get(url, **kwargs):
        if "/notes" in url:
            return note_response
        return mr_response

    client = MagicMock()
    client.get = AsyncMock(side_effect=mock_get)
    return client


def _mock_session():
    """Return a mock session that handles upsert/select patterns in gitlab_sync."""
    session = AsyncMock()
    mr_uuid = uuid.uuid4()

    mock_mr = MagicMock()
    mock_mr.id = mr_uuid
    mock_mr.project_id = 100

    # Every execute call returns a result where:
    # - scalar_one() returns mr_uuid (for INSERT RETURNING) or mock_mr (for SELECT)
    # - scalar_one_or_none() returns None (for cursor/integration lookups)
    # - fetchall() returns [(mr_uuid,)] (for embedding ID queries)
    #
    # _upsert_mr flow: execute(insert) → scalar_one() → flush → execute(select) → scalar_one()
    # We detect insert vs select by tracking call parity per upsert cycle.
    call_idx = {"n": 0}

    async def mock_execute(stmt, *args, **kwargs):
        call_idx["n"] += 1
        result = MagicMock()
        # _upsert_mr: call 1 = INSERT RETURNING (needs UUID), call 2 = SELECT (needs MR obj)
        # _upsert_review: same pattern with review UUID
        # Other calls (cursor, status, embedding queries): need scalar_one_or_none/fetchall
        if call_idx["n"] % 2 == 1:
            result.scalar_one.return_value = mr_uuid
        else:
            result.scalar_one.return_value = mock_mr
        result.scalar_one_or_none.return_value = None
        result.fetchall.return_value = [(mr_uuid,)]
        return result

    session.execute = AsyncMock(side_effect=mock_execute)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session, mr_uuid, mock_mr


# Shared patches for sync_single_project
def _make_mock_mr(mr_uuid):
    """Create a mock MR record with .id attribute."""
    mr = MagicMock()
    mr.id = mr_uuid
    mr.project_id = 100
    return mr


def _sync_patches(httpx_client, mr_uuid=None, extra_patches=None):
    """Return a list of context managers for common sync_single_project patches."""
    mock_mr = _make_mock_mr(mr_uuid or uuid.uuid4())
    patches = [
        patch("src.services.gitlab_sync.ensure_valid_token", new_callable=AsyncMock, return_value="token"),
        patch("httpx.AsyncClient.__aenter__", return_value=httpx_client),
        patch("src.services.gitlab_sync.link_mr_to_ticket", new_callable=AsyncMock),
        patch("src.services.embedding_worker.enqueue_embedding_job", new_callable=AsyncMock),
        patch("src.services.gitlab_sync._upsert_mr", new_callable=AsyncMock, return_value=mock_mr),
        patch("src.services.gitlab_sync._upsert_review", new_callable=AsyncMock),
    ]
    if extra_patches:
        patches.extend(extra_patches)
    return patches


# ---------------------------------------------------------------------------
# Test 1: Concurrent note fetching via asyncio.gather with Semaphore(5)
# ---------------------------------------------------------------------------


class TestGitlabConcurrentNoteFetch:

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Verify the note fetch semaphore caps at 5 concurrent requests."""
        from src.services.gitlab_sync import _fetch_notes_bounded, _NOTE_FETCH_SEMAPHORE

        assert _NOTE_FETCH_SEMAPHORE._value == 5

        active = 0
        max_active = 0

        async def mock_fetch(client, token, project_id, mr_iid):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return [_make_note_data(mr_iid * 100)]

        mock_client = AsyncMock()

        with patch("src.services.gitlab_sync._fetch_notes", new=mock_fetch):
            tasks = [_fetch_notes_bounded(mock_client, "token", 100, iid) for iid in range(1, 8)]
            results = await asyncio.gather(*tasks)

        assert len(results) == 7
        assert max_active >= 2, "Should run at least 2 tasks concurrently"
        assert max_active <= 5, "Semaphore should cap at 5"

    @pytest.mark.asyncio
    async def test_gather_used_for_notes(self):
        """sync_single_project uses asyncio.gather for note fetching."""
        from src.services.gitlab_sync import sync_single_project

        session, mr_uuid, mock_mr = _mock_session()
        settings = MagicMock()
        client = _mock_httpx_client(
            [_make_mr_data(1, 1001), _make_mr_data(2, 1002)],
            [_make_note_data(5001)],
        )

        gather_called = False
        real_gather = asyncio.gather

        async def tracking_gather(*coros, **kwargs):
            nonlocal gather_called
            if coros:  # only flag when there are actual coroutines (note tasks)
                gather_called = True
            return await real_gather(*coros, **kwargs)

        patches = _sync_patches(client, mr_uuid, [
            patch("src.services.gitlab_sync.asyncio.gather", side_effect=tracking_gather),
        ])
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            mr_count, review_count = await sync_single_project(WS_UUID, 100, session, settings)

        assert mr_count == 2
        assert gather_called, "asyncio.gather must be used for concurrent note fetching"


# ---------------------------------------------------------------------------
# Test 2: Incremental cursor
# ---------------------------------------------------------------------------


class TestIncrementalCursor:

    @pytest.mark.asyncio
    async def test_first_sync_uses_backfill_second_uses_cursor(self):
        """First sync uses 60-day backfill; second uses stored cursor_value."""
        from src.services.gitlab_sync import sync_single_project, BACKFILL_DAYS

        session, mr_uuid, mock_mr = _mock_session()
        settings = MagicMock()

        requested_urls: list[str] = []

        async def capturing_get(url, **kwargs):
            requested_urls.append(url)
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {}
            resp.json.return_value = []
            return resp

        client = MagicMock()
        client.get = AsyncMock(side_effect=capturing_get)

        # First call: no cursor (initial sync)
        first_cursor = MagicMock()
        first_cursor.cursor_value = None

        # Second call: stored cursor
        stored_ts = "2026-02-01T10:00:00Z"
        second_cursor = MagicMock()
        second_cursor.cursor_value = stored_ts

        cursor_iter = iter([first_cursor, second_cursor])

        async def mock_get_cursor(sess, ws_id, provider, resource_type):
            return next(cursor_iter)

        extra = [
            patch("src.services.gitlab_sync.get_or_create_cursor", side_effect=mock_get_cursor),
            patch("src.services.gitlab_sync.update_cursor_status", new_callable=AsyncMock),
            patch("src.services.embedding_worker.enqueue_embedding_job", new_callable=AsyncMock),
        ]

        with (
            patch("src.services.gitlab_sync.ensure_valid_token", new_callable=AsyncMock, return_value="token"),
            patch("httpx.AsyncClient.__aenter__", return_value=client),
            patch("src.services.gitlab_sync.link_mr_to_ticket", new_callable=AsyncMock),
            extra[0], extra[1], extra[2],
        ):
            # First sync
            await sync_single_project(WS_UUID, 100, session, settings)
            first_url = requested_urls[0]

            # Verify 60-day backfill
            ua_param = [p for p in first_url.split("&") if "updated_after=" in p][0]
            ua_value = ua_param.split("=")[1]
            ua_dt = datetime.strptime(ua_value, "%Y-%m-%dT%H:%M:%SZ")
            expected_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=BACKFILL_DAYS)
            assert abs((ua_dt - expected_cutoff).total_seconds()) < 5

            # Second sync
            requested_urls.clear()
            await sync_single_project(WS_UUID, 100, session, settings)
            second_url = requested_urls[0]
            assert stored_ts in second_url, f"Second sync should use cursor '{stored_ts}', got: {second_url}"


# ---------------------------------------------------------------------------
# Test 3: Commit persists MRs
# ---------------------------------------------------------------------------


class TestCommitPersistence:

    @pytest.mark.asyncio
    async def test_commit_called_after_sync(self):
        """session.commit() is called to persist MR data."""
        from src.services.gitlab_sync import sync_single_project

        session, mr_uuid, mock_mr = _mock_session()
        settings = MagicMock()
        client = _mock_httpx_client([_make_mr_data(1, 2001)])

        patches = _sync_patches(client, mr_uuid)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            mr_count, _ = await sync_single_project(WS_UUID, 100, session, settings)

        assert mr_count == 1
        session.commit.assert_called()


# ---------------------------------------------------------------------------
# Test 4: Review embedding scoped to project
# ---------------------------------------------------------------------------


class TestReviewEmbeddingScope:

    @pytest.mark.asyncio
    async def test_embedding_enqueue_uses_project_mr_ids(self):
        """Embedding enqueue filters reviews by project's MR IDs, not all reviews."""
        from src.services.gitlab_sync import sync_single_project

        session, mr_uuid, mock_mr = _mock_session()
        settings = MagicMock()
        client = _mock_httpx_client([_make_mr_data(1, 3001)], [_make_note_data(6001)])

        enqueue_calls: list[tuple] = []

        async def mock_enqueue(workspace_id, source_type, source_ids):
            enqueue_calls.append((source_type, list(source_ids)))

        mock_mr = _make_mock_mr(mr_uuid)
        patches = [
            patch("src.services.gitlab_sync.ensure_valid_token", new_callable=AsyncMock, return_value="token"),
            patch("httpx.AsyncClient.__aenter__", return_value=client),
            patch("src.services.gitlab_sync.link_mr_to_ticket", new_callable=AsyncMock),
            patch("src.services.embedding_worker.enqueue_embedding_job", side_effect=mock_enqueue),
            patch("src.services.gitlab_sync._upsert_mr", new_callable=AsyncMock, return_value=mock_mr),
            patch("src.services.gitlab_sync._upsert_review", new_callable=AsyncMock),
        ]
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            await sync_single_project(WS_UUID, 100, session, settings)

        # Should have enqueued gitlab_merge_request embeddings
        mr_enqueues = [c for c in enqueue_calls if c[0] == "gitlab_merge_request"]
        assert len(mr_enqueues) >= 1
        # The MR IDs should come from the session.execute query scoped to project_id
        assert mr_uuid in mr_enqueues[0][1]


# ---------------------------------------------------------------------------
# Test 5: Timeout isolation
# ---------------------------------------------------------------------------


class TestTimeoutIsolation:

    @pytest.mark.asyncio
    async def test_slow_project_does_not_block_fast_project(self):
        """A timed-out project doesn't prevent other projects from syncing."""
        from src.services.gitlab_sync import sync_projects

        session, _, _ = _mock_session()
        settings = MagicMock()

        slow_project = 999
        fast_project = 100

        async def mock_sync_single(ws_id, project_id, sess, sett, **kwargs):
            if project_id == slow_project:
                await asyncio.sleep(10)
                return (0, 0)
            return (3, 1)

        with (
            patch("src.services.gitlab_sync.sync_single_project", side_effect=mock_sync_single),
            patch("src.services.gitlab_sync.PROJECT_SYNC_TIMEOUT", 0.05),
        ):
            result = await sync_projects(WS_UUID, [slow_project, fast_project], session, settings)

        assert result["projects"][str(slow_project)]["status"] == "timeout"
        assert result["projects"][str(fast_project)]["status"] == "synced"
        assert result["projects"][str(fast_project)]["mrs"] == 3
        assert result["total_mrs"] == 3


# ---------------------------------------------------------------------------
# Test 6: Concurrent code indexing
# ---------------------------------------------------------------------------


class TestConcurrentCodeIndexing:

    @pytest.mark.asyncio
    async def test_gather_and_per_task_sessions(self):
        """index_gitlab_workspace_repos uses gather + per-task sessions."""
        from src.services.code_indexer import MAX_CONCURRENT_CLONES, index_gitlab_workspace_repos

        assert MAX_CONCURRENT_CLONES == 3

        settings = MagicMock()
        session = AsyncMock()

        repos = [
            {"id": 1, "path_with_namespace": "group/repo-a"},
            {"id": 2, "path_with_namespace": "group/repo-b"},
        ]

        task_sessions_created = []
        gather_called = False
        real_gather = asyncio.gather

        async def tracking_gather(*coros, **kwargs):
            nonlocal gather_called
            gather_called = True
            return await real_gather(*coros, **kwargs)

        mock_task_session = AsyncMock()
        mock_task_session.commit = AsyncMock()

        def session_factory():
            task_sessions_created.append(True)
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_task_session)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        with (
            patch("src.services.gitlab_repos.get_cached_repos", new_callable=AsyncMock, return_value=repos),
            patch("src.services.gitlab_repos.is_project_monitored", new_callable=AsyncMock, return_value=True),
            patch("src.services.code_indexer.index_repo", new_callable=AsyncMock, return_value={
                "repo": "group/repo-a", "files_scanned": 10,
                "chunks_created": 5, "chunks_updated": 0,
                "chunks_deleted": 0, "changed_chunk_ids": [],
            }),
            patch("src.services.code_indexer._update_index_status", new_callable=AsyncMock),
            patch("src.services.code_indexer.ensure_valid_token", new_callable=AsyncMock, return_value="token"),
            patch("src.services.code_indexer.async_session", side_effect=session_factory),
            patch("src.services.code_indexer.asyncio.gather", side_effect=tracking_gather),
        ):
            results = await index_gitlab_workspace_repos(WS_UUID, session, settings)

        assert gather_called, "asyncio.gather must be used for concurrent indexing"
        assert len(task_sessions_created) == 2, f"Expected 2 per-task sessions, got {len(task_sessions_created)}"


# ---------------------------------------------------------------------------
# Test 7: GitHub index/status provider filtering
# ---------------------------------------------------------------------------


class TestGithubIndexStatusFilter:

    @pytest.mark.asyncio
    async def test_status_updates_write_to_provider_config(self):
        """_update_index_status writes to the correct provider's config."""
        from src.services.code_indexer import _update_index_status

        github_integration = MagicMock()
        github_integration.config = {}

        gitlab_integration = MagicMock()
        gitlab_integration.config = {}

        def make_session_for(integration):
            sess = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = integration
            sess.execute = AsyncMock(return_value=result)
            sess.commit = AsyncMock()
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=sess)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        with patch("src.db.async_session", return_value=make_session_for(github_integration)):
            await _update_index_status(WS_UUID, "indexing", provider="github", progress=1, total=3)

        assert github_integration.config["code_index_status"] == "indexing"
        assert github_integration.config["code_index_progress"] == 1

        with patch("src.db.async_session", return_value=make_session_for(gitlab_integration)):
            await _update_index_status(WS_UUID, "idle", provider="gitlab", last_at="2026-03-15T00:00:00")

        assert gitlab_integration.config["code_index_status"] == "idle"
        assert gitlab_integration.config.get("code_index_last_at") == "2026-03-15T00:00:00"
        # GitHub config unchanged by GitLab update
        assert github_integration.config["code_index_status"] == "indexing"
