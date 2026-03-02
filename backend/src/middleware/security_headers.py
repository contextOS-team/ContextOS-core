"""Security headers middleware.

Adds standard security headers to all responses:
- X-Content-Type-Options: nosniff (prevent MIME-type sniffing)
- X-Frame-Options: DENY (prevent clickjacking)
- Referrer-Policy: strict-origin-when-cross-origin
- Strict-Transport-Security: max-age=31536000 (prod only -- enforce HTTPS)
- Permissions-Policy: restrict sensitive browser features
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.config import Environment, get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._add_hsts = get_settings().ENVIRONMENT != Environment.DEV

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if self._add_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
