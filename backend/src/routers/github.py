"""GitHub App OAuth integration endpoints.

Provides connect, callback, disconnect, and status endpoints for managing
the GitHub App installation integration.

The callback endpoint is NOT JWT-protected because GitHub redirects here
directly. The state parameter provides CSRF protection via HMAC-SHA256.
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

import src.config as config_module
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.github_oauth import (
    GitHubOAuthError,
    _sign_state,
    _verify_state,
    build_install_url,
    disconnect,
    get_status,
    handle_callback,
)

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
    state = _sign_state(user.workspace_id, settings.GITHUB_CLIENT_SECRET)
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
            url=f"{frontend_url}/dashboard?github=connected&account={account}",
            status_code=status.HTTP_302_FOUND,
        )
    except GitHubOAuthError as e:
        logger.error("GitHub App callback failed: %s", e)
        reason = "invalid_state" if "state" in str(e).lower() else "callback_failed"
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?github=error&reason={reason}",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/disconnect")
async def disconnect_github(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect the GitHub integration.

    Soft-deletes OAuth tokens and marks the integration as disconnected.
    Existing PR data is preserved.
    """
    await disconnect(session, user.workspace_id, user.user_id)
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
