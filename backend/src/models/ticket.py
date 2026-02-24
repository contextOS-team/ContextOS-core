"""Linear ticket and comment models mapping to linear_tickets and linear_comments tables."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class LinearTicket(BaseModel, table=True):
    """Linear ticket record mapping to public.linear_tickets table.

    Stores synced ticket data from Linear including metadata, state,
    assignee, labels, and the full raw GraphQL response.
    """

    __tablename__ = "linear_tickets"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    linear_id: str = Field(nullable=False)
    identifier: str = Field(nullable=False)
    title: str = Field(nullable=False)
    description: str | None = Field(default=None)
    status: str | None = Field(default=None)
    priority: int | None = Field(default=None)
    assignee_name: str | None = Field(default=None)
    team_name: str | None = Field(default=None)
    project_name: str | None = Field(default=None)
    labels: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String), nullable=True),
    )
    linear_created_at: datetime | None = Field(default=None)
    linear_updated_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )


class LinearComment(BaseModel, table=True):
    """Linear comment record mapping to public.linear_comments table.

    Stores synced comment data with FK reference to the parent ticket.
    """

    __tablename__ = "linear_comments"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    ticket_id: uuid.UUID = Field(foreign_key="linear_tickets.id", nullable=False)
    linear_id: str = Field(nullable=False)
    body: str = Field(nullable=False)
    author_name: str | None = Field(default=None)
    linear_created_at: datetime | None = Field(default=None)
    linear_updated_at: datetime | None = Field(default=None)
