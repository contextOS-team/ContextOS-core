"""Linear OAuth integration endpoints.

Provides connect, callback, disconnect, and status endpoints for
managing the Linear workspace integration via OAuth2.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings, get_settings
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import WorkspaceIntegration
from src.services.linear_oauth import (
    OAuthError,
    _sign_state,
    _verify_state,
    build_auth_url,
    disconnect,
    exchange_code,
)

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
    state = _sign_state(user.workspace_id, settings.LINEAR_CLIENT_SECRET)
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
        workspace_id = _verify_state(state, settings.LINEAR_CLIENT_SECRET)
    except OAuthError as e:
        logger.error("OAuth state verification failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?linear=error&reason=invalid_state",
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
                url=f"{frontend_url}/dashboard?linear=error&reason=workspace_not_found",
                status_code=status.HTTP_302_FOUND,
            )

        org_info = await exchange_code(code, session, workspace_id, user_id, settings)
        org_name = org_info.get("name", "")

        return RedirectResponse(
            url=f"{frontend_url}/dashboard?linear=connected&org={org_name}",
            status_code=status.HTTP_302_FOUND,
        )
    except OAuthError as e:
        logger.error("OAuth code exchange failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?linear=error&reason=exchange_failed",
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
        WorkspaceIntegration.provider == "linear",
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
