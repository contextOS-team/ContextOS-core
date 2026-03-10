"""Integration models mapping to oauth_tokens, workspace_integrations, and webhook_deliveries."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from src.models.base import BaseModel, TimestampMixin


class Provider(str, Enum):
    """Integration provider identifiers.

    Inherits from str so Provider.LINEAR == "linear" is True,
    avoiding any DB migration or API contract changes.
    """

    LINEAR = "linear"
    GITHUB = "github"
    SLACK = "slack"
    FATHOM = "fathom"
    NOTION = "notion"
    TELEGRAM = "telegram"


class OAuthToken(BaseModel, table=True):
    """OAuth token record mapping to public.oauth_tokens table.

    Token values (access_token, refresh_token) store Vault secret name
    references, NOT actual token values. The real tokens are encrypted
    in Supabase Vault.
    """

    __tablename__ = "oauth_tokens"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    user_id: uuid.UUID = Field(foreign_key="profiles.id", nullable=False)
    provider: str = Field(nullable=False)
    access_token: str = Field(nullable=False)
    refresh_token: str | None = Field(default=None)
    token_expires_at: datetime | None = Field(default=None)
    scopes: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String), nullable=True),
    )
    metadata_: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False, server_default=text("'{}'")),
    )


class WorkspaceIntegration(BaseModel, table=True):
    """Workspace integration status mapping to public.workspace_integrations table."""

    __tablename__ = "workspace_integrations"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    provider: str = Field(nullable=False)
    external_id: str | None = Field(default=None)
    status: str = Field(default="disconnected", nullable=False)
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )
    connected_at: datetime | None = Field(default=None)


class WebhookDelivery(SQLModel, table=True):
    """Webhook delivery record for idempotency tracking.

    Maps to public.webhook_deliveries table.
    """

    __tablename__ = "webhook_deliveries"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    delivery_id: str = Field(nullable=False, unique=True)
    provider: str = Field(nullable=False)
    processed_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
