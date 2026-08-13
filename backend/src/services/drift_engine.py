"""Drift engine: orchestrate infer -> check -> verify -> drift for a workspace.

Invoked by scripts/run_drift_scan.py today; moves onto the worker queue when
scan volume demands it (see technical plan Phase 2.4).
"""

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.decision import Decision
from src.models.decision_drift import Drift, ExpectedConsequence
from src.models.suggestion import Suggestion
from src.services.drift_checkers import check_consequence
from src.services.impact_inference import (
    decisions_needing_inference,
    infer_expected_consequences,
)
from src.services.skeptical_verifier import verify_drift

logger = logging.getLogger(__name__)


@dataclass
class DriftScanStats:
    decisions_inferred: int = 0
    consequences_created: int = 0
    consequences_checked: int = 0
    inconsistent_found: int = 0
    killed_by_verifier: int = 0
    drifts_created: int = 0
    kill_reasons: list[str] = field(default_factory=list)


async def _has_open_drift(session: AsyncSession, consequence_id: UUID) -> bool:
    stmt = select(Drift.id).where(
        Drift.expected_consequence_id == consequence_id,
        Drift.resolved_at.is_(None),  # type: ignore[union-attr]
        Drift.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    return (await session.execute(stmt)).first() is not None


def _publish_drift_suggestion(
    session: AsyncSession, drift: Drift, decision: Decision
) -> Suggestion:
    suggestion = Suggestion(
        workspace_id=drift.workspace_id,
        type="decision_drift",
        priority=(
            drift.severity if drift.severity in ("high", "medium", "low") else "medium"
        ),
        fingerprint=f"decision-drift:{drift.expected_consequence_id or drift.id}",
        entity_type="drift",
        entity_id=drift.id,
        title="Decision Drift detected",
        body=f'{drift.summary} (decision: "{decision.statement[:120]}")',
        primary_action="review_drift",
        action_href=f"/dashboard/decisions/{decision.graph_node_id or decision.id}",
        evidence={"verifier_verdict": drift.verifier_verdict},
        provenance={"producer": "drift_engine"},
    )
    session.add(suggestion)
    return suggestion


async def scan_workspace_for_drift(
    session: AsyncSession,
    workspace_id: UUID,
    max_decisions: int = 50,
    max_checks: int = 100,
) -> DriftScanStats:
    """One full drift pass over a workspace.

    Commits incrementally (after each decision's inference and after each
    surfaced drift) so a scan is never one long transaction — important
    because LLM calls leave the DB session idle-in-transaction, and the prod
    role kills sessions idle > 2 min.
    """
    stats = DriftScanStats()

    # Stage 1: impact inference for active decisions that lack consequences.
    for decision in await decisions_needing_inference(
        session, workspace_id, limit=max_decisions
    ):
        rows = await infer_expected_consequences(session, decision)
        await session.commit()
        stats.decisions_inferred += 1
        stats.consequences_created += len(rows)

    # Stage 2: check pending consequences.
    pending = (
        (
            await session.execute(
                select(ExpectedConsequence, Decision)
                .join(Decision, Decision.id == ExpectedConsequence.decision_id)
                .where(
                    ExpectedConsequence.workspace_id == workspace_id,
                    ExpectedConsequence.status == "pending",
                    ExpectedConsequence.deleted_at.is_(None),  # type: ignore[union-attr]
                    Decision.status == "active",
                )
                .limit(max_checks)
            )
        )
        .all()
    )
    for consequence, decision in pending:
        observation = await check_consequence(session, decision, consequence)
        await session.commit()
        if observation is None:
            continue
        stats.consequences_checked += 1
        if observation.consistent is not False:
            continue
        stats.inconsistent_found += 1

        # Stage 3: skeptical verification; only survivors become drifts.
        verdict = await verify_drift(decision, consequence, observation)
        if verdict is None or not verdict.is_meaningful_drift:
            stats.killed_by_verifier += 1
            if verdict is not None and verdict.kill_reason:
                stats.kill_reasons.append(verdict.kill_reason)
            continue
        if await _has_open_drift(session, consequence.id):
            continue

        drift = Drift(
            workspace_id=workspace_id,
            decision_id=decision.id,
            expected_consequence_id=consequence.id,
            summary=verdict.summary,
            severity=verdict.severity,
            verifier_verdict=verdict.model_dump(),
        )
        session.add(drift)
        await session.flush()
        suggestion = _publish_drift_suggestion(session, drift, decision)
        await session.flush()
        drift.suggestion_id = suggestion.id
        await session.commit()
        stats.drifts_created += 1

    return stats
