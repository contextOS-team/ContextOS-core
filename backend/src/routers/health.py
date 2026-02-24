"""Health check router."""

from fastapi import APIRouter
from sqlalchemy import text

from src.db import engine

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return application health status including database connectivity.

    This endpoint does NOT require authentication.
    """
    db_status = "disconnected"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {"status": "ok", "db": db_status}
