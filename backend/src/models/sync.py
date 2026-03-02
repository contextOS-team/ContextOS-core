"""Sync cursor model for tracking sync state per provider."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class SyncCursor(SQLModel, table=True):
    """Tracks sync state per workspace/provider/resource_type.

    Replaces ad-hoc JSONB in workspace_integrations.config with a
    dedicated table for reliable sync state management.
    """

    __tablename__ = "sync_cursors"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    provider: str = Field(nullable=False)
    resource_type: str = Field(default="default", nullable=False)
    cursor_type: str = Field(default="pagination", nullable=False)
    cursor_value: str | None = Field(default=None)
    records_synced: int = Field(default=0, nullable=False)
    sync_status: str = Field(default="idle", nullable=False)
    last_sync_at: datetime | None = Field(default=None)
    error_message: str | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)
