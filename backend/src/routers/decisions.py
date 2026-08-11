"""Decision State endpoints: typed decisions, versions, evidence, feedback.

Reads come from the typed `decisions` tables (source of truth), not from
graph-node properties. Status changes go through the canonical writer.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.decision import (
    DECISION_FEEDBACK_VERDICTS,
    DECISION_STATUSES,
    Decision,
    DecisionEdge,
    DecisionEvidence,
    DecisionFeedback,
    DecisionVersion,
)
from src.services.decision_writer import change_status

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


class FeedbackRequest(BaseModel):
    verdict: str
    note: str | None = None


class StatusChangeRequest(BaseModel):
    status: str
    reason: str


def _decision_payload(d: Decision, evidence_count: int | None = None) -> dict:
    return {
        "id": str(d.id),
        "statement": d.statement,
        "rationale": d.rationale,
        "status": d.status,
        "valid_from": d.valid_from.isoformat() if d.valid_from else None,
        "valid_until": d.valid_until.isoformat() if d.valid_until else None,
        "confidence": d.confidence,
        "consequentiality_score": d.consequentiality_score,
        "producer": d.producer,
        "graph_node_id": str(d.graph_node_id) if d.graph_node_id else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        **({"evidence_count": evidence_count} if evidence_count is not None else {}),
    }


@router.get("")
async def list_decisions(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if status_filter is not None and status_filter not in DECISION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid status filter: {status_filter}",
        )
    query = (
        select(Decision, func.count(DecisionEvidence.id))
        .outerjoin(DecisionEvidence, DecisionEvidence.decision_id == Decision.id)
        .where(
            Decision.workspace_id == user.workspace_id,
            Decision.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(Decision.id)
        .order_by(Decision.valid_from.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    if status_filter is not None:
        query = query.where(Decision.status == status_filter)
    rows = (await session.execute(query)).all()
    return {
        "decisions": [
            _decision_payload(d, evidence_count=count) for d, count in rows
        ]
    }


@router.get("/{decision_id}")
async def get_decision(
    decision_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    decision = await session.get(Decision, decision_id)
    if (
        decision is None
        or decision.workspace_id != user.workspace_id
        or decision.deleted_at is not None
    ):
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
    versions = (
        (
            await session.execute(
                select(DecisionVersion)
                .where(DecisionVersion.decision_id == decision_id)
                .order_by(DecisionVersion.version)
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
    return {
        **_decision_payload(decision),
        "evidence": [
            {
                "id": str(e.id),
                "source_type": e.source_type,
                "source_id": str(e.source_id),
                "quote": e.quote,
                "source_link": e.source_link,
                "captured_at": e.captured_at.isoformat() if e.captured_at else None,
                "added_by": e.added_by,
            }
            for e in evidence
        ],
        "versions": [
            {
                "version": v.version,
                "change_type": v.change_type,
                "change_reason": v.change_reason,
                "actor": v.actor,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "snapshot": v.snapshot,
            }
            for v in versions
        ],
        "edges": [
            {
                "from_decision": str(e.from_decision),
                "to_decision": str(e.to_decision),
                "edge_type": e.edge_type,
                "rationale": e.rationale,
            }
            for e in edges
        ],
    }


@router.post("/{decision_id}/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    decision_id: UUID,
    body: FeedbackRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.verdict not in DECISION_FEEDBACK_VERDICTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid verdict: {body.verdict}",
        )
    decision = await session.get(Decision, decision_id)
    if decision is None or decision.workspace_id != user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found"
        )
    session.add(
        DecisionFeedback(
            workspace_id=user.workspace_id,
            decision_id=decision_id,
            user_id=user.user_id,
            verdict=body.verdict,
            note=body.note,
        )
    )
    await session.commit()
    return {"status": "recorded", "verdict": body.verdict}


@router.post("/{decision_id}/status")
async def update_status(
    decision_id: UUID,
    body: StatusChangeRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.status not in DECISION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid status: {body.status}",
        )
    try:
        await change_status(
            session,
            user.workspace_id,
            decision_id,
            body.status,
            reason=body.reason,
            actor=f"user:{user.user_id}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    await session.commit()
    return {"status": body.status}
