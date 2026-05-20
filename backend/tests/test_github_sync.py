"""Tests for GitHub PR sync, linking, and backfill services."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from tests.conftest import TEST_WORKSPACE_ID, make_entity_execute


def _sync_repo_execute(mock_pr, pr_uuid):
    """Build a session.execute side-effect for sync_single_repo.

    Routes by ORM entity so the test no longer relies on a single shared
    MagicMock for every query (which broke when sync_single_repo started
    reading cursor.cursor_value as a string -- see github_sync.py:223-229,
    `cutoff = datetime.fromisoformat(cursor.cursor_value...)`). The mock
    SyncCursor must expose cursor_value=None so the 60-day backfill path is
    taken instead of crashing on a MagicMock value.

    - SyncCursor (get_or_create_cursor): scalar_one_or_none -> cursor with
      cursor_value=None.
    - GithubPullRequest: the post-insert `select(GithubPullRequest)` reads
      .scalar_one() (-> mock_pr) and the final embedding-id query reads
      .fetchall() (-> [(pr_uuid,)]).
    - WorkspaceIntegration (_update_repo_sync_status): scalar_one_or_none
      -> None (no-op).
    - textual (insert...returning id for PR, insert for review): the PR
      upsert reads .scalar_one() -> pr_uuid; the review insert reads nothing.
    """
    cursor = MagicMock()
    cursor.cursor_value = None

    cursor_result = MagicMock()
    cursor_result.scalar_one_or_none.return_value = cursor

    pr_result = MagicMock()
    pr_result.scalar_one.return_value = mock_pr
    pr_result.scalar_one_or_none.return_value = mock_pr
    pr_result.fetchall.return_value = [(pr_uuid,)]

    wi_result = MagicMock()
    wi_result.scalar_one_or_none.return_value = None

    textual_result = MagicMock()
    textual_result.scalar_one.return_value = pr_uuid
    textual_result.scalar_one_or_none.return_value = None
    textual_result.fetchall.return_value = []

    return make_entity_execute(
        results={
            "SyncCursor": cursor_result,
            "GithubPullRequest": pr_result,
            "WorkspaceIntegration": wi_result,
        },
        textual=textual_result,
    )


# ---------- extract_linear_issue_id ----------


class TestExtractLinearIssueId:
    """Tests for extract_linear_issue_id branch name parsing."""

    def test_feat_prefix_with_team_key(self):
        """Extracts issue ID from feat/ENG-123-add-auth."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("feat/ENG-123-add-auth", ["ENG", "PROJ"])
        assert result == "ENG-123"

    def test_bare_team_key_prefix(self):
        """Extracts issue ID from ENG-123-add-auth (no prefix)."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("ENG-123-add-auth", ["ENG", "PROJ"])
        assert result == "ENG-123"

    def test_bugfix_prefix(self):
        """Extracts issue ID from bugfix/PROJ-456."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("bugfix/PROJ-456", ["ENG", "PROJ"])
        assert result == "PROJ-456"

    def test_underscore_separator(self):
        """Extracts issue ID with underscore separator."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("feature_ENG-789_something", ["ENG"])
        assert result == "ENG-789"

    def test_no_match_returns_none(self):
        """Returns None for branches without a Linear issue pattern."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("my-feature-branch", ["ENG", "PROJ"])
        assert result is None

    def test_no_match_different_team_key(self):
        """Returns None when branch has an issue pattern but wrong team key."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("feat/UNKNOWN-123-fix", ["ENG", "PROJ"])
        assert result is None

    def test_empty_team_keys_returns_none(self):
        """Returns None when no team keys provided."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("feat/ENG-123", [])
        assert result is None

    def test_empty_branch_returns_none(self):
        """Returns None for empty branch name."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("", ["ENG"])
        assert result is None

    def test_case_insensitive_match(self):
        """Matches team keys case-insensitively, returns uppercase."""
        from src.services.github_linking import extract_linear_issue_id

        result = extract_linear_issue_id("feat/eng-123-fix", ["ENG"])
        assert result == "ENG-123"


# ---------- sync_single_repo ----------


class TestSyncSingleRepo:
    """Tests for sync_single_repo PR syncing."""

    @pytest.mark.asyncio
    async def test_sync_single_repo_upserts_prs(self, mock_session):
        """sync_single_repo fetches PRs from GitHub API and upserts them."""
        from src.services.github_sync import sync_single_repo

        settings = MagicMock()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pr_data = {
            "id": 100001,
            "number": 42,
            "title": "Add authentication",
            "body": "Implements JWT auth",
            "state": "open",
            "draft": False,
            "merged_at": None,
            "user": {"login": "developer"},
            "head": {"ref": "feat/ENG-123-add-auth"},
            "base": {"ref": "main"},
            "requested_reviewers": [{"login": "reviewer1"}],
            "created_at": (now - timedelta(days=5)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
        }

        # Mock PR list response
        pr_list_response = MagicMock()
        pr_list_response.status_code = 200
        pr_list_response.headers = {}
        pr_list_response.json.return_value = [pr_data]

        # Mock reviews response (empty)
        review_response = MagicMock()
        review_response.status_code = 200
        review_response.headers = {}
        review_response.json.return_value = []

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "pulls" in url and "reviews" not in url:
                return pr_list_response
            return review_response

        # Mock DB operations
        pr_uuid = uuid.uuid4()
        mock_pr = MagicMock()
        mock_pr.id = pr_uuid
        mock_pr.branch_name = "feat/ENG-123-add-auth"
        mock_pr.number = 42

        mock_session.execute = AsyncMock(
            side_effect=_sync_repo_execute(mock_pr, pr_uuid)
        )
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.github_sync.get_installation_token",
                new_callable=AsyncMock,
                return_value="ghs_test_token",
            ),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(get=AsyncMock(side_effect=mock_get)),
            ),
            patch(
                "src.services.github_sync.link_pr_to_ticket",
                new_callable=AsyncMock,
            ) as mock_link,
            patch(
                "src.services.github_sync.enqueue_embedding_job",
                new_callable=AsyncMock,
            ),
        ):
            pr_count, review_count = await sync_single_repo(
                UUID(TEST_WORKSPACE_ID), "org/repo", mock_session, settings
            )

        assert pr_count == 1
        assert review_count == 0
        mock_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_filters_bot_accounts(self, mock_session):
        """sync_single_repo skips PRs from bot accounts."""
        from src.services.github_sync import sync_single_repo

        settings = MagicMock()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        bot_pr = {
            "id": 100002,
            "number": 43,
            "title": "Bump dependency",
            "body": None,
            "state": "open",
            "draft": False,
            "merged_at": None,
            "user": {"login": "dependabot[bot]"},
            "head": {"ref": "dependabot/npm_and_yarn/axios-1.6.3"},
            "base": {"ref": "main"},
            "requested_reviewers": [],
            "created_at": (now - timedelta(days=1)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
        }

        human_pr = {
            "id": 100003,
            "number": 44,
            "title": "Fix auth bug",
            "body": "Fixes login issue",
            "state": "open",
            "draft": False,
            "merged_at": None,
            "user": {"login": "developer"},
            "head": {"ref": "fix/login-bug"},
            "base": {"ref": "main"},
            "requested_reviewers": [],
            "created_at": (now - timedelta(days=1)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
        }

        pr_list_response = MagicMock()
        pr_list_response.status_code = 200
        pr_list_response.headers = {}
        pr_list_response.json.return_value = [bot_pr, human_pr]

        review_response = MagicMock()
        review_response.status_code = 200
        review_response.headers = {}
        review_response.json.return_value = []

        async def mock_get(url, **kwargs):
            if "pulls" in url and "reviews" not in url:
                return pr_list_response
            return review_response

        pr_uuid = uuid.uuid4()
        mock_pr = MagicMock()
        mock_pr.id = pr_uuid
        mock_pr.branch_name = "fix/login-bug"
        mock_pr.number = 44

        mock_session.execute = AsyncMock(
            side_effect=_sync_repo_execute(mock_pr, pr_uuid)
        )
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.github_sync.get_installation_token",
                new_callable=AsyncMock,
                return_value="ghs_test_token",
            ),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(get=AsyncMock(side_effect=mock_get)),
            ),
            patch(
                "src.services.github_sync.link_pr_to_ticket",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.github_sync.enqueue_embedding_job",
                new_callable=AsyncMock,
            ),
        ):
            pr_count, _ = await sync_single_repo(
                UUID(TEST_WORKSPACE_ID), "org/repo", mock_session, settings
            )

        # Only human PR should be synced; bot PR skipped
        assert pr_count == 1

    @pytest.mark.asyncio
    async def test_sync_includes_drafts(self, mock_session):
        """sync_single_repo includes draft PRs."""
        from src.services.github_sync import sync_single_repo

        settings = MagicMock()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        draft_pr = {
            "id": 100004,
            "number": 45,
            "title": "WIP: New feature",
            "body": "Work in progress",
            "state": "open",
            "draft": True,
            "merged_at": None,
            "user": {"login": "developer"},
            "head": {"ref": "feat/new-feature"},
            "base": {"ref": "main"},
            "requested_reviewers": [],
            "created_at": (now - timedelta(days=2)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
        }

        pr_list_response = MagicMock()
        pr_list_response.status_code = 200
        pr_list_response.headers = {}
        pr_list_response.json.return_value = [draft_pr]

        review_response = MagicMock()
        review_response.status_code = 200
        review_response.headers = {}
        review_response.json.return_value = []

        async def mock_get(url, **kwargs):
            if "pulls" in url and "reviews" not in url:
                return pr_list_response
            return review_response

        pr_uuid = uuid.uuid4()
        mock_pr = MagicMock()
        mock_pr.id = pr_uuid
        mock_pr.branch_name = "feat/new-feature"
        mock_pr.number = 45

        mock_session.execute = AsyncMock(
            side_effect=_sync_repo_execute(mock_pr, pr_uuid)
        )
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.github_sync.get_installation_token",
                new_callable=AsyncMock,
                return_value="ghs_test_token",
            ),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(get=AsyncMock(side_effect=mock_get)),
            ),
            patch(
                "src.services.github_sync.link_pr_to_ticket",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.github_sync.enqueue_embedding_job",
                new_callable=AsyncMock,
            ),
        ):
            pr_count, _ = await sync_single_repo(
                UUID(TEST_WORKSPACE_ID), "org/repo", mock_session, settings
            )

        assert pr_count == 1  # Draft PR included

    @pytest.mark.asyncio
    async def test_sync_stops_at_60_day_window(self, mock_session):
        """sync_single_repo stops fetching when PRs are older than 60 days."""
        from src.services.github_sync import sync_single_repo

        settings = MagicMock()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Recent PR (within window)
        recent_pr = {
            "id": 100005,
            "number": 46,
            "title": "Recent PR",
            "body": None,
            "state": "open",
            "draft": False,
            "merged_at": None,
            "user": {"login": "developer"},
            "head": {"ref": "feat/recent"},
            "base": {"ref": "main"},
            "requested_reviewers": [],
            "created_at": (now - timedelta(days=10)).isoformat() + "Z",
            "updated_at": (now - timedelta(days=5)).isoformat() + "Z",
        }

        # Old PR (outside 60-day window)
        old_pr = {
            "id": 100006,
            "number": 47,
            "title": "Old PR",
            "body": None,
            "state": "closed",
            "draft": False,
            "merged_at": None,
            "user": {"login": "developer"},
            "head": {"ref": "feat/old"},
            "base": {"ref": "main"},
            "requested_reviewers": [],
            "created_at": (now - timedelta(days=90)).isoformat() + "Z",
            "updated_at": (now - timedelta(days=90)).isoformat() + "Z",
        }

        pr_list_response = MagicMock()
        pr_list_response.status_code = 200
        # Include a Link header to simulate a next page that should NOT be fetched
        pr_list_response.headers = {
            "link": '<https://api.github.com/repos/org/repo/pulls?page=2>; rel="next"'
        }
        pr_list_response.json.return_value = [recent_pr, old_pr]

        review_response = MagicMock()
        review_response.status_code = 200
        review_response.headers = {}
        review_response.json.return_value = []

        get_call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal get_call_count
            get_call_count += 1
            if "pulls" in url and "reviews" not in url:
                return pr_list_response
            return review_response

        pr_uuid = uuid.uuid4()
        mock_pr = MagicMock()
        mock_pr.id = pr_uuid
        mock_pr.branch_name = "feat/recent"
        mock_pr.number = 46

        mock_session.execute = AsyncMock(
            side_effect=_sync_repo_execute(mock_pr, pr_uuid)
        )
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.github_sync.get_installation_token",
                new_callable=AsyncMock,
                return_value="ghs_test_token",
            ),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(get=AsyncMock(side_effect=mock_get)),
            ),
            patch(
                "src.services.github_sync.link_pr_to_ticket",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.github_sync.enqueue_embedding_job",
                new_callable=AsyncMock,
            ),
        ):
            pr_count, _ = await sync_single_repo(
                UUID(TEST_WORKSPACE_ID), "org/repo", mock_session, settings
            )

        # Only the recent PR should be synced; old one triggers cutoff
        assert pr_count == 1
        # Should NOT fetch page 2 because cutoff was reached
        # get_call_count: 1 for PR list + 1 for reviews of the recent PR = 2
        assert get_call_count == 2


# ---------- Per-repo sync status ----------


class TestSyncRepoProgress:
    """Tests for per-repo sync progress tracking."""

    @pytest.mark.asyncio
    async def test_sync_per_repo_progress_tracking(self, mock_session):
        """sync_repos updates per-repo status in config JSONB."""
        from src.services.github_sync import sync_repos

        settings = MagicMock()

        mock_integration = MagicMock()
        mock_integration.config = {"selected_repos": ["org/repo"]}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch(
            "src.services.github_sync.sync_single_repo",
            new_callable=AsyncMock,
            return_value=(5, 3),
        ):
            result = await sync_repos(
                UUID(TEST_WORKSPACE_ID),
                ["org/repo"],
                mock_session,
                settings,
            )

        assert result["total_prs"] == 5
        assert result["total_reviews"] == 3
        assert result["repos"]["org/repo"]["status"] == "synced"

        # Verify config was updated with repo_sync_status
        updated_config = mock_integration.config
        assert "repo_sync_status" in updated_config
        assert updated_config["repo_sync_status"]["org/repo"]["status"] == "synced"


# ---------- link_pr_to_ticket ----------


class TestLinkPrToTicket:
    """Tests for PR-to-Linear ticket linking."""

    @pytest.mark.asyncio
    async def test_link_pr_to_ticket_matches_branch_name(self, mock_session):
        """link_pr_to_ticket sets linear_ticket_id when branch matches a ticket."""
        from src.services.github_linking import link_pr_to_ticket

        ticket_uuid = uuid.uuid4()

        # Mock PR record
        mock_pr = MagicMock()
        mock_pr.branch_name = "feat/ENG-123-add-auth"
        mock_pr.number = 42
        mock_pr.linear_ticket_id = None

        # Mock ticket record
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_uuid

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # get_linear_team_keys query
                result.fetchall.return_value = [("ENG",), ("PROJ",)]
            elif call_count == 2:
                # LinearTicket lookup
                result.scalar_one_or_none.return_value = mock_ticket
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        await link_pr_to_ticket(
            mock_pr, UUID(TEST_WORKSPACE_ID), mock_session
        )

        assert mock_pr.linear_ticket_id == ticket_uuid

    @pytest.mark.asyncio
    async def test_link_pr_to_ticket_stores_unlinked(self, mock_session):
        """link_pr_to_ticket leaves linear_ticket_id as None when no match."""
        from src.services.github_linking import link_pr_to_ticket

        mock_pr = MagicMock()
        mock_pr.branch_name = "my-feature-branch"
        mock_pr.number = 43
        mock_pr.linear_ticket_id = None

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # get_linear_team_keys query
                result.fetchall.return_value = [("ENG",)]
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        await link_pr_to_ticket(
            mock_pr, UUID(TEST_WORKSPACE_ID), mock_session
        )

        # linear_ticket_id should remain None (unlinked)
        assert mock_pr.linear_ticket_id is None
