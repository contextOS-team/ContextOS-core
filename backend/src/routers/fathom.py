"""Fathom integration endpoints.

Provides connect, disconnect, status, and poll endpoints for managing
the Fathom meeting transcript integration.

All endpoints require JWT authentication. The Fathom API key is stored
in Supabase Vault (not in plaintext).
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.fathom import (
    FathomError,
    connect_fathom,
    disconnect_fathom,
    get_fathom_status,
    poll_transcripts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fathom", tags=["fathom"])


@router.post("/connect")
async def connect(
    request: Request,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Connect Fathom integration with an API key.

    Validates the key by calling Fathom API, then stores it in Vault.
    Accepts JSON body: {"api_key": "..."}
    """
    body = await request.json()
    api_key = body.get("api_key", "")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required",
        )

    try:
        result = await connect_fathom(session, user.workspace_id, api_key)
        return result
    except FathomError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/disconnect")
async def disconnect(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect Fathom integration.

    Removes the API key from Vault and marks integration as disconnected.
    Existing transcript data is preserved.
    """
    await disconnect_fathom(session, user.workspace_id)
    return {"status": "disconnected"}


@router.get("/status")
async def get_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current Fathom integration status.

    Returns connection state and last poll timestamp.
    """
    return await get_fathom_status(session, user.workspace_id)


@router.post("/poll")
async def trigger_poll(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger a manual transcript poll from Fathom API.

    Runs the poll in a background task and returns 202 Accepted.
    The 15-minute auto-poll will be a scheduler concern for production.
    """
    background_tasks.add_task(
        _poll_background,
        user.workspace_id,
    )
    return {"status": "polling", "detail": "Transcript poll started in background"}


async def _poll_background(workspace_id) -> None:
    """Run Fathom transcript poll in the background.

    Creates its own database session for isolation (same pattern as
    Slack event background processing).
    """
    from src.db import async_session

    async with async_session() as session:
        try:
            result = await poll_transcripts(session, workspace_id)
            logger.info(
                "Fathom poll completed for workspace %s: %s",
                workspace_id,
                result,
            )
        except Exception:
            logger.exception(
                "Error polling Fathom transcripts for workspace %s",
                workspace_id,
            )
            await session.rollback()
