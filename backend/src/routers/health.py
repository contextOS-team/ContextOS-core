"""Health check router.

Provides two endpoints:
- GET /api/health: Liveness probe — process is up. No external dependencies.
- GET /api/health/ready: Deep readiness probe checking DB, Vault, and external
  API reachability for deployment validation.

Neither endpoint requires authentication.
"""

import json
import time
from datetime import datetime, timezone
from time import monotonic

import httpx
import redis.asyncio as aioredis
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

# Cache the readiness payload to avoid hammering the DB, Vault, and external
# APIs on every probe. Singapore-DB round-trips alone make each fresh check
# expensive (~280ms RTT), so a short shared TTL stabilizes load without
# meaningfully delaying detection of regressions.
_READY_CACHE_KEY = "health:ready"
_READY_CACHE_TTL_SECONDS = 10
_READY_REDIS_RETRY_COOLDOWN_SECONDS = 30.0

_redis_client: aioredis.Redis | None = None
_redis_retry_after: float = 0.0


async def _get_redis() -> aioredis.Redis | None:
    """Lazy Redis connection. None if unreachable (with short cooldown to retry)."""
    global _redis_client, _redis_retry_after
    if _redis_client is not None:
        return _redis_client
    now = monotonic()
    if now < _redis_retry_after:
        return None
    try:
        import src.config as config_module

        settings = config_module.get_settings()
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        logger.warning("health_ready_redis_connect_failed", exc_info=True)
        _redis_retry_after = now + _READY_REDIS_RETRY_COOLDOWN_SECONDS
        return None


@router.get("/health")
async def health_check() -> dict:
    """Liveness probe: process is up. No external dependencies.

    Use /api/health/ready for a deep readiness check (DB + Vault + APIs).
    Touching the DB here means every Docker healthcheck (every 30s) pays a
    Singapore round-trip and shows up as ~1.5s TTFB.
    """
    return {"status": "ok"}


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

    The response is cached in Redis for ~10 seconds (key: ``health:ready``)
    so frequent monitor/load-balancer probes don't repeatedly pay for the
    DB SELECT, Vault round-trip, and external HEAD requests. If Redis is
    unreachable, checks run live (graceful degrade).
    """
    # Try cache first
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            cached = await redis_client.get(_READY_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            logger.warning("health_ready_cache_read_failed", exc_info=True)

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

    payload = {
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Cache only healthy responses. Caching "unhealthy" would pin a transient
    # blip for 10s after recovery — probes should fail closed but recover open.
    if redis_client is not None and overall_status == "healthy":
        try:
            await redis_client.set(
                _READY_CACHE_KEY,
                json.dumps(payload),
                ex=_READY_CACHE_TTL_SECONDS,
            )
        except Exception:
            logger.warning("health_ready_cache_write_failed", exc_info=True)

    return payload
