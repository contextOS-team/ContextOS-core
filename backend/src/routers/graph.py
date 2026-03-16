"""Graph explorer API endpoints.

Exposes workspace-wide and per-ticket graph data as structured JSON
(nodes + edges), enabling frontend visualization and external tool consumption.
"""

import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.graph_edge import GraphEdge
from src.models.graph_node import GraphNode
from src.models.ticket import LinearTicket
from src.services.graph_ops import compute_fingerprint

logger = logging.getLogger(__name__)


class GraphNodeResponse(PydanticBaseModel):
    """A single node in the graph neighborhood."""

    id: str
    entity_type: str
    name: str
    depth: int
    properties: dict


class GraphEdgeResponse(PydanticBaseModel):
    """A single edge in the graph neighborhood."""

    source: str
    target: str
    relationship_type: str
    properties: dict


class GraphNeighborhoodResponse(PydanticBaseModel):
    """Full graph neighborhood response for a ticket."""

    ticket_identifier: str
    depth: int
    node_count: int
    edge_count: int
    truncated: bool
    total_available: int | None = None
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class WorkspaceGraphResponse(PydanticBaseModel):
    """Workspace-wide graph response."""

    node_count: int
    edge_count: int
    truncated: bool
    total_available: int
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


router = APIRouter(prefix="/api/graph", tags=["graph"])


# Default entity types: high-signal entities only
DEFAULT_ENTITY_TYPES = ["Ticket", "Person", "Decision", "Meeting", "PR", "Message", "SlackThread"]


@router.get("/")
async def get_workspace_graph(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=150, ge=1, le=500),
    entity_types: str | None = Query(
        default=None,
        description="Comma-separated entity types to include. "
        "Defaults to high-signal types (Ticket, Person, Decision, Meeting, PR, Message, SlackThread). "
        "Pass 'all' for everything.",
    ),
) -> WorkspaceGraphResponse:
    """Get the workspace-wide knowledge graph.

    Returns the most-connected nodes across the entire workspace,
    filtered to high-signal entity types by default and sorted by
    edge count descending. PRs are only included when they connect
    to at least one non-PR node in the result set.
    """
    # Parse entity type filter
    if entity_types == "all":
        type_filter = None
    elif entity_types:
        type_filter = [t.strip() for t in entity_types.split(",") if t.strip()]
    else:
        type_filter = DEFAULT_ENTITY_TYPES

    # Step 1: Get nodes for this workspace (filtered by type)
    node_stmt = select(GraphNode).where(
        GraphNode.workspace_id == user.workspace_id,
        GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    if type_filter:
        node_stmt = node_stmt.where(
            GraphNode.entity_type.in_(type_filter),  # type: ignore[union-attr]
        )
    node_result = await session.execute(node_stmt)
    all_nodes = node_result.scalars().all()

    if not all_nodes:
        return WorkspaceGraphResponse(
            node_count=0,
            edge_count=0,
            truncated=False,
            total_available=0,
            nodes=[],
            edges=[],
        )

    all_node_ids = [str(n.id) for n in all_nodes]
    node_lookup = {str(n.id): n for n in all_nodes}

    # Step 2: Get all edges where at least one endpoint is in our node set
    node_id_set = set(all_node_ids)
    edge_stmt = select(GraphEdge).where(
        GraphEdge.workspace_id == user.workspace_id,
        GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    edge_result = await session.execute(edge_stmt)
    # Only keep edges where BOTH endpoints are in our filtered set
    all_edges = [
        e for e in edge_result.scalars().all()
        if str(e.source_node_id) in node_id_set
        and str(e.target_node_id) in node_id_set
    ]

    # Step 3: Count edges per node for ranking
    edge_counter: Counter[str] = Counter()
    for edge in all_edges:
        edge_counter[str(edge.source_node_id)] += 1
        edge_counter[str(edge.target_node_id)] += 1

    # Step 4: Prune orphan PRs — only keep PRs that connect to a non-PR node
    pr_ids = {str(n.id) for n in all_nodes if n.entity_type == "PR"}
    non_pr_ids = node_id_set - pr_ids
    connected_pr_ids: set[str] = set()
    for edge in all_edges:
        src, tgt = str(edge.source_node_id), str(edge.target_node_id)
        if src in pr_ids and tgt in non_pr_ids:
            connected_pr_ids.add(src)
        if tgt in pr_ids and src in non_pr_ids:
            connected_pr_ids.add(tgt)
    # Remove orphan PRs
    orphan_prs = pr_ids - connected_pr_ids
    if orphan_prs:
        all_node_ids = [nid for nid in all_node_ids if nid not in orphan_prs]
        node_id_set -= orphan_prs

    # Step 5: Sort by connectivity (most-connected first), apply limit
    sorted_node_ids = sorted(
        all_node_ids,
        key=lambda nid: -edge_counter.get(nid, 0),
    )

    total_available = len(sorted_node_ids)
    truncated = total_available > limit
    capped_ids = set(sorted_node_ids[:limit])

    # Step 6: Filter edges to only those between capped nodes
    filtered_edges = [
        e for e in all_edges
        if str(e.source_node_id) in capped_ids
        and str(e.target_node_id) in capped_ids
    ]

    # Step 7: Build response
    response_nodes = [
        GraphNodeResponse(
            id=str(n.id),
            entity_type=n.entity_type,
            name=n.name,
            depth=0,
            properties=n.properties if n.properties else {},
        )
        for nid in sorted_node_ids[:limit]
        if (n := node_lookup.get(nid))
    ]

    response_edges = [
        GraphEdgeResponse(
            source=str(e.source_node_id),
            target=str(e.target_node_id),
            relationship_type=e.relationship_type,
            properties=e.properties if e.properties else {},
        )
        for e in filtered_edges
    ]

    return WorkspaceGraphResponse(
        node_count=len(response_nodes),
        edge_count=len(response_edges),
        truncated=truncated,
        total_available=total_available,
        nodes=response_nodes,
        edges=response_edges,
    )


@router.get("/{ticket_identifier}")
async def get_graph_neighborhood(
    ticket_identifier: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    depth: int = Query(default=2, ge=1, le=5),
    limit: int = Query(default=50, ge=1, le=200),
) -> GraphNeighborhoodResponse:
    """Get the graph neighborhood for a ticket.

    Returns the nodes and edges within `depth` hops of the ticket's
    graph node, capped at `limit` nodes. Workspace-scoped via auth.
    """
    # Step 1: Look up the ticket in linear_tickets
    ticket_stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == user.workspace_id,
        LinearTicket.identifier == ticket_identifier,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    ticket_result = await session.execute(ticket_stmt)
    ticket = ticket_result.scalar_one_or_none()

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_identifier} not found",
        )

    # Step 2: Compute fingerprint and look up graph node
    fingerprint = compute_fingerprint("Ticket", ticket_identifier)
    node_stmt = select(GraphNode).where(
        GraphNode.workspace_id == user.workspace_id,
        GraphNode.fingerprint == fingerprint,
        GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    node_result = await session.execute(node_stmt)
    graph_node = node_result.scalar_one_or_none()

    if graph_node is None:
        # Ticket exists but has no graph node -- return empty 200
        return GraphNeighborhoodResponse(
            ticket_identifier=ticket_identifier,
            depth=depth,
            node_count=0,
            edge_count=0,
            truncated=False,
            total_available=None,
            nodes=[],
            edges=[],
        )

    # Step 3: Call traverse_graph() SQL function
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
    traverse_result = await session.execute(
        traverse_stmt,
        {
            "start_node_id": str(graph_node.id),
            "workspace_id": str(user.workspace_id),
            "max_depth": depth,
        },
    )
    rows = traverse_result.fetchall()

    # Step 4: Deduplicate nodes by node_id, keeping minimum depth
    node_map: dict[str, dict] = {}
    for row in rows:
        node_id = str(row[0])
        node_depth = row[5]
        if node_id not in node_map or node_depth < node_map[node_id]["depth"]:
            node_map[node_id] = {
                "id": node_id,
                "entity_type": row[1],
                "name": row[2],
                "depth": node_depth,
                "properties": row[3] if row[3] is not None else {},
            }

    # Step 5: Query edges where both endpoints are in discovered node set
    node_ids = list(node_map.keys())
    if node_ids:
        edge_stmt = select(GraphEdge).where(
            GraphEdge.workspace_id == user.workspace_id,
            GraphEdge.source_node_id.in_(node_ids),  # type: ignore[union-attr]
            GraphEdge.target_node_id.in_(node_ids),  # type: ignore[union-attr]
            GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        edge_result = await session.execute(edge_stmt)
        edge_records = edge_result.scalars().all()
    else:
        edge_records = []

    # Step 6: Count edges per node for sort priority
    edge_counter: Counter[str] = Counter()
    for edge in edge_records:
        edge_counter[str(edge.source_node_id)] += 1
        edge_counter[str(edge.target_node_id)] += 1

    # Step 7: Sort nodes by (depth ASC, edge_count DESC), apply limit cap
    sorted_nodes = sorted(
        node_map.values(),
        key=lambda n: (n["depth"], -edge_counter.get(n["id"], 0)),
    )

    total_available = len(sorted_nodes)
    truncated = total_available > limit
    capped_nodes = sorted_nodes[:limit]

    # Step 8: Re-filter edges to only reference nodes in capped set
    capped_node_ids = {n["id"] for n in capped_nodes}
    filtered_edges = [
        edge
        for edge in edge_records
        if str(edge.source_node_id) in capped_node_ids
        and str(edge.target_node_id) in capped_node_ids
    ]

    # Step 9: Build and return response
    response_nodes = [
        GraphNodeResponse(
            id=n["id"],
            entity_type=n["entity_type"],
            name=n["name"],
            depth=n["depth"],
            properties=n["properties"],
        )
        for n in capped_nodes
    ]

    response_edges = [
        GraphEdgeResponse(
            source=str(e.source_node_id),
            target=str(e.target_node_id),
            relationship_type=e.relationship_type,
            properties=e.properties if e.properties is not None else {},
        )
        for e in filtered_edges
    ]

    return GraphNeighborhoodResponse(
        ticket_identifier=ticket_identifier,
        depth=depth,
        node_count=len(response_nodes),
        edge_count=len(response_edges),
        truncated=truncated,
        total_available=total_available if truncated else None,
        nodes=response_nodes,
        edges=response_edges,
    )
