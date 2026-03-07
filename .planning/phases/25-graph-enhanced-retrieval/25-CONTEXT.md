# Phase 25: Graph-Enhanced Retrieval - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Add graph traversal as a third retrieval signal in `find_related_content()` alongside explicit refs and hybrid search. Graph results are scored with depth decay, blended with existing signals via additive boosting, and capped at a fixed token budget before synthesis. This phase does NOT change synthesis prompts beyond adding a graph section -- full context page enhancements (decision trails, relationship paths, cross-referenced people) are Phase 26.

</domain>

<decisions>
## Implementation Decisions

### Signal Weight & Ranking
- Graph signal weight: 0.8 (equal to hybrid search, explicit refs remain 1.0)
- Score overlap handling: Additive boost -- content found by both graph and hybrid scores higher than either alone (matches existing merging pattern in linking.py)
- Graph-only results: Always included regardless of text similarity overlap -- graph-only discoveries are the core value of graph retrieval
- Provenance metadata: Each graph result includes full traversal path in signals list (e.g., "graph:Ticket->discussed_in->SlackThread->authored_by->Person") for debugging and Phase 26 relationship path rendering

### Token Budget
- Budget scope: Single unified budget for ALL retrieval signals (explicit + hybrid + graph combined), not graph-only
- Budget size: 2,000 tokens global constant in config.py (CONTEXT_TOKEN_BUDGET=2000)
- Trim strategy: Signal diversity first -- guarantee at least 1 result from each signal type (explicit, hybrid, graph) before filling remaining budget by relevance_score descending
- Configuration: Global constant, not per-workspace

### Graph Result Formatting
- Prompt structure: Separate "Graph Connections" section in synthesis prompt, distinct from existing related content section
- Result detail: Path + snippet + entity type per result (e.g., "Ticket->discussed_in->SlackThread | [snippet] | SlackThread")
- Decision highlighting: Decision nodes rendered with special format: "[DECISION] description | By: person | In: source | Affects: ticket(s) | Confidence: X.X" -- gives decisions visual priority in the prompt
- Budget allocation: Graph section shares the same 2,000 token unified budget

### Traversal Tuning
- Default depth: 2 hops (matches Phase 22 traverse_graph() default)
- same_as edges: Followed transparently without counting as a hop -- identity-resolved people reach their full connection neighborhood. Phase 23 investment pays off here
- No graph node fallback: Silent fallback -- return empty graph results, continue with explicit + hybrid only. No errors, no warnings. Context page identical to pre-graph behavior (supports SYNTH-04 graceful degradation)
- Entity type prioritization: None -- all types treated equally. Depth-decay scoring handles relevance naturally

### Claude's Discretion
- Exact depth-decay formula (linear, exponential, or custom)
- How to find the ticket's starting graph node (fingerprint lookup strategy)
- Bulk source summary fetching strategy for graph results
- Token estimation method (rough char/4 or tiktoken)
- Test fixture design and graph neighborhood mocking
- Exact formatting strings for the graph section and decision highlighting

</decisions>

<specifics>
## Specific Ideas

- traverse_graph() SQL function is already built (Phase 22, migration 00018) -- call it directly from Python with the ticket's graph node ID
- LinkedItem dataclass is the shared result type -- graph results become LinkedItems with graph-specific signals
- Signal diversity trimming should work like: sort all items by score, reserve top-1 from each signal type, then fill remaining budget by score from the rest
- Decision node special formatting prepares the ground for Phase 26 decision trails without implementing the full synthesis changes
- same_as transparent following may require modifying traverse_graph() SQL or post-processing in Python to collapse identity paths

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `linking.py:find_related_content()` (lines 329-375): Two-signal retrieval engine to extend with third `_find_graph_results()` function
- `linking.py:LinkedItem` dataclass (lines 36-45): Shared result type for all signals, reuse for graph results
- `linking.py:_bulk_lookup_source_summaries()` (lines 266-304): N+1 prevention pattern for fetching content from source tables
- `graph_ops.compute_fingerprint()` (lines 21-31): Find ticket's graph node by fingerprint lookup
- `traverse_graph()` SQL function (migration 00018): Ready-to-call recursive CTE with depth, direction, entity/relationship filtering
- `linking.py` weight constants (lines 28-30): WEIGHT_EXPLICIT=1.0, WEIGHT_HYBRID=0.8 -- add WEIGHT_GRAPH=0.8

### Established Patterns
- Signal merging: Additive score combining with signal list extension (linking.py lines 358-366)
- Fail-silent graph operations: Phase 22-03 pattern -- errors logged but never raised
- SECURITY DEFINER: traverse_graph() validates workspace once, bypasses per-row RLS
- Score normalization: hybrid_search() returns 0-1 combined_score via semantic_weight + keyword_weight

### Integration Points
- `backend/src/services/linking.py`: Add `_find_graph_results()` alongside `_find_explicit_refs()` and `_find_hybrid_matches()`
- `backend/src/services/synthesis.py`: Add graph section formatting in `_format_related_content()` (line 56) and token trimming before LLM call (line 137)
- `backend/src/config.py`: Add CONTEXT_TOKEN_BUDGET=2000 and GRAPH_MAX_DEPTH=2
- `supabase/migrations/00018_traverse_graph_function.sql`: May need modification for transparent same_as following (or handle in Python post-processing)

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 25-graph-enhanced-retrieval*
*Context gathered: 2026-03-08*
