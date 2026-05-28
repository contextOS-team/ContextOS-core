"""Audit logging helper for tracking data access events."""

import logging
from inspect import isawaitable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_audit_event(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    action: str,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Record an audit event. Non-blocking — logs errors but never raises."""
    try:
        savepoint = session.begin_nested()
        if isawaitable(savepoint):
            savepoint = await savepoint
        async with savepoint:
            entry = AuditLog(
                workspace_id=workspace_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                ip_address=ip_address,
            )
            session.add(entry)
            await session.flush()
    except Exception:
        logger.debug("Failed to write audit log entry", exc_info=True)
