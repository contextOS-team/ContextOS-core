"""Correlation ID middleware for request tracing.

Generates a unique correlation ID per HTTP request (or reuses one from the
incoming X-Correlation-ID header), sets it in a context variable for
structured log binding, and returns it in the response header.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.observability.logging import correlation_id_var, get_logger

logger = get_logger(__name__)

_HEADER_NAME = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns and propagates a correlation ID per request.

    - Reads X-Correlation-ID from incoming request headers (or generates UUID4).
    - Sets correlation_id in contextvars for structured log binding.
    - Adds X-Correlation-ID to response headers.
    - Logs request start and completion with method, path, status, and duration.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Read or generate correlation ID
        correlation_id = request.headers.get(_HEADER_NAME) or str(uuid.uuid4())

        # Set in context var for structured logging
        token = correlation_id_var.set(correlation_id)

        start_time = time.monotonic()
        method = request.method
        path = request.url.path

        logger.info("request_started", method=method, path=path)

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start_time) * 1000, 1)
            logger.error(
                "request_failed",
                method=method,
                path=path,
                duration_ms=duration_ms,
            )
            raise
        finally:
            # Reset context var to prevent leaking across requests
            correlation_id_var.reset(token)

        duration_ms = round((time.monotonic() - start_time) * 1000, 1)
        logger.info(
            "request_completed",
            method=method,
            path=path,
            status=response.status_code,
            duration_ms=duration_ms,
        )

        # Add correlation ID to response header
        response.headers[_HEADER_NAME] = correlation_id

        return response
