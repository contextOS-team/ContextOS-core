"""SyncAdapter protocol and shared sync orchestration utilities.

Provides a common interface for all provider sync services and shared
helpers for sync state management, run correlation, and error handling.
"""

import contextvars
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.sync import SyncCursor

logger = logging.getLogger(__name__)

_sync_run_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "sync_run_id", default=""
)


@runtime_checkable
class SyncAdapter(Protocol):
    """Protocol defining the common sync interface for all providers.

    Every provider (Notion, Linear, GitHub, Slack) must implement these
    three methods for consistent sync orchestration.
    """

    provider: str

    async def full_sync(
        self, session: AsyncSession, workspace_id: uuid.UUID, **kwargs
    ) -> dict:
        """Run a full sync for the given workspace.

        Returns:
            Summary dict with provider-specific sync results.
        """
        ...

    async def handle_webhook(
        self, session: AsyncSession, workspace_id: uuid.UUID, payload: dict
    ) -> None:
        """Process a single webhook event for the given workspace."""
        ...

    async def reconcile(
        self, session: AsyncSession, workspace_id: uuid.UUID
    ) -> dict:
        """Reconcile local state with remote -- polling fallback.

        Catches missed webhook events by comparing local state with
        the provider API. Returns summary of changes found.
        """
        ...


def generate_sync_run_id() -> str:
    """Generate a unique sync run ID for log correlation."""
    return str(uuid.uuid4())


async def get_or_create_cursor(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    provider: str,
    resource_type: str = "default",
) -> SyncCursor:
    """Get existing sync cursor or create a new one.

    Uses SELECT then INSERT for safe concurrent access.
    """
    stmt = select(SyncCursor).where(
        SyncCursor.workspace_id == workspace_id,
        SyncCursor.provider == provider,
        SyncCursor.resource_type == resource_type,
    )
    result = await session.execute(stmt)
    cursor = result.scalar_one_or_none()

    if cursor is None:
        cursor = SyncCursor(
            workspace_id=workspace_id,
            provider=provider,
            resource_type=resource_type,
        )
        session.add(cursor)
        await session.flush()

    return cursor


async def update_cursor_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    provider: str,
    resource_type: str,
    *,
    sync_status: str,
    records_synced: int | None = None,
    cursor_value: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update sync cursor state.

    Sets last_sync_at when status is 'complete'.
    Clears error_message on non-error statuses.
    """
    cursor = await get_or_create_cursor(
        session, workspace_id, provider, resource_type
    )
    cursor.sync_status = sync_status

    if records_synced is not None:
        cursor.records_synced = records_synced
    if cursor_value is not None:
        cursor.cursor_value = cursor_value

    if sync_status == "complete":
        cursor.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
        cursor.error_message = None
    elif sync_status == "error":
        cursor.error_message = error_message
    else:
        cursor.error_message = None

    await session.flush()


async def emit_activity(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    event_type: str,
    metadata: dict | None = None,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Insert an activity event row. Fail-silent -- never breaks callers.

    Uses a savepoint so a failed INSERT does not poison the outer transaction.
    """
    try:
        async with session.begin_nested():
            await session.execute(
                text(
                    "INSERT INTO activity_events (workspace_id, actor_id, event_type, metadata)"
                    " VALUES (:workspace_id, :actor_id, :event_type, CAST(:metadata AS jsonb))"
                ),
                {
                    "workspace_id": workspace_id,
                    "actor_id": actor_id,
                    "event_type": event_type,
                    "metadata": json.dumps(metadata or {}),
                },
            )
    except Exception:
        logger.warning(
            "emit_activity failed: type=%s workspace=%s",
            event_type,
            workspace_id,
            exc_info=True,
        )


async def get_cursor_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    provider: str,
    resource_type: str = "default",
) -> dict:
    """Get current sync cursor status as a dict.

    Returns empty dict with idle status if no cursor exists.
    """
    stmt = select(SyncCursor).where(
        SyncCursor.workspace_id == workspace_id,
        SyncCursor.provider == provider,
        SyncCursor.resource_type == resource_type,
    )
    result = await session.execute(stmt)
    cursor = result.scalar_one_or_none()

    if cursor is None:
        return {
            "sync_status": "idle",
            "records_synced": 0,
            "last_sync_at": None,
            "error_message": None,
        }

    return {
        "sync_status": cursor.sync_status,
        "records_synced": cursor.records_synced,
        "last_sync_at": cursor.last_sync_at.isoformat() if cursor.last_sync_at else None,
        "error_message": cursor.error_message,
        "cursor_value": cursor.cursor_value,
    }


class SyncRunLogger:
    """Context manager that sets sync_run_id in log context.

    Usage:
        async with SyncRunLogger("notion", workspace_id) as srl:
            srl.info("Starting sync")
            ...
    """

    def __init__(self, provider: str, workspace_id: uuid.UUID) -> None:
        self.provider = provider
        self.workspace_id = str(workspace_id)
        self.run_id = generate_sync_run_id()
        self._logger = logging.getLogger(f"sync.{provider}")

    async def __aenter__(self) -> "SyncRunLogger":
        _sync_run_id_var.set(self.run_id)
        self.info("Sync run started")
        return self

    async def __aexit__(self, *args) -> None:
        self.info("Sync run ended")
        _sync_run_id_var.set("")

    def _extra(self) -> dict:
        return {
            "sync_run_id": self.run_id,
            "provider": self.provider,
            "workspace_id": self.workspace_id,
        }

    def info(self, msg: str, **kwargs) -> None:
        self._logger.info(msg, extra={**self._extra(), **kwargs})

    def warning(self, msg: str, **kwargs) -> None:
        self._logger.warning(msg, extra={**self._extra(), **kwargs})

    def error(self, msg: str, **kwargs) -> None:
        self._logger.error(msg, extra={**self._extra(), **kwargs})

    def exception(self, msg: str, **kwargs) -> None:
        self._logger.exception(msg, extra={**self._extra(), **kwargs})
