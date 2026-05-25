"""Layered dedupe and match classification for missed-decision candidates."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.graph_node import GraphNode
from src.models.missed_decision import MissedDecisionCandidate

MATCH_STRONG = "strong_match"
MATCH_WEAK = "weak_match"
MATCH_NONE = "no_match"

LIFECYCLE_DETECTED = "detected"
LIFECYCLE_SUPPRESSED = "suppressed"
LIFECYCLE_LINKED = "linked"

SUPPRESSION_DUPLICATE_NO_NEW_EVIDENCE = "duplicate_no_new_evidence"

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
        ]
        if value
    )


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
    return [
        match
        for match in result.scalars().all()
        if match.workspace_id == candidate.workspace_id
        and getattr(match, "id", None) != getattr(candidate, "id", None)
    ]


async def _find_graph_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[GraphNode]:
    stmt = (
        select(GraphNode)
        .where(
            GraphNode.workspace_id == candidate.workspace_id,
            GraphNode.entity_type == "Decision",
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
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
            suppression_reason=(
                "raw_digest_existing_evidence"
                if _has_unresolved_source_reference(node)
                else None
            ),
        )
    if decision_overlap >= 0.25 or full_overlap >= 0.25:
        return DedupeClassification(
            match_status=MATCH_WEAK,
            lifecycle_status=LIFECYCLE_DETECTED,
            should_publish_suggestion=True,
            matched_entity_type="graph_node",
            matched_entity_id=node.id,
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
            )
        return DedupeClassification(
            match_status=MATCH_STRONG,
            lifecycle_status=LIFECYCLE_LINKED,
            should_publish_suggestion=False,
            matched_entity_type="missed_decision_candidate",
            matched_entity_id=match.id,
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

    return DedupeClassification(
        match_status=MATCH_NONE,
        lifecycle_status=LIFECYCLE_DETECTED,
        should_publish_suggestion=True,
    )
