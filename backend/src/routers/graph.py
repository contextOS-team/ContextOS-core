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
from src.models.integration import WorkspaceIntegration
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


# Core entity types shown by default — the units of work people care about.
# PRs, NotionPages, CodeChunks are supporting context and only shown when
# the user explicitly enables them via filter chips or passes entity_types=all.
DEFAULT_ENTITY_TYPES = ["Ticket", "Person", "Decision", "Meeting", "Message", "SlackThread"]

# Maps integration provider names to graph node source_type values
PROVIDER_TO_SOURCE_TYPES: dict[str, list[str]] = {
    "linear": ["linear_ticket", "linear_comment"],
    "jira": ["jira_issue", "jira_comment"],
    "slack": ["slack_message"],
    "github": ["github_pr", "github_review", "github_commit"],
    "gitlab": ["gitlab_mr", "gitlab_note"],
    "notion": ["notion_page"],
    "fathom": ["meeting_transcript"],
    "telegram": ["telegram_message"],
}


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

    # Look up connected integrations for this workspace
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.status == "connected",
    )
    int_result = await session.execute(int_stmt)
    connected_providers = {i.provider for i in int_result.scalars().all()}

    # Build the set of allowed source_types from connected providers
    allowed_source_types: set[str] = set()
    for provider in connected_providers:
        allowed_source_types.update(PROVIDER_TO_SOURCE_TYPES.get(provider, []))

    # Step 1: Get ALL workspace nodes (unfiltered) for connectivity analysis
    all_node_stmt = select(GraphNode).where(
        GraphNode.workspace_id == user.workspace_id,
        GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    all_node_result = await session.execute(all_node_stmt)
    every_node = all_node_result.scalars().all()

    if not every_node:
        return WorkspaceGraphResponse(
            node_count=0,
            edge_count=0,
            truncated=False,
            total_available=0,
            nodes=[],
            edges=[],
        )

    # Step 1b: Validate Ticket nodes against actual tickets table.
    # Text-extracted ticket references (e.g. "SHA-256" from code) that don't
    # exist as real Linear/Jira tickets get filtered out at query time.
    ticket_nodes = [n for n in every_node if n.entity_type == "Ticket"]
    if ticket_nodes:
        ticket_identifiers = {
            n.name.split(":")[0].strip()  # Handle "CON-50: title" format
            for n in ticket_nodes
            if n.name
        }
        # Also check properties.identifier
        for n in ticket_nodes:
            ident = n.properties.get("identifier") if n.properties else None
            if ident:
                ticket_identifiers.add(str(ident))

        real_ticket_stmt = select(LinearTicket.identifier).where(
            LinearTicket.workspace_id == user.workspace_id,
            LinearTicket.identifier.in_(ticket_identifiers),  # type: ignore[union-attr]
            LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        real_result = await session.execute(real_ticket_stmt)
        real_identifiers = {row[0] for row in real_result}

        # Filter: keep ticket nodes only if their identifier exists in real tickets
        def _is_real_ticket(n: GraphNode) -> bool:
            name_id = n.name.split(":")[0].strip()
            prop_id = n.properties.get("identifier") if n.properties else None
            return name_id in real_identifiers or (prop_id and str(prop_id) in real_identifiers)

        every_node = [
            n for n in every_node
            if n.entity_type != "Ticket" or _is_real_ticket(n)
        ]

    every_node_lookup = {str(n.id): n for n in every_node}
    every_node_ids = set(every_node_lookup.keys())

    # Step 2: Get ALL workspace edges for connectivity analysis
    edge_stmt = select(GraphEdge).where(
        GraphEdge.workspace_id == user.workspace_id,
        GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    edge_result = await session.execute(edge_stmt)
    every_edge = edge_result.scalars().all()

    # Step 3: Count TOTAL edges per node (across all types)
    total_edge_counter: Counter[str] = Counter()
    for edge in every_edge:
        src, tgt = str(edge.source_node_id), str(edge.target_node_id)
        if src in every_node_ids and tgt in every_node_ids:
            total_edge_counter[src] += 1
            total_edge_counter[tgt] += 1

    # Step 4: Filter to requested entity types, keeping only connected nodes
    # Also scope to nodes from connected integrations only
    def _node_passes_source_filter(n: GraphNode) -> bool:
        """Node passes if its source_type maps to a connected integration, or has no source_type."""
        if not n.source_type:
            return True  # Nodes without source_type (e.g. from identity resolution) pass
        return n.source_type in allowed_source_types

    # Nodes from connected integrations with a real source_type are always
    # shown (they're validated at ingestion). Text-extracted nodes (no
    # source_type) only shown if they have edges.
    def _should_include(n: GraphNode) -> bool:
        if not _node_passes_source_filter(n):
            return False
        has_edges = total_edge_counter.get(str(n.id), 0) > 0
        has_real_source = n.source_type is not None and n.source_type in allowed_source_types
        return has_edges or has_real_source

    if type_filter:
        display_nodes = {
            str(n.id): n for n in every_node
            if n.entity_type in type_filter and _should_include(n)
        }
    else:
        display_nodes = {
            str(n.id): n for n in every_node
            if _should_include(n)
        }

    if not display_nodes:
        return WorkspaceGraphResponse(
            node_count=0,
            edge_count=0,
            truncated=False,
            total_available=0,
            nodes=[],
            edges=[],
        )

    display_ids = set(display_nodes.keys())

    # Step 5: Get edges between display nodes only
    display_edges = [
        e for e in every_edge
        if str(e.source_node_id) in display_ids
        and str(e.target_node_id) in display_ids
    ]

    # Step 6: Re-count edges within display set for ranking
    display_edge_counter: Counter[str] = Counter()
    for edge in display_edges:
        display_edge_counter[str(edge.source_node_id)] += 1
        display_edge_counter[str(edge.target_node_id)] += 1

    # Step 7: Sort by display connectivity, apply limit
    sorted_ids = sorted(
        display_ids,
        key=lambda nid: -display_edge_counter.get(nid, 0),
    )

    total_available = len(sorted_ids)
    truncated = total_available > limit
    capped_ids = set(sorted_ids[:limit])

    # Step 8: Filter edges to capped set
    filtered_edges = [
        e for e in display_edges
        if str(e.source_node_id) in capped_ids
        and str(e.target_node_id) in capped_ids
    ]

    # Step 9: Build response
    response_nodes = [
        GraphNodeResponse(
            id=nid,
            entity_type=n.entity_type,
            name=n.name,
            depth=0,
            properties=n.properties if n.properties else {},
        )
        for nid in sorted_ids[:limit]
        if (n := display_nodes.get(nid))
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
