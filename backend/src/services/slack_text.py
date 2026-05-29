"""Slack text helpers for display-safe source rendering."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

_SLACK_USER_MENTION_RE = re.compile(r"<@([UW][A-Z0-9]{2,})(?:\|([^>]+))?>")
_SLACK_USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{2,}$")


def clean_slack_name(value: object) -> str | None:
    """Return a non-empty Slack display name, excluding raw user ids."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or is_slack_user_id(stripped):
        return None
    return stripped


def is_slack_user_id(value: object) -> bool:
    """Return True when a value looks like a Slack user id."""
    if not isinstance(value, str):
        return False
    return bool(_SLACK_USER_ID_RE.fullmatch(value.strip()))


def slack_user_ids_in_text(text: object) -> set[str]:
    """Extract Slack user ids from mention markup in text."""
    if not isinstance(text, str):
        return set()
    return {match.group(1) for match in _SLACK_USER_MENTION_RE.finditer(text)}


def slack_user_id_from_reference(value: object) -> str | None:
    """Extract a Slack user id from either raw `U...` or `<@U...>` text."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if is_slack_user_id(stripped):
        return stripped
    match = _SLACK_USER_MENTION_RE.fullmatch(stripped)
    return match.group(1) if match else None


def replace_slack_user_mentions(
    text: str,
    user_names: Mapping[str, str],
) -> str:
    """Replace Slack `<@U...>` mention markup with resolved display names."""

    def replace(match: re.Match[str]) -> str:
        user_id = match.group(1)
        fallback_label = clean_slack_name(match.group(2))
        return user_names.get(user_id) or fallback_label or match.group(0)

    return _SLACK_USER_MENTION_RE.sub(replace, text)


def render_slack_user_reference(
    value: str,
    user_names: Mapping[str, str],
) -> str:
    """Render raw Slack user references as names when a mapping is available."""
    user_id = slack_user_id_from_reference(value)
    if user_id:
        return user_names.get(user_id) or value
    return replace_slack_user_mentions(value, user_names)


async def resolve_slack_user_names(
    session: AsyncSession,
    workspace_id: UUID,
    user_ids: Iterable[str],
    *,
    token: str | None = None,
    known_user_names: Mapping[str, str | None] | None = None,
) -> dict[str, str]:
    """Resolve Slack user ids to display names, preserving known row metadata."""
    resolved: dict[str, str] = {}
    if known_user_names:
        for user_id, name in known_user_names.items():
            clean_name = clean_slack_name(name)
            if clean_name:
                resolved[user_id] = clean_name

    missing = sorted({
        user_id
        for user_id in user_ids
        if is_slack_user_id(user_id) and user_id not in resolved
    })
    if not missing:
        return resolved

    from src.services.slack_events import _resolve_user_name

    results = await asyncio.gather(
        *(
            _resolve_user_name(
                session,
                workspace_id,
                user_id,
                token=token,
            )
            for user_id in missing
        ),
        return_exceptions=True,
    )
    for user_id, result in zip(missing, results, strict=True):
        if isinstance(result, str):
            clean_name = clean_slack_name(result)
            if clean_name:
                resolved[user_id] = clean_name
    return resolved
