"""Canonical write path for Decision State.

THE ONLY module allowed to write decisions / decision_versions /
decision_evidence / decision_edges. Every producer (missed-decision promotion,
LLM extractor, digest, manual, import) routes through create_decision, which
enforces the two write-time quality gates:

1. Consequentiality gate — one structured LLM pass rejecting non-decisions
   (fixes ungated producers polluting the decision list).
2. Duplicate collapse — trigram retrieval over active decisions + one LLM
   confirm; a SAME match attaches evidence to the existing decision instead of
   creating a new row (fixes repeated-Slack-mention duplicates that
   fingerprint dedup cannot catch across rewordings).

Versioning: every change inserts an append-only decision_versions row with a
snapshot of the row BEFORE the change (version 1 snapshots the created row).

Sessions: this module flushes but never commits — callers own the transaction.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.decision import (
    DECISION_STATUSES,
    Decision,
    DecisionEdge,
    DecisionEvidence,
    DecisionVersion,
)
from src.services.graph_ops import upsert_node
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# ponytail: module constants, promote to Settings when a customer needs tuning
CONSEQUENTIALITY_MIN_SCORE = 0.6
DUPLICATE_SIMILARITY_MIN = 0.35
DUPLICATE_CANDIDATES_LIMIT = 5


@dataclass
class EvidenceRef:
    source_type: str
    source_id: UUID
    quote: str
    source_link: str | None = None


@dataclass
class DecisionDraft:
    statement: str
    rationale: str | None
    producer: str
    evidence: list[EvidenceRef] = field(default_factory=list)
    candidate_id: UUID | None = None
    confidence: float | None = None
    owner_node_id: UUID | None = None


class WriteOutcome(StrEnum):
    CREATED = "created"
    MERGED_AS_EVIDENCE = "merged_as_evidence"
    REJECTED_NOT_CONSEQUENTIAL = "rejected_not_consequential"


@dataclass
class WriteResult:
    outcome: WriteOutcome
    decision_id: UUID | None = None
    graph_node_id: UUID | None = None


class ConsequentialityVerdict(BaseModel):
    is_decision: bool
    consequential: bool
    score: float
    reason: str


class DuplicateVerdict(BaseModel):
    same_decision: bool
    confidence: float
    reason: str


_CONSEQUENTIALITY_SYSTEM = (
    "You are a strict filter for an engineering decision log. Given a candidate "
    "statement extracted from workplace communication, judge whether it records "
    "an actual, consequential engineering/organizational decision — something a "
    "CTO or engineering manager would want in the team's decision record. "
    "Status updates, opinions, questions, routine task assignments, and trivial "
    "choices are NOT consequential decisions. Score 0.0-1.0."
)

_DUPLICATE_SYSTEM = (
    "You compare two decision statements from the same engineering organization "
    "and judge whether they record the SAME decision (possibly reworded), as "
    "opposed to different decisions on a related topic."
)


async def _assess_consequentiality(
    draft: DecisionDraft, workspace_id: UUID
) -> ConsequentialityVerdict | None:
    """Returns None when the LLM call fails — caller degrades to 'tentative'."""
    prompt = (
        f"Candidate decision statement:\n{draft.statement}\n\n"
        f"Rationale (may be empty):\n{draft.rationale or '-'}\n\n"
        "Judge whether this is a consequential decision."
    )
    try:
        client = get_llm_client()
        return await client.generate_json(
            prompt,
            ConsequentialityVerdict,
            system_prompt=_CONSEQUENTIALITY_SYSTEM,
            workspace_id=workspace_id,
        )
    except Exception:
        logger.exception("consequentiality gate LLM call failed")
        return None


async def _find_similar_active(
    session: AsyncSession, workspace_id: UUID, statement: str
) -> list[tuple[UUID, str, float]]:
    """Trigram retrieval over active decisions.

    ponytail: trigram similarity; switch retrieval to embeddings/hybrid_search
    when reworded duplicates start slipping past it.
    """
    try:
        result = await session.execute(
            sa_text(
                """
                SELECT id, statement, similarity(statement, :q) AS sim
                FROM decisions
                WHERE workspace_id = :ws
                  AND deleted_at IS NULL
                  AND status = 'active'
                  AND similarity(statement, :q) >= :min_sim
                ORDER BY sim DESC
                LIMIT :lim
                """
            ),
            {
                "q": statement,
                "ws": str(workspace_id),
                "min_sim": DUPLICATE_SIMILARITY_MIN,
                "lim": DUPLICATE_CANDIDATES_LIMIT,
            },
        )
        return [(row[0], row[1], row[2]) for row in result.fetchall()]
    except Exception:
        # Fail open to CREATE: a missed merge is recoverable, a lost decision
        # is not. (Also keeps callers testable with mocked sessions.)
        logger.exception("duplicate retrieval failed; skipping collapse")
        return []


async def _confirm_duplicate(
    workspace_id: UUID, new_statement: str, existing_statement: str
) -> bool:
    client = get_llm_client()
    prompt = (
        f"Existing decision:\n{existing_statement}\n\n"
        f"New candidate:\n{new_statement}\n\n"
        "Are these the same decision?"
    )
    try:
        verdict = await client.generate_json(
            prompt,
            DuplicateVerdict,
            system_prompt=_DUPLICATE_SYSTEM,
            workspace_id=workspace_id,
        )
        return verdict.same_decision and verdict.confidence >= 0.7
    except Exception:
        logger.exception("duplicate confirm LLM call failed")
        # Fail open to CREATE: a duplicate is recoverable, a lost decision is not.
        return False


def _snapshot(decision: Decision) -> dict:
    return {
        "statement": decision.statement,
        "rationale": decision.rationale,
        "status": decision.status,
        "valid_from": decision.valid_from.isoformat() if decision.valid_from else None,
        "valid_until": (
            decision.valid_until.isoformat() if decision.valid_until else None
        ),
        "confidence": decision.confidence,
        "consequentiality_score": decision.consequentiality_score,
        "producer": decision.producer,
    }


async def _next_version(session: AsyncSession, decision_id: UUID) -> int:
    result = await session.execute(
        sa_text(
            "SELECT COALESCE(MAX(version), 0)"
            " FROM decision_versions WHERE decision_id = :d"
        ),
        {"d": str(decision_id)},
    )
    return int(result.scalar_one()) + 1


async def add_evidence(
    session: AsyncSession,
    workspace_id: UUID,
    decision_id: UUID,
    refs: list[EvidenceRef],
    actor: str,
) -> None:
    """Attach evidence rows (quotes frozen now) and record a version bump."""
    for ref in refs:
        session.add(
            DecisionEvidence(
                decision_id=decision_id,
                workspace_id=workspace_id,
                source_type=ref.source_type,
                source_id=ref.source_id,
                quote=ref.quote,
                source_link=ref.source_link,
                added_by=actor,
            )
        )
    decision = await session.get(Decision, decision_id)
    if decision is not None:
        session.add(
            DecisionVersion(
                decision_id=decision_id,
                workspace_id=workspace_id,
                version=await _next_version(session, decision_id),
                snapshot=_snapshot(decision),
                change_type="evidence_added",
                change_reason=f"{len(refs)} evidence ref(s) added",
                actor=actor,
            )
        )
    await session.flush()


async def create_decision(
    session: AsyncSession,
    workspace_id: UUID,
    draft: DecisionDraft,
    actor: str,
    # 'enforce' rejects below-threshold; 'report' scores but never rejects
    # (imports and human-confirmed candidates — a human click outranks the gate).
    gate_mode: str = "enforce",
    # Extra properties merged onto the graph mirror node. Producers pass their
    # legacy property payloads here so the existing dashboard keeps rendering
    # until the typed /api/decisions surface replaces it.
    mirror_properties: dict | None = None,
) -> WriteResult:
    """The single entry point for making a decision exist."""
    # Gate 1: consequentiality.
    verdict = await _assess_consequentiality(draft, workspace_id)
    status = "active"
    score: float | None = None
    if verdict is None:
        # LLM unavailable: keep data flowing but visibly lower-trust.
        status = "tentative"
    else:
        score = verdict.score
        is_consequential = (
            verdict.is_decision
            and verdict.consequential
            and verdict.score >= CONSEQUENTIALITY_MIN_SCORE
        )
        if not is_consequential and gate_mode == "enforce":
            logger.info(
                "decision rejected by consequentiality gate",
                extra={"producer": draft.producer, "reason": verdict.reason},
            )
            return WriteResult(WriteOutcome.REJECTED_NOT_CONSEQUENTIAL)

    # Gate 2: duplicate collapse.
    similar = await _find_similar_active(session, workspace_id, draft.statement)
    for existing_id, existing_statement, _sim in similar:
        if await _confirm_duplicate(workspace_id, draft.statement, existing_statement):
            await add_evidence(
                session, workspace_id, existing_id, draft.evidence, actor
            )
            existing = await session.get(Decision, existing_id)
            return WriteResult(
                WriteOutcome.MERGED_AS_EVIDENCE,
                existing_id,
                existing.graph_node_id if existing else None,
            )

    # Create: decision row + version 1 + evidence + graph mirror node.
    decision = Decision(
        workspace_id=workspace_id,
        statement=draft.statement,
        rationale=draft.rationale,
        status=status,
        confidence=draft.confidence,
        consequentiality_score=score,
        producer=draft.producer,
        created_from_candidate_id=draft.candidate_id,
        owner_node_id=draft.owner_node_id,
    )
    session.add(decision)
    await session.flush()

    session.add(
        DecisionVersion(
            decision_id=decision.id,
            workspace_id=workspace_id,
            version=1,
            snapshot=_snapshot(decision),
            change_type="imported" if draft.producer == "import" else "created",
            actor=actor,
        )
    )
    for ref in draft.evidence:
        session.add(
            DecisionEvidence(
                decision_id=decision.id,
                workspace_id=workspace_id,
                source_type=ref.source_type,
                source_id=ref.source_id,
                quote=ref.quote,
                source_link=ref.source_link,
                added_by=actor,
            )
        )

    first = draft.evidence[0] if draft.evidence else None
    node_id = await upsert_node(
        session,
        workspace_id,
        entity_type="Decision",
        external_id=f"decision:{decision.id}",
        name=draft.statement[:500],
        source_type=first.source_type if first else None,
        source_id=first.source_id if first else None,
        properties={
            **(mirror_properties or {}),
            "decision_id": str(decision.id),
            "status": status,
            "producer": draft.producer,
        },
    )
    decision.graph_node_id = node_id
    await session.flush()
    return WriteResult(WriteOutcome.CREATED, decision.id, node_id)


async def change_status(
    session: AsyncSession,
    workspace_id: UUID,
    decision_id: UUID,
    new_status: str,
    reason: str,
    actor: str,
    superseded_by: UUID | None = None,
) -> None:
    """Status transition with BEFORE-snapshot versioning and supersession edge."""
    if new_status not in DECISION_STATUSES:
        raise ValueError(f"invalid decision status: {new_status}")
    decision = await session.get(Decision, decision_id)
    if decision is None or decision.workspace_id != workspace_id:
        raise ValueError("decision not found in workspace")

    session.add(
        DecisionVersion(
            decision_id=decision_id,
            workspace_id=workspace_id,
            version=await _next_version(session, decision_id),
            snapshot=_snapshot(decision),
            change_type=(
                "superseded" if new_status == "superseded" else "status_changed"
            ),
            change_reason=reason,
            actor=actor,
        )
    )
    decision.status = new_status
    if new_status in ("superseded", "reversed"):
        decision.valid_until = datetime.now(UTC)
    if superseded_by is not None:
        session.add(
            DecisionEdge(
                workspace_id=workspace_id,
                from_decision=superseded_by,
                to_decision=decision_id,
                edge_type="supersedes",
                rationale=reason,
                actor=actor,
            )
        )
    # Keep the graph mirror in sync.
    if decision.graph_node_id is not None:
        await session.execute(
            sa_text(
                """
                UPDATE graph_nodes
                SET properties = properties
                    || jsonb_build_object('status', CAST(:s AS TEXT))
                WHERE id = :n AND workspace_id = :ws
                """
            ),
            {
                "s": new_status,
                "n": str(decision.graph_node_id),
                "ws": str(workspace_id),
            },
        )
    await session.flush()
