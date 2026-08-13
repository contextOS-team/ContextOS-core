"""FastAPI application entrypoint for ContextOS."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import Environment, get_settings
from src.middleware.correlation import CorrelationIdMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.security_headers import SecurityHeadersMiddleware
from src.observability.laminar import init_laminar
from src.observability.langfuse_client import init_langfuse
from src.observability.logging import configure_logging
from src.observability.sentry import SentryContextMiddleware, init_sentry
from src.routers.auth import router as auth_router
from src.routers.context import router as context_router
from src.routers.dashboard import router as dashboard_router
from src.routers.decision_context_api import router as decision_context_api_router
from src.routers.decisions import router as decisions_router
from src.routers.drifts import router as drifts_router
from src.routers.fathom import router as fathom_router
from src.routers.github import router as github_router
from src.routers.gitlab import router as gitlab_router
from src.routers.graph import router as graph_router
from src.routers.health import router as health_router
from src.routers.integrations import router as integrations_router
from src.routers.jira import router as jira_router
from src.routers.linear import router as linear_router
from src.routers.missed_decisions import router as missed_decisions_router
from src.routers.notion import router as notion_router
from src.routers.slack import router as slack_router
from src.routers.suggestions import router as suggestions_router
from src.routers.telegram import router as telegram_router
from src.routers.webhooks import router as webhooks_router
from src.routers.workspaces import router as workspaces_router

# Initialize settings and validate for production (fail fast if secrets missing)
settings = get_settings()
settings.validate_for_production()

# Initialize Sentry BEFORE app creation (must init early to capture all errors)
init_sentry(settings)

# Initialize LLM observability (no-ops safely without API keys)
init_laminar(settings)
init_langfuse(settings)

# Configure structured logging
configure_logging(settings.ENVIRONMENT)

logger = logging.getLogger(__name__)


async def _cancel_background_tasks(
    tasks: list[asyncio.Task[None]],
    *,
    timeout: float = 5.0,
) -> None:
    """Cancel background tasks without letting shutdown hang indefinitely."""
    if not tasks:
        return

    for task in tasks:
        task.cancel()

    done, pending = await asyncio.wait(tasks, timeout=timeout)

    for task in done:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(
                "Background task %s failed during shutdown",
                task.get_name(),
            )

    if pending:
        task_names = ", ".join(task.get_name() for task in pending)
        logger.warning(
            "Timed out waiting for %d background task(s) to stop: %s",
            len(pending),
            task_names,
        )


async def _reset_stale_sync_locks() -> None:
    """Reset any sync_status stuck at 'syncing' from a previous server crash."""
    from sqlalchemy import text

    from src.db import async_session

    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    UPDATE workspace_integrations
                    SET config = config || jsonb_build_object(
                        'sync_status', 'error',
                        'sync_started_at', null
                    )
                    WHERE config->>'sync_status' = 'syncing'
                """)
            )
            await session.execute(
                text("""
                    UPDATE sync_cursors
                    SET sync_status = 'error'
                    WHERE sync_status = 'syncing'
                """)
            )
            await session.commit()
            if result.rowcount:
                logger.info("Reset %d stale sync lock(s) to error", result.rowcount)
    except Exception:
        logger.exception("Failed to reset stale sync locks")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown."""
    from src.services.code_index_worker import run_code_index_worker
    from src.services.embedding_worker import run_embedding_worker
    from src.services.gitlab_sync_worker import run_gitlab_sync_worker
    from src.services.graph_scheduler import (
        backfill_missing_workspaces,
        run_community_rebuild_loop,
    )
    from src.services.sync_scheduler import run_polling_fallback

    # Startup: clear any stale sync locks left from previous crashes
    await _reset_stale_sync_locks()

    # Startup: launch background workers with auto-restart on crash
    async def _supervised(name: str, coro_fn: Callable[[], Awaitable[None]]) -> None:
        """Run a worker coroutine, restarting it if it crashes."""
        while True:
            try:
                await coro_fn()
                logger.warning("Worker %s exited normally, restarting in 5s", name)
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Worker %s crashed, restarting in 5s", name)
                await asyncio.sleep(5)

    async def _run_startup_task(
        name: str,
        coro_fn: Callable[[], Awaitable[None]],
    ) -> None:
        """Run a startup-only task once and log failures without restarting."""
        try:
            await coro_fn()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Startup task %s failed", name)

    embedding_task = asyncio.create_task(
        _supervised("embedding_worker", run_embedding_worker),
        name="embedding_worker",
    )
    polling_task = asyncio.create_task(
        _supervised("polling_fallback", run_polling_fallback),
        name="polling_fallback",
    )
    code_index_task = asyncio.create_task(
        _supervised("code_index_worker", run_code_index_worker),
        name="code_index_worker",
    )
    gitlab_sync_task = asyncio.create_task(
        _supervised("gitlab_sync_worker", run_gitlab_sync_worker),
        name="gitlab_sync_worker",
    )
    community_rebuild_task = asyncio.create_task(
        _supervised("community_rebuild", run_community_rebuild_loop),
        name="community_rebuild",
    )
    # On-startup backfill — runs once, doesn't block startup.
    community_backfill_task = asyncio.create_task(
        _run_startup_task("community_backfill", backfill_missing_workspaces),
        name="community_backfill",
    )

    logger.info(
        "Background workers started: embedding_worker, polling_fallback, "
        "code_index_worker, gitlab_sync_worker, community_rebuild, "
        "community_backfill"
    )

    yield

    # Shutdown: cancel background workers, but do not let reloads hang forever.
    await _cancel_background_tasks([
        embedding_task,
        polling_task,
        code_index_task,
        gitlab_sync_task,
        community_rebuild_task,
        community_backfill_task,
    ])

    logger.info("Background workers stopped")

    # Dispose the engine to close all connections
    from src.db import engine

    await engine.dispose()


app = FastAPI(
    title="ContextOS",
    version="0.1.0",
    description="AI-powered context synthesis engine for dev tickets",
    lifespan=lifespan,
    # OpenAPI docs enabled in dev, disabled in prod
    docs_url="/docs" if settings.ENVIRONMENT != Environment.PROD else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != Environment.PROD else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != Environment.PROD else None,
)

# Middleware stack (order matters -- bottom = first executed on request):
# 1. RateLimitMiddleware (first: reject abusive requests early)
# 2. CorrelationIdMiddleware (assign correlation ID for all subsequent logging)
# 3. CORSMiddleware (handle CORS headers)
# 4. SentryContextMiddleware (tag Sentry scope with user/workspace context)
# 5. SecurityHeadersMiddleware (outermost: add security headers to all responses)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(SentryContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Correlation-ID"],
)

app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(integrations_router)
app.include_router(linear_router)
app.include_router(slack_router)
app.include_router(suggestions_router)
app.include_router(missed_decisions_router)
app.include_router(decisions_router)
app.include_router(drifts_router)
app.include_router(decision_context_api_router)
app.include_router(fathom_router)
app.include_router(github_router)
app.include_router(gitlab_router)
app.include_router(notion_router)
app.include_router(telegram_router)
app.include_router(jira_router)
app.include_router(dashboard_router)
app.include_router(context_router)
app.include_router(graph_router)
app.include_router(workspaces_router)
app.include_router(webhooks_router)
