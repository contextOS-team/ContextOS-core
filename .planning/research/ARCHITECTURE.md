# Architecture Patterns

**Domain:** GraphRAG knowledge graph layer for engineering context synthesis
**Researched:** 2026-03-06

## Critical Finding: Apache AGE Cannot Run on Supabase Cloud

**Confidence: HIGH** -- verified via Supabase official docs and GitHub discussions.

Apache AGE is NOT in Supabase's list of supported PostgreSQL extensions. AGE is a C extension (not a Trusted Language Extension), so it cannot be installed on Supabase Cloud. The Supabase Postgres images are built with Nix and do not allow compiling C extensions at runtime.

Workarounds from the community (dual databases with `postgres_fdw`, self-hosted Supabase, Docker images with PG13) all violate ContextOS's constraint of staying on Supabase Cloud + Railway hosting.

**Recommendation: Use plain PostgreSQL tables (nodes + edges) with recursive CTEs for graph traversal.** This approach:
- Works on Supabase Cloud today (no extension required)
- Lives alongside existing pgvector + pg_trgm
- Supports RLS multi-tenancy with standard `workspace_id` patterns
- Enables graph-enhanced retrieval via SQL, blended with existing hybrid search
- Is proven in production (postgres-graph-rag library, multiple real-world deployments)

The tradeoff is that Cypher query syntax is not available -- graph queries use recursive CTEs instead. For ContextOS's use case (2-3 hop traversals within a workspace, not massive graph analytics), this is more than sufficient.

Sources:
- [Supabase Extensions List](https://supabase.com/docs/guides/database/extensions) -- AGE absent
- [Supabase Discussion #40285](https://github.com/orgs/supabase/discussions/40285) -- AGE install blocked
- [Supabase Discussion #13263](https://github.com/orgs/supabase/discussions/13263) -- AGE not supported
- [postgres-graph-rag](https://github.com/h4gen/postgres-graph-rag) -- pure PG graph RAG library

---

## Recommended Architecture

### High-Level Integration

```
                    EXISTING                              NEW (v1.2)
             +------------------+                 +--------------------+
             |  Webhook/Sync    |                 |  Entity Extraction |
             |  (Linear, Slack, |---[triggers]--->|  Pipeline          |
             |   GitHub, Notion)|                 |  (rule + LLM)     |
             +------------------+                 +--------------------+
                      |                                     |
                      v                                     v
             +------------------+                 +--------------------+
             |  Source Tables   |                 |  Graph Tables      |
             |  (linear_tickets,|                 |  (graph_nodes,     |
             |   slack_messages,|                 |   graph_edges)     |
             |   code_chunks..)|                 +--------------------+
             +------------------+                          |
                      |                                     |
                      v                                     v
             +------------------+                 +--------------------+
             |  Embeddings +    |                 |  Graph Traversal   |
             |  Hybrid Search   |<---[blended]--->|  (Recursive CTEs)  |
             +------------------+                 +--------------------+
                      |                                     |
                      v                                     v
             +--------------------------------------------------+
             |              Linking Engine (MODIFIED)            |
             |  find_related_content() + graph_signal            |
             +--------------------------------------------------+
                                     |
                                     v
             +--------------------------------------------------+
             |            Synthesis (MODIFIED prompts)           |
             |  Includes decision trails, relationship paths     |
             +--------------------------------------------------+
```

### Component Boundaries

| Component | Responsibility | Status | Communicates With |
|-----------|---------------|--------|-------------------|
| `graph_nodes` table | Store entity nodes (Person, Decision, CodeArtifact, etc.) | **NEW** | Graph edges, entity extractors |
| `graph_edges` table | Store typed relationships between entities | **NEW** | Graph nodes, traversal queries |
| `entity_extraction` service | Extract entities from source content on ingest | **NEW** | Source tables, graph tables, LLM client |
| `identity_resolution` service | Merge person identities across sources | **NEW** | Graph nodes, source tables |
| `graph_retrieval` service | Traverse graph and return related entities/paths | **NEW** | Graph tables, linking engine |
| `linking.py` | Find related content for a ticket (EXISTING) | **MODIFIED** | Graph retrieval (new signal), hybrid search, explicit refs |
| `synthesis.py` | Generate context pages (EXISTING) | **MODIFIED** | Linking engine (receives graph data), LLM client |
| `embedding.py` | Generate/store embeddings (EXISTING) | **MINOR CHANGE** | Source type constraint update only |
| Webhook handlers | Process incoming data (EXISTING) | **MODIFIED** | Trigger entity extraction after data ingest |

### New Files (Recommended Structure)

```
backend/src/
  services/
    graph/
      __init__.py
      schema.py          # Graph node/edge types, entity type enums
      extraction.py      # Entity extraction pipeline (rule + LLM)
      identity.py        # Cross-source identity resolution
      retrieval.py       # Graph traversal queries (recursive CTEs)
      decisions.py       # Decision extraction from messages/transcripts
  models/
    graph.py             # SQLModel for graph_nodes, graph_edges

supabase/migrations/
  00017_graph_tables.sql # Graph schema: nodes, edges, indexes, RLS
```

---

## Database Schema Design

### Graph Nodes Table

```sql
CREATE TABLE public.graph_nodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,

  -- Entity identity
  entity_type TEXT NOT NULL CHECK (entity_type IN (
    'person', 'decision', 'code_artifact', 'feature', 'ticket',
    'meeting', 'channel', 'repository', 'file', 'concept'
  )),
  canonical_name TEXT NOT NULL,        -- display name after resolution

  -- Source provenance (which record created/updated this node)
  source_type TEXT,                     -- e.g. 'slack_message', 'linear_ticket'
  source_id UUID,                       -- FK to original source record

  -- Flexible properties (JSONB avoids schema migration per entity type)
  properties JSONB NOT NULL DEFAULT '{}',
  -- Examples:
  --   person:  {"email": "...", "slack_id": "U123", "github_login": "...", "linear_name": "..."}
  --   decision: {"status": "decided", "decided_at": "...", "rationale": "...", "text": "..."}
  --   code_artifact: {"repo": "...", "file_path": "...", "symbol": "...", "language": "..."}
  --   feature: {"description": "...", "status": "in_progress"}

  -- Deduplication
  fingerprint TEXT NOT NULL,            -- hash of (entity_type, canonical_name, workspace_id)

  confidence FLOAT NOT NULL DEFAULT 1.0,  -- extraction confidence (1.0 = rule-based, <1.0 = LLM)

  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (workspace_id, fingerprint)
);
```

### Graph Edges Table

```sql
CREATE TABLE public.graph_edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,

  -- Relationship
  source_node_id UUID NOT NULL REFERENCES public.graph_nodes(id) ON DELETE CASCADE,
  target_node_id UUID NOT NULL REFERENCES public.graph_nodes(id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL CHECK (relationship_type IN (
    'authored', 'mentioned_in', 'decided_in', 'implements',
    'related_to', 'assigned_to', 'reviewed', 'discussed_in',
    'blocks', 'depends_on', 'motivated_by', 'part_of',
    'same_as'  -- identity resolution edge
  )),

  -- Provenance: which source record established this edge
  source_type TEXT,
  source_id UUID,

  -- Edge properties
  properties JSONB NOT NULL DEFAULT '{}',
  -- Examples:
  --   mentioned_in: {"message_ts": "...", "context_snippet": "..."}
  --   decided_in: {"decision_text": "...", "timestamp": "..."}
  --   same_as: {"match_type": "email", "confidence": 1.0}

  weight FLOAT NOT NULL DEFAULT 1.0,    -- edge strength/confidence

  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Prevent duplicate edges of the same type between same nodes from same source
  UNIQUE (workspace_id, source_node_id, target_node_id, relationship_type, source_type, source_id)
);
```

### Key Indexes

```sql
-- Node lookups
CREATE INDEX idx_graph_nodes_workspace ON public.graph_nodes (workspace_id);
CREATE INDEX idx_graph_nodes_type ON public.graph_nodes (workspace_id, entity_type);
CREATE INDEX idx_graph_nodes_name ON public.graph_nodes USING gin (canonical_name gin_trgm_ops);
CREATE INDEX idx_graph_nodes_source ON public.graph_nodes (source_type, source_id);

-- Edge traversal (both directions for bidirectional queries)
CREATE INDEX idx_graph_edges_source ON public.graph_edges (source_node_id);
CREATE INDEX idx_graph_edges_target ON public.graph_edges (target_node_id);
CREATE INDEX idx_graph_edges_workspace ON public.graph_edges (workspace_id);
CREATE INDEX idx_graph_edges_type ON public.graph_edges (workspace_id, relationship_type);

-- RLS (follows existing workspace_data pattern)
ALTER TABLE public.graph_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.graph_edges ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_data" ON public.graph_nodes
  FOR ALL USING (
    workspace_id IN (SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid())
  );

CREATE POLICY "workspace_data" ON public.graph_edges
  FOR ALL USING (
    workspace_id IN (SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid())
  );

-- Triggers
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.graph_nodes
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
```

### Graph Traversal Function (Recursive CTE)

```sql
-- Multi-hop graph traversal from a starting node
CREATE OR REPLACE FUNCTION public.traverse_graph(
  start_node_id UUID,
  match_workspace_id UUID,
  max_depth INT DEFAULT 2,
  edge_types TEXT[] DEFAULT NULL,
  node_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
  node_id UUID,
  entity_type TEXT,
  canonical_name TEXT,
  properties JSONB,
  depth INT,
  path_edge_types TEXT[],    -- relationship types along the path
  path_node_ids UUID[]       -- node IDs along the path
) AS $$
BEGIN
  RETURN QUERY
  WITH RECURSIVE graph_walk AS (
    -- Anchor: start node
    SELECT
      n.id AS node_id,
      n.entity_type,
      n.canonical_name,
      n.properties,
      0 AS depth,
      ARRAY[]::TEXT[] AS path_edge_types,
      ARRAY[n.id] AS path_node_ids
    FROM public.graph_nodes n
    WHERE n.id = start_node_id
      AND n.workspace_id = match_workspace_id
      AND n.deleted_at IS NULL

    UNION ALL

    -- Recursive: follow edges in both directions
    SELECT
      n2.id,
      n2.entity_type,
      n2.canonical_name,
      n2.properties,
      gw.depth + 1,
      gw.path_edge_types || e.relationship_type,
      gw.path_node_ids || n2.id
    FROM graph_walk gw
    JOIN public.graph_edges e ON (
      (e.source_node_id = gw.node_id OR e.target_node_id = gw.node_id)
      AND e.workspace_id = match_workspace_id
    )
    JOIN public.graph_nodes n2 ON (
      n2.id = CASE
        WHEN e.source_node_id = gw.node_id THEN e.target_node_id
        ELSE e.source_node_id
      END
    )
    WHERE gw.depth < max_depth
      AND e.deleted_at IS NULL
      AND n2.deleted_at IS NULL
      AND NOT (n2.id = ANY(gw.path_node_ids))  -- cycle prevention
      AND (edge_types IS NULL OR e.relationship_type = ANY(edge_types))
      AND (node_types IS NULL OR n2.entity_type = ANY(node_types))
  )
  SELECT DISTINCT ON (gw2.node_id) gw2.*
  FROM graph_walk gw2
  WHERE gw2.depth > 0  -- exclude start node from results
  ORDER BY gw2.node_id, gw2.depth;  -- prefer shortest path
END;
$$ LANGUAGE plpgsql;
```

---

## Data Flow

### Entity Extraction Flow (NEW)

```
1. Source data arrives (webhook or sync)
     |
2. Existing flow: store in source table, generate embedding
     |
3. NEW: Trigger entity extraction (async, after commit)
     |
4. Rule-based extractors run first (cheap, fast, deterministic):
     - Ticket IDs (regex: [A-Z]+-\d+) -> ticket node + mentioned_in edge
     - @mentions (Slack user IDs) -> person node + mentioned_in edge
     - GitHub logins (@username in PR body) -> person node + authored/reviewed edge
     - PR numbers (#\d+ with repo context) -> code_artifact node
     - File paths (src/..., *.py patterns) -> file node
     - URLs (github.com/owner/repo/...) -> code_artifact or repository node
     |
5. LLM extractors run second (for semantic entities, filtered content only):
     - Decision extraction from messages >50 chars containing decision signals
     - Concept/feature extraction from tickets and discussions
     - Relationship inference (who decided what, who is blocking whom)
     |
6. Identity resolution:
     - Match extracted person against existing graph_nodes in workspace
     - Deterministic merge: email, Slack user_id, GitHub login (confidence=1.0)
     - Fuzzy merge: name similarity Jaro-Winkler >0.85, verified per workspace
     - Create 'same_as' edges for merged identities
     - Aggregate properties JSONB across sources
     |
7. Upsert nodes and edges into graph tables (fingerprint-based dedup)
```

### Graph-Enhanced Retrieval Flow (MODIFIED find_related_content)

```
1. find_related_content() called for a ticket (EXISTING entry point)
     |
2. EXISTING: Find explicit references (PRs, comments, Slack mentions)
3. EXISTING: Run hybrid_search() (vector + full-text)
     |
4. NEW: Graph signal
     a. Find graph_node for this ticket (by source_type='linear_ticket', source_id=ticket.id)
     b. Call traverse_graph() with max_depth=2
     c. For each discovered node:
        - If node has source_type + source_id -> look up the source record
        - Build LinkedItem with relevance = WEIGHT_GRAPH * edge_weight * depth_decay
     d. Separately collect decision trail nodes (entity_type='decision')
     e. Separately collect person involvement (entity_type='person')
     f. Return graph-discovered items + structured graph context
     |
5. MODIFIED: Merge all three signals (explicit + hybrid + graph)
     - Graph items scored with WEIGHT_GRAPH = 0.9
     - Items found by multiple signals get boosted scores
     |
6. MODIFIED: Pass graph context to synthesis
     - Decision trail (decision nodes connected to this ticket + path info)
     - People involvement (person nodes + their relationship types)
     - Cross-source connections (e.g., "Daulet discussed in #eng -> decided in standup -> PR'd in repo")
```

### Identity Resolution Flow (NEW)

```
1. On first ingest of a person reference:
     - Extract identifiers: email, Slack user_id, GitHub login, Linear display name
     - Look up in properties JSONB of existing person nodes in workspace
     |
2. Deterministic matching (auto-merge, confidence=1.0):
     - Same email -> same person
     - Same Slack user_id (U...) -> same person
     - Same GitHub login -> same person
     - Merge: update properties JSONB to union all identifiers
     |
3. Fuzzy matching (candidate, confidence<1.0):
     - Name similarity only (Jaro-Winkler > 0.85)
     - Within same workspace only
     - Create 'same_as' edge with candidate confidence
     - Do NOT auto-merge -- flag for review or LLM verification
     |
4. No match -> create new person node with available identifiers
     |
5. Edge consolidation: when two nodes merge, redirect edges from
   the deprecated node to the canonical node (or keep both and
   resolve at query time via same_as traversal)
```

---

## Patterns to Follow

### Pattern 1: Async Post-Ingest Hook

**What:** Entity extraction runs as a background task triggered after source data is committed, not inline with the webhook handler.

**When:** Every time new data arrives (webhook, sync, manual import).

**Why:** Entity extraction (especially LLM calls) is slow (200ms-2s). Webhook handlers must respond within 3 seconds. Running extraction inline would timeout.

**Example:**
```python
# In webhook handler (e.g., slack_events.py after storing message)
from src.services.graph.extraction import extract_entities_from_source

async def handle_slack_message(session, workspace_id, message_data):
    # 1. Store message (existing)
    msg = await store_slack_message(session, workspace_id, message_data)
    await session.commit()

    # 2. Queue entity extraction (new, non-blocking)
    background_tasks.add_task(
        extract_entities_from_source,
        workspace_id=workspace_id,
        source_type="slack_message",
        source_id=msg.id,
    )
```

### Pattern 2: Rule-First, LLM-Second Extraction

**What:** Run cheap regex/pattern extractors before expensive LLM calls. Only invoke LLM for content that passes a relevance filter.

**When:** Processing any source content for entity extraction.

**Why:** Rule-based extraction is free, instant, and deterministic. LLM extraction costs money and is non-deterministic. For structured references (ticket IDs, @mentions, PR numbers), rules are more reliable than LLMs anyway.

**Example:**
```python
async def extract_entities(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_id: UUID,
    text: str,
) -> list[ExtractedEntity]:
    entities = []

    # Phase 1: Rules (free, instant, deterministic)
    entities.extend(extract_ticket_refs(text))       # regex: [A-Z]+-\d+
    entities.extend(extract_slack_mentions(text))     # regex: <@U[A-Z0-9]+>
    entities.extend(extract_pr_refs(text))            # regex: #\d+, github.com/.../pull/\d+
    entities.extend(extract_file_paths(text))         # regex: [\w/]+\.\w{1,4}

    # Phase 2: LLM (expensive, only for high-value content)
    if _should_run_llm_extraction(source_type, text):
        llm_entities = await _llm_extract_decisions_and_concepts(text)
        entities.extend(llm_entities)

    return entities


def _should_run_llm_extraction(source_type: str, text: str) -> bool:
    """Only run LLM extraction on content likely to contain decisions/concepts."""
    if len(text) < 50:
        return False
    if source_type == "meeting_segment" and len(text) < 100:
        return False

    # Decision signal words
    decision_signals = ["decided", "agreed", "we should", "the plan is",
                        "going with", "approved", "let's", "action item",
                        "conclusion", "resolution"]
    text_lower = text.lower()
    return any(signal in text_lower for signal in decision_signals)
```

### Pattern 3: Fingerprint-Based Deduplication

**What:** Each graph node has a deterministic fingerprint (hash of entity_type + normalized_name + workspace_id). Upserts use `ON CONFLICT (workspace_id, fingerprint) DO UPDATE` to prevent duplicates.

**When:** Every entity extraction writes to the graph.

**Why:** The same person/decision/concept will be extracted from multiple sources. Without deduplication, the graph would be full of duplicate nodes that fragment relationships.

**Example:**
```python
import hashlib

def compute_node_fingerprint(
    entity_type: str,
    canonical_name: str,
    workspace_id: UUID,
) -> str:
    """Deterministic hash for graph node dedup."""
    normalized = canonical_name.lower().strip()
    raw = f"{entity_type}:{normalized}:{workspace_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

### Pattern 4: Blended Scoring with Depth Decay

**What:** Graph-discovered items are scored with a weight that decays by hop distance. Direct connections (depth=1) score higher than 2-hop connections.

**When:** Graph retrieval returns items for the linking engine.

**Why:** A person directly assigned to a ticket is more relevant than someone who commented on a related PR two hops away. Depth decay prevents distant connections from drowning out direct relationships.

**Example:**
```python
WEIGHT_GRAPH = 0.9       # between explicit (1.0) and hybrid (0.8)
DEPTH_DECAY = 0.6        # each hop multiplies by this factor

def score_graph_item(edge_weight: float, depth: int) -> float:
    """Score a graph-discovered item with depth decay."""
    return WEIGHT_GRAPH * edge_weight * (DEPTH_DECAY ** (depth - 1))
    # depth=1: 0.9 * 1.0 * 1.0   = 0.90  (strong signal)
    # depth=2: 0.9 * 1.0 * 0.6   = 0.54  (moderate signal)
    # depth=3: 0.9 * 1.0 * 0.36  = 0.32  (weak, probably cap at 2)
```

### Pattern 5: LLM Extraction via Structured Output

**What:** Use the LLM's structured output (JSON mode) for entity extraction, not free-text parsing.

**When:** Running LLM-based extraction for decisions and concepts.

**Why:** Structured output guarantees the response matches the expected schema. No post-processing regex needed. Gemini and GPT-4o both support this well.

**Example:**
```python
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "status": {"type": "string", "enum": ["decided", "proposed", "rejected"]},
                    "people_involved": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "status"],
            },
        },
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
}

async def _llm_extract_decisions_and_concepts(text: str) -> list[ExtractedEntity]:
    """Extract decisions and concepts using structured LLM output."""
    llm = get_llm_client()
    response = await llm._client.chat.completions.create(
        model=llm.model_name,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_schema", "json_schema": {"name": "extraction", "schema": EXTRACTION_SCHEMA}},
    )
    # Parse structured response into ExtractedEntity objects
    ...
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Synchronous Graph Extraction in Webhook Handlers

**What:** Running entity extraction + graph writes inline with webhook processing.

**Why bad:** LLM extraction calls take 500ms-2s. Slack expects webhook responses within 3 seconds. GitHub webhooks timeout at 10 seconds. Inline processing will cause webhook failures, data loss, and retry storms.

**Instead:** Store source data first, commit, then trigger extraction as a background task via `BackgroundTasks`. The graph is eventually consistent (seconds, not minutes).

### Anti-Pattern 2: Replacing Hybrid Search with Graph-Only Retrieval

**What:** Removing or deprioritizing vector + full-text search in favor of graph traversal.

**Why bad:** Graph retrieval only finds entities that have been explicitly extracted and linked. New content has no graph connections yet. Hybrid search works on raw content and catches things the graph misses. The graph supplements search; it does not replace it.

**Instead:** Graph is a third signal in the linking engine, blended with existing explicit refs (weight=1.0) and hybrid search (weight=0.8). The existing retrieval pipeline is the fallback.

### Anti-Pattern 3: Over-Extracting Entities with LLM

**What:** Running LLM extraction on every incoming message, including short replies, bot notifications, emoji reactions, and status updates.

**Why bad:** Most Slack messages are noise ("sounds good", "done", "thanks", bot automated messages). LLM extraction on these wastes money ($0.001-0.01 per call adds up) and fills the graph with low-value nodes. At scale with an active Slack workspace, this becomes expensive quickly.

**Instead:** Filter before extraction. Only run LLM extraction on: messages > 50 characters, non-bot messages, messages containing decision signal words, meeting transcript segments > 100 characters. Rule-based extraction runs on everything (it is free).

### Anti-Pattern 4: Eager Identity Merging on Fuzzy Name Matches

**What:** Automatically merging person nodes when names are similar (e.g., "Dan" and "Daniel", or "Alex Kim" and "Alex Chen").

**Why bad:** False merges corrupt the graph. If "Dan Smith" and "Daniel Jones" are incorrectly merged, all of Daniel Jones's edges now point to Dan Smith. Recovering from bad merges requires manual edge surgery. At a 3-person team this is manageable; at 50+ it is catastrophic.

**Instead:** Only auto-merge on deterministic signals (same email, same Slack user_id, same GitHub login). For fuzzy name matches, create a candidate `same_as` edge with confidence < 1.0 and leave it unmerged. Query-time resolution can follow `same_as` edges when needed.

### Anti-Pattern 5: Building Graph Explorer UI Before Backend Works

**What:** Starting with a React graph visualization component before the graph is populated with real data.

**Why bad:** You cannot build a meaningful UI without real graph data to test against. The graph schema, traversal queries, and extraction pipeline all need to work first. A graph explorer built against mock data will need to be rewritten once real data shapes are understood.

**Instead:** Build the backend pipeline first (schema -> extraction -> identity resolution -> retrieval). Verify the graph quality by inspecting data directly (SQL queries, API endpoints returning JSON). Only then build the visual explorer as a stretch goal.

---

## Integration Points with Existing Code (Detailed)

### 1. MODIFIED: `backend/src/services/linking.py`

Add graph signal as a third retrieval path in `find_related_content()`:

```python
# Add import
from src.services.graph.retrieval import find_graph_connections

WEIGHT_GRAPH = 0.9  # NEW constant

async def find_related_content(session, workspace_id, ticket) -> LinkingResult:
    explicit = await _find_explicit_refs(session, workspace_id, ticket)
    hybrid = await _find_hybrid_matches(session, workspace_id, ticket)
    graph = await find_graph_connections(session, workspace_id, ticket)  # NEW

    merged = {}
    for source, signal_items in [
        ("explicit", explicit),
        ("hybrid", hybrid),
        ("graph", graph),       # NEW third signal
    ]:
        for key, item in signal_items.items():
            if key in merged:
                existing = merged[key]
                existing.relevance_score += item.relevance_score
                existing.signals.extend(item.signals)
            else:
                merged[key] = item

    sorted_items = sorted(merged.values(), key=lambda x: x.relevance_score, reverse=True)
    return LinkingResult(
        ticket_id=ticket.id,
        ticket_identifier=ticket.identifier,
        items=sorted_items,
    )
```

### 2. MODIFIED: `backend/src/services/synthesis.py`

Extend the synthesis template with graph-derived sections:

```python
# Additional prompt block appended when graph context is available
GRAPH_CONTEXT_SECTION = """
### Decision Trail
{decision_trail}

### Key People & Involvement
{people_involvement}

### Cross-Source Connections
{relationship_paths}
"""
```

The `generate_context_page()` function needs to:
- Accept optional `GraphContext` data from the linking result
- Append decision trails, people involvement, and relationship paths to the prompt
- Only include these sections when graph data is available (graceful degradation)

### 3. MODIFIED: Webhook Handlers

Each webhook handler adds a `BackgroundTasks` call for entity extraction. Files affected:
- `backend/src/services/slack_events.py` -- after storing Slack messages
- `backend/src/services/linear_webhook.py` -- after processing ticket/comment updates
- `backend/src/services/github_webhook.py` -- after processing PR/review events
- `backend/src/services/notion_webhook.py` -- after processing page updates
- `backend/src/services/fathom.py` -- after storing meeting transcripts

### 4. MODIFIED: `backend/src/routers/context.py`

Add an optional API endpoint for graph data around a ticket (for frontend graph explorer):
```
GET /api/context/{ticket_identifier}/graph
```

### 5. MODIFIED: `supabase/migrations/` -- New Migration

A new migration `00017_graph_tables.sql` creates:
- `graph_nodes` table with all columns, constraints, indexes, RLS
- `graph_edges` table with all columns, constraints, indexes, RLS
- `traverse_graph()` function
- Updated triggers

### 6. NEW: `backend/src/models/graph.py`

SQLModel classes:
- `GraphNode` -- maps to `graph_nodes` table
- `GraphEdge` -- maps to `graph_edges` table

### 7. NEW: `backend/src/services/graph/` package

- `extraction.py` -- rule-based + LLM entity extraction
- `identity.py` -- cross-source person identity resolution
- `retrieval.py` -- graph traversal via recursive CTE, returns `LinkedItem` dicts
- `decisions.py` -- decision-specific extraction logic and formatting
- `schema.py` -- entity type enums, relationship type enums, extraction schemas

---

## Suggested Build Order

Based on dependency analysis, the components should be built in this sequence:

1. **Graph Schema + Models** (no dependencies, unblocks everything)
   - Migration: `graph_nodes` and `graph_edges` tables with RLS, indexes
   - SQLModel classes: `GraphNode`, `GraphEdge`
   - Traversal function: `traverse_graph()` SQL function
   - Estimated effort: small

2. **Rule-Based Entity Extraction** (depends on: graph schema)
   - Regex extractors for ticket IDs, @mentions, PR numbers, file paths
   - Node/edge upsert logic with fingerprint deduplication
   - Integration with webhook handlers via `BackgroundTasks`
   - High value, zero LLM cost -- populates graph immediately
   - Estimated effort: medium

3. **Identity Resolution** (depends on: entity extraction producing person nodes)
   - Deterministic matching (email, Slack user_id, GitHub login)
   - Person node merging with `same_as` edges
   - Properties JSONB aggregation across sources
   - Estimated effort: medium

4. **Graph-Enhanced Retrieval** (depends on: graph schema + some populated nodes)
   - `find_graph_connections()` function
   - Blended scoring with depth decay
   - Modify `find_related_content()` to include graph signal
   - Estimated effort: medium

5. **LLM Entity Extraction** (depends on: rule-based extraction pipeline working)
   - Decision extraction from Slack messages and meeting transcripts
   - Concept/feature extraction
   - Structured output via LLM client (JSON mode)
   - Content filtering (only run on high-value messages)
   - Estimated effort: medium-high

6. **Updated Synthesis Prompts** (depends on: graph retrieval integrated in linking)
   - Decision trail section in context pages
   - People involvement section
   - Relationship path descriptions
   - Graceful degradation when no graph data exists
   - Estimated effort: small-medium

7. **Graph Explorer UI** (stretch -- depends on: graph populated + retrieval working)
   - API endpoint returning graph data around a ticket
   - React component for graph visualization
   - Estimated effort: high (frontend)

---

## Sources

- [Supabase Extensions Documentation](https://supabase.com/docs/guides/database/extensions) -- AGE not available (HIGH confidence)
- [Supabase Discussion on AGE](https://github.com/orgs/supabase/discussions/40285) -- confirmed not installable (HIGH confidence)
- [Supabase Discussion #13263](https://github.com/orgs/supabase/discussions/13263) -- AGE not supported, workarounds discussed (HIGH confidence)
- [postgres-graph-rag library](https://github.com/h4gen/postgres-graph-rag) -- pure PG graph RAG approach validated (HIGH confidence)
- [Graph Retrieval with Recursive CTEs](https://www.sheshbabu.com/posts/graph-retrieval-using-postgres-recursive-ctes/) -- SQL traversal patterns (HIGH confidence)
- [Knowledge Graphs with PostgreSQL](https://app.readytensor.ai/publications/knowledge-graphs-with-postgresql-eQyINuo4ojwW) -- nodes/edges table approach (HIGH confidence)
- [LangChain LLMGraphTransformer](https://python.langchain.com/api_reference/experimental/graph_transformers/langchain_experimental.graph_transformers.llm.LLMGraphTransformer.html) -- entity extraction patterns (MEDIUM confidence)
- [GraphRAG Intro](https://graphrag.com/concepts/intro-to-graphrag/) -- retrieval architecture patterns (HIGH confidence)
- [GraphRAG at Scale](https://particula.tech/blog/graphrag-implementation-enterprise-data-platform) -- identity resolution is the hardest part (MEDIUM confidence)
- [Entity Resolved Knowledge Graphs (Neo4j)](https://neo4j.com/blog/developer/entity-resolved-knowledge-graphs/) -- identity resolution patterns (MEDIUM confidence)
- [Google Gemini Structured Outputs](https://blog.google/technology/developers/gemini-api-structured-outputs/) -- entity extraction with structured output (HIGH confidence)
- [LangExtract by Google](https://developers.googleblog.com/en/introducing-langextract-a-gemini-powered-information-extraction-library/) -- Gemini extraction library (MEDIUM confidence)
- [Gemini Large-Scale Entity Extraction](https://www.sweetspot-data.com/blog/gemini-les-miserables-graph) -- Gemini 2.5 Flash for graph construction (MEDIUM confidence)
- [source{d} Identity Matching](https://github.com/src-d/identity-matching) -- Git signature to person matching approach (LOW confidence, archived project)
- [Supabase pgrouting blog](https://supabase.com/blog/pgrouting-postgres-graph-database) -- Supabase's own approach to graph in Postgres (HIGH confidence)

---

*Architecture research: 2026-03-06*
