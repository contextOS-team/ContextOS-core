"""Knowledge graph community detection (Louvain) + LLM summaries.

Per nightly cron:
1. Build a weighted undirected graph of Person+Ticket nodes
   (direct edges + edges projected through Decision/SlackThread/Meeting/PR bridges)
2. Run Louvain partitioning, drop clusters with <3 members
3. Generate a label + paragraph summary per surviving cluster via Gemini Flash
4. Persist to graph_communities table + community_id column on graph_nodes
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Any

import networkx as nx  # type: ignore[import-untyped]
from sqlalchemy import delete as sql_delete
from sqlalchemy import select as sql_select
from sqlalchemy import update as sql_update

from src.models.graph_community import GraphCommunity
from src.models.graph_edge import GraphEdge
from src.models.graph_node import GraphNode

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

    from networkx.algorithms.community import louvain_communities  # type: ignore[import-untyped]

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
            sql_delete(GraphCommunity).where(GraphCommunity.workspace_id == workspace_id)  # type: ignore[arg-type]
        )
        await session.execute(
            sql_update(GraphNode)
            .where(GraphNode.workspace_id == workspace_id)  # type: ignore[arg-type]
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
                .where(GraphNode.id == node_id)  # type: ignore[arg-type]
                .values(community_id=cid)
            )


async def _load_workspace_subgraph(
    session: Any,
    workspace_id: _uuid.UUID,
) -> tuple[list[Any], list[Any], list[Any]]:
    """Load Person+Ticket nodes, direct P/T edges, and bridge descriptors.

    Returns (person_ticket_nodes, direct_edges, bridges).
    """
    # 1. Person + Ticket nodes (community members).
    pt_stmt = sql_select(GraphNode).where(
        GraphNode.workspace_id == workspace_id,  # type: ignore[arg-type]
        GraphNode.entity_type.in_(("Person", "Ticket")),  # type: ignore[attr-defined]
        GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    pt_result = await session.execute(pt_stmt)
    pt_nodes = list(pt_result.scalars().all())
    pt_ids = {n.id for n in pt_nodes}

    # 2. Bridge nodes (Decision/SlackThread/Meeting/PR).
    bridge_stmt = sql_select(GraphNode).where(
        GraphNode.workspace_id == workspace_id,  # type: ignore[arg-type]
        GraphNode.entity_type.in_(tuple(BRIDGE_ENTITY_TYPES)),  # type: ignore[attr-defined]
        GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    bridge_result = await session.execute(bridge_stmt)
    bridge_nodes = list(bridge_result.scalars().all())
    bridge_ids = {n.id for n in bridge_nodes}

    # 3. All non-deleted edges in this workspace.
    edge_stmt = sql_select(GraphEdge).where(
        GraphEdge.workspace_id == workspace_id,  # type: ignore[arg-type]
        GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
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
    bridges_acc: dict[_uuid.UUID, tuple[list[Any], list[Any]]] = {
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
