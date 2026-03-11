"""In-memory rate limiting middleware for public endpoints.

Uses a sliding window counter per client IP. No external dependencies (no Redis)
-- suitable for MVP single-instance deployment. Protects webhook, OAuth callback,
and Fathom endpoints from abuse.
"""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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

# Default rate limit for matched paths if not specified above
_DEFAULT_LIMIT = 60

# Window size in seconds
_WINDOW_SECONDS = 60

# Cleanup threshold: remove entries older than this many seconds
_CLEANUP_THRESHOLD = 120


@dataclass
class _WindowEntry:
    """A sliding window entry tracking request counts."""

    timestamps: list[float] = field(default_factory=list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using in-memory sliding window counters.

    Only applies to specific public endpoint prefixes (webhooks, OAuth callbacks,
    Fathom API). All other paths pass through unaffected.

    Returns 429 Too Many Requests with Retry-After header when rate exceeded.
    """

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        # {client_ip: {path_prefix: _WindowEntry}}
        self._buckets: dict[str, dict[str, _WindowEntry]] = defaultdict(
            lambda: defaultdict(_WindowEntry)
        )
        self._last_cleanup = time.monotonic()

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

    def _cleanup_old_entries(self, now: float) -> None:
        """Remove stale entries from the buckets dict."""
        cutoff = now - _CLEANUP_THRESHOLD
        empty_ips = []
        for ip, prefixes in self._buckets.items():
            empty_prefixes = []
            for prefix, entry in prefixes.items():
                entry.timestamps = [t for t in entry.timestamps if t > cutoff]
                if not entry.timestamps:
                    empty_prefixes.append(prefix)
            for prefix in empty_prefixes:
                del prefixes[prefix]
            if not prefixes:
                empty_ips.append(ip)
        for ip in empty_ips:
            del self._buckets[ip]

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
        now = time.monotonic()

        # Periodic cleanup (every 60s)
        if now - self._last_cleanup > _WINDOW_SECONDS:
            self._cleanup_old_entries(now)
            self._last_cleanup = now

        # Get or create window entry for this IP + prefix
        entry = self._buckets[client_ip][prefix]

        # Remove timestamps outside the current window
        window_start = now - _WINDOW_SECONDS
        entry.timestamps = [t for t in entry.timestamps if t > window_start]

        if len(entry.timestamps) >= limit:
            # Rate limit exceeded
            retry_after = int(entry.timestamps[0] - window_start) + 1
            retry_after = max(retry_after, 1)

            logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                path=path,
                limit=limit,
                retry_after=retry_after,
            )

            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry later."},
                headers={"Retry-After": str(retry_after)},
            )

        # Record this request
        entry.timestamps.append(now)

        return await call_next(request)
