"""Agent-facing Decision Context API (v1, read-only).

Lets AI coding agents ask "what has this org decided?" before acting.
Authenticated by scoped API keys (not human JWTs). Deliberate differences from
the dashboard endpoints:
  - responses carry provenance (verification, confidence, consequentiality) so
    an agent can weigh unreviewed auto-saved decisions differently
  - decisions never disappear when a provider disconnects — this is a source of
    truth, not a per-integration view
Envelope: {"schema_version": "1", "data": ...}
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api_auth import MachinePrincipal, require_scope
from src.db import get_session
from src.models.decision import Decision, DecisionEdge, DecisionEvidence

router = APIRouter(prefix="/api/v1", tags=["decision-context-api"])

SCHEMA_VERSION = "1"
_READ = "decisions:read"


def _envelope(data: object) -> dict:
    return {"schema_version": SCHEMA_VERSION, "data": data}


def _verification(d: Decision) -> str:
    # Confirmed/human-promoted vs auto-saved-but-unreviewed. producer 'digest'
    # and 'llm_extractor' land without human review; missed_decision may be
    # human-confirmed. Tentative status = the gate degraded, treat as low-trust.
    if d.status == "tentative":
        return "unreviewed"
    if d.producer in ("manual", "missed_decision", "import"):
        return "reviewed"
    return "auto_saved"


def _decision_data(d: Decision, evidence_count: int | None = None) -> dict:
    out = {
        "id": str(d.id),
        "statement": d.statement,
        "rationale": d.rationale,
        "status": d.status,
        "valid_from": d.valid_from.isoformat() if d.valid_from else None,
        "valid_until": d.valid_until.isoformat() if d.valid_until else None,
        "confidence": d.confidence,
        "consequentiality_score": d.consequentiality_score,
        "verification": _verification(d),
    }
    if evidence_count is not None:
        out["evidence_count"] = evidence_count
    return out


@router.get("/decisions")
async def get_current_decisions(
    query: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=50, le=200),
    principal: MachinePrincipal = Depends(require_scope(_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Active decisions for the key's workspace. `query` does a trigram match
    over statements (best-effort relevance); omit it for the full active set."""
    stmt = (
        select(Decision, func.count(DecisionEvidence.id))
        .outerjoin(DecisionEvidence, DecisionEvidence.decision_id == Decision.id)
        .where(
            Decision.workspace_id == principal.workspace_id,
            Decision.status == "active",
            Decision.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(Decision.id)
        .order_by(Decision.valid_from.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    if query:
        stmt = stmt.where(func.similarity(Decision.statement, query) >= 0.1).order_by(
            func.similarity(Decision.statement, query).desc()
        )
    rows = (await session.execute(stmt)).all()
    return _envelope(
        {
            "decisions": [_decision_data(d, count) for d, count in rows],
            "count": len(rows),
        }
    )


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: UUID,
    principal: MachinePrincipal = Depends(require_scope(_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    d = await session.get(Decision, decision_id)
    if d is None or d.workspace_id != principal.workspace_id or d.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found"
        )
    evidence = (
        (
            await session.execute(
                select(DecisionEvidence)
                .where(DecisionEvidence.decision_id == decision_id)
                .order_by(DecisionEvidence.captured_at)  # type: ignore[arg-type]
            )
        )
        .scalars()
        .all()
    )
    edges = (
        (
            await session.execute(
                select(DecisionEdge).where(
                    (DecisionEdge.from_decision == decision_id)
                    | (DecisionEdge.to_decision == decision_id)
                )
            )
        )
        .scalars()
        .all()
    )
    return _envelope(
        {
            **_decision_data(d),
            "evidence": [
                {
                    "source_type": e.source_type,
                    "source_id": str(e.source_id),
                    "quote": e.quote,
                    "source_link": e.source_link,
                    "captured_at": e.captured_at.isoformat() if e.captured_at else None,
                }
                for e in evidence
            ],
            "relations": [
                {
                    "from_decision": str(e.from_decision),
                    "to_decision": str(e.to_decision),
                    "edge_type": e.edge_type,
                }
                for e in edges
            ],
        }
    )


@router.get("/constraints")
async def get_constraints(
    action: str = Query(max_length=500),
    limit: int = Query(default=10, le=50),
    principal: MachinePrincipal = Depends(require_scope(_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Active decisions most relevant to a proposed action — the read-only
    precursor to Decision Guard's check_action. Returns constraints to weigh,
    not a verdict."""
    stmt = (
        select(Decision)
        .where(
            Decision.workspace_id == principal.workspace_id,
            Decision.status == "active",
            Decision.deleted_at.is_(None),  # type: ignore[union-attr]
            func.similarity(Decision.statement, action) >= 0.1,
        )
        .order_by(func.similarity(Decision.statement, action).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return _envelope(
        {
            "action": action,
            "constraints": [_decision_data(d) for d in rows],
            "count": len(rows),
        }
    )
