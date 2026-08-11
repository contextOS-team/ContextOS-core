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
) -> UUID | None:
    """Persist an extracted decision through the canonical decision writer.

    The writer enforces the consequentiality gate (this producer is otherwise
    ungated) and duplicate collapse; on CREATE it also makes the graph mirror
    node. This function then wires the extraction-specific edges:
    - 'discussed_in' edge: Decision -> source_node_id
    - 'authored_by' edge: Decision -> author_node_id (if provided)
    - 'references' edges: Decision -> Ticket nodes (for each ticket_ref)

    Returns:
        UUID of the Decision graph node, or None when the consequentiality
        gate rejected the candidate (no node exists then).
    """
    from src.services import graph_ops
    from src.services.decision_writer import (
        DecisionDraft,
        EvidenceRef,
        WriteOutcome,
        create_decision,
    )

    source_node = await session.get(_get_graph_node_class(), source_node_id)
    evidence: list[EvidenceRef] = []
    if source_node is not None and source_node.source_type and source_node.source_id:
        evidence.append(
            EvidenceRef(
                source_type=source_node.source_type,
                source_id=source_node.source_id,
                quote=decision.source_quote,
            )
        )

    result = await create_decision(
        session,
        workspace_id,
        DecisionDraft(
            statement=decision.description,
            rationale=decision.rationale,
            producer="llm_extractor",
            evidence=evidence,
            confidence=decision.confidence,
        ),
        actor="system:llm_extractor",
        mirror_properties={
            "description": decision.description,
            "rationale": decision.rationale,
            "source_quote": decision.source_quote,
            "confidence": decision.confidence,
            "extraction_model": "gemini-2.0-flash",
        },
    )
    if result.outcome is WriteOutcome.REJECTED_NOT_CONSEQUENTIAL:
        return None
    decision_node_id = result.graph_node_id
    if decision_node_id is None:
        return None

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
        node_id = await persist_decision(
            session, workspace_id, decision, source_node_id,
            author_node_id=author_node_id,
        )
        if node_id is not None:
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


# ============================================================
# Batch Extraction Pipeline
# ============================================================

# Source types that warrant LLM extraction (unstructured text content)
DEFAULT_LLM_SOURCE_TYPES = ["slack_message", "meeting_transcript"]


def _get_async_session():
    """Lazy import of async_session to avoid DB/sqlmodel imports at module level."""
    from src.db import async_session
    return async_session()


async def _query_source_records(session, source_type: str) -> list:
    """Query all non-deleted records for a given source type.

    Returns a list of ORM records with id, workspace_id, text/transcript,
    and author metadata.
    """
    from sqlmodel import select

    if source_type == "slack_message":
        from src.models.slack import SlackMessage
        stmt = select(SlackMessage).where(
            SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    elif source_type == "meeting_transcript":
        from src.models.meeting import MeetingTranscript
        stmt = select(MeetingTranscript).where(
            MeetingTranscript.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    else:
        logger.warning("Unknown source_type for LLM extraction: %s", source_type)
        return []


async def _find_source_node_id(session, workspace_id: UUID, source_type: str, record) -> UUID | None:
    """Look up the graph node for a source record by fingerprint.

    Uses the SOURCE_TYPE_TO_ENTITY mapping to determine entity type, then
    computes the fingerprint and queries for the matching graph node.

    Returns None if no matching graph node exists (rule-based extraction
    hasn't run yet for this record).
    """
    from src.services.graph_extractor import SOURCE_TYPE_TO_ENTITY
    from src.services import graph_ops

    entity_type = SOURCE_TYPE_TO_ENTITY.get(source_type)
    if not entity_type:
        return None

    # Determine external_id based on source_type (matching graph_backfill.py patterns)
    if source_type == "slack_message":
        external_id = record.slack_ts
    elif source_type == "meeting_transcript":
        external_id = str(record.id)
    else:
        external_id = str(record.id)

    # Compute fingerprint and query for node
    fingerprint = _compute_fingerprint(entity_type, external_id)
    GraphNode = _get_graph_node_class()

    from sqlmodel import select
    stmt = select(GraphNode).where(
        GraphNode.workspace_id == workspace_id,  # type: ignore[arg-type]
        GraphNode.fingerprint == fingerprint,
    )
    result = await session.execute(stmt)
    node = result.scalars().first()
    return node.id if node else None


def _compute_fingerprint(entity_type: str, external_id: str) -> str:
    """Compute fingerprint matching graph_ops.compute_fingerprint."""
    return hashlib.sha256(f"{entity_type}:{external_id}".encode()).hexdigest()


def _get_content_and_author(record, source_type: str) -> tuple[str, str | None, str | None]:
    """Extract content text, author_user_id, and bot_id from a source record.

    Returns:
        Tuple of (content, author_user_id, bot_id).
    """
    if source_type == "slack_message":
        content = record.text
        author_user_id = getattr(record, "user_id", None)
        bot_id = (getattr(record, "raw_data", None) or {}).get("bot_id")
        return content, author_user_id, bot_id

    elif source_type == "meeting_transcript":
        title = getattr(record, "title", None) or ""
        transcript = getattr(record, "transcript", "")
        content = f"{title}\n\n{transcript}".strip()
        return content, None, None

    else:
        return str(record), None, None


async def batch_extract_llm(
    workspace_id: UUID,
    source_types: list[str] | None = None,
    batch_size: int = 50,
    max_concurrent: int = 5,
) -> dict:
    """Batch LLM extraction pipeline for Slack messages and meeting transcripts.

    Processes source records in batches, applying content hash dedup,
    pre-filtering, Gemini extraction with asyncio.Semaphore rate limiting,
    and per-batch commits.

    Args:
        workspace_id: Workspace UUID to process.
        source_types: Source types to process (default: slack_message, meeting_transcript).
        batch_size: Number of records per batch commit.
        max_concurrent: Maximum concurrent Gemini API calls.

    Returns:
        Aggregate stats dict: extracted, skipped_filter, skipped_dedup, errors,
        decisions, blockers, source_types_processed.
    """
    import asyncio

    if source_types is None:
        source_types = list(DEFAULT_LLM_SOURCE_TYPES)

    client = get_gemini_client()
    semaphore = asyncio.Semaphore(max_concurrent)

    aggregate = {
        "extracted": 0,
        "skipped_filter": 0,
        "skipped_dedup": 0,
        "errors": 0,
        "decisions": 0,
        "blockers": 0,
        "source_types_processed": [],
    }

    async with _get_async_session() as session:
        for source_type in source_types:
            logger.info("LLM extraction: processing source_type=%s", source_type)
            records = await _query_source_records(session, source_type)
            total = len(records)

            if total == 0:
                logger.info("LLM extraction: no records for %s", source_type)
                continue

            aggregate["source_types_processed"].append(source_type)
            import math
            total_batches = max(1, math.ceil(total / batch_size))

            for i in range(0, total, batch_size):
                batch = records[i : i + batch_size]
                batch_num = (i // batch_size) + 1

                async def _process_one(record):
                    async with semaphore:
                        source_node_id = await _find_source_node_id(
                            session, workspace_id, source_type, record,
                        )
                        if source_node_id is None:
                            return {"extracted": 0, "skipped_filter": 0, "skipped_dedup": 0, "errors": 0, "decisions": 0, "blockers": 0}

                        content, author_user_id, bot_id = _get_content_and_author(record, source_type)
                        return await process_single_content(
                            session=session,
                            client=client,
                            workspace_id=workspace_id,
                            content=content,
                            source_type=source_type,
                            source_node_id=source_node_id,
                            author_user_id=author_user_id,
                            bot_id=bot_id,
                        )

                results = await asyncio.gather(
                    *[_process_one(record) for record in batch]
                )

                for stats in results:
                    for key in ("extracted", "skipped_filter", "skipped_dedup", "errors", "decisions", "blockers"):
                        aggregate[key] += stats.get(key, 0)

                await session.commit()
                logger.info(
                    "LLM extraction %s: batch %d/%d, %d records processed",
                    source_type, batch_num, total_batches, len(batch),
                )

    logger.info(
        "LLM extraction complete: %d extracted, %d skipped (filter=%d, dedup=%d), %d errors",
        aggregate["extracted"], aggregate["skipped_filter"] + aggregate["skipped_dedup"],
        aggregate["skipped_filter"], aggregate["skipped_dedup"], aggregate["errors"],
    )
    return aggregate
