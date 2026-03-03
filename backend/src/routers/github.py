"""GitHub App integration endpoints.

Provides OAuth connect/callback/disconnect/status endpoints, repo listing/
selection endpoints, PR sync trigger/status endpoints, and code index
trigger/status endpoints.

The callback endpoint is NOT JWT-protected because GitHub redirects here
directly. The state parameter provides CSRF protection via HMAC-SHA256.
"""

import logging

import httpx
import sqlalchemy.exc

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import src.config as config_module
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import Provider, WorkspaceIntegration
from src.services.github_oauth import (
    GitHubOAuthError,
    build_install_url,
    disconnect,
    get_status,
    handle_callback,
)
from src.services.oauth_common import sign_oauth_state
from src.services.code_index_worker import enqueue_code_index_job, enqueue_workspace_index_job
from src.services.github_repos import (
    get_cached_repos,
    is_repo_monitored,
    refresh_repos,
    save_selected_repos,
)
from src.services.github_sync import sync_repos

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/connect")
async def connect(
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Generate a GitHub App installation URL.

    Returns a JSON object with the installation URL that the frontend
    should redirect the user to install the GitHub App.
    """
    settings = config_module.get_settings()
    state = sign_oauth_state(user.workspace_id, settings.GITHUB_CLIENT_SECRET)
    installation_url = build_install_url(state, settings)
    return {"installation_url": installation_url}


@router.get("/callback")
async def callback(
    installation_id: int = Query(...),
    setup_action: str = Query(default="install"),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle GitHub App installation callback.

    After the user installs the GitHub App on their org/account, GitHub
    redirects here with the installation_id. We generate an installation
    access token and store it in Vault.

    This endpoint is NOT auth-protected because GitHub redirects here
    directly. The state parameter provides CSRF protection.
    """
    settings = config_module.get_settings()
    frontend_url = settings.CORS_ORIGINS.split(",")[0].strip()

    try:
        result = await handle_callback(
            installation_id=installation_id,
            setup_action=setup_action,
            state=state,
            session=session,
            settings=settings,
        )
        account = result.get("account", "")
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/integrations?github=connected&account={account}",
            status_code=status.HTTP_302_FOUND,
        )
    except GitHubOAuthError as e:
        logger.error("GitHub App callback failed: %s", e)
        reason = "invalid_state" if "state" in str(e).lower() else "callback_failed"
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/integrations?github=error&reason={reason}",
            status_code=status.HTTP_302_FOUND,
        )
    except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError) as e:
        logger.exception("Unexpected error in GitHub callback: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/integrations?github=error&reason=internal_error",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/disconnect")
async def disconnect_github(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect the GitHub integration and uninstall the GitHub App.

    Removes the app from the user's GitHub account/org, soft-deletes
    OAuth tokens, and marks the integration as disconnected.
    Existing PR data is preserved.
    """
    settings = config_module.get_settings()
    await disconnect(session, user.workspace_id, user.user_id, settings)
    return {"status": "disconnected"}


@router.get("/status")
async def get_github_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current GitHub integration status.

    Returns connection state, account name, and status for the
    authenticated user's workspace.
    """
    return await get_status(user.workspace_id, session)


# ---------- Repo listing and selection ----------


class RepoSelectRequest(BaseModel):
    """Request body for selecting repos to monitor."""

    repo_full_names: list[str]


@router.get("/repos")
async def get_repos(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get cached list of available repos.

    Returns the cached repo list from workspace_integrations.config
    without making a GitHub API call. Use POST /repos/refresh to
    fetch a fresh list from GitHub.
    """
    repos = await get_cached_repos(user.workspace_id, session)
    return {"repos": repos}


@router.post("/repos/refresh")
async def refresh_repos_endpoint(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Refresh repo list from GitHub API.

    Fetches a fresh list of installation repositories from the
    GitHub API and updates the cache.
    """
    settings = config_module.get_settings()
    try:
        repos = await refresh_repos(user.workspace_id, session, settings)
        return {"repos": repos}
    except GitHubOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/repos/select")
async def select_repos(
    body: RepoSelectRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Select repos to monitor for PR sync and webhooks.

    Validates the provided repo names against the cached available
    repos list and saves the selection.
    """
    try:
        selected = await save_selected_repos(
            user.workspace_id, body.repo_full_names, session
        )
        return {"selected_repos": selected}
    except GitHubOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------- PR sync ----------


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger PR sync for selected repos.

    Runs the sync in a background task and returns 202 immediately.
    Check GET /sync/status for progress.
    """
    from sqlmodel import select as sm_select

    settings = config_module.get_settings()

    # Get selected repos from config
    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.GITHUB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub integration found",
        )

    selected_repos = integration.config.get("selected_repos", [])
    if not selected_repos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No repos selected for sync",
        )

    # Import async session factory for background task isolation
    from src.db import async_session

    async def _run_sync():
        async with async_session() as bg_session:
            await sync_repos(
                user.workspace_id, selected_repos, bg_session, settings
            )

    background_tasks.add_task(_run_sync)

    return {"status": "sync_started", "repos": selected_repos}


@router.get("/sync/status")
async def get_sync_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get per-repo sync status.

    Reads repo_sync_status from workspace_integrations.config JSONB.
    """
    from sqlmodel import select as sm_select

    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.GITHUB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return {"repo_sync_status": {}}

    return {
        "repo_sync_status": integration.config.get("repo_sync_status", {})
    }


# ---------- Code indexing ----------


@router.post("/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_index(
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Trigger code indexing for all selected repos in the workspace.

    Enqueues a workspace-wide code index job for async processing.
    Returns 202 immediately. Check GET /index/status for progress.
    """
    await enqueue_workspace_index_job(user.workspace_id)
    return {
        "status": "accepted",
        "message": "Code indexing started for all selected repos",
    }


@router.post("/index/{repo_full_name:path}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_repo_index(
    repo_full_name: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger code indexing for a specific repo.

    Validates the repo is monitored, then enqueues a single-repo
    code index job. Returns 202 immediately.
    """
    monitored = await is_repo_monitored(user.workspace_id, repo_full_name, session)
    if not monitored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repo {repo_full_name} is not monitored",
        )

    await enqueue_code_index_job(user.workspace_id, repo_full_name)
    return {"status": "accepted", "repo": repo_full_name}


@router.get("/index/status")
async def get_index_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get code indexing status for the workspace.

    Returns the current indexing state, last indexed timestamp,
    and per-repo chunk counts from the code_chunks table.
    """
    from sqlalchemy import func, text as sa_text
    from sqlmodel import select as sm_select

    from src.models.code_chunk import CodeChunk

    # Get indexing status from workspace_integrations config
    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.GITHUB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    config = integration.config if integration and integration.config else {}
    index_status = config.get("code_index_status", "idle")
    last_indexed_at = config.get("code_index_last_at")

    # Get per-repo chunk counts
    chunk_stmt = (
        sm_select(
            CodeChunk.repo_full_name,
            func.count(CodeChunk.id).label("chunk_count"),
        )
        .where(
            CodeChunk.workspace_id == user.workspace_id,
            CodeChunk.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(CodeChunk.repo_full_name)
    )
    chunk_result = await session.execute(chunk_stmt)
    repos = [
        {"repo": row.repo_full_name, "chunks": row.chunk_count}
        for row in chunk_result.fetchall()
    ]

    return {
        "status": index_status,
        "last_indexed_at": last_indexed_at,
        "repos": repos,
    }
