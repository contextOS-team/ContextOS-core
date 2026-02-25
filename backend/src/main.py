"""FastAPI application entrypoint for ContextOS."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import Environment, get_settings
from src.middleware.correlation import CorrelationIdMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.observability.laminar import init_laminar
from src.observability.logging import configure_logging
from src.observability.sentry import SentryContextMiddleware, init_sentry
from src.routers.auth import router as auth_router
from src.routers.fathom import router as fathom_router
from src.routers.github import router as github_router
from src.routers.health import router as health_router
from src.routers.integrations import router as integrations_router
from src.routers.linear import router as linear_router
from src.routers.slack import router as slack_router
from src.routers.webhooks import router as webhooks_router
from src.routers.workspaces import router as workspaces_router

# Initialize Sentry BEFORE app creation (must init early to capture all errors)
settings = get_settings()
init_sentry(settings)

# Initialize Laminar for LLM observability (no-ops safely without API key)
init_laminar(settings)

# Configure structured logging
configure_logging(settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    yield
    # Shutdown: dispose the engine to close all connections
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

app.add_middleware(SentryContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(integrations_router)
app.include_router(linear_router)
app.include_router(slack_router)
app.include_router(fathom_router)
app.include_router(github_router)
app.include_router(workspaces_router)
app.include_router(webhooks_router)
