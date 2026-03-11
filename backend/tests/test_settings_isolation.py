"""Tests proving config correctness.

These tests verify that:
- Redirect URIs derive from BACKEND_URL for all providers
- Slack override takes precedence when set
- BACKEND_URL propagates correctly to all redirect properties
- Production validation catches missing HTTPS
- SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are distinct fields
"""

import pytest

from tests.conftest import _make_test_settings


class TestRedirectUris:
    """Prove redirect URI derivation logic is correct."""

    def test_all_providers_derive_from_backend_url(self):
        """Every provider must build its redirect URI from BACKEND_URL."""
        settings = _make_test_settings(BACKEND_URL="http://myhost:9999")
        assert settings.linear_redirect_uri == "http://myhost:9999/api/linear/callback"
        assert settings.github_redirect_uri == "http://myhost:9999/api/github/callback"
        assert settings.notion_redirect_uri == "http://myhost:9999/api/notion/callback"
        assert settings.gitlab_redirect_uri == "http://myhost:9999/api/gitlab/callback"
        assert settings.jira_redirect_uri == "http://myhost:9999/api/jira/callback"
        # Slack falls back to BACKEND_URL when no override
        assert settings.slack_redirect_uri == "http://myhost:9999/api/slack/callback"

    def test_slack_override_wins_over_backend_url(self):
        """SLACK_REDIRECT_URI must take precedence over BACKEND_URL."""
        settings = _make_test_settings(
            BACKEND_URL="http://localhost:8000",
            SLACK_REDIRECT_URI="https://my-ngrok.dev/api/slack/callback",
        )
        assert settings.slack_redirect_uri == "https://my-ngrok.dev/api/slack/callback"

    def test_slack_override_does_not_affect_other_providers(self):
        """Setting SLACK_REDIRECT_URI must not change any other provider."""
        settings = _make_test_settings(
            BACKEND_URL="http://localhost:8000",
            SLACK_REDIRECT_URI="https://ngrok.dev/api/slack/callback",
        )
        assert "ngrok" not in settings.linear_redirect_uri
        assert "ngrok" not in settings.gitlab_redirect_uri
        assert "ngrok" not in settings.jira_redirect_uri

    def test_only_slack_has_override_field(self):
        """No other provider should have a redirect URI override field."""
        from src.config import Settings

        # These fields must not exist — if someone adds them back, this catches it
        for field in [
            "LINEAR_REDIRECT_URI",
            "GITHUB_REDIRECT_URI",
            "NOTION_REDIRECT_URI",
            "GITLAB_REDIRECT_URI",
            "JIRA_REDIRECT_URI",
        ]:
            assert field not in Settings.model_fields, (
                f"{field} should not exist on Settings — use BACKEND_URL"
            )
        # Slack override must exist
        assert "SLACK_REDIRECT_URI" in Settings.model_fields


class TestProductionValidation:
    """Prove production validation catches misconfigurations."""

    def test_http_backend_url_rejected_in_prod(self):
        """BACKEND_URL must be HTTPS in production."""
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db:5432/x",
            SUPABASE_JWT_SECRET="secret",
            SENTRY_DSN="https://sentry.io/123",
            CORS_ORIGINS="https://app.example.com",
            BACKEND_URL="http://localhost:8000",
        )
        with pytest.raises(RuntimeError, match="BACKEND_URL"):
            settings.validate_for_production()

    def test_https_backend_url_passes_in_prod(self):
        """HTTPS BACKEND_URL must pass production validation."""
        settings = _make_test_settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://x:x@db:5432/x",
            SUPABASE_JWT_SECRET="secret",
            SENTRY_DSN="https://sentry.io/123",
            CORS_ORIGINS="https://app.example.com",
            BACKEND_URL="https://api.example.com",
        )
        # Should not raise
        settings.validate_for_production()


class TestSupabaseKeySeparation:
    """Prove that anon and service-role keys are distinct config fields."""

    def test_anon_key_and_service_role_key_are_separate_fields(self):
        """Settings must have both SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY."""
        settings = _make_test_settings(
            SUPABASE_ANON_KEY="anon-key-value",
            SUPABASE_SERVICE_ROLE_KEY="service-role-value",
        )
        assert settings.SUPABASE_ANON_KEY == "anon-key-value"
        assert settings.SUPABASE_SERVICE_ROLE_KEY == "service-role-value"
        assert settings.SUPABASE_ANON_KEY != settings.SUPABASE_SERVICE_ROLE_KEY

    def test_old_supabase_key_field_does_not_exist(self):
        """The ambiguous SUPABASE_KEY field must not exist on Settings."""
        settings = _make_test_settings()
        assert not hasattr(settings, "SUPABASE_KEY")
