"""API key model mapping to public.api_keys table."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel


class ApiKey(SQLModel, table=True):
    """API key for workspace-scoped programmatic access.

    The full key is only available at creation time. Only the prefix
    and SHA-256 hash are stored in the database.
    """

    __tablename__ = "api_keys"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    created_by: uuid.UUID = Field(nullable=False)
    name: str = Field(nullable=False)
    key_prefix: str = Field(nullable=False)
    key_hash: str = Field(nullable=False)
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("now()")
        ),
    )
