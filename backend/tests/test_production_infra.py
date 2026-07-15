"""Tests for Phase 11 production infrastructure changes.

Covers: security headers, rate limiting on new paths, config validation.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Environment, Settings
from tests.conftest import _make_test_settings


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Deployment configuration
# ---------------------------------------------------------------------------


class TestProductionDeploymentConfig:
    """Keep rebuilt hosts aligned with the canonical production environment."""

    def test_frontend_build_args_reuse_canonical_env_names(self) -> None:
        compose = (REPO_ROOT / "docker-compose.prod.yml").read_text()

        expected = {
            "NEXT_PUBLIC_SUPABASE_URL": "SUPABASE_URL",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": "SUPABASE_ANON_KEY",
            "NEXT_PUBLIC_BACKEND_URL": "BACKEND_URL",
            "NEXT_PUBLIC_APP_URL": "APP_URL",
        }
        for build_arg, canonical_name in expected.items():
            assert f"{build_arg}: ${{{canonical_name}}}" in compose

        assert "NEXT_PUBLIC_SENTRY_DSN: ${SENTRY_DSN:-}" in compose

    def test_api_uses_shared_san_certificate(self) -> None:
        api_config = (REPO_ROOT / "nginx" / "api.conf").read_text()

        assert "/live/contextos.pro/fullchain.pem" in api_config
        assert "/live/contextos.pro/privkey.pem" in api_config
        assert "/live/api.contextos.pro/" not in api_config


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

    def test_allows_empty_legacy_jwt_secret_for_jwks(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_JWT_SECRET="",
            CORS_ORIGINS="https://app.contextos.dev",
            BACKEND_URL="https://api.contextos.dev",
        )
        settings.validate_for_production()

    def test_fails_with_empty_supabase_url(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_URL="",
            CORS_ORIGINS="https://app.contextos.dev",
        )
        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            settings.validate_for_production()

    def test_fails_with_empty_supabase_anon_key(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SUPABASE_ANON_KEY="",
            CORS_ORIGINS="https://app.contextos.dev",
        )
        with pytest.raises(RuntimeError, match="SUPABASE_ANON_KEY"):
            settings.validate_for_production()

    def test_allows_empty_sentry_dsn(self) -> None:
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db/x",
            SENTRY_DSN="",
            CORS_ORIGINS="https://app.contextos.dev",
            BACKEND_URL="https://api.contextos.dev",
        )
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
            SUPABASE_URL="",
            SUPABASE_ANON_KEY="",
            SENTRY_DSN="",
            CORS_ORIGINS="http://localhost:3000",
        )
        with pytest.raises(RuntimeError) as exc_info:
            settings.validate_for_production()
        msg = str(exc_info.value)
        assert "DATABASE_URL" in msg
        assert "SUPABASE_URL" in msg
        assert "SUPABASE_ANON_KEY" in msg
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
