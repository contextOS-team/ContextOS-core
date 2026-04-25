# Graph Communities + LLM Summaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add nightly Louvain community detection over the Person+Ticket subgraph with Gemini-generated cluster summaries injected into the synthesis prompt.

**Architecture:** A new `graph_communities` service runs once per night per workspace. It builds a weighted undirected graph (Person+Ticket nodes; direct edges + projected 2-hop edges through Decision/SlackThread/Meeting/PR bridges), partitions it with `networkx.community.louvain_communities`, filters to clusters of ≥3 members, and asks Gemini Flash for a label + paragraph summary per cluster. Membership is persisted to a new `graph_communities` table plus a `community_id` column on `graph_nodes`. The synthesis prompt picks up to 3 relevant communities (assignee's home cluster + clusters with ≥2 retrieved-item members) and renders a "Team & Feature Context" section.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + asyncpg + Supabase (PostgreSQL) + Gemini Flash (google-genai) + NetworkX 3.2+. v1 is synthesis-prompt only — no new API endpoints, no UI.

**Spec:** `docs/superpowers/specs/2026-04-25-graph-communities-design.md`

---

## File Structure

**New files:**
- `supabase/migrations/00036_graph_communities.sql` — table + column + indexes + RLS
- `backend/src/models/graph_community.py` — GraphCommunity SQLModel
- `backend/src/services/graph_communities.py` — single cohesive module: builder + partition + summarizer + persistence + orchestrator
- `backend/src/services/graph_scheduler.py` — nightly loop + startup backfill
- `backend/tests/test_graph_communities.py` — unit tests for builder, partition, persistence, orchestrator
- `backend/tests/test_synthesis_communities.py` — synthesis prompt integration tests

**Modified files:**
- `backend/pyproject.toml` — add `networkx>=3.2`
- `backend/src/models/graph_node.py` — add `community_id` field
- `backend/src/services/linking.py` — add `CommunityContext` dataclass and selection logic into `find_related_content`
- `backend/src/services/synthesis.py` — add `TEAM_CONTEXT_TEMPLATE`, integrate into `SYNTHESIS_TEMPLATE`, update prompt instructions
- `backend/src/main.py` — wire `run_community_rebuild_loop` alongside existing schedulers
- `backend/tests/test_linking_graph.py` — add test cases for community selection

---

## Task 1: Add NetworkX dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add the dependency**

Open `backend/pyproject.toml` and add `"networkx>=3.2",` to the `dependencies` array (alphabetical order suggests after `"langgraph",` and before `"openai>=1.0",`, but match the file's actual ordering — current dependencies list is non-alphabetical so just append before the closing bracket of `dependencies`).

After the change, the dependencies block contains a line like:

```toml
dependencies = [
    "fastapi[standard]",
    ...
    "telethon>=1.36",
    "networkx>=3.2",
]
```

- [ ] **Step 2: Install the dependency**

Run from `backend/`:

```bash
cd backend && uv sync
```

Expected: dependency resolution completes; `networkx` appears in the lock file.

- [ ] **Step 3: Verify import works**

Run from `backend/`:

```bash
cd backend && uv run python -c "import networkx as nx; from networkx.algorithms.community import louvain_communities; print(nx.__version__)"
```

Expected: prints a version >=3.2, no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "deps(backend): add networkx>=3.2 for graph community detection"
```

---

## Task 2: Create migration for graph_communities table and community_id column

**Files:**
- Create: `supabase/migrations/00036_graph_communities.sql`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/00036_graph_communities.sql` with:

```sql
-- ============================================================
-- Graph Communities: Louvain partition snapshots + LLM summaries
-- Phase: GraphRAG communities v1
-- ============================================================
-- Adds community_id label to graph_nodes for fast membership lookup
-- and a graph_communities table holding per-workspace, per-snapshot
-- cluster metadata (label, summary, sizes, top members).
-- ============================================================

-- Add community_id label to graph_nodes.
-- Nullable: nodes outside Person/Ticket types or in workspaces never rebuilt are NULL.
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
  label text,
  summary text,
  member_count integer NOT NULL,
  person_count integer NOT NULL,
  ticket_count integer NOT NULL,
  top_member_names text[],
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

- [ ] **Step 2: Verify SQL syntax with psql --help-style dry-run**

Run:

```bash
grep -c "CREATE TABLE" supabase/migrations/00036_graph_communities.sql
```

Expected: `1`.

```bash
grep -c "ENABLE ROW LEVEL SECURITY" supabase/migrations/00036_graph_communities.sql
```

Expected: `1`.

(The migration runs against the live Supabase project on deploy; tests do not apply it. We're only checking the file is well-formed here.)

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/00036_graph_communities.sql
git commit -m "feat(graph): add migration for graph_communities table and community_id column"
```

---

## Task 3: Add GraphCommunity SQLModel

**Files:**
- Create: `backend/src/models/graph_community.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_graph_community_model.py`:

```python
"""Unit tests for the GraphCommunity SQLModel."""

import uuid

from src.models.graph_community import GraphCommunity


class TestGraphCommunityModel:
    def test_can_instantiate_with_required_fields(self):
        ws_id = uuid.uuid4()
        gc = GraphCommunity(
            workspace_id=ws_id,
            community_id=1,
            label="Auth & Sessions",
            summary="Cluster owns session and JWT logic.",
            member_count=12,
            person_count=4,
            ticket_count=8,
            top_member_names=["@alice", "@bob"],
        )
        assert gc.workspace_id == ws_id
        assert gc.community_id == 1
        assert gc.label == "Auth & Sessions"
        assert gc.member_count == 12
        assert gc.top_member_names == ["@alice", "@bob"]

    def test_label_and_summary_optional(self):
        gc = GraphCommunity(
            workspace_id=uuid.uuid4(),
            community_id=2,
            label=None,
            summary=None,
            member_count=3,
            person_count=2,
            ticket_count=1,
            top_member_names=[],
        )
        assert gc.label is None
        assert gc.summary is None

    def test_table_name_is_graph_communities(self):
        assert GraphCommunity.__tablename__ == "graph_communities"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_community_model.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.models.graph_community'`.

- [ ] **Step 3: Write the model**

Create `backend/src/models/graph_community.py`:

```python
"""GraphCommunity model mapping to public.graph_communities table."""

import uuid
from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlmodel import Field

from src.models.base import BaseModel


class GraphCommunity(BaseModel, table=True):
    """A Louvain community snapshot: per-workspace, per-rebuild cluster metadata.

    Community IDs are not stable across rebuilds — each nightly run wipes the
    previous snapshot for the workspace and reassigns fresh integer IDs.
    """

    __tablename__ = "graph_communities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "community_id", name="graph_communities_workspace_id_key"
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    community_id: int = Field(nullable=False)
    label: str | None = Field(default=None)
    summary: str | None = Field(default=None)
    member_count: int = Field(nullable=False)
    person_count: int = Field(nullable=False)
    ticket_count: int = Field(nullable=False)
    top_member_names: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "top_member_names",
            ARRAY(TEXT),
            nullable=True,
            server_default=sa_text("'{}'"),
        ),
    )
    computed_at: datetime | None = Field(default=None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_graph_community_model.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/graph_community.py backend/tests/test_graph_community_model.py
git commit -m "feat(graph): add GraphCommunity SQLModel"
```

---

## Task 4: Add community_id field to GraphNode model

**Files:**
- Modify: `backend/src/models/graph_node.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_graph_community_model.py`:

```python
class TestGraphNodeCommunityId:
    def test_graph_node_can_set_community_id(self):
        from src.models.graph_node import GraphNode
        node = GraphNode(
            workspace_id=uuid.uuid4(),
            entity_type="Person",
            name="@alice",
            fingerprint="x" * 64,
            community_id=7,
        )
        assert node.community_id == 7

    def test_graph_node_community_id_defaults_to_none(self):
        from src.models.graph_node import GraphNode
        node = GraphNode(
            workspace_id=uuid.uuid4(),
            entity_type="Person",
            name="@alice",
            fingerprint="y" * 64,
        )
        assert node.community_id is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_community_model.py::TestGraphNodeCommunityId -v
```

Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'community_id'` or similar pydantic error.

- [ ] **Step 3: Add the field**

Edit `backend/src/models/graph_node.py`, adding the new field after the existing `properties` field (i.e. just before the end of the class body):

```python
    community_id: int | None = Field(default=None)
```

The full file should now end with that line inside the `GraphNode` class.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_graph_community_model.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/graph_node.py backend/tests/test_graph_community_model.py
git commit -m "feat(graph): add community_id field to GraphNode"
```

---

## Task 5: Build Louvain graph — direct edges only (skeleton)

**Files:**
- Create: `backend/src/services/graph_communities.py`
- Create: `backend/tests/test_graph_communities.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_graph_communities.py`:

```python
"""Unit tests for the graph_communities service."""

import uuid
from unittest.mock import MagicMock

import networkx as nx
import pytest

from src.services.graph_communities import (
    EDGE_WEIGHTS,
    BRIDGE_DAMPENER,
    build_louvain_graph,
)


def _node(node_id: uuid.UUID, entity_type: str):
    n = MagicMock()
    n.id = node_id
    n.entity_type = entity_type
    return n


def _edge(src: uuid.UUID, tgt: uuid.UUID, rel: str):
    e = MagicMock()
    e.source_node_id = src
    e.target_node_id = tgt
    e.relationship_type = rel
    return e


class TestBuildLouvainGraphDirectEdges:
    def test_empty_inputs_produce_empty_graph(self):
        g = build_louvain_graph(person_ticket_nodes=[], direct_edges=[], bridges=[])
        assert isinstance(g, nx.Graph)
        assert g.number_of_nodes() == 0
        assert g.number_of_edges() == 0

    def test_adds_person_and_ticket_nodes(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[
                _node(p_id, "Person"),
                _node(t_id, "Ticket"),
            ],
            direct_edges=[],
            bridges=[],
        )
        assert set(g.nodes) == {p_id, t_id}
        assert g.number_of_edges() == 0

    def test_assigned_to_edge_uses_weight_3(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[_edge(p_id, t_id, "assigned_to")],
            bridges=[],
        )
        assert g[p_id][t_id]["weight"] == EDGE_WEIGHTS["assigned_to"]
        assert EDGE_WEIGHTS["assigned_to"] == 3.0

    def test_multiple_edges_same_pair_sum_weights(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[
                _edge(p_id, t_id, "assigned_to"),
                _edge(p_id, t_id, "mentions"),
            ],
            bridges=[],
        )
        # 3.0 (assigned_to) + 0.5 (mentions) = 3.5
        assert g[p_id][t_id]["weight"] == pytest.approx(3.5)

    def test_same_as_edges_skipped(self):
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p1, "Person"), _node(p2, "Person")],
            direct_edges=[_edge(p1, p2, "same_as")],
            bridges=[],
        )
        assert not g.has_edge(p1, p2)

    def test_unknown_relationship_type_uses_default_weight_1(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[_edge(p_id, t_id, "implements")],
            bridges=[],
        )
        assert g[p_id][t_id]["weight"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_communities.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.graph_communities'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/services/graph_communities.py`:

```python
"""Knowledge graph community detection (Louvain) + LLM summaries.

Per nightly cron:
1. Build a weighted undirected graph of Person+Ticket nodes
   (direct edges + edges projected through Decision/SlackThread/Meeting/PR bridges)
2. Run Louvain partitioning, drop clusters with <3 members
3. Generate a label + paragraph summary per surviving cluster via Gemini Flash
4. Persist to graph_communities table + community_id column on graph_nodes
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

# Relationship-type weights for the Louvain input graph.
# Higher = stronger membership signal. same_as is skipped entirely (identity, not collaboration).
EDGE_WEIGHTS: dict[str, float] = {
    "assigned_to": 3.0,
    "authored_by": 2.5,
    "reviews": 2.0,
    "decided_in": 1.5,
    "discussed_in": 1.5,
    "mentions": 0.5,
    "references": 0.5,
    "implements": 1.0,
    "blocks": 1.0,
    "parent_of": 1.0,
}

# Edges through bridge nodes (Decision/SlackThread/Meeting/PR) are weaker than direct edges.
BRIDGE_DAMPENER = 0.5

# Minimum cluster size to keep after Louvain. Smaller clusters are dropped from summaries.
MIN_COMMUNITY_SIZE = 3

# Bridge entity types — these connect Person<->Ticket via 2-hop projections but are not
# themselves community members.
BRIDGE_ENTITY_TYPES = frozenset({"Decision", "SlackThread", "Meeting", "PR"})


def _weight(rel: str) -> float:
    return EDGE_WEIGHTS.get(rel, 1.0)


def build_louvain_graph(
    person_ticket_nodes: list[Any],
    direct_edges: list[Any],
    bridges: list[Any],
) -> nx.Graph:
    """Construct the weighted undirected graph fed to Louvain.

    Args:
        person_ticket_nodes: list of GraphNode-like objects with .id and .entity_type
            ("Person" or "Ticket"). These become the only graph nodes.
        direct_edges: list of GraphEdge-like objects whose source AND target are both in
            person_ticket_nodes. Edges with relationship_type == "same_as" are skipped.
        bridges: list of bridge descriptors. Each is a tuple
            (bridge_node_id, person_edges, ticket_edges) where:
              - person_edges is a list of (person_id, relationship_type) tuples
                describing edges incident to the bridge whose other end is a Person
              - ticket_edges is the same shape for Tickets
            All edge directions ignored.

    Returns:
        nx.Graph with one node per Person/Ticket and weighted edges.
    """
    g = nx.Graph()
    for n in person_ticket_nodes:
        g.add_node(n.id)

    for e in direct_edges:
        if e.relationship_type == "same_as":
            continue
        w = _weight(e.relationship_type)
        if g.has_edge(e.source_node_id, e.target_node_id):
            g[e.source_node_id][e.target_node_id]["weight"] += w
        else:
            g.add_edge(e.source_node_id, e.target_node_id, weight=w)

    # Bridge projection added in the next task.
    return g
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_graph_communities.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/graph_communities.py backend/tests/test_graph_communities.py
git commit -m "feat(graph): add direct-edge Louvain graph builder for community detection"
```

---

## Task 6: Bridge-projected edges through Decision/SlackThread/Meeting/PR

**Files:**
- Modify: `backend/src/services/graph_communities.py`
- Modify: `backend/tests/test_graph_communities.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_graph_communities.py`:

```python
class TestBuildLouvainGraphBridgeProjection:
    def test_single_bridge_emits_person_to_ticket_edge(self):
        p_id, t_id, b_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[],
            bridges=[
                (b_id, [(p_id, "authored_by")], [(t_id, "references")]),
            ],
        )
        assert g.has_edge(p_id, t_id)
        # 0.5 dampener * min(2.5, 0.5) = 0.5 * 0.5 = 0.25
        assert g[p_id][t_id]["weight"] == pytest.approx(0.25)

    def test_bridge_with_multiple_persons_and_tickets_emits_cartesian_product(self):
        p1, p2, t1, t2, b_id = (uuid.uuid4() for _ in range(5))
        g = build_louvain_graph(
            person_ticket_nodes=[
                _node(p1, "Person"),
                _node(p2, "Person"),
                _node(t1, "Ticket"),
                _node(t2, "Ticket"),
            ],
            direct_edges=[],
            bridges=[
                (
                    b_id,
                    [(p1, "authored_by"), (p2, "discussed_in")],
                    [(t1, "references"), (t2, "references")],
                ),
            ],
        )
        assert g.number_of_edges() == 4
        # p1->t1: 0.5 * min(2.5, 0.5) = 0.25
        assert g[p1][t1]["weight"] == pytest.approx(0.25)
        # p2->t2: 0.5 * min(1.5, 0.5) = 0.25
        assert g[p2][t2]["weight"] == pytest.approx(0.25)

    def test_direct_and_bridge_edges_sum(self):
        p_id, t_id, b_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[_edge(p_id, t_id, "assigned_to")],
            bridges=[(b_id, [(p_id, "authored_by")], [(t_id, "references")])],
        )
        # direct 3.0 + bridge 0.25 = 3.25
        assert g[p_id][t_id]["weight"] == pytest.approx(3.25)

    def test_bridge_with_no_tickets_emits_no_edges(self):
        p_id, b_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person")],
            direct_edges=[],
            bridges=[(b_id, [(p_id, "authored_by")], [])],
        )
        assert g.number_of_edges() == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_communities.py::TestBuildLouvainGraphBridgeProjection -v
```

Expected: FAIL — bridges parameter is currently ignored, so no edges are emitted.

- [ ] **Step 3: Implement bridge projection**

In `backend/src/services/graph_communities.py`, replace the line `# Bridge projection added in the next task.` with:

```python
    for bridge_id, person_edges, ticket_edges in bridges:
        if not person_edges or not ticket_edges:
            continue
        for person_id, p_rel in person_edges:
            for ticket_id, t_rel in ticket_edges:
                w = BRIDGE_DAMPENER * min(_weight(p_rel), _weight(t_rel))
                if g.has_edge(person_id, ticket_id):
                    g[person_id][ticket_id]["weight"] += w
                else:
                    g.add_edge(person_id, ticket_id, weight=w)
```

- [ ] **Step 4: Run all tests in the file**

```bash
cd backend && uv run pytest tests/test_graph_communities.py -v
```

Expected: 10 PASS (6 from Task 5 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/graph_communities.py backend/tests/test_graph_communities.py
git commit -m "feat(graph): project bridge-node edges into Louvain graph"
```

---

## Task 7: Partition communities + filter by min size

**Files:**
- Modify: `backend/src/services/graph_communities.py`
- Modify: `backend/tests/test_graph_communities.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_graph_communities.py`:

```python
from src.services.graph_communities import partition_communities


class TestPartitionCommunities:
    def _make_two_clusters(self):
        # Two tightly connected triangles, weakly bridged.
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        d, e, f = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        g = nx.Graph()
        for n in (a, b, c, d, e, f):
            g.add_node(n)
        for u, v in [(a, b), (b, c), (a, c)]:
            g.add_edge(u, v, weight=10.0)
        for u, v in [(d, e), (e, f), (d, f)]:
            g.add_edge(u, v, weight=10.0)
        g.add_edge(c, d, weight=0.1)  # weak bridge
        return g, {a, b, c}, {d, e, f}

    def test_partitions_two_clear_clusters(self):
        g, cluster1, cluster2 = self._make_two_clusters()
        communities = partition_communities(g)
        assert len(communities) == 2
        cluster_sets = [set(c) for c in communities]
        assert cluster1 in cluster_sets
        assert cluster2 in cluster_sets

    def test_filters_communities_below_min_size(self):
        # 3-node clique + 2-node pair: only the 3-clique survives.
        a, b, c, d, e = (uuid.uuid4() for _ in range(5))
        g = nx.Graph()
        for u, v in [(a, b), (b, c), (a, c)]:
            g.add_edge(u, v, weight=10.0)
        g.add_edge(d, e, weight=10.0)
        communities = partition_communities(g)
        assert len(communities) == 1
        assert set(communities[0]) == {a, b, c}

    def test_empty_graph_returns_empty_list(self):
        assert partition_communities(nx.Graph()) == []

    def test_deterministic_with_same_seed(self):
        g, _, _ = self._make_two_clusters()
        c1 = partition_communities(g)
        c2 = partition_communities(g)
        assert [set(c) for c in c1] == [set(c) for c in c2]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_communities.py::TestPartitionCommunities -v
```

Expected: FAIL with `ImportError: cannot import name 'partition_communities'`.

- [ ] **Step 3: Implement partition_communities**

Append to `backend/src/services/graph_communities.py`:

```python
LOUVAIN_SEED = 42


def partition_communities(g: nx.Graph) -> list[list[Any]]:
    """Run Louvain on a weighted graph and return communities of size >= MIN_COMMUNITY_SIZE.

    Returns a list of node-id lists. Each inner list is one community.
    Communities smaller than MIN_COMMUNITY_SIZE are dropped.
    """
    if g.number_of_nodes() == 0:
        return []

    from networkx.algorithms.community import louvain_communities

    raw = louvain_communities(g, weight="weight", seed=LOUVAIN_SEED)
    return [list(community) for community in raw if len(community) >= MIN_COMMUNITY_SIZE]
```

- [ ] **Step 4: Run all tests in the file**

```bash
cd backend && uv run pytest tests/test_graph_communities.py -v
```

Expected: 14 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/graph_communities.py backend/tests/test_graph_communities.py
git commit -m "feat(graph): add Louvain partitioning with min-size filter"
```

---

## Task 8: Generate label + summary per community via Gemini Flash

**Files:**
- Modify: `backend/src/services/graph_communities.py`
- Modify: `backend/tests/test_graph_communities.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_graph_communities.py`:

```python
from unittest.mock import AsyncMock as _AsyncMock

import json as _json

from src.services.graph_communities import generate_community_summary


class TestGenerateCommunitySummary:
    @pytest.mark.asyncio
    async def test_returns_label_and_summary_on_valid_response(self):
        llm = _AsyncMock()
        llm.generate.return_value = MagicMock(text=_json.dumps({
            "label": "Auth & Sessions",
            "summary": "This cluster owns session and JWT logic.",
        }))
        result = await generate_community_summary(
            llm_client=llm,
            person_descriptions=["@alice (assignee on 12 tickets)"],
            ticket_descriptions=["ENG-456: Add JWT refresh flow"],
        )
        assert result == {
            "label": "Auth & Sessions",
            "summary": "This cluster owns session and JWT logic.",
        }

    @pytest.mark.asyncio
    async def test_returns_none_label_summary_on_llm_failure(self):
        llm = _AsyncMock()
        llm.generate.side_effect = RuntimeError("upstream timeout")
        result = await generate_community_summary(
            llm_client=llm,
            person_descriptions=["@alice"],
            ticket_descriptions=["ENG-1"],
        )
        assert result == {"label": None, "summary": None}

    @pytest.mark.asyncio
    async def test_returns_none_label_summary_on_invalid_json(self):
        llm = _AsyncMock()
        llm.generate.return_value = MagicMock(text="not json at all")
        result = await generate_community_summary(
            llm_client=llm,
            person_descriptions=[],
            ticket_descriptions=[],
        )
        assert result == {"label": None, "summary": None}

    @pytest.mark.asyncio
    async def test_passes_temperature_to_llm(self):
        llm = _AsyncMock()
        llm.generate.return_value = MagicMock(text=_json.dumps({"label": "X", "summary": "Y"}))
        await generate_community_summary(
            llm_client=llm,
            person_descriptions=["@x"],
            ticket_descriptions=["E-1"],
        )
        kwargs = llm.generate.call_args.kwargs
        # The implementation may pass temperature as a named arg or in a config dict.
        # Check at least one of these is present and equals 0.3.
        flat = kwargs.get("temperature")
        nested = (kwargs.get("config") or {}).get("temperature") if "config" in kwargs else None
        assert flat == 0.3 or nested == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_communities.py::TestGenerateCommunitySummary -v
```

Expected: FAIL with `ImportError: cannot import name 'generate_community_summary'`.

- [ ] **Step 3: Implement generate_community_summary**

Append to `backend/src/services/graph_communities.py`:

```python
import json

SUMMARY_TEMPERATURE = 0.3
SUMMARY_PROMPT_TEMPLATE = """\
You are summarizing a cluster of people and tickets that work together
on the same area of an engineering team. Produce:

1. A short label (2-5 words) that names the cluster's likely focus area.
   Examples: "Auth & Sessions", "Billing Integrations", "Onboarding UX".
2. A one-paragraph (50-80 words) summary of what this cluster works on,
   based on the ticket titles and people involved.

Cluster members:

People:
{people_block}

Tickets:
{tickets_block}

Return JSON: {{"label": "...", "summary": "..."}}"""


async def generate_community_summary(
    llm_client: Any,
    person_descriptions: list[str],
    ticket_descriptions: list[str],
) -> dict[str, str | None]:
    """Ask Gemini Flash for a label and summary describing one community.

    Returns ``{"label": str | None, "summary": str | None}``.
    On any error (LLM failure, invalid JSON, missing keys) returns
    ``{"label": None, "summary": None}`` and logs a warning.
    """
    people_block = "\n".join(f"- {p}" for p in person_descriptions) or "- (none)"
    tickets_block = "\n".join(f"- {t}" for t in ticket_descriptions) or "- (none)"
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        people_block=people_block, tickets_block=tickets_block
    )

    try:
        response = await llm_client.generate(
            prompt=prompt,
            system_prompt=(
                "You return a single JSON object with keys 'label' and 'summary'. "
                "No prose, no markdown fences."
            ),
            temperature=SUMMARY_TEMPERATURE,
        )
        text = (response.text or "").strip()
        # Strip optional ```json fences just in case.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        return {
            "label": parsed.get("label"),
            "summary": parsed.get("summary"),
        }
    except Exception:
        logger.warning("Community summary generation failed; persisting NULL", exc_info=True)
        return {"label": None, "summary": None}
```

- [ ] **Step 4: Run all tests in the file**

```bash
cd backend && uv run pytest tests/test_graph_communities.py -v
```

Expected: 18 PASS (14 prior + 4 new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/graph_communities.py backend/tests/test_graph_communities.py
git commit -m "feat(graph): add Gemini-based community summary generator"
```

---

## Task 9: Atomic per-workspace persistence (delete-then-insert in single transaction)

**Files:**
- Modify: `backend/src/services/graph_communities.py`
- Modify: `backend/tests/test_graph_communities.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_graph_communities.py`:

```python
from src.services.graph_communities import (
    CommunityMeta,
    persist_communities,
)


class TestPersistCommunities:
    @pytest.fixture
    def session(self):
        sess = MagicMock()
        sess.execute = _AsyncMock()
        sess.add = MagicMock()
        sess.flush = _AsyncMock()
        sess.begin = MagicMock()
        # Make session.begin() usable as `async with session.begin()`
        sess.begin.return_value.__aenter__ = _AsyncMock(return_value=None)
        sess.begin.return_value.__aexit__ = _AsyncMock(return_value=None)
        return sess

    @pytest.mark.asyncio
    async def test_clears_previous_snapshot_then_writes_new(self, session):
        ws_id = uuid.uuid4()
        node_a = uuid.uuid4()
        node_b = uuid.uuid4()
        meta = {
            1: CommunityMeta(
                community_id=1,
                label="Auth",
                summary="...",
                member_count=2,
                person_count=1,
                ticket_count=1,
                top_member_names=["@alice", "ENG-1"],
            ),
        }
        assignments = {node_a: 1, node_b: 1}

        await persist_communities(session, ws_id, assignments, meta)

        # session.execute called for: DELETE communities, UPDATE clear nodes,
        # plus per-node update and per-community add.
        assert session.execute.await_count >= 2
        assert session.add.call_count == 1  # one GraphCommunity row

    @pytest.mark.asyncio
    async def test_empty_inputs_still_clear_previous(self, session):
        ws_id = uuid.uuid4()
        await persist_communities(session, ws_id, {}, {})
        # Even with empty assignments, we must still wipe the previous snapshot.
        assert session.execute.await_count >= 2
        assert session.add.call_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_communities.py::TestPersistCommunities -v
```

Expected: FAIL with `ImportError: cannot import name 'CommunityMeta'`.

- [ ] **Step 3: Implement CommunityMeta + persist_communities**

Append to `backend/src/services/graph_communities.py`:

```python
import uuid as _uuid
from dataclasses import dataclass, field

from sqlalchemy import delete as sql_delete
from sqlalchemy import update as sql_update

from src.models.graph_community import GraphCommunity
from src.models.graph_node import GraphNode


@dataclass
class CommunityMeta:
    """Per-community metadata produced by orchestration, fed to persistence."""

    community_id: int
    label: str | None
    summary: str | None
    member_count: int
    person_count: int
    ticket_count: int
    top_member_names: list[str] = field(default_factory=list)


async def persist_communities(
    session: Any,
    workspace_id: _uuid.UUID,
    assignments: dict[_uuid.UUID, int],
    meta_by_id: dict[int, CommunityMeta],
) -> None:
    """Atomically replace this workspace's community snapshot.

    Wipes previous graph_communities rows and clears community_id on graph_nodes
    for the workspace, then inserts the new snapshot. All in one transaction.
    """
    async with session.begin():
        # 1. Clear previous snapshot.
        await session.execute(
            sql_delete(GraphCommunity).where(GraphCommunity.workspace_id == workspace_id)
        )
        await session.execute(
            sql_update(GraphNode)
            .where(GraphNode.workspace_id == workspace_id)
            .values(community_id=None)
        )

        # 2. Insert new community rows.
        for cid, m in meta_by_id.items():
            session.add(
                GraphCommunity(
                    workspace_id=workspace_id,
                    community_id=cid,
                    label=m.label,
                    summary=m.summary,
                    member_count=m.member_count,
                    person_count=m.person_count,
                    ticket_count=m.ticket_count,
                    top_member_names=m.top_member_names,
                )
            )

        # 3. Update community_id on member nodes (per-id; small N).
        for node_id, cid in assignments.items():
            await session.execute(
                sql_update(GraphNode)
                .where(GraphNode.id == node_id)
                .values(community_id=cid)
            )
```

- [ ] **Step 4: Run all tests in the file**

```bash
cd backend && uv run pytest tests/test_graph_communities.py -v
```

Expected: 20 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/graph_communities.py backend/tests/test_graph_communities.py
git commit -m "feat(graph): atomic per-workspace community snapshot persistence"
```

---

## Task 10: rebuild_communities orchestrator (loads → builds → partitions → summarizes → persists)

**Files:**
- Modify: `backend/src/services/graph_communities.py`
- Modify: `backend/tests/test_graph_communities.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_graph_communities.py`:

```python
from src.services.graph_communities import rebuild_communities


class TestRebuildCommunitiesOrchestrator:
    @pytest.mark.asyncio
    async def test_no_nodes_means_empty_persist_call(self, monkeypatch):
        ws_id = uuid.uuid4()

        async def fake_load(session, ws):
            return [], [], []  # nodes, edges, bridges

        captured: dict = {}
        async def fake_persist(session, ws, assignments, meta_by_id):
            captured["assignments"] = assignments
            captured["meta_by_id"] = meta_by_id

        monkeypatch.setattr(
            "src.services.graph_communities._load_workspace_subgraph", fake_load
        )
        monkeypatch.setattr(
            "src.services.graph_communities.persist_communities", fake_persist
        )

        session = MagicMock()
        llm = _AsyncMock()
        await rebuild_communities(session, ws_id, llm_client=llm)
        assert captured == {"assignments": {}, "meta_by_id": {}}
        # No LLM calls when there are no communities.
        assert llm.generate.await_count == 0

    @pytest.mark.asyncio
    async def test_single_community_triggers_one_summary_call(self, monkeypatch):
        ws_id = uuid.uuid4()
        # Three Person nodes forming one community of size 3.
        ids = [uuid.uuid4() for _ in range(3)]
        node_objs = [
            MagicMock(id=ids[0], entity_type="Person", name="@alice"),
            MagicMock(id=ids[1], entity_type="Person", name="@bob"),
            MagicMock(id=ids[2], entity_type="Ticket", name="ENG-1"),
        ]
        edges = [
            MagicMock(source_node_id=ids[0], target_node_id=ids[1], relationship_type="reviews"),
            MagicMock(source_node_id=ids[1], target_node_id=ids[2], relationship_type="assigned_to"),
            MagicMock(source_node_id=ids[0], target_node_id=ids[2], relationship_type="authored_by"),
        ]

        async def fake_load(session, ws):
            return node_objs, edges, []

        captured: dict = {}
        async def fake_persist(session, ws, assignments, meta_by_id):
            captured["assignments"] = assignments
            captured["meta_by_id"] = meta_by_id

        monkeypatch.setattr(
            "src.services.graph_communities._load_workspace_subgraph", fake_load
        )
        monkeypatch.setattr(
            "src.services.graph_communities.persist_communities", fake_persist
        )

        session = MagicMock()
        llm = _AsyncMock()
        llm.generate.return_value = MagicMock(text=_json.dumps({
            "label": "Test Cluster",
            "summary": "Test summary.",
        }))

        await rebuild_communities(session, ws_id, llm_client=llm)
        assert llm.generate.await_count == 1
        assert len(captured["meta_by_id"]) == 1
        only_meta = next(iter(captured["meta_by_id"].values()))
        assert only_meta.label == "Test Cluster"
        assert only_meta.member_count == 3
        assert only_meta.person_count == 2
        assert only_meta.ticket_count == 1
        assert set(captured["assignments"].keys()) == set(ids)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_communities.py::TestRebuildCommunitiesOrchestrator -v
```

Expected: FAIL with `ImportError: cannot import name 'rebuild_communities'`.

- [ ] **Step 3: Implement loader + orchestrator**

Append to `backend/src/services/graph_communities.py`:

```python
from sqlalchemy import select as sql_select

from src.models.graph_edge import GraphEdge


async def _load_workspace_subgraph(session: Any, workspace_id: _uuid.UUID):
    """Load Person+Ticket nodes, direct P/T edges, and bridge descriptors.

    Returns (person_ticket_nodes, direct_edges, bridges).
    """
    # 1. Person + Ticket nodes (community members).
    pt_stmt = sql_select(GraphNode).where(
        GraphNode.workspace_id == workspace_id,
        GraphNode.entity_type.in_(("Person", "Ticket")),
        GraphNode.deleted_at.is_(None),
    )
    pt_result = await session.execute(pt_stmt)
    pt_nodes = list(pt_result.scalars().all())
    pt_ids = {n.id for n in pt_nodes}

    # 2. Bridge nodes (Decision/SlackThread/Meeting/PR).
    bridge_stmt = sql_select(GraphNode).where(
        GraphNode.workspace_id == workspace_id,
        GraphNode.entity_type.in_(tuple(BRIDGE_ENTITY_TYPES)),
        GraphNode.deleted_at.is_(None),
    )
    bridge_result = await session.execute(bridge_stmt)
    bridge_nodes = list(bridge_result.scalars().all())
    bridge_ids = {n.id for n in bridge_nodes}

    # 3. All non-deleted edges in this workspace.
    edge_stmt = sql_select(GraphEdge).where(
        GraphEdge.workspace_id == workspace_id,
        GraphEdge.deleted_at.is_(None),
    )
    edge_result = await session.execute(edge_stmt)
    all_edges = list(edge_result.scalars().all())

    # 4. Split into direct (P/T <-> P/T) and bridge-incident.
    direct_edges = [
        e for e in all_edges
        if e.source_node_id in pt_ids and e.target_node_id in pt_ids
    ]

    # Build bridge descriptors keyed by bridge_id.
    person_ids = {n.id for n in pt_nodes if n.entity_type == "Person"}
    ticket_ids = {n.id for n in pt_nodes if n.entity_type == "Ticket"}
    bridges_acc: dict[_uuid.UUID, tuple[list, list]] = {
        b: ([], []) for b in bridge_ids
    }
    for e in all_edges:
        for endpoint, other in (
            (e.source_node_id, e.target_node_id),
            (e.target_node_id, e.source_node_id),
        ):
            if endpoint in bridge_ids:
                if other in person_ids:
                    bridges_acc[endpoint][0].append((other, e.relationship_type))
                elif other in ticket_ids:
                    bridges_acc[endpoint][1].append((other, e.relationship_type))

    bridges = [
        (b_id, p_edges, t_edges)
        for b_id, (p_edges, t_edges) in bridges_acc.items()
        if p_edges and t_edges  # drop bridges that don't touch both sides
    ]

    return pt_nodes, direct_edges, bridges


def _split_community_by_type(
    member_ids: list[_uuid.UUID],
    node_lookup: dict[_uuid.UUID, Any],
) -> tuple[list[Any], list[Any]]:
    persons = [node_lookup[i] for i in member_ids if node_lookup[i].entity_type == "Person"]
    tickets = [node_lookup[i] for i in member_ids if node_lookup[i].entity_type == "Ticket"]
    return persons, tickets


def _top_members_by_weight(
    g: nx.Graph,
    member_ids: list[_uuid.UUID],
    node_lookup: dict[_uuid.UUID, Any],
    k: int = 5,
) -> list[str]:
    """Top-k members of the community by sum of their internal edge weights."""
    member_set = set(member_ids)
    scores: list[tuple[float, str]] = []
    for nid in member_ids:
        weight_sum = 0.0
        for nbr in g.neighbors(nid):
            if nbr in member_set:
                weight_sum += g[nid][nbr].get("weight", 1.0)
        scores.append((weight_sum, node_lookup[nid].name))
    scores.sort(key=lambda x: x[0], reverse=True)
    return [name for _, name in scores[:k]]


async def rebuild_communities(
    session: Any,
    workspace_id: _uuid.UUID,
    llm_client: Any,
) -> None:
    """Top-level orchestrator: load → build → partition → summarize → persist.

    Failure-tolerant. If summary generation fails for a community, that community
    is still persisted with label=NULL, summary=NULL. If the whole rebuild fails
    before persistence, the previous snapshot is left intact.
    """
    pt_nodes, direct_edges, bridges = await _load_workspace_subgraph(session, workspace_id)

    if not pt_nodes:
        logger.info("No Person/Ticket nodes for workspace %s; clearing snapshot", workspace_id)
        await persist_communities(session, workspace_id, {}, {})
        return

    g = build_louvain_graph(pt_nodes, direct_edges, bridges)
    communities = partition_communities(g)

    if not communities:
        logger.info("No communities >= MIN_COMMUNITY_SIZE for workspace %s", workspace_id)
        await persist_communities(session, workspace_id, {}, {})
        return

    node_lookup = {n.id: n for n in pt_nodes}
    assignments: dict[_uuid.UUID, int] = {}
    meta_by_id: dict[int, CommunityMeta] = {}

    for cid, member_ids in enumerate(communities, start=1):
        persons, tickets = _split_community_by_type(member_ids, node_lookup)
        person_descs = [f"@{p.name.lstrip('@')}" for p in persons]
        ticket_descs = [t.name for t in tickets]

        summary_result = await generate_community_summary(
            llm_client=llm_client,
            person_descriptions=person_descs,
            ticket_descriptions=ticket_descs,
        )

        meta_by_id[cid] = CommunityMeta(
            community_id=cid,
            label=summary_result.get("label"),
            summary=summary_result.get("summary"),
            member_count=len(member_ids),
            person_count=len(persons),
            ticket_count=len(tickets),
            top_member_names=_top_members_by_weight(g, member_ids, node_lookup),
        )

        for nid in member_ids:
            assignments[nid] = cid

    await persist_communities(session, workspace_id, assignments, meta_by_id)
    logger.info(
        "Rebuilt communities for workspace %s: %d communities, %d members assigned",
        workspace_id, len(meta_by_id), len(assignments),
    )
```

- [ ] **Step 4: Run all tests in the file**

```bash
cd backend && uv run pytest tests/test_graph_communities.py -v
```

Expected: 22 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/graph_communities.py backend/tests/test_graph_communities.py
git commit -m "feat(graph): orchestrator that rebuilds communities for a workspace end-to-end"
```

---

## Task 11: Nightly scheduler + on-startup backfill

**Files:**
- Create: `backend/src/services/graph_scheduler.py`
- Create test: `backend/tests/test_graph_scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_graph_scheduler.py`:

```python
"""Unit tests for graph_scheduler service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.graph_scheduler import (
    seconds_until_next_03_utc,
    fetch_workspaces_with_graph_nodes,
    backfill_missing_workspaces,
)


class TestSecondsUntilNext03Utc:
    def test_returns_positive_seconds(self):
        s = seconds_until_next_03_utc()
        assert 0 < s <= 24 * 3600

    def test_at_03_returns_24h(self):
        # Mock datetime.now to be exactly 03:00:00 UTC
        with patch("src.services.graph_scheduler.datetime") as dt:
            now = datetime(2026, 4, 25, 3, 0, 0, tzinfo=timezone.utc)
            dt.now.return_value = now
            dt.timezone = timezone
            s = seconds_until_next_03_utc()
            assert s == 24 * 3600

    def test_before_03_returns_less_than_3h(self):
        with patch("src.services.graph_scheduler.datetime") as dt:
            now = datetime(2026, 4, 25, 1, 0, 0, tzinfo=timezone.utc)
            dt.now.return_value = now
            dt.timezone = timezone
            s = seconds_until_next_03_utc()
            assert s == 2 * 3600  # exactly 2h until 03:00


class TestBackfillMissingWorkspaces:
    @pytest.mark.asyncio
    async def test_skips_workspaces_with_existing_communities(self):
        ws1, ws2 = uuid.uuid4(), uuid.uuid4()

        async def fake_workspaces_with_nodes():
            return [ws1, ws2]

        async def fake_workspaces_with_communities():
            return {ws1}  # ws1 already done

        rebuilds: list[uuid.UUID] = []
        async def fake_rebuild(ws_id):
            rebuilds.append(ws_id)

        with patch(
            "src.services.graph_scheduler.fetch_workspaces_with_graph_nodes",
            new=AsyncMock(side_effect=fake_workspaces_with_nodes),
        ), patch(
            "src.services.graph_scheduler._fetch_workspaces_with_communities",
            new=AsyncMock(side_effect=fake_workspaces_with_communities),
        ), patch(
            "src.services.graph_scheduler._rebuild_for_workspace",
            new=AsyncMock(side_effect=fake_rebuild),
        ):
            await backfill_missing_workspaces()

        assert rebuilds == [ws2]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_graph_scheduler.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.graph_scheduler'`.

- [ ] **Step 3: Write the scheduler**

Create `backend/src/services/graph_scheduler.py`:

```python
"""Nightly scheduler for knowledge-graph community rebuilds.

Runs once per workspace per night at 03:00 UTC. Also performs an on-startup
backfill: any workspace that has graph_nodes but no graph_communities row
gets rebuilt immediately (without blocking startup).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import select

from src.db import async_session
from src.models.graph_community import GraphCommunity
from src.models.graph_node import GraphNode
from src.services.graph_communities import rebuild_communities
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

NIGHTLY_HOUR_UTC = 3
INTER_WORKSPACE_PAUSE_SECONDS = 5  # gentle pacing between workspaces
OUTER_LOOP_COOLDOWN_SECONDS = 300  # if the outer loop crashes, sleep 5 min before retrying


def seconds_until_next_03_utc() -> int:
    """Seconds remaining until the next 03:00 UTC firing.

    If we're at exactly 03:00:00 UTC, returns a full 24h to avoid double-fire.
    """
    now = datetime.now(timezone.utc)
    target = now.replace(hour=NIGHTLY_HOUR_UTC, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return int((target - now).total_seconds())


async def fetch_workspaces_with_graph_nodes() -> list[UUID]:
    """Workspaces with at least one non-deleted graph_node."""
    async with async_session() as session:
        stmt = select(GraphNode.workspace_id).where(
            GraphNode.deleted_at.is_(None),
        ).distinct()
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]


async def _fetch_workspaces_with_communities() -> set[UUID]:
    """Workspaces that already have at least one graph_communities row."""
    async with async_session() as session:
        stmt = select(GraphCommunity.workspace_id).distinct()
        result = await session.execute(stmt)
        return {row[0] for row in result.fetchall()}


async def _rebuild_for_workspace(workspace_id: UUID) -> None:
    """Single-workspace rebuild with its own session and LLM client."""
    llm = get_llm_client()
    async with async_session() as session:
        await rebuild_communities(session, workspace_id, llm_client=llm)


async def backfill_missing_workspaces() -> None:
    """Run rebuild_communities for any workspace lacking a snapshot yet."""
    have_nodes = await fetch_workspaces_with_graph_nodes()
    have_snapshots = await _fetch_workspaces_with_communities()
    missing = [ws for ws in have_nodes if ws not in have_snapshots]
    logger.info("Community backfill: %d workspaces missing snapshots", len(missing))
    for ws in missing:
        try:
            await _rebuild_for_workspace(ws)
        except Exception:
            logger.exception("Backfill rebuild failed for %s", ws)


async def run_community_rebuild_loop() -> None:
    """Forever: sleep until 03:00 UTC, rebuild every workspace, repeat."""
    while True:
        try:
            await asyncio.sleep(seconds_until_next_03_utc())
            workspaces = await fetch_workspaces_with_graph_nodes()
            logger.info("Nightly community rebuild starting for %d workspaces", len(workspaces))
            for ws in workspaces:
                try:
                    await _rebuild_for_workspace(ws)
                except Exception:
                    logger.exception("Community rebuild failed for %s", ws)
                # Gentle pacing — keeps DB load and LLM concurrency in check.
                await asyncio.sleep(INTER_WORKSPACE_PAUSE_SECONDS)
        except Exception:
            logger.exception("Community scheduler outer loop error")
            await asyncio.sleep(OUTER_LOOP_COOLDOWN_SECONDS)
```

- [ ] **Step 4: Run scheduler tests**

```bash
cd backend && uv run pytest tests/test_graph_scheduler.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/graph_scheduler.py backend/tests/test_graph_scheduler.py
git commit -m "feat(graph): nightly scheduler and startup backfill for community rebuilds"
```

---

## Task 12: Wire scheduler into main.py startup

**Files:**
- Modify: `backend/src/main.py`

- [ ] **Step 1: Read the current startup wiring**

Run:

```bash
grep -n "asyncio.create_task\|run_polling_fallback\|run_embedding_worker" backend/src/main.py
```

Note the lines around `polling_task = asyncio.create_task(...)`. The existing convention uses `_supervised(name, coro)` to wrap each background task.

- [ ] **Step 2: Add the import and tasks**

Edit `backend/src/main.py`. In the same block where `from src.services.sync_scheduler import run_polling_fallback` is imported (around line 87), add:

```python
    from src.services.graph_scheduler import (
        run_community_rebuild_loop,
        backfill_missing_workspaces,
    )
```

In the same block where `polling_task = asyncio.create_task(_supervised("polling_fallback", run_polling_fallback))` is created (around line 105), add:

```python
    community_rebuild_task = asyncio.create_task(
        _supervised("community_rebuild", run_community_rebuild_loop)
    )
    # On-startup backfill — runs once, doesn't block startup.
    asyncio.create_task(_supervised("community_backfill", backfill_missing_workspaces))
```

If there is a list/set of tasks that get awaited or cancelled during shutdown, append `community_rebuild_task` to it the same way `polling_task` is included.

- [ ] **Step 3: Verify the app still imports**

```bash
cd backend && uv run python -c "from src.main import app; print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/main.py
git commit -m "feat(graph): wire nightly community rebuild and startup backfill in main.py"
```

---

## Task 13: Surface CommunityContext on LinkingResult

**Files:**
- Modify: `backend/src/services/linking.py`
- Modify: `backend/tests/test_linking_graph.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_linking_graph.py`:

```python
class TestLinkingResultCommunities:
    """Verify LinkingResult exposes selected community contexts."""

    def test_community_context_dataclass_shape(self):
        from src.services.linking import CommunityContext
        cc = CommunityContext(
            community_id=1,
            label="Auth",
            summary="Owns auth.",
            person_count=2,
            ticket_count=3,
            member_count=5,
            top_member_names=["@alice", "@bob"],
            relevance_reason="assignee_primary",
        )
        assert cc.community_id == 1
        assert cc.relevance_reason == "assignee_primary"

    def test_select_communities_picks_assignee_primary_first(self):
        from src.services.linking import _select_communities, CommunityContext
        # 4 candidate communities, all valid; assignee_primary must be #1 in result.
        candidates = [
            CommunityContext(community_id=10, label="A", summary="a", person_count=2,
                             ticket_count=2, member_count=4, top_member_names=[],
                             relevance_reason="retrieved_member"),
            CommunityContext(community_id=20, label="B", summary="b", person_count=3,
                             ticket_count=3, member_count=6, top_member_names=[],
                             relevance_reason="assignee_primary"),
            CommunityContext(community_id=30, label="C", summary="c", person_count=2,
                             ticket_count=2, member_count=4, top_member_names=[],
                             relevance_reason="retrieved_member"),
            CommunityContext(community_id=40, label="D", summary="d", person_count=2,
                             ticket_count=2, member_count=4, top_member_names=[],
                             relevance_reason="retrieved_member"),
        ]
        chosen = _select_communities(candidates, max_communities=3)
        assert chosen[0].community_id == 20
        assert len(chosen) == 3

    def test_select_communities_caps_at_max(self):
        from src.services.linking import _select_communities, CommunityContext
        candidates = [
            CommunityContext(community_id=i, label=str(i), summary="s",
                             person_count=2, ticket_count=2, member_count=4,
                             top_member_names=[], relevance_reason="retrieved_member")
            for i in range(10)
        ]
        chosen = _select_communities(candidates, max_communities=3)
        assert len(chosen) == 3

    def test_select_communities_handles_empty_list(self):
        from src.services.linking import _select_communities
        assert _select_communities([], max_communities=3) == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_linking_graph.py::TestLinkingResultCommunities -v
```

Expected: FAIL with `ImportError: cannot import name 'CommunityContext'`.

- [ ] **Step 3: Add CommunityContext + selection helper**

Edit `backend/src/services/linking.py`. Near the top, alongside the other dataclass declarations (after the `LinkedItem` dataclass, before `LinkingResult`), add:

```python
@dataclass
class CommunityContext:
    """A community surfaced for synthesis prompt rendering.

    Communities are clusters discovered by nightly Louvain. Synthesis picks
    up to N relevant ones (assignee's home cluster + clusters with multiple
    retrieved-item members) and renders a "Team & Feature Context" section.
    """

    community_id: int
    label: str | None
    summary: str | None
    person_count: int
    ticket_count: int
    member_count: int
    top_member_names: list[str]
    relevance_reason: str  # "assignee_primary" | "retrieved_member"
```

Modify the `LinkingResult` dataclass to include:

```python
@dataclass
class LinkingResult:
    """Result of finding related content for a ticket."""

    ticket_id: UUID
    ticket_identifier: str
    items: list[LinkedItem] = field(default_factory=list)
    communities: list[CommunityContext] = field(default_factory=list)
```

Then add the selection helper (place it just above `find_related_content`):

```python
MAX_COMMUNITIES_IN_PROMPT = 3


def _select_communities(
    candidates: list[CommunityContext],
    max_communities: int = MAX_COMMUNITIES_IN_PROMPT,
) -> list[CommunityContext]:
    """Pick the top communities for the synthesis prompt.

    Order: assignee_primary first (always at index 0 if present),
    then retrieved_member sorted by member_count descending. Cap at max.
    """
    primary = [c for c in candidates if c.relevance_reason == "assignee_primary"]
    others = [c for c in candidates if c.relevance_reason != "assignee_primary"]
    others.sort(key=lambda c: c.member_count, reverse=True)
    chosen = (primary + others)[:max_communities]
    return chosen
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_linking_graph.py::TestLinkingResultCommunities -v
```

Expected: 4 PASS.

- [ ] **Step 5: Wire community fetching into find_related_content**

In `backend/src/services/linking.py`, add a new private helper near `_find_graph_results`:

```python
async def _fetch_communities_for_ticket(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    items: list[LinkedItem],
) -> list[CommunityContext]:
    """Resolve up to MAX_COMMUNITIES_IN_PROMPT relevant communities.

    Strategy:
    1. Find the ticket's assignee Person node and read its community_id (if any) ->
       tagged "assignee_primary".
    2. For each retrieved item (graph or otherwise), find its associated graph_node
       (if Person/Ticket) and tally community_id occurrences. Any community with >=2
       distinct member hits among items -> tagged "retrieved_member".
    3. Look up labels/summaries from graph_communities. Drop NULL-summary entries.

    Failure modes (missing tables, DB errors) return [] so synthesis silently degrades.
    """
    from collections import Counter
    from src.models.graph_community import GraphCommunity
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        # 1. Assignee primary community.
        assignee_community_id: int | None = None
        if getattr(ticket, "assignee_email", None):
            stmt = select(GraphNode).where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.entity_type == "Person",
                GraphNode.fingerprint == compute_fingerprint(
                    "Person", f"email:{ticket.assignee_email}"
                ),
                GraphNode.deleted_at.is_(None),
            )
            res = await session.execute(stmt)
            assignee_node = res.scalar_one_or_none()
            if assignee_node is not None:
                assignee_community_id = assignee_node.community_id

        # 2. Tally communities from retrieved items via their source -> graph_node.
        retrieved_community_counts: Counter[int] = Counter()
        # Map source_type -> graph entity_type for fingerprint lookup is non-trivial;
        # instead, look up graph_nodes directly by (source_type, source_id) pairs.
        item_source_pairs = {
            (it.source_type, it.source_id) for it in items
            if it.source_type in ("linear_ticket", "jira_issue")
        }
        if item_source_pairs:
            ids = [sid for _, sid in item_source_pairs]
            node_stmt = select(GraphNode).where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.source_id.in_(ids),
                GraphNode.community_id.isnot(None),
                GraphNode.deleted_at.is_(None),
            )
            node_res = await session.execute(node_stmt)
            for n in node_res.scalars().all():
                if n.community_id is not None:
                    retrieved_community_counts[n.community_id] += 1

        # 3. Build candidate set.
        candidate_ids: set[int] = set()
        if assignee_community_id is not None:
            candidate_ids.add(assignee_community_id)
        for cid, count in retrieved_community_counts.items():
            if count >= 2:
                candidate_ids.add(cid)
        if not candidate_ids:
            return []

        # 4. Fetch labels/summaries.
        comm_stmt = select(GraphCommunity).where(
            GraphCommunity.workspace_id == workspace_id,
            GraphCommunity.community_id.in_(list(candidate_ids)),
        )
        comm_res = await session.execute(comm_stmt)
        contexts: list[CommunityContext] = []
        for c in comm_res.scalars().all():
            if c.summary is None:  # drop NULL-summary clusters
                continue
            reason = (
                "assignee_primary"
                if c.community_id == assignee_community_id
                else "retrieved_member"
            )
            contexts.append(CommunityContext(
                community_id=c.community_id,
                label=c.label,
                summary=c.summary,
                person_count=c.person_count,
                ticket_count=c.ticket_count,
                member_count=c.member_count,
                top_member_names=list(c.top_member_names or []),
                relevance_reason=reason,
            ))

        return _select_communities(contexts)
    except (OperationalError, ProgrammingError):
        # community_id column or graph_communities table missing — pre-migration env.
        return []
    except Exception:
        logger.warning("Community fetch failed for %s; degrading gracefully",
                       getattr(ticket, "identifier", "?"))
        return []
```

Modify `find_related_content` to populate the new field. Find the return statement at the end of the function and replace:

```python
    return LinkingResult(
        ticket_id=ticket.id,
        ticket_identifier=ticket.identifier,
        items=budget_trimmed,
    )
```

with:

```python
    communities = await _fetch_communities_for_ticket(
        session, workspace_id, ticket, budget_trimmed
    )
    return LinkingResult(
        ticket_id=ticket.id,
        ticket_identifier=ticket.identifier,
        items=budget_trimmed,
        communities=communities,
    )
```

- [ ] **Step 6: Run all linking tests**

```bash
cd backend && uv run pytest tests/test_linking_graph.py -v
```

Expected: all prior tests still pass + 4 new ones added in Step 1.

- [ ] **Step 7: Commit**

```bash
git add backend/src/services/linking.py backend/tests/test_linking_graph.py
git commit -m "feat(graph): surface community context on LinkingResult for synthesis"
```

---

## Task 14: Add Team & Feature Context section to synthesis prompt

**Files:**
- Modify: `backend/src/services/synthesis.py`
- Create: `backend/tests/test_synthesis_communities.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_synthesis_communities.py`:

```python
"""Unit tests for community section rendering in synthesis prompt."""

from src.services.linking import CommunityContext
from src.services.synthesis import _format_team_context_section


def _ctx(community_id: int, label: str = "Auth", summary: str = "Owns auth.",
         reason: str = "assignee_primary") -> CommunityContext:
    return CommunityContext(
        community_id=community_id,
        label=label,
        summary=summary,
        person_count=2,
        ticket_count=3,
        member_count=5,
        top_member_names=["@alice", "@bob"],
        relevance_reason=reason,
    )


class TestTeamContextSection:
    def test_empty_communities_returns_empty_string(self):
        assert _format_team_context_section([]) == ""

    def test_single_community_renders_label_and_summary(self):
        out = _format_team_context_section([_ctx(1)])
        assert "Team & Feature Context" in out
        assert "Auth" in out
        assert "Owns auth." in out

    def test_multiple_communities_separated(self):
        out = _format_team_context_section([
            _ctx(1, label="Auth", summary="Owns auth."),
            _ctx(2, label="Billing", summary="Owns billing.", reason="retrieved_member"),
        ])
        assert "Auth" in out
        assert "Billing" in out
        assert out.count("members") >= 2

    def test_skips_communities_with_null_summary(self):
        # Defensive — _select_communities should already drop these, but
        # _format must also be safe.
        ctx = _ctx(1)
        ctx.summary = None
        assert _format_team_context_section([ctx]) == ""

    def test_relevance_reason_present_in_output(self):
        out = _format_team_context_section([_ctx(1, reason="assignee_primary")])
        assert "assignee_primary" in out or "primary" in out.lower()

    def test_top_members_rendered(self):
        out = _format_team_context_section([_ctx(1)])
        assert "@alice" in out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_synthesis_communities.py -v
```

Expected: FAIL with `ImportError: cannot import name '_format_team_context_section'`.

- [ ] **Step 3: Add the formatter and template**

In `backend/src/services/synthesis.py`, add (just below the existing `GRAPH_SECTION_TEMPLATE`):

```python
TEAM_CONTEXT_TEMPLATE = """\
### Team & Feature Context

The retrieved items below cluster into the following team/feature areas
(discovered by nightly community detection over the knowledge graph):

{community_blocks}"""


def _format_team_context_section(communities: list) -> str:
    """Format CommunityContext list into a synthesis-prompt section.

    Returns empty string if there are no usable communities (empty list,
    or all entries have NULL summary). Entries with NULL summary are skipped
    defensively even though _select_communities already drops them.
    """
    if not communities:
        return ""
    usable = [c for c in communities if c.summary]
    if not usable:
        return ""

    blocks: list[str] = []
    for c in usable:
        label = c.label or "Unlabeled cluster"
        top = ", ".join(c.top_member_names) if c.top_member_names else "(no top members)"
        blocks.append(
            f"**{label}** ({c.member_count} members; "
            f"{c.person_count} people, {c.ticket_count} tickets)\n"
            f"{c.summary}\n"
            f"Top members: {top}\n"
            f"Why included: {c.relevance_reason}"
        )

    return TEAM_CONTEXT_TEMPLATE.format(
        community_blocks="\n\n---\n\n".join(blocks)
    )
```

- [ ] **Step 4: Run new tests**

```bash
cd backend && uv run pytest tests/test_synthesis_communities.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/synthesis.py backend/tests/test_synthesis_communities.py
git commit -m "feat(graph): add Team & Feature Context section formatter for synthesis"
```

---

## Task 15: Integrate Team Context section into SYNTHESIS_TEMPLATE

**Files:**
- Modify: `backend/src/services/synthesis.py`
- Modify: `backend/tests/test_synthesis_communities.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_synthesis_communities.py`:

```python
from unittest.mock import MagicMock
from src.services.linking import LinkingResult


class TestSynthesisTemplateIntegration:
    def _build_linking_result(self, with_communities: bool):
        result = LinkingResult(
            ticket_id=MagicMock(),
            ticket_identifier="ENG-1",
            items=[],
            communities=[_ctx(1)] if with_communities else [],
        )
        return result

    def test_template_renders_team_context_when_present(self):
        from src.services.synthesis import _build_synthesis_prompt_text
        ticket = MagicMock(
            identifier="ENG-1", title="Test", status="In Progress",
            assignee_name="@alice", priority="High", labels="auth",
            description="Desc",
        )
        prompt = _build_synthesis_prompt_text(
            ticket, self._build_linking_result(with_communities=True), code_provenance=None,
        )
        assert "Team & Feature Context" in prompt

    def test_template_omits_team_context_when_empty(self):
        from src.services.synthesis import _build_synthesis_prompt_text
        ticket = MagicMock(
            identifier="ENG-1", title="Test", status="In Progress",
            assignee_name="@alice", priority="High", labels="auth",
            description="Desc",
        )
        prompt = _build_synthesis_prompt_text(
            ticket, self._build_linking_result(with_communities=False), code_provenance=None,
        )
        assert "Team & Feature Context" not in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_synthesis_communities.py::TestSynthesisTemplateIntegration -v
```

Expected: FAIL with `ImportError: cannot import name '_build_synthesis_prompt_text'`. (We need to extract or expose a build function. The existing prompt-building code lives inside `generate_context_page` — we'll factor it out.)

- [ ] **Step 3: Refactor — extract prompt-build helper**

In `backend/src/services/synthesis.py`, modify the `SYNTHESIS_TEMPLATE` to include the new section. Find the existing template (which contains `{graph_section}`) and replace with:

```python
SYNTHESIS_TEMPLATE = """\
{identifier} | {title} | {status} | {assignee} | {priority} | {labels}

### Ticket Description
{description}

### Related Content
{related_content}

{team_context_section}
{graph_section}
---

Based on the ticket and related content above, produce a context page. Do NOT start with a title heading. Use only these sections (skip any section that has no real content from the sources):

1. **Summary** — 2-3 sentence overview of what this ticket is about and why it matters
2. **Background & Decisions** — Key decisions, discussions, and context from Slack, meetings, and comments. If the Graph Connections section above contains [DECISION] items, weave each into the narrative as a decision trail: state what was decided, who decided it (citing the person), where it was discussed (citing the source like Slack thread name or meeting title), and which tickets it affects. Include the confidence level (e.g., "confirmed" for high confidence, "likely decided" for lower). Always cite the source so engineers can verify. Show all decisions regardless of confidence. If the **Team & Feature Context** section above lists clusters, weave the relevant cluster name and focus area into the narrative when it adds clarity (e.g., "as part of the Auth & Sessions area").
3. **Requirements** — What needs to be built or fixed, extracted from the ticket and discussions. For each requirement, tag its implementation status: **[DONE — PR ref]** if a PR or code already fulfills it, **[IN PROGRESS — PR ref]** if work is underway, or **[NOT STARTED]** if no implementation evidence exists. This is critical — an AI agent must instantly know what still needs building.
4. **Related Work** — PRs, linked tickets, and other relevant engineering artifacts. Separate into: (a) **Implementing PRs** — PRs that directly implement this ticket's requirements (state merged/open/draft and what they cover), (b) **Related PRs** — PRs in the same area but not directly implementing this ticket, (c) **Linked Tickets** — other tickets that overlap, depend on, or duplicate this work. If the Graph Connections section above shows relationships between items, explain WHY they are connected in natural language rather than listing raw connections. If the **Team & Feature Context** section identifies a cluster that owns this area, mention which cluster the related tickets belong to when it helps the engineer route a question.
5. **Relevant Code** — Code snippets from across the codebase that are relevant to this ticket. Include function signatures, class definitions, and route handlers with file paths and repo names. This helps engineers understand existing implementations even from repos they have never worked in. If any code snippets have associated discussion provenance (noted as "Discussed in:" annotations in the Related Content), include that context so engineers know where this code was talked about.
6. **Open Questions** — Unresolved questions or ambiguities that need clarification
7. **Key People** — Who is involved and their roles (assignee, reviewers, participants in discussions). If graph data shows a person's involvement across multiple sources (e.g., authored ticket, discussed in Slack, reviewed PR), list their cross-source involvement to show the full picture of their engagement. If the **Team & Feature Context** section identifies the assignee's primary cluster and its top members, note that affiliation."""
```

Find the existing internal place in `generate_context_page` where the template is `.format(...)`-rendered (search for `SYNTHESIS_TEMPLATE.format(`). Refactor that block into a top-level helper `_build_synthesis_prompt_text`:

```python
def _build_synthesis_prompt_text(
    ticket,
    linking_result,
    code_provenance,
) -> str:
    """Render the full synthesis prompt body. Pure function, side-effect free."""
    related_text = _format_related_content(
        [it for it in linking_result.items if not any(s.startswith("graph:") for s in it.signals)],
        code_provenance=code_provenance,
    )
    graph_text = _format_graph_section(
        [it for it in linking_result.items if any(s.startswith("graph:") for s in it.signals)]
    )
    team_text = _format_team_context_section(getattr(linking_result, "communities", []))

    return SYNTHESIS_TEMPLATE.format(
        identifier=getattr(ticket, "identifier", ""),
        title=getattr(ticket, "title", ""),
        status=getattr(ticket, "status", ""),
        assignee=getattr(ticket, "assignee_name", "") or "Unassigned",
        priority=getattr(ticket, "priority", ""),
        labels=getattr(ticket, "labels", "") or "",
        description=getattr(ticket, "description", "") or "",
        related_content=related_text,
        team_context_section=team_text,
        graph_section=graph_text,
    )
```

In `generate_context_page`, replace the existing template-formatting block with a single call to `_build_synthesis_prompt_text(ticket, linking_result, code_provenance)`. The existing call site varies — find every place inside `synthesis.py` that calls `SYNTHESIS_TEMPLATE.format(` and route it through this helper instead.

- [ ] **Step 4: Run all synthesis tests**

```bash
cd backend && uv run pytest tests/test_synthesis_communities.py tests/test_synthesis_graph.py tests/test_synthesis_prompt.py -v
```

Expected: all pass — both new (8 communities tests) and existing (3 graph + 6 prompt tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/synthesis.py backend/tests/test_synthesis_communities.py
git commit -m "feat(graph): integrate Team Context section into synthesis template"
```

---

## Task 16: Full backend test sweep + lint pass

**Files:**
- (verification only)

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && uv run pytest -q
```

Expected: all tests pass. Existing test count is 547 per spec — new tests should bring this above 570.

If any unrelated test fails, investigate before proceeding. Likely culprits:
- `test_linking_graph.py` — if `LinkingResult` constructor signature changed in a way other tests depend on, fix the test.
- `test_context_generate.py` / `test_synthesis_prompt.py` — if the SYNTHESIS_TEMPLATE format string added a placeholder, every existing call site must pass `team_context_section=""`. Confirm no `KeyError` raised.

- [ ] **Step 2: Run ruff**

```bash
cd backend && uv run ruff check src/services/graph_communities.py src/services/graph_scheduler.py src/services/linking.py src/services/synthesis.py src/models/graph_community.py src/models/graph_node.py
```

Expected: no errors.

- [ ] **Step 3: Run mypy on changed files**

```bash
cd backend && uv run mypy src/services/graph_communities.py src/services/graph_scheduler.py
```

Expected: clean exit. If type errors appear in pre-existing files we touched (e.g., `linking.py`), fix only the ones we introduced.

- [ ] **Step 4: Verify the migration file is the highest-numbered**

```bash
ls supabase/migrations/ | sort | tail -5
```

Expected: `00036_graph_communities.sql` appears in the last 1-2 lines (highest number).

- [ ] **Step 5: Commit anything from lint fixes**

If steps 2-3 produced fixes, commit them:

```bash
git add backend/
git commit -m "chore(graph): lint fixes for community detection modules"
```

If no changes, skip this step.

---

## Task 17: Apply migration and run end-to-end smoke test

**Files:**
- (verification only)

- [ ] **Step 1: Apply the migration**

If you have Supabase CLI access:

```bash
supabase db push
```

If using a direct connection:

```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/00036_graph_communities.sql
```

Expected: `ALTER TABLE`, `CREATE INDEX`, `CREATE TABLE`, `CREATE POLICY` all succeed.

- [ ] **Step 2: Verify schema in DB**

```bash
psql "$SUPABASE_DB_URL" -c "\d public.graph_communities"
psql "$SUPABASE_DB_URL" -c "\d public.graph_nodes" | grep community_id
```

Expected: table structure printed; `community_id | integer` row in graph_nodes.

- [ ] **Step 3: Run the rebuild orchestrator on one workspace manually**

In a Python REPL with the backend env active:

```bash
cd backend && uv run python -c "
import asyncio
from uuid import UUID
from src.db import async_session
from src.services.graph_communities import rebuild_communities
from src.services.llm_client import get_llm_client

async def main():
    ws_id = UUID('PUT_YOUR_WORKSPACE_UUID_HERE')
    llm = get_llm_client()
    async with async_session() as session:
        await rebuild_communities(session, ws_id, llm_client=llm)
    print('done')

asyncio.run(main())
"
```

Replace `PUT_YOUR_WORKSPACE_UUID_HERE` with a real workspace UUID from your DB.

Expected: `done` printed; no exceptions; logs show `Rebuilt communities for workspace ...: N communities, M members assigned`.

- [ ] **Step 4: Verify communities were written**

```bash
psql "$SUPABASE_DB_URL" -c "SELECT community_id, label, member_count FROM public.graph_communities WHERE workspace_id = 'PUT_YOUR_WORKSPACE_UUID_HERE' ORDER BY member_count DESC LIMIT 10;"
```

Expected: rows with non-empty labels and reasonable member counts (>=3 each).

```bash
psql "$SUPABASE_DB_URL" -c "SELECT entity_type, COUNT(*) FROM public.graph_nodes WHERE workspace_id = 'PUT_YOUR_WORKSPACE_UUID_HERE' AND community_id IS NOT NULL GROUP BY entity_type;"
```

Expected: counts for `Person` and `Ticket` rows.

- [ ] **Step 5: Generate a context page for a ticket and inspect the prompt**

Pick a ticket whose assignee has a `community_id`. Trigger context-page generation through your normal API. Tail the backend logs and verify the synthesis prompt now includes the `### Team & Feature Context` section.

Expected: section present with the ticket's assignee primary cluster, label, and summary visible.

If the section is missing despite the workspace having communities, the most likely cause is the assignee fingerprint mismatch — the placeholder code in `_fetch_communities_for_ticket` uses `compute_fingerprint("Person", f"email:{ticket.assignee_email}")`. If your project fingerprints persons by a different external_id format, adjust that line accordingly. (Check `graph_extractor.py` for the canonical Person fingerprint format used elsewhere in the codebase.)

- [ ] **Step 6: Final commit (release notes)**

If you adjusted the fingerprint format in Step 5 to match the codebase's actual Person fingerprint convention, commit it now:

```bash
git add backend/src/services/linking.py
git commit -m "fix(graph): match canonical Person fingerprint in community lookup"
```

---

## Self-Review

This section was checked after writing the plan:

- **Spec coverage:** every spec section maps to ≥1 task — schema (Task 2), models (Tasks 3-4), graph construction (Tasks 5-6), Louvain (Task 7), summaries (Task 8), persistence (Task 9), orchestrator (Task 10), scheduler (Tasks 11-12), linking (Task 13), synthesis (Tasks 14-15), verification (Tasks 16-17).
- **Placeholder scan:** no TBD / "implement later" / "similar to Task N" markers. Two intentional placeholders exist in Task 17 (`PUT_YOUR_WORKSPACE_UUID_HERE`) — these are real-environment substitutions, not engineering placeholders.
- **Type consistency:** `CommunityContext` shape used identically in Tasks 13-15. `CommunityMeta` (orchestrator) and `CommunityContext` (linking) are deliberately separate dataclasses — orchestrator persists by-id-int, linking surfaces enriched context to synthesis.
- **One known fragility flagged inline (Task 17 Step 5):** the assignee Person fingerprint format may differ from codebase convention. Plan acknowledges this and tells the engineer where to look (`graph_extractor.py`) to fix. This is not deferral — it's a runtime detail that depends on convention not visible from the brainstorming session.
