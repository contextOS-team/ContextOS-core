"""Missed-decision review endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.missed_decision import MissedDecisionCandidate
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

router = APIRouter(prefix="/api/missed-decisions", tags=["missed-decisions"])


class DeferCandidateRequest(BaseModel):
    """Optional body for deferring a candidate."""

    snoozed_until: datetime | None = None


class RejectCandidateRequest(BaseModel):
    """Optional body for rejecting a candidate."""

    reason: str | None = None


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
        "people": candidate.people or [],
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
