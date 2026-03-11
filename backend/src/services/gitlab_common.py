"""Shared GitLab API utilities.

Common helpers used by gitlab_repos, gitlab_sync, and gitlab_webhook services.
Centralised to avoid duplication and ensure consistent behaviour across
all GitLab integration code paths.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import OAuthToken, Provider
from src.services.oauth_common import TOKEN_REFRESH_BUFFER
from src.services.vault import read_token, store_token, token_name

logger = logging.getLogger(__name__)

# GitLab API endpoints
GITLAB_API_BASE = "https://gitlab.com/api/v4"
GITLAB_AUTH_URL = "https://gitlab.com/oauth/authorize"
GITLAB_TOKEN_URL = "https://gitlab.com/oauth/token"


class GitLabOAuthError(Exception):
    """Raised when a GitLab OAuth operation fails."""


def gitlab_headers(token: str) -> dict[str, str]:
    """Build standard GitLab API request headers.

    Uses Bearer auth as required by GitLab OAuth2 tokens.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def parse_link_next(link_header: str | None) -> str | None:
    """Parse the GitLab Link header to extract the 'next' page URL.

    GitLab uses RFC 5988 Link headers for pagination, same format as GitHub.

    Args:
        link_header: The raw Link header value.

    Returns:
        The URL for the next page, or None if no next page.
    """
    if not link_header:
        return None
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    return match.group(1) if match else None


def parse_gitlab_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string to naive UTC datetime.

    GitLab returns timestamps like "2024-01-01T00:00:00.000Z".

    Args:
        ts: ISO 8601 datetime string or None.

    Returns:
        Naive UTC datetime, or None if input is None/empty.
    """
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)  # Naive UTC per project convention
    except (ValueError, AttributeError):
        return None


def is_bot_user(user_data: dict) -> bool:
    """Check if a GitLab user is a bot account.

    Checks the ``bot`` field (present on full user objects from /user endpoint),
    then falls back to username pattern matching for project access tokens
    (``project_*_bot``) and other bot accounts (``*_bot``, ``*[bot]``).

    Args:
        user_data: GitLab user dict from the API or webhook payload.

    Returns:
        True if the user is a bot.
    """
    if user_data.get("bot", False):
        return True
    username = user_data.get("username", "")
    if not username:
        return False
    return (
        username.endswith("_bot")
        or username.endswith("[bot]")
        or re.match(r"^project_\d+_bot\d*$", username) is not None
    )


def map_mr_state(gitlab_state: str) -> str:
    """Map GitLab MR state to our model's state enum.

    GitLab MR states: opened, closed, merged, locked.

    Args:
        gitlab_state: GitLab merge request state string.

    Returns:
        One of 'open', 'closed', or 'merged'.
    """
    state_map = {
        "opened": "open",
        "closed": "closed",
        "merged": "merged",
        "locked": "closed",
    }
    return state_map.get(gitlab_state, "open")


async def ensure_valid_token(
    session: AsyncSession,
    workspace_id,
    settings,
) -> str:
    """Get a valid GitLab access token, refreshing if expired.

    GitLab OAuth2 access tokens expire after 2 hours. This function
    reads the current token from Vault, checks expiry, and refreshes
    if needed using the refresh token.

    Args:
        workspace_id: Workspace to get the token for.
        session: Async database session.
        settings: Application settings.

    Returns:
        A valid access token string.

    Raises:
        GitLabOAuthError: If no token exists or refresh fails.
    """
    from uuid import UUID

    wid = workspace_id if isinstance(workspace_id, UUID) else UUID(str(workspace_id))

    # Find the OAuthToken record
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == wid,
        OAuthToken.provider == Provider.GITLAB,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise GitLabOAuthError("No GitLab integration found for this workspace")

    # Check if token is still valid (with 5 min buffer)
    if oauth_token.token_expires_at:
        expires_at = oauth_token.token_expires_at
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expires_at > (now_utc + TOKEN_REFRESH_BUFFER):
            # Token still valid, read from Vault
            access_name = token_name(Provider.GITLAB, wid, "access_token")
            current_token = await read_token(session, access_name)
            if current_token:
                return current_token

    # Token expired or expiring soon -- refresh using refresh_token
    refresh_name = token_name(Provider.GITLAB, wid, "refresh_token")
    refresh_token_value = await read_token(session, refresh_name)

    if not refresh_token_value:
        raise GitLabOAuthError("No refresh token found -- reconnect GitLab")

    # Exchange refresh token for new access token
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GITLAB_TOKEN_URL,
            data={
                "client_id": settings.GITLAB_CLIENT_ID,
                "client_secret": settings.GITLAB_CLIENT_SECRET,
                "refresh_token": refresh_token_value,
                "grant_type": "refresh_token",
                "redirect_uri": settings.gitlab_redirect_uri,
            },
        )

    if response.status_code != 200:
        raise GitLabOAuthError(
            f"Failed to refresh GitLab token: {response.status_code} {response.text}"
        )

    token_data = response.json()
    new_access = token_data["access_token"]
    new_refresh = token_data.get("refresh_token", refresh_token_value)
    expires_in = token_data.get("expires_in", 7200)  # Default 2 hours

    token_expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(seconds=expires_in)
    )

    # Store new tokens in Vault
    access_name = token_name(Provider.GITLAB, wid, "access_token")
    await store_token(session, access_name, new_access)
    await store_token(session, refresh_name, new_refresh)

    # Update expiry in DB
    oauth_token.token_expires_at = token_expires_at
    await session.flush()

    return new_access
