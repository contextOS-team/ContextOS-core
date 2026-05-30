"""Phase 44 suggestion adapter for missed-decision candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.missed_decision import MissedDecisionCandidate
from src.models.suggestion import Suggestion
from src.services.missed_decision_attribution import candidate_people
from src.services.missed_decision_extractor import is_surfaceable_confidence
from src.services.suggestion_quality import (
    NO_WRITE_BOUNDARY,
    SuggestionFamily,
    SuggestionGroundingTrace,
    assess_suggestion_family,
)
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


def _actionability(candidate: MissedDecisionCandidate) -> dict | None:
    evidence = candidate.evidence or {}
    value = evidence.get("actionability")
    return dict(value) if isinstance(value, dict) else None


def _draft_action(candidate: MissedDecisionCandidate) -> dict | None:
    actionability = _actionability(candidate)
    if actionability:
        next_action = actionability.get("next_action")
        if isinstance(next_action, dict):
            return dict(next_action)
    hints = candidate.action_hints or []
    if hints and isinstance(hints[0], dict):
        return dict(hints[0])
    return None


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
    grounding = SuggestionGroundingTrace(
        source_type=candidate.source_type,
        source_id=str(candidate.source_id),
        source_link=candidate.source_link,
        source_quote=candidate.source_quote,
        retrieval_signals=["missed_decision_candidate"],
        action_hints=candidate.action_hints or [],
        metadata={"candidate_id": str(candidate_id)},
    )
    required_evidence = ["source_ref", "source_link", "source_quote"]
    if candidate.action_hints:
        required_evidence.append("action_hint_grounding")
    assessment = assess_suggestion_family(
        family=SuggestionFamily.MISSED_DECISION,
        grounding=grounding,
        reason="Source-backed missed-decision candidate is ready for review.",
        confidence=1.0 if candidate.confidence == "very_high" else 0.85,
        required_evidence=required_evidence,
    )
    if not assessment.should_surface:
        return None
    action_hint_grounding = grounding.action_hint_grounding()
    provenance = {
        "generator": MISSED_DECISION_SUGGESTION_GENERATOR,
        "source": "missed_decision_candidate",
        "candidate_id": str(candidate_id),
        "quote_fingerprint": candidate.quote_fingerprint,
        "decision_fingerprint": candidate.decision_fingerprint,
        "retrieval_signals": grounding.retrieval_signals,
        "source_link": candidate.source_link,
        "source_quote": candidate.source_quote,
        "quality_gate": assessment.quality_gate(),
    }
    if action_hint_grounding:
        provenance["no_write_boundary"] = NO_WRITE_BOUNDARY
    actionability = _actionability(candidate)
    draft_action = _draft_action(candidate)
    if actionability:
        provenance["actionability"] = actionability

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
            "people": candidate_people(candidate),
            "affected_systems": candidate.affected_systems or [],
            "match_status": candidate.match_status,
            "actionability": actionability,
            "draft_action": draft_action,
            "draft_title": (
                draft_action.get("title") if isinstance(draft_action, dict) else None
            ),
            "draft_body": (
                draft_action.get("body") if isinstance(draft_action, dict) else None
            ),
            "action_hints": candidate.action_hints or [],
            "action_hint_grounding": action_hint_grounding,
            "explanation": assessment.explanation(),
        },
        provenance=provenance,
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
        await session.flush()
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
