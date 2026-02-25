"""Sentry SDK initialization and context helpers for FastAPI.

Provides:
- init_sentry(): Initialize Sentry SDK with FastAPI + SQLAlchemy integrations
- set_sentry_context(): Tag requests with workspace_id, user_id, endpoint
- SentryContextMiddleware: Auto-tag authenticated requests with Sentry context
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)

# Application version -- matches pyproject.toml
_APP_VERSION = "0.1.0"


def init_sentry(settings: Settings) -> None:
    """Initialize Sentry SDK for error tracking and performance monitoring.

    No-op if SENTRY_DSN is empty (safe for local dev without Sentry).

    Args:
        settings: Application settings containing SENTRY_DSN and ENVIRONMENT.
    """
    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured -- error tracking disabled")
        return

    is_production = settings.ENVIRONMENT.value == "prod"

    # Build integration list -- SqlalchemyIntegration imported lazily
    # because it requires sqlalchemy to be installed at import time
    integrations: list = [FastApiIntegration()]
    try:
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        integrations.append(SqlalchemyIntegration())
    except Exception:
        logger.debug("SQLAlchemy integration not available for Sentry")

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=integrations,
        traces_sample_rate=0.2 if is_production else 1.0,
        profiles_sample_rate=0.1 if is_production else 0.0,
        environment=settings.ENVIRONMENT.value,
        release=f"contextos-backend@{_APP_VERSION}",
        send_default_pii=False,
    )
    logger.info(
        "Sentry initialized (env=%s, traces=%.1f)",
        settings.ENVIRONMENT.value,
        0.2 if is_production else 1.0,
    )


def set_sentry_context(
    workspace_id: str | None = None,
    user_id: str | None = None,
    endpoint: str | None = None,
) -> None:
    """Set Sentry tags and user context for the current scope.

    Safe to call even if Sentry is not initialized (tags are silently dropped).

    Args:
        workspace_id: Current workspace UUID string.
        user_id: Current user UUID string.
        endpoint: Request endpoint path.
    """
    if workspace_id:
        sentry_sdk.set_tag("workspace_id", workspace_id)
    if user_id:
        sentry_sdk.set_tag("user_id", user_id)
        sentry_sdk.set_user({"id": user_id})
    if endpoint:
        sentry_sdk.set_tag("endpoint", endpoint)


class SentryContextMiddleware(BaseHTTPMiddleware):
    """Middleware that auto-tags Sentry scope with user/workspace context.

    Extracts user information from the Authorization header JWT on each request.
    Does NOT block on auth failures -- just tags what is available.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        endpoint = request.url.path

        # Try to extract user context from auth header (best-effort)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from src.auth import decode_supabase_jwt

                payload = decode_supabase_jwt(token)
                set_sentry_context(
                    user_id=str(payload.sub),
                    endpoint=endpoint,
                )
            except Exception:
                # Auth failed -- still tag the endpoint
                set_sentry_context(endpoint=endpoint)
        else:
            set_sentry_context(endpoint=endpoint)

        return await call_next(request)
