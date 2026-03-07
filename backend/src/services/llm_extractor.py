"""LLM extraction service: Gemini Flash structured extraction, graph persistence.

Provides:
- Pydantic schemas for Decision and Blocker extraction output (no defaults for Gemini SDK)
- Content pre-filter to skip bot, short, and emoji-only messages before LLM calls
- Source text validation to drop hallucinated entities
- SHA-256 content hash for deduplication
- Gemini Flash extraction with structured output (extract_entities)
- Decision and blocker persistence to graph nodes and edges
"""

import hashlib
import logging
import re
from uuid import UUID

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.config import get_settings

logger = logging.getLogger(__name__)

# ============================================================
# Pydantic Extraction Schemas (no defaults -- Gemini SDK requirement)
# ============================================================


class ExtractedDecision(BaseModel):
    """A decision extracted from source text by LLM.

    All fields are required with no defaults -- the Gemini SDK rejects
    response_schema models that have default field values.
    """

    description: str = Field(description="What was decided, in one sentence")
    rationale: str = Field(description="Why this decision was made")
    source_quote: str = Field(
        description="Exact quote from the source text that contains the decision"
    )
    confidence: float = Field(description="Confidence score 0.0-1.0 that this is a real decision")
    person_name: str = Field(
        description="Name or handle of the person who made the decision, or empty string if unclear"
    )
    ticket_refs: list[str] = Field(
        description="Ticket identifiers mentioned in context of this decision, e.g. ENG-123"
    )


class ExtractedBlocker(BaseModel):
    """A blocker extracted from source text by LLM.

    All fields are required with no defaults.
    """

    description: str = Field(description="What is blocked and why")
    source_quote: str = Field(description="Exact quote from the source text")
    confidence: float = Field(description="Confidence score 0.0-1.0")


class ExtractionResult(BaseModel):
    """Aggregated extraction output from a single LLM call."""

    decisions: list[ExtractedDecision]
    blockers: list[ExtractedBlocker]


# ============================================================
# Content Pre-Filter
# ============================================================

_EMOJI_ONLY_PATTERN = re.compile(
    r"^[\s"
    r"\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF"  # flags
    r"\U00002702-\U000027B0"  # dingbats
    r"\U0000FE00-\U0000FE0F"  # variation selectors
    r"\U0000200D"  # zero width joiner
    r"]+$"
)


def should_skip_for_llm(
    text: str,
    user_id: str | None = None,
    bot_id: str | None = None,
) -> bool:
    """Return True if content should be skipped for LLM extraction.

    Filters out content that would waste Gemini API budget:
    - Bot messages (any bot_id present)
    - Short messages (< 50 chars after stripping)
    - Emoji-only content (no substantive text)
    """
    # Bot messages
    if bot_id:
        return True

    stripped = text.strip()

    # Short messages (< 50 chars)
    if len(stripped) < 50:
        return True

    # Emoji-only content
    if _EMOJI_ONLY_PATTERN.match(stripped):
        return True

    return False


# ============================================================
# Source Text Validation (Anti-Hallucination)
# ============================================================


def validate_extraction(result: ExtractionResult, original_content: str) -> ExtractionResult:
    """Remove extracted entities whose source_quote is not found in original text.

    Performs case-insensitive substring matching to catch minor LLM case
    adjustments while still verifying the quote exists in the source.
    """
    content_lower = original_content.lower()

    valid_decisions = []
    for decision in result.decisions:
        if decision.source_quote.lower() in content_lower:
            valid_decisions.append(decision)
        else:
            logger.warning(
                "Hallucinated decision dropped: quote '%.80s' not found in source",
                decision.source_quote,
            )

    valid_blockers = []
    for blocker in result.blockers:
        if blocker.source_quote.lower() in content_lower:
            valid_blockers.append(blocker)
        else:
            logger.warning(
                "Hallucinated blocker dropped: quote '%.80s' not found in source",
                blocker.source_quote,
            )

    return ExtractionResult(decisions=valid_decisions, blockers=valid_blockers)


# ============================================================
# Content Hash Deduplication
# ============================================================


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of whitespace-normalized content for deduplication.

    Normalizes whitespace (collapses multiple spaces, strips leading/trailing)
    but preserves case -- different-cased content is semantically different.
    """
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


# ============================================================
# Extraction System Prompt
# ============================================================

EXTRACTION_SYSTEM_PROMPT = """\
You are an entity extraction assistant for engineering team communications.
Extract decisions and blockers from the provided text.

Rules:
- Only extract entities that are explicitly stated in the text
- The source_quote MUST be an exact substring of the input text -- do not paraphrase
- Do not infer or fabricate entities that are not directly stated
- If no decisions or blockers are found, return empty lists

Decision language indicators (look for these patterns):
- "agreed", "decided", "going with", "let's do", "approved"
- Statements that resolve a choice between alternatives
- Explicit commitments to a course of action

Confidence calibration:
- 1.0 = explicit decision language ("we decided", "agreed to", "going with")
- 0.7-0.9 = strong implication of a decision
- 0.5-0.7 = possible decision, ambiguous language
- Below 0.5 = do not extract

For person_name: use the name or handle of the person who made the decision.
If unclear, use an empty string.

For ticket_refs: extract any ticket identifiers mentioned in the context
of the decision (e.g., ENG-123, PROJ-456). If none, use an empty list.
"""


# ============================================================
# Gemini Client
# ============================================================


def get_gemini_client() -> genai.Client:
    """Create a Gemini client using the project's API key."""
    settings = get_settings()
    return genai.Client(api_key=settings.GEMINI_API_KEY)


# ============================================================
# Gemini Extraction Service
# ============================================================


async def extract_entities(
    client: genai.Client,
    content: str,
    source_type: str,
) -> ExtractionResult:
    """Extract semantic entities from content using Gemini Flash structured output.

    Calls Gemini with temperature=0 and Pydantic response_schema for type-safe
    extraction. Validates results against source text before returning.

    Args:
        client: Gemini API client instance.
        content: The text content to extract entities from.
        source_type: Type of source (e.g. 'slack_message', 'meeting_transcript').

    Returns:
        Validated ExtractionResult with decisions and blockers.
    """
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"Extract decisions and blockers from this {source_type}:\n\n{content}",
        config=types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ExtractionResult,
            temperature=0,
        ),
    )
    result: ExtractionResult = response.parsed
    return validate_extraction(result, content)


# ============================================================
# Graph Persistence: Decision and Blocker nodes + edges
# ============================================================

async def persist_decision(
    session,
    workspace_id: UUID,
    decision: ExtractedDecision,
    source_node_id: UUID,
    author_node_id: UUID | None = None,
) -> UUID:
    """Create Decision node and edges from extraction result.

    Creates:
    - Decision node with all extraction properties
    - 'discussed_in' edge: Decision -> source_node_id
    - 'authored_by' edge: Decision -> author_node_id (if provided)
    - 'references' edges: Decision -> Ticket nodes (for each ticket_ref)

    External ID uses hash of source_quote for deterministic dedup -- same
    quote from the same source always maps to the same Decision node.

    Args:
        session: Async database session.
        workspace_id: Workspace UUID.
        decision: Extracted decision from Gemini.
        source_node_id: UUID of the source content node (SlackThread, Meeting, etc.).
        author_node_id: Optional UUID of the Person node who authored the decision.

    Returns:
        UUID of the created/updated Decision node.
    """
    from src.services import graph_ops

    external_id = f"decision:{compute_content_hash(decision.source_quote)}"

    decision_node_id = await graph_ops.upsert_node(
        session=session,
        workspace_id=workspace_id,
        entity_type="Decision",
        external_id=external_id,
        name=decision.description[:100],
        properties={
            "description": decision.description,
            "rationale": decision.rationale,
            "source_quote": decision.source_quote,
            "confidence": decision.confidence,
            "status": "active",
            "extraction_model": "gemini-2.0-flash",
        },
    )

    # Edge: Decision -> discussed_in -> Source (SlackThread/Meeting)
    await graph_ops.upsert_edge(
        session=session,
        workspace_id=workspace_id,
        source_node_id=decision_node_id,
        target_node_id=source_node_id,
        relationship_type="discussed_in",
    )

    # Edge: Decision -> authored_by -> Person (if author known)
    if author_node_id is not None:
        await graph_ops.upsert_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=decision_node_id,
            target_node_id=author_node_id,
            relationship_type="authored_by",
        )

    # Edges: Decision -> references -> Ticket (for each ticket_ref)
    for ticket_ref in decision.ticket_refs:
        ticket_node_id = await graph_ops.upsert_node(
            session=session,
            workspace_id=workspace_id,
            entity_type="Ticket",
            external_id=ticket_ref,
            name=ticket_ref,
        )
        await graph_ops.upsert_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=decision_node_id,
            target_node_id=ticket_node_id,
            relationship_type="references",
        )

    return decision_node_id


async def persist_blocker(
    session,
    workspace_id: UUID,
    blocker: ExtractedBlocker,
    source_node_id: UUID,
) -> UUID:
    """Create Blocker node and edge from extraction result.

    Creates:
    - Blocker node with extraction properties
    - 'blocks' edge: Blocker -> source_node_id

    External ID uses hash of source_quote for deterministic dedup.

    Args:
        session: Async database session.
        workspace_id: Workspace UUID.
        blocker: Extracted blocker from Gemini.
        source_node_id: UUID of the source content node.

    Returns:
        UUID of the created/updated Blocker node.
    """
    from src.services import graph_ops

    external_id = f"blocker:{compute_content_hash(blocker.source_quote)}"

    blocker_node_id = await graph_ops.upsert_node(
        session=session,
        workspace_id=workspace_id,
        entity_type="Blocker",
        external_id=external_id,
        name=blocker.description[:100],
        properties={
            "description": blocker.description,
            "source_quote": blocker.source_quote,
            "confidence": blocker.confidence,
            "status": "active",
            "extraction_model": "gemini-2.0-flash",
        },
    )

    # Edge: Blocker -> blocks -> Source
    await graph_ops.upsert_edge(
        session=session,
        workspace_id=workspace_id,
        source_node_id=blocker_node_id,
        target_node_id=source_node_id,
        relationship_type="blocks",
    )

    return blocker_node_id


# ============================================================
# Single-Content Extraction Pipeline
# ============================================================

# Platform prefix mapping for author resolution
_AUTHOR_PREFIX: dict[str, str] = {
    "slack_message": "slack",
    "meeting_transcript": "meeting",
}


async def process_single_content(
    session,
    client: genai.Client,
    workspace_id: UUID,
    content: str,
    source_type: str,
    source_node_id: UUID,
    author_user_id: str | None = None,
    bot_id: str | None = None,
) -> dict:
    """Process a single content item through the full LLM extraction pipeline.

    Pipeline steps:
    1. Pre-filter via should_skip_for_llm (bot, short, emoji-only)
    2. Content hash dedup against source node properties
    3. Gemini extraction with validation (fail-silent on errors)
    4. Person resolution from author_user_id
    5. Persist decisions and blockers to graph
    6. Mark source node with extraction metadata

    Args:
        session: Async database session.
        client: Gemini API client instance.
        workspace_id: Workspace UUID.
        content: Text content to extract entities from.
        source_type: Type of source (e.g. 'slack_message', 'meeting_transcript').
        source_node_id: UUID of the source graph node.
        author_user_id: Optional platform user ID for person resolution.
        bot_id: Optional bot ID (if present, content is skipped).

    Returns:
        Stats dict with keys: extracted, skipped_filter, skipped_dedup,
        errors, decisions, blockers.
    """
    from src.services import graph_ops

    stats = {
        "extracted": 0,
        "skipped_filter": 0,
        "skipped_dedup": 0,
        "errors": 0,
        "decisions": 0,
        "blockers": 0,
    }

    # Step 1: Pre-filter
    if should_skip_for_llm(content, bot_id=bot_id):
        stats["skipped_filter"] = 1
        return stats

    # Step 2: Content hash dedup
    content_hash = compute_content_hash(content)
    source_node = await session.get(
        _get_graph_node_class(), source_node_id
    )
    if source_node and (source_node.properties or {}).get("llm_content_hash") == content_hash:
        stats["skipped_dedup"] = 1
        return stats

    # Step 3: Gemini extraction (fail-silent)
    try:
        result = await extract_entities(client, content, source_type)
    except Exception:
        logger.error(
            "LLM extraction failed for source_node %s", source_node_id, exc_info=True
        )
        stats["errors"] = 1
        return stats

    # Step 4: Person resolution
    author_node_id = None
    if author_user_id:
        prefix = _AUTHOR_PREFIX.get(source_type, source_type)
        external_id = f"{prefix}:{author_user_id}"
        author_node_id = await graph_ops.upsert_node(
            session=session,
            workspace_id=workspace_id,
            entity_type="Person",
            external_id=external_id,
            name=author_user_id,
        )

    # Step 5: Persist decisions and blockers
    for decision in result.decisions:
        await persist_decision(
            session, workspace_id, decision, source_node_id,
            author_node_id=author_node_id,
        )
        stats["decisions"] += 1

    for blocker in result.blockers:
        await persist_blocker(session, workspace_id, blocker, source_node_id)
        stats["blockers"] += 1

    # Step 6: Mark source node as extracted
    if source_node:
        from datetime import datetime, timezone

        props = dict(source_node.properties or {})
        props["llm_content_hash"] = content_hash
        props["llm_extracted_at"] = datetime.now(timezone.utc).isoformat()
        props["llm_extraction_model"] = "gemini-2.0-flash"
        source_node.properties = props

    stats["extracted"] = 1
    return stats


def _get_graph_node_class():
    """Lazy import of GraphNode to avoid circular/heavy imports at module level."""
    from src.models.graph_node import GraphNode
    return GraphNode
