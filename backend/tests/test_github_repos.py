"""Tests for GitHub repo listing, selection, and caching service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from tests.conftest import TEST_WORKSPACE_ID


# ---------- list_repos / pagination ----------


class TestListRepos:
    """Tests for list_repos and pagination."""

    @pytest.mark.asyncio
    async def test_list_repos_from_github_api(self, mock_session):
        """list_repos fetches repos from GitHub API and returns parsed list."""
        from src.services.github_repos import list_repos

        settings = MagicMock()

        # Mock get_installation_token
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}  # No Link header = single page
        mock_response.json.return_value = {
            "total_count": 2,
            "repositories": [
                {
                    "full_name": "org/repo-a",
                    "name": "repo-a",
                    "private": False,
                    "description": "Repo A description",
                    "default_branch": "main",
                    "language": "Python",
                },
                {
                    "full_name": "org/repo-b",
                    "name": "repo-b",
                    "private": True,
                    "description": None,
                    "default_branch": "develop",
                    "language": "TypeScript",
                },
            ],
        }

        # Mock integration for cache update
        mock_integration = MagicMock()
        mock_integration.config = {"installation_id": 12345}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.github_repos.get_installation_token",
                new_callable=AsyncMock,
                return_value="ghs_test_token",
            ),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    get=AsyncMock(return_value=mock_response),
                ),
            ),
        ):
            repos = await list_repos(
                UUID(TEST_WORKSPACE_ID), mock_session, settings
            )

        assert len(repos) == 2
        assert repos[0]["full_name"] == "org/repo-a"
        assert repos[0]["language"] == "Python"
        assert repos[1]["full_name"] == "org/repo-b"
        assert repos[1]["private"] is True

    @pytest.mark.asyncio
    async def test_list_repos_paginates(self, mock_session):
        """list_repos follows Link header to fetch multiple pages."""
        from src.services.github_repos import list_repos

        settings = MagicMock()

        # Page 1 response with Link header pointing to next
        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.headers = {
            "link": '<https://api.github.com/installation/repositories?page=2&per_page=100>; rel="next"'
        }
        page1_response.json.return_value = {
            "total_count": 3,
            "repositories": [
                {"full_name": "org/repo-1", "name": "repo-1", "private": False,
                 "description": None, "default_branch": "main", "language": "Python"},
                {"full_name": "org/repo-2", "name": "repo-2", "private": False,
                 "description": None, "default_branch": "main", "language": "Go"},
            ],
        }

        # Page 2 response without Link header (last page)
        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.headers = {}
        page2_response.json.return_value = {
            "total_count": 3,
            "repositories": [
                {"full_name": "org/repo-3", "name": "repo-3", "private": True,
                 "description": "Third repo", "default_branch": "main", "language": "Rust"},
            ],
        }

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return page1_response
            return page2_response

        mock_integration = MagicMock()
        mock_integration.config = {"installation_id": 12345}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.github_repos.get_installation_token",
                new_callable=AsyncMock,
                return_value="ghs_test_token",
            ),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(get=AsyncMock(side_effect=mock_get)),
            ),
        ):
            repos = await list_repos(
                UUID(TEST_WORKSPACE_ID), mock_session, settings
            )

        assert len(repos) == 3
        assert repos[2]["full_name"] == "org/repo-3"
        assert call_count == 2  # Two API calls made


# ---------- get_cached_repos ----------


class TestGetCachedRepos:
    """Tests for get_cached_repos."""

    @pytest.mark.asyncio
    async def test_get_cached_repos_returns_empty_when_no_cache(self, mock_session):
        """get_cached_repos returns empty list when no integration exists."""
        from src.services.github_repos import get_cached_repos

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repos = await get_cached_repos(UUID(TEST_WORKSPACE_ID), mock_session)

        assert repos == []

    @pytest.mark.asyncio
    async def test_get_cached_repos_returns_cached_data(self, mock_session):
        """get_cached_repos returns cached repos from config JSONB."""
        from src.services.github_repos import get_cached_repos

        cached = [
            {"full_name": "org/repo-a", "name": "repo-a", "private": False},
            {"full_name": "org/repo-b", "name": "repo-b", "private": True},
        ]
        mock_integration = MagicMock()
        mock_integration.config = {"available_repos": cached}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        repos = await get_cached_repos(UUID(TEST_WORKSPACE_ID), mock_session)

        assert len(repos) == 2
        assert repos[0]["full_name"] == "org/repo-a"


# ---------- refresh_repos ----------


class TestRefreshRepos:
    """Tests for refresh_repos."""

    @pytest.mark.asyncio
    async def test_refresh_repos_updates_cache(self, mock_session):
        """refresh_repos fetches fresh data from GitHub API and updates cache."""
        from src.services.github_repos import refresh_repos

        settings = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "total_count": 1,
            "repositories": [
                {"full_name": "org/new-repo", "name": "new-repo", "private": False,
                 "description": "Fresh repo", "default_branch": "main", "language": "Python"},
            ],
        }

        mock_integration = MagicMock()
        mock_integration.config = {"installation_id": 12345, "available_repos": []}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.github_repos.get_installation_token",
                new_callable=AsyncMock,
                return_value="ghs_test_token",
            ),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    get=AsyncMock(return_value=mock_response),
                ),
            ),
        ):
            repos = await refresh_repos(
                UUID(TEST_WORKSPACE_ID), mock_session, settings
            )

        assert len(repos) == 1
        assert repos[0]["full_name"] == "org/new-repo"

        # Verify cache was updated
        updated_config = mock_integration.config
        assert "available_repos" in updated_config
        assert len(updated_config["available_repos"]) == 1


# ---------- save_selected_repos ----------


class TestSaveSelectedRepos:
    """Tests for save_selected_repos."""

    @pytest.mark.asyncio
    async def test_save_selected_repos_validates_against_cache(self, mock_session):
        """save_selected_repos rejects repo names not in available_repos."""
        from src.services.github_oauth import GitHubOAuthError
        from src.services.github_repos import save_selected_repos

        mock_integration = MagicMock()
        mock_integration.config = {
            "available_repos": [
                {"full_name": "org/repo-a"},
                {"full_name": "org/repo-b"},
            ],
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(GitHubOAuthError, match="Invalid repo names"):
            await save_selected_repos(
                UUID(TEST_WORKSPACE_ID),
                ["org/repo-a", "org/nonexistent"],
                mock_session,
            )

    @pytest.mark.asyncio
    async def test_save_selected_repos_stores_in_config_jsonb(self, mock_session):
        """save_selected_repos stores selection in config JSONB."""
        from src.services.github_repos import save_selected_repos

        mock_integration = MagicMock()
        mock_integration.config = {
            "available_repos": [
                {"full_name": "org/repo-a"},
                {"full_name": "org/repo-b"},
                {"full_name": "org/repo-c"},
            ],
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        result = await save_selected_repos(
            UUID(TEST_WORKSPACE_ID),
            ["org/repo-a", "org/repo-c"],
            mock_session,
        )

        assert result == ["org/repo-a", "org/repo-c"]
        assert mock_integration.config["selected_repos"] == ["org/repo-a", "org/repo-c"]
        mock_session.commit.assert_called_once()


# ---------- is_repo_monitored ----------


class TestIsRepoMonitored:
    """Tests for is_repo_monitored."""

    @pytest.mark.asyncio
    async def test_is_repo_monitored_returns_true_for_selected(self, mock_session):
        """is_repo_monitored returns True for repos in selected_repos."""
        from src.services.github_repos import is_repo_monitored

        mock_integration = MagicMock()
        mock_integration.config = {
            "selected_repos": ["org/repo-a", "org/repo-b"],
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        assert await is_repo_monitored(
            UUID(TEST_WORKSPACE_ID), "org/repo-a", mock_session
        ) is True

    @pytest.mark.asyncio
    async def test_is_repo_monitored_returns_false_when_no_selection(self, mock_session):
        """is_repo_monitored returns False when no repos selected (no auto-monitoring)."""
        from src.services.github_repos import is_repo_monitored

        mock_integration = MagicMock()
        mock_integration.config = {}  # No selected_repos key

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        assert await is_repo_monitored(
            UUID(TEST_WORKSPACE_ID), "org/repo-a", mock_session
        ) is False

    @pytest.mark.asyncio
    async def test_is_repo_monitored_returns_false_for_unselected(self, mock_session):
        """is_repo_monitored returns False for repos not in selected_repos."""
        from src.services.github_repos import is_repo_monitored

        mock_integration = MagicMock()
        mock_integration.config = {
            "selected_repos": ["org/repo-a"],
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        assert await is_repo_monitored(
            UUID(TEST_WORKSPACE_ID), "org/repo-b", mock_session
        ) is False


# ---------- Link header parsing ----------


class TestLinkHeaderParsing:
    """Tests for _parse_link_next helper."""

    def test_parse_link_next_extracts_url(self):
        """_parse_link_next extracts the next URL from Link header."""
        from src.services.github_common import parse_link_next as _parse_link_next

        link = (
            '<https://api.github.com/installation/repositories?page=2&per_page=100>; rel="next", '
            '<https://api.github.com/installation/repositories?page=5&per_page=100>; rel="last"'
        )
        result = _parse_link_next(link)
        assert result == "https://api.github.com/installation/repositories?page=2&per_page=100"

    def test_parse_link_next_returns_none_for_last_page(self):
        """_parse_link_next returns None when no next link."""
        from src.services.github_common import parse_link_next as _parse_link_next

        link = '<https://api.github.com/installation/repositories?page=1&per_page=100>; rel="last"'
        result = _parse_link_next(link)
        assert result is None

    def test_parse_link_next_returns_none_for_empty(self):
        """_parse_link_next returns None for empty/None input."""
        from src.services.github_common import parse_link_next as _parse_link_next

        assert _parse_link_next(None) is None
        assert _parse_link_next("") is None
