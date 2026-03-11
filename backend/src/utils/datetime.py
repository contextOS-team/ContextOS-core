"""Shared datetime parsing utilities.

Provides datetime parsing helpers used across multiple services
and routers for consistent timestamp handling.
"""

from __future__ import annotations

from datetime import datetime


def parse_notion_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string from the Notion API.

    Notion returns timestamps like '2025-06-03T05:29:00.000Z'.
    asyncpg requires actual datetime objects, not raw strings.
    Returns naive UTC datetime for SQLModel compatibility.

    Args:
        value: ISO 8601 datetime string (e.g. '2025-06-03T05:29:00.000Z'),
               or None.

    Returns:
        Parsed naive datetime (UTC), or None if value is falsy.
    """
    if not value:
        return None
    # Replace only trailing 'Z' (Zulu time) with an explicit UTC offset
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).replace(tzinfo=None)
