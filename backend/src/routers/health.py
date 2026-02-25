"""Health check router.

Provides two endpoints:
- GET /api/health: Lightweight check for load balancers (DB connectivity only).
- GET /api/health/ready: Deep readiness probe checking DB, Vault, and external
  API reachability for deployment validation.

Neither endpoint requires authentication.
"""

import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from src.db import async_session, engine
from src.services.vault import check_vault_health

try:
    from src.observability.logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

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


async def _check_db() -> dict:
    """Check database connectivity via SELECT 1."""
    start = time.monotonic()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = round((time.monotonic() - start) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception:
        latency = round((time.monotonic() - start) * 1000)
        return {"status": "unreachable", "latency_ms": latency}


async def _check_vault() -> dict:
    """Check Vault connectivity via store/read/delete probe."""
    start = time.monotonic()
    try:
        async with async_session() as session:
            healthy = await check_vault_health(session)
        latency = round((time.monotonic() - start) * 1000)
        return {"status": "ok" if healthy else "degraded", "latency_ms": latency}
    except Exception:
        latency = round((time.monotonic() - start) * 1000)
        return {"status": "unreachable", "latency_ms": latency}


async def _check_external_api(url: str, timeout_seconds: float = 3.0) -> dict:
    """Check external API reachability with a HEAD request.

    Falls back to GET if HEAD returns 405 Method Not Allowed.

    Args:
        url: URL to check reachability against.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Dict with status ("ok", "degraded", "unreachable") and latency_ms.
    """
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.head(url)
            # Some APIs don't support HEAD -- try GET as fallback
            if response.status_code == 405:
                response = await client.get(url)
        latency = round((time.monotonic() - start) * 1000)
        # Any 2xx/3xx/4xx means the API is reachable (even 401/403)
        if response.status_code < 500:
            return {"status": "ok", "latency_ms": latency}
        return {"status": "degraded", "latency_ms": latency}
    except httpx.TimeoutException:
        latency = round((time.monotonic() - start) * 1000)
        return {"status": "degraded", "latency_ms": latency}
    except Exception:
        latency = round((time.monotonic() - start) * 1000)
        return {"status": "unreachable", "latency_ms": latency}


@router.get("/health/ready")
async def health_ready() -> dict:
    """Deep health check for deployment readiness probes.

    Checks database, Vault, and external API reachability. Returns
    individual check results and an overall status.

    Overall status logic:
    - "healthy" if both database AND Vault are ok (external APIs may be degraded)
    - "unhealthy" if database OR Vault is not ok

    This endpoint does NOT require authentication.
    """
    import src.config as config_module

    settings = config_module.get_settings()

    # Run all checks (DB and Vault are critical; external APIs are informational)
    db_result = await _check_db()
    vault_result = await _check_vault()
    linear_result = await _check_external_api("https://api.linear.app")
    slack_result = await _check_external_api("https://slack.com/api/api.test")
    fathom_result = await _check_external_api(settings.FATHOM_API_BASE_URL)

    checks = {
        "database": db_result,
        "vault": vault_result,
        "linear_api": linear_result,
        "slack_api": slack_result,
        "fathom_api": fathom_result,
    }

    # Overall status: healthy only if DB + Vault are ok
    critical_ok = (
        db_result["status"] == "ok" and vault_result["status"] == "ok"
    )
    overall_status = "healthy" if critical_ok else "unhealthy"

    logger.info(
        "Health ready check completed",
        status=overall_status,
        checks={k: v["status"] for k, v in checks.items()},
    )

    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
