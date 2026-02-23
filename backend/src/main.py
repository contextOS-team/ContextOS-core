"""FastAPI application entry point for ContextOS backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.config import Environment, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle application startup and shutdown lifecycle events."""
    settings = get_settings()

    # Initialize Sentry for error tracking
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT.value,
            traces_sample_rate=1.0 if settings.ENVIRONMENT == Environment.DEV else 0.1,
        )

    # Initialize Laminar for observability
    if settings.LAMINAR_API_KEY:
        try:
            from lmnr import Laminar

            Laminar.initialize(project_api_key=settings.LAMINAR_API_KEY)
        except ImportError:
            pass  # laminai not installed

    yield

    # Shutdown: clean up resources if needed


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ContextOS Backend",
        description="AI-powered context synthesis engine for dev tickets",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    origins: list[str] = []
    if settings.ENVIRONMENT == Environment.DEV:
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    return app


app = create_app()
