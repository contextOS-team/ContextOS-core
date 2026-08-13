"""Decision Drift endpoints: list drifts and drive the review lifecycle.

Lifecycle: detected -> confirmed -> owner_assigned -> resolved -> verified.
Feedback verdicts (confirmed/false_positive/…) are the eval training signal.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.decision import Decision
from src.models.decision_drift import (
    DRIFT_FEEDBACK_VERDICTS,
    DRIFT_RESOLUTION_TYPES,
    Drift,
    ExpectedConsequence,
)

router = APIRouter(prefix="/api/drifts", tags=["drifts"])

_OPEN = "open"
_RESOLVED = "resolved"


class ConfirmRequest(BaseModel):
    feedback_verdict: str | None = None


class ResolveRequest(BaseModel):
    resolution_type: str


def _lifecycle(d: Drift) -> str:
    if d.verified_at:
        return "verified"
    if d.resolved_at:
        return "resolved"
    if d.owner_assigned_at:
        return "owner_assigned"
    if d.confirmed_at:
        return "confirmed"
    return "detected"


def _payload(d: Drift, decision_statement: str | None = None) -> dict:
    return {
        "id": str(d.id),
        "decision_id": str(d.decision_id),
        "decision_statement": decision_statement,
        "summary": d.summary,
        "severity": d.severity,
        "lifecycle": _lifecycle(d),
        "feedback_verdict": d.feedback_verdict,
        "resolution_type": d.resolution_type,
        "detected_at": d.detected_at.isoformat() if d.detected_at else None,
        "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
        "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None,
        "verified_at": d.verified_at.isoformat() if d.verified_at else None,
        "verifier_verdict": d.verifier_verdict,
    }


async def _load(session: AsyncSession, user: UserContext, drift_id: UUID) -> Drift:
    drift = await session.get(Drift, drift_id)
    if drift is None or drift.workspace_id != user.workspace_id or drift.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Drift not found"
        )
    return drift


@router.get("")
async def list_drifts(
    state: str = Query(default="open"),  # open | resolved | all
    limit: int = Query(default=100, le=500),
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    query = (
        select(Drift, Decision.statement)
        .join(Decision, Decision.id == Drift.decision_id)
        .where(
            Drift.workspace_id == user.workspace_id,
            Drift.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(Drift.detected_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    if state == _OPEN:
        query = query.where(Drift.resolved_at.is_(None))  # type: ignore[union-attr]
    elif state == _RESOLVED:
        query = query.where(Drift.resolved_at.is_not(None))  # type: ignore[union-attr]
    rows = (await session.execute(query)).all()
    return {"drifts": [_payload(d, statement) for d, statement in rows]}


@router.get("/{drift_id}")
async def get_drift(
    drift_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    drift = await _load(session, user, drift_id)
    decision = await session.get(Decision, drift.decision_id)
    consequence = (
        await session.get(ExpectedConsequence, drift.expected_consequence_id)
        if drift.expected_consequence_id
        else None
    )
    return {
        **_payload(drift, decision.statement if decision else None),
        "decision_rationale": decision.rationale if decision else None,
        "expected_state": consequence.expected_state if consequence else None,
        "target_type": consequence.target_type if consequence else None,
    }


@router.post("/{drift_id}/confirm")
async def confirm_drift(
    drift_id: UUID,
    body: ConfirmRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.feedback_verdict and body.feedback_verdict not in DRIFT_FEEDBACK_VERDICTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid feedback_verdict: {body.feedback_verdict}",
        )
    drift = await _load(session, user, drift_id)
    drift.confirmed_at = drift.confirmed_at or datetime.now(UTC)
    drift.feedback_verdict = body.feedback_verdict or "confirmed"
    await session.commit()
    return _payload(drift)


@router.post("/{drift_id}/dismiss")
async def dismiss_drift(
    drift_id: UUID,
    body: ConfirmRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """False positive: record the verdict (eval signal) and close the drift."""
    verdict = body.feedback_verdict or "false_positive"
    if verdict not in DRIFT_FEEDBACK_VERDICTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid feedback_verdict: {verdict}",
        )
    drift = await _load(session, user, drift_id)
    drift.feedback_verdict = verdict
    drift.resolved_at = drift.resolved_at or datetime.now(UTC)
    await session.commit()
    return _payload(drift)


@router.post("/{drift_id}/assign")
async def assign_drift(
    drift_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    drift = await _load(session, user, drift_id)
    drift.owner_user_id = user.user_id
    drift.owner_assigned_at = datetime.now(UTC)
    if drift.confirmed_at is None:
        drift.confirmed_at = datetime.now(UTC)
    await session.commit()
    return _payload(drift)


@router.post("/{drift_id}/resolve")
async def resolve_drift(
    drift_id: UUID,
    body: ResolveRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.resolution_type not in DRIFT_RESOLUTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid resolution_type: {body.resolution_type}",
        )
    drift = await _load(session, user, drift_id)
    drift.resolution_type = body.resolution_type
    drift.resolved_at = datetime.now(UTC)
    if drift.confirmed_at is None:
        drift.confirmed_at = datetime.now(UTC)
    if drift.feedback_verdict is None:
        drift.feedback_verdict = "confirmed"
    await session.commit()
    return _payload(drift)


@router.post("/{drift_id}/verify")
async def verify_drift_resolution(
    drift_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    drift = await _load(session, user, drift_id)
    if drift.resolved_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot verify a drift that is not resolved",
        )
    drift.verified_at = datetime.now(UTC)
    await session.commit()
    return _payload(drift)
