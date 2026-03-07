"""LLM extraction service: schemas, content filter, source validation, content hash.

Provides the pure-function foundation for Gemini Flash structured extraction:
- Pydantic schemas for Decision and Blocker extraction output (no defaults for Gemini SDK)
- Content pre-filter to skip bot, short, and emoji-only messages before LLM calls
- Source text validation to drop hallucinated entities
- SHA-256 content hash for deduplication
"""

import hashlib
import logging
import re

from pydantic import BaseModel, Field

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
