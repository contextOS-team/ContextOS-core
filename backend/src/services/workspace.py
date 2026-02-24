"""Workspace business logic."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.user import WorkspaceMember
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
