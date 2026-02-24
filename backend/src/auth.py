"""JWT decoding and validation for Supabase tokens."""

from datetime import datetime
from uuid import UUID

from jose import JWTError, jwt
from pydantic import BaseModel

from src.config import get_settings


class JWTPayload(BaseModel):
    """Structured payload extracted from a decoded Supabase JWT."""

    sub: UUID  # User ID
    email: str | None = None
    role: str | None = None
    exp: int | None = None


def decode_supabase_jwt(token: str) -> JWTPayload:
    """Decode and validate a Supabase JWT using the JWT secret.

    Uses HS256 algorithm (Supabase default). Verifies expiration.
    Returns a structured JWTPayload with sub (user_id), email, role, exp.

    Raises:
        JWTError: If the token is invalid, expired, or cannot be decoded.
    """
    settings = get_settings()

    if not settings.SUPABASE_JWT_SECRET:
        raise JWTError("SUPABASE_JWT_SECRET is not configured")

    payload = jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_exp": True},
    )

    # Validate required 'sub' claim
    if "sub" not in payload:
        raise JWTError("Token missing 'sub' claim")

    return JWTPayload(
        sub=UUID(payload["sub"]),
        email=payload.get("email"),
        role=payload.get("role"),
        exp=payload.get("exp"),
    )
