"""Telegram models.

- TelegramMessage: per-message row in public.telegram_messages (Phase 26 — UNCHANGED).
- TelegramChatWorkspace: chat→workspace mapping (Phase 40, PK chat_id, sticky).
- TelegramPairingCode: single-use ~15-min TTL pairing codes (Phase 40).
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, UniqueConstraint
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
    message_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    chat_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    chat_title: str | None = Field(default=None)
    chat_type: str | None = Field(default=None)
    from_user_id: int | None = Field(default=None, sa_column=Column(BigInteger))
    from_username: str | None = Field(default=None)
    from_first_name: str | None = Field(default=None)
    text: str = Field(nullable=False)
    reply_to_message_id: int | None = Field(default=None, sa_column=Column(BigInteger))
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


class TelegramChatWorkspace(SQLModel, table=True):
    """Sticky chat → workspace mapping (Phase 40).

    `chat_id` is the PRIMARY KEY: INSERT ... ON CONFLICT (chat_id) DO NOTHING
    enforces "first claim wins". Mapping is sticky -- regaining ownership
    requires removing the bot from the chat (handled by handle_my_chat_member
    soft-delete on left/kicked, then re-pair).
    """

    __tablename__ = "telegram_chat_workspace"

    chat_id: int = Field(sa_column=Column(BigInteger, primary_key=True))
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    chat_title: str | None = Field(default=None)
    chat_type: str | None = Field(default=None)
    paired_by: uuid.UUID | None = Field(default=None)
    paired_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    removed_at: datetime | None = Field(default=None)


class TelegramPairingCode(SQLModel, table=True):
    """Single-use ~15-min TTL pairing code (Phase 40).

    Codes are 16-char base64url strings (secrets.token_urlsafe(12)). Atomic
    redemption uses DELETE ... RETURNING. POST /api/telegram/pairing-code
    deletes any unexpired prior codes for the workspace before INSERTing
    a new one (one-active-code-per-workspace invariant -- Pitfall 5).
    """

    __tablename__ = "telegram_pairing_codes"

    code: str = Field(primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    created_by: uuid.UUID | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    expires_at: datetime = Field(nullable=False)
