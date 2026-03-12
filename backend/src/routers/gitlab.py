"""GitLab integration endpoints.

Provides OAuth connect/callback/disconnect/status endpoints, project listing/
selection endpoints, MR sync trigger/status endpoints, and webhook endpoint.

The callback endpoint is NOT JWT-protected because GitLab redirects here
directly. The state parameter provides CSRF protection via HMAC-SHA256.
The webhook endpoint is NOT JWT-protected -- it uses X-Gitlab-Token verification.
"""

import logging

import httpx
import sqlalchemy.exc

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import src.config as config_module
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import Provider, WorkspaceIntegration
from src.services.gitlab_common import GitLabOAuthError
from src.services.gitlab_oauth import (
    build_auth_url,
    disconnect,
    get_status,
    handle_callback,
)
from src.services.gitlab_repos import (
    get_cached_repos,
    refresh_repos,
    save_selected_repos,
)
from src.services.code_index_worker import enqueue_workspace_index_job
from src.services.gitlab_sync import sync_projects
from src.services.gitlab_webhook import process_gitlab_event, verify_webhook_token
from src.services.oauth_common import sign_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gitlab", tags=["gitlab"])


@router.get("/connect")
async def connect(
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Generate a GitLab OAuth2 authorization URL.

    Returns a JSON object with the authorization URL that the frontend
    should redirect the user to authorize the GitLab integration.
    """
    settings = config_module.get_settings()
    state = sign_oauth_state(user.workspace_id, settings.GITLAB_CLIENT_SECRET)
    authorization_url = build_auth_url(state, settings)
    return {"authorization_url": authorization_url}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle GitLab OAuth2 callback.

    After the user authorizes, GitLab redirects here with an
    authorization code. We exchange it for tokens and store them.

    This endpoint is NOT auth-protected because GitLab redirects here
    directly. The state parameter provides CSRF protection.
    """
    settings = config_module.get_settings()
    frontend_url = settings.CORS_ORIGINS.split(",")[0].strip()

    try:
        result = await handle_callback(
            code=code,
            state=state,
            session=session,
            settings=settings,
        )
        account = result.get("account", "")
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&gitlab=connected&account={account}",
            status_code=status.HTTP_302_FOUND,
        )
    except GitLabOAuthError as e:
        logger.error("GitLab OAuth callback failed: %s", e)
        reason = "invalid_state" if "state" in str(e).lower() else "callback_failed"
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&gitlab=error&reason={reason}",
            status_code=status.HTTP_302_FOUND,
        )
    except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError) as e:
        logger.exception("Unexpected error in GitLab callback: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&gitlab=error&reason=internal_error",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/disconnect")
async def disconnect_gitlab(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect the GitLab integration.

    Soft-deletes OAuth tokens, deletes Vault secrets, and marks the
    integration as disconnected. Existing MR data is preserved.
    """
    settings = config_module.get_settings()
    await disconnect(session, user.workspace_id, user.user_id, settings)
    return {"status": "disconnected"}


@router.get("/status")
async def get_gitlab_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current GitLab integration status.

    Returns connection state, account name, and status for the
    authenticated user's workspace.
    """
    return await get_status(user.workspace_id, session)


# ---------- Project listing and selection ----------


class ProjectSelectRequest(BaseModel):
    """Request body for selecting projects to monitor."""

    project_ids: list[int]


async def _get_selected_projects(
    workspace_id, session: AsyncSession
) -> list[int]:
    """Read selected_projects from workspace_integrations config."""
    from sqlmodel import select as sm_select

    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()
    if not integration or not integration.config:
        return []
    return integration.config.get("selected_projects", [])


@router.get("/repos")
async def get_repos(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get cached list of available projects and current selection.

    Returns the cached project list and selected_projects from
    workspace_integrations.config without making a GitLab API call.
    Use POST /repos/refresh to fetch a fresh list from GitLab.
    """
    repos = await get_cached_repos(user.workspace_id, session)
    selected = await _get_selected_projects(user.workspace_id, session)
    return {"repos": repos, "selected_projects": selected}


@router.post("/repos/refresh")
async def refresh_repos_endpoint(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Refresh project list from GitLab API.

    Fetches a fresh list of accessible projects from the
    GitLab API and updates the cache.
    """
    settings = config_module.get_settings()
    try:
        repos = await refresh_repos(user.workspace_id, session, settings)
        selected = await _get_selected_projects(user.workspace_id, session)
        return {"repos": repos, "selected_projects": selected}
    except GitLabOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/repos/select")
async def select_repos(
    body: ProjectSelectRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Select projects to monitor for MR sync and webhooks.

    Validates the provided project IDs against the cached available
    projects list and saves the selection. Uses numeric IDs.
    """
    try:
        selected = await save_selected_repos(
            user.workspace_id, body.project_ids, session
        )
        return {"selected_projects": selected}
    except GitLabOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------- MR sync ----------


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger MR sync for selected projects.

    Runs the sync in a background task and returns 202 immediately.
    Check GET /sync/status for progress.
    """
    from sqlmodel import select as sm_select

    settings = config_module.get_settings()

    # Get selected projects from config
    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitLab integration found",
        )

    selected_projects = integration.config.get("selected_projects", [])
    if not selected_projects:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No projects selected for sync",
        )

    # Import async session factory for background task isolation
    from src.db import async_session

    async def _run_sync():
        async with async_session() as bg_session:
            await sync_projects(
                user.workspace_id, selected_projects, bg_session, settings
            )

    # TODO(Phase 28): Replace BackgroundTasks with Redis queue for durability.
    # FastAPI BackgroundTasks are lost on server restart, unlike the GitHub
    # integration which uses Redis Streams for reliable background processing.
    background_tasks.add_task(_run_sync)

    return {"status": "sync_started", "projects": selected_projects}


@router.get("/sync/status")
async def get_sync_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get per-project sync status.

    Reads project_sync_status from workspace_integrations.config JSONB.
    """
    from sqlmodel import select as sm_select

    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return {"project_sync_status": {}}

    return {
        "project_sync_status": integration.config.get("project_sync_status", {})
    }


# ---------- Webhook ----------


@router.post("/webhook")
async def webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Receive GitLab webhook events.

    Verifies the X-Gitlab-Token header and processes the event.
    NOT auth-protected -- uses webhook secret verification instead.
    """
    settings = config_module.get_settings()

    # Verify webhook token
    gitlab_token = request.headers.get("X-Gitlab-Token", "")
    if not await verify_webhook_token(gitlab_token, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook token",
        )

    payload = await request.json()
    await process_gitlab_event(payload, session, settings)

    return {"status": "ok"}


# ---------- Code indexing ----------


@router.post("/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_index(
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Trigger code indexing for all selected GitLab projects.

    Enqueues a workspace-wide code index job with provider="gitlab"
    for async processing. Returns 202 immediately. Check
    GET /index/status for progress.
    """
    await enqueue_workspace_index_job(user.workspace_id, provider="gitlab")
    return {"status": "accepted", "message": "Code indexing started for selected GitLab projects"}


@router.get("/index/status")
async def get_index_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get code indexing status for GitLab projects.

    Returns the current indexing state, last indexed timestamp,
    and per-project chunk counts filtered to GitLab projects only.
    """
    from sqlalchemy import func
    from sqlmodel import select as sm_select

    from src.models.code_chunk import CodeChunk

    # Get indexing status from workspace_integrations config
    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    config = integration.config if integration and integration.config else {}
    index_status = config.get("code_index_status", "idle")
    last_indexed_at = config.get("code_index_last_at")

    # Build set of GitLab project paths to filter chunks
    available_repos = config.get("available_projects", [])
    gitlab_paths = {r.get("path_with_namespace", "") for r in available_repos if r.get("path_with_namespace")}

    repos: list[dict] = []
    if gitlab_paths:
        # Get per-repo chunk counts filtered to GitLab projects
        chunk_stmt = (
            sm_select(
                CodeChunk.repo_full_name,
                func.count(CodeChunk.id).label("chunk_count"),
            )
            .where(
                CodeChunk.workspace_id == user.workspace_id,
                CodeChunk.deleted_at.is_(None),  # type: ignore[union-attr]
                CodeChunk.repo_full_name.in_(gitlab_paths),  # type: ignore[union-attr]
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
