"""Missed-decision review endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.graph_node import GraphNode
from src.models.missed_decision import MissedDecisionCandidate, MissedDecisionScanRun
from src.models.slack import SlackMessage
from src.models.suggestion import Suggestion
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
    candidate_source_metadata,
)
from src.services.slack_events import slack_archive_url
from src.services.slack_text import (
    render_slack_user_reference,
    replace_slack_user_mentions,
    resolve_slack_user_names,
    slack_user_id_from_reference,
    slack_user_ids_in_text,
)

router = APIRouter(prefix="/api/missed-decisions", tags=["missed-decisions"])


class DeferCandidateRequest(BaseModel):
    """Optional body for deferring a candidate."""

    snoozed_until: datetime | None = None


class RejectCandidateRequest(BaseModel):
    """Optional body for rejecting a candidate."""

    reason: str | None = None


class AddEvidenceRequest(BaseModel):
    """Optional body for attaching evidence to a selected Decision."""

    target_decision_id: UUID | None = None


class MissedDecisionScanStatus(BaseModel):
    """Dashboard-safe missed-decision scan progress payload."""

    id: str
    source_type: str
    source_resource_id: str | None
    status: str
    source_window_start: str | None
    source_window_end: str | None
    sources_scanned: int
    sources_total: int | None
    progress_percent: int | None
    candidates_created: int
    review_candidates: int
    auto_saved: int
    suppressed: int
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


def _entity_href(
    entity_type: str | None,
    entity_id: str | None,
    props: dict | None = None,
) -> str | None:
    if not entity_id:
        return None
    if entity_type == "Decision":
        return f"/dashboard/decisions/{entity_id}"
    if props:
        for key in ("url", "html_url", "web_url", "source_link", "link"):
            value = props.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _recommended_action(
    candidate: MissedDecisionCandidate,
    match: dict | None,
) -> str:
    if candidate.match_status in {"weak_match", "strong_match"}:
        if match and match.get("entity_type") == "Decision":
            return "add_as_evidence"
        if candidate.match_status == "strong_match":
            return "ignore_duplicate"
        return "inspect_existing_match"
    return "save_as_new_decision"


def _review_context(candidate: MissedDecisionCandidate) -> dict:
    evidence = candidate.evidence or {}
    raw_context = evidence.get("review_context")
    context = dict(raw_context) if isinstance(raw_context, dict) else {}
    if not context.get("affected_object") and candidate.affected_systems:
        context["affected_object"] = candidate.affected_systems[0]
    if not context.get("affected_objects") and candidate.affected_systems:
        context["affected_objects"] = candidate.affected_systems
    if not context.get("searched_sources"):
        context["searched_sources"] = [
            "Decision memory",
            "Existing candidates",
            "Suggestions",
            "Tickets",
            "PRs",
            "Docs",
        ]
    quality_gate = evidence.get("quality_gate")
    if isinstance(quality_gate, dict):
        context["quality_gate"] = {
            key: quality_gate.get(key)
            for key in ("passed", "suppress_reason", "artifact_search")
            if key in quality_gate
        }
    return context


def _render_slack_people(
    people: list[str],
    user_names: dict[str, str],
) -> list[str]:
    rendered: list[str] = []
    seen: set[str] = set()
    for person in people:
        name = render_slack_user_reference(person, user_names).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        rendered.append(name)
    return rendered


def _serialize_candidate(
    candidate: MissedDecisionCandidate,
    match_metadata: dict | None = None,
    source_link: str | None = None,
    slack_user_names: dict[str, str] | None = None,
) -> dict:
    slack_user_names = slack_user_names or {}
    inferred_decision = replace_slack_user_mentions(
        candidate.inferred_decision,
        slack_user_names,
    )
    inferred_rationale = replace_slack_user_mentions(
        candidate.inferred_rationale,
        slack_user_names,
    )
    source_quote = replace_slack_user_mentions(
        candidate.source_quote,
        slack_user_names,
    )
    people = _render_slack_people(candidate_people(candidate), slack_user_names)
    author_name = candidate_author_name(candidate)
    if author_name:
        author_name = render_slack_user_reference(author_name, slack_user_names)

    evidence_match = (candidate.evidence or {}).get("possible_existing_match")
    if not isinstance(evidence_match, dict):
        evidence_match = {}
    entity_id = (
        str(candidate.matched_entity_id) if candidate.matched_entity_id else None
    )
    match = {
        "match_status": candidate.match_status,
        "entity_type": candidate.matched_entity_type,
        "entity_id": entity_id,
        "title": evidence_match.get("title"),
        "href": evidence_match.get("href"),
        "match_reason": evidence_match.get("match_reason"),
    }
    if match_metadata:
        match.update(
            {key: value for key, value in match_metadata.items() if value is not None}
        )

    return {
        "id": str(candidate.id),
        "workspace_id": str(candidate.workspace_id),
        "status": candidate.lifecycle_status,
        "suggestion_id": (
            str(candidate.suggestion_id) if candidate.suggestion_id else None
        ),
        "title": inferred_decision,
        "inferred_decision": inferred_decision,
        "inferred_rationale": inferred_rationale,
        "source_quote": source_quote,
        "source_link": source_link or candidate.source_link,
        "confidence": candidate.confidence,
        "people": people,
        "author_name": author_name,
        "source_channel": candidate_source_channel(candidate),
        "source_context": candidate_source_context(candidate),
        "affected_systems": candidate.affected_systems or [],
        "review_context": _review_context(candidate),
        "possible_existing_match": {
            "match_status": match["match_status"],
            "entity_type": match["entity_type"],
            "entity_id": match["entity_id"],
            "title": match["title"],
            "href": match["href"],
            "match_reason": match["match_reason"],
        },
        "recommended_action": _recommended_action(candidate, match),
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


async def _match_metadata_for_candidates(
    session: AsyncSession,
    candidates: list[MissedDecisionCandidate],
) -> dict[UUID, dict]:
    graph_ids = [
        candidate.matched_entity_id
        for candidate in candidates
        if candidate.matched_entity_type == "graph_node" and candidate.matched_entity_id
    ]
    suggestion_ids = [
        candidate.matched_entity_id
        for candidate in candidates
        if candidate.matched_entity_type == "suggestion" and candidate.matched_entity_id
    ]
    candidate_ids = [
        candidate.matched_entity_id
        for candidate in candidates
        if candidate.matched_entity_type == "missed_decision_candidate"
        and candidate.matched_entity_id
    ]
    metadata: dict[UUID, dict] = {}
    if graph_ids:
        result = await session.execute(
            select(GraphNode).where(
                GraphNode.id.in_(graph_ids),  # type: ignore[attr-defined]
                GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
            )
        )
        for node in result.scalars().all():
            if not isinstance(node, GraphNode):
                continue
            metadata[node.id] = {
                "entity_type": node.entity_type,
                "entity_id": str(node.id),
                "title": node.name,
                "href": _entity_href(node.entity_type, str(node.id), node.properties),
            }
    if suggestion_ids:
        result = await session.execute(
            select(Suggestion).where(
                Suggestion.id.in_(suggestion_ids),  # type: ignore[attr-defined]
                Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
            )
        )
        for suggestion in result.scalars().all():
            if not isinstance(suggestion, Suggestion):
                continue
            metadata[suggestion.id] = {
                "entity_type": "suggestion",
                "entity_id": str(suggestion.id),
                "title": suggestion.title,
                "href": suggestion.action_href,
            }
    if candidate_ids:
        result = await session.execute(
            select(MissedDecisionCandidate).where(
                MissedDecisionCandidate.id.in_(candidate_ids),  # type: ignore[attr-defined]
                MissedDecisionCandidate.workspace_id == candidates[0].workspace_id,
                MissedDecisionCandidate.deleted_at.is_(None),  # type: ignore[union-attr]
            )
        )
        for matched_candidate in result.scalars().all():
            if not isinstance(matched_candidate, MissedDecisionCandidate):
                continue
            metadata[matched_candidate.id] = {
                "entity_type": "missed_decision_candidate",
                "entity_id": str(matched_candidate.id),
                "title": matched_candidate.inferred_decision,
                "match_reason": "Same decision was already captured for review.",
            }
    return metadata


def _is_internal_source_reference(source_link: str) -> bool:
    return urlparse(source_link).path == "/dashboard/source-reference"


def _source_links_for_candidates(
    candidates: list[MissedDecisionCandidate],
    slack_rows: dict[UUID, SlackMessage],
) -> dict[UUID, str]:
    internal_slack_candidates = [
        candidate
        for candidate in candidates
        if candidate.source_type == "slack_message"
        and _is_internal_source_reference(candidate.source_link)
    ]
    if not internal_slack_candidates:
        return {}

    links: dict[UUID, str] = {}
    for candidate in internal_slack_candidates:
        row = slack_rows.get(candidate.source_id)
        if row is None:
            continue
        link = slack_archive_url(row.channel_id, row.slack_ts)
        if link:
            links[candidate.id] = link
    return links


async def _slack_rows_for_candidates(
    session: AsyncSession,
    candidates: list[MissedDecisionCandidate],
) -> dict[UUID, SlackMessage]:
    slack_source_ids = [
        candidate.source_id
        for candidate in candidates
        if candidate.source_type == "slack_message"
    ]
    if not slack_source_ids:
        return {}

    result = await session.execute(
        select(SlackMessage).where(
            SlackMessage.id.in_(slack_source_ids),  # type: ignore[attr-defined]
            SlackMessage.workspace_id == candidates[0].workspace_id,
            SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    rows = {
        row.id: row
        for row in result.scalars().all()
        if isinstance(row, SlackMessage)
    }
    return rows


def _candidate_slack_user_ids(candidate: MissedDecisionCandidate) -> set[str]:
    user_ids: set[str] = set()
    for value in (
        candidate.source_quote,
        candidate.inferred_decision,
        candidate.inferred_rationale,
    ):
        user_ids.update(slack_user_ids_in_text(value))
    for person in candidate_people(candidate):
        user_id = slack_user_id_from_reference(person)
        if user_id:
            user_ids.add(user_id)
    return user_ids


async def _slack_user_names_for_candidates(
    session: AsyncSession,
    candidates: list[MissedDecisionCandidate],
    slack_rows: dict[UUID, SlackMessage],
) -> dict[UUID, dict[str, str]]:
    slack_candidates = [
        candidate
        for candidate in candidates
        if candidate.source_type == "slack_message"
    ]
    if not slack_candidates:
        return {}

    user_ids: set[str] = set()
    known_user_names: dict[str, str | None] = {}
    for candidate in slack_candidates:
        row = slack_rows.get(candidate.source_id)
        user_ids.update(_candidate_slack_user_ids(candidate))
        metadata = candidate_source_metadata(candidate)
        raw_user_names = metadata.get("slack_user_names")
        if isinstance(raw_user_names, dict):
            for user_id, name in raw_user_names.items():
                if isinstance(user_id, str):
                    known_user_names[user_id] = name if isinstance(name, str) else None
        if row and row.user_id:
            user_ids.add(row.user_id)
            known_user_names[row.user_id] = row.user_name

    resolved = await resolve_slack_user_names(
        session,
        slack_candidates[0].workspace_id,
        user_ids,
        known_user_names=known_user_names,
    )
    return {candidate.id: resolved for candidate in slack_candidates}


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
        "source_resource_id": scan_run.source_resource_id,
        "status": scan_run.status,
        "source_window_start": _iso_timestamp(scan_run.source_window_start),
        "source_window_end": _iso_timestamp(scan_run.source_window_end),
        "sources_scanned": scan_run.sources_scanned,
        "sources_total": scan_run.sources_total,
        "progress_percent": _progress_percent(scan_run),
        "candidates_created": scan_run.candidates_created,
        "review_candidates": scan_run.review_candidates,
        "auto_saved": scan_run.auto_saved,
        "suppressed": scan_run.suppressed,
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
    match_metadata = await _match_metadata_for_candidates(session, candidates)
    slack_rows = await _slack_rows_for_candidates(session, candidates)
    source_links = _source_links_for_candidates(candidates, slack_rows)
    slack_user_names = await _slack_user_names_for_candidates(
        session,
        candidates,
        slack_rows,
    )
    return [
        _serialize_candidate(
            candidate,
            match_metadata.get(candidate.matched_entity_id)
            if candidate.matched_entity_id
            else None,
            source_link=source_links.get(candidate.id),
            slack_user_names=slack_user_names.get(candidate.id),
        )
        for candidate in candidates
    ]


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
    seen_sources: set[tuple[str, str | None]] = set()
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
        source_key = (run.source_type, run.source_resource_id)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
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
    body: AddEvidenceRequest | None = None,
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
            target_decision_id=body.target_decision_id if body else None,
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
