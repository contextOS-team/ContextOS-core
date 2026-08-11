"""Skeptical verifier: try to prove a candidate drift is NOT meaningful.

The last gate before a drift reaches a human. Its instruction is adversarial
by design — only findings that survive an active refutation attempt surface.
Every verdict (including kills) is persisted on the drift/observation trail
for the eval gold sets.
"""

import logging

from pydantic import BaseModel

from src.models.decision import Decision
from src.models.decision_drift import ArtifactObservation, ExpectedConsequence
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

_VERIFIER_SYSTEM = (
    "You are a skeptical reviewer for a decision-drift detector. Your job is "
    "to PROVE the candidate finding is NOT a meaningful drift. Work through "
    "the checklist: (1) Is the underlying decision actually consequential? "
    "(2) Is the decision still active, or plausibly superseded? (3) Is this "
    "artifact really affected by the decision? (4) Could the apparent "
    "contradiction be intentional or already explained by another artifact? "
    "(5) Is this a semantic wording difference rather than real drift? "
    "(6) Would a CTO or engineering manager genuinely care? Only if every "
    "refutation fails, conclude is_meaningful_drift=true. When killing a "
    "finding, name the checklist item in kill_reason. Be strict: a drift "
    "detector that cries wolf is worthless."
)


class VerifierVerdict(BaseModel):
    is_meaningful_drift: bool
    kill_reason: str | None
    severity: str
    summary: str
    confidence: float


async def verify_drift(
    decision: Decision,
    consequence: ExpectedConsequence,
    observation: ArtifactObservation,
) -> VerifierVerdict | None:
    """One adversarial LLM pass; None on failure (finding is then dropped —
    an unverified drift never reaches a human)."""
    evidence_lines = "\n".join(
        f"- [{e.get('source_type')}] {e.get('excerpt', '')[:200]}"
        for e in (observation.evidence or [])[:6]
    )
    prompt = (
        f"Decision:\n{decision.statement}\n"
        f"Decision rationale: {decision.rationale or '-'}\n"
        f"Decision consequentiality score: {decision.consequentiality_score}\n\n"
        f"Expected consequence ({consequence.importance} importance):\n"
        f"{consequence.expected_state}\n\n"
        f"Checker observed:\n{observation.observed_state}\n\n"
        f"Evidence excerpts:\n{evidence_lines}\n\n"
        "Try to refute this as a meaningful drift. severity: high/medium/low. "
        "summary: one sentence a CTO would read."
    )
    try:
        client = get_llm_client()
        verdict = await client.generate_json(
            prompt,
            VerifierVerdict,
            system_prompt=_VERIFIER_SYSTEM,
            workspace_id=decision.workspace_id,
        )
    except Exception:
        logger.exception("skeptical verifier LLM call failed")
        return None
    if verdict.severity not in ("high", "medium", "low"):
        verdict.severity = "medium"
    return verdict
