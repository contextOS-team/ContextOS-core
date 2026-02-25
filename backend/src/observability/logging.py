"""Structured JSON logging with correlation ID support.

Uses structlog for structured logging with automatic correlation ID binding
from the CorrelationIdMiddleware context variable.

Provides:
- configure_logging(): Set up structlog processors based on environment
- get_logger(): Return a bound structlog logger with automatic context
- correlation_id_var: ContextVar for correlation ID propagation
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.config import Environment

# Context variable for correlation ID propagation across async boundaries
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def _add_correlation_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Structlog processor that binds correlation_id from context var."""
    cid = correlation_id_var.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging(environment: Environment) -> None:
    """Configure structlog with environment-appropriate rendering.

    - Production: JSON renderer for machine-parseable log aggregation.
    - Dev/Staging: Console renderer with colors for human readability.

    Args:
        environment: Application environment enum value.
    """
    is_production = environment.value == "prod"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger with automatic correlation_id binding.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)
