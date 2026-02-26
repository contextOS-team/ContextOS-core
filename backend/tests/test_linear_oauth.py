"""Tests for Linear OAuth integration endpoints and services."""

import time
from datetime import datetime, timedelta, timezone
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

# Test Linear OAuth config values
LINEAR_CLIENT_ID = "test-linear-client-id"
LINEAR_CLIENT_SECRET = "test-linear-client-secret"
LINEAR_WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture()
def linear_settings():
    """Create test settings with Linear OAuth config and patch everywhere."""
    from tests.conftest import _make_test_settings

    settings = _make_test_settings(
        LINEAR_CLIENT_ID=LINEAR_CLIENT_ID,
        LINEAR_CLIENT_SECRET=LINEAR_CLIENT_SECRET,
        LINEAR_WEBHOOK_SECRET=LINEAR_WEBHOOK_SECRET,
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

    # Patch the router module if already imported (full suite scenario)
    old_router = None
    if "src.routers.linear" in sys.modules:
        import src.routers.linear

        old_router = src.routers.linear.get_settings
        src.routers.linear.get_settings = _override  # type: ignore[assignment]

    yield settings

    src.config.get_settings = old_config  # type: ignore[assignment]
    src.auth.get_settings = old_auth  # type: ignore[assignment]
    if old_router is not None:
        import src.routers.linear

        src.routers.linear.get_settings = old_router  # type: ignore[assignment]
    get_settings.cache_clear()


@pytest.fixture()
def app_with_linear(linear_settings, mock_session):
    """Create a FastAPI app with Linear settings and mocked session."""
    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session():
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session
    # Override get_settings via the original @lru_cache reference
    fastapi_app.dependency_overrides[get_settings] = lambda: linear_settings
    # The router's Depends(get_settings) may have captured a conftest _override
    # lambda if the router was first imported during a mock_settings fixture.
    # Find and override the actual callable from the route dependency graph.
    for route in fastapi_app.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                name = getattr(dep.call, "__name__", "")
                if name in ("get_settings", "_override"):
                    fastapi_app.dependency_overrides[dep.call] = lambda: linear_settings
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def linear_client(app_with_linear):
    """Provide a TestClient for the app with Linear config."""
    from fastapi.testclient import TestClient

    with TestClient(app_with_linear) as c:
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


# ---------- /api/linear/connect ----------


class TestConnect:
    """Tests for GET /api/linear/connect."""

    def test_connect_returns_authorization_url(
        self, linear_client, mock_session, linear_settings
    ):
        """GET /api/linear/connect returns 200 with authorization_url containing client_id and state."""
        # Mock the workspace membership lookup that get_current_user does
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
        mock_session.execute.return_value = mock_result

        response = linear_client.get(
            "/api/linear/connect", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        url = data["authorization_url"]
        assert "linear.app/oauth/authorize" in url
        assert f"client_id={LINEAR_CLIENT_ID}" in url
        assert "state=" in url
        assert "scope=read,write" in url

    def test_connect_requires_auth(self, linear_client):
        """GET /api/linear/connect without token returns 401/403."""
        response = linear_client.get("/api/linear/connect")
        assert response.status_code in (401, 403)


# ---------- /api/linear/callback ----------


class TestCallback:
    """Tests for GET /api/linear/callback."""

    @pytest.mark.asyncio
    async def test_callback_exchanges_code_and_stores_token(
        self, linear_settings, mock_session
    ):
        """exchange_code stores tokens in Vault and creates integration record."""
        from src.services.linear_oauth import exchange_code

        # Mock the httpx calls
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "lin_access_token_123",
            "refresh_token": "lin_refresh_token_456",
            "expires_in": 86400,
        }

        mock_org_response = MagicMock()
        mock_org_response.status_code = 200
        mock_org_response.json.return_value = {
            "data": {"organization": {"id": "org-123", "name": "Test Org"}}
        }

        # Track vault calls
        vault_calls = []

        async def mock_store(session, name, value):
            vault_calls.append(("store", name, value))
            return "secret-uuid"

        # Mock DB queries - return None for existing records (will create new)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with (
            patch("src.services.linear_oauth.store_token", side_effect=mock_store),
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    post=AsyncMock(
                        side_effect=[mock_token_response, mock_org_response]
                    )
                ),
            ),
        ):
            org_info = await exchange_code(
                code="test-auth-code",
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID(TEST_USER_ID),
                settings=linear_settings,
            )

        assert org_info["id"] == "org-123"
        assert org_info["name"] == "Test Org"

        # Verify tokens were stored in Vault
        assert len(vault_calls) == 2
        access_call = vault_calls[0]
        assert access_call[0] == "store"
        assert "access" in access_call[1]
        assert access_call[2] == "lin_access_token_123"

        refresh_call = vault_calls[1]
        assert refresh_call[0] == "store"
        assert "refresh" in refresh_call[1]
        assert refresh_call[2] == "lin_refresh_token_456"

        # Verify session.add was called (new records created)
        assert mock_session.add.call_count == 2  # OAuthToken + WorkspaceIntegration


# ---------- /api/linear/disconnect ----------


class TestDisconnect:
    """Tests for POST /api/linear/disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect_soft_deletes_token(self, linear_settings, mock_session):
        """POST /api/linear/disconnect marks integration as disconnected."""
        from src.services.linear_oauth import disconnect

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
            elif call_count == 4:
                # WorkspaceIntegration query
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


# ---------- /api/linear/status ----------


class TestStatus:
    """Tests for GET /api/linear/status."""

    def test_status_returns_connected_when_integration_exists(
        self, linear_client, mock_session, linear_settings
    ):
        """GET /api/linear/status returns connected:true when integration exists."""
        mock_workspace_result = MagicMock()
        mock_workspace_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.external_id = "org-123"

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

        response = linear_client.get(
            "/api/linear/status", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["status"] == "connected"
        assert data["organization_name"] == "org-123"

    def test_status_returns_disconnected_when_no_integration(
        self, linear_client, mock_session, linear_settings
    ):
        """GET /api/linear/status returns connected:false when no integration exists."""
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

        response = linear_client.get(
            "/api/linear/status", headers=_make_auth_header()
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["status"] == "disconnected"
        assert data["organization_name"] is None


# ---------- Token Refresh ----------


class TestTokenRefresh:
    """Tests for token refresh with advisory lock."""

    @pytest.mark.asyncio
    async def test_refresh_token_acquires_advisory_lock(
        self, linear_settings, mock_session
    ):
        """refresh_access_token calls pg_advisory_xact_lock during refresh."""
        from src.services.linear_oauth import refresh_access_token

        mock_oauth_token = MagicMock()
        mock_oauth_token.token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=1
        )
        mock_oauth_token.refresh_token = "vault_ref_name"

        # Track executed SQL
        executed_sql = []

        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 86400,
        }

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            stmt = args[0] if args else None
            if hasattr(stmt, "text"):
                executed_sql.append(str(stmt.text))
            elif hasattr(stmt, "__str__"):
                executed_sql.append(str(stmt))

            result = MagicMock()
            if call_count == 1:
                # Advisory lock call
                result.scalar_one_or_none.return_value = None
            elif call_count == 2:
                # OAuthToken query
                result.scalar_one_or_none.return_value = mock_oauth_token
            elif call_count == 3:
                # Read refresh token from Vault
                result.scalar_one_or_none.return_value = "actual_refresh_token"
            else:
                # Store token calls
                result.scalar_one.return_value = "uuid"
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_session.commit = AsyncMock()

        with patch(
            "httpx.AsyncClient.__aenter__",
            return_value=MagicMock(
                post=AsyncMock(return_value=mock_token_response)
            ),
        ):
            new_token = await refresh_access_token(
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID(TEST_USER_ID),
                settings=linear_settings,
            )

        assert new_token == "new_access_token"

        # Verify advisory lock was acquired
        assert any("pg_advisory_xact_lock" in sql for sql in executed_sql)

    @pytest.mark.asyncio
    async def test_refresh_failure_marks_integration_error(
        self, linear_settings, mock_session
    ):
        """When refresh POST fails, integration.status becomes 'error'."""
        from src.services.linear_oauth import OAuthError, refresh_access_token

        mock_oauth_token = MagicMock()
        mock_oauth_token.token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=1
        )

        mock_integration = MagicMock()
        mock_integration.status = "connected"

        mock_error_response = MagicMock()
        mock_error_response.status_code = 400
        mock_error_response.text = "invalid_grant"

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # Advisory lock
                result.scalar_one_or_none.return_value = None
            elif call_count == 2:
                # OAuthToken query
                result.scalar_one_or_none.return_value = mock_oauth_token
            elif call_count == 3:
                # Read refresh token from Vault
                result.scalar_one_or_none.return_value = "old_refresh_token"
            elif call_count == 4:
                # WorkspaceIntegration query in _mark_integration_error
                result.scalar_one_or_none.return_value = mock_integration
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_session.commit = AsyncMock()

        with (
            patch(
                "httpx.AsyncClient.__aenter__",
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_error_response)
                ),
            ),
            pytest.raises(OAuthError, match="Token refresh failed"),
        ):
            await refresh_access_token(
                session=mock_session,
                workspace_id=UUID(TEST_WORKSPACE_ID),
                user_id=UUID(TEST_USER_ID),
                settings=linear_settings,
            )

        # Verify integration was marked as error
        assert mock_integration.status == "error"
