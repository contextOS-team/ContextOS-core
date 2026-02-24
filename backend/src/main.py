"""FastAPI application entrypoint for ContextOS."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import Environment, get_settings
from src.routers.auth import router as auth_router
from src.routers.fathom import router as fathom_router
from src.routers.health import router as health_router
from src.routers.integrations import router as integrations_router
from src.routers.linear import router as linear_router
from src.routers.slack import router as slack_router
from src.routers.webhooks import router as webhooks_router
from src.routers.workspaces import router as workspaces_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    yield
    # Shutdown: dispose the engine to close all connections
    from src.db import engine

    await engine.dispose()


settings = get_settings()

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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(integrations_router)
app.include_router(linear_router)
app.include_router(slack_router)
app.include_router(fathom_router)
app.include_router(workspaces_router)
app.include_router(webhooks_router)
