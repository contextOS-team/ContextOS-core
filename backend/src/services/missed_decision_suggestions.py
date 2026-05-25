"""Phase 44 suggestion adapter for missed-decision candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.missed_decision import MissedDecisionCandidate
from src.models.suggestion import Suggestion
from src.services.missed_decision_extractor import is_surfaceable_confidence
from src.services.suggestions import (
    SUGGESTION_STATUS_OPEN,
    SUGGESTION_STATUS_SNOOZED,
    SUGGESTION_TYPE_MISSED_DECISION,
)

MISSED_DECISION_SUGGESTION_GENERATOR = "missed_decision:v1"
MISSED_DECISION_PRIMARY_ACTION = "Review"
SUGGESTIONS_QUEUE_HREF = "/dashboard/suggestions"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(candidate: MissedDecisionCandidate) -> str:
    return (
        f"missed-decision:{candidate.decision_fingerprint}:"
        f"{candidate.quote_fingerprint}"
    )


def _title(candidate: MissedDecisionCandidate) -> str:
    decision = candidate.inferred_decision.strip()
    if len(decision) <= 90:
        return f"Review missed decision: {decision}"
    return f"Review missed decision: {decision[:87].rstrip()}..."


def _body(candidate: MissedDecisionCandidate) -> str:
    return candidate.inferred_rationale.strip()


def _candidate_id(candidate: MissedDecisionCandidate) -> UUID:
    return candidate.id


def build_missed_decision_suggestion(
    candidate: MissedDecisionCandidate,
) -> Suggestion | None:
    """Build a Phase 44 suggestion for an eligible persisted candidate."""
    if not isinstance(candidate, MissedDecisionCandidate):
        raise TypeError("missed-decision suggestions require persisted candidates")
    if not is_surfaceable_confidence(candidate.confidence):
        return None
    if candidate.lifecycle_status in {"suppressed", "linked"}:
        return None

    candidate_id = _candidate_id(candidate)
    return Suggestion(
        workspace_id=candidate.workspace_id,
        type=SUGGESTION_TYPE_MISSED_DECISION,
        status=SUGGESTION_STATUS_OPEN,
        priority="high" if candidate.confidence == "very_high" else "medium",
        fingerprint=_fingerprint(candidate),
        entity_type="missed_decision_candidate",
        entity_id=candidate_id,
        title=_title(candidate),
        body=_body(candidate),
        primary_action=MISSED_DECISION_PRIMARY_ACTION,
        action_href=SUGGESTIONS_QUEUE_HREF,
        evidence={
            "source_refs": [
                {
                    "type": candidate.source_type,
                    "id": str(candidate.source_id),
                    "link": candidate.source_link,
                }
            ],
            "source_quote": candidate.source_quote,
            "source_link": candidate.source_link,
        },
        details={
            "candidate_id": str(candidate_id),
            "confidence": candidate.confidence,
            "people": candidate.people or [],
            "affected_systems": candidate.affected_systems or [],
            "match_status": candidate.match_status,
            "action_hints": candidate.action_hints or [],
        },
        provenance={
            "generator": MISSED_DECISION_SUGGESTION_GENERATOR,
            "source": "missed_decision_candidate",
            "candidate_id": str(candidate_id),
            "quote_fingerprint": candidate.quote_fingerprint,
            "decision_fingerprint": candidate.decision_fingerprint,
        },
        last_seen_at=_now(),
    )


async def _find_existing_suggestion(
    session: AsyncSession,
    workspace_id: UUID,
    fingerprint: str,
) -> Suggestion | None:
    stmt = select(Suggestion).where(
        Suggestion.workspace_id == workspace_id,
        Suggestion.type == SUGGESTION_TYPE_MISSED_DECISION,
        Suggestion.fingerprint == fingerprint,
        Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def publish_missed_decision_suggestion(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> Suggestion | None:
    """Create or refresh a Phase 44 suggestion for an eligible candidate."""
    built = build_missed_decision_suggestion(candidate)
    if built is None:
        return None

    existing = await _find_existing_suggestion(
        session,
        candidate.workspace_id,
        built.fingerprint,
    )
    if existing is None:
        session.add(built)
        suggestion = built
    else:
        suggestion = existing
        if suggestion.status in {SUGGESTION_STATUS_OPEN, SUGGESTION_STATUS_SNOOZED}:
            suggestion.title = built.title
            suggestion.body = built.body
            suggestion.priority = built.priority
            suggestion.primary_action = built.primary_action
            suggestion.action_href = built.action_href
            suggestion.evidence = built.evidence
            suggestion.details = built.details
            suggestion.provenance = built.provenance
        suggestion.last_seen_at = _now()

    candidate.lifecycle_status = "surfaced"
    candidate.surfaced_at = _now()
    candidate.suggestion_id = suggestion.id
    await session.flush()
    return suggestion
