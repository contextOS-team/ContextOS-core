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
            All edge directions ignored. For each bridge, a weighted edge is added
            for every (person, ticket) pair using BRIDGE_DAMPENER * min(p_weight, t_weight).
            If a direct edge already exists between the pair, the bridge weight is summed in.

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

    return g


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
