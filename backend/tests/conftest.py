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

import src.config
from src.config import Settings, get_settings

# Test constants
TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-only"
TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
TEST_WORKSPACE_ID = "22222222-2222-2222-2222-222222222222"
TEST_EMAIL = "test@example.com"
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"


@pytest.fixture(autouse=True)
def _reset_settings():
    """Reset settings singleton before and after every test.

    This ensures no test leaks real .env values into subsequent tests.
    Setting _settings directly (instead of monkey-patching get_settings)
    keeps the function identity stable so dependency_overrides always works.
    """
    src.config._settings = None
    yield
    src.config._settings = None


def _make_test_settings(**overrides: str) -> Settings:
    """Create a Settings instance with test defaults."""
    defaults = {
        "SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
        "DATABASE_URL": TEST_DATABASE_URL,
        "ENVIRONMENT": "dev",
        "BACKEND_URL": "http://localhost:8000",
        "SLACK_REDIRECT_URI": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture()
def mock_settings() -> Generator[Settings, None, None]:
    """Inject test settings into the config singleton.

    Sets src.config._settings directly so that both get_settings() calls
    and Depends(get_settings) resolve to the test settings.
    """
    test_settings = _make_test_settings()
    src.config._settings = test_settings
    yield test_settings
    src.config._settings = None


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


class _QueryCounter:
    """Counts `session.execute()` calls and captures the SQL each ran.

    Used by perf-regression tests to assert "this code path made ≤ N round-trips".
    Wraps an existing AsyncSession (mock or real) by spying on .execute().
    """

    def __init__(self) -> None:
        self.count = 0
        self.sql: list[str] = []

    def reset(self) -> None:
        self.count = 0
        self.sql.clear()

    def attach(self, session) -> None:
        original_execute = session.execute

        async def counting_execute(stmt, *args, **kwargs):
            self.count += 1
            try:
                self.sql.append(str(stmt))
            except Exception:
                self.sql.append("<unstringable stmt>")
            return await original_execute(stmt, *args, **kwargs)

        session.execute = counting_execute


@pytest.fixture()
def query_counter() -> _QueryCounter:
    """Per-test query counter. Attach to a session via `query_counter.attach(session)`.

    Example:
        async def test_one_query(mock_session, query_counter):
            query_counter.attach(mock_session)
            await my_code(mock_session)
            assert query_counter.count == 1
    """
    return _QueryCounter()


@pytest.fixture()
def app(mock_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with mocked dependencies for testing.

    Overrides get_session to return a mock session, avoiding real DB connections.
    """
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
