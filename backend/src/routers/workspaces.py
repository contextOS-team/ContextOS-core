"""Workspace CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.workspace import get_workspace_by_id

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("/current")
async def get_current_workspace_info(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return current workspace info for the authenticated user.

    Queries the workspace by the user's workspace_id from the dependency.
    """
    workspace = await get_workspace_by_id(session, user.workspace_id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "slug": workspace.slug,
        "created_at": workspace.created_at.isoformat(),
    }
