"""Shared GitHub API utilities.

Common helpers used by github_repos, github_sync, and github_webhook services.
Centralised to avoid duplication and ensure consistent behaviour across
all GitHub integration code paths.
"""

import asyncio
import logging
import re
import time
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"

# GitHub API version header
GITHUB_API_VERSION = "2022-11-28"

# Bot accounts to filter (lowercased for consistent comparison)
BOT_ACCOUNTS: frozenset[str] = frozenset({
    "dependabot[bot]",
    "renovate[bot]",
    "github-actions[bot]",
})

# Rate limit threshold: pause when remaining < this value
RATE_LIMIT_THRESHOLD = 100


def github_headers(token: str) -> dict[str, str]:
    """Build standard GitHub API request headers.

    Uses Bearer auth as required by GitHub App installation access tokens.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def parse_link_next(link_header: str | None) -> str | None:
    """Parse the GitHub Link header to extract the 'next' page URL.

    GitHub uses RFC 5988 Link headers for pagination:
    <https://api.github.com/...?page=2>; rel="next", <...>; rel="last"

    Args:
        link_header: The raw Link header value.

    Returns:
        The URL for the next page, or None if no next page.
    """
    if not link_header:
        return None
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    return match.group(1) if match else None


def parse_github_timestamp(iso_str: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string to naive UTC datetime.

    GitHub returns timestamps like "2024-01-01T00:00:00Z".

    Args:
        iso_str: ISO 8601 datetime string or None.

    Returns:
        Naive UTC datetime, or None if input is None/empty.
    """
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)  # Naive UTC per project convention
    except (ValueError, AttributeError):
        return None


def is_bot_author(login: str) -> bool:
    """Check if the author login matches a known bot account.

    Uses case-insensitive comparison against the known bot set.
    """
    return login.lower() in BOT_ACCOUNTS


def map_pr_state(state: str, merged_at: str | None = None, *, merged: bool | None = None) -> str:
    """Map GitHub PR state to our model's state enum.

    Supports both sync (state + merged_at) and webhook (action + merged bool)
    patterns.

    Args:
        state: GitHub PR state or webhook action ('open', 'closed', 'reopened').
        merged_at: ISO timestamp if the PR was merged (sync path).
        merged: Boolean merged flag from webhook payload.

    Returns:
        One of 'open', 'closed', or 'merged'.
    """
    if state == "closed":
        if merged or merged_at:
            return "merged"
        return "closed"
    if state == "reopened":
        return "open"
    return state


def map_review_state(state: str) -> str:
    """Map GitHub review state to our model's state enum.

    GitHub review states: APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING.

    Args:
        state: GitHub review state string (uppercase from API).

    Returns:
        Lowercase state matching the DB check constraint.
    """
    state_map = {
        "APPROVED": "approved",
        "CHANGES_REQUESTED": "changes_requested",
        "COMMENTED": "commented",
        "DISMISSED": "dismissed",
        "PENDING": "commented",  # Treat pending as commented for storage
    }
    return state_map.get(state.upper(), "commented")


async def check_rate_limit(response: httpx.Response) -> None:
    """Check GitHub API rate limit headers and sleep if needed.

    Monitors X-RateLimit-Remaining and X-RateLimit-Reset headers.
    If remaining requests < RATE_LIMIT_THRESHOLD, sleeps until the
    reset timestamp.
    """
    remaining = response.headers.get("x-ratelimit-remaining")
    reset_at = response.headers.get("x-ratelimit-reset")

    if remaining is not None and int(remaining) < RATE_LIMIT_THRESHOLD:
        if reset_at:
            reset_timestamp = int(reset_at)
            wait_seconds = max(reset_timestamp - int(time.time()), 1)
            logger.warning(
                "GitHub rate limit low (%s remaining), sleeping %d seconds",
                remaining,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
