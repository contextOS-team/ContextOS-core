# Phase 27: Graph Explorer API - Research

**Researched:** 2026-03-08
**Domain:** FastAPI REST endpoint for graph neighborhood traversal
**Confidence:** HIGH

## Summary

Phase 27 adds a single GET endpoint that exposes a ticket's graph neighborhood as structured JSON (nodes + edges). The implementation is straightforward because all infrastructure already exists: `traverse_graph()` SQL function (Phase 22), `compute_fingerprint()` for ticket lookup (graph_ops.py), workspace-scoped auth via `UserContext`, and the established router registration pattern in main.py. The `_find_graph_results()` function in linking.py provides a near-identical pattern for fingerprint lookup then traverse_graph() call.

The main design challenge is reconstructing explicit edge records. `traverse_graph()` returns per-node rows with the relationship type used to reach each node and a path array, but does not return edge IDs, edge properties, or edges between sibling nodes. The endpoint needs a two-step approach: (1) traverse_graph() to discover the node set, (2) query graph_edges between those nodes for complete edge data with properties.

**Primary recommendation:** Create a single router file `backend/src/routers/graph.py` with one GET endpoint. Use traverse_graph() for node discovery, then query graph_edges for the discovered node set. Apply node cap (default 50, max 200) and return truncation metadata. Follow existing context.py router patterns exactly.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Response shape: `{ nodes: [...], edges: [...] }` with metadata (ticket_identifier, depth, node_count, edge_count)
- Node fields: id, entity_type, name, depth (0 = root), properties (JSONB)
- Edge fields: source (node UUID), target (node UUID), relationship_type, properties (JSONB)
- Root ticket is a regular node with depth=0, no separate root field
- Unknown ticket identifier (not in linear_tickets): 404 with `"Ticket {id} not found"`
- Ticket exists but has no graph node: empty 200 with `nodes: [], edges: [], node_count: 0`
- Default cap: 50 nodes, adjustable via `?limit=N`, hard max 200
- Truncated responses include `truncated: true` and `total_available: N`
- Sort priority: depth ascending (closer first), then by edge count

### Claude's Discretion
- URL path design (e.g., `/api/graph/{ticket_identifier}` vs `/api/graph/neighborhood/{ticket_identifier}`)
- Exact query parameter names for depth and limit
- Whether to support entity_type/relationship_type filtering via query params
- Deduplication of nodes from traverse_graph() (same node reachable via multiple paths)
- Pydantic response models vs dict serialization
- Test fixture design and graph neighborhood mocking

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GAPI-01 | GET endpoint returns subgraph JSON (nodes + edges) for a ticket's graph neighborhood | All infrastructure exists: traverse_graph() SQL, compute_fingerprint(), GraphNode/GraphEdge models, router patterns, workspace-scoped auth. Two-step query pattern: traverse for nodes, then fetch edges between node set. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | (installed) | API router, path params, query params, Depends | Project standard -- all routers use it |
| SQLAlchemy | >=2.0 (async) | Raw SQL execution for traverse_graph(), ORM queries for graph_edges | Project uses sqlalchemy.text() for SQL function calls |
| SQLModel | >=0.0.22 | GraphNode/GraphEdge model queries | Project ORM -- all models inherit from it |
| Pydantic | >=2.0 | Response model validation (discretionary) | Already used for request bodies in context.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| graph_ops.compute_fingerprint() | internal | SHA-256 fingerprint for ticket node lookup | Finding root graph node for a ticket identifier |
| src.dependencies.UserContext | internal | JWT auth + workspace_id extraction | Workspace scoping on the endpoint |
| src.db.get_session | internal | Async session injection | Database access |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dict serialization | Pydantic response models | Pydantic gives type safety and OpenAPI schema generation, slightly more code. **Recommend Pydantic** for this endpoint since the response shape is well-defined and benefits from schema docs. |
| Two-step query (traverse + edges) | Single traverse_graph() with path reconstruction | Path reconstruction misses cross-edges between sibling nodes and lacks edge properties/IDs. Two-step is correct. |

**Installation:**
No new dependencies needed -- everything is already installed.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/
  routers/
    graph.py          # NEW: Graph explorer endpoint
  services/
    graph_ops.py      # EXISTING: compute_fingerprint() reused
  models/
    graph_node.py     # EXISTING: GraphNode model
    graph_edge.py     # EXISTING: GraphEdge model
  main.py             # MODIFIED: Register graph_router
```

### Pattern 1: Router Registration
**What:** New router file follows established pattern, registered in main.py
**When to use:** Always for new endpoints
**Example:**
```python
# backend/src/routers/graph.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.graph_node import GraphNode
from src.models.ticket import LinearTicket
from src.services.graph_ops import compute_fingerprint

router = APIRouter(prefix="/api/graph", tags=["graph"])

# In main.py:
# from src.routers.graph import router as graph_router
# app.include_router(graph_router)
```

### Pattern 2: Fingerprint-Based Graph Node Lookup
**What:** Find a ticket's graph node using compute_fingerprint("Ticket", identifier)
**When to use:** When resolving a ticket identifier to its graph node
**Example:**
```python
# From linking.py:_find_graph_results() -- proven pattern
fingerprint = compute_fingerprint("Ticket", ticket_identifier)
node_stmt = select(GraphNode).where(
    GraphNode.workspace_id == workspace_id,
    GraphNode.fingerprint == fingerprint,
    GraphNode.deleted_at.is_(None),
)
node_result = await session.execute(node_stmt)
graph_node = node_result.scalar_one_or_none()
```

### Pattern 3: traverse_graph() SQL Call
**What:** Call the SECURITY DEFINER function for recursive CTE traversal
**When to use:** Getting the neighborhood node set
**Example:**
```python
# From linking.py -- proven pattern
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
""")
result = await session.execute(traverse_stmt, {
    "start_node_id": str(graph_node.id),
    "workspace_id": str(workspace_id),
    "max_depth": depth,
})
```

### Pattern 4: Two-Step Node+Edge Retrieval
**What:** After getting nodes from traverse_graph(), query graph_edges for all edges between those nodes
**When to use:** When the API needs complete edge data (IDs, properties, source/target)
**Why needed:** traverse_graph() returns per-node rows with relationship_type but no edge IDs, no edge properties, and no cross-edges between sibling nodes. The API response shape requires full edge records.
**Example:**
```python
# After collecting node_ids from traverse_graph():
from src.models.graph_edge import GraphEdge

edge_stmt = select(GraphEdge).where(
    GraphEdge.workspace_id == workspace_id,
    GraphEdge.source_node_id.in_(node_ids),
    GraphEdge.target_node_id.in_(node_ids),
    GraphEdge.deleted_at.is_(None),
)
edge_result = await session.execute(edge_stmt)
edges = edge_result.scalars().all()
```

### Pattern 5: Node Deduplication
**What:** Same node can appear multiple times in traverse_graph() results when reachable via different paths
**When to use:** Always -- deduplicate by node_id, keeping the minimum depth
**Example:**
```python
node_map: dict[UUID, dict] = {}
for row in rows:
    nid = row.node_id
    if nid not in node_map or row.depth < node_map[nid]["depth"]:
        node_map[nid] = {
            "id": str(nid),
            "entity_type": row.entity_type,
            "name": row.name,
            "depth": row.depth,
            "properties": row.properties or {},
        }
```

### Pattern 6: Auth + Workspace Scoping
**What:** JWT auth dependency extracts workspace_id, all queries filter by it
**When to use:** Every endpoint
**Example:**
```python
@router.get("/{ticket_identifier}")
async def get_graph_neighborhood(
    ticket_identifier: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    depth: int = Query(default=2, ge=1, le=5),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    # All queries use user.workspace_id for scoping
```

### Anti-Patterns to Avoid
- **Calling traverse_graph() without workspace_id:** The SECURITY DEFINER function validates workspace membership via auth.uid(). In the backend context with service role, always pass workspace_id explicitly.
- **Building edge list from path arrays only:** This misses cross-edges between sibling nodes and lacks edge properties. Always query graph_edges for the full edge set.
- **Not deduplicating traverse_graph() results:** The recursive CTE can return the same node via multiple paths. Must deduplicate by node_id, keeping minimum depth.
- **Returning properties as-is without ensuring dict:** Properties column can be None. Always default to `{}`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph traversal | Custom recursive Python code | `traverse_graph()` SQL function | Already handles cycle detection, depth limiting, workspace validation, direction control |
| Fingerprint computation | Ad-hoc hash | `graph_ops.compute_fingerprint()` | Deterministic SHA-256, consistent with all graph extractors |
| Auth + workspace scoping | Custom JWT decode | `Depends(get_current_user)` | Standard across all endpoints, returns UserContext with workspace_id |
| Session management | Manual engine.connect() | `Depends(get_session)` | Async session with proper lifecycle management |

**Key insight:** This phase is almost entirely assembly of existing components. The traverse_graph() function, fingerprint system, auth pattern, and router pattern are all built and battle-tested.

## Common Pitfalls

### Pitfall 1: traverse_graph() Returns Rows, Not Edges
**What goes wrong:** Attempting to build the edge list directly from traverse_graph() output
**Why it happens:** traverse_graph() returns one row per node with the relationship_type of the edge that reached it, plus a path array. It does NOT return edge records.
**How to avoid:** Use traverse_graph() for node discovery only. Query graph_edges separately for all edges where both source_node_id and target_node_id are in the discovered node set.
**Warning signs:** Missing edges in the response, no edge properties, no cross-edges between siblings

### Pitfall 2: Node Deduplication
**What goes wrong:** Same node appears multiple times in the response with different depths
**Why it happens:** In a densely connected graph, the same node is reachable via multiple paths. The recursive CTE returns each path separately.
**How to avoid:** Build a node_map keyed by UUID, keep the row with minimum depth for each node_id
**Warning signs:** node_count in metadata doesn't match actual unique nodes

### Pitfall 3: traverse_graph() Auth Context
**What goes wrong:** traverse_graph() returns empty results even when data exists
**Why it happens:** The function uses `auth.uid()` to validate workspace membership. In a backend service context with service role JWT, auth.uid() may not match the user's membership.
**How to avoid:** The existing linking.py pattern works because the session uses the service role. Verify this works the same way for the new endpoint. The function already checks workspace_members table -- as long as the user's workspace membership is valid, it works.
**Warning signs:** Empty results for users who should have data

### Pitfall 4: Confusing "Ticket Not Found" vs "No Graph Data"
**What goes wrong:** Returning 404 when a ticket exists but has no graph node
**Why it happens:** Not checking linear_tickets table first, going straight to graph_nodes
**How to avoid:** Two-step validation: (1) Check linear_tickets for the identifier -- 404 if not found. (2) Check graph_nodes for fingerprint -- empty 200 if no graph node. This matches the CONTEXT.md decision.
**Warning signs:** Valid tickets returning 404 instead of empty 200

### Pitfall 5: Node Cap Applied Before Edge Query
**What goes wrong:** Edges reference nodes that were truncated away
**Why it happens:** Applying the limit to nodes, then querying edges with the full (pre-truncation) node set, or vice versa
**How to avoid:** Apply node cap first (depth ascending, edge count descending), then query edges only between the capped node set
**Warning signs:** Edge source/target IDs not present in the nodes array

### Pitfall 6: Edge Count Sort Requires Subquery
**What goes wrong:** Can't sort nodes by edge count without knowing edge counts
**Why it happens:** traverse_graph() doesn't return edge count per node
**How to avoid:** After node deduplication, count edges per node from the graph_edges query, then sort by (depth ASC, edge_count DESC) for truncation
**Warning signs:** Incorrect sort order, missing important high-connectivity nodes

## Code Examples

Verified patterns from the existing codebase:

### Ticket Existence Check (404 pattern)
```python
# From context.py -- proven pattern for ticket lookup
ticket_stmt = select(LinearTicket).where(
    LinearTicket.workspace_id == user.workspace_id,
    LinearTicket.identifier == ticket_identifier,
    LinearTicket.deleted_at.is_(None),
)
result = await session.execute(ticket_stmt)
ticket = result.scalar_one_or_none()

if ticket is None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Ticket {ticket_identifier} not found",
    )
```

### Complete Response Shape
```python
# Final response matching CONTEXT.md decisions
{
    "ticket_identifier": "ENG-123",
    "depth": 2,
    "node_count": 12,
    "edge_count": 15,
    "truncated": False,
    "nodes": [
        {
            "id": "uuid-string",
            "entity_type": "Ticket",
            "name": "ENG-123",
            "depth": 0,
            "properties": {}
        },
        # ...
    ],
    "edges": [
        {
            "source": "source-uuid-string",
            "target": "target-uuid-string",
            "relationship_type": "mentions",
            "properties": {"confidence": 0.95}
        },
        # ...
    ]
}
```

### Router Registration in main.py
```python
# Pattern from existing main.py
from src.routers.graph import router as graph_router
app.include_router(graph_router)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Apache AGE graph extension | Plain PG tables + recursive CTE | Phase 22 (v1.2 planning) | No external dependencies, works on Supabase Cloud |
| Per-row RLS on graph tables | SECURITY DEFINER function | Phase 22 | Single workspace validation, no per-row overhead |

**Deprecated/outdated:**
- None relevant -- all infrastructure is current (Phase 22-26)

## Recommendations for Discretionary Items

### URL Path: `/api/graph/{ticket_identifier}`
**Recommendation:** Use `/api/graph/{ticket_identifier}` (not `/api/graph/neighborhood/...`). Simpler, consistent with `/api/context/{ticket_identifier}`. If future sub-resources needed (e.g., specific node details), they nest naturally under `/api/graph/{ticket_identifier}/nodes/{node_id}`.

### Query Parameters
**Recommendation:** `?depth=2&limit=50`
- `depth`: integer, default 2, min 1, max 5
- `limit`: integer, default 50, min 1, max 200
- Keep parameter names short and conventional

### Entity/Relationship Type Filtering
**Recommendation:** Support optional `?entity_types=Person,Ticket&relationship_types=mentions,authored_by` query params. traverse_graph() already supports `filter_entity_types` and `filter_relationship_types` arrays -- pass them through. Low implementation cost, high utility for frontend consumers.

### Pydantic Response Models
**Recommendation:** Use Pydantic response models. The response shape is well-defined with specific fields. Pydantic gives: (1) automatic OpenAPI schema for frontend developers consuming the API, (2) type validation, (3) consistent serialization of UUIDs to strings. The project already uses Pydantic for request bodies. Example:

```python
class GraphNodeResponse(PydanticBaseModel):
    id: str
    entity_type: str
    name: str
    depth: int
    properties: dict

class GraphEdgeResponse(PydanticBaseModel):
    source: str
    target: str
    relationship_type: str
    properties: dict

class GraphNeighborhoodResponse(PydanticBaseModel):
    ticket_identifier: str
    depth: int
    node_count: int
    edge_count: int
    truncated: bool
    total_available: int | None = None
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
```

### Node Deduplication
**Recommendation:** Deduplicate by node_id, keeping the minimum depth. This is the correct behavior since depth represents "how close to the root ticket" and the shortest path is most relevant.

## Open Questions

1. **traverse_graph() with service role auth**
   - What we know: linking.py calls traverse_graph() successfully via service role sessions. The function checks `auth.uid()` against workspace_members.
   - What's unclear: Whether auth.uid() returns the service role user or the JWT user in the backend's async session context. linking.py works, so the pattern is proven, but worth confirming in tests.
   - Recommendation: Follow the exact same session/parameter pattern as linking.py. If tests pass with the same mock pattern as test_context_api.py, auth is working correctly.

2. **Edge count for sort priority**
   - What we know: CONTEXT.md specifies sort by "depth ascending, then by edge count"
   - What's unclear: Whether "edge count" means edges in the full graph or edges within the returned subgraph
   - Recommendation: Use edge count within the returned subgraph (count of edges incident to each node in the query result). This is what the consumer cares about for visual layout.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_graph_api.py -x` |
| Full suite command | `cd backend && python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GAPI-01a | GET returns nodes + edges for ticket with graph data | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_success -x` | No -- Wave 0 |
| GAPI-01b | Returns 404 for unknown ticket identifier | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_ticket_not_found -x` | No -- Wave 0 |
| GAPI-01c | Returns empty 200 for ticket with no graph node | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_no_graph_data -x` | No -- Wave 0 |
| GAPI-01d | Respects workspace scoping (auth required) | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_requires_auth -x` | No -- Wave 0 |
| GAPI-01e | Node cap truncation with metadata | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_truncation -x` | No -- Wave 0 |
| GAPI-01f | Depth and limit query params respected | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_query_params -x` | No -- Wave 0 |
| GAPI-01g | Nodes are deduplicated by ID | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_deduplication -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_graph_api.py -x`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_graph_api.py` -- covers GAPI-01 (all sub-behaviors)
- No new test fixtures needed in conftest.py -- existing `client`, `valid_auth_header`, `mock_session` fixtures are sufficient
- No framework install needed -- pytest + pytest-asyncio already in dev dependencies

## Sources

### Primary (HIGH confidence)
- `backend/src/routers/context.py` -- Router pattern, auth pattern, 404 pattern, response format
- `backend/src/services/linking.py:_find_graph_results()` -- Fingerprint lookup + traverse_graph() call pattern
- `supabase/migrations/00018_traverse_graph_function.sql` -- traverse_graph() function signature, return columns, workspace validation
- `backend/src/services/graph_ops.py` -- compute_fingerprint() API
- `backend/src/models/graph_node.py` -- GraphNode schema (entity_type, name, fingerprint, properties, source_type, source_id)
- `backend/src/models/graph_edge.py` -- GraphEdge schema (source_node_id, target_node_id, relationship_type, properties)
- `backend/src/dependencies.py` -- UserContext with workspace_id, get_current_user dependency
- `backend/src/main.py` -- Router registration pattern (include_router)
- `backend/tests/conftest.py` -- Test fixtures pattern (mock_session, valid_auth_header, app override)
- `backend/tests/test_context_api.py` -- Test patterns for router endpoints with mocked session

### Secondary (MEDIUM confidence)
- `.planning/phases/27-graph-explorer-api/27-CONTEXT.md` -- User decisions on response shape, error states, node cap

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and used across the project
- Architecture: HIGH -- all patterns directly observed in existing codebase (context.py, linking.py)
- Pitfalls: HIGH -- identified from actual traverse_graph() function analysis and known graph data patterns
- Two-step query approach: HIGH -- necessary because traverse_graph() output lacks edge records; verified by reading SQL function return columns

**Research date:** 2026-03-08
**Valid until:** Stable -- all infrastructure is settled (Phase 22-26 complete), no external dependencies changing
