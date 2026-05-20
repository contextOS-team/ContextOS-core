"""Tests that prove (or disprove) correctness of the code indexer's
transaction handling — the per-repo commit/rollback fix and the
isolated status session.

These tests target the ACTUAL bugs found in code review:

1. Double commit: worker calls session.commit() AFTER the indexer
   already committed per-repo.  Harmless today, latent bug tomorrow.

2. ensure_valid_token mutates the data session: a rollback after a
   failed repo also rolls back the token refresh, but GitLab already
   invalidated the old token server-side.  Data loss on the rollback path.

3. Second repo proceeds after first repo rollback: proves isolation
   actually works (or doesn't).

4. Status reaches idle even when data session is poisoned: proves
   the independent-session fix in _update_index_status works.

5. Worker's extra commit after workspace indexer already committed:
   proves the double-commit is at least not destructive.

Unlike the existing test_code_index_progress.py (which mocks everything
and tests that a for-loop iterates), these tests exercise real
SQLAlchemy session state transitions.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


# ---------------------------------------------------------------------------
# Stateful fake session that tracks transaction state like a real one
# ---------------------------------------------------------------------------

class FakeSessionState:
    """Tracks what a real AsyncSession would track, minus the DB.

    This is NOT a mock — it enforces real session semantics:
    - flush() pushes operations to the "DB" (pending list) but doesn't commit
    - commit() persists pending operations and clears the pending list
    - rollback() discards pending operations
    - After an exception, the session enters "needs_rollback" state and
      refuses new operations until rollback() is called
    """

    def __init__(self):
        self.committed: list[dict] = []    # operations that survived commit
        self.pending: list[dict] = []      # flushed but not committed
        self.rolled_back: list[dict] = []  # operations lost to rollback
        self.needs_rollback = False
        self.commit_count = 0
        self.rollback_count = 0
        self.flush_count = 0
        self._execute_side_effects: list = []
        self._execute_call_count = 0

    def _check_state(self):
        if self.needs_rollback:
            from sqlalchemy.exc import PendingRollbackError
            raise PendingRollbackError(
                "Can't proceed until invalid transaction is rolled back."
            )

    async def execute(self, stmt, params=None):
        self._check_state()
        self._execute_call_count += 1
        # Record the operation
        op = {"stmt": str(stmt)[:100], "call_num": self._execute_call_count}
        self.pending.append(op)

        # If we have side effects registered, use them
        if self._execute_side_effects:
            effect = self._execute_side_effects.pop(0)
            if isinstance(effect, Exception):
                self.needs_rollback = True
                raise effect
            return effect

        # Default: return a mock result
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalar_one.return_value = str(uuid4())
        result.fetchall.return_value = []
        result.first.return_value = (uuid4(),)
        return result

    async def flush(self):
        self._check_state()
        self.flush_count += 1
        # flush doesn't commit — just marks that data is "sent" to DB

    async def commit(self):
        self._check_state()
        self.committed.extend(self.pending)
        self.pending = []
        self.commit_count += 1

    async def rollback(self):
        self.rolled_back.extend(self.pending)
        self.pending = []
        self.needs_rollback = False
        self.rollback_count += 1

    def poison(self):
        """Simulate a DB error that puts the session in needs_rollback state."""
        self.needs_rollback = True


# ---------------------------------------------------------------------------
# Per-repo session wiring
#
# Drift note (commit e8cd2fb "add concurrent repo indexing with semaphore and
# per-repo timeout"): index_workspace_repos / index_gitlab_workspace_repos no
# longer index through the caller's data session. Each repo now runs inside
# its own `async with async_session() as task_session:` block (code_indexer.py
# lines 631 / 512), commits that task_session on success, and relies on the
# sessionmaker context manager to roll back on failure. The caller's `session`
# arg is only used for get_cached_repos / is_*_monitored.
#
# These tests still want to assert commit/rollback isolation on a single
# tracked session, so we patch `src.services.code_indexer.async_session` to
# hand every task the SAME FakeSessionState, wrapped in a context manager that
# mirrors real async_sessionmaker `async with` semantics: roll back on an
# exception, close (no implicit commit) on clean exit.
# ---------------------------------------------------------------------------


class _SharedSessionCM:
    """async-context-manager that yields a shared FakeSessionState and rolls
    back on exception, matching async_sessionmaker() `async with` behavior."""

    def __init__(self, session: "FakeSessionState"):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            # Real AsyncSession context manager rolls back on a propagating
            # exception before closing.
            await self._session.rollback()
        return False  # never suppress


def _shared_async_session(session: "FakeSessionState"):
    """Build a MagicMock factory usable as `async_session()` that always
    yields the given shared FakeSessionState."""
    return MagicMock(side_effect=lambda *a, **k: _SharedSessionCM(session))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_index_repo(succeed=True, chunks_created=5):
    """Return a fake index_repo that flushes to the session (like the real one)."""
    async def _fake(workspace_id, repo_name, session, settings, provider="github"):
        if not succeed:
            # Simulate a DB error mid-upsert
            await session.execute("INSERT INTO code_chunks ...")
            raise RuntimeError(f"Simulated failure indexing {repo_name}")
        # Simulate successful upserts + flush (like real index_repo line 358)
        for i in range(chunks_created):
            await session.execute(f"INSERT chunk {i} for {repo_name}")
        await session.flush()
        return {
            "repo": repo_name,
            "files_scanned": 10,
            "chunks_created": chunks_created,
            "chunks_updated": 0,
            "chunks_deleted": 0,
            "changed_chunk_ids": [uuid4() for _ in range(chunks_created)],
        }
    return _fake


def _stub_index_repo_sequence(outcomes: list[bool], chunks_per_repo=3):
    """Return a fake index_repo that succeeds/fails per the outcomes list."""
    call_count = 0

    async def _fake(workspace_id, repo_name, session, settings, provider="gitlab"):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(outcomes) and not outcomes[idx]:
            await session.execute(f"INSERT partial chunk for {repo_name}")
            raise RuntimeError(f"Simulated failure indexing {repo_name}")
        for i in range(chunks_per_repo):
            await session.execute(f"INSERT chunk {i} for {repo_name}")
        await session.flush()
        return {
            "repo": repo_name,
            "files_scanned": 5,
            "chunks_created": chunks_per_repo,
            "chunks_updated": 0,
            "chunks_deleted": 0,
            "changed_chunk_ids": [uuid4() for _ in range(chunks_per_repo)],
        }
    return _fake


def _noop_update_status():
    """Capture _update_index_status calls without DB access."""
    calls = []
    async def _fake(ws_id, status, **kwargs):
        calls.append({"status": status, **kwargs})
    return _fake, calls


def _patch_gitlab_deps(index_repo_fn, repos, monitored_ids=None, shared_session=None):
    """Return a context manager that patches all gitlab workspace indexer deps.

    When ``shared_session`` is given, ``src.services.code_indexer.async_session``
    is patched so every per-repo task session is that shared FakeSessionState
    (see "Per-repo session wiring" above). This is what lets the per-repo
    commit/rollback assertions work against the now-isolated task sessions.
    """
    if monitored_ids is None:
        monitored_ids = {r["id"] for r in repos}

    async def fake_get_cached(ws_id, sess):
        return repos

    async def fake_is_monitored(ws_id, project_id, sess):
        return project_id in monitored_ids

    async def fake_ensure_token(sess, ws_id, sett):
        return "fake-token"

    from contextlib import contextmanager

    @contextmanager
    def _ctx(update_fn):
        extra = []
        if shared_session is not None:
            extra.append(patch(
                "src.services.code_indexer.async_session",
                _shared_async_session(shared_session),
            ))
        with (
            patch("src.services.code_indexer._update_index_status", side_effect=update_fn),
            patch("src.services.code_indexer.index_repo", side_effect=index_repo_fn),
            patch("src.services.code_indexer.ensure_valid_token", side_effect=fake_ensure_token),
            patch("src.services.gitlab_repos.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.gitlab_repos.is_project_monitored", side_effect=fake_is_monitored),
        ):
            from contextlib import ExitStack
            with ExitStack() as stack:
                for p in extra:
                    stack.enter_context(p)
                yield
    return _ctx


# ---------------------------------------------------------------------------
# Test 1: Second repo proceeds after first repo rollback
# ---------------------------------------------------------------------------

class TestRepoIsolation:
    """Prove that a failed repo doesn't poison subsequent repos."""

    @pytest.mark.asyncio
    async def test_second_repo_committed_after_first_fails(self):
        """Repo A fails mid-upsert → rollback.  Repo B succeeds → commit.
        Repo B's chunks must be in committed, Repo A's must not."""
        from src.services.code_indexer import index_gitlab_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        repos = [
            {"id": 1, "path_with_namespace": "org/fails"},
            {"id": 2, "path_with_namespace": "org/succeeds"},
        ]
        # First repo fails, second succeeds
        index_fn = _stub_index_repo_sequence([False, True], chunks_per_repo=3)
        update_fn, status_calls = _noop_update_status()
        patches = _patch_gitlab_deps(index_fn, repos, shared_session=session)

        with patches(update_fn):
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        # Both repos should have results
        assert len(results) == 2
        assert "error" in results[0]          # first failed
        assert results[1]["chunks_created"] == 3  # second succeeded

        # Session state: rollback happened for first, commit for second
        assert session.rollback_count >= 1, "First repo failure should trigger rollback"
        assert session.commit_count >= 1, "Second repo success should trigger commit"

        # The committed list should contain ops from the second repo only
        committed_stmts = [op["stmt"] for op in session.committed]
        assert any("org/succeeds" in s for s in committed_stmts), \
            "Second repo chunks should be committed"
        # The rolled-back list should contain the partial op from first repo
        rolled_back_stmts = [op["stmt"] for op in session.rolled_back]
        assert any("org/fails" in s for s in rolled_back_stmts), \
            "First repo's partial chunk should be rolled back"

    @pytest.mark.asyncio
    async def test_session_usable_after_rollback(self):
        """After rollback, the session must accept new operations.
        This is the core invariant the per-repo fix claims to provide."""
        from src.services.code_indexer import index_gitlab_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        repos = [
            {"id": 1, "path_with_namespace": "org/bad"},
            {"id": 2, "path_with_namespace": "org/good"},
            {"id": 3, "path_with_namespace": "org/also-good"},
        ]
        # First fails, rest succeed
        index_fn = _stub_index_repo_sequence([False, True, True])
        update_fn, _ = _noop_update_status()
        patches = _patch_gitlab_deps(index_fn, repos, shared_session=session)

        with patches(update_fn):
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        # All three should complete (no PendingRollbackError)
        assert len(results) == 3
        assert "error" in results[0]
        assert results[1]["chunks_created"] == 3
        assert results[2]["chunks_created"] == 3

        # Two commits (one per successful repo), one rollback
        assert session.commit_count == 2
        assert session.rollback_count == 1


# ---------------------------------------------------------------------------
# Test 2: Status reaches idle even when data session is poisoned
# ---------------------------------------------------------------------------

class TestStatusSessionIsolation:
    """Prove _update_index_status uses its own session and isn't blocked
    by a poisoned data session."""

    @pytest.mark.asyncio
    async def test_idle_status_set_despite_poisoned_data_session(self):
        """If the data session is in needs_rollback state, the finally block's
        _update_index_status must still succeed (because it uses its own session)."""
        from src.services.code_indexer import index_gitlab_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        # A single repo that will fail and poison the session
        repos = [{"id": 1, "path_with_namespace": "org/poison"}]

        async def _poison_index(ws_id, repo_name, sess, sett, provider="gitlab"):
            """Fail in a way that leaves session needing rollback,
            but DON'T let the except clause fix it."""
            await sess.execute("INSERT partial data")
            raise RuntimeError("boom")

        update_fn, status_calls = _noop_update_status()
        patches = _patch_gitlab_deps(_poison_index, repos)

        with patches(update_fn):
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        # The finally block should have called _update_index_status with "idle"
        # even though the data session was troubled
        idle_calls = [c for c in status_calls if c["status"] == "idle"]
        assert len(idle_calls) == 1, \
            f"Expected exactly 1 idle status call, got {len(idle_calls)}: {status_calls}"
        assert "last_at" in idle_calls[0]

    @pytest.mark.asyncio
    async def test_update_index_status_creates_own_session(self):
        """_update_index_status must use async_session() internally,
        NOT accept a session parameter, and commit on its own session.

        Drift note (commit 8ef0d27 "eliminate JSONB read-modify-write race"):
        _update_index_status no longer does SELECT -> mutate integration.config
        -> write back. It now issues a single SQL-level
        ``UPDATE WorkspaceIntegration ... SET config = config || :patch::jsonb``
        and commits (code_indexer.py lines 438-452). There is no Python-side
        config dict to inspect, so we assert on the emitted statement instead.
        """
        from sqlalchemy.dialects import postgresql

        from src.services.code_indexer import _update_index_status

        captured: list = []

        inner_session = AsyncMock()

        async def _capture_execute(stmt, *a, **k):
            captured.append(stmt)
            return MagicMock()

        inner_session.execute = AsyncMock(side_effect=_capture_execute)
        inner_session.commit = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__.return_value = inner_session
        cm.__aexit__.return_value = False
        factory = MagicMock(return_value=cm)

        with patch("src.db.async_session", factory):
            # This should succeed — it doesn't need any caller session
            await _update_index_status(
                uuid4(), "idle", last_at="2026-01-01T00:00:00", provider="gitlab",
            )

        # Created and committed its own session
        inner_session.commit.assert_awaited_once()
        assert len(captured) == 1, f"Expected exactly 1 statement, got {len(captured)}"

        sql = str(captured[0].compile(dialect=postgresql.dialect()))
        # SQL-level merge, not a read-modify-write
        assert sql.startswith("UPDATE"), f"Expected UPDATE, got: {sql[:80]}"
        assert "||" in sql, f"Expected JSONB || merge, got: {sql}"
        assert "SELECT" not in sql, f"Must not read-modify-write, got: {sql}"

        # The merge patch carries the new status (idle nulls progress keys)
        params = dict(captured[0].compile(dialect=postgresql.dialect()).params)
        patch_dicts = [v for v in params.values() if isinstance(v, dict)]
        assert len(patch_dicts) == 1, f"Expected one patch dict, got: {params}"
        assert patch_dicts[0]["code_index_status"] == "idle"
        assert patch_dicts[0]["code_index_last_at"] == "2026-01-01T00:00:00"


# ---------------------------------------------------------------------------
# Test 3: Double commit from worker after indexer already committed
# ---------------------------------------------------------------------------

class TestDoubleCommit:
    """The worker calls session.commit() AFTER the indexer already committed
    per-repo.  This is currently harmless but fragile."""

    @pytest.mark.asyncio
    async def test_worker_commit_after_indexer_commits_is_noop(self):
        """Simulate the worker flow: call index_gitlab_workspace_repos
        (which commits per-repo), then call session.commit() again.
        Verify the extra commit doesn't re-commit anything."""
        from src.services.code_indexer import index_gitlab_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        repos = [{"id": 1, "path_with_namespace": "org/repo-a"}]
        index_fn = _stub_index_repo_sequence([True], chunks_per_repo=5)
        update_fn, _ = _noop_update_status()
        patches = _patch_gitlab_deps(index_fn, repos)

        with patches(update_fn):
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        committed_before = len(session.committed)
        commit_count_before = session.commit_count

        # This is what the worker does (code_index_worker.py:141)
        await session.commit()

        # The extra commit should have committed nothing new
        assert len(session.committed) == committed_before, \
            f"Extra commit added {len(session.committed) - committed_before} phantom operations"
        assert session.commit_count == commit_count_before + 1  # commit was called, but empty

    @pytest.mark.asyncio
    async def test_worker_commit_after_last_repo_failed(self):
        """If last repo failed (rollback), worker's commit should be a no-op
        on a clean session — not commit stale data."""
        from src.services.code_indexer import index_gitlab_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        repos = [{"id": 1, "path_with_namespace": "org/only-repo"}]
        index_fn = _stub_index_repo_sequence([False])
        update_fn, _ = _noop_update_status()
        patches = _patch_gitlab_deps(index_fn, repos, shared_session=session)

        with patches(update_fn):
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        assert "error" in results[0]
        assert session.rollback_count == 1

        # Worker's commit should succeed (session is clean after rollback)
        # and should NOT commit any rolled-back data
        committed_before = list(session.committed)
        await session.commit()
        assert session.committed == committed_before, \
            "Worker commit after rollback should not resurrect rolled-back data"


# ---------------------------------------------------------------------------
# Test 4: ensure_valid_token mutations get rolled back with repo failure
# (This test DOCUMENTS the bug — it shows the token is lost on rollback)
# ---------------------------------------------------------------------------

class TestTokenRollbackSafe:
    """Verify that ensure_valid_token uses its own session so token refresh
    survives a rollback on the caller's data session.

    The bug was: ensure_valid_token wrote to the data session, so when a
    repo failed and we rolled back, the token refresh was also rolled back.
    But GitLab already invalidated the old token server-side → stale DB.

    The fix: ensure_valid_token now persists tokens in an independent session.
    """

    @pytest.mark.asyncio
    async def test_token_refresh_survives_repo_failure(self):
        """Token refresh (own session) → repo index fails → data rollback.
        Token operations must NOT appear in the data session's rolled_back list."""
        from src.services.code_indexer import index_gitlab_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        repos = [{"id": 1, "path_with_namespace": "org/doomed"}]

        token_refreshed = False

        async def _fake_ensure_token(sess, ws_id, sett):
            nonlocal token_refreshed
            # After the fix, ensure_valid_token uses its own session internally.
            # It does NOT write to the caller's data session (sess).
            # We simulate this by NOT touching sess at all.
            token_refreshed = True
            return "new-access-token"

        async def _fail_index(ws_id, repo_name, sess, sett, provider="gitlab"):
            await sess.execute(f"INSERT chunk for {repo_name}")
            raise RuntimeError("clone failed after token was refreshed")

        update_fn, _ = _noop_update_status()

        async def fake_get_cached(ws_id, sess):
            return repos

        async def fake_is_monitored(ws_id, project_id, sess):
            return True

        with (
            patch("src.services.code_indexer._update_index_status", side_effect=update_fn),
            patch("src.services.code_indexer.index_repo", side_effect=_fail_index),
            patch("src.services.code_indexer.ensure_valid_token", side_effect=_fake_ensure_token),
            patch("src.services.code_indexer.async_session", _shared_async_session(session)),
            patch("src.services.gitlab_repos.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.gitlab_repos.is_project_monitored", side_effect=fake_is_monitored),
        ):
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        assert token_refreshed, "Token should have been refreshed before failure"
        assert session.rollback_count == 1

        # Token operations must NOT be in the rolled-back list
        rolled_back_stmts = [op["stmt"] for op in session.rolled_back]
        token_ops = [s for s in rolled_back_stmts if "store_vault_secret" in s]
        assert len(token_ops) == 0, (
            f"Token operations should NOT be on the data session anymore. "
            f"Found {len(token_ops)} in rolled_back: {rolled_back_stmts}"
        )

    @pytest.mark.asyncio
    async def test_ensure_valid_token_uses_independent_session(self):
        """Directly verify ensure_valid_token persists tokens in its own session
        by checking that no vault calls go through the caller's session."""
        from src.services.gitlab_common import ensure_valid_token

        caller_session = FakeSessionState()
        workspace_id = uuid4()
        settings = MagicMock()
        settings.GITLAB_CLIENT_ID = "test-id"
        settings.GITLAB_CLIENT_SECRET = "test-secret"
        settings.gitlab_redirect_uri = "http://localhost/callback"

        # Set up caller session to return an OAuthToken that needs refresh
        oauth_token = MagicMock()
        oauth_token.id = uuid4()
        oauth_token.token_expires_at = datetime(2020, 1, 1)  # expired

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = oauth_token
        caller_session._execute_side_effects = [
            result_mock,  # SELECT OAuthToken
            MagicMock(scalar_one_or_none=MagicMock(return_value="old-refresh-token")),  # read_token (refresh)
        ]

        # Mock the HTTP call to GitLab
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 7200,
        }

        # Mock the independent token session
        token_inner_session = AsyncMock()
        fresh_token = MagicMock()
        token_result_mock = MagicMock()
        token_result_mock.scalar_one.return_value = fresh_token
        token_inner_session.execute.return_value = token_result_mock

        token_cm = AsyncMock()
        token_cm.__aenter__.return_value = token_inner_session
        token_cm.__aexit__.return_value = False
        token_factory = MagicMock(return_value=token_cm)

        with (
            patch("src.services.gitlab_common.httpx.AsyncClient") as mock_client_cls,
            patch("src.db.async_session", token_factory),
        ):
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await ensure_valid_token(caller_session, workspace_id, settings)

        assert result == "new-access"
        # The independent session should have committed the tokens
        token_inner_session.commit.assert_awaited_once()
        # The caller's session should NOT have had store_token calls
        # (only the initial SELECT OAuthToken and read_token for refresh)
        assert caller_session.commit_count == 0, \
            "Caller session should not have committed anything"


# ---------------------------------------------------------------------------
# Test 5: GitHub indexer has the same fix as GitLab
# ---------------------------------------------------------------------------

class TestGitHubParityWithGitLab:
    """The GitHub workspace indexer must have identical commit/rollback behavior."""

    @pytest.mark.asyncio
    async def test_github_commits_per_repo_and_rolls_back_on_failure(self):
        """Mirror of test_second_repo_committed_after_first_fails but for GitHub."""
        from src.services.code_indexer import index_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        fake_repos = [
            {"full_name": "org/fails-gh", "id": 1},
            {"full_name": "org/succeeds-gh", "id": 2},
        ]

        call_count = 0

        async def _index_fn(ws_id, repo_name, sess, sett, provider="github"):
            nonlocal call_count
            idx = call_count
            call_count += 1
            if idx == 0:
                await sess.execute(f"INSERT partial for {repo_name}")
                raise RuntimeError("github repo failed")
            for i in range(3):
                await sess.execute(f"INSERT chunk {i} for {repo_name}")
            await sess.flush()
            return {
                "repo": repo_name,
                "files_scanned": 5,
                "chunks_created": 3,
                "chunks_updated": 0,
                "chunks_deleted": 0,
                "changed_chunk_ids": [uuid4() for _ in range(3)],
            }

        update_fn, status_calls = _noop_update_status()

        async def fake_get_cached(ws_id, sess):
            return fake_repos

        async def fake_is_monitored(ws_id, full_name, sess):
            return True

        with (
            patch("src.services.code_indexer._update_index_status", side_effect=update_fn),
            patch("src.services.code_indexer.index_repo", side_effect=_index_fn),
            patch("src.services.code_indexer.async_session", _shared_async_session(session)),
            patch("src.services.code_indexer.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.code_indexer.is_repo_monitored", side_effect=fake_is_monitored),
        ):
            results = await index_workspace_repos(workspace_id, session, settings)

        assert len(results) == 2
        assert "error" in results[0]
        assert results[1]["chunks_created"] == 3

        assert session.rollback_count >= 1
        assert session.commit_count >= 1

        # Verify isolation
        committed_stmts = [op["stmt"] for op in session.committed]
        assert any("org/succeeds-gh" in s for s in committed_stmts)
        rolled_back_stmts = [op["stmt"] for op in session.rolled_back]
        assert any("org/fails-gh" in s for s in rolled_back_stmts)

    @pytest.mark.asyncio
    async def test_github_reaches_idle_after_all_fail(self):
        """Even if every repo fails, status must reach idle."""
        from src.services.code_indexer import index_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        fake_repos = [{"full_name": "org/dead", "id": 1}]

        async def _fail(ws_id, repo_name, sess, sett, provider="github"):
            raise RuntimeError("nope")

        update_fn, status_calls = _noop_update_status()

        async def fake_get_cached(ws_id, sess):
            return fake_repos

        async def fake_is_monitored(ws_id, full_name, sess):
            return True

        with (
            patch("src.services.code_indexer._update_index_status", side_effect=update_fn),
            patch("src.services.code_indexer.index_repo", side_effect=_fail),
            patch("src.services.code_indexer.get_cached_repos", side_effect=fake_get_cached),
            patch("src.services.code_indexer.is_repo_monitored", side_effect=fake_is_monitored),
        ):
            results = await index_workspace_repos(workspace_id, session, settings)

        idle_calls = [c for c in status_calls if c["status"] == "idle"]
        assert len(idle_calls) == 1


# ---------------------------------------------------------------------------
# Test 6: PendingRollbackError doesn't propagate to caller
# ---------------------------------------------------------------------------

class TestPendingRollbackRecovery:
    """If a repo causes PendingRollbackError, the except clause must
    rollback and continue — not propagate the error to the worker."""

    @pytest.mark.asyncio
    async def test_pending_rollback_error_caught_and_recovered(self):
        """Simulate a DB integrity error that puts session in needs_rollback,
        then verify the indexer recovers via rollback and processes next repo."""
        from sqlalchemy.exc import IntegrityError
        from src.services.code_indexer import index_gitlab_workspace_repos

        session = FakeSessionState()
        settings = MagicMock()
        workspace_id = uuid4()

        repos = [
            {"id": 1, "path_with_namespace": "org/constraint-violation"},
            {"id": 2, "path_with_namespace": "org/fine"},
        ]

        call_count = 0

        async def _index_fn(ws_id, repo_name, sess, sett, provider="gitlab"):
            nonlocal call_count
            idx = call_count
            call_count += 1
            if idx == 0:
                # Simulate IntegrityError that poisons the session
                sess.poison()
                raise IntegrityError("duplicate key", {}, Exception())
            for i in range(2):
                await sess.execute(f"INSERT chunk {i} for {repo_name}")
            await sess.flush()
            return {
                "repo": repo_name, "files_scanned": 1,
                "chunks_created": 2, "chunks_updated": 0,
                "chunks_deleted": 0, "changed_chunk_ids": [],
            }

        update_fn, _ = _noop_update_status()
        patches = _patch_gitlab_deps(_index_fn, repos, shared_session=session)

        with patches(update_fn):
            # This must NOT raise — the indexer should catch and rollback
            results = await index_gitlab_workspace_repos(workspace_id, session, settings)

        assert len(results) == 2
        assert "error" in results[0]
        assert results[1]["chunks_created"] == 2
        assert session.rollback_count >= 1
        assert not session.needs_rollback, "Session should be clean after recovery"
