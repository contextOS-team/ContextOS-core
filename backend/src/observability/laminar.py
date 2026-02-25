"""Laminar SDK integration for LLM observability.

Provides initialization, the @observe decorator for tracing LLM calls,
and a metadata helper for tagging traces with workspace and ticket context.
When LAMINAR_API_KEY is not set, all functions degrade gracefully to no-ops.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lmnr import Laminar, observe  # noqa: F401 -- re-exported for downstream use

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)


def init_laminar(settings: Settings) -> None:
    """Initialize the Laminar SDK for LLM call tracing.

    Safe to call in any environment:
    - If ``settings.LAMINAR_API_KEY`` is empty the call is a no-op and a log
      message indicates Laminar is disabled.
    - If initialization fails for any reason the exception is logged as a
      warning and the application continues normally.

    Args:
        settings: Application settings containing LAMINAR_API_KEY.
    """
    if not settings.LAMINAR_API_KEY:
        logger.info("Laminar disabled (no API key)")
        return

    try:
        Laminar.initialize(project_api_key=settings.LAMINAR_API_KEY)
        logger.info("Laminar initialized successfully")
    except Exception:
        logger.warning("Laminar initialization failed", exc_info=True)


def set_laminar_metadata(
    workspace_id: str | None = None,
    ticket_identifier: str | None = None,
) -> None:
    """Tag the current Laminar trace span with workspace and ticket context.

    Uses ``Laminar.set_span_attributes`` to attach metadata visible in the
    Laminar dashboard. If Laminar is not initialized (e.g. no API key), this
    is a silent no-op.

    Args:
        workspace_id: UUID string of the workspace for this call.
        ticket_identifier: Human-readable ticket reference (e.g. ``ENG-42``).
    """
    try:
        attributes: dict[str, str] = {}
        if workspace_id is not None:
            attributes["workspace_id"] = str(workspace_id)
        if ticket_identifier is not None:
            attributes["ticket_identifier"] = ticket_identifier
        if attributes:
            Laminar.set_span_attributes(attributes)
    except Exception:
        # Laminar not initialized or other issue -- silently ignore.
        pass
