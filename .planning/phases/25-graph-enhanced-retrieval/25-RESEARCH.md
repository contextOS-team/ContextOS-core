# Phase 25: Graph-Enhanced Retrieval - Research

**Researched:** 2026-03-08
**Domain:** Graph traversal integration into multi-signal retrieval engine, token budgeting, depth-decay scoring, prompt formatting
**Confidence:** HIGH

## Summary

This phase adds graph traversal as a third retrieval signal in `find_related_content()` alongside explicit refs (weight 1.0) and hybrid search (weight 0.8). The graph infrastructure is fully built on a parallel branch (Phases 22-24 in v1.2 numbering): `graph_nodes` and `graph_edges` tables, `traverse_graph()` SQL function, `graph_ops.py` service, identity resolution with `same_as` edges, and LLM-based decision extraction. All of this code must be merged before Phase 25 work begins.

The implementation is a focused Python-side integration: (1) a new `_find_graph_results()` function in `linking.py` that calls `traverse_graph()` SQL, applies depth-decay scoring, and returns `LinkedItem` results with graph provenance metadata; (2) a unified token budget (2,000 tokens) applied across all three signal types with signal-diversity-first trimming; (3) a separate "Graph Connections" section in the synthesis prompt with decision node highlighting. The entire phase stays within `linking.py`, `synthesis.py`, and `config.py` -- no new tables, no new endpoints, no frontend changes.

**Primary recommendation:** Build `_find_graph_results()` as a peer function to `_find_explicit_refs()` and `_find_hybrid_matches()`, using the same `LinkedItem` return type and `dict[tuple[str, UUID], LinkedItem]` merging pattern. Apply exponential depth decay (score = base_score * decay^depth where decay ~0.5-0.7) for graph scoring. Handle `same_as` edge transparency in Python post-processing rather than modifying the SQL function. Add token budget trimming as a new function called after merging all three signals.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Graph signal weight: 0.8 (equal to hybrid search, explicit refs remain 1.0)
- Score overlap handling: Additive boost -- content found by both graph and hybrid scores higher than either alone (matches existing merging pattern in linking.py)
- Graph-only results: Always included regardless of text similarity overlap -- graph-only discoveries are the core value of graph retrieval
- Provenance metadata: Each graph result includes full traversal path in signals list (e.g., "graph:Ticket->discussed_in->SlackThread->authored_by->Person") for debugging and Phase 26 relationship path rendering
- Budget scope: Single unified budget for ALL retrieval signals (explicit + hybrid + graph combined), not graph-only
- Budget size: 2,000 tokens global constant in config.py (CONTEXT_TOKEN_BUDGET=2000)
- Trim strategy: Signal diversity first -- guarantee at least 1 result from each signal type (explicit, hybrid, graph) before filling remaining budget by relevance_score descending
- Configuration: Global constant, not per-workspace
- Prompt structure: Separate "Graph Connections" section in synthesis prompt, distinct from existing related content section
- Result detail: Path + snippet + entity type per result (e.g., "Ticket->discussed_in->SlackThread | [snippet] | SlackThread")
- Decision highlighting: Decision nodes rendered with special format: "[DECISION] description | By: person | In: source | Affects: ticket(s) | Confidence: X.X"
- Budget allocation: Graph section shares the same 2,000 token unified budget
- Default depth: 2 hops (matches Phase 22 traverse_graph() default)
- same_as edges: Followed transparently without counting as a hop -- identity-resolved people reach their full connection neighborhood
- No graph node fallback: Silent fallback -- return empty graph results, continue with explicit + hybrid only. No errors, no warnings
- Entity type prioritization: None -- all types treated equally. Depth-decay scoring handles relevance naturally

### Claude's Discretion
- Exact depth-decay formula (linear, exponential, or custom)
- How to find the ticket's starting graph node (fingerprint lookup strategy)
- Bulk source summary fetching strategy for graph results
- Token estimation method (rough char/4 or tiktoken)
- Test fixture design and graph neighborhood mocking
- Exact formatting strings for the graph section and decision highlighting

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlalchemy | >=2.0 (existing) | Call traverse_graph() via `text()` SQL, async session | Already used throughout linking.py |
| sqlmodel | >=0.22 (existing) | GraphNode model queries for fingerprint lookup | Already used for all models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib | stdlib | Compute fingerprint to find ticket's graph node | Always -- `compute_fingerprint("Ticket", ticket.identifier)` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| char/4 token estimation | tiktoken library | tiktoken is accurate but adds a dependency; char/4 is sufficient for budget enforcement at this scale |
| Python same_as handling | Modified traverse_graph() SQL | SQL modification would be cleaner but riskier; Python post-processing is safer and more testable |
| Exponential depth decay | Linear depth decay | Exponential penalizes distant nodes more aggressively, better matching intuition that 2-hop results are much less relevant than 1-hop |

**Installation:**
```bash
# No new dependencies needed -- all existing libraries
```

## Architecture Patterns

### Recommended Integration Points
```
backend/src/services/linking.py     # Add _find_graph_results(), modify find_related_content(), add _apply_token_budget()
backend/src/services/synthesis.py   # Add _format_graph_section() for separate Graph Connections prompt section
backend/src/config.py               # Add CONTEXT_TOKEN_BUDGET=2000 and GRAPH_MAX_DEPTH=2 constants
```

### Pattern 1: Graph Signal as Peer Function
**What:** `_find_graph_results()` follows the exact same pattern as `_find_explicit_refs()` and `_find_hybrid_matches()` -- takes `(session, workspace_id, ticket)`, returns `dict[tuple[str, UUID], LinkedItem]`.
**When to use:** Always -- this is the core integration pattern.
**Example:**
```python
# Source: Existing linking.py pattern (lines 61-219)
async def _find_graph_results(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find related content via knowledge graph traversal."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    try:
        # 1. Find the ticket's graph node via fingerprint
        from src.services.graph_ops import compute_fingerprint
        fingerprint = compute_fingerprint("Ticket", ticket.identifier)

        node_stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.fingerprint == fingerprint,
            GraphNode.deleted_at.is_(None),
        )
        result = await session.execute(node_stmt)
        start_node = result.scalar_one_or_none()

        if start_node is None:
            return items  # Silent fallback

        # 2. Call traverse_graph() SQL function
        traverse_stmt = text("""
            SELECT node_id, entity_type, name, properties,
                   edge_relationship_type, depth, path
            FROM traverse_graph(
                CAST(:start_node_id AS uuid),
                CAST(:workspace_id AS uuid),
                :max_depth,
                'both',
                NULL,
                NULL
            )
            WHERE depth > 0
        """)
        traverse_result = await session.execute(traverse_stmt, {
            "start_node_id": str(start_node.id),
            "workspace_id": str(workspace_id),
            "max_depth": GRAPH_MAX_DEPTH,
        })

        # 3. Process results with depth-decay scoring
        graph_rows = traverse_result.fetchall()
        # ... (expand same_as, score, build LinkedItems)

    except Exception:
        logger.warning("Graph retrieval failed for %s", ticket.identifier, exc_info=True)

    return items
```

### Pattern 2: same_as Transparent Following (Python Post-Processing)
**What:** After getting traverse_graph() results, identify `same_as` edges and re-traverse from the canonical Person node without incrementing depth.
**When to use:** When graph results include Person nodes connected via `same_as`.
**Example:**
```python
# Post-process: for each result with same_as edge, fetch the canonical
# node's additional neighbors at the SAME depth level
for row in graph_rows:
    if row.edge_relationship_type == "same_as":
        # This is a canonical person node -- traverse its neighbors
        # at effective depth = row.depth (not row.depth + 1)
        canonical_neighbors = await _traverse_from_node(
            session, row.node_id, workspace_id,
            remaining_depth=GRAPH_MAX_DEPTH - row.depth + 1,  # +1 because same_as doesn't count
        )
        # Add canonical neighbors to results with adjusted depth
```

**Alternative (simpler):** Instead of re-traversing, simply increase `max_depth` by 1 in the initial call and then subtract 1 from the depth of any node reached via a `same_as` hop. This avoids the extra DB query.

### Pattern 3: Signal Diversity First Trimming
**What:** After merging all three signals, guarantee at least 1 result from each signal type that contributed, then fill remaining token budget by descending relevance_score.
**When to use:** In the new `_apply_token_budget()` function, called after merging in `find_related_content()`.
**Example:**
```python
def _apply_token_budget(
    items: list[LinkedItem],
    budget_tokens: int = CONTEXT_TOKEN_BUDGET,
) -> list[LinkedItem]:
    """Trim items to fit within token budget with signal diversity guarantee."""
    if not items:
        return items

    # Group by primary signal type
    signal_groups: dict[str, list[LinkedItem]] = {}
    for item in items:
        primary_signal = item.signals[0] if item.signals else "unknown"
        # Normalize: "explicit_link"/"explicit_reference" -> "explicit"
        # "hybrid_search" -> "hybrid", "graph:..." -> "graph"
        signal_key = _normalize_signal(primary_signal)
        signal_groups.setdefault(signal_key, []).append(item)

    # Reserve top-1 from each signal type
    reserved: list[LinkedItem] = []
    remaining_pool: list[LinkedItem] = []

    for signal_key, group in signal_groups.items():
        group.sort(key=lambda x: x.relevance_score, reverse=True)
        reserved.append(group[0])
        remaining_pool.extend(group[1:])

    # Sort remaining by score
    remaining_pool.sort(key=lambda x: x.relevance_score, reverse=True)

    # Fill budget
    result: list[LinkedItem] = list(reserved)
    used_tokens = sum(_estimate_tokens(item) for item in result)

    for item in remaining_pool:
        item_tokens = _estimate_tokens(item)
        if used_tokens + item_tokens > budget_tokens:
            break
        result.append(item)
        used_tokens += item_tokens

    result.sort(key=lambda x: x.relevance_score, reverse=True)
    return result
```

### Pattern 4: Depth-Decay Scoring
**What:** Graph results scored using exponential decay based on traversal depth.
**When to use:** When converting graph traversal rows to LinkedItem relevance_score.
**Recommended formula:** `score = WEIGHT_GRAPH * (DECAY_FACTOR ** depth)` where `DECAY_FACTOR = 0.6`.
```python
WEIGHT_GRAPH = 0.8
DEPTH_DECAY = 0.6

# depth=1: 0.8 * 0.6^1 = 0.48
# depth=2: 0.8 * 0.6^2 = 0.288
# depth=0 is the start node (the ticket itself), excluded from results
```
**Why exponential over linear:** Linear decay (e.g., `0.8 * (1 - depth/max_depth)`) gives depth=1 a score of 0.4 and depth=2 a score of 0.0, which means 2-hop results would score zero. Exponential decay always produces a positive score, and the steep falloff at higher depths naturally deprioritizes distant nodes without excluding them.

### Anti-Patterns to Avoid
- **Do NOT modify the traverse_graph() SQL function** for same_as handling -- handle it in Python. SQL modifications require a new migration and are harder to test.
- **Do NOT add per-workspace budget configuration** -- the user explicitly decided on a global constant.
- **Do NOT replace the existing `_format_related_content()`** -- add a new `_format_graph_section()` alongside it. The prompt must have a separate Graph Connections section.
- **Do NOT filter graph results by entity type** -- the user explicitly decided all types are treated equally, with depth-decay handling relevance naturally.
- **Do NOT raise exceptions on graph failures** -- follow the Phase 22-03 fail-silent pattern: log warnings, return empty results.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph traversal | Custom recursive Python traversal | `traverse_graph()` SQL function (migration 00018) | Already built, cycle-detection via path array, workspace-scoped, SECURITY DEFINER for performance |
| Fingerprint computation | Manual hash construction | `graph_ops.compute_fingerprint()` | SHA-256 deterministic, already standard across all graph code |
| Source summary lookup | Per-result DB queries | `_bulk_lookup_source_summaries()` | Existing N+1 prevention pattern, groups by source_type |
| Score merging | Custom merge logic | Existing additive pattern in `find_related_content()` lines 431-444 | Already handles multi-signal score accumulation |

**Key insight:** Almost everything needed is already built. The graph schema, traversal function, fingerprint system, node/edge models, and entity extraction pipeline are all complete on the graph branch. This phase is purely about wiring graph results into the existing linking engine and adding token budget management.

## Common Pitfalls

### Pitfall 1: Graph Node Not Found for Ticket
**What goes wrong:** The ticket has no corresponding graph node in `graph_nodes`, so `_find_graph_results()` returns empty.
**Why it happens:** The ticket was created before graph extraction was enabled, or graph backfill hasn't run yet.
**How to avoid:** Silent fallback (per CONTEXT.md decision). Return empty dict, continue with explicit + hybrid. This is the expected behavior -- pre-graph content still works identically.
**Warning signs:** All context pages show no graph results. Run graph backfill.

### Pitfall 2: same_as Edge Creates Infinite Traversal
**What goes wrong:** Following `same_as` edges transparently without depth counting leads to traversing through all identity-linked person nodes and their neighborhoods, potentially returning the entire graph.
**Why it happens:** If a canonical Person node has 5 platform Person nodes via same_as, and each has neighbors, the expansion is multiplicative.
**How to avoid:** Cap total results (e.g., max 20 graph results before budget trimming). Also, when expanding via same_as, only traverse outbound edges from the canonical node (not back through other same_as edges). Add a seen-nodes set to prevent revisiting.
**Warning signs:** Graph retrieval returns hundreds of results or takes > 1 second.

### Pitfall 3: Token Budget Estimation Drift
**What goes wrong:** Using char/4 for token estimation is inaccurate for content with lots of short words, code snippets, or non-ASCII characters, causing the prompt to exceed LLM context limits.
**Why it happens:** char/4 is an approximation; real tokenization varies by 20-30%.
**How to avoid:** Use a conservative estimate (char/3.5 or char/3) to leave buffer. At 2,000 tokens budget, even 30% overestimate only adds ~600 tokens, well within Gemini Flash's 1M context window.
**Warning signs:** LLM responses getting truncated or mentioning they couldn't process all context.

### Pitfall 4: Merging Graph and Hybrid Results Creates Duplicate Snippets
**What goes wrong:** A Slack message found by both hybrid search (via embedding similarity) and graph traversal (via mentions edge) appears with different snippets or inconsistent metadata.
**Why it happens:** Hybrid search returns snippet from the embeddings table metadata, while graph traversal returns snippet from the source table via bulk lookup.
**How to avoid:** When merging, always keep the existing item's snippet/title (the first signal to find it). The additive scoring just bumps relevance_score and extends signals list, preserving the original content.
**Warning signs:** Duplicate content in the prompt, or conflicting information in the same result.

### Pitfall 5: traverse_graph() Returns the Start Node
**What goes wrong:** The start node (the ticket itself) is included in graph results, creating a self-referencing LinkedItem.
**Why it happens:** The SQL function returns the start node at depth=0 as the anchor of the recursive CTE.
**How to avoid:** Filter out depth=0 results in Python, or add `WHERE depth > 0` to the SQL query.
**Warning signs:** The ticket appearing in its own "Graph Connections" section.

### Pitfall 6: Graph Results Without Source Records
**What goes wrong:** Graph nodes exist for entities that have no corresponding source record in the application tables (e.g., a Person node extracted from a Slack message has no standalone table row).
**Why it happens:** Graph nodes are created for all extracted entities, but not all entity types map to application tables (e.g., Person, Decision, Blocker have no dedicated source table).
**How to avoid:** For graph results where the entity_type doesn't map to a source table (Person, Decision, Blocker, Feature, Component), use the graph node's own `name` and `properties` to build the snippet directly, rather than trying to look up a source record. Only use `_bulk_lookup_source_summaries()` for entity types that have source tables (Ticket->linear_ticket, SlackThread->slack_message, PR->github_pull_request, etc.).
**Warning signs:** Empty snippets for Person and Decision results.

## Code Examples

### Finding the Ticket's Graph Node via Fingerprint
```python
# Source: graph_ops.compute_fingerprint() from the graph branch
from src.services.graph_ops import compute_fingerprint
from src.models.graph_node import GraphNode

fingerprint = compute_fingerprint("Ticket", ticket.identifier)
# fingerprint = sha256("Ticket:CON-16".encode()).hexdigest()

node_stmt = select(GraphNode).where(
    GraphNode.workspace_id == workspace_id,
    GraphNode.fingerprint == fingerprint,
    GraphNode.deleted_at.is_(None),
)
result = await session.execute(node_stmt)
start_node = result.scalar_one_or_none()
```

### Calling traverse_graph() from Python
```python
# Source: 00018_traverse_graph_function.sql
traverse_stmt = text("""
    SELECT node_id, entity_type, name, properties,
           edge_relationship_type, depth, path
    FROM traverse_graph(
        CAST(:start_node_id AS uuid),
        CAST(:workspace_id AS uuid),
        :max_depth,
        'both',
        NULL,
        NULL
    )
    WHERE depth > 0
""")
result = await session.execute(traverse_stmt, {
    "start_node_id": str(start_node.id),
    "workspace_id": str(workspace_id),
    "max_depth": 2,
})
rows = result.fetchall()
# Each row: (node_id, entity_type, name, properties, edge_relationship_type, depth, path)
```

### Building Graph Path Provenance String
```python
# Source: CONTEXT.md requirement for provenance metadata
# path column is uuid[] -- map through graph_nodes to build readable path
def _build_path_string(rows_by_id: dict, path: list[UUID]) -> str:
    """Build human-readable traversal path from UUID path array.

    Example output: "graph:Ticket->discussed_in->SlackThread->authored_by->Person"
    """
    parts = []
    for node_id in path:
        node_info = rows_by_id.get(node_id)
        if node_info:
            if parts:
                parts.append(node_info.edge_relationship_type or "?")
            parts.append(node_info.entity_type)
    return "graph:" + "->".join(parts)
```

### Entity Type to Source Type Mapping for Bulk Lookup
```python
# Map graph entity_types to source_types used by _bulk_lookup_source_summaries()
ENTITY_TO_SOURCE_TYPE: dict[str, str] = {
    "Ticket": "linear_ticket",
    "SlackThread": "slack_message",
    "PR": "github_pull_request",
    "CodeChunk": "code_chunk",
    "NotionPage": "notion_page",
    "Meeting": "meeting_transcript",
}

# Entity types that have no source table -- use graph node data directly
GRAPH_ONLY_ENTITIES = {"Person", "Decision", "Blocker", "Feature", "Component"}
```

### Decision Node Formatting
```python
# Source: CONTEXT.md decision highlighting format
def _format_decision_node(name: str, properties: dict) -> str:
    """Format a Decision graph node with special highlighting.

    Format: "[DECISION] description | By: person | In: source | Affects: ticket(s) | Confidence: X.X"
    """
    person = properties.get("person_name", "Unknown")
    source = properties.get("source_type", "Unknown")
    tickets = ", ".join(properties.get("ticket_refs", []))
    confidence = properties.get("confidence", "N/A")

    parts = [f"[DECISION] {name}"]
    parts.append(f"By: {person}")
    parts.append(f"In: {source}")
    if tickets:
        parts.append(f"Affects: {tickets}")
    parts.append(f"Confidence: {confidence}")

    return " | ".join(parts)
```

### Token Estimation
```python
def _estimate_tokens(item: LinkedItem) -> int:
    """Estimate token count for a LinkedItem using char/4 approximation.

    Counts title + snippet + signal metadata. Conservative enough
    for budget enforcement without needing tiktoken dependency.
    """
    text_len = len(item.title) + len(item.snippet) + sum(len(s) for s in item.signals)
    # Add overhead for formatting (section headers, separators)
    return (text_len + 50) // 4
```

### Graph Section in Synthesis Prompt
```python
# New template section to add after {related_content}
GRAPH_SECTION_TEMPLATE = """\
### Graph Connections
The following items were discovered through knowledge graph traversal --
connections between entities that may not appear in direct text search:

{graph_content}
"""

def _format_graph_section(graph_items: list[LinkedItem]) -> str:
    """Format graph-discovered items for the synthesis prompt."""
    if not graph_items:
        return ""

    sections = []
    for item in graph_items:
        if item.source_type == "Decision":
            # Special decision formatting
            section = _format_decision_node(item.title, ...)
        else:
            # Standard: path + snippet + entity type
            path_signal = next((s for s in item.signals if s.startswith("graph:")), "")
            section = f"**{path_signal}**\n{item.snippet}\n*Type: {item.source_type}*"
        sections.append(section)

    return GRAPH_SECTION_TEMPLATE.format(graph_content="\n\n".join(sections))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Two-signal retrieval (explicit + hybrid) | Three-signal with graph traversal | This phase | Graph-only discoveries surface multi-hop connections |
| No token budget | Unified 2,000 token budget with diversity trimming | This phase | Prevents prompt flooding while ensuring signal variety |
| Single "Related Content" prompt section | Split: Related Content + Graph Connections | This phase | Gives LLM clearer signal about graph-discovered context |

**Branch state:** The graph infrastructure (tables, traverse function, models, extractors, identity resolution, LLM extraction) is complete on a parallel git branch (`a0c612d`). These branches must be merged before Phase 25 implementation.

## Open Questions

1. **Branch merge strategy**
   - What we know: Graph infrastructure is on a separate branch from HEAD. Phase 25 code changes depend on GraphNode model, graph_ops module, and traverse_graph() SQL function.
   - What's unclear: Whether the branches will be merged before Phase 25 planning or the plan should include merge tasks.
   - Recommendation: Assume merge happens first (prerequisite). If not, Plan 01 must start with merging the graph branch.

2. **same_as expansion approach**
   - What we know: `traverse_graph()` already follows same_as edges, but counts them as hops. CONTEXT.md says same_as should not count as a hop.
   - What's unclear: Whether to modify the SQL function or handle in Python.
   - Recommendation: Handle in Python post-processing. After initial traversal, identify nodes reached via same_as edges, then do a second traverse_graph() call from those canonical nodes with remaining depth budget. Simpler: just call traverse_graph() with max_depth=3 and treat same_as traversals as depth-0 transitions (subtract 1 from their depth when scoring).

3. **Graph node source_id population completeness**
   - What we know: Graph nodes have optional `source_type` and `source_id` fields linking back to application tables. These are populated during extraction.
   - What's unclear: Whether all graph nodes have populated source_id fields, or if some (especially LLM-extracted Decision/Blocker nodes) lack them.
   - Recommendation: For nodes without source_id, use the node's own `name` and `properties` as the snippet. For nodes with source_id, use `_bulk_lookup_source_summaries()` for richer content.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | backend/pyproject.toml ([tool.pytest] if present) |
| Quick run command | `cd backend && python -m pytest tests/test_linking.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-SIGNAL | _find_graph_results returns LinkedItems with graph provenance | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_find_graph_results_basic -x` | Wave 0 |
| GRAPH-FALLBACK | _find_graph_results returns empty when no graph node exists | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_find_graph_results_no_node -x` | Wave 0 |
| GRAPH-ERROR | _find_graph_results returns empty on DB error (fail-silent) | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_find_graph_results_error_silent -x` | Wave 0 |
| DEPTH-DECAY | Depth-1 results score higher than depth-2 results | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_depth_decay_scoring -x` | Wave 0 |
| SAME-AS | same_as edges don't count as depth hops | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_same_as_transparent -x` | Wave 0 |
| MERGE-3WAY | find_related_content merges all 3 signals with additive scoring | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_three_signal_merge -x` | Wave 0 |
| TOKEN-BUDGET | _apply_token_budget trims results within 2000 token limit | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_token_budget_basic -x` | Wave 0 |
| TOKEN-DIVERSITY | _apply_token_budget guarantees 1 result per signal type | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_token_budget_diversity -x` | Wave 0 |
| GRAPH-SECTION | _format_graph_section produces separate prompt section | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py::test_format_graph_section -x` | Wave 0 |
| DECISION-FMT | Decision nodes render with [DECISION] highlighting | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py::test_decision_node_format -x` | Wave 0 |
| E2E-MERGE | generate_context_page calls graph signal and includes graph section | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py::test_generate_includes_graph -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_linking_graph.py tests/test_synthesis_graph.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_linking_graph.py` -- covers graph signal, depth decay, same_as, 3-way merge, token budget
- [ ] `backend/tests/test_synthesis_graph.py` -- covers graph section formatting, decision highlighting, e2e graph in synthesis

*(No framework install needed -- pytest and pytest-asyncio are already in dev dependencies)*

## Sources

### Primary (HIGH confidence)
- Project codebase: `backend/src/services/linking.py` -- current two-signal retrieval engine, LinkedItem dataclass, merging pattern, bulk lookup
- Project codebase: `backend/src/services/synthesis.py` -- current synthesis prompt template, _format_related_content(), generate_context_page()
- Project codebase (graph branch `a0c612d`): `backend/src/services/graph_ops.py` -- compute_fingerprint(), upsert_node(), upsert_edge()
- Project codebase (graph branch `a0c612d`): `backend/src/models/graph_node.py` -- GraphNode model with fingerprint, entity_type, properties
- Project codebase (graph branch `a0c612d`): `backend/src/models/graph_edge.py` -- GraphEdge model with relationship_type
- Project codebase (graph branch `a0c612d`): `supabase/migrations/00018_traverse_graph_function.sql` -- traverse_graph() recursive CTE with cycle detection
- Project codebase (graph branch `a0c612d`): `supabase/migrations/00017_graph_tables.sql` -- graph_nodes/graph_edges schema with entity types and relationship types
- Project codebase (graph branch `a0c612d`): `backend/src/services/identity_resolution.py` -- same_as edge creation, canonical person nodes
- Project codebase: `backend/tests/test_linking.py` -- existing test patterns (mock session, mock ticket, mock results)
- Phase 25 CONTEXT.md -- all user decisions and integration points

### Secondary (MEDIUM confidence)
- Project STATE.md -- accumulated decisions from Phases 22-24 (graph schema, extractors, identity resolution, LLM extraction)

### Tertiary (LOW confidence)
- None -- all findings verified with primary codebase sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing libraries
- Architecture: HIGH -- follows existing linking.py patterns exactly, graph infrastructure fully built
- Pitfalls: HIGH -- identified through codebase analysis (same_as expansion, source_id gaps, depth-0 filtering)

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable domain, all dependencies are project-internal)
