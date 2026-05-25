"""Suggestion model for workspace-scoped review guidance."""

import uuid
from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class Suggestion(BaseModel, table=True):
    """Reusable suggestion contract with durable lifecycle state."""

    __tablename__ = "suggestions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "fingerprint",
            name="suggestions_workspace_fingerprint_key",
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    type: str = Field(nullable=False)
    status: str = Field(default="open", nullable=False)
    priority: str = Field(default="medium", nullable=False)
    fingerprint: str = Field(nullable=False)
    entity_type: str | None = Field(default=None)
    entity_id: uuid.UUID | None = Field(default=None)
    title: str = Field(nullable=False)
    body: str = Field(nullable=False)
    primary_action: str | None = Field(default=None)
    action_href: str | None = Field(default=None)
    evidence: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "evidence",
            JSONB,
            nullable=False,
            server_default=sa_text("'{}'"),
        ),
    )
    details: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "details",
            JSONB,
            nullable=False,
            server_default=sa_text("'{}'"),
        ),
    )
    provenance: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "provenance",
            JSONB,
            nullable=False,
            server_default=sa_text("'{}'"),
        ),
    )
    snoozed_until: datetime | None = Field(default=None)
    dismissed_at: datetime | None = Field(default=None)
    resolved_at: datetime | None = Field(default=None)
    reopened_at: datetime | None = Field(default=None)
    last_seen_at: datetime | None = Field(default=None)
    created_by_user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="profiles.id",
    )
    updated_by_user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="profiles.id",
    )
