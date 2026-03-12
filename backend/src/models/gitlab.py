"""GitLab merge request and review models mapping to gitlab_merge_requests and gitlab_reviews tables."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class GitlabMergeRequest(BaseModel, table=True):
    """GitLab merge request record mapping to public.gitlab_merge_requests table.

    Stores synced MR data from GitLab including metadata, state,
    author, branches, reviewers, and the full raw API response.
    """

    __tablename__ = "gitlab_merge_requests"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    linear_ticket_id: uuid.UUID | None = Field(
        default=None, foreign_key="linear_tickets.id"
    )
    gitlab_id: int = Field(nullable=False)
    project_id: int = Field(nullable=False)
    project_path: str = Field(nullable=False)
    iid: int = Field(nullable=False)
    title: str = Field(nullable=False)
    description: str | None = Field(default=None)
    state: str = Field(nullable=False)
    author: str = Field(nullable=False)
    source_branch: str = Field(nullable=False)
    target_branch: str = Field(nullable=False)
    reviewers: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String), nullable=True),
    )
    is_draft: bool = Field(default=False)
    gitlab_created_at: datetime | None = Field(default=None)
    gitlab_updated_at: datetime | None = Field(default=None)
    gitlab_merged_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )


class GitlabReview(BaseModel, table=True):
    """GitLab review record mapping to public.gitlab_reviews table.

    Stores synced review/note data with FK reference to the parent merge request.
    """

    __tablename__ = "gitlab_reviews"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    merge_request_id: uuid.UUID = Field(
        foreign_key="gitlab_merge_requests.id", nullable=False
    )
    gitlab_id: int = Field(nullable=False)
    author: str = Field(nullable=False)
    state: str = Field(nullable=False)
    body: str | None = Field(default=None)
    file_path: str | None = Field(default=None)
    line_range: str | None = Field(default=None)
    gitlab_submitted_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )
