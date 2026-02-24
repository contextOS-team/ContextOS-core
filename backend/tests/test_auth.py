"""Tests for authentication: JWT decoding, /api/auth/me endpoint, 401 behavior."""

import time
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient

from src.auth import JWTError
from tests.conftest import TEST_EMAIL, TEST_JWT_SECRET, TEST_USER_ID, TEST_WORKSPACE_ID


# ---------------------------------------------------------------------------
# Unit tests for decode_supabase_jwt
# ---------------------------------------------------------------------------


def test_jwt_decode_valid_token(mock_settings) -> None:
    """decode_supabase_jwt with a valid HS256 token returns correct payload."""
    from src.auth import decode_supabase_jwt

    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
    }
    token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

    result = decode_supabase_jwt(token)

    assert result.sub == UUID(TEST_USER_ID)
    assert result.email == TEST_EMAIL
    assert result.role == "authenticated"
    assert result.exp is not None


def test_jwt_decode_invalid_token(mock_settings) -> None:
    """decode_supabase_jwt raises error on garbage input."""
    from src.auth import decode_supabase_jwt

    with pytest.raises(JWTError):
        decode_supabase_jwt("this-is-not-a-valid-jwt-token")


def test_jwt_decode_expired_token(mock_settings) -> None:
    """decode_supabase_jwt raises error on expired token."""
    from src.auth import decode_supabase_jwt

    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) - 3600,  # 1 hour ago
        "aud": "authenticated",
    }
    token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

    with pytest.raises(JWTError):
        decode_supabase_jwt(token)


def test_jwt_decode_wrong_secret(mock_settings) -> None:
    """decode_supabase_jwt raises error when token signed with different secret."""
    from src.auth import decode_supabase_jwt

    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
    }
    token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

    with pytest.raises(JWTError):
        decode_supabase_jwt(token)


def test_jwt_decode_missing_sub_claim(mock_settings) -> None:
    """decode_supabase_jwt raises error when 'sub' claim is missing."""
    from src.auth import decode_supabase_jwt

    payload = {
        "email": TEST_EMAIL,
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
    }
    token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

    with pytest.raises(JWTError, match="sub"):
        decode_supabase_jwt(token)


# ---------------------------------------------------------------------------
# Endpoint tests for GET /api/auth/me
# ---------------------------------------------------------------------------


def test_me_returns_401_without_token(client: TestClient) -> None:
    """GET /api/auth/me without Authorization header returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_401_with_invalid_token(client: TestClient) -> None:
    """GET /api/auth/me with 'Bearer invalid' returns 401."""
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_returns_401_with_expired_token(
    client: TestClient,
    expired_auth_header: dict[str, str],
) -> None:
    """GET /api/auth/me with expired JWT returns 401."""
    response = client.get("/api/auth/me", headers=expired_auth_header)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_returns_user_info_with_valid_token(
    client: TestClient,
    valid_auth_header: dict[str, str],
    mock_session: AsyncMock,
) -> None:
    """GET /api/auth/me with valid JWT returns user info when workspace exists."""
    # Mock the DB query to return a workspace_id for the user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)
    mock_session.execute.return_value = mock_result

    response = client.get("/api/auth/me", headers=valid_auth_header)
    assert response.status_code == 200

    data = response.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["email"] == TEST_EMAIL
    assert data["workspace_id"] == TEST_WORKSPACE_ID


def test_me_returns_401_when_no_workspace_membership(
    client: TestClient,
    valid_auth_header: dict[str, str],
    mock_session: AsyncMock,
) -> None:
    """GET /api/auth/me returns 401 when user has no workspace membership."""
    # Mock the DB query to return None (no membership found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    response = client.get("/api/auth/me", headers=valid_auth_header)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
