"""JWT decoding and validation for Supabase tokens."""

from uuid import UUID

import httpx
import jwt
from jwt import PyJWKClient
from pydantic import BaseModel

from src.config import get_settings


class JWTPayload(BaseModel):
    """Structured payload extracted from a decoded Supabase JWT."""

    sub: UUID  # User ID
    email: str | None = None
    role: str | None = None
    exp: int | None = None


class JWTError(Exception):
    """Raised when JWT decoding or validation fails."""


# Cache the JWKS client per Supabase URL (module-level singleton)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Return a cached JWKS client for the Supabase instance."""
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def decode_supabase_jwt(token: str) -> JWTPayload:
    """Decode and validate a Supabase JWT.

    Supports both ES256 (Supabase v2 default, verified via JWKS) and
    HS256 (legacy, verified via SUPABASE_JWT_SECRET). The algorithm is
    detected from the token header.

    Raises:
        JWTError: If the token is invalid, expired, or cannot be decoded.
    """
    settings = get_settings()

    try:
        # Peek at header to determine algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "HS256":
            # Legacy: verify with shared secret
            if not settings.SUPABASE_JWT_SECRET:
                raise JWTError("SUPABASE_JWT_SECRET is not configured")
            key = settings.SUPABASE_JWT_SECRET
            algorithms = ["HS256"]
        elif alg in {"ES256", "RS256"}:
            # ES256/RS256: verify with JWKS public key
            jwks_client = _get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            key = signing_key.key
            algorithms = [alg]
        else:
            raise JWTError(f"Unsupported JWT algorithm: {alg}")

        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience="authenticated",
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError as e:
        raise JWTError("Token has expired") from e
    except jwt.InvalidAudienceError as e:
        raise JWTError("Invalid audience claim") from e
    except jwt.PyJWTError as e:
        raise JWTError(f"Invalid token: {e}") from e
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise JWTError(f"JWT verification failed: {e}") from e

    # Validate required 'sub' claim
    if "sub" not in payload:
        raise JWTError("Token missing 'sub' claim")

    return JWTPayload(
        sub=UUID(payload["sub"]),
        email=payload.get("email"),
        role=payload.get("role"),
        exp=payload.get("exp"),
    )
