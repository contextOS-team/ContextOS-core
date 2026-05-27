"""Notion page model mapping to public.notion_pages table."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class NotionPage(SQLModel, table=True):
    """Notion page record mapping to public.notion_pages table.

    Maps all columns from the existing DB schema in 00001_initial_schema.sql.
    Field names match DB column names exactly.

    The unique constraint (workspace_id, notion_id) supports
    upsert-on-conflict for idempotent page ingestion.
    """

    __tablename__ = "notion_pages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "notion_id", name="uq_notion_page"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    notion_id: str = Field(nullable=False)
    title: str = Field(nullable=False)
    content: str | None = Field(default=None)
    page_type: str | None = Field(default=None)  # 'page', 'database_entry', 'wiki'
    parent_id: str | None = Field(default=None)
    url: str | None = Field(default=None)
    last_edited_by: str | None = Field(default=None)
    notion_created_at: datetime | None = Field(default=None)
    notion_updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default=sa_text("'{}'")),
    )
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    updated_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
