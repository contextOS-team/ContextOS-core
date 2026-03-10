"""Telegram message model mapping to public.telegram_messages table."""

import uuid
from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class TelegramMessage(SQLModel, table=True):
    """Telegram message record mapping to public.telegram_messages table.

    Maps all columns from the DB schema. Does NOT inherit from BaseModel
    because the DB table has no updated_at column (same pattern as SlackMessage).

    The unique constraint (workspace_id, chat_id, message_id) supports
    upsert-on-conflict for idempotent message ingestion and edit handling.
    """

    __tablename__ = "telegram_messages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "chat_id", "message_id", name="uq_tg_msg"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    message_id: int = Field(nullable=False)
    chat_id: int = Field(nullable=False)
    chat_title: str | None = Field(default=None)
    chat_type: str | None = Field(default=None)
    from_user_id: int | None = Field(default=None)
    from_username: str | None = Field(default=None)
    from_first_name: str | None = Field(default=None)
    text: str = Field(nullable=False)
    reply_to_message_id: int | None = Field(default=None)
    is_reply: bool = Field(default=False)
    telegram_date: datetime | None = Field(default=None)
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
