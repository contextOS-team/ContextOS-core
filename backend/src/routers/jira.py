"""Jira OAuth and sync integration endpoints.

Provides connect, callback, disconnect, status, sync, webhook, and
search endpoints for managing the Jira workspace integration.
"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from src.config import Settings, get_settings
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import Provider, WorkspaceIntegration
from src.models.jira import JiraIssue
from src.services.jira_oauth import (
    JiraOAuthError,
    build_auth_url,
    disconnect,
    exchange_code,
    get_valid_token,
)
from src.services.oauth_common import sign_oauth_state, verify_state_or_raise, is_user_onboarding
from src.services.sync_adapter import emit_activity, mark_sync_requested

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jira", tags=["jira"])


@router.get("/connect")
async def connect(
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Generate a Jira OAuth 2.0 (3LO) authorization URL.

    Returns a JSON object with the authorization URL that the frontend
    should redirect the user to.
    """
    state = sign_oauth_state(user.workspace_id, settings.JIRA_CLIENT_SECRET)
    authorization_url = build_auth_url(state, settings)
    return {"authorization_url": authorization_url}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Handle Jira OAuth callback.

    Validates the state parameter, exchanges the authorization code for
    tokens, stores them in Vault, and redirects to the frontend.

    This endpoint is NOT auth-protected because Jira redirects here
    directly. The state parameter provides CSRF protection.
    """
    frontend_url = settings.CORS_ORIGINS.split(",")[0].strip()

    try:
        workspace_id = verify_state_or_raise(state, settings.JIRA_CLIENT_SECRET, JiraOAuthError)
    except JiraOAuthError as e:
        logger.error("Jira OAuth state verification failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&jira=error&reason=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        # Look up the workspace owner for the token record
        from src.models.user import WorkspaceMember

        stmt = select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        user_id = result.scalar_one_or_none()

        if user_id is None:
            return RedirectResponse(
                url=f"{frontend_url}/dashboard/settings?tab=integrations&jira=error&reason=workspace_not_found",
                status_code=status.HTTP_302_FOUND,
            )

        # Mutual exclusion: reject if Linear is already connected
        linear_stmt = select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.provider == Provider.LINEAR,
            WorkspaceIntegration.status == "connected",
        )
        linear_result = await session.execute(linear_stmt)
        if linear_result.scalar_one_or_none() is not None:
            if await is_user_onboarding(session, user_id):
                return RedirectResponse(
                    url=f"{frontend_url}/onboarding?oauth_error=jira&reason=provider_conflict",
                    status_code=status.HTTP_302_FOUND,
                )
            return RedirectResponse(
                url=f"{frontend_url}/dashboard/settings?tab=integrations&jira=error&reason=provider_conflict",
                status_code=status.HTTP_302_FOUND,
            )

        cloud_info = await exchange_code(code, session, workspace_id, user_id, settings)
        site_name = cloud_info.get("site_name", "")

        await emit_activity(
            session, workspace_id, "integration_connected",
            metadata={"integration": "jira"},
            actor_id=user_id,
        )

        if await is_user_onboarding(session, user_id):
            return RedirectResponse(
                url=f"{frontend_url}/onboarding",
                status_code=status.HTTP_302_FOUND,
            )

        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&jira=connected&site={site_name}",
            status_code=status.HTTP_302_FOUND,
        )
    except JiraOAuthError as e:
        logger.error("Jira OAuth code exchange failed: %s", e)

        if user_id and await is_user_onboarding(session, user_id):
            return RedirectResponse(
                url=f"{frontend_url}/onboarding?oauth_error=jira&reason=exchange_failed",
                status_code=status.HTTP_302_FOUND,
            )

        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&jira=error&reason=exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/disconnect")
async def disconnect_jira(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect the Jira integration.

    Soft-deletes OAuth tokens and marks the integration as disconnected.
    Existing issue data is preserved.
    """
    await disconnect(session, user.workspace_id, user.user_id)
    await emit_activity(
        session, user.workspace_id, "integration_disconnected",
        metadata={"integration": "jira"},
        actor_id=user.user_id,
    )
    return {"status": "disconnected"}


@router.get("/status")
async def get_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current Jira integration status.

    Returns connection state, site name, and status for the
    authenticated user's workspace.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.JIRA,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status == "disconnected":
        return {
            "connected": False,
            "site_name": None,
            "status": "disconnected",
        }

    config = integration.config or {}
    return {
        "connected": integration.status == "connected",
        "site_name": config.get("external_name"),
        "cloud_id": config.get("cloud_id"),
        "status": integration.status,
    }


# ---------- Sync Endpoints ----------


class SyncRequest(PydanticBaseModel):
    """Request body for POST /api/jira/sync."""

    jql: str | None = None


@router.post("/sync")
async def start_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Start a background sync of Jira issues.

    Validates that the Jira integration is connected, then runs the
    sync as a FastAPI background task. Returns immediately with status.
    """
    # Verify integration is connected
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.JIRA,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jira integration is not connected. Complete OAuth flow first.",
        )

    mark_sync_requested(integration, "issues_synced")
    await emit_activity(
        session,
        user.workspace_id,
        "sync_started",
        metadata={"integration": "jira"},
        actor_id=user.user_id,
    )
    # Release the integration row before the background sync opens its own
    # session and updates the same config record.
    await session.commit()

    # Start sync in background with its own session
    async def _run_sync():
        from src.db import async_session
        from src.services.jira_sync import sync_jira_issues

        async with async_session() as bg_session:
            try:
                await sync_jira_issues(
                    bg_session,
                    user.workspace_id,
                    settings,
                    jql=body.jql,
                )
                await bg_session.commit()
            except Exception:
                await bg_session.rollback()
                raise

    background_tasks.add_task(_run_sync)

    return {"status": "sync_started", "jql": body.jql}


@router.get("/sync/status")
async def get_sync_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current sync status and issue count.

    Reads sync progress from workspace_integrations.config and counts
    issues in jira_issues for the workspace.
    """
    # Get integration config
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.JIRA,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    config = integration.config if integration else {}

    # Count issues
    count_stmt = select(func.count()).select_from(JiraIssue).where(
        JiraIssue.workspace_id == user.workspace_id,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    count_result = await session.execute(count_stmt)
    issues_count = count_result.scalar_one()

    return {
        "sync_status": config.get("sync_status"),
        "issues_synced": config.get("issues_synced", 0),
        "last_sync_at": config.get("last_sync_at"),
        "issues_count": issues_count,
    }


# ---------- Webhook Endpoint ----------


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Receive Jira webhook events.

    Jira Cloud webhooks are secured via OAuth scopes (manage:jira-webhook),
    NOT via HMAC signatures. The X-Hub-Signature header does not exist in
    Jira webhook requests. Authentication relies on cloud_id matching to
    find the workspace.
    """
    from src.services.jira_webhook import process_jira_webhook

    raw_body = await request.body()
    payload = json.loads(raw_body)

    # Determine workspace from payload
    # Jira webhooks don't include cloud_id directly; we match via the
    # self URL or the webhook registration metadata.
    # For now, try to extract from the issue's self URL or use a header.
    cloud_id = _extract_cloud_id(payload)
    if not cloud_id:
        logger.warning("Could not determine cloud_id from Jira webhook payload")
        return {"status": "ignored", "reason": "unknown_cloud_id"}

    # Look up workspace by cloud_id
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.provider == Provider.JIRA,
        WorkspaceIntegration.external_id == cloud_id,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration:
        logger.warning("No workspace found for Jira cloud_id %s", cloud_id)
        return {"status": "ignored", "reason": "workspace_not_found"}

    await process_jira_webhook(session, payload, integration.workspace_id)
    await session.commit()

    return {"status": "processed"}


def _extract_cloud_id(payload: dict) -> str | None:
    """Extract cloud_id from Jira webhook payload.

    Tries to extract from the issue's self URL, which contains the cloud_id:
    https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue/...

    Falls back to checking common payload locations.
    """
    # Try extracting from issue.self URL
    issue = payload.get("issue", {})
    self_url = issue.get("self", "")
    if "ex/jira/" in self_url:
        parts = self_url.split("ex/jira/")
        if len(parts) > 1:
            cloud_id = parts[1].split("/")[0]
            if cloud_id:
                return cloud_id

    # Try matchedWebhookIds metadata (some Jira configurations)
    # The cloud_id may also be available via the base URL pattern
    return None


# ---------- Search Endpoint ----------


@router.get("/search")
async def search_issues(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    q: str = Query(default="", max_length=200),
) -> dict:
    """Search Jira issues for UI autocomplete.

    When q is empty, returns locally-synced issues assigned to the
    current user (or all recent issues if assignee is unknown).
    When q is provided, proxies search to Jira's API via JQL text search.
    """
    from src.services.jira_sync import list_my_jira_issues, search_jira_issues

    try:
        if not q.strip():
            results = await list_my_jira_issues(session, user.workspace_id, settings)
        else:
            results = await search_jira_issues(session, user.workspace_id, settings, q.strip())
    except JiraOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Jira integration not connected: {e}",
        )

    return {"issues": results, "count": len(results)}
