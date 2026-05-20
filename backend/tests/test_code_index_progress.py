"""Tests for code indexing progress tracking in _update_index_status
and index_gitlab_workspace_repos.

Verifies:
1. _update_index_status writes progress/total/current_repo during indexing
2. _update_index_status clears progress fields when status becomes idle
3. _update_index_status uses its own session (isolation from data session)
4. index_gitlab_workspace_repos reports correct progress sequence
5. Progress reaches total/total before transitioning to idle
6. Progress fields are cleared in final idle state even after errors
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_integration(config: dict | None = None):
    """Create a mock WorkspaceIntegration with mutable config."""
    integration = MagicMock()
    integration.config = config or {}
    return integration


def _mock_async_session(integration):
    """Build a mock async_session context manager that returns a session
    whose execute().scalar_one_or_none() returns the given integration."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = integration
    session.execute.return_value = result_mock

    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = False

    factory = MagicMock(return_value=cm)
    return factory, session


# ---------------------------------------------------------------------------
# Drift note (commit 8ef0d27 "eliminate JSONB read-modify-write race in code
# index status updates"): _update_index_status no longer does
# SELECT WorkspaceIntegration -> mutate integration.config -> write back.
# It now issues ONE statement:
#
#     UPDATE workspace_integrations
#        SET config = config || :patch::jsonb
#      WHERE workspace_id = :wid AND provider = :provider
#
# then commits its own session (code_indexer.py lines 438-452). There is no
# Python-side config dict to assert on, and the patch is built unconditionally
# regardless of whether a matching row exists (the UPDATE is simply a no-op at
# the DB level when nothing matches). The helper below captures the emitted
# statement so tests can assert on the merge patch instead of a mutated dict.
# ---------------------------------------------------------------------------


def _capture_update_session():
    """async_session() mock that captures every executed statement.

    Returns (factory, session, captured) where ``captured`` is a list the
    executed SQLAlchemy statements are appended to.
    """
    captured: list = []
    session = AsyncMock()

    async def _capture_execute(stmt, *a, **k):
        captured.append(stmt)
        return MagicMock()

    session.execute = AsyncMock(side_effect=_capture_execute)
    session.commit = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = False

    factory = MagicMock(return_value=cm)
    return factory, session, captured


def _merge_patch(stmt) -> dict:
    """Extract the JSONB merge patch dict from a captured UPDATE statement."""
    from sqlalchemy.dialects import postgresql

    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert sql.startswith("UPDATE"), f"Expected UPDATE, got: {sql[:80]}"
    assert "||" in sql, f"Expected JSONB || merge, got: {sql}"
    assert "SELECT" not in sql, f"Must not read-modify-write, got: {sql}"
    patch_dicts = [v for v in dict(compiled.params).values() if isinstance(v, dict)]
    assert len(patch_dicts) == 1, f"Expected exactly one patch dict, got: {compiled.params}"
    return patch_dicts[0]


# ---------------------------------------------------------------------------
# _update_index_status unit tests
# ---------------------------------------------------------------------------


class TestUpdateIndexStatus:
    """Unit tests for the _update_index_status helper."""

    @pytest.mark.asyncio
    async def test_sets_progress_fields_during_indexing(self):
        """When status=indexing, the merge patch carries progress/total/repo.

        The || merge only touches the indexing keys, so unrelated config keys
        (e.g. OAuth tokens) survive untouched — that is verified by the
        absence of any other keys in the patch dict.
        """
        from src.services.code_indexer import _update_index_status

        factory, session, captured = _capture_update_session()

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "indexing", provider="gitlab",
                progress=2, total=5, current_repo="org/repo",
            )

        assert len(captured) == 1
        patch_ = _merge_patch(captured[0])
        assert patch_ == {
            "code_index_status": "indexing",
            "code_index_progress": 2,
            "code_index_total": 5,
            "code_index_current_repo": "org/repo",
        }
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clears_progress_fields_when_idle(self):
        """When status=idle, the merge patch nulls the progress keys.

        The old code used dict.pop() to delete the keys; the new code sets
        them to JSON null via the || merge. Both are equivalent because the
        API endpoint uses dict.get() (None for absent or null).
        """
        from src.services.code_indexer import _update_index_status

        factory, session, captured = _capture_update_session()

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "idle", last_at="2026-03-12T00:00:00",
                provider="gitlab",
            )

        assert len(captured) == 1
        patch_ = _merge_patch(captured[0])
        assert patch_ == {
            "code_index_status": "idle",
            "code_index_last_at": "2026-03-12T00:00:00",
            "code_index_progress": None,
            "code_index_total": None,
            "code_index_current_repo": None,
        }

    @pytest.mark.asyncio
    async def test_noop_when_integration_not_found(self):
        """No matching row → the UPDATE is a DB-level no-op but still runs.

        The new SQL-level merge does not SELECT first, so it cannot branch on
        "integration not found". It always emits one UPDATE (which simply
        affects zero rows when nothing matches) and commits, without error.
        """
        from src.services.code_indexer import _update_index_status

        factory, session, captured = _capture_update_session()

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "indexing", provider="gitlab",
                progress=0, total=3,
            )

        # Exactly one UPDATE issued, committed, no exception raised
        assert len(captured) == 1
        _merge_patch(captured[0])  # asserts it's an UPDATE ... || merge
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_none_config(self):
        """A NULL config column is handled by Postgres coalescing in the
        merge SQL; the patch dict still carries the indexing keys.

        There is no Python-side config dict anymore — the merge is evaluated
        in Postgres — so we assert on the emitted patch instead.
        """
        from src.services.code_indexer import _update_index_status

        factory, session, captured = _capture_update_session()

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "indexing", provider="gitlab",
                progress=0, total=2,
            )

        assert len(captured) == 1
        patch_ = _merge_patch(captured[0])
        assert patch_["code_index_status"] == "indexing"
        assert patch_["code_index_progress"] == 0
        assert patch_["code_index_total"] == 2

    @pytest.mark.asyncio
    async def test_uses_own_session_not_callers(self):
        """_update_index_status must create its own session, never accept one."""
        import inspect
        from src.services.code_indexer import _update_index_status

        sig = inspect.signature(_update_index_status)
        param_names = list(sig.parameters.keys())
        assert "session" not in param_names, (
            "_update_index_status should not accept a session parameter"
        )


# ---------------------------------------------------------------------------
# index_gitlab_workspace_repos progress sequence test
# ---------------------------------------------------------------------------


class TestGitlabIndexProgressSequence:
    """Integration-style test verifying the full progress update sequence."""

    @pytest.mark.asyncio
    async def test_progress_sequence_for_3_repos(self):
        """Verify the _update_index_status sequence for 3 monitored repos.

        Drift notes:
        - commit e8cd2fb ("add concurrent repo indexing with semaphore"):
          repos are now indexed concurrently via asyncio.gather, each in its
          own ``async with async_session() as task_session`` block, so the
          per-repo "indexing" updates can interleave (order is not strict).
        - commit 8ef0d27 ("eliminate JSONB read-modify-write race"): the
          "Remove dead completion markers" change deleted the old extra
          ``(indexing, progress==total, current_repo=None)`` call.

        Current contract (code_indexer.py 610-687):
          1. one start update: ("indexing", progress=0, total=3)
          2. one per-repo update each: ("indexing", progress=idx, total=3,
             current_repo=<name>) with idx in {0,1,2}
          3. one final ("idle", last_at=...) from the finally block
          (no completion marker)
        """
        workspace_id = uuid4()
        settings = MagicMock()
        session = AsyncMock()

        fake_repos = [
            {"id": 1, "path_with_namespace": "org/alpha"},
            {"id": 2, "path_with_namespace": "org/beta"},
            {"id": 3, "path_with_namespace": "org/gamma"},
            {"id": 99, "path_with_namespace": "org/unmonitored"},
        ]

        update_calls: list[dict] = []

        async def fake_update(ws_id, status, **kwargs):
            update_calls.append({"status": status, **kwargs})

        async def fake_index_repo(ws_id, repo_name, sess, sett, provider="gitlab"):
            return {"repo": repo_name, "files_scanned": 1, "chunks_created": 1,
                    "chunks_updated": 0, "chunks_deleted": 0, "changed_chunk_ids": []}

        async def fake_is_monitored(ws_id, project_id, sess):
            return project_id != 99  # All except 99

        async def fake_get_cached(ws_id, sess):
            return fake_repos

        async def fake_ensure_token(sess, ws_id, sett):
            pass

        # Each per-repo task opens its own async_session(); give it an inert
        # context manager (fake_index_repo / fake_ensure_token don't touch it).
        task_session = AsyncMock()
        task_cm = AsyncMock()
        task_cm.__aenter__.return_value = task_session
        task_cm.__aexit__.return_value = False
        session_factory = MagicMock(return_value=task_cm)

        with (
            patch("src.services.code_indexer._update_index_status", side_effect=fake_update),
            patch("src.services.code_indexer.index_repo", side_effect=fake_index_repo),
            patch("src.services.code_indexer.ensure_valid_token", side_effect=fake_ensure_token),
            patch("src.services.code_indexer.async_session", session_factory),
            patch("src.services.gitlab_repos.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.gitlab_repos.is_project_monitored", side_effect=fake_is_monitored),
        ):
            from src.services.code_indexer import index_gitlab_workspace_repos
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        # 3 monitored repos processed (unmonitored id=99 filtered out)
        assert len(results) == 3

        # Exactly 5 updates: 1 start + 3 per-repo + 1 idle (no completion marker)
        assert len(update_calls) == 5, (
            f"Expected 5 status updates (start + 3 repos + idle), "
            f"got {len(update_calls)}: {update_calls}"
        )

        # Call 0: initial "indexing" with progress=0, total=3
        assert update_calls[0]["status"] == "indexing"
        assert update_calls[0]["progress"] == 0
        assert update_calls[0]["total"] == 3
        assert update_calls[0].get("current_repo") is None

        # Calls 1-3: one per-repo update each. Concurrent → order not strict,
        # so assert on the multiset of (progress, current_repo).
        per_repo = update_calls[1:4]
        for call in per_repo:
            assert call["status"] == "indexing"
            assert call["total"] == 3
            assert call.get("current_repo") is not None
        assert sorted(c["progress"] for c in per_repo) == [0, 1, 2]
        assert {c["current_repo"] for c in per_repo} == {
            "org/alpha", "org/beta", "org/gamma",
        }

        # Last call: idle transition (no completion marker before it)
        idle_call = update_calls[-1]
        assert idle_call["status"] == "idle"
        assert "last_at" in idle_call
        indexing_calls = [c for c in update_calls if c["status"] == "indexing"]
        assert len(indexing_calls) == 4  # start + 3 repos, no completion marker

    @pytest.mark.asyncio
    async def test_zero_monitored_repos_skips_completion_marker(self):
        """When no repos are monitored, should go straight to idle without completion marker."""
        workspace_id = uuid4()
        settings = MagicMock()
        session = AsyncMock()

        update_calls: list[dict] = []

        async def fake_update(ws_id, status, **kwargs):
            update_calls.append({"status": status, **kwargs})

        async def fake_get_cached(ws_id, sess):
            return [{"id": 1, "path_with_namespace": "org/repo"}]

        async def fake_is_monitored(ws_id, project_id, sess):
            return False

        with (
            patch("src.services.code_indexer._update_index_status", side_effect=fake_update),
            patch("src.services.gitlab_repos.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.gitlab_repos.is_project_monitored", side_effect=fake_is_monitored),
        ):
            from src.services.code_indexer import index_gitlab_workspace_repos
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        assert len(results) == 0

        # Should have: initial indexing (progress=0, total=0) + idle
        assert update_calls[0]["status"] == "indexing"
        assert update_calls[0]["total"] == 0
        assert update_calls[-1]["status"] == "idle"

        # No completion marker (total=0 skips it)
        indexing_calls = [c for c in update_calls if c["status"] == "indexing"]
        assert len(indexing_calls) == 1  # Only the initial one

    @pytest.mark.asyncio
    async def test_idle_reached_even_when_repo_fails(self):
        """If index_repo raises, status must still reach idle at the end."""
        workspace_id = uuid4()
        settings = MagicMock()
        session = AsyncMock()

        update_calls: list[dict] = []

        async def fake_update(ws_id, status, **kwargs):
            update_calls.append({"status": status, **kwargs})

        async def fake_index_repo(ws_id, repo_name, sess, sett, provider="gitlab"):
            raise RuntimeError("clone failed")

        async def fake_get_cached(ws_id, sess):
            return [{"id": 1, "path_with_namespace": "org/broken"}]

        async def fake_is_monitored(ws_id, project_id, sess):
            return True

        async def fake_ensure_token(sess, ws_id, sett):
            pass

        with (
            patch("src.services.code_indexer._update_index_status", side_effect=fake_update),
            patch("src.services.code_indexer.index_repo", side_effect=fake_index_repo),
            patch("src.services.code_indexer.ensure_valid_token", side_effect=fake_ensure_token),
            patch("src.services.gitlab_repos.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.gitlab_repos.is_project_monitored", side_effect=fake_is_monitored),
        ):
            from src.services.code_indexer import index_gitlab_workspace_repos
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        # Should still have result (with error)
        assert len(results) == 1
        assert "error" in results[0]

        # Final call must be idle
        assert update_calls[-1]["status"] == "idle"
