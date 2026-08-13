"""Impact inference: derive expected consequences from a confirmed decision.

One structured LLM call per decision produces up to MAX_CONSEQUENCES
ExpectedConsequence rows — explicit, checkable predictions of what should
have changed in trackers, code, and docs because of the decision.
"""

import logging
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.decision import Decision
from src.models.decision_drift import CONSEQUENCE_TARGET_TYPES, ExpectedConsequence
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

MAX_CONSEQUENCES = 5

_IMPACT_SYSTEM = (
    "You are an impact analyst for an engineering organization's decision log. "
    "Given a decision, predict what SHOULD have changed because of it — as "
    "concrete, individually checkable expectations. Allowed target_type values: "
    "linear (tickets/cycles), jira (issues), github (PRs/branches/code), docs "
    "(Notion/wiki pages), release (release plans/dates), other. For each "
    "expectation give target_query (a short search phrase locating the affected "
    "artifacts), expected_state (what the artifacts should now say/be), a brief "
    "rationale, importance (high/medium/low), and confidence 0-1. Only predict "
    "consequences the decision genuinely implies; fewer, sharper expectations "
    "beat exhaustive speculation. An empty list is a valid answer for decisions "
    "with no artifact footprint."
)


class ConsequenceDraft(BaseModel):
    target_type: str
    target_query: str
    expected_state: str
    rationale: str
    importance: str
    confidence: float


class ImpactInferenceResult(BaseModel):
    consequences: list[ConsequenceDraft]


async def infer_expected_consequences(
    session: AsyncSession, decision: Decision
) -> list[ExpectedConsequence]:
    """Infer and persist consequences for a decision. Idempotent per decision:
    returns existing rows if inference already ran."""
    existing = (
        (
            await session.execute(
                select(ExpectedConsequence).where(
                    ExpectedConsequence.decision_id == decision.id,
                    ExpectedConsequence.deleted_at.is_(None),  # type: ignore[union-attr]
                )
            )
        )
        .scalars()
        .all()
    )
    if existing:
        return list(existing)

    prompt = (
        f"Decision:\n{decision.statement}\n\n"
        f"Rationale:\n{decision.rationale or '-'}\n\n"
        "Predict the expected consequences."
    )
    try:
        client = get_llm_client()
        result = await client.generate_json(
            prompt,
            ImpactInferenceResult,
            system_prompt=_IMPACT_SYSTEM,
            workspace_id=decision.workspace_id,
        )
    except Exception:
        logger.exception("impact inference LLM call failed for %s", decision.id)
        return []

    rows: list[ExpectedConsequence] = []
    for draft in result.consequences[:MAX_CONSEQUENCES]:
        if draft.target_type not in CONSEQUENCE_TARGET_TYPES:
            draft.target_type = "other"
        if draft.importance not in ("high", "medium", "low"):
            draft.importance = "medium"
        row = ExpectedConsequence(
            workspace_id=decision.workspace_id,
            decision_id=decision.id,
            target_type=draft.target_type,
            target_query=draft.target_query,
            expected_state=draft.expected_state,
            rationale=draft.rationale,
            importance=draft.importance,
            confidence=max(0.0, min(1.0, draft.confidence)),
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def decisions_needing_inference(
    session: AsyncSession,
    workspace_id: UUID,
    limit: int = 50,
    min_consequentiality: float = 0.6,
) -> list[Decision]:
    """Active, consequential decisions with no expected consequences yet.

    The consequentiality floor keeps low-scoring junk ("schedule a meeting")
    out of the drift pipeline — inferring/checking those wastes LLM calls and
    can only produce noise. NULL scores (never gated) are included so they get
    a first look.
    """
    stmt = (
        select(Decision)
        .outerjoin(
            ExpectedConsequence,
            ExpectedConsequence.decision_id == Decision.id,
        )
        .where(
            Decision.workspace_id == workspace_id,
            Decision.status == "active",
            Decision.deleted_at.is_(None),  # type: ignore[union-attr]
            ExpectedConsequence.id.is_(None),  # type: ignore[union-attr]
            (Decision.consequentiality_score.is_(None))  # type: ignore[union-attr]
            | (Decision.consequentiality_score >= min_consequentiality),
        )
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
