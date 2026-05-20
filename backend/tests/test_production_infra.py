"""Tests for Phase 11 production infrastructure changes.

Covers: security headers, rate limiting on new paths, config validation.
"""

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Environment, Settings
from tests.conftest import _make_test_settings


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """Verify security headers are present on actual HTTP responses."""

    def test_permissions_policy_header_present(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_existing_headers_still_present(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_hsts_absent_in_dev(self, client: TestClient) -> None:
        """HSTS must NOT be sent in dev mode — would break local HTTP."""
        response = client.get("/api/health")
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_flag_true_when_not_dev(self) -> None:
        """Middleware must set _add_hsts=True when environment is not DEV."""
        prod_settings = _make_test_settings(ENVIRONMENT="prod", SENTRY_DSN="https://fake@sentry.io/1")
        src.config._settings = prod_settings

        from src.middleware.security_headers import SecurityHeadersMiddleware

        # Instantiate middleware directly to verify init-time decision
        middleware = SecurityHeadersMiddleware(app=None)  # type: ignore[arg-type]
        assert middleware._add_hsts is True

    def test_hsts_flag_false_in_dev(self) -> None:
        """Middleware must set _add_hsts=False when environment is DEV."""
        dev_settings = _make_test_settings(ENVIRONMENT="dev")
        src.config._settings = dev_settings

        from src.middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=None)  # type: ignore[arg-type]
        assert middleware._add_hsts is False


# ---------------------------------------------------------------------------
# Rate limiting — new OAuth callback paths
# ---------------------------------------------------------------------------


class TestRateLimitNewPaths:
    """Verify GitHub and Notion callback paths are rate-limited."""

    def test_github_callback_is_rate_limited(self) -> None:
        from src.middleware.rate_limit import _RATE_LIMITED_PREFIXES

        paths = [prefix for prefix, _ in _RATE_LIMITED_PREFIXES]
        assert "/api/github/callback" in paths

    def test_notion_callback_is_rate_limited(self) -> None:
        from src.middleware.rate_limit import _RATE_LIMITED_PREFIXES

        paths = [prefix for prefix, _ in _RATE_LIMITED_PREFIXES]
        assert "/api/notion/callback" in paths

    def test_github_callback_limit_is_60(self) -> None:
        from src.middleware.rate_limit import _RATE_LIMITED_PREFIXES

        limits = {prefix: limit for prefix, limit in _RATE_LIMITED_PREFIXES}
        assert limits["/api/github/callback"] == 60

    def test_notion_callback_limit_is_60(self) -> None:
        from src.middleware.rate_limit import _RATE_LIMITED_PREFIXES

        limits = {prefix: limit for prefix, limit in _RATE_LIMITED_PREFIXES}
        assert limits["/api/notion/callback"] == 60


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Verify validate_for_production() catches real misconfigurations."""

    def test_skips_in_dev(self) -> None:
        """Should silently return in dev, even with missing values."""
        settings = _make_test_settings(
            ENVIRONMENT="dev",
            DATABASE_URL="",
            SUPABASE_JWT_SECRET="",
            SENTRY_DSN="",
        )
        # Must not raise
        settings.validate_for_production()

    def test_skips_in_staging(self) -> None:
        """Should silently return in staging."""
        settings = _make_test_settings(ENVIRONMENT="staging", DATABASE_URL="")
        settings.validate_for_production()

    def test_fails_with_empty_database_url(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="",
            SUPABASE_JWT_SECRET="real-secret",
            SENTRY_DSN="https://fake@sentry.io/1",
            CORS_ORIGINS="https://app.contextos.dev",
        )
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            settings.validate_for_production()

    def test_fails_with_empty_jwt_secret(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_JWT_SECRET="",
            SENTRY_DSN="https://fake@sentry.io/1",
            CORS_ORIGINS="https://app.contextos.dev",
        )
        with pytest.raises(RuntimeError, match="SUPABASE_JWT_SECRET"):
            settings.validate_for_production()

    def test_fails_with_empty_sentry_dsn(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_JWT_SECRET="real-secret",
            SENTRY_DSN="",
            CORS_ORIGINS="https://app.contextos.dev",
        )
        with pytest.raises(RuntimeError, match="SENTRY_DSN"):
            settings.validate_for_production()

    def test_fails_with_localhost_in_cors(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_JWT_SECRET="real-secret",
            SENTRY_DSN="https://fake@sentry.io/1",
            CORS_ORIGINS="http://localhost:3000",
        )
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            settings.validate_for_production()

    def test_fails_with_localhost_among_multiple_origins(self) -> None:
        """Catches localhost even when mixed with real origins."""
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_JWT_SECRET="real-secret",
            SENTRY_DSN="https://fake@sentry.io/1",
            CORS_ORIGINS="https://app.contextos.dev,http://localhost:3000",
        )
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            settings.validate_for_production()

    def test_passes_with_all_valid_prod_config(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_JWT_SECRET="real-secret",
            SENTRY_DSN="https://fake@sentry.io/1",
            CORS_ORIGINS="https://app.contextos.dev",
            # Production requires an HTTPS backend URL (validate_for_production
            # rejects the http://localhost test default).
            BACKEND_URL="https://api.contextos.dev",
        )
        # Must not raise
        settings.validate_for_production()

    def test_reports_all_missing_at_once(self) -> None:
        """Should list ALL problems, not fail on the first one."""
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="",
            SUPABASE_JWT_SECRET="",
            SENTRY_DSN="",
            CORS_ORIGINS="http://localhost:3000",
        )
        with pytest.raises(RuntimeError) as exc_info:
            settings.validate_for_production()
        msg = str(exc_info.value)
        assert "DATABASE_URL" in msg
        assert "SUPABASE_JWT_SECRET" in msg
        assert "SENTRY_DSN" in msg
        assert "CORS_ORIGINS" in msg


# ---------------------------------------------------------------------------
# DB pool configuration
# ---------------------------------------------------------------------------


class TestDbPoolConfig:
    """Verify connection pool parameters are set on the engine."""

    def test_pool_size_configured(self) -> None:
        from src.db import engine

        assert engine.pool.size() == 5

    def test_pool_recycle_configured(self) -> None:
        """pool_recycle=300 prevents stale connections behind PgBouncer."""
        from src.db import engine

        assert engine.pool._recycle == 300
