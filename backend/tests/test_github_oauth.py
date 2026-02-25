"""Tests for GitHub App OAuth integration endpoints and services."""

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.config import get_settings
from tests.conftest import (
    TEST_EMAIL,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
)

# Test GitHub App config values
GITHUB_APP_ID = "123456"
GITHUB_APP_SLUG = "contextos-test"
GITHUB_CLIENT_ID = "Iv1.test_client_id"
GITHUB_CLIENT_SECRET = "test-github-client-secret"
GITHUB_WEBHOOK_SECRET = "test-github-webhook-secret"
# RSA private key for testing (DO NOT use in production)
GITHUB_APP_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA58SxBdGQrMrcdzkZlVyC0v+ldivW0YpfvQZlgIaRL42A9LEq
GRfDU48C+cis3SKl/GdOkJBfn2AgP7C5xO86KKozyCtY1EkgKD1X2wbSGhh/wYlQ
Z9htnbfEOgBcvjA8iBcCqQB1ZlMuXwAmDVWw7lu1s8apaJE8/fJ0iw0aS3FCCOLO
tkaMstizUDBdSu0T+3zbVZuvf2QmyQlRUARaspDSU+U4qACKLN4Zi8WWLrWcDyBN
+nX7QvlN03VOytyHWaoFa0p5KEl0HJnDDC8ZGp//w/l19KEa0kCK5FoEtqwU/Oei
CRXWJKIAnKX2zXNKmVnReebM41qQAQH2qmlvyQIDAQABAoIBAGcPnWJHfqx/psqz
Tu+OjDQ0bwjd1LAn9ouxKPienjgFlfb5Qw2WdgqVmQ6m0EujSSk0bQi20namAaEg
vnLWqEeF6/HSaLU5cT3DjWo9nbbx9vmCTIlpAdF08qKSH6uI+pnPlaS+KfZe/ctL
3x/l34AWsvVm3VU85GDObEmbAXrS4ROCRAIwjXJxxbIe9HdEPwg9SOcg/7NYIS18
tNtkDM60+2GGZY/N4/FewmAeXxCWtB0JHNoX7dJcNrHGUaMygpZoHWA1J3nkzQC5
CmlIt36RIzuiC45PFbbdpt3BKRmJBQBUeX0QG7Iqy+8K6l8tqmEjlzOwPhbZR3kc
KCESwoMCgYEA9kxl1PRgTYFbVGFgC8Y5MyRV43N0K9rWwWKjU5dVExOd+44DgBd/
L+a0LmtQTcPIIDWIZR3JsY8LAIMuV2AHPMaleuzn/vNoeyA4A9sE0XXPA9bMaSgY
tgGsBttAeQ6UpQzTQgp7zDxnn8hnWlUnYxCWU0blnikOhUPHwEyQ/z8CgYEA8OXG
vz2KIvgQZPtcaEAhLQKh39Cam/Wd0GFKkUgB+p1JKaZIHsT6vOzcCttw7/e7FfY2
B7qIxfJ5w1P3b/8c519fUjRlyrhBlIbqiWOWLAypBEhP2QrchaJAlT2bwh9ox9qG
+CdP8JjII+2X5ZYSKxaRAYK9xdhnBB3fWT48VvcCgYEA3aE/nRJOOlAlu9dn0xCL
Vi7jLqospm3lA93btJOf1Wu4pK1VDwWVyKfkCUU93MxJIFqrorncTe+26b4hjDR4
LsNeEzBtTuj/YpRKc4W5XzaQkxbNl+6h1d3JS94ttQFe1uqki2/dmJnecVSnVAz+
RVGew88vPlQZoeetLqh3bYcCgYA5LSBuFaoqwJwLi8mUCNyW9U/8cmOv7q0lX2I2
d1PY6uoJk6j8fJ5SpxlXDlyQ6EikXsrWLMT3zqRt4wkQsQloNS/HsB4U7oTKPvd9
4oArNloLZSpmhnhu02LmyTel7JSPEuQEFDiaD3k5ZdQurt7jETkbla97PPC+fmSb
pvTlYwKBgEVEB2cnJai6ccVd+Vy9mBK5YxI4o1IiBY1UOkqN4XtjiGOg3CwFqMPH
iWLtoXMS3/OgPRN/l5qw82npGQBKZXa7zm/sVhzdWQ1uayvOOVHwcvYJqCaFBTpa
7SVY7QfLwNZ9TUzXEPQmoVTmGGz6vhyeNP3G8ICNIORAnNw/ZQbB
-----END RSA PRIVATE KEY-----"""


@pytest.fixture()
def github_settings():
    """Create test settings with GitHub App config and patch everywhere."""
    from tests.conftest import _make_test_settings

    settings = _make_test_settings(
        GITHUB_APP_ID=GITHUB_APP_ID,
        GITHUB_APP_SLUG=GITHUB_APP_SLUG,
        GITHUB_CLIENT_ID=GITHUB_CLIENT_ID,
        GITHUB_CLIENT_SECRET=GITHUB_CLIENT_SECRET,
        GITHUB_WEBHOOK_SECRET=GITHUB_WEBHOOK_SECRET,
        GITHUB_APP_PRIVATE_KEY=GITHUB_APP_PRIVATE_KEY,
    )
    get_settings.cache_clear()

    import sys

    import src.auth
    import src.config

    old_config = src.config.get_settings
    old_auth = src.auth.get_settings

    _override = lambda: settings  # noqa: E731
    src.config.get_settings = _override  # type: ignore[assignment]
    src.auth.get_settings = _override  # type: ignore[assignment]

    # Patch the router module if already imported
    old_router = None
    if "src.routers.github" in sys.modules:
        import src.routers.github

        old_router = getattr(src.routers.github.config_module, "get_settings", None)
        src.routers.github.config_module.get_settings = _override  # type: ignore[assignment]

    yield settings

    src.config.get_settings = old_config  # type: ignore[assignment]
    src.auth.get_settings = old_auth  # type: ignore[assignment]
    if old_router is not None:
        import src.routers.github

        src.routers.github.config_module.get_settings = old_router  # type: ignore[assignment]
    get_settings.cache_clear()


@pytest.fixture()
def app_with_github(github_settings, mock_session):
    """Create a FastAPI app with GitHub settings and mocked session."""
    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session():
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session
    fastapi_app.dependency_overrides[get_settings] = lambda: github_settings
    # Override get_settings for any route dependency that captured a different callable
    for route in fastapi_app.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                name = getattr(dep.call, "__name__", "")
                if name in ("get_settings", "_override"):
                    fastapi_app.dependency_overrides[dep.call] = lambda: github_settings
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def github_client(app_with_github):
    """Provide a TestClient for the app with GitHub config."""
    from fastapi.testclient import TestClient

    with TestClient(app_with_github) as c:
        yield c


def _make_auth_header() -> dict[str, str]:
    """Create a valid auth header for tests."""
    import jwt as pyjwt

    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
        "iss": "http://localhost:54321/auth/v1",
    }
    token = pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


# ---------- /api/github/connect ----------


class TestConnect:
    """Tests for GET /api/github/connect."""

    def test_connect_returns_install_url(
        self, github_client, mock_session, github_settings
    ):
        """GET /api/github/connect returns 200 with installation_url containing app slug and signed state."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
        mock_session.execute.return_value = mock_result

        response = github_client.get(
            "/api/github/connect", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert "installation_url" in data
        url = data["installation_url"]
        assert f"github.com/apps/{GITHUB_APP_SLUG}" in url
        assert "state=" in url

    def test_connect_requires_auth(self, github_client):
        """GET /api/github/connect without token returns 401/403."""
        response = github_client.get("/api/github/connect")
        assert response.status_code in (401, 403)


# ---------- /api/github/callback ----------


class TestCallback:
    """Tests for GET /api/github/callback."""

    @pytest.mark.asyncio
    async def test_callback_stores_token_in_vault(
        self, github_settings, mock_session
    ):
        """handle_callback stores installation access token in Vault and creates records."""
        from src.services.github_oauth import handle_callback, _sign_state

        # Create a valid state
        state = _sign_state(UUID(TEST_WORKSPACE_ID), GITHUB_CLIENT_SECRET)

        # Mock installation token response
        mock_token_response = MagicMock()
        mock_token_response.status_code = 201
        mock_token_response.json.return_value = {
            "token": "ghs_installation_token_123",
            "expires_at": "2026-03-01T00:00:00Z",
            "permissions": {"pull_requests": "read"},
        }

        # Mock installation details response
        mock_install_response = MagicMock()
        mock_install_response.status_code = 200
        mock_install_response.json.return_value = {
            "id": 12345,
            "account": {"login": "test-org", "id": 67890},
        }

        # Track vault calls
        vault_calls = []

        async def mock_store(session, name, value):
            vault_calls.append(("store", name, value))
            return "secret-uuid"

        # Mock DB queries - return None for existing records (will create new)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        # Mock workspace member lookup to return a user_id
        call_count = 0
        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # WorkspaceMember lookup
                result.scalar_one_or_none.return_value = UUID(TEST_USER_ID)
            else:
                # All other queries return None (no existing records)
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        with (
            patch("src.services.github_oauth.store_token", side_effect=mock_store),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_token_response),
                    get=AsyncMock(return_value=mock_install_response),
                ),
            ),
        ):
            result = await handle_callback(
                installation_id=12345,
                setup_action="install",
                state=state,
                session=mock_session,
                settings=github_settings,
            )

        assert result["installation_id"] == 12345
        assert result["account"] == "test-org"

        # Verify token was stored in Vault
        assert len(vault_calls) == 1
        store_call = vault_calls[0]
        assert store_call[0] == "store"
        assert "access_token" in store_call[1]
        assert store_call[2] == "ghs_installation_token_123"

        # Verify session.add was called (OAuthToken + WorkspaceIntegration)
        assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_callback_invalid_state_rejected(
        self, github_settings, mock_session
    ):
        """handle_callback raises GitHubOAuthError on bad HMAC state."""
        from src.services.github_oauth import GitHubOAuthError, handle_callback

        with pytest.raises(GitHubOAuthError, match="Invalid state"):
            await handle_callback(
                installation_id=12345,
                setup_action="install",
                state="bad-workspace-id:bad-signature",
                session=mock_session,
                settings=github_settings,
            )


# ---------- /api/github/disconnect ----------


class TestDisconnect:
    """Tests for POST /api/github/disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_token(self, github_settings, mock_session):
        """disconnect soft-deletes OAuthToken, removes Vault secret, marks integration disconnected."""
        from src.services.github_oauth import disconnect

        # Mock OAuthToken query
        mock_oauth_token = MagicMock()
        mock_oauth_token.deleted_at = None

        # Mock WorkspaceIntegration query
        mock_integration = MagicMock()
        mock_integration.status = "connected"

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # OAuthToken query
                result.scalar_one_or_none.return_value = mock_oauth_token
            elif call_count == 3:
                # WorkspaceIntegration query (call 2 is vault delete)
                result.scalar_one_or_none.return_value = mock_integration
            else:
                # Vault delete calls
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_session.commit = AsyncMock()

        await disconnect(
            session=mock_session,
            workspace_id=UUID(TEST_WORKSPACE_ID),
            user_id=UUID(TEST_USER_ID),
        )

        # Verify soft-delete
        assert mock_oauth_token.deleted_at is not None
        assert mock_integration.status == "disconnected"
        mock_session.commit.assert_called_once()


# ---------- /api/github/status ----------


class TestStatus:
    """Tests for GET /api/github/status."""

    def test_status_connected(
        self, github_client, mock_session, github_settings
    ):
        """GET /api/github/status returns connected:true when integration exists."""
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.external_id = "test-org"

        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = mock_integration

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            return mock_integration_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        response = github_client.get(
            "/api/github/status", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["status"] == "connected"
        assert data["account"] == "test-org"

    def test_status_disconnected(
        self, github_client, mock_session, github_settings
    ):
        """GET /api/github/status returns connected:false when no integration exists."""
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        mock_integration_result = MagicMock()
        mock_integration_result.scalar_one_or_none.return_value = None

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_workspace_result
            return mock_integration_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        response = github_client.get(
            "/api/github/status", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["status"] == "disconnected"
        assert data["account"] is None


# ---------- Installation Token Refresh ----------


class TestInstallationToken:
    """Tests for installation token generation and refresh."""

    @pytest.mark.asyncio
    async def test_get_installation_token_refreshes_on_expiry(
        self, github_settings, mock_session
    ):
        """get_installation_token generates new token when expired via App JWT."""
        from src.services.github_oauth import get_installation_token

        # Mock expired OAuthToken
        mock_oauth_token = MagicMock()
        mock_oauth_token.token_expires_at = datetime.utcnow() - timedelta(hours=1)
        mock_oauth_token.metadata_ = {"installation_id": 12345}
        mock_oauth_token.deleted_at = None

        # Track vault calls
        vault_calls = []

        async def mock_store(session, name, value):
            vault_calls.append(("store", name, value))
            return "secret-uuid"

        # Mock GitHub API response for new installation token
        mock_token_response = MagicMock()
        mock_token_response.status_code = 201
        mock_token_response.json.return_value = {
            "token": "ghs_new_token_456",
            "expires_at": "2026-03-01T01:00:00Z",
            "permissions": {"pull_requests": "read"},
        }

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # OAuthToken query
                result.scalar_one_or_none.return_value = mock_oauth_token
            else:
                # Store token vault call
                result.scalar_one.return_value = "uuid"
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_session.commit = AsyncMock()

        with (
            patch("src.services.github_oauth.store_token", side_effect=mock_store),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_token_response)
                ),
            ),
        ):
            new_token = await get_installation_token(
                workspace_id=UUID(TEST_WORKSPACE_ID),
                session=mock_session,
                settings=github_settings,
            )

        assert new_token == "ghs_new_token_456"

        # Verify new token was stored in Vault
        assert len(vault_calls) == 1
        assert vault_calls[0][2] == "ghs_new_token_456"

        # Verify token expiry was updated in DB
        assert mock_oauth_token.token_expires_at is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_installation_token_returns_cached_when_valid(
        self, github_settings, mock_session
    ):
        """get_installation_token returns existing token when not expired."""
        from src.services.github_oauth import get_installation_token

        # Mock valid OAuthToken (expires in 30 minutes)
        mock_oauth_token = MagicMock()
        mock_oauth_token.token_expires_at = datetime.utcnow() + timedelta(minutes=30)
        mock_oauth_token.metadata_ = {"installation_id": 12345}
        mock_oauth_token.deleted_at = None

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = mock_oauth_token
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        with patch(
            "src.services.github_oauth.read_token",
            new_callable=AsyncMock,
            return_value="ghs_existing_valid_token",
        ):
            token = await get_installation_token(
                workspace_id=UUID(TEST_WORKSPACE_ID),
                session=mock_session,
                settings=github_settings,
            )

        assert token == "ghs_existing_valid_token"

    @pytest.mark.asyncio
    async def test_get_installation_token_no_integration_raises(
        self, github_settings, mock_session
    ):
        """get_installation_token raises GitHubOAuthError when no token exists."""
        from src.services.github_oauth import GitHubOAuthError, get_installation_token

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(GitHubOAuthError, match="No GitHub integration found"):
            await get_installation_token(
                workspace_id=UUID(TEST_WORKSPACE_ID),
                session=mock_session,
                settings=github_settings,
            )


# ---------- App JWT Generation ----------


class TestAppJWT:
    """Tests for GitHub App JWT creation."""

    def test_create_app_jwt_produces_valid_rs256_token(self, github_settings):
        """_create_app_jwt creates a JWT signed with RS256 containing correct claims."""
        from src.services.github_oauth import _create_app_jwt
        import jwt as pyjwt
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        token = _create_app_jwt(github_settings)

        # Decode without verification to inspect claims
        decoded = pyjwt.decode(token, options={"verify_signature": False})

        assert decoded["iss"] == GITHUB_APP_ID
        assert "iat" in decoded
        assert "exp" in decoded
        # exp should be ~10 minutes from iat
        assert decoded["exp"] - decoded["iat"] <= 11 * 60  # iat is 60s in past

        # Verify the JWT header uses RS256
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"
