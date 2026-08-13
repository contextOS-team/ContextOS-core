"""Tests for agent API-key authentication (MachinePrincipal)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api_auth import MachinePrincipal, get_api_principal, require_scope
from src.db import get_session
from src.models.api_key import ApiKey
from src.services.api_key import generate_api_key

WS = uuid.uuid4()


def _stored_key(full_key: str, prefix: str, key_hash: str, salt: str, **over) -> ApiKey:
    values = dict(
        id=uuid.uuid4(),
        workspace_id=WS,
        created_by=uuid.uuid4(),
        name="agent",
        key_prefix=prefix,
        key_hash=key_hash,
        salt=salt,
        scopes=["decisions:read"],
        expires_at=None,
        revoked_at=None,
    )
    values.update(over)
    return ApiKey(**values)


def _app(session) -> FastAPI:
    app = FastAPI()

    async def _session_override():
        yield session

    app.dependency_overrides[get_session] = _session_override

    @app.get("/whoami")
    async def whoami(p: MachinePrincipal = Depends(get_api_principal)):
        return {"workspace_id": str(p.workspace_id), "scopes": p.scopes}

    @app.get("/scoped")
    async def scoped(p: MachinePrincipal = Depends(require_scope("decisions:read"))):
        return {"ok": True}

    @app.get("/needs-write")
    async def needs_write(
        p: MachinePrincipal = Depends(require_scope("decisions:write")),
    ):
        return {"ok": True}

    return app


def _session_returning(keys: list[ApiKey]) -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = keys
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def test_valid_key_authenticates():
    full, prefix, key_hash, salt = generate_api_key()
    key = _stored_key(full, prefix, key_hash, salt)
    client = TestClient(_app(_session_returning([key])))
    resp = client.get("/whoami", headers={"Authorization": f"Bearer {full}"})
    assert resp.status_code == 200
    assert resp.json()["workspace_id"] == str(WS)


def test_missing_key_is_401():
    client = TestClient(_app(_session_returning([])))
    assert client.get("/whoami").status_code == 401


def test_non_cos_bearer_is_401():
    client = TestClient(_app(_session_returning([])))
    resp = client.get("/whoami", headers={"Authorization": "Bearer eyJ.jwt.token"})
    assert resp.status_code == 401


def test_wrong_key_is_401():
    full, prefix, key_hash, salt = generate_api_key()
    key = _stored_key(full, prefix, key_hash, salt)
    other, *_ = generate_api_key()
    # Same prefix row returned, but the presented key won't verify.
    client = TestClient(_app(_session_returning([key])))
    resp = client.get("/whoami", headers={"Authorization": f"Bearer {other}"})
    assert resp.status_code == 401


def test_expired_key_is_401():
    full, prefix, key_hash, salt = generate_api_key()
    key = _stored_key(
        full, prefix, key_hash, salt, expires_at=datetime.now(UTC) - timedelta(days=1)
    )
    client = TestClient(_app(_session_returning([key])))
    resp = client.get("/whoami", headers={"Authorization": f"Bearer {full}"})
    assert resp.status_code == 401


def test_scope_enforced():
    full, prefix, key_hash, salt = generate_api_key()
    key = _stored_key(full, prefix, key_hash, salt, scopes=["decisions:read"])
    client = TestClient(_app(_session_returning([key])))
    hdr = {"Authorization": f"Bearer {full}"}
    assert client.get("/scoped", headers=hdr).status_code == 200
    assert client.get("/needs-write", headers=hdr).status_code == 403


@pytest.mark.parametrize("legacy_salt", [None])
def test_legacy_unsalted_key_still_verifies(legacy_salt):
    # Legacy keys (pre-00022) have NULL salt; verify_api_key handles them.
    full, prefix, _hash, _salt = generate_api_key()
    from src.services.api_key import _hash_key

    key = _stored_key(full, prefix, _hash_key(full, None), legacy_salt)
    client = TestClient(_app(_session_returning([key])))
    resp = client.get("/whoami", headers={"Authorization": f"Bearer {full}"})
    assert resp.status_code == 200
