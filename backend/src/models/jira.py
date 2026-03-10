"""Jira issue and comment models mapping to jira_issues and jira_comments tables."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class JiraIssue(BaseModel, table=True):
    """Jira issue record mapping to public.jira_issues table.

    Stores synced issue data from Jira including metadata, status,
    assignee, labels, and the full raw API response.
    """

    __tablename__ = "jira_issues"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    jira_id: str = Field(nullable=False)
    jira_key: str = Field(nullable=False)
    summary: str = Field(nullable=False)
    description: str | None = Field(default=None)
    status: str | None = Field(default=None)
    priority: str | None = Field(default=None)
    issue_type: str | None = Field(default=None)
    assignee_name: str | None = Field(default=None)
    reporter_name: str | None = Field(default=None)
    project_key: str | None = Field(default=None)
    project_name: str | None = Field(default=None)
    labels: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String), nullable=True),
    )
    jira_created_at: datetime | None = Field(default=None)
    jira_updated_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )


class JiraComment(BaseModel, table=True):
    """Jira comment record mapping to public.jira_comments table.

    Stores synced comment data with FK reference to the parent issue.
    """

    __tablename__ = "jira_comments"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    issue_id: uuid.UUID = Field(foreign_key="jira_issues.id", nullable=False)
    jira_id: str = Field(nullable=False)
    author_name: str | None = Field(default=None)
    body: str | None = Field(default=None)
    jira_created_at: datetime | None = Field(default=None)
    jira_updated_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )
