"""Tests proving .env cleanup correctness.

These tests verify that:
- Test settings don't leak real .env values into OAuth redirect URIs
- SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are distinct fields
- _make_test_settings produces deterministic, .env-independent results
"""

from tests.conftest import _make_test_settings


class TestSettingsIsolation:
    """Prove that _make_test_settings doesn't leak real .env values."""

    def test_redirect_uris_use_localhost_not_ngrok(self):
        """OAuth redirect URIs must resolve to localhost, never a real ngrok domain."""
        settings = _make_test_settings(
            LINEAR_CLIENT_ID="test-client",
            LINEAR_CLIENT_SECRET="test-secret",
        )
        assert "ngrok" not in settings.linear_redirect_uri
        assert "localhost" in settings.linear_redirect_uri

    def test_all_providers_redirect_to_localhost(self):
        """Every provider's redirect URI must be deterministic and local."""
        settings = _make_test_settings()
        for uri in [
            settings.linear_redirect_uri,
            settings.github_redirect_uri,
            settings.notion_redirect_uri,
            settings.slack_redirect_uri,
        ]:
            assert uri.startswith("http://localhost:8000/api/"), (
                f"Expected localhost redirect, got: {uri}"
            )

    def test_ngrok_domain_is_blank_in_test_settings(self):
        """NGROK_DOMAIN must be empty so _public_base_url falls back to BACKEND_URL."""
        settings = _make_test_settings()
        assert settings.NGROK_DOMAIN == ""

    def test_explicit_ngrok_overrides_when_passed(self):
        """When a test explicitly passes NGROK_DOMAIN, it should be used."""
        settings = _make_test_settings(NGROK_DOMAIN="test.ngrok.dev")
        assert settings.linear_redirect_uri == "https://test.ngrok.dev/api/linear/callback"


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
