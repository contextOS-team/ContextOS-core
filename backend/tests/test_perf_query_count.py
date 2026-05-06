"""Perf-regression tests for high-traffic code paths.

Production Supabase lives in Singapore, app server in Nuremberg — every
DB query pays ~280ms RTT. These tests pin specific call counts so a
future "innocent" refactor that reintroduces a query loop is caught by CI
instead of a user-visible latency spike.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fakeredis.aioredis import FakeRedis
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


# ---------------------------------------------------------------------------
# fakeredis-backed tests — exercise real Redis semantics rather than
# monkeypatching the helper functions out from under us.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_cache_key_format_and_ttl(monkeypatch):
    """Pin the on-disk cache key shape and TTL.

    A future refactor that changes the prefix silently invalidates every
    existing prod cache entry — should require an explicit code change,
    not slip through unnoticed.
    """
    from src import dependencies

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(dependencies, "_get_redis", AsyncMock(return_value=fake))

    await dependencies._cache_set_workspace(USER_ID, WORKSPACE_ID)

    raw = await fake.get(f"userctx:workspace:{USER_ID}")
    assert raw == str(WORKSPACE_ID), f"unexpected cache key shape; got value={raw!r}"

    ttl = await fake.ttl(f"userctx:workspace:{USER_ID}")
    # 5 min TTL ± jitter for the test runtime.
    assert 295 <= ttl <= 300, f"workspace cache TTL drifted: {ttl}s"


@pytest.mark.asyncio
async def test_workspace_cache_get_returns_none_on_miss(monkeypatch):
    """Cache miss returns None — never raises, never logs an error path."""
    from src import dependencies

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(dependencies, "_get_redis", AsyncMock(return_value=fake))

    got = await dependencies._cache_get_workspace(USER_ID)
    assert got is None


@pytest.mark.asyncio
async def test_workspace_cache_corrupt_value_treated_as_miss(monkeypatch):
    """Garbage in Redis (e.g. previous serialization scheme) must not crash."""
    from src import dependencies

    fake = FakeRedis(decode_responses=True)
    await fake.set(f"userctx:workspace:{USER_ID}", "not-a-uuid")
    monkeypatch.setattr(dependencies, "_get_redis", AsyncMock(return_value=fake))

    got = await dependencies._cache_get_workspace(USER_ID)
    assert got is None


# ---------------------------------------------------------------------------
# Digest lock tests
#
# The bug in the previous commit: _emit_daily_digest released the Redis
# lock when generate_digest returned None. None means either "DB dedup
# tripped" or "no messages" — in both cases the lock SHOULD stay held,
# because releasing it just means the next 15-min poll cycle pays the
# wasted DB round-trip the lock was meant to prevent.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _noop_session_cm():
    """Stand-in for `async with async_session() as session:`."""
    session = AsyncMock()
    session.commit = AsyncMock()
    yield session


def _patch_async_session(monkeypatch, module):
    """Replace `module.async_session` with a no-op async context manager factory."""

    def _factory(*_a, **_kw):
        return _noop_session_cm()

    monkeypatch.setattr(module, "async_session", _factory)


@pytest.mark.asyncio
async def test_digest_lock_held_when_generate_digest_returns_none(monkeypatch):
    """REGRESSION GUARD.

    If generate_digest returns None (DB dedup tripped OR no messages), the
    Redis lock MUST remain held until its 23h TTL expires. The previous
    implementation deleted the lock on None, which silently regressed the
    perf claim — every 15-minute cycle for the next 20h would re-enter
    generate_digest and pay the wasted ~9 DB round-trips its internal
    dedup costs.
    """
    from src.services import sync_scheduler

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(sync_scheduler, "_get_redis", AsyncMock(return_value=fake))
    monkeypatch.setattr(
        "src.services.digest.generate_digest",
        AsyncMock(return_value=None),
    )
    _patch_async_session(monkeypatch, sync_scheduler)

    ws = uuid4()
    await sync_scheduler._emit_daily_digest(ws, "slack")

    lock_key = f"digest:lock:{ws}:slack"
    assert await fake.get(lock_key) == "1", (
        "lock was released after generate_digest returned None — next poll "
        "cycle will pay the wasted DB round-trips again"
    )

    ttl = await fake.ttl(lock_key)
    # 23h ± a few seconds for test runtime.
    assert 23 * 3600 - 5 <= ttl <= 23 * 3600, f"digest lock TTL drifted: {ttl}s"


@pytest.mark.asyncio
async def test_digest_lock_blocks_concurrent_workers(monkeypatch):
    """Two workers entering _emit_daily_digest simultaneously: only one wins.

    The whole reason we moved off the in-memory dict was that two --workers
    processes have independent state. SET NX is atomic across them.
    """
    from src.services import sync_scheduler

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(sync_scheduler, "_get_redis", AsyncMock(return_value=fake))

    call_count = {"n": 0}

    async def fake_generate(*_a, **_kw):
        call_count["n"] += 1
        return {"message_count": 7}

    monkeypatch.setattr("src.services.digest.generate_digest", fake_generate)
    _patch_async_session(monkeypatch, sync_scheduler)

    ws = uuid4()
    # Two "workers" call back-to-back; the second must see the lock held.
    await sync_scheduler._emit_daily_digest(ws, "telegram")
    await sync_scheduler._emit_daily_digest(ws, "telegram")

    assert call_count["n"] == 1, (
        f"generate_digest ran {call_count['n']} times — Redis lock did not "
        "deduplicate concurrent workers"
    )


@pytest.mark.asyncio
async def test_digest_lock_released_on_exception(monkeypatch):
    """If generate_digest raises, the lock must be released so the next
    cycle can retry. (Otherwise a transient LLM error would silence the
    digest for 23h.)"""
    from src.services import sync_scheduler

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(sync_scheduler, "_get_redis", AsyncMock(return_value=fake))

    async def boom(*_a, **_kw):
        raise RuntimeError("LLM provider down")

    monkeypatch.setattr("src.services.digest.generate_digest", boom)
    _patch_async_session(monkeypatch, sync_scheduler)

    ws = uuid4()
    with pytest.raises(RuntimeError):
        await sync_scheduler._emit_daily_digest(ws, "slack")

    lock_key = f"digest:lock:{ws}:slack"
    assert await fake.get(lock_key) is None, "lock not released after exception"


@pytest.mark.asyncio
async def test_digest_no_redis_falls_through_to_db_dedup(monkeypatch):
    """Redis unavailable (returns None from _get_redis) — we still call
    generate_digest and rely on its own DB-based dedup. We do NOT crash."""
    from src.services import sync_scheduler

    monkeypatch.setattr(sync_scheduler, "_get_redis", AsyncMock(return_value=None))

    called = {"n": 0}

    async def fake_generate(*_a, **_kw):
        called["n"] += 1
        return None

    monkeypatch.setattr("src.services.digest.generate_digest", fake_generate)
    _patch_async_session(monkeypatch, sync_scheduler)

    await sync_scheduler._emit_daily_digest(uuid4(), "slack")
    assert called["n"] == 1
