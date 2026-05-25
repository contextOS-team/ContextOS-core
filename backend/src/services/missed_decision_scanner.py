"""Queue orchestration for post-sync missed-decision scans."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from inspect import isawaitable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.missed_decision import (
    MissedDecisionCandidate,
    MissedDecisionScanRun,
    MissedDecisionScanState,
)
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
    load_source_window,
)
from src.services.missed_decision_suggestions import (
    publish_missed_decision_suggestion,
)

logger = logging.getLogger(__name__)

FIRST_SCAN_LOOKBACK_DAYS = 14
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


async def get_scan_window(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    *,
    source_resource_id: str | None = None,
    sync_completed_at: datetime | None = None,
    source_connected_at: datetime | None = None,
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
        fallback = end - timedelta(days=14)
        start = max(source_connected_at, fallback) if source_connected_at else fallback

    return ScanWindow(state=state, start=start, end=end)


async def enqueue_missed_decision_scan(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_resource_id: str | None = None,
    sync_completed_at: datetime | None = None,
    source_connected_at: datetime | None = None,
) -> MissedDecisionScanRun | None:
    """Queue a missed-decision scan without letting failures affect sync success."""
    try:
        savepoint = session.begin_nested()
        if isawaitable(savepoint):
            savepoint = await savepoint
        async with savepoint:
            window = await get_scan_window(
                session,
                workspace_id,
                source_type,
                source_resource_id=source_resource_id,
                sync_completed_at=sync_completed_at,
                source_connected_at=source_connected_at,
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


async def process_missed_decision_source_window(
    session: AsyncSession,
    scan_run: MissedDecisionScanRun,
    records: list[MissedDecisionSourceRecord],
) -> dict:
    """Extract, dedupe, persist, and publish source-backed candidates."""
    candidates_created = 0
    suggestions_published = 0
    for record in records:
        drafts = await extract_missed_decision_candidates(record)
        for draft in drafts:
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
                quote_fingerprint=quote_fingerprint(draft.source_quote),
                decision_fingerprint=decision_fingerprint(draft.inferred_decision),
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

            await _add(session, candidate)
            await session.flush()
            candidates_created += 1

            if (
                classification.should_publish_suggestion
                and is_surfaceable_confidence(candidate.confidence)
            ):
                suggestion = await publish_missed_decision_suggestion(
                    session,
                    candidate,
                )
                if suggestion is not None:
                    suggestions_published += 1

    return {
        "candidates_created": candidates_created,
        "suggestions_published": suggestions_published,
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

    window = await get_scan_window(
        session,
        scan_run.workspace_id,
        scan_run.source_type,
        source_resource_id=scan_run.source_resource_id,
        sync_completed_at=scan_run.source_window_end or now,
    )
    scan_run.source_window_start = scan_run.source_window_start or window.start
    scan_run.source_window_end = scan_run.source_window_end or window.end

    try:
        records = await load_source_window(
            session,
            scan_run.workspace_id,
            scan_run.source_type,
            scan_run.source_window_start,
            scan_run.source_window_end,
            source_resource_id=scan_run.source_resource_id,
        )
        result = await process_missed_decision_source_window(session, scan_run, records)
        scan_run.sources_scanned = len(records)
        scan_run.candidates_created = int(result.get("candidates_created", 0))
        scan_run.status = SCAN_STATUS_SUCCEEDED
        scan_run.completed_at = _now()
        window.state.last_missed_decision_scan_at = scan_run.source_window_end
        await session.flush()
    except Exception as exc:
        scan_run.status = SCAN_STATUS_FAILED
        scan_run.error_message = str(exc)[:1000]
        scan_run.completed_at = _now()
        await session.flush()
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
    stmt = (
        select(MissedDecisionScanRun)
        .where(
            MissedDecisionScanRun.status == SCAN_STATUS_QUEUED,
            MissedDecisionScanRun.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(MissedDecisionScanRun.created_at.asc())  # type: ignore[union-attr]
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    runs = list(result.scalars().all())
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
