"""Queue orchestration for post-sync missed-decision scans."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from inspect import isawaitable
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.missed_decision import (
    MissedDecisionCandidate,
    MissedDecisionScanRun,
    MissedDecisionScanState,
)
from src.services.missed_decision_actionability import (
    ACTION_SAVE_DECISION_RECEIPT,
    ACTIONABILITY_ACTIONABLE,
    WRITE_POLICY_AUTO_INTERNAL,
    WRITE_POLICY_DRAFT_EXTERNAL,
    WRITE_POLICY_REVIEW_REQUIRED,
    verify_candidate_actionability,
)
from src.services.missed_decision_actions import auto_confirm_candidate
from src.services.missed_decision_dedupe import (
    classify_missed_decision_candidate,
    decision_fingerprint,
    quote_fingerprint,
)
from src.services.missed_decision_extractor import (
    extract_missed_decision_candidates,
    is_surfaceable_confidence,
)
from src.services.missed_decision_sources import (
    MissedDecisionSourceRecord,
    count_source_window,
    load_source_window,
)
from src.services.missed_decision_suggestions import (
    publish_missed_decision_suggestion,
)

logger = logging.getLogger(__name__)

FIRST_SCAN_LOOKBACK_DAYS = 14
SOURCE_WINDOW_BATCH_SIZE = 100
PROGRESS_COMMIT_INTERVAL = 5
STALE_RUNNING_SCAN_AFTER = timedelta(minutes=10)
SCAN_STATUS_QUEUED = "queued"
SCAN_STATUS_RUNNING = "running"
SCAN_STATUS_SUCCEEDED = "succeeded"
SCAN_STATUS_FAILED = "failed"


@dataclass
class ScanWindow:
    """Resolved source window and durable checkpoint state."""

    state: MissedDecisionScanState
    start: datetime
    end: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def _updated_at_cutoff(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def running_scan_is_stale_filter(stale_before: datetime):
    """Return SQL condition for a running scan with no recent heartbeat."""
    updated_at_stale_before = _updated_at_cutoff(stale_before)
    return and_(
        MissedDecisionScanRun.status == SCAN_STATUS_RUNNING,
        or_(
            MissedDecisionScanRun.started_at.is_(None),  # type: ignore[union-attr]
            and_(
                MissedDecisionScanRun.started_at < stale_before,
                or_(
                    MissedDecisionScanRun.updated_at.is_(None),  # type: ignore[union-attr]
                    MissedDecisionScanRun.updated_at < updated_at_stale_before,
                ),
            ),
        ),
    )


async def _add(session: AsyncSession, instance: object) -> None:
    result = session.add(instance)
    if isawaitable(result):
        await result


async def _get_scan_state(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_resource_id: str | None,
) -> MissedDecisionScanState | None:
    stmt = select(MissedDecisionScanState).where(
        MissedDecisionScanState.workspace_id == workspace_id,
        MissedDecisionScanState.source_type == source_type,
        MissedDecisionScanState.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    if source_resource_id is None:
        stmt = stmt.where(
            MissedDecisionScanState.source_resource_id.is_(None)  # type: ignore[union-attr]
        )
    else:
        stmt = stmt.where(
            MissedDecisionScanState.source_resource_id == source_resource_id
        )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _has_queued_or_running_scan(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_resource_id: str | None,
) -> bool:
    stmt = (
        select(MissedDecisionScanRun.id)
        .where(
            MissedDecisionScanRun.workspace_id == workspace_id,
            MissedDecisionScanRun.source_type == source_type,
            MissedDecisionScanRun.status.in_(  # type: ignore[attr-defined]
                [SCAN_STATUS_QUEUED, SCAN_STATUS_RUNNING]
            ),
            MissedDecisionScanRun.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(1)
    )
    if source_resource_id is None:
        stmt = stmt.where(
            MissedDecisionScanRun.source_resource_id.is_(None)  # type: ignore[union-attr]
        )
    else:
        stmt = stmt.where(
            MissedDecisionScanRun.source_resource_id == source_resource_id
        )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def get_scan_window(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    *,
    source_resource_id: str | None = None,
    sync_completed_at: datetime | None = None,
) -> ScanWindow:
    """Resolve the bounded scan window for a workspace/source."""
    end = sync_completed_at or _now()
    state = await _get_scan_state(
        session,
        workspace_id,
        source_type,
        source_resource_id,
    )
    if state is None:
        state = MissedDecisionScanState(
            workspace_id=workspace_id,
            source_type=source_type,
            source_resource_id=source_resource_id,
        )
        await _add(session, state)
        await session.flush()

    if state.last_missed_decision_scan_at is not None:
        start = state.last_missed_decision_scan_at
    else:
        start = end - timedelta(days=FIRST_SCAN_LOOKBACK_DAYS)

    return ScanWindow(state=state, start=start, end=end)


async def enqueue_missed_decision_scan(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_resource_id: str | None = None,
    sync_completed_at: datetime | None = None,
) -> MissedDecisionScanRun | None:
    """Queue a missed-decision scan without letting failures affect sync success."""
    try:
        savepoint = session.begin_nested()
        if isawaitable(savepoint):
            savepoint = await savepoint
        async with savepoint:
            if await _has_queued_or_running_scan(
                session,
                workspace_id,
                source_type,
                source_resource_id,
            ):
                return None
            window = await get_scan_window(
                session,
                workspace_id,
                source_type,
                source_resource_id=source_resource_id,
                sync_completed_at=sync_completed_at,
            )
            run = MissedDecisionScanRun(
                workspace_id=workspace_id,
                source_type=source_type,
                source_resource_id=source_resource_id,
                status=SCAN_STATUS_QUEUED,
                source_window_start=window.start,
                source_window_end=window.end,
            )
            await _add(session, run)
            await session.flush()
            return run
    except Exception:
        logger.warning(
            "Failed to enqueue missed-decision scan for %s/%s in workspace %s",
            source_type,
            source_resource_id or "*",
            workspace_id,
            exc_info=True,
        )
        return None


async def _find_existing_candidate(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    source_type: str,
    source_id: UUID,
    quote_fp: str,
    decision_fp: str,
) -> MissedDecisionCandidate | None:
    stmt = (
        select(MissedDecisionCandidate)
        .where(
            MissedDecisionCandidate.workspace_id == workspace_id,
            MissedDecisionCandidate.source_type == source_type,
            MissedDecisionCandidate.source_id == source_id,
            MissedDecisionCandidate.quote_fingerprint == quote_fp,
            MissedDecisionCandidate.decision_fingerprint == decision_fp,
            MissedDecisionCandidate.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    candidate = result.scalar_one_or_none()
    if isinstance(candidate, MissedDecisionCandidate):
        return candidate
    return None


def _record_match_metadata(
    candidate: MissedDecisionCandidate,
    classification,
) -> None:
    if not (
        classification.matched_title
        or classification.matched_href
        or classification.match_reason
    ):
        return
    evidence = dict(candidate.evidence or {})
    evidence["possible_existing_match"] = {
        "title": classification.matched_title,
        "href": classification.matched_href,
        "match_reason": classification.match_reason,
    }
    candidate.evidence = evidence


def _record_artifact_search_metadata(
    candidate: MissedDecisionCandidate,
    classification,
) -> None:
    evidence = dict(candidate.evidence or {})
    review_context = dict(evidence.get("review_context") or {})
    searched_sources = review_context.get("searched_sources") or [
        "Decision memory",
        "Existing candidates",
        "Suggestions",
        "Tickets",
        "PRs",
        "Docs",
    ]
    review_context["searched_sources"] = searched_sources

    quality_gate = dict(evidence.get("quality_gate") or {})
    quality_gate["searched_sources"] = searched_sources

    if classification.match_status == "strong_match":
        review_context["missing_artifact_status"] = "already_backed"
        review_context["missing_artifact_reason"] = (
            classification.match_reason
            or "A strong matching durable artifact already backs this decision."
        )
        quality_gate["passed"] = False
        quality_gate["suppress_reason"] = (
            classification.suppression_reason or "already_backed_by_artifact"
        )
    elif classification.match_status == "weak_match":
        review_context["missing_artifact_status"] = "possible_match"
        review_context["missing_artifact_reason"] = (
            classification.match_reason
            or "A possible existing artifact needs human inspection."
        )
        quality_gate["artifact_search"] = "possible_match"
    else:
        review_context["missing_artifact_status"] = "not_found"
        review_context["missing_artifact_reason"] = (
            "No strong matching Decision, ticket, PR, doc, suggestion, or "
            "prior candidate was found."
        )
        quality_gate["artifact_search"] = "not_found"

    evidence["review_context"] = review_context
    evidence["quality_gate"] = quality_gate
    candidate.evidence = evidence


async def process_missed_decision_source_window(
    session: AsyncSession,
    scan_run: MissedDecisionScanRun,
    records: list[MissedDecisionSourceRecord],
) -> dict:
    """Extract, dedupe, persist, and publish source-backed candidates."""
    candidates_created = 0
    review_candidates = 0
    auto_saved = 0
    suppressed = 0

    drafts = []
    for record in records:
        drafts.extend(await extract_missed_decision_candidates(record))

    for draft in drafts:
        quote_fp = quote_fingerprint(draft.source_quote)
        decision_fp = decision_fingerprint(draft.inferred_decision)
        existing = await _find_existing_candidate(
            session,
            workspace_id=draft.workspace_id,
            source_type=draft.source_type,
            source_id=draft.source_id,
            quote_fp=quote_fp,
            decision_fp=decision_fp,
        )
        if existing is not None:
            existing.scan_run_id = existing.scan_run_id or scan_run.id
            continue

        candidate = MissedDecisionCandidate(
            workspace_id=draft.workspace_id,
            scan_run_id=scan_run.id,
            source_type=draft.source_type,
            source_id=draft.source_id,
            source_resource_id=draft.source_resource_id,
            source_quote=draft.source_quote,
            inferred_decision=draft.inferred_decision,
            inferred_rationale=draft.inferred_rationale,
            source_link=draft.source_link,
            confidence=draft.confidence,
            quote_fingerprint=quote_fp,
            decision_fingerprint=decision_fp,
            evidence=draft.evidence,
            people=draft.people,
            affected_systems=draft.affected_systems,
            action_hints=draft.action_hints,
        )
        classification = await classify_missed_decision_candidate(
            session,
            candidate,
        )
        candidate.match_status = classification.match_status
        candidate.lifecycle_status = classification.lifecycle_status
        candidate.suppression_reason = classification.suppression_reason
        candidate.matched_entity_type = classification.matched_entity_type
        candidate.matched_entity_id = classification.matched_entity_id
        _record_match_metadata(candidate, classification)
        _record_artifact_search_metadata(candidate, classification)
        actionability = await verify_candidate_actionability(
            session,
            candidate,
            classification,
        )

        await _add(session, candidate)
        await session.flush()
        candidates_created += 1
        if candidate.lifecycle_status == "suppressed":
            suppressed += 1

        next_action = actionability.next_action
        if (
            actionability.status == ACTIONABILITY_ACTIONABLE
            and next_action.kind == ACTION_SAVE_DECISION_RECEIPT
            and next_action.write_policy == WRITE_POLICY_AUTO_INTERNAL
        ):
            await auto_confirm_candidate(session, candidate)
            auto_saved += 1
        elif (
            actionability.status == ACTIONABILITY_ACTIONABLE
            and next_action.write_policy
            in {WRITE_POLICY_DRAFT_EXTERNAL, WRITE_POLICY_REVIEW_REQUIRED}
            and classification.should_publish_suggestion
            and is_surfaceable_confidence(candidate.confidence)
        ):
            suggestion = await publish_missed_decision_suggestion(
                session,
                candidate,
            )
            if suggestion is not None:
                review_candidates += 1

    return {
        "candidates_created": candidates_created,
        "decisions_auto_saved": auto_saved,
        "suggestions_published": review_candidates,
        "review_candidates": review_candidates,
        "auto_saved": auto_saved,
        "suppressed": suppressed,
    }


async def run_missed_decision_scan_once(
    session: AsyncSession,
    scan_run: MissedDecisionScanRun,
) -> MissedDecisionScanRun:
    """Process one claimed scan run and update run/checkpoint state."""
    now = _now()
    if scan_run.status != SCAN_STATUS_RUNNING:
        scan_run.status = SCAN_STATUS_RUNNING
        scan_run.attempts += 1
    scan_run.started_at = scan_run.started_at or now
    scan_run.error_message = None
    await session.flush()
    await session.commit()

    window = await get_scan_window(
        session,
        scan_run.workspace_id,
        scan_run.source_type,
        source_resource_id=scan_run.source_resource_id,
        sync_completed_at=scan_run.source_window_end or now,
    )
    if (
        scan_run.source_window_start is None
        or window.start > scan_run.source_window_start
    ):
        scan_run.source_window_start = window.start
    scan_run.source_window_end = scan_run.source_window_end or window.end
    await session.flush()
    await session.commit()

    if scan_run.sources_total is None:
        scan_run.sources_total = await count_source_window(
            session,
            scan_run.workspace_id,
            scan_run.source_type,
            scan_run.source_window_start,
            scan_run.source_window_end,
            source_resource_id=scan_run.source_resource_id,
        )
        await session.flush()
        await session.commit()

    try:
        sources_scanned = 0
        candidates_created = 0
        review_candidates = 0
        auto_saved = 0
        suppressed = 0
        after_source_created_at: datetime | None = None
        after_source_id: UUID | None = None
        while True:
            records = await load_source_window(
                session,
                scan_run.workspace_id,
                scan_run.source_type,
                scan_run.source_window_start,
                scan_run.source_window_end,
                source_resource_id=scan_run.source_resource_id,
                after_source_created_at=after_source_created_at,
                after_source_id=after_source_id,
                limit=SOURCE_WINDOW_BATCH_SIZE,
            )
            if not records:
                break
            await session.commit()

            for start_index in range(0, len(records), PROGRESS_COMMIT_INTERVAL):
                progress_chunk = records[
                    start_index : start_index + PROGRESS_COMMIT_INTERVAL
                ]
                result = await process_missed_decision_source_window(
                    session,
                    scan_run,
                    progress_chunk,
                )
                sources_scanned += len(progress_chunk)
                candidates_created += int(result.get("candidates_created", 0))
                review_candidates += int(result.get("review_candidates", 0))
                auto_saved += int(result.get("auto_saved", 0))
                suppressed += int(result.get("suppressed", 0))
                scan_run.sources_scanned = sources_scanned
                scan_run.candidates_created = candidates_created
                scan_run.review_candidates = review_candidates
                scan_run.auto_saved = auto_saved
                scan_run.suppressed = suppressed
                await session.flush()
                await session.commit()

            if len(records) < SOURCE_WINDOW_BATCH_SIZE:
                break

            last = records[-1]
            if (
                after_source_created_at == last.source_created_at
                and after_source_id == last.source_id
            ):
                raise RuntimeError("missed-decision source cursor did not advance")
            after_source_created_at = last.source_created_at
            after_source_id = last.source_id

        scan_run.status = SCAN_STATUS_SUCCEEDED
        scan_run.completed_at = _now()
        window.state.last_missed_decision_scan_at = scan_run.source_window_end
        await session.flush()
        await session.commit()
    except Exception as exc:
        await session.rollback()
        scan_run.status = SCAN_STATUS_FAILED
        scan_run.error_message = str(exc)[:1000]
        scan_run.completed_at = _now()
        await session.flush()
        await session.commit()
        logger.warning(
            "Missed-decision scan failed for run %s",
            scan_run.id,
            exc_info=True,
        )

    return scan_run


async def drain_queued_missed_decision_scans(
    session: AsyncSession,
    *,
    limit: int = 10,
) -> int:
    """Claim and process queued scan runs."""
    stale_started_before = _now() - STALE_RUNNING_SCAN_AFTER
    stmt = (
        select(MissedDecisionScanRun)
        .where(
            or_(
                MissedDecisionScanRun.status == SCAN_STATUS_QUEUED,
                running_scan_is_stale_filter(stale_started_before),
            ),
            MissedDecisionScanRun.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(MissedDecisionScanRun.created_at.desc())  # type: ignore[union-attr]
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    claimed_keys: set[tuple[UUID, str, str | None]] = set()
    runs: list[MissedDecisionScanRun] = []
    for run in result.scalars().all():
        key = (run.workspace_id, run.source_type, run.source_resource_id)
        if key in claimed_keys:
            run.status = SCAN_STATUS_FAILED
            run.error_message = "Superseded by a newer active scan for this source."
            run.completed_at = _now()
            continue
        claimed_keys.add(key)
        runs.append(run)

    for run in runs:
        run.status = SCAN_STATUS_RUNNING
        run.started_at = _now()
        run.attempts += 1
    if runs:
        await session.flush()

    processed = 0
    for run in runs:
        await run_missed_decision_scan_once(session, run)
        processed += 1

    return processed
