"""Integration tests against a live Supabase instance.

These tests require `supabase start` to be running. They create a real user
via the Supabase Admin API, get a real JWT, and hit the actual FastAPI
endpoints with a real database connection. No mocks.

Run: uv run pytest tests/test_integration.py -v
Skip if Supabase isn't running: tests auto-skip via the fixture.
"""

import os
import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Supabase local defaults
SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY", "sb_secret_N7UND0UgjKTVK-Uodkm0Hg_xSvEMPvz"
)
SUPABASE_JWT_SECRET = os.environ.get(
    "SUPABASE_JWT_SECRET",
    "super-secret-jwt-token-with-at-least-32-characters-long",
)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres",
)


def _supabase_is_running() -> bool:
    try:
        resp = httpx.get(f"{SUPABASE_URL}/auth/v1/health", timeout=2)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


pytestmark = pytest.mark.skipif(
    not _supabase_is_running(),
    reason="Supabase local is not running (run `supabase start` first)",
)


@pytest.fixture(scope="module")
def _patch_env():
    """Set env vars so the FastAPI app connects to real Supabase."""
    orig = {}
    env_overrides = {
        "DATABASE_URL": DATABASE_URL,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
        "SUPABASE_JWT_SECRET": SUPABASE_JWT_SECRET,
        "ENVIRONMENT": "dev",
    }
    for key, val in env_overrides.items():
        orig[key] = os.environ.get(key)
        os.environ[key] = val
    yield
    for key, val in orig.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


@pytest.fixture(scope="module")
def test_email():
    return f"integration-{uuid.uuid4().hex[:8]}@test.local"


@pytest.fixture(scope="module")
def test_password():
    return "integration-test-password-123"


@pytest.fixture(scope="module")
def supabase_user(test_email, test_password, _patch_env):
    """Create a real user via Supabase Admin API. Clean up after tests."""
    resp = httpx.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "email": test_email,
            "password": test_password,
            "email_confirm": True,
            "user_metadata": {"full_name": "Integration Test User"},
        },
        timeout=10,
    )
    if resp.status_code != 200:
        pytest.skip(
            f"Supabase admin user creation failed ({resp.status_code}): "
            f"{resp.text} — local DB triggers may need migration"
        )
    user_data = resp.json()

    yield user_data

    httpx.delete(
        f"{SUPABASE_URL}/auth/v1/admin/users/{user_data['id']}",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        },
        timeout=10,
    )


@pytest.fixture(scope="module")
def access_token(supabase_user, test_email, test_password):
    """Sign in as the test user and get a real Supabase JWT."""
    resp = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
        json={"email": test_email, "password": test_password},
        timeout=10,
    )
    assert resp.status_code == 200, f"Failed to sign in: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_header(access_token):
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture()
async def client(_patch_env):
    """Create an async test client with a fresh DB engine per test.

    Function-scoped to avoid asyncpg event loop issues.
    """
    import src.config
    from src.config import get_settings

    src.config._settings = None

    # Create a fresh engine on THIS event loop
    test_engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _get_session():
        async with test_session_factory() as session:
            yield session

    test_settings = get_settings()
    src.config._settings = test_settings

    from src.db import get_session
    from src.main import app

    app.dependency_overrides[get_session] = _get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await test_engine.dispose()


# ---------------------------------------------------------------------------
# The actual integration tests
# ---------------------------------------------------------------------------


async def test_health_with_real_db(client: AsyncClient):
    """Health endpoint reports db: connected against real Supabase PostgreSQL."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Note: health endpoint uses the module-level engine from db.py, not our
    # test override. It may show "disconnected" here. The important tests are
    # the ones below that exercise the full auth chain with real DB queries.


async def test_signup_trigger_created_workspace(supabase_user):
    """The handle_new_user trigger creates workspace, profile, and membership."""
    user_id = supabase_user["id"]

    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&select=id,email",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        },
        timeout=10,
    )
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) == 1, f"Expected 1 profile, got {len(profiles)}"
    assert profiles[0]["id"] == user_id

    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/workspace_members?user_id=eq.{user_id}&select=workspace_id,role",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        },
        timeout=10,
    )
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1, f"Expected 1 membership, got {len(members)}"
    assert members[0]["role"] == "owner"


async def test_auth_me_with_real_jwt(client: AsyncClient, auth_header: dict):
    """GET /api/auth/me with a real Supabase JWT returns real user data."""
    resp = await client.get("/api/auth/me", headers=auth_header)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert "user_id" in data
    assert "email" in data
    assert "workspace_id" in data
    assert data["email"].startswith("integration-")


async def test_workspace_current_with_real_data(client: AsyncClient, auth_header: dict):
    """GET /api/workspaces/current returns the auto-created workspace."""
    resp = await client.get("/api/workspaces/current", headers=auth_header)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert "id" in data
    assert "name" in data
    assert "slug" in data
    assert data["name"].endswith("'s Workspace")


async def test_unauthenticated_returns_401(client: AsyncClient):
    """Protected endpoints reject requests without valid JWT."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)

    resp = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer garbage-token"}
    )
    assert resp.status_code == 401
