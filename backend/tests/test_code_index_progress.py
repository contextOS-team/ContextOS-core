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
# _update_index_status unit tests
# ---------------------------------------------------------------------------


class TestUpdateIndexStatus:
    """Unit tests for the _update_index_status helper."""

    @pytest.mark.asyncio
    async def test_sets_progress_fields_during_indexing(self):
        """When status=indexing, progress/total/current_repo should be written."""
        from src.services.code_indexer import _update_index_status

        integration = _make_integration({"existing_key": "keep_me"})
        factory, session = _mock_async_session(integration)

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "indexing", provider="gitlab",
                progress=2, total=5, current_repo="org/repo",
            )

        config = integration.config
        assert config["code_index_status"] == "indexing"
        assert config["code_index_progress"] == 2
        assert config["code_index_total"] == 5
        assert config["code_index_current_repo"] == "org/repo"
        assert config["existing_key"] == "keep_me"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clears_progress_fields_when_idle(self):
        """When status=idle, progress fields should be removed from config."""
        from src.services.code_indexer import _update_index_status

        integration = _make_integration({
            "code_index_status": "indexing",
            "code_index_progress": 3,
            "code_index_total": 5,
            "code_index_current_repo": "org/repo",
            "other_key": "preserved",
        })
        factory, session = _mock_async_session(integration)

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "idle", last_at="2026-03-12T00:00:00",
                provider="gitlab",
            )

        config = integration.config
        assert config["code_index_status"] == "idle"
        assert config["code_index_last_at"] == "2026-03-12T00:00:00"
        assert "code_index_progress" not in config
        assert "code_index_total" not in config
        assert "code_index_current_repo" not in config
        assert config["other_key"] == "preserved"

    @pytest.mark.asyncio
    async def test_noop_when_integration_not_found(self):
        """When no integration exists, should return without error or commit."""
        from src.services.code_indexer import _update_index_status

        factory, session = _mock_async_session(None)

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "indexing", provider="gitlab",
                progress=0, total=3,
            )
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_none_config(self):
        """When integration.config is None, should create fresh dict."""
        from src.services.code_indexer import _update_index_status

        integration = _make_integration(None)
        factory, _ = _mock_async_session(integration)

        with patch("src.db.async_session", factory):
            await _update_index_status(
                uuid4(), "indexing", provider="gitlab",
                progress=0, total=2,
            )

        config = integration.config
        assert config["code_index_status"] == "indexing"
        assert config["code_index_progress"] == 0
        assert config["code_index_total"] == 2

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
        """Verify exact sequence of _update_index_status calls for 3 monitored repos.

        Expected calls (in order):
          1. ("indexing", progress=0, total=3)           # start
          2. ("indexing", progress=0, total=3, repo=A)   # before repo A
          3. ("indexing", progress=1, total=3, repo=B)   # before repo B
          4. ("indexing", progress=2, total=3, repo=C)   # before repo C
          5. ("indexing", progress=3, total=3, repo=None) # completion
          6. ("idle", last_at=..., progress cleared)      # final
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

        with (
            patch("src.services.code_indexer._update_index_status", side_effect=fake_update),
            patch("src.services.code_indexer.index_repo", side_effect=fake_index_repo),
            patch("src.services.code_indexer.ensure_valid_token", side_effect=fake_ensure_token),
            patch("src.services.gitlab_repos.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.gitlab_repos.is_project_monitored", side_effect=fake_is_monitored),
        ):
            from src.services.code_indexer import index_gitlab_workspace_repos
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        # 3 monitored repos processed
        assert len(results) == 3

        # Verify the progress update sequence
        assert len(update_calls) >= 5, f"Expected at least 5 status updates, got {len(update_calls)}"

        # Call 0: initial "indexing" with progress=0, total=3
        assert update_calls[0]["status"] == "indexing"
        assert update_calls[0]["progress"] == 0
        assert update_calls[0]["total"] == 3

        # Calls 1-3: per-repo updates with incrementing progress
        for i in range(3):
            call = update_calls[1 + i]
            assert call["status"] == "indexing"
            assert call["progress"] == i
            assert call["total"] == 3
            assert call.get("current_repo") is not None

        # Call 4: completion marker — progress == total, current_repo is None
        completion = update_calls[4]
        assert completion["status"] == "indexing"
        assert completion["progress"] == 3
        assert completion["total"] == 3
        assert completion.get("current_repo") is None

        # Call 5: idle transition
        idle_call = update_calls[5]
        assert idle_call["status"] == "idle"
        assert "last_at" in idle_call

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
