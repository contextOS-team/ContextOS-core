"""Freshness policy for Graph RAG retrieval candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping

from src.services.graph_rag_types import FreshnessState, VerificationState


@dataclass(frozen=True)
class ProviderFreshnessPolicy:
    """Timestamp policy for one source family."""

    source_type: str
    timestamp_fields: tuple[str, ...]
    fresh_within_days: int
    stale_after_days: int
    source_originality: str


@dataclass(frozen=True)
class FreshnessAssessment:
    """Calculated freshness and provenance originality for one candidate."""

    freshness_state: FreshnessState
    source_timestamp: datetime | None
    freshness_age_days: float | None
    source_originality: str


PROVIDER_FRESHNESS_POLICIES: dict[str, ProviderFreshnessPolicy] = {
    "slack_message": ProviderFreshnessPolicy(
        "slack_message",
        ("slack_created_at", "created_at", "source_timestamp"),
        45,
        180,
        "source_of_record",
    ),
    "telegram_message": ProviderFreshnessPolicy(
        "telegram_message",
        ("telegram_date", "created_at", "source_timestamp"),
        45,
        180,
        "source_of_record",
    ),
    "notion_page": ProviderFreshnessPolicy(
        "notion_page",
        ("notion_updated_at", "updated_at", "notion_created_at", "created_at"),
        60,
        365,
        "source_of_record",
    ),
    "meeting_transcript": ProviderFreshnessPolicy(
        "meeting_transcript",
        ("meeting_date", "created_at", "source_timestamp"),
        90,
        365,
        "source_of_record",
    ),
    "meeting_segment": ProviderFreshnessPolicy(
        "meeting_segment",
        ("created_at", "source_timestamp"),
        90,
        365,
        "source_of_record",
    ),
    "github_pull_request": ProviderFreshnessPolicy(
        "github_pull_request",
        ("github_merged_at", "github_updated_at", "updated_at", "created_at"),
        90,
        365,
        "source_of_record",
    ),
    "github_review": ProviderFreshnessPolicy(
        "github_review",
        ("github_submitted_at", "updated_at", "created_at"),
        90,
        365,
        "source_of_record",
    ),
    "gitlab_merge_request": ProviderFreshnessPolicy(
        "gitlab_merge_request",
        ("gitlab_merged_at", "gitlab_updated_at", "updated_at", "created_at"),
        90,
        365,
        "source_of_record",
    ),
    "gitlab_review": ProviderFreshnessPolicy(
        "gitlab_review",
        ("gitlab_submitted_at", "updated_at", "created_at"),
        90,
        365,
        "source_of_record",
    ),
    "linear_ticket": ProviderFreshnessPolicy(
        "linear_ticket",
        ("linear_updated_at", "updated_at", "linear_created_at", "created_at"),
        60,
        365,
        "source_of_record",
    ),
    "linear_comment": ProviderFreshnessPolicy(
        "linear_comment",
        ("linear_updated_at", "updated_at", "linear_created_at", "created_at"),
        60,
        365,
        "source_of_record",
    ),
    "jira_issue": ProviderFreshnessPolicy(
        "jira_issue",
        ("jira_updated_at", "updated_at", "jira_created_at", "created_at"),
        60,
        365,
        "source_of_record",
    ),
    "jira_comment": ProviderFreshnessPolicy(
        "jira_comment",
        ("jira_updated_at", "updated_at", "jira_created_at", "created_at"),
        60,
        365,
        "source_of_record",
    ),
    "code_chunk": ProviderFreshnessPolicy(
        "code_chunk",
        ("updated_at", "created_at", "source_timestamp"),
        120,
        365,
        "indexed_source",
    ),
    "decision": ProviderFreshnessPolicy(
        "decision",
        ("source_timestamp", "updated_at", "created_at"),
        180,
        730,
        "source_of_record",
    ),
    "context_page": ProviderFreshnessPolicy(
        "context_page",
        ("generated_at", "updated_at", "created_at", "source_timestamp"),
        14,
        90,
        "generated_context",
    ),
}

DEFAULT_FRESHNESS_POLICY = ProviderFreshnessPolicy(
    "unknown",
    ("source_timestamp", "updated_at", "created_at"),
    60,
    365,
    "unknown",
)


def _coerce_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _pick_timestamp(
    timestamps: Mapping[str, object] | None,
    policy: ProviderFreshnessPolicy,
) -> datetime | None:
    if not timestamps:
        return None
    for field_name in policy.timestamp_fields:
        timestamp = _coerce_datetime(timestamps.get(field_name))
        if timestamp is not None:
            return timestamp
    return None


def calculate_freshness_state(
    source_type: str,
    timestamps: Mapping[str, object] | None = None,
    *,
    verification_state: VerificationState = VerificationState.UNKNOWN,
    generated_context: bool = False,
    now: datetime | None = None,
) -> FreshnessAssessment:
    """Calculate freshness without treating authority as recency."""
    policy = PROVIDER_FRESHNESS_POLICIES.get(source_type, DEFAULT_FRESHNESS_POLICY)
    timestamp = _pick_timestamp(timestamps, policy)
    originality = "generated_context" if generated_context else policy.source_originality

    if source_type == "context_page" or verification_state == VerificationState.GENERATED_CONTEXT:
        originality = "generated_context"

    if timestamp is None:
        return FreshnessAssessment(
            freshness_state=FreshnessState.UNKNOWN,
            source_timestamp=None,
            freshness_age_days=None,
            source_originality=originality,
        )

    current = now or datetime.now(UTC)
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    age_days = max(0.0, (current - timestamp).total_seconds() / 86_400)
    if age_days <= policy.fresh_within_days:
        state = FreshnessState.FRESH
    elif age_days >= policy.stale_after_days:
        state = FreshnessState.STALE
    else:
        state = FreshnessState.UNKNOWN

    return FreshnessAssessment(
        freshness_state=state,
        source_timestamp=timestamp,
        freshness_age_days=round(age_days, 2),
        source_originality=originality,
    )
