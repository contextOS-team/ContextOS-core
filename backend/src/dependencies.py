"""FastAPI dependency injection for authentication and workspace scoping."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.auth import JWTError, decode_supabase_jwt
from src.db import get_session
from src.models.user import Profile, WorkspaceMember

security = HTTPBearer()


class UserContext(BaseModel):
    """Authenticated user context injected into route handlers."""

    user_id: UUID
    email: str
    workspace_id: UUID


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> UserContext:
    """Decode JWT, look up user profile and workspace membership.

    Returns UserContext with user_id, email, workspace_id.
    Raises 401 if token is invalid or user not found.
    """
    try:
        payload = decode_supabase_jwt(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Look up the user's workspace membership
    stmt = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == payload.sub,
        WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return UserContext(
        user_id=payload.sub,
        email=payload.email or "",
        workspace_id=membership,
    )


async def get_current_workspace(
    user: UserContext = Depends(get_current_user),
) -> UUID:
    """Extract just the workspace_id for workspace-scoped queries."""
    return user.workspace_id
