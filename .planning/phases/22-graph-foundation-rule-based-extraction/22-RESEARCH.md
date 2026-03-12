# Phase 22: Graph Foundation + Rule-Based Extraction - Research

**Researched:** 2026-03-07
**Domain:** PostgreSQL graph schema, recursive CTE traversal, regex entity extraction, Supabase RLS
**Confidence:** HIGH

## Summary

This phase establishes the knowledge graph foundation in Supabase Postgres using plain tables (graph_nodes + graph_edges) with workspace-scoped RLS, fingerprint-based deduplication, and a SECURITY DEFINER traversal function using recursive CTEs. Simultaneously, it ships five deterministic regex extractors that populate graph entities from all ingested content at zero LLM cost.

The codebase already has well-established patterns for every building block: polymorphic source_type+source_id linking (embeddings table), SECURITY DEFINER functions (match_embeddings, hybrid_search), ON CONFLICT upserts with fingerprint deduplication (content_hash on embeddings), RLS policies (workspace_members membership check), moddatetime triggers, and inline post-upsert side effects (embedding.queue_embedding_generation calls in every webhook handler). The new graph tables and extractors follow these patterns exactly.

PostgreSQL 14+ provides native CYCLE and SEARCH clauses for recursive CTEs, eliminating the need for manual cycle detection. The traverse_graph() function validates workspace_id once at entry as SECURITY DEFINER, bypassing per-row RLS overhead during recursive traversal -- matching the proven pattern from match_embeddings() and hybrid_search().

**Primary recommendation:** Follow existing codebase conventions exactly. The graph schema mirrors the embeddings table pattern (polymorphic source linking, workspace-scoped RLS, JSONB metadata). Extractors follow the embedding.queue_embedding_generation post-upsert pattern. No new libraries needed -- this is pure SQL migrations + Python regex + SQLAlchemy.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Entity types: Expanded set from day one -- Person, Ticket, SlackThread, PR, CodeChunk, NotionPage, Meeting, Decision, Blocker, Feature, Component. Prepares schema for LLM extraction in Phase 24 even though rule-based extractors won't populate all types yet
- Source linking: Polymorphic source_type + source_id columns (same pattern as embeddings table). No nullable FK columns per type
- Fingerprint strategy: hash(entity_type + external_id), e.g. hash('Ticket:ENG-123') or hash('Person:slack:U12345'). Deterministic, survives re-ingestion. Unique constraint per workspace (workspace_id, fingerprint)
- Relationship types: Comprehensive taxonomy from start -- mentions, references, authored_by, assigned_to, discussed_in, implements, reviews, decided_in, blocks, same_as, parent_of. Ready for all phases
- Properties: JSONB column on both nodes and edges for flexible metadata storage
- Standard columns: workspace_id FK, created_at, updated_at, deleted_at (soft delete), follows existing schema conventions
- Regex extractors: All five patterns -- ticket refs (ENG-123, CON-45), @mentions (Slack user IDs, Linear usernames), PR/commit refs (#123, SHA prefixes), file paths (/src/..., .ts/.py extensions), URLs (links to Linear, GitHub, Notion, Slack that resolve to known entities)
- Content sources: All ingested content -- Slack messages, Linear tickets + comments, GitHub PRs + reviews, Notion pages, meeting transcripts/segments
- Source nodes: Extractors also create nodes for the source content itself (e.g., SlackThread node for the message being extracted from) so edges connect entity -> source. Full graph neighborhood from the start
- Unresolved references: Create dangling nodes with status='unresolved' in properties. When the referenced entity syncs later, the node gets updated via fingerprint match. No broken edges
- Hook location: Inline after upsert -- call extract_and_populate_graph() right after each record is upserted in webhook background tasks and sync services. Same transaction context, zero latency. Matches EXTR-02 requirement
- Backfill: One-time backfill script processes all existing content (Slack messages, tickets, PRs, Notion pages, meetings). Graph is immediately useful, not just for new content
- Error handling: Fail silently with warning logs. Graph extraction is additive -- if it fails, core ingestion (ticket upsert, embedding job) still succeeds. Graph data is best-effort
- Interface: Registry pattern -- each extractor (ticket_ref, mention, pr_ref, file_path, url) is a registered function. run_extractors(content, source_type) iterates the registry. Easy to add new extractors in Phase 24+
- Traversal depth limits: Default 2 hops, maximum 4
- Traversal direction: Supports outbound, inbound, or both (default). Optional direction parameter on traverse_graph()
- Return shape: Rich result -- (node_id, entity_type, name, properties, edge_relationship_type, depth, path). Callers can reconstruct subgraph or use flat list
- Traversal filtering: Optional entity_types[] and relationship_types[] parameters for targeted queries
- Traversal security: SECURITY DEFINER function validates workspace_id once at entry, bypasses per-row RLS overhead during recursive traversal

### Claude's Discretion
- Exact regex patterns and edge cases for each extractor
- SQL migration file numbering and ordering
- Backfill script batch size and concurrency
- Index selection beyond the required composites
- Test fixture design for graph traversal tests

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GRAPH-01 | Database has graph_nodes and graph_edges tables with workspace-scoped RLS, fingerprint deduplication, and JSONB properties | Schema design section provides exact DDL following existing migration patterns. RLS policy pattern from initial_schema.sql. Fingerprint uses SHA256 via encode(digest(), 'hex') |
| GRAPH-02 | traverse_graph() SECURITY DEFINER function performs recursive CTE traversal with depth limiting and workspace validation | Traversal function section provides the full SQL pattern with CYCLE detection, depth parameter, direction filtering. SECURITY DEFINER follows match_embeddings() pattern |
| GRAPH-03 | Graph tables have composite indexes on (workspace_id, entity_type), (workspace_id, relationship_type), and fingerprint uniqueness | Index section covers all required indexes plus additional recommendations for edge traversal performance |
| EXTR-01 | Rule-based extractors create graph nodes and edges for ticket references, PR numbers, @mentions, and file paths from ingested content | Extractor patterns section provides exact regex patterns for all five extractors with edge case handling |
| EXTR-02 | Rule-based extraction runs inline during webhook/sync ingestion with zero LLM cost | Integration points section maps every webhook handler and sync service to the extraction call site, following the existing enqueue_embedding_job pattern |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PostgreSQL | 15+ (Supabase) | Graph tables, recursive CTE traversal, RLS | Already in use. All graph storage is in Postgres |
| SQLModel | 0.0.22+ | Python ORM models for GraphNode and GraphEdge | Already in use for all models (BaseModel pattern) |
| SQLAlchemy | 2.0+ (asyncio) | Async DB operations, ON CONFLICT upserts | Already in use for all database operations |
| Python re | stdlib | Regex extractors for entity extraction | Zero dependency, deterministic, fast |
| hashlib | stdlib | SHA256 fingerprint generation | Zero dependency, deterministic |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | current | Async Postgres driver (already installed) | Connection pooling for backfill script |
| pgcrypto | extension | SHA256 in SQL via digest() | Available for SQL-side fingerprinting if needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plain PG tables | Apache AGE | AGE not available on Supabase Cloud (C extension, not TLE). Core team dismissed Oct 2024. Plain tables work today |
| Plain PG tables | Neo4j | Doubles operational complexity, requires bidirectional sync. Graph stays in Postgres |
| Python re | SpaCy NER | 300MB+ dependency for generic NER when domain entities are regex-extractable |
| hashlib SHA256 | pgcrypto digest() | Python-side hashing is simpler to test, consistent between Python and SQL |

**Installation:**
No new packages needed. All dependencies already in `backend/pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
supabase/migrations/
  00017_graph_tables.sql           # graph_nodes, graph_edges, indexes, RLS, triggers
  00018_traverse_graph_function.sql # traverse_graph() SECURITY DEFINER function

backend/src/models/
  graph_node.py                     # GraphNode SQLModel (follows BaseModel pattern)
  graph_edge.py                     # GraphEdge SQLModel (follows BaseModel pattern)

backend/src/services/
  graph_extractor.py                # Registry pattern, run_extractors(), individual extractors
  graph_ops.py                      # upsert_node(), upsert_edge(), ensure_source_node()
  graph_backfill.py                 # One-time backfill script for existing content

backend/tests/
  test_graph_extractor.py           # Unit tests for regex extractors (pure functions, no DB)
  test_graph_ops.py                 # Integration tests for upsert operations
```

### Pattern 1: Fingerprint-Based Deduplication
**What:** Every graph node has a deterministic fingerprint computed from entity_type + external_id. Re-ingesting the same content produces the same fingerprint, hitting ON CONFLICT and updating instead of duplicating.
**When to use:** Every node creation/update.
**Example:**
```python
# Source: Follows embeddings table content_hash pattern from codebase
import hashlib

def compute_fingerprint(entity_type: str, external_id: str) -> str:
    """Deterministic fingerprint for graph node deduplication.

    Examples:
        compute_fingerprint("Ticket", "ENG-123") -> "a1b2c3..."
        compute_fingerprint("Person", "slack:U12345") -> "d4e5f6..."
    """
    raw = f"{entity_type}:{external_id}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

### Pattern 2: Registry-Based Extractor System
**What:** Each extractor is a registered function with a common interface. `run_extractors()` iterates the registry and collects all extracted entities. Phase 24's LLM extractor registers alongside regex extractors.
**When to use:** Every content ingestion (webhook, sync, backfill).
**Example:**
```python
# Source: Follows embedding_worker.enqueue_embedding_job pattern
from dataclasses import dataclass
from typing import Protocol

@dataclass
class ExtractedEntity:
    entity_type: str        # "Ticket", "Person", "PR", etc.
    external_id: str        # "ENG-123", "slack:U12345", etc.
    name: str               # Human-readable display name
    properties: dict        # Additional metadata
    relationship_type: str  # "references", "mentions", etc.

class Extractor(Protocol):
    def extract(self, content: str, source_type: str) -> list[ExtractedEntity]: ...

# Registry
_EXTRACTORS: list[Extractor] = []

def register_extractor(extractor: Extractor) -> None:
    _EXTRACTORS.append(extractor)

def run_extractors(content: str, source_type: str) -> list[ExtractedEntity]:
    results = []
    for extractor in _EXTRACTORS:
        try:
            results.extend(extractor.extract(content, source_type))
        except Exception:
            logger.warning("Extractor %s failed", type(extractor).__name__, exc_info=True)
    return results
```

### Pattern 3: Inline Post-Upsert Extraction Hook
**What:** Graph extraction runs inline after content upsert, matching the existing `embedding.queue_embedding_generation()` pattern in every webhook handler.
**When to use:** Every webhook handler and sync service after upsert.
**Example:**
```python
# Source: Follows handle_issue_create in linear_webhook.py pattern
async def handle_issue_create(session, workspace_id, data):
    # ... existing upsert logic ...
    ticket = await sync_single_ticket(session, workspace_id, access_token, linear_id)

    # Existing: queue embedding
    await embedding.queue_embedding_generation(session, workspace_id, "linear_ticket", [ticket.id])

    # NEW: extract and populate graph (fail-silent)
    try:
        await extract_and_populate_graph(
            session, workspace_id,
            content=f"{ticket.title}\n\n{ticket.description or ''}",
            source_type="linear_ticket",
            source_id=ticket.id,
            source_name=f"{ticket.identifier}: {ticket.title}",
        )
    except Exception:
        logger.warning("Graph extraction failed for ticket %s", ticket.id, exc_info=True)
```

### Pattern 4: SECURITY DEFINER Traversal Function
**What:** SQL function that validates workspace_id once at entry, then performs recursive CTE traversal without per-row RLS evaluation.
**When to use:** Any graph neighborhood query.
**Example:**
```sql
-- Source: Follows match_embeddings() and hybrid_search() patterns from codebase
CREATE OR REPLACE FUNCTION public.traverse_graph(
  start_node_id uuid,
  match_workspace_id uuid,
  max_depth int DEFAULT 2,
  direction text DEFAULT 'both',
  filter_entity_types text[] DEFAULT NULL,
  filter_relationship_types text[] DEFAULT NULL
)
RETURNS TABLE (
  node_id uuid,
  entity_type text,
  name text,
  properties jsonb,
  edge_relationship_type text,
  depth int,
  path uuid[]
)
SECURITY DEFINER
AS $$
BEGIN
  -- Validate workspace access once at entry
  IF NOT EXISTS (
    SELECT 1 FROM public.workspace_members
    WHERE workspace_id = match_workspace_id
      AND user_id = auth.uid()
  ) THEN
    RETURN;
  END IF;

  RETURN QUERY
  WITH RECURSIVE graph_walk(node_id, entity_type, name, properties,
                            edge_rel_type, depth, path, is_cycle) AS (
    -- Anchor: start node
    SELECT n.id, n.entity_type, n.name, n.properties,
           NULL::text, 0, ARRAY[n.id], false
    FROM public.graph_nodes n
    WHERE n.id = start_node_id
      AND n.workspace_id = match_workspace_id
      AND n.deleted_at IS NULL

    UNION ALL

    -- Recursive: follow edges
    SELECT
      next_node.id, next_node.entity_type, next_node.name, next_node.properties,
      e.relationship_type, gw.depth + 1,
      gw.path || next_node.id,
      next_node.id = ANY(gw.path)
    FROM graph_walk gw
    JOIN public.graph_edges e ON (
      (direction IN ('both', 'outbound') AND e.source_node_id = gw.node_id)
      OR
      (direction IN ('both', 'inbound') AND e.target_node_id = gw.node_id)
    )
    JOIN public.graph_nodes next_node ON (
      CASE
        WHEN e.source_node_id = gw.node_id THEN next_node.id = e.target_node_id
        ELSE next_node.id = e.source_node_id
      END
    )
    WHERE gw.depth < max_depth
      AND NOT gw.is_cycle
      AND e.workspace_id = match_workspace_id
      AND e.deleted_at IS NULL
      AND next_node.workspace_id = match_workspace_id
      AND next_node.deleted_at IS NULL
      AND (filter_entity_types IS NULL OR next_node.entity_type = ANY(filter_entity_types))
      AND (filter_relationship_types IS NULL OR e.relationship_type = ANY(filter_relationship_types))
  )
  SELECT gw.node_id, gw.entity_type, gw.name, gw.properties,
         gw.edge_rel_type, gw.depth, gw.path
  FROM graph_walk gw
  WHERE NOT gw.is_cycle;
END;
$$ LANGUAGE plpgsql;
```

### Anti-Patterns to Avoid
- **Querying graph_nodes/graph_edges directly with RLS enabled from application code:** RLS evaluates per-row workspace membership. Use the SECURITY DEFINER traverse_graph() function instead for any multi-hop query.
- **Computing fingerprints with different algorithms in different places:** Always use `hashlib.sha256(f"{entity_type}:{external_id}".encode()).hexdigest()` in Python. Never mix MD5 or other hashing.
- **Creating edges without ensuring both nodes exist:** Always upsert source and target nodes before creating the edge. Use the "unresolved" status for dangling references.
- **Making graph extraction blocking/failure-critical:** Extraction MUST be try/except wrapped. Core ingestion (ticket upsert, embedding) must never fail because of graph extraction errors.
- **Duplicating extractor logic per webhook handler:** Use a single `extract_and_populate_graph()` entry point. Each handler passes content + source metadata. The registry handles dispatching.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph cycle detection | Manual visited-set tracking in Python | PostgreSQL CYCLE clause or manual `ANY(path)` check in SQL | Database handles cycle detection atomically within the CTE |
| Content hashing | Custom hash functions | `hashlib.sha256` (Python stdlib) | Standard, deterministic, no external dependency |
| Upsert deduplication | SELECT-then-INSERT race conditions | `INSERT ... ON CONFLICT (workspace_id, fingerprint) DO UPDATE` | Atomic, handles concurrency correctly |
| Workspace access validation | Per-row Python checks | `SECURITY DEFINER` + single workspace membership check at function entry | Single check vs N per-row evaluations |
| Regex pattern composition | String concatenation | Pre-compiled `re.compile()` patterns | Compiled once, faster execution, clearer error messages |

**Key insight:** Every building block for this phase already exists in the codebase as a proven pattern. The graph schema is the embeddings table pattern with different columns. The extractor registry is the embedding_worker pattern with synchronous execution. The traversal function is match_embeddings() with recursion added. Do not invent new patterns.

## Common Pitfalls

### Pitfall 1: RLS Performance on Graph Tables
**What goes wrong:** Recursive CTE queries evaluate RLS policies per row at each recursion level. With 4 hops and fan-out of 10, this means 10,000+ workspace_members subquery evaluations.
**Why it happens:** Default Supabase behavior applies RLS to every SELECT on enabled tables.
**How to avoid:** Use SECURITY DEFINER function (traverse_graph) that validates workspace once, then bypasses RLS for internal queries. The function runs as the postgres role which has bypassrls.
**Warning signs:** Graph queries taking >500ms for simple 2-hop traversals.

### Pitfall 2: Fingerprint Collisions Across Workspaces
**What goes wrong:** Using fingerprint alone as unique constraint means Ticket:ENG-123 in workspace A conflicts with Ticket:ENG-123 in workspace B.
**Why it happens:** Fingerprint is entity_type + external_id, which can repeat across workspaces.
**How to avoid:** Unique constraint is `(workspace_id, fingerprint)`, NOT `fingerprint` alone. Already specified in CONTEXT.md decisions.
**Warning signs:** ON CONFLICT errors during multi-workspace operations.

### Pitfall 3: Regex Extracting From Already-Extracted Content
**What goes wrong:** Running extractors on a Linear ticket description that contains "See ENG-123" and also running on the same ticket's title creates duplicate entities.
**Why it happens:** Multiple fields concatenated without deduplication.
**How to avoid:** Deduplicate extracted entities by fingerprint before upserting. The `run_extractors()` function should return unique entities by (entity_type, external_id).
**Warning signs:** Duplicate edges between the same two nodes.

### Pitfall 4: Backfill Script Overloading Database
**What goes wrong:** Processing 10,000 existing Slack messages sequentially in a single transaction causes memory pressure and long locks.
**Why it happens:** Backfill tries to process everything at once.
**How to avoid:** Batch processing with configurable batch_size (default 100). Commit after each batch. Optional asyncio concurrency with semaphore.
**Warning signs:** Database connection timeouts during backfill.

### Pitfall 5: Recursive CTE Infinite Loops
**What goes wrong:** Bidirectional edges (A->B and B->A) cause the recursive CTE to loop forever.
**Why it happens:** Graph edges can form cycles. Without cycle detection, recursion never terminates.
**How to avoid:** Track visited node IDs in a path array. Check `node_id = ANY(path)` and set `is_cycle = true`. Filter out cycles from results with `WHERE NOT is_cycle`.
**Warning signs:** Query hangs indefinitely, database CPU spikes.

### Pitfall 6: URL Extractor Matching Non-Entity URLs
**What goes wrong:** Extracting every URL from Slack messages creates noise nodes for random websites, image links, etc.
**Why it happens:** Broad URL regex matches everything.
**How to avoid:** URL extractor should only match known integration URL patterns: `linear.app/*`, `github.com/*/pull/*`, `notion.so/*`, `app.slack.com/archives/*`. Reject all other URLs.
**Warning signs:** Graph filled with nodes for random websites.

## Code Examples

Verified patterns from existing codebase:

### Graph Node Schema (SQL Migration)
```sql
-- Source: Follows 00001_initial_schema.sql patterns
-- Migration: 00017_graph_tables.sql

CREATE TABLE public.graph_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  entity_type text NOT NULL CHECK (entity_type IN (
    'Person', 'Ticket', 'SlackThread', 'PR', 'CodeChunk',
    'NotionPage', 'Meeting', 'Decision', 'Blocker', 'Feature', 'Component'
  )),
  name text NOT NULL,
  fingerprint text NOT NULL,
  source_type text,          -- polymorphic: 'slack_message', 'linear_ticket', etc.
  source_id uuid,            -- FK to source record (not enforced, polymorphic)
  properties jsonb DEFAULT '{}',
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, fingerprint)
);

CREATE TABLE public.graph_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  source_node_id uuid NOT NULL REFERENCES public.graph_nodes(id) ON DELETE CASCADE,
  target_node_id uuid NOT NULL REFERENCES public.graph_nodes(id) ON DELETE CASCADE,
  relationship_type text NOT NULL CHECK (relationship_type IN (
    'mentions', 'references', 'authored_by', 'assigned_to',
    'discussed_in', 'implements', 'reviews', 'decided_in',
    'blocks', 'same_as', 'parent_of'
  )),
  properties jsonb DEFAULT '{}',
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, source_node_id, target_node_id, relationship_type)
);
```

### Graph Node SQLModel
```python
# Source: Follows backend/src/models/embedding.py and base.py patterns
import uuid
from sqlalchemy import Column, UniqueConstraint, text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field
from src.models.base import BaseModel

class GraphNode(BaseModel, table=True):
    """Graph node mapping to public.graph_nodes table."""
    __tablename__ = "graph_nodes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "fingerprint", name="graph_nodes_workspace_fingerprint_key"),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    entity_type: str = Field(nullable=False)
    name: str = Field(nullable=False)
    fingerprint: str = Field(nullable=False)
    source_type: str | None = Field(default=None)
    source_id: uuid.UUID | None = Field(default=None)
    properties: dict = Field(
        default_factory=dict,
        sa_column=Column("properties", JSONB, nullable=False, server_default=sa_text("'{}'")),
    )
```

### Ticket Reference Extractor
```python
# Source: Claude's discretion on exact regex patterns
import re
from dataclasses import dataclass

# Matches ticket identifiers like ENG-123, CON-45, BUG-1
# Team prefix: 2-10 uppercase letters. Number: 1-6 digits.
TICKET_REF_PATTERN = re.compile(
    r'\b([A-Z]{2,10})-(\d{1,6})\b'
)

def extract_ticket_refs(content: str, source_type: str) -> list[ExtractedEntity]:
    """Extract ticket references like ENG-123, CON-45."""
    entities = []
    seen = set()
    for match in TICKET_REF_PATTERN.finditer(content):
        identifier = match.group(0)  # "ENG-123"
        if identifier not in seen:
            seen.add(identifier)
            entities.append(ExtractedEntity(
                entity_type="Ticket",
                external_id=identifier,
                name=identifier,
                properties={"identifier": identifier, "team_prefix": match.group(1)},
                relationship_type="references",
            ))
    return entities
```

### Mention Extractor
```python
# Slack user IDs: <@U12345ABC> format
# Linear/GitHub usernames: @username format (word boundary)
SLACK_MENTION_PATTERN = re.compile(r'<@(U[A-Z0-9]{6,12})>')
AT_MENTION_PATTERN = re.compile(r'(?<!\S)@([a-zA-Z][a-zA-Z0-9._-]{1,38})\b')

def extract_mentions(content: str, source_type: str) -> list[ExtractedEntity]:
    """Extract @mentions from Slack user IDs and platform usernames."""
    entities = []
    seen = set()

    # Slack user ID mentions: <@U12345ABC>
    for match in SLACK_MENTION_PATTERN.finditer(content):
        user_id = match.group(1)
        key = f"slack:{user_id}"
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(
                entity_type="Person",
                external_id=key,
                name=f"Slack user {user_id}",
                properties={"platform": "slack", "platform_user_id": user_id},
                relationship_type="mentions",
            ))

    # @username mentions (Linear, GitHub)
    for match in AT_MENTION_PATTERN.finditer(content):
        username = match.group(1)
        key = f"username:{username}"
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(
                entity_type="Person",
                external_id=key,
                name=f"@{username}",
                properties={"platform": source_type.split("_")[0], "username": username},
                relationship_type="mentions",
            ))

    return entities
```

### PR/Commit Reference Extractor
```python
# PR references: #123 (preceded by non-digit to avoid issue with hex colors)
PR_REF_PATTERN = re.compile(r'(?<!\w)#(\d{1,6})\b')
# Git SHA references: 7+ hex chars (short SHA), isolated word
SHA_PATTERN = re.compile(r'\b([0-9a-f]{7,40})\b')

def extract_pr_refs(content: str, source_type: str) -> list[ExtractedEntity]:
    """Extract PR numbers (#123) and commit SHA references."""
    entities = []
    seen = set()

    for match in PR_REF_PATTERN.finditer(content):
        pr_num = match.group(1)
        key = f"PR:#{pr_num}"
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(
                entity_type="PR",
                external_id=key,
                name=f"PR #{pr_num}",
                properties={"number": int(pr_num)},
                relationship_type="references",
            ))

    for match in SHA_PATTERN.finditer(content):
        sha = match.group(1)
        # Only match if >= 7 chars and not all digits (avoid plain numbers)
        if len(sha) >= 7 and not sha.isdigit():
            key = f"commit:{sha[:7]}"
            if key not in seen:
                seen.add(key)
                entities.append(ExtractedEntity(
                    entity_type="PR",  # Commit refs resolve to PR context
                    external_id=key,
                    name=f"Commit {sha[:7]}",
                    properties={"sha": sha, "short_sha": sha[:7]},
                    relationship_type="references",
                ))

    return entities
```

### File Path Extractor
```python
# File paths: /src/..., ./src/..., or bare paths with common extensions
FILE_PATH_PATTERN = re.compile(
    r'(?<!\S)'                           # start of word
    r'((?:\.{0,2}/)?'                    # optional ./ or ../
    r'(?:[a-zA-Z0-9_.-]+/)*'            # directory segments
    r'[a-zA-Z0-9_.-]+'                   # filename
    r'\.(?:ts|tsx|js|jsx|py|rs|go|'      # common code extensions
    r'sql|md|json|yaml|yml|toml|css|html))'
    r'(?:\s|$|[,;)\]}])',               # end of word
    re.MULTILINE
)

def extract_file_paths(content: str, source_type: str) -> list[ExtractedEntity]:
    """Extract file path references from content."""
    entities = []
    seen = set()

    for match in FILE_PATH_PATTERN.finditer(content):
        path = match.group(1)
        if path not in seen:
            seen.add(path)
            entities.append(ExtractedEntity(
                entity_type="CodeChunk",
                external_id=f"path:{path}",
                name=path,
                properties={"file_path": path},
                relationship_type="references",
            ))

    return entities
```

### URL Extractor (Known Integrations Only)
```python
# Only match known integration URLs
URL_PATTERNS = {
    "linear": re.compile(r'https?://linear\.app/[a-zA-Z0-9-]+/issue/([A-Z]+-\d+)'),
    "github_pr": re.compile(r'https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)/pull/(\d+)'),
    "github_commit": re.compile(r'https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)/commit/([0-9a-f]{7,40})'),
    "notion": re.compile(r'https?://(?:www\.)?notion\.so/(?:[a-zA-Z0-9-]+/)?([a-f0-9]{32})'),
    "slack": re.compile(r'https?://[a-zA-Z0-9-]+\.slack\.com/archives/([A-Z0-9]+)/p(\d+)'),
}

def extract_urls(content: str, source_type: str) -> list[ExtractedEntity]:
    """Extract URLs that resolve to known integration entities."""
    entities = []
    seen = set()

    for platform, pattern in URL_PATTERNS.items():
        for match in pattern.finditer(content):
            if platform == "linear":
                identifier = match.group(1)
                key = f"Ticket:{identifier}"
                if key not in seen:
                    seen.add(key)
                    entities.append(ExtractedEntity(
                        entity_type="Ticket",
                        external_id=identifier,
                        name=identifier,
                        properties={"url": match.group(0), "resolved_from": "url"},
                        relationship_type="references",
                    ))
            elif platform == "github_pr":
                repo, pr_num = match.group(1), match.group(2)
                key = f"PR:{repo}#{pr_num}"
                if key not in seen:
                    seen.add(key)
                    entities.append(ExtractedEntity(
                        entity_type="PR",
                        external_id=key,
                        name=f"PR {repo}#{pr_num}",
                        properties={"repo": repo, "number": int(pr_num), "url": match.group(0)},
                        relationship_type="references",
                    ))
            # ... similar for notion, slack, github_commit

    return entities
```

### Graph Upsert Operations
```python
# Source: Follows ON CONFLICT pattern from linear_sync.py _upsert_tickets
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def upsert_node(
    session: AsyncSession,
    workspace_id: UUID,
    entity_type: str,
    external_id: str,
    name: str,
    source_type: str | None = None,
    source_id: UUID | None = None,
    properties: dict | None = None,
) -> UUID:
    """Upsert a graph node with fingerprint deduplication."""
    fingerprint = compute_fingerprint(entity_type, external_id)

    values = {
        "workspace_id": workspace_id,
        "entity_type": entity_type,
        "name": name,
        "fingerprint": fingerprint,
        "source_type": source_type,
        "source_id": source_id,
        "properties": properties or {},
    }

    stmt = pg_insert(GraphNode).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="graph_nodes_workspace_fingerprint_key",
        set_={
            "name": stmt.excluded.name,
            "source_type": stmt.excluded.source_type,
            "source_id": stmt.excluded.source_id,
            "properties": stmt.excluded.properties,
            "deleted_at": None,  # Restore if soft-deleted
        },
    ).returning(GraphNode.__table__.c.id)

    result = await session.execute(stmt)
    return result.scalar_one()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Apache AGE graph extension | Plain PG tables + recursive CTEs | Supabase dismissed AGE Oct 2024 | No dependency on unavailable C extension |
| Manual cycle detection in app code | PostgreSQL CYCLE clause | PostgreSQL 14 (2021) | Database handles cycle detection natively |
| Per-row RLS on graph queries | SECURITY DEFINER bypass | Established Supabase pattern | 100x+ performance improvement on traversal queries |
| Full NLP pipeline (SpaCy) for entity extraction | Two-tier: regex (Phase 22) + LLM (Phase 24) | Project decision | Zero LLM cost for deterministic patterns, LLM only for semantic entities |

**Deprecated/outdated:**
- Apache AGE for Supabase: Not available on Supabase Cloud (C extension, not TLE). Do not use.
- CTE materialization forcing (pre-PG12): CTEs are no longer always materialized. No need to work around this.

## Open Questions

1. **Edge uniqueness constraint scope**
   - What we know: Unique on (workspace_id, source_node_id, target_node_id, relationship_type) prevents duplicate edges
   - What's unclear: Should the same two nodes allow multiple edges of the same type (e.g., person mentions ticket in two different Slack messages)?
   - Recommendation: Keep unique constraint. The edge's `properties` JSONB can accumulate source references. Prevents graph bloat. If the same relationship is extracted again, update properties to add the new source.

2. **Backfill ordering and idempotency**
   - What we know: Backfill must process all existing content. Fingerprint deduplication makes it idempotent.
   - What's unclear: Optimal ordering (process tickets first so they exist when Slack messages reference them, or process in any order relying on "unresolved" nodes?)
   - Recommendation: Process in any order. Unresolved nodes are by design. When a later batch processes the referenced entity, the fingerprint match updates the unresolved node. Simpler code, same end state.

3. **PR reference disambiguation**
   - What we know: `#123` could be a PR number or an issue number or even a Slack channel reference
   - What's unclear: How to disambiguate without context
   - Recommendation: Create as PR type by default (most common in engineering context). If the content source is GitHub-related (github_pull_request, github_review), it's definitely a PR reference. For other sources, mark as status='ambiguous' in properties. Phase 24 LLM extraction can resolve ambiguity.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_graph_extractor.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-01 | graph_nodes and graph_edges tables exist with correct schema | integration | `cd backend && python -m pytest tests/test_graph_ops.py::test_node_upsert_dedup -x` | Wave 0 |
| GRAPH-01 | fingerprint deduplication prevents duplicates | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_fingerprint_deterministic -x` | Wave 0 |
| GRAPH-02 | traverse_graph() returns correct subgraph | integration | `cd backend && python -m pytest tests/test_graph_ops.py::test_traverse_graph_depth -x` | Wave 0 |
| GRAPH-02 | traverse_graph() respects workspace isolation | integration | `cd backend && python -m pytest tests/test_graph_ops.py::test_traverse_workspace_isolation -x` | Wave 0 |
| GRAPH-03 | Composite indexes used by query plans | manual-only | `EXPLAIN ANALYZE` on graph queries in Supabase SQL editor | N/A |
| EXTR-01 | Ticket ref extractor finds ENG-123 pattern | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_ticket_ref_extraction -x` | Wave 0 |
| EXTR-01 | Mention extractor finds Slack UIDs and @usernames | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_mention_extraction -x` | Wave 0 |
| EXTR-01 | PR ref extractor finds #123 and SHA prefixes | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_pr_ref_extraction -x` | Wave 0 |
| EXTR-01 | File path extractor finds code file references | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_file_path_extraction -x` | Wave 0 |
| EXTR-01 | URL extractor matches known integration URLs only | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_url_extraction -x` | Wave 0 |
| EXTR-02 | Extraction runs inline with zero LLM calls | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_no_llm_calls -x` | Wave 0 |
| EXTR-02 | Re-ingestion does not create duplicates | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_reingestion_dedup -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_graph_extractor.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_graph_extractor.py` -- covers EXTR-01, EXTR-02 (unit tests for pure regex functions)
- [ ] `backend/tests/test_graph_ops.py` -- covers GRAPH-01, GRAPH-02 (integration tests for DB operations)
- [ ] No new framework install needed -- pytest + pytest-asyncio already in dev dependencies

## Sources

### Primary (HIGH confidence)
- Existing codebase: `supabase/migrations/00001_initial_schema.sql` -- Schema patterns, RLS policies, index conventions, trigger patterns
- Existing codebase: `backend/src/models/embedding.py` -- Polymorphic source_type + source_id pattern, JSONB properties
- Existing codebase: `backend/src/models/base.py` -- BaseModel with TimestampMixin (id, created_at, updated_at, deleted_at)
- Existing codebase: `backend/src/services/linking.py` -- LinkedItem result shape that Phase 25 graph retrieval must support
- Existing codebase: `backend/src/services/linear_webhook.py` -- Post-upsert side effect pattern (embedding.queue_embedding_generation)
- Existing codebase: `backend/src/services/slack_events.py` -- Inline processing pattern with fail-silent error handling
- Existing codebase: `backend/src/services/github_webhook.py` -- Upsert + post-processing pattern for webhook handlers
- Existing codebase: `supabase/migrations/00008_hybrid_search.sql` -- SECURITY DEFINER function pattern with workspace scoping
- [PostgreSQL 18 WITH Queries documentation](https://www.postgresql.org/docs/current/queries-with.html) -- CYCLE clause, SEARCH clause, recursive CTE semantics

### Secondary (MEDIUM confidence)
- [Supabase RLS Performance and Best Practices](https://supabase.com/docs/guides/troubleshooting/rls-performance-and-best-practices-Z5Jjwv) -- SECURITY DEFINER bypass pattern, initPlan optimization
- [Supabase RLS bypass discussion](https://github.com/orgs/supabase/discussions/3563) -- SECURITY DEFINER function runs as creator role, bypasses RLS
- [Supabase RLS using Functions - Security Definers](https://blog.entrostat.com/supabase-rls-functions/) -- Security Definer pattern explanation

### Tertiary (LOW confidence)
- None -- all findings verified against codebase or official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Entire stack already in use in the codebase. No new dependencies.
- Architecture: HIGH - Every pattern (polymorphic source linking, ON CONFLICT upserts, SECURITY DEFINER functions, post-upsert hooks, registry pattern) is directly modeled on existing, proven code.
- Pitfalls: HIGH - RLS performance documented by Supabase. Cycle detection documented by PostgreSQL. Other pitfalls derived from standard graph data modeling.
- Regex patterns: MEDIUM - Patterns cover known entity formats but edge cases may emerge in production data. Claude's discretion per CONTEXT.md.

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable domain -- PostgreSQL, Python stdlib, established codebase patterns)
