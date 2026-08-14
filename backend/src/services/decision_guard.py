"""Decision Guard: advisory check_action.

Given a proposed action, retrieve the active decisions most relevant to it plus
any sanctioned exceptions, then make ONE conflict assessment. Advisory only —
returns constraints to weigh, never blocks. Vocabulary is epistemically bounded:
never "allowed", because ContextOS cannot guarantee complete coverage.

Every verdict is persisted (guard_verdicts) as the offline eval set.
"""

import logging
import time
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.decision import Decision
from src.models.decision_guard import GuardVerdict
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

STATUS_NO_CONFLICT = "no_known_conflict"
STATUS_POTENTIAL = "potential_conflict"
STATUS_REQUIRES_REVIEW = "requires_review"
_VALID = {STATUS_NO_CONFLICT, STATUS_POTENTIAL, STATUS_REQUIRES_REVIEW}

RETRIEVAL_LIMIT = 8
SIMILARITY_FLOOR = 0.1

_GUARD_SYSTEM = (
    "You advise an AI coding agent whether a proposed action conflicts with the "
    "engineering organization's active decisions. You are ADVISORY, never a gate. "
    "Choose exactly one status:\n"
    "no_known_conflict - no active decision is contradicted by this action.\n"
    "potential_conflict - an active decision appears to be contradicted or "
    "narrowed by this action.\n"
    "requires_review - genuinely ambiguous, or a high-stakes decision is nearby "
    "and a human should look.\n"
    "Never claim the action is 'allowed' or 'safe' — you only see retrieved "
    "decisions, not the whole org. If a listed exception sanctions the apparent "
    "conflict, treat it as no_known_conflict. Prefer no_known_conflict when "
    "nothing is genuinely contradicted; prefer potential_conflict/requires_review "
    "only on real tension. Cite the decisions that drove your verdict."
)


class GuardAssessment(BaseModel):
    status: str
    rationale: str
    confidence: float


class CheckActionResult(BaseModel):
    status: str
    rationale: str
    confidence: float
    decisions: list[dict]


async def _relevant_decisions(
    session: AsyncSession, workspace_id: UUID, action: str
) -> list[Decision]:
    stmt = (
        select(Decision)
        .where(
            Decision.workspace_id == workspace_id,
            Decision.status == "active",
            Decision.deleted_at.is_(None),  # type: ignore[union-attr]
            func.similarity(Decision.statement, action) >= SIMILARITY_FLOOR,
        )
        .order_by(func.similarity(Decision.statement, action).desc())
        .limit(RETRIEVAL_LIMIT)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _active_exceptions(
    session: AsyncSession, workspace_id: UUID, decision_ids: list[UUID]
) -> dict[str, list[str]]:
    """decision_id -> [exception scope/reason strings] for unexpired exceptions."""
    if not decision_ids:
        return {}
    result = await session.execute(
        sa_text(
            """
            SELECT decision_id, scope, reason
            FROM decision_exceptions
            WHERE workspace_id = :ws
              AND deleted_at IS NULL
              AND (expires_at IS NULL OR expires_at > now())
              AND decision_id = ANY(CAST(:ids AS uuid[]))
            """
        ),
        {"ws": str(workspace_id), "ids": [str(d) for d in decision_ids]},
    )
    out: dict[str, list[str]] = {}
    for row in result.fetchall():
        out.setdefault(str(row[0]), []).append(
            f"{row[1]}" + (f" — {row[2]}" if row[2] else "")
        )
    return out


async def check_action(
    session: AsyncSession,
    workspace_id: UUID,
    action: str,
    actor: str,
    scope: dict | None = None,
) -> CheckActionResult:
    """Advisory conflict assessment; persists the verdict. Never raises on LLM
    failure — degrades to requires_review (safe: defers to a human)."""
    started = time.monotonic()
    decisions = await _relevant_decisions(session, workspace_id, action)

    if not decisions:
        result = CheckActionResult(
            status=STATUS_NO_CONFLICT,
            rationale=(
                "No active decision appears relevant. No known conflict — but "
                "coverage may be incomplete."
            ),
            confidence=0.5,
            decisions=[],
        )
        await _persist(session, workspace_id, action, scope, result, [], actor, started)
        return result

    exceptions = await _active_exceptions(
        session, workspace_id, [d.id for d in decisions]
    )
    listing = []
    for d in decisions:
        line = f"- [{d.id}] {d.statement} (status: {d.status})"
        exc = exceptions.get(str(d.id))
        if exc:
            line += f"\n    EXCEPTION: {'; '.join(exc)}"
        listing.append(line)

    prompt = (
        f"Proposed action:\n{action}\n\n"
        f"Scope: {scope or {}}\n\n"
        f"Active decisions that may be relevant:\n" + "\n".join(listing) + "\n\n"
        "Assess the conflict."
    )
    try:
        client = get_llm_client()
        assessment = await client.generate_json(
            prompt,
            GuardAssessment,
            system_prompt=_GUARD_SYSTEM,
            workspace_id=workspace_id,
        )
        status = (
            assessment.status
            if assessment.status in _VALID
            else STATUS_REQUIRES_REVIEW
        )
        rationale = assessment.rationale
        confidence = max(0.0, min(1.0, assessment.confidence))
    except Exception:
        logger.exception("guard assessment LLM call failed")
        status, rationale, confidence = (
            STATUS_REQUIRES_REVIEW,
            "Assessment unavailable; deferring to human review.",
            0.0,
        )

    result = CheckActionResult(
        status=status,
        rationale=rationale,
        confidence=confidence,
        decisions=[
            {
                "id": str(d.id),
                "statement": d.statement,
                "status": d.status,
                "consequentiality_score": d.consequentiality_score,
                "has_exception": str(d.id) in exceptions,
            }
            for d in decisions
        ],
    )
    await _persist(
        session,
        workspace_id,
        action,
        scope,
        result,
        [d.id for d in decisions],
        actor,
        started,
    )
    return result


async def _persist(
    session: AsyncSession,
    workspace_id: UUID,
    action: str,
    scope: dict | None,
    result: CheckActionResult,
    decision_ids: list[UUID],
    actor: str,
    started: float,
) -> None:
    session.add(
        GuardVerdict(
            workspace_id=workspace_id,
            proposed_action=action,
            scope=scope or {},
            status=result.status,
            rationale=result.rationale,
            confidence=result.confidence,
            considered_decision_ids=[str(d) for d in decision_ids],
            actor=actor,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
    )
    await session.commit()
