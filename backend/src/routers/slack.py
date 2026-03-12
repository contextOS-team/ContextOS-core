"""Slack OAuth, Events API, and Channel Management endpoints.

Provides connect, callback, disconnect, status endpoints for managing the
Slack workspace integration, the Events API webhook endpoint for
real-time message ingestion, and channel listing/selection endpoints
for controlling which channels are monitored.

The Events API endpoint is NOT JWT-protected -- Slack sends events directly.
Security is provided by HMAC-SHA256 signature verification using the signing secret.
"""

import json
import logging

import sqlalchemy.exc

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import src.config as config_module
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import Provider, WorkspaceIntegration
from src.models.user import WorkspaceMember
from src.services.slack_channels import (
    get_cached_channels,
    get_selected_channels,
    list_channels as fetch_channels,
    save_channel_selection,
)
from src.services.slack_events import process_event, verify_signature
from src.services.slack_oauth import (
    SlackOAuthError,
    build_auth_url,
    disconnect,
    exchange_code,
)
from src.services.oauth_common import sign_oauth_state, verify_state_or_raise

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack", tags=["slack"])


@router.get("/connect")
async def connect(
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Generate a Slack OAuth V2 authorization URL.

    Returns a JSON object with the authorization URL that the frontend
    should redirect the user to.
    """
    settings = config_module.get_settings()
    state = sign_oauth_state(user.workspace_id, settings.SLACK_CLIENT_SECRET)
    authorization_url = build_auth_url(state, settings)
    return {"authorization_url": authorization_url}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle Slack OAuth callback.

    Validates the state parameter, exchanges the authorization code for
    a bot token, stores it in Vault, and redirects to the frontend.

    This endpoint is NOT auth-protected because Slack redirects here
    directly. The state parameter provides CSRF protection.
    """
    settings = config_module.get_settings()
    frontend_url = settings.CORS_ORIGINS.split(",")[0].strip()

    try:
        workspace_id = verify_state_or_raise(state, settings.SLACK_CLIENT_SECRET, SlackOAuthError)
    except SlackOAuthError as e:
        logger.error("Slack OAuth state verification failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?slack=error&reason=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        # Look up workspace owner for user_id
        stmt = select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        user_id = result.scalar_one_or_none()

        if user_id is None:
            return RedirectResponse(
                url=f"{frontend_url}/dashboard?slack=error&reason=workspace_not_found",
                status_code=status.HTTP_302_FOUND,
            )

        team_info = await exchange_code(code, session, workspace_id, user_id, settings)
        team_name = team_info.get("name", "")

        return RedirectResponse(
            url=f"{frontend_url}/dashboard?slack=connected&team={team_name}",
            status_code=status.HTTP_302_FOUND,
        )
    except SlackOAuthError as e:
        logger.error("Slack OAuth code exchange failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?slack=error&reason=exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/disconnect")
async def disconnect_slack(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect the Slack integration.

    Soft-deletes OAuth tokens and marks the integration as disconnected.
    Existing message data is preserved.
    """
    await disconnect(session, user.workspace_id, user.user_id)
    return {"status": "disconnected"}


@router.get("/status")
async def get_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current Slack integration status.

    Returns connection state, team name, and status for the
    authenticated user's workspace.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.SLACK,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status == "disconnected":
        return {
            "connected": False,
            "team_name": None,
            "status": "disconnected",
        }

    return {
        "connected": integration.status == "connected",
        "team_name": integration.external_id,
        "status": integration.status,
    }


@router.get("/channels")
async def get_channels(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get available Slack channels from cache.

    Returns the cached channel list from workspace_integrations.config.
    Use POST /channels/refresh to fetch fresh data from Slack API.
    """
    channels = await get_cached_channels(session, user.workspace_id)
    selected = await get_selected_channels(session, user.workspace_id)
    return {"channels": channels, "selected_channels": selected}


@router.post("/channels/refresh")
async def refresh_channels(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Refresh the channel list from Slack API.

    Fetches a fresh channel list from the Slack conversations.list API,
    updates the cache, and returns the result. Triggered by the user
    clicking the 'Refresh channels' button.
    """
    try:
        channels = await fetch_channels(session, user.workspace_id)
        return {"channels": channels}
    except SlackOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/channels/select")
async def select_channels(
    request: Request,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Save the user's channel selection.

    Accepts a JSON body with channel_ids to monitor:
    {"channel_ids": ["C123", "C456"]}

    Only messages from selected channels will be ingested.
    """
    body = await request.json()
    channel_ids = body.get("channel_ids", [])

    if not isinstance(channel_ids, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="channel_ids must be a list",
        )

    try:
        await save_channel_selection(session, user.workspace_id, channel_ids)
        return {"status": "ok", "selected_channels": channel_ids}
    except SlackOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/events")
async def receive_slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Receive and process Slack Events API callbacks.

    This endpoint is NOT JWT-protected -- Slack sends events here directly.
    Security is provided by HMAC-SHA256 signature verification using the
    Slack signing secret.

    Handles:
    1. URL verification challenge (required during event subscription setup)
    2. Event callbacks with signature verification and background processing
    """
    settings = config_module.get_settings()

    # Read raw body for signature verification
    raw_body = await request.body()

    # Get Slack headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Parse payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # Handle URL verification challenge (no signature check needed for initial setup)
    if payload.get("type") == "url_verification":
        # Still verify signature if headers are present
        if signature and timestamp:
            if not verify_signature(settings.SLACK_SIGNING_SECRET, timestamp, raw_body, signature):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature",
                )
        return {"challenge": payload.get("challenge", "")}

    # For event callbacks, verify signature
    if not signature or not timestamp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature headers",
        )

    if not verify_signature(settings.SLACK_SIGNING_SECRET, timestamp, raw_body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Handle event_callback
    if payload.get("type") == "event_callback":
        team_id = payload.get("team_id", "")

        # Look up workspace by team_id (matching workspace_integrations.external_id)
        ws_stmt = select(WorkspaceIntegration).where(
            WorkspaceIntegration.provider == Provider.SLACK,
            WorkspaceIntegration.external_id == team_id,
        )
        ws_result = await session.execute(ws_stmt)
        integration = ws_result.scalar_one_or_none()

        if not integration:
            logger.warning("Slack event for unknown team %s", team_id)
            return {"status": "unknown_team"}

        # Delegate event processing to background task for fast response
        background_tasks.add_task(
            _process_event_background,
            payload,
            integration.workspace_id,
        )

    return {"status": "ok"}


async def _process_event_background(
    payload: dict,
    workspace_id,
) -> None:
    """Process a Slack event in the background.

    Creates its own database session for isolation (same pattern as
    Linear webhook background processing).

    Args:
        payload: The full Slack event callback payload.
        workspace_id: The workspace this event belongs to.
    """
    from src.db import async_session

    async with async_session() as session:
        try:
            await process_event(payload, workspace_id, session)
        except (sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError):
            logger.exception(
                "Error processing Slack event for workspace %s",
                workspace_id,
            )
            await session.rollback()
