"""Workspace business logic."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.user import Profile, WorkspaceMember
from src.models.workspace import Workspace


async def get_workspace_by_id(session: AsyncSession, workspace_id: UUID) -> Workspace | None:
    """Fetch a workspace by its ID.

    Returns None if the workspace does not exist or has been soft-deleted.
    """
    stmt = select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_workspace(session: AsyncSession, user_id: UUID) -> Workspace | None:
    """Get the workspace for a user via workspace_members join.

    Returns the first active workspace for the given user.
    """
    stmt = (
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
            Workspace.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_workspace_name(
    session: AsyncSession,
    workspace_id: UUID,
    name: str,
) -> Workspace:
    """Update a workspace's name.

    Validates name is 1-50 characters.
    Raises ValueError if validation fails.
    """
    stripped = name.strip()
    if not stripped or len(stripped) > 50:
        raise ValueError("Workspace name must be 1-50 characters")

    stmt = select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise ValueError("Workspace not found")

    workspace.name = stripped
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)

    return workspace


async def list_workspace_members(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[dict]:
    """List workspace members with their profile information.

    Joins workspace_members with profiles to return user details.
    Filters out soft-deleted members.
    """
    stmt = (
        select(
            WorkspaceMember.user_id,
            Profile.full_name,
            Profile.email,
            WorkspaceMember.role,
            WorkspaceMember.created_at,
        )
        .join(Profile, Profile.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "user_id": str(row.user_id),
            "full_name": row.full_name,
            "email": row.email,
            "role": row.role,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
