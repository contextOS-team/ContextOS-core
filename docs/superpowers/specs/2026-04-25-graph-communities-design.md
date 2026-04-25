# Design: Knowledge Graph Communities + LLM Summaries

**Status:** Draft
**Author:** brainstormed with Claude
**Date:** 2026-04-25
**Scope:** v1 — minimum viable, synthesis-prompt only (no new API/UI surfaces)

## Motivation

ContextOS builds a per-workspace knowledge graph (Person, Ticket, PR, SlackThread, Decision, etc.) and walks it during context-page generation to surface implicit connections. The current graph traversal (`linking._find_graph_results`) discovers individual neighbor nodes but has no notion of **clusters** — implicit "teams" or "feature areas" that emerge from collaboration patterns.

dana-ai's GraphRAG runs Louvain community detection over its entity graph and pre-generates LLM summaries per community, then injects those summaries into the SQL coder prompt. The same pattern adapted for ContextOS gives the synthesis LLM cluster-level context like:

> The Auth/Backend cluster owns session and JWT logic. Members: @alice, @bob, @carol. Recent decisions in this cluster: PostgreSQL adoption, JWT rotation policy. Recent tickets: ENG-401, ENG-456, ENG-489.

This is a single, qualitative jump in synthesis quality without changing the existing 3-signal retrieval engine.

## Non-Goals (v1)

- No new API endpoints (`GET /api/communities` is deferred).
- No Graph Explorer (`GET /api/graph/{id}`) response changes.
- No frontend / UI surface changes.
- No on-demand rebuild trigger (cron-only; manual endpoint deferred).
- No community-ID stability across rebuilds — fresh integer IDs assigned each night, summaries regenerated. `graph_nodes.community_id` is a within-snapshot label, not a stable identity.
- No Decision/Blocker/Meeting/SlackThread nodes as community members. Edges through them get **projected** onto Person-Ticket weighted edges (see "Graph Construction") but those node types stay out of the community partition itself.

## High-Level Design

A nightly per-workspace background job:

1. Reads the workspace's graph (`graph_nodes` + `graph_edges`).
2. Builds an undirected weighted graph of Person + Ticket nodes (relationship-type-weighted edges, two-hop edges projected through Decision/SlackThread/Meeting/PR).
3. Runs `networkx.community.louvain_communities(weight="weight")`.
4. Filters out singletons and pairs (min size = 3).
5. For each surviving community, calls Gemini Flash to generate a one-paragraph summary.
6. Writes membership (`community_id` on `graph_nodes`) and metadata (`graph_communities` table) atomically per workspace.

Synthesis (`linking.find_related_content` → `synthesis.generate_context_page`) reads `community_id` for retrieved items and the assignee, picks up to 3 relevant communities, and injects a new **"Team & Feature Context"** section into the prompt.

Failure modes (Louvain crash, Gemini timeout, no communities ≥3) silently degrade to current behavior.

## Schema Changes

### New migration: `supabase/migrations/00036_graph_communities.sql`

```sql
-- Add community_id label to graph_nodes for fast membership lookup.
-- Nullable: nodes outside Person/Ticket types, or in workspaces never rebuilt, are NULL.
ALTER TABLE public.graph_nodes
  ADD COLUMN community_id integer;

CREATE INDEX idx_graph_nodes_workspace_community
  ON public.graph_nodes (workspace_id, community_id)
  WHERE community_id IS NOT NULL;

-- One row per (workspace, community) per rebuild snapshot.
CREATE TABLE public.graph_communities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  community_id integer NOT NULL,
  label text,                        -- LLM-generated short label (e.g., "Auth & Sessions")
  summary text,                      -- LLM-generated one-paragraph summary
  member_count integer NOT NULL,
  person_count integer NOT NULL,
  ticket_count integer NOT NULL,
  top_member_names text[],           -- Top 5 by sum of edge weights inside the community
  computed_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT graph_communities_workspace_id_key UNIQUE (workspace_id, community_id)
);

CREATE INDEX idx_graph_communities_workspace
  ON public.graph_communities (workspace_id);

ALTER TABLE public.graph_communities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_data" ON public.graph_communities
  FOR ALL USING (
    workspace_id IN (
      SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
    )
  );
```

### Model: `backend/src/models/graph_community.py`

New `GraphCommunity` SQLModel mirroring the table.

### Model: `backend/src/models/graph_node.py`

Add: `community_id: int | None = Field(default=None)`.

## Graph Construction

The Louvain input graph is **not** the raw `graph_edges` table. It is a derived weighted multigraph over Person + Ticket nodes only.

### Node set

```python
nodes = SELECT id, entity_type FROM graph_nodes
        WHERE workspace_id = :ws
          AND deleted_at IS NULL
          AND entity_type IN ('Person', 'Ticket')
```

### Edge set — direct edges

For every active edge in `graph_edges` where both endpoints are Person or Ticket:

| relationship_type | weight |
|---|---|
| `assigned_to` | 3.0 |
| `authored_by` | 2.5 |
| `reviews` | 2.0 |
| `decided_in` | 1.5 |
| `discussed_in` | 1.5 |
| `mentions` | 0.5 |
| `references` | 0.5 |
| `same_as` | (skip — identity edges should not influence partition) |
| `parent_of`, `implements`, `blocks` | 1.0 (default) |

When the same Person-Ticket pair has multiple edges (e.g., `mentions` + `assigned_to`), sum the weights.

### Edge set — projected edges through bridge nodes

Decisions, SlackThreads, Meetings, and PRs act as bridges. For each bridge node `B`, take every active edge incident to `B` whose other endpoint is a Person (call these `r1` edges), paired with every active edge incident to `B` whose other endpoint is a Ticket (call these `r2` edges). Edge direction is ignored — both endpoints from `graph_edges.source_node_id` and `graph_edges.target_node_id` are considered. For each (Person, Ticket) pair so produced, emit a derived weighted edge `(Person, Ticket, weight)` where:

```
weight = 0.5 * min(WEIGHTS[r1.relationship_type], WEIGHTS[r2.relationship_type])
```

The 0.5 dampener ensures derived edges are weaker than direct edges of equivalent relationship types. Use the SAME weight table above for `r1` and `r2` lookups; if a relationship_type isn't in the table, fall back to 1.0.

Bridge node types: `Decision`, `SlackThread`, `Meeting`, `PR`. `same_as` edges remain skipped at this step too.

### Pseudocode

```python
def build_louvain_graph(workspace_id):
    g = nx.Graph()
    nodes = fetch_person_ticket_nodes(workspace_id)
    g.add_nodes_from(n.id for n in nodes)

    # Direct edges
    for edge in fetch_edges_between(nodes):
        w = WEIGHTS.get(edge.relationship_type, 1.0)
        if g.has_edge(edge.source_node_id, edge.target_node_id):
            g[edge.source_node_id][edge.target_node_id]["weight"] += w
        else:
            g.add_edge(edge.source_node_id, edge.target_node_id, weight=w)

    # Projected edges via bridges
    bridges = fetch_bridge_nodes(workspace_id)  # Decision, SlackThread, Meeting, PR
    for bridge in bridges:
        person_neighbors = edges_to_persons(bridge)
        ticket_neighbors = edges_to_tickets(bridge)
        for p_edge in person_neighbors:
            for t_edge in ticket_neighbors:
                w = 0.5 * min(WEIGHTS[p_edge.rel], WEIGHTS[t_edge.rel])
                if g.has_edge(p_edge.person_id, t_edge.ticket_id):
                    g[p_edge.person_id][t_edge.ticket_id]["weight"] += w
                else:
                    g.add_edge(p_edge.person_id, t_edge.ticket_id, weight=w)

    return g
```

## Louvain & Filtering

```python
import networkx as nx
from networkx.algorithms import community as nx_community

partition = nx_community.louvain_communities(g, weight="weight", seed=42)
# partition: list[set[node_id]]

# Filter: drop communities with < MIN_COMMUNITY_SIZE members
MIN_COMMUNITY_SIZE = 3
communities = [c for c in partition if len(c) >= MIN_COMMUNITY_SIZE]

# Assign integer IDs (1-indexed, 0 reserved for "no community")
community_assignments = {}  # node_id -> community_id
for cid, members in enumerate(communities, start=1):
    for node_id in members:
        community_assignments[node_id] = cid
```

`seed=42` makes the partition deterministic for a given input graph (Louvain is non-deterministic by default).

## LLM Summary Generation

For each community ≥3 members, call Gemini Flash once with this prompt:

```
You are summarizing a cluster of people and tickets that work together
on the same area of an engineering team. Produce:

1. A short label (2-5 words) that names the cluster's likely focus area.
   Examples: "Auth & Sessions", "Billing Integrations", "Onboarding UX".
2. A one-paragraph (50-80 words) summary of what this cluster works on,
   based on the ticket titles and people involved.

Cluster members:

People:
- @alice (assignee on 12 tickets, author of 3 decisions)
- @bob (reviewer on 8 PRs, assignee on 5 tickets)
...

Tickets:
- ENG-456: "Add JWT refresh flow"
- ENG-401: "Fix session timeout bug"
- ENG-489: "Implement OAuth callback"
...

Return JSON: {"label": "...", "summary": "..."}
```

Use `temperature=0.3` for the Gemini call — low enough to keep summaries stable across reruns of the same cluster, high enough to avoid the rigid phrasing temperature=0 sometimes produces. (Note: Louvain's `seed=42` controls partition determinism; this temperature controls summary determinism. They're independent knobs.) Response is parsed and stored on `graph_communities.label` / `summary`.

If summary generation fails for any community, store `label=NULL, summary=NULL` and continue. The synthesis prompt's Team Context section gracefully omits communities with NULL summary.

## Persistence (Atomic Per-Workspace Swap)

```python
async def persist_communities(workspace_id, assignments, community_meta):
    async with session.begin():
        # 1. Clear previous snapshot for this workspace
        await session.execute(
            delete(GraphCommunity).where(GraphCommunity.workspace_id == workspace_id)
        )
        await session.execute(
            update(GraphNode)
              .where(GraphNode.workspace_id == workspace_id)
              .values(community_id=None)
        )

        # 2. Write new snapshot
        for cid, meta in community_meta.items():
            session.add(GraphCommunity(
                workspace_id=workspace_id,
                community_id=cid,
                label=meta["label"],
                summary=meta["summary"],
                member_count=meta["member_count"],
                person_count=meta["person_count"],
                ticket_count=meta["ticket_count"],
                top_member_names=meta["top_member_names"],
            ))

        # 3. Bulk-update community_id on graph_nodes
        for node_id, cid in assignments.items():
            await session.execute(
                update(GraphNode)
                  .where(GraphNode.id == node_id)
                  .values(community_id=cid)
            )
```

The transaction wraps the wipe + reinsert so a partial failure leaves either the previous snapshot or the new snapshot intact, never a mix.

## Scheduler

A new module `backend/src/services/graph_scheduler.py` follows the existing `sync_scheduler.py` pattern:

```python
async def run_community_rebuild_loop():
    """Nightly loop: rebuild communities for every workspace that has graph_nodes."""
    while True:
        try:
            await asyncio.sleep(seconds_until_next_03_utc())
            # "Active" = workspace has at least one non-deleted graph_node.
            # Cheap query (uses workspace+entity_type composite index).
            workspaces = await fetch_workspaces_with_graph_nodes()
            for ws in workspaces:
                try:
                    await rebuild_communities(ws.id)
                except Exception:
                    logger.exception("Community rebuild failed for %s", ws.id)
                    # Continue to next workspace
        except Exception:
            logger.exception("Community scheduler tick error")
            await asyncio.sleep(300)  # 5min cooldown on outer loop error
```

Wired into `backend/src/main.py` startup alongside the existing `run_polling_fallback`.

**One-time backfill on deploy:** the same `rebuild_communities(workspace_id)` function runs once per workspace at app startup if the workspace has no rows in `graph_communities` yet. Uses an `asyncio.create_task(...)` so it doesn't block startup.

## Synthesis Integration

### Linking layer (`backend/src/services/linking.py`)

Extend `LinkingResult` and `LinkedItem` to surface community membership:

```python
@dataclass
class CommunityContext:
    community_id: int
    label: str | None
    summary: str | None
    person_count: int
    ticket_count: int
    member_count: int
    top_member_names: list[str]
    relevance_reason: str  # "assignee_primary" | "retrieved_member"
```

`find_related_content` returns `LinkingResult.communities: list[CommunityContext]` selected by:

1. The ticket assignee's `community_id` (if non-null) → tagged `assignee_primary`.
2. Any community with ≥2 retrieved-item members → tagged `retrieved_member`.
3. Cap at 3 communities total. Priority: assignee_primary > more retrieved members > larger community.

### Synthesis layer (`backend/src/services/synthesis.py`)

New template constant:

```python
TEAM_CONTEXT_TEMPLATE = """\
### Team & Feature Context

The retrieved items below cluster into the following team/feature areas:

{community_blocks}"""
```

Each community block:

```
**{label}** ({member_count} members; {person_count} people, {ticket_count} tickets)
{summary}
Top members: {top_member_names}
Why included: {relevance_reason}
```

The new section is inserted into `SYNTHESIS_TEMPLATE` between `### Related Content` and `{graph_section}`. Uses an empty string when `LinkingResult.communities` is empty — preserves graceful degradation pattern already used for `graph_section`.

### Updated synthesis instructions

In sections 2 (Background & Decisions), 4 (Related Work), and 7 (Key People) of the synthesis instructions, add conditional instruction:

> If the **Team & Feature Context** section above lists communities, weave the cluster context into the narrative — name the team/area when relevant, identify which decisions and tickets belong to which cluster.

## Failure Modes

| Failure | Behavior |
|---|---|
| `networkx` import fails | Log error, skip rebuild for the workspace, retry tomorrow. |
| Louvain raises (e.g., empty graph) | Log warning, skip workspace; nodes keep their previous `community_id` (or NULL if first run). |
| All communities below `MIN_COMMUNITY_SIZE` | Wipe `community_id` for workspace, write zero rows to `graph_communities`. Synthesis sees empty `communities` list and omits the Team Context section. |
| Gemini summary call fails for a community | Persist the community with `label=NULL, summary=NULL`. Synthesis filter drops NULL-summary communities from the prompt. |
| `community_id` column missing (pre-migration) | Linking layer catches `OperationalError` on read and returns empty `communities` — synthesis silently degrades. |

All failure paths preserve current synthesis behavior; the feature is purely additive.

## Cost & Performance

Per workspace per night:

- **Louvain:** O(E log V) on a sparse graph. For a workspace with 5k Person+Ticket nodes and 30k edges, NetworkX Louvain runs in <2 seconds on a single CPU.
- **Summary generation:** ~30-100 communities × 1 Gemini Flash call ≈ $0.02-$0.05 per workspace per night.
- **DB writes:** one transaction with O(nodes_in_communities) updates. Negligible.

Total: <30 seconds and <$0.10 per workspace per night.

## Dependencies

Add to `backend/pyproject.toml`:

```
"networkx>=3.2",
```

NetworkX 3.2+ ships `louvain_communities` in `networkx.algorithms.community`. No other deps needed (we already have google-genai for summary generation).

## Testing

New test files:

### `backend/tests/test_graph_communities.py`

- `test_build_louvain_graph_direct_edges` — verifies weight summation and skip of `same_as`.
- `test_build_louvain_graph_projected_edges` — verifies bridge projection and 0.5 dampener.
- `test_louvain_filters_min_size` — partitions with members <3 get dropped.
- `test_louvain_deterministic_with_seed` — same input → same output.
- `test_persist_atomic_swap` — failed mid-swap leaves old snapshot intact.
- `test_summary_generation_handles_llm_failure` — community persisted with NULL summary.
- `test_rebuild_for_empty_graph` — no crash, no rows written.

### `backend/tests/test_synthesis_communities.py`

- `test_team_context_section_renders_when_communities_present`.
- `test_team_context_section_omitted_when_no_communities`.
- `test_synthesis_picks_assignee_primary_first`.
- `test_synthesis_caps_at_3_communities`.
- `test_synthesis_drops_null_summary_communities`.

### Modify `backend/tests/test_linking_graph.py`

Add cases for `LinkingResult.communities` selection logic.

## File Manifest

| Path | Action | Purpose |
|---|---|---|
| `supabase/migrations/00036_graph_communities.sql` | new | Schema (table + column + indexes + RLS) |
| `backend/src/models/graph_community.py` | new | SQLModel |
| `backend/src/models/graph_node.py` | modify | Add `community_id` field |
| `backend/src/services/graph_communities.py` | new | Louvain build, summary gen, persistence |
| `backend/src/services/graph_scheduler.py` | new | Nightly loop + on-startup backfill |
| `backend/src/services/linking.py` | modify | Populate `LinkingResult.communities` |
| `backend/src/services/synthesis.py` | modify | New `TEAM_CONTEXT_TEMPLATE`, update prompt |
| `backend/src/main.py` | modify | Wire `run_community_rebuild_loop` on startup |
| `backend/pyproject.toml` | modify | Add `networkx>=3.2` |
| `backend/tests/test_graph_communities.py` | new | Build + filter + persist tests |
| `backend/tests/test_synthesis_communities.py` | new | Prompt section tests |
| `backend/tests/test_linking_graph.py` | modify | LinkingResult.communities selection tests |

## Open Questions for Future Phases

These are explicitly **not** decided in v1 and are left for follow-up phases:

1. **Community ID stability across rebuilds.** v1 reassigns IDs every night. If we surface communities in a UI or API, we'll need Jaccard-overlap mapping to preserve labels across rebuilds.
2. **Community-level Graph Explorer endpoint.** `GET /api/communities` and `GET /api/communities/{id}` for frontend consumption.
3. **On-demand rebuild trigger.** `POST /api/admin/rebuild-communities` for after big imports.
4. **Cross-community edge highlighting in synthesis.** When two retrieved items belong to different communities, surface the bridge edges that connect their clusters.
5. **Refining the bridge dampener.** 0.5 is a guess; tune empirically once communities are visible.
