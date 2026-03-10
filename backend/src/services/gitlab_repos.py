"""GitLab project listing, selection, and caching service.

Provides functions to:
- List available projects from the GitLab API (user's accessible projects)
- Cache project lists in workspace_integrations.config JSONB
- Save/retrieve project selections for MR monitoring
- Check if a specific project is monitored

Uses httpx.AsyncClient for GitLab API calls with proper Link header pagination.
Uses numeric project IDs (not paths) per research pitfall 2.
"""

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import Provider, WorkspaceIntegration
from src.services.gitlab_common import (
    GITLAB_API_BASE,
    GitLabOAuthError,
    ensure_valid_token,
    gitlab_headers,
    parse_link_next,
)

logger = logging.getLogger(__name__)


async def refresh_repos(
    workspace_id: UUID,
    session: AsyncSession,
    settings: Settings,
) -> list[dict]:
    """Fetch accessible projects from GitLab API and cache in DB.

    Calls GET /projects?membership=true with Link header pagination
    to retrieve all projects accessible to the authenticated user.
    Caches the result in workspace_integrations.config JSONB under
    the key 'available_projects'.

    Args:
        workspace_id: Workspace whose GitLab integration to query.
        session: Async database session.
        settings: Application settings.

    Returns:
        List of project dicts with keys: id, path_with_namespace, name,
        visibility, web_url.

    Raises:
        GitLabOAuthError: If no token or API call fails.
    """
    token = await ensure_valid_token(session, workspace_id, settings)

    all_projects: list[dict] = []
    url: str | None = (
        f"{GITLAB_API_BASE}/projects"
        f"?membership=true&per_page=100&order_by=last_activity_at&sort=desc"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            response = await client.get(url, headers=gitlab_headers(token))

            if response.status_code != 200:
                raise GitLabOAuthError(
                    f"GitLab API error listing projects: {response.status_code} {response.text}"
                )

            projects = response.json()
            for p in projects:
                all_projects.append({
                    "id": p["id"],
                    "path_with_namespace": p.get("path_with_namespace", ""),
                    "name": p.get("name", ""),
                    "visibility": p.get("visibility", "private"),
                    "web_url": p.get("web_url", ""),
                })

            # Parse Link header for next page
            url = parse_link_next(response.headers.get("link"))

    # Cache in workspace_integrations.config
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        config["available_projects"] = all_projects
        integration.config = config
        await session.commit()

    return all_projects


async def get_cached_repos(
    workspace_id: UUID,
    session: AsyncSession,
) -> list[dict]:
    """Read cached project list from workspace_integrations.config.

    Returns the cached 'available_projects' list without hitting the
    GitLab API. Returns empty list if no cache exists.

    Args:
        workspace_id: Workspace to look up.
        session: Async database session.

    Returns:
        List of cached project dicts, or empty list if no cache.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return []

    return integration.config.get("available_projects", [])


async def save_selected_repos(
    workspace_id: UUID,
    project_ids: list[int],
    session: AsyncSession,
) -> list[int]:
    """Save the user's project selection to workspace_integrations.config.

    Validates project_ids against the cached available_projects list.
    Stores selection in config JSONB under 'selected_projects' key.
    Uses numeric project IDs (not paths) per research pitfall 2.

    Args:
        workspace_id: Workspace to update.
        project_ids: List of numeric GitLab project IDs to monitor.
        session: Async database session.

    Returns:
        The saved list of selected project IDs.

    Raises:
        GitLabOAuthError: If no integration found or invalid project IDs.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration:
        raise GitLabOAuthError("No GitLab integration found for this workspace")

    config = dict(integration.config) if integration.config else {}
    available = config.get("available_projects", [])
    available_ids = {p["id"] for p in available}

    # Validate all selected project IDs exist in available list
    invalid = [pid for pid in project_ids if pid not in available_ids]
    if invalid:
        raise GitLabOAuthError(
            f"Invalid project IDs not in available projects: {', '.join(str(i) for i in invalid)}"
        )

    config["selected_projects"] = project_ids
    integration.config = config
    await session.commit()

    return project_ids


async def is_project_monitored(
    workspace_id: UUID,
    project_id: int,
    session: AsyncSession,
) -> bool:
    """Check if a project is in the selected projects list.

    GitLab projects are NOT auto-monitored. If no selected_projects
    is configured, returns False.

    Args:
        workspace_id: Workspace to check.
        project_id: Numeric GitLab project ID.
        session: Async database session.

    Returns:
        True if the project is explicitly selected for monitoring.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return False

    selected = integration.config.get("selected_projects", [])

    if not selected:
        return False

    return project_id in selected
