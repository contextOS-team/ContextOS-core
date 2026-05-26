"""Review actions and Decision Receipt promotion for missed-decision candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.graph_node import GraphNode
from src.models.missed_decision import MissedDecisionCandidate
from src.services.graph_ops import upsert_edge, upsert_node
from src.services.missed_decision_dedupe import (
    SUPPRESSION_DUPLICATE_NO_NEW_EVIDENCE,
)
from src.services.suggestion_quality import NO_WRITE_BOUNDARY, SuggestionGroundingTrace
from src.services.suggestions import resolve_suggestion, snooze_suggestion

LIFECYCLE_SURFACED = "surfaced"
LIFECYCLE_SUPPRESSED = "suppressed"
LIFECYCLE_LINKED = "linked"
LIFECYCLE_CONFIRMED = "confirmed"
LIFECYCLE_REJECTED = "rejected"
LIFECYCLE_DEFERRED = "deferred"

TERMINAL_LIFECYCLES = {
    LIFECYCLE_SUPPRESSED,
    LIFECYCLE_LINKED,
    LIFECYCLE_CONFIRMED,
    LIFECYCLE_REJECTED,
}
ACTIONABLE_LIFECYCLES = {LIFECYCLE_SURFACED, LIFECYCLE_DEFERRED}


class CandidateNotFoundError(Exception):
    """Raised when a candidate is not visible in the workspace."""


class InvalidCandidateTransitionError(Exception):
    """Raised when a lifecycle action is not legal for the candidate."""


@dataclass(frozen=True)
class CandidateActionResult:
    """Result from an action that may create or link an artifact."""

    candidate: MissedDecisionCandidate
    decision_node_id: UUID | None = None


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _load_candidate(
    session: AsyncSession,
    workspace_id: UUID,
    candidate_id: UUID,
) -> MissedDecisionCandidate:
    stmt = select(MissedDecisionCandidate).where(
        MissedDecisionCandidate.id == candidate_id,
        MissedDecisionCandidate.workspace_id == workspace_id,
        MissedDecisionCandidate.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise CandidateNotFoundError(str(candidate_id))
    return candidate


def _ensure_actionable(candidate: MissedDecisionCandidate, action: str) -> None:
    if candidate.lifecycle_status in TERMINAL_LIFECYCLES:
        raise InvalidCandidateTransitionError(
            f"Cannot {action} candidate in {candidate.lifecycle_status} state"
        )
    if candidate.lifecycle_status not in ACTIONABLE_LIFECYCLES:
        raise InvalidCandidateTransitionError(
            f"Cannot {action} candidate in {candidate.lifecycle_status} state"
        )


def _record_action(
    candidate: MissedDecisionCandidate,
    *,
    action: str,
    user_id: UUID,
    reason: str | None = None,
) -> None:
    evidence = dict(candidate.evidence or {})
    actions = list(evidence.get("review_actions") or [])
    actions.append(
        {
            "action": action,
            "actor_user_id": str(user_id),
            "reason": reason,
            "created_at": _now().isoformat(),
            "action_hints": candidate.action_hints or [],
        }
    )
    evidence["review_actions"] = actions
    candidate.evidence = evidence


async def _resolve_related_suggestion(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    if candidate.suggestion_id is None:
        return
    await resolve_suggestion(session, workspace_id, user_id, candidate.suggestion_id)


async def _snooze_related_suggestion(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
    workspace_id: UUID,
    user_id: UUID,
    snoozed_until: datetime,
) -> None:
    if candidate.suggestion_id is None:
        return
    await snooze_suggestion(
        session,
        workspace_id,
        user_id,
        candidate.suggestion_id,
        snoozed_until,
    )


async def list_review_candidates(
    session: AsyncSession,
    workspace_id: UUID,
    *,
    limit: int = 5,
) -> list[MissedDecisionCandidate]:
    """List open review candidates for the current workspace."""
    stmt = (
        select(MissedDecisionCandidate)
        .where(
            MissedDecisionCandidate.workspace_id == workspace_id,
            MissedDecisionCandidate.lifecycle_status == LIFECYCLE_SURFACED,
            MissedDecisionCandidate.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(MissedDecisionCandidate.detected_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [
        candidate
        for candidate in result.scalars().all()
        if candidate.workspace_id == workspace_id
    ]


def _decision_properties(candidate: MissedDecisionCandidate) -> dict:
    grounding = SuggestionGroundingTrace(
        source_type=candidate.source_type,
        source_id=str(candidate.source_id),
        source_link=candidate.source_link,
        source_quote=candidate.source_quote,
        retrieval_signals=["confirmed_missed_decision_candidate"],
        action_hints=candidate.action_hints or [],
        metadata={"candidate_id": str(candidate.id)},
    )
    action_hint_grounding = grounding.action_hint_grounding()
    return {
        "description": candidate.inferred_decision,
        "rationale": candidate.inferred_rationale,
        "source_quote": candidate.source_quote,
        "source_link": candidate.source_link,
        "confidence": candidate.confidence,
        "person_name": (candidate.people or [None])[0],
        "participants": candidate.people or [],
        "affected_systems": candidate.affected_systems or [],
        "candidate_id": str(candidate.id),
        "scan_run_id": str(candidate.scan_run_id) if candidate.scan_run_id else None,
        "source_type": candidate.source_type,
        "source_id": str(candidate.source_id),
        "action_hints": candidate.action_hints or [],
        "action_hint_grounding": action_hint_grounding,
        "grounding_explanation": {
            "selected_because": (
                "Confirmed missed-decision candidate preserves exact source evidence."
            ),
            "grounding_state": "source_backed_candidate",
            "candidate_id": str(candidate.id),
            "source_quote": candidate.source_quote,
            "source_link": candidate.source_link,
            "retrieval_signals": grounding.retrieval_signals,
            "no_write_boundary": NO_WRITE_BOUNDARY,
        },
        "status": "confirmed",
        "model": "missed_decision:v1",
    }


async def promote_candidate_to_decision(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> UUID:
    """Promote a confirmed candidate into source-backed Decision memory."""
    decision_node_id = await upsert_node(
        session=session,
        workspace_id=candidate.workspace_id,
        entity_type="Decision",
        external_id=f"missed_decision:{candidate.id}",
        name=candidate.inferred_decision,
        source_type=candidate.source_type,
        source_id=candidate.source_id,
        properties=_decision_properties(candidate),
    )
    await upsert_edge(
        session=session,
        workspace_id=candidate.workspace_id,
        source_node_id=decision_node_id,
        target_node_id=decision_node_id,
        relationship_type="evidenced_by",
        properties={
            "source_type": candidate.source_type,
            "source_id": str(candidate.source_id),
            "source_link": candidate.source_link,
            "source_quote": candidate.source_quote,
            "candidate_id": str(candidate.id),
        },
    )
    return decision_node_id


async def confirm_candidate(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    candidate_id: UUID,
) -> CandidateActionResult:
    """Confirm a surfaced candidate as trusted decision memory."""
    candidate = await _load_candidate(session, workspace_id, candidate_id)
    _ensure_actionable(candidate, "confirm")
    decision_node_id = await promote_candidate_to_decision(session, candidate)
    candidate.lifecycle_status = LIFECYCLE_CONFIRMED
    candidate.resolved_at = _now()
    candidate.matched_entity_type = "graph_node"
    candidate.matched_entity_id = decision_node_id
    _record_action(candidate, action="confirm", user_id=user_id)
    await _resolve_related_suggestion(session, candidate, workspace_id, user_id)
    await session.flush()
    return CandidateActionResult(
        candidate=candidate,
        decision_node_id=decision_node_id,
    )


async def reject_candidate(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    candidate_id: UUID,
    *,
    reason: str | None = None,
) -> MissedDecisionCandidate:
    """Reject a surfaced candidate and resolve its suggestion."""
    candidate = await _load_candidate(session, workspace_id, candidate_id)
    _ensure_actionable(candidate, "reject")
    candidate.lifecycle_status = LIFECYCLE_REJECTED
    candidate.resolved_at = _now()
    _record_action(candidate, action="reject", user_id=user_id, reason=reason)
    await _resolve_related_suggestion(session, candidate, workspace_id, user_id)
    await session.flush()
    return candidate


async def defer_candidate(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    candidate_id: UUID,
    *,
    snoozed_until: datetime | None = None,
) -> MissedDecisionCandidate:
    """Defer a candidate using the Phase 44 snooze semantics."""
    candidate = await _load_candidate(session, workspace_id, candidate_id)
    _ensure_actionable(candidate, "defer")
    candidate.lifecycle_status = LIFECYCLE_DEFERRED
    when = snoozed_until or (_now() + timedelta(days=7))
    _record_action(candidate, action="defer", user_id=user_id)
    await _snooze_related_suggestion(session, candidate, workspace_id, user_id, when)
    await session.flush()
    return candidate


async def _load_graph_node(
    session: AsyncSession,
    workspace_id: UUID,
    node_id: UUID,
) -> GraphNode:
    stmt = select(GraphNode).where(
        GraphNode.id == node_id,
        GraphNode.workspace_id == workspace_id,
        GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    node = result.scalar_one_or_none()
    if node is None:
        raise CandidateNotFoundError(str(node_id))
    return node


async def add_candidate_as_evidence(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    candidate_id: UUID,
) -> MissedDecisionCandidate:
    """Attach useful candidate source evidence to an existing graph Decision."""
    candidate = await _load_candidate(session, workspace_id, candidate_id)
    _ensure_actionable(candidate, "add_evidence")
    if candidate.matched_entity_type != "graph_node" or not candidate.matched_entity_id:
        raise InvalidCandidateTransitionError("Candidate has no graph match")

    node = await _load_graph_node(session, workspace_id, candidate.matched_entity_id)
    props = dict(node.properties or {})
    evidence = list(props.get("missed_decision_evidence") or [])
    evidence.append(
        {
            "candidate_id": str(candidate.id),
            "source_type": candidate.source_type,
            "source_id": str(candidate.source_id),
            "source_quote": candidate.source_quote,
            "source_link": candidate.source_link,
            "rationale": candidate.inferred_rationale,
            "confidence": candidate.confidence,
        }
    )
    props["missed_decision_evidence"] = evidence
    node.properties = props

    await upsert_edge(
        session=session,
        workspace_id=workspace_id,
        source_node_id=node.id,
        target_node_id=node.id,
        relationship_type="has_evidence",
        properties=evidence[-1],
    )
    candidate.lifecycle_status = LIFECYCLE_LINKED
    candidate.resolved_at = _now()
    _record_action(candidate, action="add_evidence", user_id=user_id)
    await _resolve_related_suggestion(session, candidate, workspace_id, user_id)
    await session.flush()
    return candidate


async def ignore_duplicate_candidate(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    candidate_id: UUID,
) -> MissedDecisionCandidate:
    """Ignore a duplicate candidate and resolve its suggestion."""
    candidate = await _load_candidate(session, workspace_id, candidate_id)
    _ensure_actionable(candidate, "ignore_duplicate")
    if candidate.match_status == "strong_match":
        candidate.lifecycle_status = LIFECYCLE_SUPPRESSED
        candidate.suppression_reason = SUPPRESSION_DUPLICATE_NO_NEW_EVIDENCE
    else:
        candidate.lifecycle_status = LIFECYCLE_REJECTED
    candidate.resolved_at = _now()
    _record_action(candidate, action="ignore_duplicate", user_id=user_id)
    await _resolve_related_suggestion(session, candidate, workspace_id, user_id)
    await session.flush()
    return candidate
