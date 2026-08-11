"""Review actions and Decision Receipt promotion for missed-decision candidates."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from inspect import isawaitable
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.graph_node import GraphNode
from src.models.missed_decision import MissedDecisionCandidate
from src.models.suggestion import Suggestion
from src.services.audit import log_audit_event
from src.services.graph_ops import upsert_edge
from src.services.missed_decision_attribution import (
    candidate_author_name,
    candidate_people,
    candidate_source_channel,
    candidate_source_context,
    candidate_source_timestamp,
)
from src.services.missed_decision_autosave import AUTOSAVE_POLICY_VERSION
from src.services.missed_decision_dedupe import (
    SUPPRESSION_DUPLICATE_NO_NEW_EVIDENCE,
)
from src.services.suggestion_quality import NO_WRITE_BOUNDARY, SuggestionGroundingTrace
from src.services.suggestions import (
    SUGGESTION_STATUS_SNOOZED,
    resolve_suggestion,
    snooze_suggestion,
)

logger = logging.getLogger(__name__)

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
VISIBLE_ACTIONABILITY_STATUSES = {None, "actionable"}


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


async def _best_effort_evidence_edge(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    source_node_id: UUID,
    target_node_id: UUID,
    relationship_type: str,
    properties: dict,
) -> None:
    """Persist graph evidence edge without blocking the review action."""
    try:
        savepoint = session.begin_nested()
        if isawaitable(savepoint):
            savepoint = await savepoint
        async with savepoint:
            await upsert_edge(
                session=session,
                workspace_id=workspace_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relationship_type=relationship_type,
                properties=properties,
            )
    except Exception:
        logger.debug(
            "missed_decision_evidence_edge_failed workspace=%s node=%s relationship=%s",
            workspace_id,
            source_node_id,
            relationship_type,
            exc_info=True,
        )


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


def _record_system_action(
    candidate: MissedDecisionCandidate,
    *,
    action: str,
    policy_version: str,
) -> None:
    evidence = dict(candidate.evidence or {})
    actions = list(evidence.get("review_actions") or [])
    actions.append(
        {
            "action": action,
            "actor_type": "system",
            "autosave_policy_version": policy_version,
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
    now = _now()
    stmt = (
        select(MissedDecisionCandidate)
        .outerjoin(Suggestion, MissedDecisionCandidate.suggestion_id == Suggestion.id)
        .where(
            MissedDecisionCandidate.workspace_id == workspace_id,
            or_(
                MissedDecisionCandidate.lifecycle_status == LIFECYCLE_SURFACED,
                (
                    (MissedDecisionCandidate.lifecycle_status == LIFECYCLE_DEFERRED)
                    & (Suggestion.status == SUGGESTION_STATUS_SNOOZED)
                    & (Suggestion.snoozed_until <= now)  # type: ignore[operator]
                ),
            ),
            MissedDecisionCandidate.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(MissedDecisionCandidate.detected_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    result = await session.execute(stmt)
    candidates = [
        candidate
        for candidate in result.scalars().all()
        if candidate.workspace_id == workspace_id
        and _visible_actionability_status(candidate) in VISIBLE_ACTIONABILITY_STATUSES
    ]
    reopened = False
    for candidate in candidates:
        if candidate.lifecycle_status == LIFECYCLE_DEFERRED:
            candidate.lifecycle_status = LIFECYCLE_SURFACED
            candidate.surfaced_at = now
            reopened = True
    if reopened:
        await session.flush()
    return candidates


def _visible_actionability_status(candidate: MissedDecisionCandidate) -> str | None:
    evidence = candidate.evidence if isinstance(candidate.evidence, dict) else {}
    actionability = evidence.get("actionability")
    if not isinstance(actionability, dict):
        return None
    status = actionability.get("status")
    return status if isinstance(status, str) else None


def _decision_properties(
    candidate: MissedDecisionCandidate,
    *,
    autosave_policy_version: str | None = None,
) -> dict:
    people = candidate_people(candidate)
    author_name = candidate_author_name(candidate)
    source_channel = candidate_source_channel(candidate)
    source_context = candidate_source_context(candidate)
    source_timestamp = candidate_source_timestamp(candidate)
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
    evidence = candidate.evidence or {}
    actionability = evidence.get("actionability")
    if not isinstance(actionability, dict):
        actionability = None
    properties = {
        "description": candidate.inferred_decision,
        "rationale": candidate.inferred_rationale,
        "source_quote": candidate.source_quote,
        "source_link": candidate.source_link,
        "confidence": candidate.confidence,
        "author_name": author_name,
        "person_name": people[0] if people else None,
        "participants": people,
        "affected_systems": candidate.affected_systems or [],
        "candidate_id": str(candidate.id),
        "scan_run_id": str(candidate.scan_run_id) if candidate.scan_run_id else None,
        "source_type": candidate.source_type,
        "source_id": str(candidate.source_id),
        "source_channel": source_channel,
        "source_context": source_context,
        "date": source_timestamp,
        "action_hints": candidate.action_hints or [],
        "actionability": actionability,
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
            "actionability": actionability,
        },
        "status": "confirmed",
        "model": "missed_decision:v1",
    }
    if autosave_policy_version:
        properties["autosave_policy_version"] = autosave_policy_version
    return properties


async def promote_candidate_to_decision(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
    *,
    autosave_policy_version: str | None = None,
) -> UUID:
    """Promote a confirmed candidate through the canonical decision writer.

    gate_mode='report': this pipeline already gates consequentiality at
    extraction time, and confirmation (human click or autosave policy) is the
    authority here — the writer records its score but never rejects. Duplicate
    collapse stays active: confirming the same decision from a second source
    merges as evidence instead of duplicating.
    """
    from src.services.decision_writer import (
        DecisionDraft,
        EvidenceRef,
        create_decision,
    )

    result = await create_decision(
        session,
        candidate.workspace_id,
        DecisionDraft(
            statement=candidate.inferred_decision,
            rationale=candidate.inferred_rationale,
            producer="missed_decision",
            evidence=[
                EvidenceRef(
                    source_type=candidate.source_type,
                    source_id=candidate.source_id,
                    quote=candidate.source_quote,
                    source_link=candidate.source_link,
                )
            ],
            candidate_id=candidate.id,
        ),
        actor=(
            f"system:autosave:{autosave_policy_version}"
            if autosave_policy_version
            else "user:confirm"
        ),
        gate_mode="report",
        mirror_properties=_decision_properties(
            candidate,
            autosave_policy_version=autosave_policy_version,
        ),
    )
    decision_node_id = result.graph_node_id
    if decision_node_id is None:
        # Merged into a decision that has no mirror node (shouldn't happen —
        # every CREATE makes one). Fall back to the decision id so callers
        # still record a linkage.
        return result.decision_id
    source_node = await _find_source_graph_node(session, candidate, decision_node_id)
    if source_node is not None:
        await _best_effort_evidence_edge(
            session=session,
            workspace_id=candidate.workspace_id,
            source_node_id=source_node.id,
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


async def auto_confirm_candidate(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
    *,
    policy_version: str = AUTOSAVE_POLICY_VERSION,
) -> CandidateActionResult:
    """Confirm a safe candidate as Decision memory without creating review work."""
    decision_node_id = await promote_candidate_to_decision(
        session,
        candidate,
        autosave_policy_version=policy_version,
    )
    candidate.lifecycle_status = LIFECYCLE_CONFIRMED
    candidate.resolved_at = _now()
    candidate.matched_entity_type = "graph_node"
    candidate.matched_entity_id = decision_node_id
    _record_system_action(
        candidate,
        action="auto_confirm",
        policy_version=policy_version,
    )
    await log_audit_event(
        session,
        workspace_id=candidate.workspace_id,
        action="missed_decision.auto_confirm",
        user_id=None,
        resource_type="missed_decision_candidate",
        resource_id=candidate.id,
        details={
            "candidate_id": str(candidate.id),
            "decision_node_id": str(decision_node_id),
            "autosave_policy_version": policy_version,
            "source_type": candidate.source_type,
            "source_id": str(candidate.source_id),
        },
    )
    await session.flush()
    return CandidateActionResult(
        candidate=candidate,
        decision_node_id=decision_node_id,
    )


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


async def _find_source_graph_node(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
    target_node_id: UUID,
) -> GraphNode | None:
    stmt = (
        select(GraphNode)
        .where(
            GraphNode.workspace_id == candidate.workspace_id,
            GraphNode.source_type == candidate.source_type,
            GraphNode.source_id == candidate.source_id,
            GraphNode.id != target_node_id,
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    node = result.scalar_one_or_none()
    if isawaitable(node):
        node = await node
    if node is None or not isinstance(node, GraphNode):
        return None
    return node


async def add_candidate_as_evidence(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    candidate_id: UUID,
    *,
    target_decision_id: UUID | None = None,
) -> MissedDecisionCandidate:
    """Attach useful candidate source evidence to an existing graph Decision."""
    candidate = await _load_candidate(session, workspace_id, candidate_id)
    _ensure_actionable(candidate, "add_evidence")

    if candidate.match_status not in {"weak_match", "strong_match"}:
        raise InvalidCandidateTransitionError("Candidate has no existing match")
    if candidate.matched_entity_type != "graph_node":
        raise InvalidCandidateTransitionError("Candidate has no graph match")

    target_id = target_decision_id
    if target_id is None and candidate.match_status == "strong_match":
        target_id = candidate.matched_entity_id
    if target_id is None:
        raise InvalidCandidateTransitionError("Add evidence requires a target decision")

    node = await _load_graph_node(session, workspace_id, target_id)
    if node.entity_type != "Decision":
        raise InvalidCandidateTransitionError("Target must be a Decision node")
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

    source_node = await _find_source_graph_node(session, candidate, node.id)
    if source_node is not None:
        await _best_effort_evidence_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=source_node.id,
            target_node_id=node.id,
            relationship_type="has_evidence",
            properties=evidence[-1],
        )
    candidate.lifecycle_status = LIFECYCLE_LINKED
    candidate.resolved_at = _now()
    candidate.matched_entity_type = "graph_node"
    candidate.matched_entity_id = node.id
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
