"""Six-way relation classification between a candidate and existing decisions.

A strong semantic match can mean several different things; the binary
suppress-or-create model loses that. Relations and their write actions:

  SAME        -> merge as duplicate evidence on the existing decision
  SUPPORTS    -> reinforce: attach evidence to the existing decision
  SUPERSEDES  -> create new decision + supersedes edge + review proposal
  CONTRADICTS -> create new decision + contradicts edge + review proposal
  REFINES     -> create new decision + refines edge (scope narrowing)
  UNRELATED   -> create a plain new decision

The classifier only ever *proposes* supersession/contradiction — status
transitions on the old decision remain a human action on the Review surface.
"""

import logging
from uuid import UUID

from pydantic import BaseModel

from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

RELATION_SAME = "SAME"
RELATION_SUPPORTS = "SUPPORTS"
RELATION_SUPERSEDES = "SUPERSEDES"
RELATION_CONTRADICTS = "CONTRADICTS"
RELATION_REFINES = "REFINES"
RELATION_UNRELATED = "UNRELATED"

RELATIONS = {
    RELATION_SAME,
    RELATION_SUPPORTS,
    RELATION_SUPERSEDES,
    RELATION_CONTRADICTS,
    RELATION_REFINES,
    RELATION_UNRELATED,
}

MERGE_RELATIONS = {RELATION_SAME, RELATION_SUPPORTS}
EDGE_RELATIONS = {RELATION_SUPERSEDES, RELATION_CONTRADICTS, RELATION_REFINES}
PROPOSAL_RELATIONS = {RELATION_SUPERSEDES, RELATION_CONTRADICTS}

RELATION_MIN_CONFIDENCE = 0.7


class RelationVerdict(BaseModel):
    relation: str
    confidence: float
    rationale: str


_RELATION_SYSTEM = (
    "You compare two engineering-organization decision records and classify "
    "how the NEW candidate relates to the EXISTING decision. Answer with "
    "exactly one relation:\n"
    "SAME - the same decision, possibly reworded or re-discussed.\n"
    "SUPPORTS - a new mention reinforcing the existing decision without "
    "changing it.\n"
    "SUPERSEDES - same topic but the commitment changed; the new decision "
    "replaces the existing one (e.g. a date moved, an approach swapped).\n"
    "CONTRADICTS - same topic with incompatible commitments and no sign the "
    "team consciously replaced the old one.\n"
    "REFINES - narrows scope, adds an exception, or specializes the existing "
    "decision without replacing it.\n"
    "UNRELATED - different decisions that merely share vocabulary.\n"
    "Be conservative: prefer UNRELATED over a low-confidence strong relation."
)


async def classify_decision_relation(
    workspace_id: UUID,
    new_statement: str,
    new_rationale: str | None,
    existing_statement: str,
    existing_rationale: str | None = None,
) -> RelationVerdict | None:
    """One structured LLM call; None on failure (caller treats as UNRELATED)."""
    prompt = (
        f"EXISTING decision:\n{existing_statement}\n"
        f"Rationale: {existing_rationale or '-'}\n\n"
        f"NEW candidate:\n{new_statement}\n"
        f"Rationale: {new_rationale or '-'}\n\n"
        "Classify the relation of the NEW candidate to the EXISTING decision."
    )
    try:
        client = get_llm_client()
        verdict = await client.generate_json(
            prompt,
            RelationVerdict,
            system_prompt=_RELATION_SYSTEM,
            workspace_id=workspace_id,
        )
    except Exception:
        logger.exception("relation classification LLM call failed")
        return None
    if verdict.relation not in RELATIONS:
        logger.warning("classifier returned unknown relation %r", verdict.relation)
        return None
    return verdict
