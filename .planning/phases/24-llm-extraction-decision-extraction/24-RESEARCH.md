# Phase 24: LLM Extraction + Decision Extraction - Research

**Researched:** 2026-03-07
**Domain:** Gemini Flash structured output, LLM entity extraction, content hash deduplication, decision graph modeling
**Confidence:** HIGH

## Summary

This phase adds LLM-powered semantic extraction to the two-tier extraction system established in Phase 22. The existing rule-based extractors handle deterministic patterns (ticket refs, @mentions, PR numbers, file paths, URLs) inline at zero cost. Phase 24 adds Gemini Flash batch extraction for semantic entities that require language understanding -- decisions, rationale, blockers, and other entities that cannot be captured by regex. Decisions are the highest-value extraction target: linking what was decided, who decided it, where it was discussed, and which tickets it affects.

The project already has `google-genai` v1.4.0 installed with `GEMINI_API_KEY` configured in Settings. The SDK provides an async client (`client.aio.models.generate_content`) with native Pydantic structured output support -- passing a Pydantic model as `response_schema` returns a `parsed` attribute containing the validated model instance. This eliminates manual JSON parsing and provides schema-enforced extraction output. The existing graph infrastructure (graph_nodes, graph_edges, upsert operations, fingerprint deduplication) is ready to accept new entity types: the database CHECK constraint already includes `'Decision'` and `'Blocker'`, and relationship types include `'decided_in'`, `'authored_by'`, and `'blocks'`.

Content filtering (bot messages, short messages, emoji-only) already exists in `slack_events.py._should_filter()` for real-time ingestion. The batch LLM extraction pipeline needs its own pre-filter layer that applies similar rules before burning API budget. Content hash deduplication prevents re-processing already-extracted content and avoids duplicate entities. Source text traceability is critical to avoid hallucinated entities -- every extracted entity must reference the source text span it was derived from.

**Primary recommendation:** Build a new `llm_extractor.py` service using the existing `google-genai` SDK's Pydantic structured output. Use `gemini-2.0-flash` model with `temperature=0`, structured response schema, and source text validation. Follow the existing extractor registry pattern from Phase 22 for architecture, and the backfill pattern from `graph_backfill.py` for batch processing. Store content hashes in graph_node properties to enable deduplication.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXTR-03 | LLM extraction identifies decisions, rationale, blockers, and semantic entities from Slack messages and meeting transcripts | Gemini Flash structured output section provides the extraction prompt design, Pydantic schema, and entity-to-graph-node mapping. Covers Decision, Blocker entity types already in DB CHECK constraint |
| EXTR-04 | LLM extraction runs as batch background task via Gemini Flash with content hash deduplication | Batch processing section provides the content hash strategy (SHA-256 of normalized text), dedup lookup pattern, and batch orchestration following graph_backfill.py conventions |
| EXTR-05 | LLM extraction output is validated against source text to prevent hallucinated entities | Source validation section provides the text-span verification strategy: every extracted entity includes a source_quote field that must exist as substring in the original content |
| EXTR-06 | Content filtering skips bot messages, short messages, and emoji-only content before LLM extraction | Content filter section provides the pre-filter function: bot_id check, length < 50 chars, emoji-only regex, already-processed content hash check |
| DECIDE-01 | LLM extraction targets decision language in Slack messages and meeting transcripts | Decision extraction prompt section provides the system prompt and Pydantic schema targeting decision language patterns (agreed, decided, going with, let's do, approved) |
| DECIDE-02 | Decision nodes store description, rationale, source reference, date, confidence score, and status | Decision node schema section maps Pydantic extraction output to graph_node properties JSONB: description, rationale, source_ref, date, confidence, status fields |
| DECIDE-03 | Decisions link bidirectionally to Person, SlackThread/Meeting, and Ticket nodes | Decision edge creation section provides the edge creation pattern: decided_by -> Person, discussed_in -> SlackThread/Meeting, references -> Ticket, all using existing upsert_edge() |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | 1.4.0 | Gemini Flash API calls with async client and structured output | Already installed. SDK provides `client.aio.models.generate_content` with native Pydantic schema support |
| Pydantic | 2.0+ | Structured extraction schema definition | Already installed. Gemini SDK accepts Pydantic classes as `response_schema`, returns `parsed` as model instance |
| SQLModel | 0.0.22+ | GraphNode/GraphEdge ORM models | Already in use for all graph operations |
| SQLAlchemy | 2.0+ (asyncio) | Async DB operations, ON CONFLICT upserts | Already in use for all database operations |
| hashlib | stdlib | SHA-256 content hash for deduplication | Already used for fingerprint computation in graph_ops.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re | stdlib | Emoji-only content detection regex | Pre-filter before LLM extraction |
| asyncio | stdlib | Batch processing with concurrency control | Semaphore-based rate limiting for Gemini API |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Gemini Flash | OpenAI GPT-4o-mini | OpenAI is used for synthesis but Gemini Flash is cheaper ($0.10/M input vs ~$0.15/M). Project already has GEMINI_API_KEY configured. Use Gemini for extraction, keep OpenAI for synthesis |
| Pydantic structured output | Manual JSON parsing | Pydantic schema gives compile-time type safety, SDK validates response automatically, `parsed` field eliminates json.loads() + validation boilerplate |
| Content hash in properties | Separate tracking table | Simpler -- hash stored as property on the source node already created by rule-based extraction. No new migration needed |

**Installation:**
No new packages needed. All dependencies already in `backend/pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/services/
  llm_extractor.py            # Gemini client, structured extraction, content filtering
  llm_extraction_schemas.py   # Pydantic models for extraction output (or inline in llm_extractor.py)
  graph_extractor.py          # Existing: rule-based extractors + registry (unchanged)
  graph_ops.py                # Existing: upsert_node, upsert_edge (unchanged)
  graph_backfill.py           # Existing: batch backfill (may add LLM extraction entry point)

backend/tests/
  test_llm_extractor.py       # Unit tests with mocked Gemini responses
```

### Pattern 1: Gemini Flash Async Structured Output
**What:** Use the google-genai SDK's async client with Pydantic response schema to get type-safe extraction results.
**When to use:** Every LLM extraction call.
**Example:**
```python
# Source: google-genai SDK v1.4.0, verified against installed package
from google import genai
from google.genai import types
from pydantic import BaseModel

class ExtractedDecision(BaseModel):
    description: str
    rationale: str
    source_quote: str  # Must be substring of original content
    confidence: float  # 0.0 - 1.0
    # No default values -- Gemini SDK rejects defaults in response_schema

class ExtractionResult(BaseModel):
    decisions: list[ExtractedDecision]
    blockers: list[dict]  # simplified for example
    entities: list[dict]

client = genai.Client(api_key=settings.GEMINI_API_KEY)

response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents=f"Extract decisions and entities from:\n\n{content}",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ExtractionResult,
        temperature=0,
    ),
)

result: ExtractionResult = response.parsed  # Pydantic model instance
token_count = response.usage_metadata.total_token_count
```

### Pattern 2: Content Hash Deduplication
**What:** SHA-256 hash of normalized content text stored as property on the source graph node. Before LLM extraction, check if the hash already exists -- skip if so.
**When to use:** Every batch extraction run.
**Example:**
```python
import hashlib

def compute_content_hash(text: str) -> str:
    """Normalize and hash content for dedup."""
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()

# Check before calling Gemini
async def should_extract(session, workspace_id, source_node_id, content_hash):
    """Check if content has already been LLM-extracted."""
    node = await session.get(GraphNode, source_node_id)
    if node and node.properties.get("llm_content_hash") == content_hash:
        return False  # Already processed
    return True
```

### Pattern 3: Content Pre-Filter
**What:** Filter out content that should not burn LLM API budget before sending to Gemini.
**When to use:** Before every LLM extraction call.
**Example:**
```python
import re

_EMOJI_ONLY_PATTERN = re.compile(
    r"^[\s"
    r"\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF"  # flags
    r"\U00002702-\U000027B0"  # dingbats
    r"\U0000FE00-\U0000FE0F"  # variation selectors
    r"\U0000200D"             # zero width joiner
    r"]+$"
)

def should_skip_for_llm(text: str, user_id: str | None = None, bot_id: str | None = None) -> bool:
    """Return True if content should be skipped for LLM extraction."""
    # Bot messages
    if bot_id:
        return True
    # Short messages (< 50 chars per success criteria)
    if len(text.strip()) < 50:
        return True
    # Emoji-only content
    if _EMOJI_ONLY_PATTERN.match(text):
        return True
    return False
```

### Pattern 4: Source Text Validation (Anti-Hallucination)
**What:** Every extracted entity includes a `source_quote` field. After extraction, verify the quote exists as a substring in the original content.
**When to use:** After every LLM extraction response.
**Example:**
```python
def validate_extraction(result: ExtractionResult, original_content: str) -> ExtractionResult:
    """Remove extracted entities whose source_quote is not found in original."""
    content_lower = original_content.lower()

    valid_decisions = []
    for decision in result.decisions:
        if decision.source_quote.lower() in content_lower:
            valid_decisions.append(decision)
        else:
            logger.warning(
                "Hallucinated decision dropped: quote '%s' not found in source",
                decision.source_quote[:80],
            )

    # Return filtered result
    return ExtractionResult(
        decisions=valid_decisions,
        blockers=[b for b in result.blockers if _validate_quote(b, content_lower)],
        entities=[e for e in result.entities if _validate_quote(e, content_lower)],
    )
```

### Pattern 5: Decision-to-Graph Mapping
**What:** Map extracted Decision objects to graph nodes and edges using existing upsert operations.
**When to use:** After validated extraction.
**Example:**
```python
async def persist_decision(
    session: AsyncSession,
    workspace_id: UUID,
    decision: ExtractedDecision,
    source_node_id: UUID,
    source_type: str,
    author_user_id: str | None,
) -> UUID:
    """Create Decision node and edges from extraction result."""
    # Create Decision node
    # External ID: hash of source_quote for deterministic dedup
    external_id = f"decision:{compute_content_hash(decision.source_quote)}"

    decision_node_id = await upsert_node(
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
    await upsert_edge(
        session=session,
        workspace_id=workspace_id,
        source_node_id=decision_node_id,
        target_node_id=source_node_id,
        relationship_type="discussed_in",
    )

    # Edge: Decision -> authored_by -> Person (if author known)
    if author_user_id:
        person_node_id = await upsert_node(
            session=session,
            workspace_id=workspace_id,
            entity_type="Person",
            external_id=f"slack:{author_user_id}",
            name=f"Slack user {author_user_id}",
        )
        await upsert_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=decision_node_id,
            target_node_id=person_node_id,
            relationship_type="authored_by",
        )

    return decision_node_id
```

### Anti-Patterns to Avoid
- **Calling Gemini inline during webhook processing:** Burns API budget on every message. LLM extraction must be batch-only. Rule-based extractors remain inline.
- **Trusting LLM output without validation:** Never insert extracted entities without verifying source_quote exists in original content. Hallucinated entities pollute the graph and cannot be traced back.
- **Using default values in Pydantic extraction schemas:** The Gemini SDK rejects response_schema models with default field values. All fields must be required.
- **Re-extracting already-processed content:** Without content hash checking, the same Slack message gets extracted on every batch run, creating duplicate entities and wasting Gemini calls.
- **Single-call extraction for long transcripts:** Meeting transcripts can be very long. Chunk them into manageable segments (e.g., 4K tokens) and extract from each chunk separately, then merge results.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output parsing | Manual JSON.loads() + try/except + dict access | Gemini SDK `response_schema=PydanticModel` + `response.parsed` | SDK handles JSON parsing, schema validation, type coercion. Eliminates ~30 lines of error-prone parsing per extraction call |
| Content deduplication | Custom dedup table or Redis set | SHA-256 content hash in graph_node properties JSONB | Reuses existing graph infrastructure, no new migration, atomic with node upsert |
| Entity fingerprint computation | Custom ID schemes | `compute_fingerprint(entity_type, external_id)` from graph_ops.py | Proven pattern from Phase 22, deterministic, handles re-ingestion |
| Async rate limiting | Custom token bucket | `asyncio.Semaphore(max_concurrent)` | Standard library, proven pattern, prevents Gemini rate limit errors |

**Key insight:** The existing graph infrastructure (upsert_node, upsert_edge, fingerprint dedup, graph_backfill batch pattern) handles 90% of the persistence logic. This phase is primarily about the Gemini extraction layer and the Decision entity modeling.

## Common Pitfalls

### Pitfall 1: Gemini Structured Output Schema Rejection
**What goes wrong:** Pydantic models with `Optional` fields, default values, or complex union types cause the Gemini SDK to reject the schema at request time.
**Why it happens:** The Gemini API has a stricter subset of JSON Schema than standard Pydantic. Fields with `default=None` or `Optional[str]` trigger client-side validation errors.
**How to avoid:** All fields in extraction schemas must be required (no defaults). Use `str` instead of `Optional[str]`. If a field truly may be absent, use empty string as the sentinel value and document it in the schema description.
**Warning signs:** `ValueError` or schema validation errors from google-genai SDK before the API call is even made.

### Pitfall 2: Hallucinated Entity Extraction
**What goes wrong:** The LLM invents decisions or entities that are not actually present in the source text. These phantom entities pollute the graph and mislead downstream synthesis.
**Why it happens:** LLMs are prone to generating plausible-sounding content. With structured output forcing specific fields, the model may fabricate content to fill required fields.
**How to avoid:** Require `source_quote` in every extracted entity. Post-extraction validation checks that `source_quote` is a substring of the original content. Drop any entity that fails this check.
**Warning signs:** Extracted entities with source_quote text that reads like a paraphrase rather than a direct quote.

### Pitfall 3: API Budget Waste on Low-Value Content
**What goes wrong:** Sending every Slack message to Gemini burns API budget on "ok", "lol", "+1", emoji reactions, and bot notifications.
**Why it happens:** No pre-filter before the LLM call. The success criteria specifically requires filtering bot messages, short messages (<50 chars), and emoji-only content.
**How to avoid:** Pre-filter function runs before any Gemini call. The 50-char threshold (not 10 as in real-time filtering) is specifically for LLM extraction cost optimization.
**Warning signs:** High Gemini API costs with very few extracted entities. Most responses returning empty extraction results.

### Pitfall 4: Duplicate Entities on Re-Run
**What goes wrong:** Running batch extraction twice on the same content creates duplicate Decision nodes with different UUIDs.
**Why it happens:** Without content hash dedup, the batch processor re-sends content to Gemini and re-inserts entities.
**How to avoid:** Two-layer dedup: (1) Content hash check skips already-extracted content. (2) Entity fingerprint dedup (existing upsert_node ON CONFLICT) prevents duplicate nodes even if extraction runs again. Both layers are needed -- content hash saves API cost, fingerprint dedup prevents duplicate graph nodes.
**Warning signs:** Multiple Decision nodes with similar descriptions linking to the same source.

### Pitfall 5: Meeting Transcript Length Exceeding Context Window
**What goes wrong:** Long meeting transcripts (30-60 min) can be 5K-20K tokens. Sending the full transcript in a single extraction call may hit quality degradation or context limits.
**Why it happens:** Gemini 2.0 Flash has a 1M token context window, so it technically fits, but extraction quality degrades with very long inputs.
**How to avoid:** Chunk long transcripts into segments of ~4K tokens. Extract from each chunk separately. Use meeting segment boundaries (from MeetingSegment table) as natural chunk points. Merge and deduplicate extracted entities across chunks.
**Warning signs:** Extraction returning fewer entities from long transcripts than from shorter ones covering the same content.

## Code Examples

Verified patterns from the installed SDK and existing codebase:

### Gemini Client Initialization
```python
# Source: google-genai SDK v1.4.0 installed in project venv
from google import genai
from src.config import get_settings

def get_gemini_client() -> genai.Client:
    """Create a Gemini client using the project's API key."""
    settings = get_settings()
    return genai.Client(api_key=settings.GEMINI_API_KEY)
```

### Full Extraction Call with Structured Output
```python
# Source: google-genai SDK v1.4.0, verified async interface
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class ExtractedDecision(BaseModel):
    description: str = Field(description="What was decided, in one sentence")
    rationale: str = Field(description="Why this decision was made")
    source_quote: str = Field(description="Exact quote from the source text that contains the decision")
    confidence: float = Field(description="Confidence score 0.0-1.0 that this is a real decision")
    person_name: str = Field(description="Name or handle of the person who made the decision, or empty string if unclear")
    ticket_refs: list[str] = Field(description="Ticket identifiers mentioned in context of this decision, e.g. ENG-123")

class ExtractedBlocker(BaseModel):
    description: str = Field(description="What is blocked and why")
    source_quote: str = Field(description="Exact quote from the source text")
    confidence: float = Field(description="Confidence score 0.0-1.0")

class ExtractionResult(BaseModel):
    decisions: list[ExtractedDecision]
    blockers: list[ExtractedBlocker]

EXTRACTION_SYSTEM_PROMPT = """\
You are an entity extraction assistant for engineering team communications.
Extract decisions and blockers from the provided text.

Rules:
- Only extract entities that are explicitly stated in the text
- The source_quote MUST be an exact substring of the input text
- Do not paraphrase or infer -- only extract what is directly stated
- If no decisions or blockers are found, return empty lists
- Confidence should reflect how clearly the text states the entity:
  1.0 = explicit decision language ("we decided", "agreed to", "going with")
  0.7-0.9 = strong implication of decision
  0.5-0.7 = possible decision, ambiguous language
  Below 0.5 = do not extract
"""

async def extract_entities(
    client: genai.Client,
    content: str,
    source_type: str,
) -> ExtractionResult:
    """Extract semantic entities from content using Gemini Flash."""
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
    return response.parsed
```

### Content Hash for Deduplication
```python
# Source: follows existing graph_ops.py fingerprint pattern
import hashlib

def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized content for dedup."""
    normalized = " ".join(text.strip().split())  # normalize whitespace
    return hashlib.sha256(normalized.encode()).hexdigest()

async def mark_as_extracted(
    session: AsyncSession,
    source_node_id: UUID,
    content_hash: str,
    extraction_model: str,
) -> None:
    """Mark a source node as LLM-extracted by storing content hash."""
    from src.models.graph_node import GraphNode
    node = await session.get(GraphNode, source_node_id)
    if node:
        props = dict(node.properties or {})
        props["llm_content_hash"] = content_hash
        props["llm_extracted_at"] = datetime.now(timezone.utc).isoformat()
        props["llm_extraction_model"] = extraction_model
        node.properties = props
```

### Batch Processing Following Existing Backfill Pattern
```python
# Source: follows graph_backfill.py pattern exactly
async def batch_extract_slack_messages(
    workspace_id: UUID,
    batch_size: int = 50,
    max_concurrent: int = 5,
) -> dict:
    """Batch LLM extraction for Slack messages."""
    client = get_gemini_client()
    semaphore = asyncio.Semaphore(max_concurrent)

    async with async_session() as session:
        stmt = select(SlackMessage).where(
            SlackMessage.workspace_id == workspace_id,
            SlackMessage.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        extracted = 0
        skipped = 0

        for i in range(0, len(messages), batch_size):
            batch = messages[i : i + batch_size]
            for msg in batch:
                # Pre-filter
                if should_skip_for_llm(msg.text, bot_id=msg.raw_data.get("bot_id")):
                    skipped += 1
                    continue

                # Content hash dedup
                content_hash = compute_content_hash(msg.text)
                if not await should_extract(session, workspace_id, msg.id, content_hash):
                    skipped += 1
                    continue

                # Extract with rate limiting
                async with semaphore:
                    result = await extract_entities(client, msg.text, "slack_message")

                # Validate and persist
                validated = validate_extraction(result, msg.text)
                await persist_extraction_results(
                    session, workspace_id, validated,
                    source_node_id=...,  # lookup from graph
                    source_type="slack_message",
                    author_user_id=msg.user_id,
                )

                await mark_as_extracted(session, ..., content_hash, "gemini-2.0-flash")
                extracted += 1

            await session.commit()

    return {"extracted": extracted, "skipped": skipped}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| google-generativeai (old SDK) | google-genai (unified SDK) | 2024-2025 | New SDK has async support, Pydantic response_schema, unified API |
| Manual JSON parsing of LLM output | response_schema + parsed field | google-genai v1.0+ | Eliminates parsing boilerplate, type-safe extraction |
| response_json_schema (dict-based) | response_schema (Pydantic class) | google-genai v1.0+ | Direct Pydantic class support, SDK converts response to model instance |
| gemini-1.5-flash | gemini-2.0-flash | Feb 2025 | Better structured output adherence, lower cost ($0.10/M input tokens) |

**Deprecated/outdated:**
- `google-generativeai` package: replaced by `google-genai`. Do NOT import from `google.generativeai`
- `genai.configure()` global setup: replaced by `genai.Client(api_key=...)` instance pattern
- `model.generate_content()` sync pattern: replaced by `client.aio.models.generate_content()` async pattern

## Open Questions

1. **Gemini rate limits for batch extraction**
   - What we know: Gemini Flash has generous rate limits (RPM varies by plan: free tier ~15 RPM, paid ~1000+ RPM)
   - What's unclear: Exact rate limits for the project's API key tier
   - Recommendation: Use `asyncio.Semaphore(5)` for conservative concurrency, add exponential backoff on 429 errors

2. **Decision external_id strategy for fingerprint dedup**
   - What we know: Existing entities use deterministic external_ids (e.g., ticket identifier, Slack user ID)
   - What's unclear: Decisions don't have a natural external identifier -- two extractions of the same decision could produce slightly different descriptions
   - Recommendation: Use `hash(source_quote)` as external_id since source_quote is validated to be an exact substring. Same quote = same decision = same fingerprint

3. **Ticket reference linking from decisions**
   - What we know: The LLM can extract ticket references from decision context (e.g., "decided to use Redis for CON-42")
   - What's unclear: Whether to link to existing Ticket nodes or create new unresolved ones
   - Recommendation: Use existing `TicketRefExtractor` output pattern -- create nodes with status=unresolved, fingerprint dedup will merge if the ticket exists

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_llm_extractor.py -x` |
| Full suite command | `cd backend && python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTR-03 | Gemini extracts decisions, blockers from Slack/meeting content | unit (mocked Gemini) | `cd backend && python -m pytest tests/test_llm_extractor.py::TestLLMExtraction -x` | Wave 0 |
| EXTR-04 | Content hash dedup prevents re-extraction, batch processing works | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestContentHashDedup -x` | Wave 0 |
| EXTR-05 | Source text validation drops hallucinated entities | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestSourceValidation -x` | Wave 0 |
| EXTR-06 | Pre-filter skips bot, short, emoji-only content | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestContentFilter -x` | Wave 0 |
| DECIDE-01 | Decision extraction targets decision language patterns | unit (mocked) | `cd backend && python -m pytest tests/test_llm_extractor.py::TestDecisionExtraction -x` | Wave 0 |
| DECIDE-02 | Decision nodes have all required properties | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestDecisionNodeSchema -x` | Wave 0 |
| DECIDE-03 | Decision nodes link bidirectionally to Person, Source, Ticket | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestDecisionEdges -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_llm_extractor.py -x`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_llm_extractor.py` -- covers EXTR-03, EXTR-04, EXTR-05, EXTR-06, DECIDE-01, DECIDE-02, DECIDE-03
- [ ] No new fixtures needed beyond existing conftest.py (mock_session, mock_settings already available)
- [ ] Gemini responses will be mocked -- no API key needed for tests

## Sources

### Primary (HIGH confidence)
- google-genai SDK v1.4.0 installed in project venv -- async client interface, structured output, Pydantic response_schema verified via Python introspection
- Existing codebase: graph_extractor.py, graph_ops.py, graph_backfill.py, slack_events.py -- all patterns verified by reading source code
- supabase/migrations/00017_graph_tables.sql -- entity_type CHECK constraint includes 'Decision' and 'Blocker', relationship_type CHECK includes 'decided_in', 'authored_by', 'blocks'
- backend/src/config.py -- GEMINI_API_KEY already in Settings class

### Secondary (MEDIUM confidence)
- [Google AI Structured Output docs](https://ai.google.dev/gemini-api/docs/structured-output) -- Pydantic schema pattern, response_mime_type requirement
- [googleapis/python-genai GitHub](https://github.com/googleapis/python-genai) -- SDK documentation and async patterns
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) -- $0.10/M input, $0.40/M output for gemini-2.0-flash

### Tertiary (LOW confidence)
- Gemini rate limits for specific API key tiers -- varies by plan, needs runtime validation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- google-genai 1.4.0 installed, async interface verified by introspection, GEMINI_API_KEY configured
- Architecture: HIGH -- follows existing graph_extractor.py registry pattern and graph_backfill.py batch pattern exactly
- Pitfalls: HIGH -- Pydantic schema restrictions verified against SDK source, hallucination prevention is well-understood pattern
- Decision modeling: HIGH -- entity_type 'Decision' and relationship_type 'decided_in' already in DB CHECK constraints from Phase 22

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable -- google-genai SDK and graph infrastructure are established)
