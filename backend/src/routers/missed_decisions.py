"""Missed-decision review endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.missed_decision import MissedDecisionCandidate, MissedDecisionScanRun
from src.services.missed_decision_actions import (
    CandidateActionResult,
    CandidateNotFoundError,
    InvalidCandidateTransitionError,
    add_candidate_as_evidence,
    confirm_candidate,
    defer_candidate,
    ignore_duplicate_candidate,
    list_review_candidates,
    reject_candidate,
)
from src.services.missed_decision_attribution import (
    candidate_author_name,
    candidate_people,
    candidate_source_channel,
    candidate_source_context,
)

router = APIRouter(prefix="/api/missed-decisions", tags=["missed-decisions"])


class DeferCandidateRequest(BaseModel):
    """Optional body for deferring a candidate."""

    snoozed_until: datetime | None = None


class RejectCandidateRequest(BaseModel):
    """Optional body for rejecting a candidate."""

    reason: str | None = None


class MissedDecisionScanStatus(BaseModel):
    """Dashboard-safe missed-decision scan progress payload."""

    id: str
    source_type: str
    status: str
    sources_scanned: int
    sources_total: int | None
    progress_percent: int | None
    candidates_created: int
    started_at: str | None
    completed_at: str | None
    error_message: str | None


def _legal_actions(candidate: MissedDecisionCandidate) -> list[str]:
    if candidate.lifecycle_status != "surfaced":
        return []
    actions = ["confirm", "defer", "reject"]
    if candidate.match_status in {"weak_match", "strong_match"}:
        actions.append("add_evidence")
        actions.append("ignore_duplicate")
    return actions


def _serialize_candidate(candidate: MissedDecisionCandidate) -> dict:
    return {
        "id": str(candidate.id),
        "workspace_id": str(candidate.workspace_id),
        "status": candidate.lifecycle_status,
        "suggestion_id": (
            str(candidate.suggestion_id) if candidate.suggestion_id else None
        ),
        "title": candidate.inferred_decision,
        "inferred_decision": candidate.inferred_decision,
        "inferred_rationale": candidate.inferred_rationale,
        "source_quote": candidate.source_quote,
        "source_link": candidate.source_link,
        "confidence": candidate.confidence,
        "people": candidate_people(candidate),
        "author_name": candidate_author_name(candidate),
        "source_channel": candidate_source_channel(candidate),
        "source_context": candidate_source_context(candidate),
        "affected_systems": candidate.affected_systems or [],
        "possible_existing_match": {
            "match_status": candidate.match_status,
            "entity_type": candidate.matched_entity_type,
            "entity_id": (
                str(candidate.matched_entity_id)
                if candidate.matched_entity_id
                else None
            ),
        },
        "legal_actions": _legal_actions(candidate),
    }


def _serialize_action_result(
    result: MissedDecisionCandidate | CandidateActionResult,
) -> dict:
    if isinstance(result, CandidateActionResult):
        payload = _serialize_candidate(result.candidate)
        payload["decision_node_id"] = (
            str(result.decision_node_id) if result.decision_node_id else None
        )
        return payload
    return _serialize_candidate(result)


def _iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _progress_percent(scan_run: MissedDecisionScanRun) -> int | None:
    total = scan_run.sources_total
    if total is None or total <= 0:
        return None
    scanned = max(0, scan_run.sources_scanned)
    return max(0, min(100, round((scanned / total) * 100)))


def _serialize_scan_status(scan_run: MissedDecisionScanRun) -> dict:
    return {
        "id": str(scan_run.id),
        "source_type": scan_run.source_type,
        "status": scan_run.status,
        "sources_scanned": scan_run.sources_scanned,
        "sources_total": scan_run.sources_total,
        "progress_percent": _progress_percent(scan_run),
        "candidates_created": scan_run.candidates_created,
        "started_at": _iso_timestamp(scan_run.started_at),
        "completed_at": _iso_timestamp(scan_run.completed_at),
        "error_message": scan_run.error_message,
    }


async def _translate_errors(coro):
    try:
        return await coro
    except CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        ) from exc
    except InvalidCandidateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/review")
async def review(
    limit: int = Query(default=5, ge=1, le=20),
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List workspace-scoped missed-decision candidates needing review."""
    candidates = await list_review_candidates(session, user.workspace_id, limit=limit)
    return [_serialize_candidate(candidate) for candidate in candidates]


@router.get("/scans", response_model=list[MissedDecisionScanStatus])
async def scans(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return latest active or recently completed missed-decision scans."""
    recent_cutoff = datetime.now(UTC) - timedelta(minutes=10)
    stmt = (
        select(MissedDecisionScanRun)
        .where(
            MissedDecisionScanRun.workspace_id == user.workspace_id,
            MissedDecisionScanRun.deleted_at.is_(None),  # type: ignore[union-attr]
            or_(
                MissedDecisionScanRun.status.in_(  # type: ignore[attr-defined]
                    ["queued", "running"]
                ),
                and_(
                    MissedDecisionScanRun.status == "failed",
                    MissedDecisionScanRun.completed_at.is_not(None),  # type: ignore[union-attr]
                    MissedDecisionScanRun.completed_at >= recent_cutoff,  # type: ignore[operator]
                ),
                and_(
                    MissedDecisionScanRun.status == "succeeded",
                    MissedDecisionScanRun.completed_at.is_not(None),  # type: ignore[union-attr]
                    MissedDecisionScanRun.completed_at >= recent_cutoff,  # type: ignore[operator]
                ),
            ),
        )
        .order_by(
            MissedDecisionScanRun.source_type.asc(),  # type: ignore[union-attr]
            MissedDecisionScanRun.created_at.desc(),  # type: ignore[union-attr]
        )
    )
    result = await session.execute(stmt)
    seen_sources: set[str] = set()
    latest: list[MissedDecisionScanRun] = []
    for run in result.scalars().all():
        if run.workspace_id != user.workspace_id:
            continue
        if run.status in {"failed", "succeeded"}:
            completed_at = run.completed_at
            if completed_at is None:
                continue
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=UTC)
            if completed_at < recent_cutoff:
                continue
        if run.source_type in seen_sources:
            continue
        seen_sources.add(run.source_type)
        latest.append(run)
    return [_serialize_scan_status(scan_run) for scan_run in latest]


@router.post("/{candidate_id}/confirm")
async def confirm(
    candidate_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Confirm a candidate as a source-backed Decision."""
    result = await _translate_errors(
        confirm_candidate(session, user.workspace_id, user.user_id, candidate_id)
    )
    await session.commit()
    return _serialize_action_result(result)


@router.post("/{candidate_id}/add-evidence")
async def add_evidence(
    candidate_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Attach candidate source evidence to an existing Decision/artifact."""
    result = await _translate_errors(
        add_candidate_as_evidence(
            session,
            user.workspace_id,
            user.user_id,
            candidate_id,
        )
    )
    await session.commit()
    return _serialize_action_result(result)


@router.post("/{candidate_id}/defer")
async def defer(
    candidate_id: UUID,
    body: DeferCandidateRequest | None = None,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Defer a candidate through suggestion snooze semantics."""
    result = await _translate_errors(
        defer_candidate(
            session,
            user.workspace_id,
            user.user_id,
            candidate_id,
            snoozed_until=body.snoozed_until if body else None,
        )
    )
    await session.commit()
    return _serialize_action_result(result)


@router.post("/{candidate_id}/reject")
async def reject(
    candidate_id: UUID,
    body: RejectCandidateRequest | None = None,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reject a candidate."""
    result = await _translate_errors(
        reject_candidate(
            session,
            user.workspace_id,
            user.user_id,
            candidate_id,
            reason=body.reason if body else None,
        )
    )
    await session.commit()
    return _serialize_action_result(result)


@router.post("/{candidate_id}/ignore-duplicate")
async def ignore_duplicate(
    candidate_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Suppress or reject a candidate as a duplicate."""
    result = await _translate_errors(
        ignore_duplicate_candidate(
            session,
            user.workspace_id,
            user.user_id,
            candidate_id,
        )
    )
    await session.commit()
    return _serialize_action_result(result)
