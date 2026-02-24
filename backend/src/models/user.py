"""User-related models mapping to public.profiles and public.workspace_members."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from src.models.base import TimestampMixin


class Profile(TimestampMixin, table=True):
    """User profile mapping to public.profiles table.

    The id is the Supabase Auth user ID (UUID), used as the primary key.
    """

    __tablename__ = "profiles"

    id: uuid.UUID = Field(primary_key=True)
    email: str = Field(nullable=False)
    full_name: str | None = Field(default=None)
    avatar_url: str | None = Field(default=None)


class WorkspaceMember(SQLModel, table=True):
    """Workspace membership mapping to public.workspace_members table."""

    __tablename__ = "workspace_members"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="profiles.id", primary_key=True)
    role: str = Field(default="member", nullable=False)
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
