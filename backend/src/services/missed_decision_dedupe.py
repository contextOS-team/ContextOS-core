"""Layered dedupe and match classification for missed-decision candidates."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.graph_node import GraphNode
from src.models.missed_decision import MissedDecisionCandidate
from src.models.suggestion import Suggestion
from src.services.suggestions import (
    SUGGESTION_STATUS_OPEN,
    SUGGESTION_STATUS_RESOLVED,
    SUGGESTION_STATUS_SNOOZED,
)

MATCH_STRONG = "strong_match"
MATCH_WEAK = "weak_match"
MATCH_NONE = "no_match"

LIFECYCLE_DETECTED = "detected"
LIFECYCLE_SURFACED = "surfaced"
LIFECYCLE_SUPPRESSED = "suppressed"
LIFECYCLE_LINKED = "linked"
LIFECYCLE_CONFIRMED = "confirmed"
LIFECYCLE_DEFERRED = "deferred"

SUPPRESSION_ALREADY_BACKED_BY_ARTIFACT = "already_backed_by_artifact"
SUPPRESSION_DUPLICATE_EXISTING_DECISION = "duplicate_existing_decision"
SUPPRESSION_DUPLICATE_NO_NEW_EVIDENCE = SUPPRESSION_DUPLICATE_EXISTING_DECISION

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "be",
    "before",
    "by",
    "do",
    "for",
    "in",
    "is",
    "it",
    "keep",
    "must",
    "of",
    "on",
    "or",
    "our",
    "should",
    "so",
    "stay",
    "the",
    "to",
    "we",
    "will",
}


@dataclass(frozen=True)
class DedupeClassification:
    """Candidate match result used before suggestion publishing."""

    match_status: str
    lifecycle_status: str
    should_publish_suggestion: bool
    suppression_reason: str | None = None
    matched_entity_type: str | None = None
    matched_entity_id: UUID | None = None
    matched_title: str | None = None
    matched_href: str | None = None
    match_reason: str | None = None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(value.lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


def _token_signature(value: str) -> str:
    tokens = sorted(set(_tokens(value)))
    return " ".join(tokens) if tokens else " ".join(value.lower().split())


def quote_fingerprint(source_quote: str) -> str:
    """Fingerprint exact source quote material."""
    return _hash(" ".join(source_quote.lower().split()))


def decision_fingerprint(inferred_decision: str) -> str:
    """Fingerprint normalized decision meaning for close paraphrase matching."""
    return _hash(_token_signature(inferred_decision))


def _candidate_text(candidate: MissedDecisionCandidate) -> str:
    return " ".join(
        [
            candidate.inferred_decision,
            candidate.inferred_rationale,
            candidate.source_quote,
        ]
    )


def _node_text(node: GraphNode) -> str:
    props = node.properties or {}
    return " ".join(
        str(value)
        for value in [
            node.name,
            props.get("rationale"),
            props.get("source_quote"),
            props.get("description"),
            props.get("title"),
            props.get("jira"),
            props.get("pr"),
            props.get("mr"),
            props.get("identifier"),
            props.get("url"),
            props.get("source_link"),
            props.get("summary"),
        ]
        if value
    )


def _node_href(node: GraphNode) -> str | None:
    props = node.properties or {}
    if node.entity_type == "Decision":
        return f"/dashboard/decisions/{node.id}"
    for key in ("url", "html_url", "web_url", "source_link", "link"):
        value = props.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


async def _find_candidate_fingerprint_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[MissedDecisionCandidate]:
    stmt = select(MissedDecisionCandidate).where(
        MissedDecisionCandidate.workspace_id == candidate.workspace_id,
        MissedDecisionCandidate.deleted_at.is_(None),  # type: ignore[union-attr]
        or_(
            MissedDecisionCandidate.quote_fingerprint == candidate.quote_fingerprint,
            MissedDecisionCandidate.decision_fingerprint
            == candidate.decision_fingerprint,
        ),
    )
    result = await session.execute(stmt)
    matches = [
        match
        for match in result.scalars().all()
        if match.workspace_id == candidate.workspace_id
        and getattr(match, "id", None) != getattr(candidate, "id", None)
    ]
    return await _eligible_candidate_matches(session, candidate.workspace_id, matches)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _expired_deferred_suggestion_ids(
    session: AsyncSession,
    workspace_id: UUID,
    candidates: list[MissedDecisionCandidate],
) -> set[UUID]:
    suggestion_ids = [
        match.suggestion_id
        for match in candidates
        if match.lifecycle_status == LIFECYCLE_DEFERRED and match.suggestion_id
    ]
    if not suggestion_ids:
        return set()

    stmt = select(Suggestion.id).where(
        Suggestion.workspace_id == workspace_id,
        Suggestion.id.in_(suggestion_ids),  # type: ignore[attr-defined]
        Suggestion.status == SUGGESTION_STATUS_SNOOZED,
        Suggestion.snoozed_until <= _now(),  # type: ignore[operator]
        Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def _eligible_candidate_matches(
    session: AsyncSession,
    workspace_id: UUID,
    matches: list[MissedDecisionCandidate],
) -> list[MissedDecisionCandidate]:
    expired_suggestion_ids = await _expired_deferred_suggestion_ids(
        session,
        workspace_id,
        matches,
    )
    eligible: list[MissedDecisionCandidate] = []
    for match in matches:
        if match.lifecycle_status in {
            LIFECYCLE_DETECTED,
            LIFECYCLE_SURFACED,
            LIFECYCLE_CONFIRMED,
            LIFECYCLE_LINKED,
        }:
            eligible.append(match)
            continue
        if (
            match.lifecycle_status == LIFECYCLE_DEFERRED
            and match.suggestion_id in expired_suggestion_ids
        ):
            eligible.append(match)
    return eligible


async def _find_graph_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[GraphNode]:
    stmt = (
        select(GraphNode)
        .where(
            GraphNode.workspace_id == candidate.workspace_id,
            GraphNode.entity_type.in_(  # type: ignore[attr-defined]
                ["Decision", "Ticket", "PR", "NotionPage", "SlackThread"]
            ),
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(100)
    )
    result = await session.execute(stmt)
    return [
        node
        for node in result.scalars().all()
        if node.workspace_id == candidate.workspace_id
    ]


def _has_unresolved_source_reference(node: GraphNode) -> bool:
    props = node.properties or {}
    return (
        node.source_type == "messages_digest"
        and node.source_id is None
        and not props.get("source_link")
        and not props.get("source_id")
    )


def _classify_graph_node(
    candidate: MissedDecisionCandidate,
    node: GraphNode,
) -> DedupeClassification | None:
    node_text = _node_text(node)
    decision_overlap = _token_overlap(candidate.inferred_decision, node_text)
    full_overlap = _token_overlap(_candidate_text(candidate), node_text)
    same_fingerprint = (
        decision_fingerprint(candidate.inferred_decision)
        == decision_fingerprint(node.name)
    )

    if same_fingerprint or (decision_overlap >= 0.65 and full_overlap >= 0.35):
        return DedupeClassification(
            match_status=MATCH_STRONG,
            lifecycle_status=LIFECYCLE_LINKED,
            should_publish_suggestion=False,
            matched_entity_type="graph_node",
            matched_entity_id=node.id,
            matched_title=node.name,
            matched_href=_node_href(node),
            match_reason=(
                f"Strong {node.entity_type} match on decision wording "
                "and source context."
            ),
            suppression_reason=SUPPRESSION_ALREADY_BACKED_BY_ARTIFACT,
        )
    if decision_overlap >= 0.25 or full_overlap >= 0.25:
        return DedupeClassification(
            match_status=MATCH_WEAK,
            lifecycle_status=LIFECYCLE_DETECTED,
            should_publish_suggestion=True,
            matched_entity_type="graph_node",
            matched_entity_id=node.id,
            matched_title=node.name,
            matched_href=_node_href(node),
            match_reason=(
                f"Possible {node.entity_type} match based on overlapping source terms."
            ),
        )
    return None


def _suggestion_text(suggestion: Suggestion) -> str:
    details = suggestion.details or {}
    evidence = suggestion.evidence or {}
    return " ".join(
        str(value)
        for value in [
            suggestion.title,
            suggestion.body,
            details.get("decision_title"),
            details.get("candidate_title"),
            details.get("match_reason"),
            evidence.get("source_quote"),
        ]
        if value
    )


async def _find_suggestion_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[Suggestion]:
    stmt = (
        select(Suggestion)
        .where(
            Suggestion.workspace_id == candidate.workspace_id,
            Suggestion.status.in_(  # type: ignore[attr-defined]
                [SUGGESTION_STATUS_OPEN, SUGGESTION_STATUS_RESOLVED]
            ),
            Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    result = await session.execute(stmt)
    return [
        suggestion
        for suggestion in result.scalars().all()
        if suggestion.workspace_id == candidate.workspace_id
    ]


def _classify_suggestion(
    candidate: MissedDecisionCandidate,
    suggestion: Suggestion,
) -> DedupeClassification | None:
    suggestion_text = _suggestion_text(suggestion)
    decision_overlap = _token_overlap(candidate.inferred_decision, suggestion_text)
    full_overlap = _token_overlap(_candidate_text(candidate), suggestion_text)

    if decision_overlap >= 0.25 or full_overlap >= 0.25:
        return DedupeClassification(
            match_status=MATCH_WEAK,
            lifecycle_status=LIFECYCLE_DETECTED,
            should_publish_suggestion=True,
            matched_entity_type="suggestion",
            matched_entity_id=suggestion.id,
            matched_title=suggestion.title,
            matched_href=suggestion.action_href,
            match_reason="Possible match to an existing suggestion.",
        )
    return None


async def classify_missed_decision_candidate(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> DedupeClassification:
    """Classify duplicate, weak-match, and fresh candidates within a workspace."""
    for match in await _find_candidate_fingerprint_matches(session, candidate):
        if match.quote_fingerprint == candidate.quote_fingerprint:
            return DedupeClassification(
                match_status=MATCH_STRONG,
                lifecycle_status=LIFECYCLE_SUPPRESSED,
                should_publish_suggestion=False,
                suppression_reason=SUPPRESSION_DUPLICATE_NO_NEW_EVIDENCE,
                matched_entity_type="missed_decision_candidate",
                matched_entity_id=match.id,
                matched_title=match.inferred_decision,
                match_reason="Same source quote was already captured.",
            )
        return DedupeClassification(
            match_status=MATCH_STRONG,
            lifecycle_status=LIFECYCLE_LINKED,
            should_publish_suggestion=False,
            matched_entity_type="missed_decision_candidate",
            matched_entity_id=match.id,
            matched_title=match.inferred_decision,
            match_reason="Same decision fingerprint was already captured.",
        )

    weak: DedupeClassification | None = None
    for node in await _find_graph_matches(session, candidate):
        classification = _classify_graph_node(candidate, node)
        if classification is None:
            continue
        if classification.match_status == MATCH_STRONG:
            return classification
        weak = weak or classification

    if weak is not None:
        return weak

    for suggestion in await _find_suggestion_matches(session, candidate):
        classification = _classify_suggestion(candidate, suggestion)
        if classification is None:
            continue
        if classification.match_status == MATCH_STRONG:
            return classification
        weak = weak or classification

    if weak is not None:
        return weak

    return DedupeClassification(
        match_status=MATCH_NONE,
        lifecycle_status=LIFECYCLE_DETECTED,
        should_publish_suggestion=True,
    )
