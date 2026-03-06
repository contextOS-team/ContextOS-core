"""Workspace CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.api_key import create_api_key, list_api_keys, revoke_api_key
from src.services.workspace import (
    get_workspace_by_id,
    list_workspace_members,
    update_workspace_name,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# -- Request/Response models --------------------------------------------------


class CreateApiKeyRequest(BaseModel):
    """Request body for creating an API key."""

    name: str


class UpdateWorkspaceRequest(BaseModel):
    """Request body for updating workspace settings."""

    name: str


# -- Existing endpoints -------------------------------------------------------


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


# -- Workspace update ---------------------------------------------------------


@router.patch("/current")
async def update_current_workspace(
    body: UpdateWorkspaceRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update the current workspace's name."""
    try:
        workspace = await update_workspace_name(
            session, user.workspace_id, body.name
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "slug": workspace.slug,
        "created_at": workspace.created_at.isoformat(),
    }


# -- Members -------------------------------------------------------------------


@router.get("/current/members")
async def get_workspace_members(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return team members for the current workspace with profile data."""
    members = await list_workspace_members(session, user.workspace_id)
    return {"members": members}


# -- API Keys ------------------------------------------------------------------


@router.post("/current/api-keys")
async def create_workspace_api_key(
    body: CreateApiKeyRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new API key for the current workspace.

    Returns the full key once. It cannot be retrieved again.
    """
    name = body.name.strip()
    if not name or len(name) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Key name must be 1-50 characters",
        )

    api_key, full_key = await create_api_key(
        session, user.workspace_id, user.user_id, name
    )

    return {
        "id": str(api_key.id),
        "name": api_key.name,
        "key": full_key,
        "key_prefix": api_key.key_prefix,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }


@router.get("/current/api-keys")
async def get_workspace_api_keys(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List all active API keys for the current workspace.

    Returns key metadata only (no full keys).
    """
    keys = await list_api_keys(session, user.workspace_id)

    return {
        "keys": [
            {
                "id": str(k.id),
                "name": k.name,
                "key_prefix": k.key_prefix,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
            for k in keys
        ]
    }


@router.delete("/current/api-keys/{key_id}")
async def delete_workspace_api_key(
    key_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Revoke (soft-delete) an API key."""
    result = await revoke_api_key(session, user.workspace_id, key_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or already revoked",
        )

    return {"status": "revoked"}
