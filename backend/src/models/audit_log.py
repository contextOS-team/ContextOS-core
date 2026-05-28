"""Audit log model for tracking data access."""

import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    """Records privacy-sensitive data access events."""

    __tablename__ = "audit_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    user_id: uuid.UUID | None = Field(default=None)
    action: str = Field(nullable=False)
    resource_type: str | None = Field(default=None)
    resource_id: uuid.UUID | None = Field(default=None)
    details: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "details",
            JSONB,
            nullable=True,
            server_default=sa_text("'{}'"),
        ),
    )
    ip_address: str | None = Field(
        default=None,
        sa_column=Column("ip_address", INET, nullable=True),
    )
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
