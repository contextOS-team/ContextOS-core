"""Slack message model mapping to public.slack_messages table."""

import uuid
from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class SlackMessage(SQLModel, table=True):
    """Slack message record mapping to public.slack_messages table.

    Maps all columns from the DB schema. Does NOT inherit from BaseModel
    because the DB table has no updated_at column.

    The unique constraint (workspace_id, channel_id, slack_ts) supports
    upsert-on-conflict for idempotent message ingestion.
    """

    __tablename__ = "slack_messages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "channel_id", "slack_ts", name="uq_slack_msg"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    slack_ts: str = Field(nullable=False)
    channel_id: str = Field(nullable=False)
    channel_name: str | None = Field(default=None)
    user_id: str | None = Field(default=None)  # Slack user ID, not our user_id
    user_name: str | None = Field(default=None)  # display name at ingestion time
    text: str = Field(nullable=False)
    thread_ts: str | None = Field(default=None)
    parent_ts: str | None = Field(default=None)
    is_thread_reply: bool = Field(default=False)
    reactions: dict = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=sa_text("'[]'")),
    )
    slack_created_at: datetime | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=sa_text("'{}'")),
    )
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
