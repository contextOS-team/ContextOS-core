"""Langfuse SDK integration for LLM observability.

Provides initialization and helpers for tracing LLM calls with full
input/output capture. When LANGFUSE_SECRET_KEY is not set, all functions
degrade gracefully to no-ops.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)

_langfuse_enabled = False


def init_langfuse(settings: Settings) -> None:
    """Initialize Langfuse by setting env vars that the SDK reads automatically."""
    global _langfuse_enabled

    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        logger.info("Langfuse disabled (no API keys)")
        return

    try:
        # Langfuse decorators read from env vars automatically
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

        # Import to verify installation
        from langfuse.decorators import langfuse_context  # noqa: F401

        _langfuse_enabled = True
        logger.info("Langfuse initialized successfully (host=%s)", settings.LANGFUSE_HOST)
    except Exception:
        logger.warning("Langfuse initialization failed", exc_info=True)


def update_langfuse_trace(
    *,
    name: str | None = None,
    input: object | None = None,
    output: object | None = None,
    metadata: dict | None = None,
    user_id: str | None = None,
) -> None:
    """Update the current Langfuse trace/observation with input, output, and metadata.

    No-op if Langfuse is not enabled.
    """
    if not _langfuse_enabled:
        return
    try:
        from langfuse.decorators import langfuse_context

        update = {}
        if name is not None:
            update["name"] = name
        if input is not None:
            update["input"] = input
        if output is not None:
            update["output"] = output
        if metadata is not None:
            update["metadata"] = metadata
        if user_id is not None:
            update["user_id"] = user_id
        if update:
            langfuse_context.update_current_trace(**update)
    except Exception:
        pass


def langfuse_observe(name: str) -> object:
    """Decorator that wraps a function with Langfuse's @observe.

    Falls back to a no-op decorator if Langfuse is not installed.
    """
    try:
        from langfuse.decorators import observe as lf_observe
        return lf_observe(name=name)
    except ImportError:
        def noop(func):
            return func
        return noop
