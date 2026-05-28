"""Attribution helpers for missed-decision candidates."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from src.models.missed_decision import MissedDecisionCandidate


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _clean_strings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = _clean_string(value)
        if text is None or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def candidate_source_metadata(candidate: MissedDecisionCandidate) -> dict:
    """Return extraction-time source metadata in a normalized dict shape."""
    evidence = candidate.evidence if isinstance(candidate.evidence, dict) else {}
    metadata = evidence.get("source_metadata")
    return metadata if isinstance(metadata, dict) else {}


def candidate_author_name(candidate: MissedDecisionCandidate) -> str | None:
    """Best available human who authored the source line or candidate."""
    metadata = candidate_source_metadata(candidate)
    for key in ("user_name", "from_first_name", "from_username"):
        value = _clean_string(metadata.get(key))
        if value:
            return value
    people = candidate_people(candidate)
    return people[0] if people else None


def candidate_people(candidate: MissedDecisionCandidate) -> list[str]:
    """People to display for a candidate without fabricating from document titles."""
    people = _clean_strings(candidate.people)
    if people:
        return people

    metadata = candidate_source_metadata(candidate)
    participants = _clean_strings(metadata.get("participants"))
    if participants:
        return participants

    for key in ("user_name", "from_first_name", "from_username"):
        value = _clean_string(metadata.get(key))
        if value:
            return [value]

    return []


def candidate_source_context(candidate: MissedDecisionCandidate) -> str | None:
    """Human-readable source container, such as a Telegram chat or Notion title."""
    metadata = candidate_source_metadata(candidate)
    for key in ("channel_name", "chat_title", "title", "source_context"):
        value = _clean_string(metadata.get(key))
        if value:
            return value
    return None


def candidate_source_channel(candidate: MissedDecisionCandidate) -> str | None:
    """Slack channel-style source context used by existing dashboard formatting."""
    metadata = candidate_source_metadata(candidate)
    return _clean_string(metadata.get("channel_name"))


def candidate_source_timestamp(candidate: MissedDecisionCandidate) -> str | None:
    """Extract the structural source timestamp encoded in dashboard links."""
    parsed = urlparse(candidate.source_link or "")
    values = parse_qs(parsed.query).get("source_timestamp") or []
    return _clean_string(values[0]) if values else None
