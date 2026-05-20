"""Shared pytest fixtures for ContextOS backend tests."""

import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
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


def _stmt_entity_name(stmt: object) -> str | None:
    """Best-effort name of the ORM entity a SELECT targets.

    Returns the mapped class name (e.g. ``"SlackMessage"``) for
    ``select(Model)`` statements, or ``None`` for textual / unrecognised
    statements (raw ``text()`` SQL, ``hybrid_search()`` calls, etc.).
    """
    try:
        descriptions = getattr(stmt, "column_descriptions", None)
        if descriptions:
            for desc in descriptions:
                entity = desc.get("entity") or desc.get("type")
                name = getattr(entity, "__name__", None)
                if name:
                    return name
    except Exception:
        pass
    return None


class _TextualRouter:
    """Marker wrapper: route textual statements by their bound params.

    A plain ``callable()`` check can't distinguish "a function that maps
    params -> result" from a ``MagicMock`` result (every MagicMock is
    callable), so the router must be explicitly tagged. Build one with
    :func:`route_textual`.
    """

    __slots__ = ("fn",)

    def __init__(self, fn):
        self.fn = fn


def route_textual(fn):
    """Wrap a ``(params: dict) -> result`` function for ``textual=``.

    Use when several ``text()`` calls share one statement but differ by
    bound params (e.g. the general vs. dedicated-code ``hybrid_search``
    calls, which differ only by ``source_type``)::

        textual=route_textual(
            lambda p: code_rows if p.get("source_type") == "code_chunk"
            else general_rows
        )
    """
    return _TextualRouter(fn)


def make_entity_execute(
    results: dict[str, object] | None = None,
    *,
    textual: object | None = None,
    default: object | None = None,
):
    """Build an ``AsyncMock`` side-effect that dispatches by ORM entity.

    Positional ``side_effect`` lists rot every time a service grows another
    ``session.execute()``: a test that doesn't care about the new query
    still has to add a mock for it in exactly the right slot, or every
    later mock shifts and the suite breaks with ``StopAsyncIteration``.

    This dispatcher routes by *what* is being queried, not call order:

    - ``results``: ``{"SlackMessage": <result>, ...}`` keyed by model name
      (the class passed to ``select()``).
    - ``textual``: result for raw ``text()`` / function statements such as
      the ``hybrid_search()`` SQL (no ORM entity to key on). May be a fixed
      result, or a callable ``(params: dict) -> result`` when several
      ``text()`` calls share one statement but differ by bound params
      (e.g. the general vs. dedicated-code hybrid_search calls, which only
      differ by ``source_type``).
    - ``default``: returned for any entity not in ``results``. Defaults to
      an empty ``.scalars().all()`` result so unmodelled queries are inert.

    Adding a new ``select(NewModel)`` to the service therefore can't break
    a test that doesn't register ``NewModel`` — it just gets ``default``.
    """
    results = results or {}

    def _empty():
        r = MagicMock()
        r.scalars.return_value.all.return_value = []
        r.scalar_one_or_none.return_value = None
        r.fetchall.return_value = []
        return r

    default_result = default if default is not None else _empty()

    async def _execute(stmt, *args, **kwargs):
        name = _stmt_entity_name(stmt)
        if name is not None:
            return results.get(name, default_result)
        # Textual / function statement (no ORM entity to key on).
        if isinstance(textual, _TextualRouter):
            params = args[0] if args else kwargs.get("params") or {}
            return textual.fn(params)
        return textual if textual is not None else _empty()

    return _execute


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
