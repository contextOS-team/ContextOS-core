"""Context page model mapping to public.context_pages table."""

import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class ContextPage(BaseModel, table=True):
    """AI-generated context page for a Linear ticket.

    Synthesizes information from tickets, PRs, Slack messages, and meetings
    into a structured context document for engineers.

    Inherits BaseModel (has updated_at via moddatetime trigger).
    """

    __tablename__ = "context_pages"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    ticket_id: uuid.UUID | None = Field(
        default=None, foreign_key="linear_tickets.id"
    )
    jira_issue_id: uuid.UUID | None = Field(
        default=None, foreign_key="jira_issues.id"
    )
    ticket_identifier: str | None = Field(default=None)
    title: str = Field(nullable=False)
    content: str = Field(nullable=False)
    summary: str | None = Field(default=None)
    status: str = Field(default="draft", nullable=False)
    sources: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=sa_text("'[]'")),
    )
    generated_at: datetime | None = Field(default=None)
    generation_model: str | None = Field(default=None)
    generation_tokens_used: int | None = Field(default=None)
