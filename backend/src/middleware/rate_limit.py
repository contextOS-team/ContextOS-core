"""Redis-backed sliding window rate limiting middleware for public endpoints.

SEC-05: Uses Redis sorted sets for rate limit state that survives process
restarts. Falls open on Redis failure to prevent outages from blocking
all API requests. Protects webhook, OAuth callback, and Fathom endpoints.
"""

from __future__ import annotations

import ipaddress
import time

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import get_settings
from src.observability.logging import get_logger

logger = get_logger(__name__)

# Paths subject to rate limiting (prefix match)
_RATE_LIMITED_PREFIXES: list[tuple[str, int]] = [
    # (path_prefix, max_requests_per_minute)
    ("/api/webhooks/", 120),  # Higher limit for legitimate webhook bursts
    ("/api/linear/callback", 60),
    ("/api/slack/callback", 60),
    ("/api/github/callback", 60),
    ("/api/notion/callback", 60),
    ("/api/fathom/", 60),
]

# Window size in seconds
_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis sorted sets (sliding window).

    Only applies to specific public endpoint prefixes (webhooks, OAuth callbacks,
    Fathom API). All other paths pass through unaffected.

    Returns 429 Too Many Requests with Retry-After header when rate exceeded.
    On Redis failure, fails open (allows request) and logs a warning.
    """

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis | None:
        """Lazy Redis connection with error handling."""
        if self._redis is None:
            try:
                settings = get_settings()
                self._redis = aioredis.from_url(
                    settings.REDIS_URL, decode_responses=True
                )
                # Verify connection
                await self._redis.ping()
            except Exception:
                logger.warning("rate_limit_redis_connect_failed", exc_info=True)
                self._redis = None
        return self._redis

    @staticmethod
    def _is_trusted_proxy(ip: str) -> bool:
        """Check if IP is a known proxy (loopback or private range).

        SEC-02: Only trust X-Forwarded-For from these addresses to prevent
        direct clients from spoofing their IP to bypass rate limits.
        """
        try:
            addr = ipaddress.ip_address(ip)
            return addr.is_loopback or addr.is_private
        except ValueError:
            return False

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, only trusting X-Forwarded-For from known proxies."""
        client_host = request.client.host if request.client else "unknown"

        # SEC-02: Only trust X-Forwarded-For when request comes from a proxy
        if client_host != "unknown" and self._is_trusted_proxy(client_host):
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()

        return client_host

    def _get_rate_limit(self, path: str) -> tuple[str, int] | None:
        """Return (prefix, limit) if path matches a rate-limited prefix, else None."""
        for prefix, limit in _RATE_LIMITED_PREFIXES:
            if path.startswith(prefix):
                return prefix, limit
        return None

    async def _check_rate_limit(
        self, r: aioredis.Redis, key: str, limit: int, now: float
    ) -> tuple[bool, int]:
        """Check rate limit using Redis sorted set sliding window.

        Returns:
            Tuple of (allowed, count) where allowed is True if under limit.
        """
        window_start = now - _WINDOW_SECONDS

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, _WINDOW_SECONDS + 10)  # TTL slightly longer than window
        results = await pipe.execute()

        count = results[2]  # ZCARD result
        return count <= limit, count

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        match = self._get_rate_limit(path)

        if match is None:
            # Not a rate-limited path -- pass through
            return await call_next(request)

        prefix, limit = match
        client_ip = self._get_client_ip(request)
        now = time.time()

        # SEC-05: Fail open on Redis failure -- never block requests due to Redis outage
        try:
            r = await self._get_redis()
            if r is None:
                return await call_next(request)

            key = f"ratelimit:{client_ip}:{prefix}"
            allowed, count = await self._check_rate_limit(r, key, limit, now)

            if not allowed:
                retry_after = max(1, _WINDOW_SECONDS)

                logger.warning(
                    "rate_limit_exceeded",
                    client_ip=client_ip,
                    path=path,
                    limit=limit,
                    count=count,
                    retry_after=retry_after,
                )

                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please retry later."},
                    headers={"Retry-After": str(retry_after)},
                )

        except Exception:
            # Fail open: allow request on any Redis error
            logger.warning(
                "rate_limit_redis_error",
                client_ip=client_ip,
                path=path,
                exc_info=True,
            )

        return await call_next(request)
