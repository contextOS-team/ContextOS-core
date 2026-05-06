"""Perf-regression tests for high-traffic code paths.

Production Supabase lives in Singapore, app server in Nuremberg — every
DB query pays ~280ms RTT. These tests pin specific call counts so a
future "innocent" refactor that reintroduces a query loop is caught by CI
instead of a user-visible latency spike.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi.security import HTTPAuthorizationCredentials

WORKSPACE_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_workspace_cache_hit_skips_db(monkeypatch):
    """get_current_user with a cache hit must NOT execute the workspace_members SELECT.

    Locks in the PERF-01 fix in src/dependencies.py — a Singapore round-trip
    is saved on every authenticated request when Redis returns a cached
    workspace_id.
    """
    from src import dependencies

    monkeypatch.setattr(
        dependencies,
        "_cache_get_workspace",
        AsyncMock(return_value=WORKSPACE_ID),
    )

    fake_payload = MagicMock(sub=USER_ID, email="test@example.com")
    monkeypatch.setattr(
        dependencies, "decode_supabase_jwt", lambda token: fake_payload
    )

    session = AsyncMock()
    session.execute = AsyncMock()

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake")
    user = await dependencies.get_current_user(credentials=creds, session=session)

    assert user.user_id == USER_ID
    assert user.workspace_id == WORKSPACE_ID
    assert session.execute.await_count == 0, (
        "get_current_user hit the DB despite a Redis cache hit — "
        "this is the regression PERF-01 was meant to prevent."
    )


@pytest.mark.asyncio
async def test_workspace_cache_miss_hits_db_and_writes_cache(monkeypatch):
    """On Redis miss, the DB is queried exactly once and the result is cached."""
    from src import dependencies

    monkeypatch.setattr(
        dependencies, "_cache_get_workspace", AsyncMock(return_value=None)
    )
    cache_set = AsyncMock()
    monkeypatch.setattr(dependencies, "_cache_set_workspace", cache_set)

    fake_payload = MagicMock(sub=USER_ID, email="test@example.com")
    monkeypatch.setattr(
        dependencies, "decode_supabase_jwt", lambda token: fake_payload
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = WORKSPACE_ID
    session = AsyncMock()
    session.execute = AsyncMock(return_value=db_result)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake")
    user = await dependencies.get_current_user(credentials=creds, session=session)

    assert user.workspace_id == WORKSPACE_ID
    assert session.execute.await_count == 1
    cache_set.assert_awaited_once_with(USER_ID, WORKSPACE_ID)
