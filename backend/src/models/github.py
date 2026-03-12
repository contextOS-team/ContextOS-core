"""GitHub pull request and review models mapping to github_pull_requests and github_reviews tables."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class GithubPullRequest(BaseModel, table=True):
    """GitHub pull request record mapping to public.github_pull_requests table.

    Stores synced PR data from GitHub including metadata, state,
    author, branches, reviewers, and the full raw API response.
    """

    __tablename__ = "github_pull_requests"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    linear_ticket_id: uuid.UUID | None = Field(
        default=None, foreign_key="linear_tickets.id"
    )
    jira_issue_id: uuid.UUID | None = Field(
        default=None, foreign_key="jira_issues.id"
    )
    github_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    repo_full_name: str = Field(nullable=False)
    number: int = Field(nullable=False)
    title: str = Field(nullable=False)
    description: str | None = Field(default=None)
    state: str = Field(nullable=False)
    author: str = Field(nullable=False)
    branch_name: str = Field(nullable=False)
    base_branch: str = Field(nullable=False)
    reviewers: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String), nullable=True),
    )
    is_draft: bool = Field(default=False)
    github_created_at: datetime | None = Field(default=None)
    github_updated_at: datetime | None = Field(default=None)
    github_merged_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )


class GithubReview(BaseModel, table=True):
    """GitHub review record mapping to public.github_reviews table.

    Stores synced review data with FK reference to the parent pull request.
    """

    __tablename__ = "github_reviews"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    pull_request_id: uuid.UUID = Field(
        foreign_key="github_pull_requests.id", nullable=False
    )
    github_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    author: str = Field(nullable=False)
    state: str = Field(nullable=False)
    body: str | None = Field(default=None)
    file_path: str | None = Field(default=None)
    line_range: str | None = Field(default=None)
    github_submitted_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )
