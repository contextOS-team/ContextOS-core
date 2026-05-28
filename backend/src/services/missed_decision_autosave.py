"""Conservative auto-save policy for source-backed missed decisions."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from src.models.missed_decision import MissedDecisionCandidate
from src.services.missed_decision_dedupe import MATCH_NONE, DedupeClassification
from src.services.missed_decision_extractor import CONFIDENCE_VERY_HIGH

AUTOSAVE_POLICY_VERSION = "conservative_v1"

_RISK_TERMS = (
    "prod",
    "production",
    "database",
    "migration",
    "supabase",
    "secret",
    "api key",
    "auth",
    "security",
    "billing",
    "payment",
    "delete",
    "drop",
    "rollback",
    "incident",
    "outage",
    "compliance",
    "legal",
    "pii",
    "customer data",
    "gdpr",
    "hipaa",
)

_RISK_PATTERN = re.compile(
    "|".join(
        rf"(?<![a-z0-9]){re.escape(term).replace(r'\\ ', r'\\s+')}(?![a-z0-9])"
        for term in _RISK_TERMS
    ),
    re.IGNORECASE,
)

_SOURCE_HOSTS_BY_TYPE = {
    "slack_message": ("slack.com",),
    "telegram_message": ("t.me", "telegram.me"),
    "notion_page": ("notion.so", "notion.site"),
    "fathom_transcript": ("fathom.video",),
    "meeting_transcript": ("fathom.video",),
}


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: object) -> bool:
    return isinstance(value, list) and any(_non_empty_text(item) for item in value)


def _source_metadata(candidate: MissedDecisionCandidate) -> dict:
    evidence = candidate.evidence or {}
    metadata = evidence.get("source_metadata") if isinstance(evidence, dict) else None
    return metadata if isinstance(metadata, dict) else {}


def _valid_internal_source_reference(
    candidate: MissedDecisionCandidate,
    source_link: str,
) -> bool:
    parsed = urlparse(source_link)
    if parsed.path != "/dashboard/source-reference":
        return False
    params = parse_qs(parsed.query)
    required = {"source_type", "source_id", "workspace_id", "source_timestamp"}
    if not required.issubset(params):
        return False
    return (
        params["source_type"][0] == candidate.source_type
        and params["source_id"][0] == str(candidate.source_id)
        and params["workspace_id"][0] == str(candidate.workspace_id)
        and bool(params["source_timestamp"][0].strip())
    )


def _host_matches(host: str, allowed: tuple[str, ...]) -> bool:
    host = host.lower().strip()
    return any(
        host == expected or host.endswith(f".{expected}") for expected in allowed
    )


def _valid_provider_url(candidate: MissedDecisionCandidate, source_link: str) -> bool:
    parsed = urlparse(source_link)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    allowed_hosts = _SOURCE_HOSTS_BY_TYPE.get(candidate.source_type)
    if not allowed_hosts:
        return False
    return _host_matches(parsed.hostname or "", allowed_hosts)


def _has_resolvable_source_link(candidate: MissedDecisionCandidate) -> bool:
    source_link = candidate.source_link.strip() if candidate.source_link else ""
    if not source_link:
        return False
    return _valid_internal_source_reference(
        candidate,
        source_link,
    ) or _valid_provider_url(candidate, source_link)


def _has_attribution(candidate: MissedDecisionCandidate) -> bool:
    if _non_empty_list(candidate.people):
        return True
    metadata = _source_metadata(candidate)
    for key in (
        "user_name",
        "channel_name",
        "chat_title",
        "title",
        "provider_title",
        "source_context",
    ):
        if _non_empty_text(metadata.get(key)):
            return True
    return _non_empty_list(metadata.get("participants"))


def _has_risk_term(candidate: MissedDecisionCandidate) -> bool:
    text = " ".join(
        [
            candidate.source_quote or "",
            candidate.inferred_decision or "",
            candidate.inferred_rationale or "",
        ]
    )
    return bool(_RISK_PATTERN.search(text))


def should_auto_save_missed_decision(
    candidate: MissedDecisionCandidate,
    classification: DedupeClassification,
) -> bool:
    """Return whether a candidate is safe enough to become trusted memory.

    ``classification.should_publish_suggestion`` remains the upstream signal for
    "eligible to surface if not auto-saved"; auto-save only consumes the safest
    subset of that review-eligible queue.
    """
    return (
        candidate.confidence == CONFIDENCE_VERY_HIGH
        and classification.match_status == MATCH_NONE
        and classification.should_publish_suggestion is True
        and _non_empty_text(candidate.source_quote)
        and _non_empty_text(candidate.source_link)
        and _non_empty_text(candidate.inferred_decision)
        and _non_empty_text(candidate.inferred_rationale)
        and _has_resolvable_source_link(candidate)
        and _non_empty_list(candidate.affected_systems)
        and _has_attribution(candidate)
        and not _has_risk_term(candidate)
    )
