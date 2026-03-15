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
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

        from langfuse import observe  # noqa: F401

        _langfuse_enabled = True
        logger.info("Langfuse initialized successfully (host=%s)", settings.LANGFUSE_HOST)
    except Exception:
        logger.warning("Langfuse initialization failed", exc_info=True)


def update_generation(
    *,
    model: str | None = None,
    usage: dict | None = None,
    output: object | None = None,
    metadata: dict | None = None,
) -> None:
    """Update the current Langfuse generation span with model, usage, and output.

    Must be called inside a function decorated with @langfuse_observe(as_type="generation").
    No-op if Langfuse is not enabled.
    """
    if not _langfuse_enabled:
        return
    try:
        from langfuse import get_client

        client = get_client()
        update = {}
        if model is not None:
            update["model"] = model
        if usage is not None:
            update["usage"] = usage
        if output is not None:
            update["output"] = output
        if metadata is not None:
            update["metadata"] = metadata
        if update:
            client.update_current_generation(**update)
    except Exception:
        pass


def langfuse_observe(name: str, as_type: str | None = None) -> object:
    """Decorator that wraps a function with Langfuse's @observe.

    Args:
        name: Name for the trace/span.
        as_type: Observation type - "generation" for LLM calls, "embedding" for embeddings.
    """
    try:
        from langfuse import observe as lf_observe
        kwargs = {"name": name}
        if as_type is not None:
            kwargs["as_type"] = as_type
        return lf_observe(**kwargs)
    except ImportError:
        def noop(func):
            return func
        return noop
