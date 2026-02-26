"""Shared OAuth state parameter utilities.

Provides HMAC-SHA256 state signing and verification used by all OAuth
providers (Linear, Slack, GitHub). Extracted to eliminate code triplication.
"""

import hashlib
import hmac
from uuid import UUID


class OAuthStateError(ValueError):
    """Raised when OAuth state parameter is invalid or tampered."""


def sign_oauth_state(workspace_id: UUID, secret: str) -> str:
    """Create a signed state parameter encoding workspace_id.

    Uses HMAC-SHA256 to prevent CSRF. Format: {workspace_id}:{signature}

    Args:
        workspace_id: Workspace UUID to encode.
        secret: Client secret for HMAC signing.

    Returns:
        Signed state string: "{workspace_id}:{hmac_signature}"
    """
    message = str(workspace_id)
    signature = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{message}:{signature}"


def verify_oauth_state(state: str, secret: str) -> UUID:
    """Verify and extract workspace_id from a signed state parameter.

    Args:
        state: Signed state string from OAuth callback.
        secret: Client secret for HMAC verification.

    Returns:
        The extracted workspace UUID.

    Raises:
        OAuthStateError: If the state format or signature is invalid.
    """
    try:
        workspace_str, signature = state.rsplit(":", 1)
    except ValueError as e:
        raise OAuthStateError("Invalid state parameter format") from e

    expected = hmac.new(
        secret.encode(), workspace_str.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise OAuthStateError("Invalid state signature")

    return UUID(workspace_str)
