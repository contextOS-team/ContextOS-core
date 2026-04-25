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
            NOTE: bridge projection is not yet implemented (Task 6).

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
