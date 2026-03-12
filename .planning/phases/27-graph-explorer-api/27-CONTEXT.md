# Phase 27: Graph Explorer API - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

A GET endpoint exposes the graph neighborhood for any ticket as structured JSON (nodes + edges), enabling future frontend visualization (GAPI-02) and external tool consumption. This phase delivers the API only — no frontend visualization component.

</domain>

<decisions>
## Implementation Decisions

### Response Shape
- Nodes + edges arrays format: `{ nodes: [...], edges: [...] }` — standard graph interchange, directly compatible with react-force-graph and D3
- Each node includes: id, entity_type, name, depth (0 = root ticket), properties (JSONB)
- Each edge includes: source (node UUID), target (node UUID), relationship_type, properties (JSONB)
- Top-level metadata: ticket_identifier, depth (requested), node_count, edge_count
- Root ticket is a regular node with depth=0 — no separate root field
- Properties included on both nodes and edges (confidence scores, status, rationale, etc.)

### Error & Empty States
- Unknown ticket identifier (not in linear_tickets table): 404 with `"Ticket {id} not found"`
- Ticket exists but has no graph node: Empty 200 with `nodes: [], edges: [], node_count: 0`
- Matches Phase 25's silent fallback pattern — missing graph data is normal, not an error
- Two distinct states: "ticket doesn't exist" (404 error) vs "ticket has no graph" (200 empty)

### Node Cap & Limits
- Default cap: 50 nodes per response
- Adjustable via `?limit=N` query param, hard max 200
- When truncated: response includes `truncated: true` and `total_available: N`
- Sort priority: depth ascending (closer nodes first), then by edge count
- No cursor pagination — cap is sufficient for neighborhood overview use case

### Claude's Discretion
- URL path design (e.g., `/api/graph/{ticket_identifier}` vs `/api/graph/neighborhood/{ticket_identifier}`)
- Exact query parameter names for depth and limit
- Whether to support entity_type/relationship_type filtering via query params (traverse_graph() already supports it)
- Deduplication of nodes returned from traverse_graph() (same node reachable via multiple paths)
- Pydantic response models vs dict serialization
- Test fixture design and graph neighborhood mocking

</decisions>

<specifics>
## Specific Ideas

- traverse_graph() SQL function is already built (Phase 22, migration 00018) — call it directly with the ticket's graph node ID
- _find_graph_results() in linking.py (Phase 25) already does fingerprint-based graph node lookup + traverse_graph() call — similar pattern reusable for the API endpoint
- compute_fingerprint('Ticket', identifier) gives the starting node fingerprint
- Response shape directly compatible with future GAPI-02 react-force-graph-2d visualization

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `graph_ops.compute_fingerprint()`: Find ticket's graph node by fingerprint lookup
- `traverse_graph()` SQL function (migration 00018): Recursive CTE with depth, direction, entity_types[], relationship_types[] filtering
- `linking.py:_find_graph_results()`: Working pattern for fingerprint lookup → traverse_graph() → result processing
- `GraphNode` / `GraphEdge` SQLModel models: Schema for graph tables
- `UserContext` dependency: JWT auth with workspace_id extraction
- `get_session` dependency: Async database session injection

### Established Patterns
- Router pattern: `APIRouter(prefix="/api/...", tags=[...])` registered in main.py
- Auth pattern: `user: UserContext = Depends(get_current_user)` for workspace-scoped endpoints
- 404 pattern: `raise HTTPException(status_code=404, detail=...)` for missing resources
- Response format: Dict returns with explicit field serialization (see context.py)
- SECURITY DEFINER: traverse_graph() validates workspace once, bypasses per-row RLS

### Integration Points
- `backend/src/routers/`: New graph.py router file
- `backend/src/main.py`: Register graph_router with `app.include_router()`
- `backend/src/services/graph_ops.py`: Reuse compute_fingerprint()
- `supabase/migrations/00018_traverse_graph_function.sql`: Called via `text()` SQL

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 27-graph-explorer-api*
*Context gathered: 2026-03-08*
