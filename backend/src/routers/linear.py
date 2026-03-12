"""Linear OAuth and sync integration endpoints.

Provides connect, callback, disconnect, status, team selection, and
sync endpoints for managing the Linear workspace integration.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from src.config import Settings, get_settings
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import Provider, WorkspaceIntegration
from src.models.ticket import LinearTicket
from src.services.linear_oauth import (
    OAuthError,
    build_auth_url,
    disconnect,
    exchange_code,
    get_valid_access_token,
)
from src.services.oauth_common import sign_oauth_state, verify_state_or_raise
from src.services.linear_graphql import LinearAPIError, LinearGraphQLClient
from src.services.linear_sync import fetch_teams, sync_tickets_for_teams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/linear", tags=["linear"])


@router.get("/connect")
async def connect(
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Generate a Linear OAuth authorization URL.

    Returns a JSON object with the authorization URL that the frontend
    should redirect the user to.
    """
    state = sign_oauth_state(user.workspace_id, settings.LINEAR_CLIENT_SECRET)
    authorization_url = build_auth_url(state, settings)
    return {"authorization_url": authorization_url}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Handle Linear OAuth callback.

    Validates the state parameter, exchanges the authorization code for
    tokens, stores them in Vault, and redirects to the frontend.

    This endpoint is NOT auth-protected because Linear redirects here
    directly. The state parameter provides CSRF protection.
    """
    frontend_url = settings.CORS_ORIGINS.split(",")[0].strip()

    try:
        workspace_id = verify_state_or_raise(state, settings.LINEAR_CLIENT_SECRET, OAuthError)
    except OAuthError as e:
        logger.error("OAuth state verification failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&linear=error&reason=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        # We need a user_id for the token record. Extract from state
        # In a full implementation, state would also encode user_id.
        # For now, we look up the workspace owner.
        from src.models.user import WorkspaceMember

        stmt = select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        user_id = result.scalar_one_or_none()

        if user_id is None:
            return RedirectResponse(
                url=f"{frontend_url}/dashboard/settings?tab=integrations&linear=error&reason=workspace_not_found",
                status_code=status.HTTP_302_FOUND,
            )

        # Mutual exclusion: reject if Jira is already connected
        jira_stmt = select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.provider == Provider.JIRA,
        )
        jira_result = await session.execute(jira_stmt)
        if jira_result.scalar_one_or_none() is not None:
            return RedirectResponse(
                url=f"{frontend_url}/dashboard/settings?tab=integrations&linear=error&reason=provider_conflict",
                status_code=status.HTTP_302_FOUND,
            )

        org_info = await exchange_code(code, session, workspace_id, user_id, settings)
        org_name = org_info.get("name", "")

        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&linear=connected&org={org_name}",
            status_code=status.HTTP_302_FOUND,
        )
    except OAuthError as e:
        logger.error("OAuth code exchange failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?tab=integrations&linear=error&reason=exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/disconnect")
async def disconnect_linear(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect the Linear integration.

    Soft-deletes OAuth tokens and marks the integration as disconnected.
    Existing ticket data is preserved.
    """
    await disconnect(session, user.workspace_id, user.user_id)
    return {"status": "disconnected"}


@router.get("/status")
async def get_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current Linear integration status.

    Returns connection state, organization name, and status for the
    authenticated user's workspace.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.LINEAR,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status == "disconnected":
        return {
            "connected": False,
            "organization_name": None,
            "status": "disconnected",
        }

    # Fetch organization name from integration config or external_id
    return {
        "connected": integration.status == "connected",
        "organization_name": integration.external_id,
        "status": integration.status,
    }


# ---------- Team Selection ----------


@router.get("/teams")
async def get_teams(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Fetch the list of Linear teams for the connected organization.

    Reads the access token from Vault and queries Linear's GraphQL API
    for all teams in the organization.
    """
    try:
        access_token = await get_valid_access_token(
            session, user.workspace_id, user.user_id, settings
        )
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Linear integration not connected: {e}",
        )

    teams = await fetch_teams(access_token)
    return {"teams": teams}


# ---------- Sync Endpoints ----------


class SyncRequest(PydanticBaseModel):
    """Request body for POST /api/linear/sync."""

    team_ids: list[str]


@router.post("/sync")
async def start_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Start a background sync of Linear tickets for selected teams.

    Validates that the Linear integration is connected, then runs the
    sync as a FastAPI background task. Returns immediately with status.
    """
    # Verify integration is connected
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.LINEAR,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Linear integration is not connected. Complete OAuth flow first.",
        )

    # Start sync in background with its own session
    # (request session closes when response is sent, before background task runs)
    async def _run_sync():
        from src.db import async_session
        async with async_session() as bg_session:
            try:
                await sync_tickets_for_teams(
                    bg_session,
                    user.workspace_id,
                    user.user_id,
                    body.team_ids,
                    settings,
                )
                await bg_session.commit()
            except Exception:
                await bg_session.rollback()
                raise

    background_tasks.add_task(_run_sync)

    return {"status": "sync_started", "team_ids": body.team_ids}


@router.get("/sync/status")
async def get_sync_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current sync status and ticket count.

    Reads sync progress from workspace_integrations.config and counts
    tickets in linear_tickets for the workspace.
    """
    # Get integration config
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.LINEAR,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    config = integration.config if integration else {}

    # Count tickets
    count_stmt = select(func.count()).select_from(LinearTicket).where(
        LinearTicket.workspace_id == user.workspace_id,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    count_result = await session.execute(count_stmt)
    tickets_count = count_result.scalar_one()

    return {
        "synced_teams": config.get("synced_teams", []),
        "sync_status": config.get("sync_status"),
        "last_sync_at": config.get("last_sync_at"),
        "tickets_count": tickets_count,
    }


# ---------- Ticket Search ----------

SEARCH_ISSUES_QUERY = """
query($query: String!, $first: Int!, $after: String) {
    issueSearch(query: $query, first: $first, after: $after) {
        nodes {
            id
            identifier
            title
            state { name type }
            assignee { name }
            team { key name }
            priority
            updatedAt
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""

ASSIGNED_ISSUES_QUERY = """
query($first: Int!, $after: String) {
    viewer {
        assignedIssues(
            first: $first,
            after: $after,
            filter: { state: { type: { nin: ["canceled", "completed"] } } },
            orderBy: updatedAt
        ) {
            nodes {
                id
                identifier
                title
                state { name type }
                assignee { name }
                team { key name }
                priority
                updatedAt
            }
            pageInfo { hasNextPage endCursor }
        }
    }
}
"""


@router.get("/tickets/search")
async def search_tickets(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    after: str | None = Query(default=None),
) -> dict:
    """Search Linear tickets via the API.

    If a query is provided, uses Linear's issue search. Otherwise returns
    the user's most recently updated assigned issues.  Supports cursor-based
    pagination via the ``after`` parameter.
    """
    try:
        access_token = await get_valid_access_token(
            session, user.workspace_id, user.user_id, settings
        )
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Linear integration not connected: {e}",
        )

    client = LinearGraphQLClient(access_token)
    try:
        variables: dict = {"first": limit}
        if after:
            variables["after"] = after

        if q.strip():
            variables["query"] = q.strip()
            data = await client.query(SEARCH_ISSUES_QUERY, variables)
            connection = data.get("data", {}).get("issueSearch", {})
        else:
            data = await client.query(ASSIGNED_ISSUES_QUERY, variables)
            connection = (
                data.get("data", {})
                .get("viewer", {})
                .get("assignedIssues", {})
            )

        nodes = connection.get("nodes", [])
        page_info = connection.get("pageInfo", {})
    except LinearAPIError as e:
        logger.error("Linear API error during ticket search: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Linear API error: {e.message}",
        )
    finally:
        await client.close()

    tickets = [
        {
            "id": n["id"],
            "identifier": n["identifier"],
            "title": n["title"],
            "state": n.get("state", {}).get("name"),
            "state_type": n.get("state", {}).get("type"),
            "assignee": n.get("assignee", {}).get("name") if n.get("assignee") else None,
            "team_key": n.get("team", {}).get("key"),
            "team_name": n.get("team", {}).get("name"),
            "priority": n.get("priority"),
            "updated_at": n.get("updatedAt"),
        }
        for n in nodes
    ]

    return {
        "tickets": tickets,
        "count": len(tickets),
        "has_next_page": page_info.get("hasNextPage", False),
        "end_cursor": page_info.get("endCursor"),
    }
