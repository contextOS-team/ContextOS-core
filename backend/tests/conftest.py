"""Shared pytest fixtures for ContextOS backend tests."""

import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings

# Test constants
TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-only"
TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
TEST_WORKSPACE_ID = "22222222-2222-2222-2222-222222222222"
TEST_EMAIL = "test@example.com"
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"


def _make_test_settings(**overrides: str) -> Settings:
    """Create a Settings instance with test defaults."""
    defaults = {
        "SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
        "DATABASE_URL": TEST_DATABASE_URL,
        "ENVIRONMENT": "dev",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture()
def mock_settings() -> Generator[Settings, None, None]:
    """Override get_settings() everywhere with test values for the duration of a test.

    Patches get_settings in src.config AND in any module that imported it directly
    (e.g., src.auth does `from src.config import get_settings`).
    """
    test_settings = _make_test_settings()
    get_settings.cache_clear()

    import src.auth
    import src.config

    original_config = src.config.get_settings
    original_auth = src.auth.get_settings

    def _override() -> Settings:
        return test_settings

    src.config.get_settings = _override  # type: ignore[assignment]
    src.auth.get_settings = _override  # type: ignore[assignment]
    yield test_settings
    src.config.get_settings = original_config  # type: ignore[assignment]
    src.auth.get_settings = original_auth  # type: ignore[assignment]
    get_settings.cache_clear()


@pytest.fixture()
def mock_jwt_payload() -> dict:
    """Return a valid JWT payload dict matching Supabase token structure."""
    return {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) + 3600,  # 1 hour from now
        "aud": "authenticated",
        "iss": "http://localhost:54321/auth/v1",
    }


@pytest.fixture()
def expired_jwt_payload() -> dict:
    """Return an expired JWT payload."""
    return {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) - 3600,  # 1 hour ago
        "aud": "authenticated",
    }


def _encode_jwt(payload: dict, secret: str = TEST_JWT_SECRET) -> str:
    """Encode a JWT payload with the given secret."""
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture()
def valid_token(mock_jwt_payload: dict) -> str:
    """Create a valid JWT token signed with the test secret."""
    return _encode_jwt(mock_jwt_payload)


@pytest.fixture()
def expired_token(expired_jwt_payload: dict) -> str:
    """Create an expired JWT token signed with the test secret."""
    return _encode_jwt(expired_jwt_payload)


@pytest.fixture()
def valid_auth_header(valid_token: str) -> dict[str, str]:
    """Return an Authorization header with a valid Bearer token."""
    return {"Authorization": f"Bearer {valid_token}"}


@pytest.fixture()
def expired_auth_header(expired_token: str) -> dict[str, str]:
    """Return an Authorization header with an expired Bearer token."""
    return {"Authorization": f"Bearer {expired_token}"}


@pytest.fixture()
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture()
def app(mock_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with mocked dependencies for testing.

    Overrides get_session to return a mock session, avoiding real DB connections.
    """
    # Import app after settings are overridden so engine creation uses test URL
    # We must override the session dependency to avoid actual DB connections
    from src.db import get_session
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session] = _mock_get_session
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def client(app) -> Generator[TestClient, None, None]:
    """Provide a sync TestClient for the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async httpx client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
