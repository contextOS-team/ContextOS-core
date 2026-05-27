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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
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
from src.services.gitlab_sync_worker import enqueue_gitlab_sync_job
from src.services.gitlab_webhook import process_gitlab_event, verify_webhook_token
from src.services.oauth_common import sign_oauth_state, verify_state_or_raise
from src.services.sync_adapter import emit_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gitlab", tags=["gitlab"])


def _normalize_project_sync_status(
    project_sync_status: dict,
    cursor_statuses: dict[str, str],
) -> dict:
    """Prefer durable cursor terminal states over stale JSONB progress rows."""
    normalized = {}
    for project_id, status_row in project_sync_status.items():
        if not isinstance(status_row, dict):
            normalized[project_id] = status_row
            continue

        next_row = dict(status_row)
        cursor_status = cursor_statuses.get(str(project_id))
        synced = next_row.get("synced")
        total = next_row.get("total")
        has_complete_progress = (
            isinstance(synced, int)
            and isinstance(total, int)
            and total > 0
            and synced >= total
        )
        if (
            next_row.get("status") == "syncing"
            and cursor_status in {"error", "failed", "timeout"}
        ):
            next_row["status"] = cursor_status
        elif (
            next_row.get("status") == "syncing"
            and (cursor_status == "complete" or has_complete_progress)
        ):
            next_row["status"] = "synced"
        normalized[project_id] = next_row

    return normalized


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

        # Emit integration_connected event
        try:
            workspace_id = verify_state_or_raise(state, settings.GITLAB_CLIENT_SECRET, GitLabOAuthError)
            await emit_activity(
                session, workspace_id, "integration_connected",
                metadata={"integration": "gitlab"},
            )
        except Exception:
            pass  # Non-critical

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
    await emit_activity(
        session, user.workspace_id, "integration_disconnected",
        metadata={"integration": "gitlab"},
        actor_id=user.user_id,
    )
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
    projects list and saves the selection. Auto-triggers MR sync
    for the selected projects via Redis Stream.
    """
    try:
        selected = await save_selected_repos(
            user.workspace_id, body.project_ids, session
        )

        # Auto-trigger MR sync for selected projects
        if selected:
            await enqueue_gitlab_sync_job(user.workspace_id, selected)

        return {"selected_projects": selected}
    except GitLabOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------- MR sync ----------


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger MR sync for selected projects.

    Enqueues a sync job via Redis Stream for crash resilience.
    Check GET /sync/status for progress.
    """
    from sqlmodel import select as sm_select

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

    await enqueue_gitlab_sync_job(user.workspace_id, selected_projects)

    return {"status": "sync_started", "projects": selected_projects}


@router.get("/sync/status")
async def get_sync_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get MR sync status with total counts from DB.

    Returns per-project sync status from JSONB plus aggregate MR/review
    counts queried from the database for accurate totals.
    """
    from sqlalchemy import func
    from sqlmodel import select as sm_select

    from src.models.gitlab import GitlabMergeRequest, GitlabReview

    stmt = sm_select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    project_sync_status = {}
    config_last_sync_at = None
    if integration and integration.config:
        project_sync_status = integration.config.get("project_sync_status", {})
        config_last_sync_at = integration.config.get("last_sync_at")

    cursor_statuses = {}
    cursor_last_sync_at = None
    if project_sync_status:
        from src.models.sync import SyncCursor

        cursor_result = await session.execute(
            sm_select(
                SyncCursor.resource_type,
                SyncCursor.sync_status,
                SyncCursor.last_sync_at,
            ).where(
                SyncCursor.workspace_id == user.workspace_id,
                SyncCursor.provider == "gitlab",
            )
        )
        for resource_type, sync_status, last_sync_at in cursor_result.fetchall():
            cursor_statuses[str(resource_type)] = sync_status
            if last_sync_at and (
                cursor_last_sync_at is None or last_sync_at > cursor_last_sync_at
            ):
                cursor_last_sync_at = last_sync_at

        project_sync_status = _normalize_project_sync_status(
            project_sync_status,
            cursor_statuses,
        )

    # Get actual MR and review counts from DB
    mr_count_result = await session.execute(
        sm_select(func.count(GitlabMergeRequest.id)).where(
            GitlabMergeRequest.workspace_id == user.workspace_id,
            GitlabMergeRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    total_mrs = mr_count_result.scalar() or 0

    review_count_result = await session.execute(
        sm_select(func.count(GitlabReview.id)).where(
            GitlabReview.workspace_id == user.workspace_id,
            GitlabReview.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    total_reviews = review_count_result.scalar() or 0

    # Check if any project is currently syncing
    is_syncing = any(
        p.get("status") == "syncing"
        for p in project_sync_status.values()
    )

    return {
        "project_sync_status": project_sync_status,
        "total_mrs": total_mrs,
        "total_reviews": total_reviews,
        "is_syncing": is_syncing,
        "last_sync_at": (
            cursor_last_sync_at.isoformat() if cursor_last_sync_at else config_last_sync_at
        ),
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
        "progress": config.get("code_index_progress"),
        "total": config.get("code_index_total"),
        "current_repo": config.get("code_index_current_repo"),
    }
