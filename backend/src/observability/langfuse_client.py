"""Langfuse SDK integration for LLM observability.

Provides initialization and the @observe decorator for tracing LLM calls.
When LANGFUSE_SECRET_KEY is not set, all functions degrade gracefully to no-ops.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)

_langfuse_enabled = False


def init_langfuse(settings: Settings) -> None:
    """Initialize the Langfuse SDK for LLM call tracing.

    Safe to call in any environment:
    - If keys are empty the call is a no-op.
    - If initialization fails the exception is logged and the app continues.
    """
    global _langfuse_enabled

    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        logger.info("Langfuse disabled (no API keys)")
        return

    try:
        from langfuse import Langfuse

        # Initialize the singleton -- the decorators will pick it up automatically
        Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )
        _langfuse_enabled = True
        logger.info("Langfuse initialized successfully (host=%s)", settings.LANGFUSE_HOST)
    except Exception:
        logger.warning("Langfuse initialization failed", exc_info=True)


def langfuse_observe(name: str) -> Callable:
    """Decorator that wraps a function with Langfuse's @observe when available.

    Falls back to a no-op decorator if Langfuse is not installed or not enabled.
    """
    def decorator(func: Callable) -> Callable:
        try:
            from langfuse.decorators import observe as lf_observe

            return lf_observe(name=name)(func)
        except ImportError:
            return func
    return decorator
