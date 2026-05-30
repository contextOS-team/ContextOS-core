"""Reclassify missed-decision candidates with the actionability verifier.

Usage:
    cd backend
    uv run python scripts/reclassify_missed_decisions.py --workspace-id <uuid>
    uv run python scripts/reclassify_missed_decisions.py --apply --include-surfaced
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import select  # noqa: E402

from src.db import async_session  # noqa: E402
from src.models.missed_decision import MissedDecisionCandidate  # noqa: E402
from src.models.suggestion import Suggestion  # noqa: E402
from src.services.audit import log_audit_event  # noqa: E402
from src.services.missed_decision_actionability import (  # noqa: E402
    ACTION_SAVE_DECISION_RECEIPT,
    ACTIONABILITY_ACTIONABLE,
    WRITE_POLICY_AUTO_INTERNAL,
    WRITE_POLICY_DRAFT_EXTERNAL,
    WRITE_POLICY_REVIEW_REQUIRED,
    verify_candidate_actionability,
)
from src.services.missed_decision_actions import auto_confirm_candidate  # noqa: E402
from src.services.missed_decision_dedupe import (  # noqa: E402
    classify_missed_decision_candidate,
)
from src.services.missed_decision_scanner import (  # noqa: E402
    _record_artifact_search_metadata,
    _record_match_metadata,
)
from src.services.missed_decision_suggestions import (  # noqa: E402
    publish_missed_decision_suggestion,
)
from src.services.suggestions import (  # noqa: E402
    SUGGESTION_STATUS_OPEN,
    SUGGESTION_STATUS_RESOLVED,
    SUGGESTION_STATUS_SNOOZED,
)

logger = logging.getLogger("reclassify_missed_decisions")

REPROCESS_LIFECYCLES = {"detected", "deferred"}
TERMINAL_LIFECYCLES = {"confirmed", "linked", "suppressed", "rejected"}


@dataclass
class ReclassifyStats:
    scanned: int = 0
    actionable: int = 0
    held: int = 0
    auto_confirmed: int = 0
    suggestions_published: int = 0
    suggestions_hidden: int = 0
    skipped_terminal: int = 0


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _load_related_suggestion(session, candidate: MissedDecisionCandidate):
    if candidate.suggestion_id is None:
        return None
    result = await session.execute(
        select(Suggestion).where(
            Suggestion.id == candidate.suggestion_id,
            Suggestion.workspace_id == candidate.workspace_id,
            Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    return result.scalar_one_or_none()


async def _hide_related_suggestion(
    session,
    candidate: MissedDecisionCandidate,
    *,
    reason: str,
) -> bool:
    suggestion = await _load_related_suggestion(session, candidate)
    if suggestion is None or suggestion.status not in {
        SUGGESTION_STATUS_OPEN,
        SUGGESTION_STATUS_SNOOZED,
    }:
        return False
    now = _now()
    suggestion.status = SUGGESTION_STATUS_RESOLVED
    suggestion.resolved_at = suggestion.resolved_at or now
    suggestion.deleted_at = now
    await log_audit_event(
        session,
        workspace_id=candidate.workspace_id,
        action="missed_decision.reclassify_hide_suggestion",
        user_id=None,
        resource_type="suggestion",
        resource_id=suggestion.id,
        details={
            "candidate_id": str(candidate.id),
            "reason": reason,
            "type": suggestion.type,
        },
    )
    return True


async def _load_candidates(
    session,
    *,
    workspace_id: UUID | None,
    limit: int,
    include_surfaced: bool,
) -> list[MissedDecisionCandidate]:
    lifecycles = set(REPROCESS_LIFECYCLES)
    if include_surfaced:
        lifecycles.add("surfaced")
    stmt = (
        select(MissedDecisionCandidate)
        .where(
            MissedDecisionCandidate.lifecycle_status.in_(lifecycles),  # type: ignore[attr-defined]
            MissedDecisionCandidate.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(MissedDecisionCandidate.detected_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    if workspace_id is not None:
        stmt = stmt.where(MissedDecisionCandidate.workspace_id == workspace_id)
    result = await session.execute(stmt)
    candidates = result.scalars().all()
    return [
        candidate
        for candidate in candidates
        if candidate.lifecycle_status not in TERMINAL_LIFECYCLES
    ]


async def reclassify(
    *,
    dry_run: bool,
    workspace_id: UUID | None,
    limit: int,
    include_surfaced: bool,
) -> ReclassifyStats:
    stats = ReclassifyStats()
    async with async_session() as session:
        candidates = await _load_candidates(
            session,
            workspace_id=workspace_id,
            limit=limit,
            include_surfaced=include_surfaced,
        )
        for candidate in candidates:
            stats.scanned += 1
            classification = await classify_missed_decision_candidate(
                session,
                candidate,
            )
            candidate.match_status = classification.match_status
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
            next_action = actionability.next_action
            if actionability.status == ACTIONABILITY_ACTIONABLE:
                stats.actionable += 1
            else:
                stats.held += 1

            if dry_run:
                logger.info(
                    "[DRY-RUN] candidate=%s status=%s action=%s policy=%s",
                    candidate.id,
                    actionability.status,
                    next_action.kind,
                    next_action.write_policy,
                )
                continue

            if (
                actionability.status == ACTIONABILITY_ACTIONABLE
                and next_action.kind == ACTION_SAVE_DECISION_RECEIPT
                and next_action.write_policy == WRITE_POLICY_AUTO_INTERNAL
            ):
                await auto_confirm_candidate(session, candidate)
                stats.auto_confirmed += 1
                continue

            if (
                actionability.status == ACTIONABILITY_ACTIONABLE
                and next_action.write_policy
                in {WRITE_POLICY_DRAFT_EXTERNAL, WRITE_POLICY_REVIEW_REQUIRED}
            ):
                suggestion = await publish_missed_decision_suggestion(
                    session,
                    candidate,
                )
                if suggestion is not None:
                    stats.suggestions_published += 1
                continue

            if await _hide_related_suggestion(
                session,
                candidate,
                reason=actionability.status,
            ):
                stats.suggestions_hidden += 1

        if dry_run:
            await session.rollback()
            return stats
        await session.commit()
    return stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist metadata/actionability updates. Default is dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect without writes. This is the default unless --apply is passed.",
    )
    parser.add_argument("--workspace-id", type=UUID, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--include-surfaced",
        action="store_true",
        help="Also reprocess currently surfaced candidates.",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    dry_run = not args.apply or args.dry_run
    stats = await reclassify(
        dry_run=dry_run,
        workspace_id=args.workspace_id,
        limit=args.limit,
        include_surfaced=args.include_surfaced,
    )
    mode = "DRY-RUN" if dry_run else "APPLIED"
    logger.info(
        "%s scanned=%d actionable=%d held=%d auto_confirmed=%d "
        "suggestions_published=%d suggestions_hidden=%d",
        mode,
        stats.scanned,
        stats.actionable,
        stats.held,
        stats.auto_confirmed,
        stats.suggestions_published,
        stats.suggestions_hidden,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(main())
