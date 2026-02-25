"""GitHub repository listing, selection, and caching service.

Provides functions to:
- List available repos from the GitHub API (installation repositories)
- Cache repo lists in workspace_integrations.config JSONB
- Save/retrieve repo selections for PR monitoring
- Check if a specific repo is monitored

Uses httpx.AsyncClient for GitHub API calls with proper Link header pagination.
New repos are NOT auto-monitored (unlike Slack channels -- per user decision).
"""

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import WorkspaceIntegration
from src.services.github_common import GITHUB_API_BASE, github_headers, parse_link_next
from src.services.github_oauth import GitHubOAuthError, get_installation_token

logger = logging.getLogger(__name__)


async def list_repos(
    workspace_id: UUID,
    session: AsyncSession,
    settings: Settings,
) -> list[dict]:
    """Fetch installation repositories from GitHub API and cache in DB.

    Calls GET /installation/repositories with Link header pagination
    to retrieve all repos accessible to the GitHub App installation.
    Caches the result in workspace_integrations.config JSONB under
    the key 'available_repos'.

    Args:
        workspace_id: Workspace whose GitHub integration to query.
        session: Async database session.
        settings: Application settings.

    Returns:
        List of repo dicts with keys: full_name, name, private,
        description, default_branch, language.

    Raises:
        GitHubOAuthError: If no installation token or API call fails.
    """
    token = await get_installation_token(workspace_id, session, settings)

    all_repos: list[dict] = []
    url: str | None = f"{GITHUB_API_BASE}/installation/repositories?per_page=100"

    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, headers=github_headers(token))

            if response.status_code != 200:
                raise GitHubOAuthError(
                    f"GitHub API error listing repos: {response.status_code} {response.text}"
                )

            data = response.json()
            repositories = data.get("repositories", [])

            for repo in repositories:
                all_repos.append({
                    "full_name": repo.get("full_name", ""),
                    "name": repo.get("name", ""),
                    "private": repo.get("private", False),
                    "description": repo.get("description"),
                    "default_branch": repo.get("default_branch", "main"),
                    "language": repo.get("language"),
                })

            # Parse Link header for next page
            url = parse_link_next(response.headers.get("link"))

    # Cache in workspace_integrations.config
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        config["available_repos"] = all_repos
        integration.config = config
        await session.commit()

    return all_repos


async def get_cached_repos(
    workspace_id: UUID,
    session: AsyncSession,
) -> list[dict]:
    """Read cached repo list from workspace_integrations.config.

    Returns the cached 'available_repos' list without hitting the
    GitHub API. Returns empty list if no cache exists.

    Args:
        workspace_id: Workspace to look up.
        session: Async database session.

    Returns:
        List of cached repo dicts, or empty list if no cache.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return []

    return integration.config.get("available_repos", [])


async def refresh_repos(
    workspace_id: UUID,
    session: AsyncSession,
    settings: Settings,
) -> list[dict]:
    """Refresh repo list from GitHub API (forces fresh API call).

    Same as list_repos -- always fetches fresh from GitHub.

    Args:
        workspace_id: Workspace to refresh repos for.
        session: Async database session.
        settings: Application settings.

    Returns:
        List of fresh repo dicts from GitHub API.
    """
    return await list_repos(workspace_id, session, settings)


async def save_selected_repos(
    workspace_id: UUID,
    repo_full_names: list[str],
    session: AsyncSession,
) -> list[str]:
    """Save the user's repo selection to workspace_integrations.config.

    Validates repo_full_names against the cached available_repos list.
    Stores selection in config JSONB under 'selected_repos' key.

    Args:
        workspace_id: Workspace to update.
        repo_full_names: List of repo full_name strings to monitor.
        session: Async database session.

    Returns:
        The saved list of selected repo full_names.

    Raises:
        GitHubOAuthError: If no integration found or invalid repo names.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration:
        raise GitHubOAuthError("No GitHub integration found for this workspace")

    config = dict(integration.config) if integration.config else {}
    available = config.get("available_repos", [])
    available_names = {r["full_name"] for r in available}

    # Validate all selected repos exist in available list
    invalid = [name for name in repo_full_names if name not in available_names]
    if invalid:
        raise GitHubOAuthError(
            f"Invalid repo names not in available repos: {', '.join(invalid)}"
        )

    config["selected_repos"] = repo_full_names
    integration.config = config
    await session.commit()

    return repo_full_names


async def is_repo_monitored(
    workspace_id: UUID,
    repo_full_name: str,
    session: AsyncSession,
) -> bool:
    """Check if a repo is in the selected repos list.

    Unlike Slack channels (which default to all when no selection),
    GitHub repos are NOT auto-monitored. If no selected_repos is
    configured, returns False per user decision.

    Args:
        workspace_id: Workspace to check.
        repo_full_name: Full name of the repo (e.g., "org/repo").
        session: Async database session.

    Returns:
        True if the repo is explicitly selected for monitoring.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return False

    selected = integration.config.get("selected_repos", [])

    if not selected:
        return False  # No auto-monitoring per user decision

    return repo_full_name in selected
