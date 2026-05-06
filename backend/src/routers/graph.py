"""Graph explorer API endpoints.

Exposes workspace-wide and per-ticket graph data as structured JSON
(nodes + edges), enabling frontend visualization and external tool consumption.
"""

import logging
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import get_settings
from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.graph_edge import GraphEdge
from src.models.graph_node import GraphNode
from src.models.identity_mapping import IdentityMapping
from src.models.integration import WorkspaceIntegration
from src.models.jira import JiraIssue
from src.models.ticket import LinearTicket
from src.services.dashboard_sprint import get_active_sprint, get_sprint_ticket_identifiers
from src.services.graph_ops import compute_fingerprint
from src.services.jira_sync import list_my_jira_issues
from src.services.linear_graphql import LinearGraphQLClient
from src.services.linear_oauth import get_valid_access_token

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


class TicketCluster(PydanticBaseModel):
    """A cluster of nodes around a single ticket."""

    ticket_identifier: str
    ticket_node_id: str
    ticket_name: str
    ticket_state: str | None = None
    ticket_priority: int | None = None
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class LensGraphResponse(PydanticBaseModel):
    """Response for lens-based graph views."""

    lens: Literal["my_work", "sprint", "blocked"]
    clusters: list[TicketCluster]
    all_nodes: list[GraphNodeResponse]
    all_edges: list[GraphEdgeResponse]
    node_count: int
    edge_count: int
    truncated: bool
    sprint_name: str | None = None
    sprint_progress: float | None = None


router = APIRouter(prefix="/api/graph", tags=["graph"])


# Core entity types shown by default — the units of work people care about.
# PRs, NotionPages, CodeChunks are supporting context and only shown when
# the user explicitly enables them via filter chips or passes entity_types=all.
DEFAULT_ENTITY_TYPES = ["Ticket", "Person", "Decision", "Meeting", "Message", "SlackThread"]

# Maps integration provider names to graph node source_type values
PROVIDER_TO_SOURCE_TYPES: dict[str, list[str]] = {
    "linear": ["linear_ticket", "linear_comment"],
    "jira": ["jira_issue", "jira_comment"],
    "slack": ["slack_message", "messages_digest"],
    "github": ["github_pr", "github_review", "github_commit"],
    "gitlab": ["gitlab_mr", "gitlab_note"],
    "notion": ["notion_page"],
    "fathom": ["meeting_transcript"],
    "telegram": ["telegram_message", "messages_digest"],
}


def _detect_provider(connected_providers: set[str]) -> str | None:
    """Detect primary ticket provider. Prefers Linear when both connected."""
    if "linear" in connected_providers:
        return "linear"
    if "jira" in connected_providers:
        return "jira"
    return None


async def _lens_context(session: AsyncSession, workspace_id) -> tuple[set[str], set[str], str | None]:
    """Common setup for lens endpoints: connected providers, allowed source types, primary provider."""
    connected = await _get_connected_providers(session, workspace_id)
    allowed_src = _allowed_source_types(connected)
    provider = _detect_provider(connected)
    return connected, allowed_src, provider


async def _get_connected_providers(
    session: AsyncSession, workspace_id,
) -> set[str]:
    """Get set of connected integration provider names."""
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.status == "connected",
    )
    int_result = await session.execute(int_stmt)
    return {i.provider for i in int_result.scalars().all()}


def _allowed_source_types(connected_providers: set[str]) -> set[str]:
    """Build the set of allowed source_types from connected providers."""
    allowed: set[str] = set()
    for provider in connected_providers:
        allowed.update(PROVIDER_TO_SOURCE_TYPES.get(provider, []))
    return allowed


def _node_passes_source_filter(n, allowed_source_types: set[str]) -> bool:
    """Node passes if its source_type maps to a connected integration, or has no source_type."""
    if not n.source_type:
        return True
    return n.source_type in allowed_source_types


async def _validate_ticket_identifiers(
    session: AsyncSession,
    workspace_id,
    identifiers: set[str],
    provider: str | None,
) -> set[str]:
    """Return subset of identifiers that exist as real tickets."""
    if not identifiers:
        return set()
    if provider == "jira":
        stmt = select(JiraIssue.jira_key).where(
            JiraIssue.workspace_id == workspace_id,
            JiraIssue.jira_key.in_(identifiers),
            JiraIssue.deleted_at.is_(None),
        )
    else:
        stmt = select(LinearTicket.identifier).where(
            LinearTicket.workspace_id == workspace_id,
            LinearTicket.identifier.in_(identifiers),
            LinearTicket.deleted_at.is_(None),
        )
    result = await session.execute(stmt)
    return {row[0] for row in result}


async def _inject_user_decisions(
    session: AsyncSession,
    user: UserContext,
    all_nodes: list[GraphNodeResponse],
    all_edges: list[GraphEdgeResponse],
) -> tuple[list[GraphNodeResponse], list[GraphEdgeResponse]]:
    """Find Decision nodes connected to the user via decided_in edges.

    Looks up the user's Person node(s) via identity_mappings, then finds
    Decision nodes linked by decided_in edges, and appends them to the
    response lists (deduplicating against already-included node IDs).
    """
    # Single query: fetch all identity mappings for this workspace,
    # then filter by email in Python to avoid two round-trips
    id_stmt = select(
        IdentityMapping.canonical_person_id,
        IdentityMapping.email,
    ).where(
        IdentityMapping.workspace_id == user.workspace_id,
        IdentityMapping.canonical_person_id.is_not(None),
    )
    id_result = await session.execute(id_stmt)
    all_mappings = [(row[0], row[1]) for row in id_result if row[0]]

    # Try exact email match
    person_ids = list({pid for pid, email in all_mappings if email == user.email})

    # Fallback: if single-member workspace, use all person IDs
    # (safe because there's only one user, so all identities belong to them)
    if not person_ids and all_mappings:
        from src.models.user import WorkspaceMember
        member_stmt = select(func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspace_id == user.workspace_id,
            WorkspaceMember.deleted_at.is_(None),
        )
        member_count = (await session.execute(member_stmt)).scalar_one()
        if member_count == 1:
            person_ids = list({pid for pid, _ in all_mappings})

    if not person_ids:
        return all_nodes, all_edges

    # Find decided_in edges from these person nodes
    edge_stmt = select(GraphEdge).where(
        GraphEdge.workspace_id == user.workspace_id,
        GraphEdge.relationship_type == "decided_in",
        GraphEdge.source_node_id.in_(person_ids),
        GraphEdge.deleted_at.is_(None),
    )
    edge_result = await session.execute(edge_stmt)
    decision_edges = edge_result.scalars().all()

    if not decision_edges:
        return all_nodes, all_edges

    # Fetch the Decision nodes
    decision_node_ids = [e.target_node_id for e in decision_edges]
    node_stmt = select(GraphNode).where(
        GraphNode.id.in_(decision_node_ids),
        GraphNode.entity_type == "Decision",
        GraphNode.deleted_at.is_(None),
    )
    node_result = await session.execute(node_stmt)
    decision_nodes = node_result.scalars().all()

    # Deduplicate against existing nodes
    existing_ids = {n.id for n in all_nodes}
    new_nodes = list(all_nodes)
    new_edges = list(all_edges)

    # Also ensure the Person node is in the response (needed for edge rendering)
    person_stmt = select(GraphNode).where(
        GraphNode.id.in_(person_ids),
        GraphNode.deleted_at.is_(None),
    )
    person_result = await session.execute(person_stmt)
    person_nodes = person_result.scalars().all()

    for pn in person_nodes:
        str_id = str(pn.id)
        if str_id not in existing_ids:
            new_nodes.append(GraphNodeResponse(
                id=str_id,
                entity_type=pn.entity_type,
                name=pn.name,
                depth=0,
                properties=pn.properties or {},
            ))
            existing_ids.add(str_id)

    for dn in decision_nodes:
        str_id = str(dn.id)
        if str_id not in existing_ids:
            new_nodes.append(GraphNodeResponse(
                id=str_id,
                entity_type=dn.entity_type,
                name=dn.name,
                depth=1,
                properties=dn.properties or {},
            ))
            existing_ids.add(str_id)

    existing_edge_keys = {
        (e.source, e.target, e.relationship_type) for e in all_edges
    }
    person_id_strs = {str(pid) for pid in person_ids}
    for edge in decision_edges:
        if str(edge.source_node_id) not in person_id_strs:
            continue
        key = (str(edge.source_node_id), str(edge.target_node_id), edge.relationship_type)
        if key in existing_edge_keys:
            continue
        new_edges.append(GraphEdgeResponse(
            source=key[0],
            target=key[1],
            relationship_type=edge.relationship_type,
            properties=edge.properties or {},
        ))
        existing_edge_keys.add(key)

    return new_nodes, new_edges


async def _build_ticket_clusters(
    session: AsyncSession,
    workspace_id,
    ticket_identifiers: list[str],
    provider: str | None,
    max_total_nodes: int = 50,
    allowed_src: set[str] | None = None,
) -> tuple[list[TicketCluster], list[GraphNodeResponse], list[GraphEdgeResponse]]:
    """Build ego-centric clusters around a list of ticket identifiers.

    Returns (clusters, all_nodes, all_edges) where all_nodes/all_edges
    are deduplicated across clusters.
    """
    if not ticket_identifiers:
        return [], [], []

    # Reuse caller's allowed source types if provided, otherwise query
    if allowed_src is None:
        connected_providers = await _get_connected_providers(session, workspace_id)
        allowed_src = _allowed_source_types(connected_providers)

    # Validate identifiers against real tickets
    real_ids = await _validate_ticket_identifiers(
        session, workspace_id, set(ticket_identifiers), provider
    )
    ticket_identifiers = [t for t in ticket_identifiers if t in real_ids]
    if not ticket_identifiers:
        return [], [], []

    # Look up graph nodes for each ticket
    fingerprints = {
        ident: compute_fingerprint("Ticket", ident)
        for ident in ticket_identifiers
    }
    fp_values = list(fingerprints.values())
    node_stmt = select(GraphNode).where(
        GraphNode.workspace_id == workspace_id,
        GraphNode.fingerprint.in_(fp_values),
        GraphNode.deleted_at.is_(None),
    )
    node_result = await session.execute(node_stmt)
    fp_to_node = {n.fingerprint: n for n in node_result.scalars().all()}

    # Map identifier -> graph node
    ident_to_node: dict[str, GraphNode] = {}
    for ident, fp in fingerprints.items():
        if fp in fp_to_node:
            ident_to_node[ident] = fp_to_node[fp]

    if not ident_to_node:
        return [], [], []

    # Traverse 1-hop from each ticket node.
    # Phase 1: collect raw traversal data per ticket.
    # Single query with unnest+LATERAL collapses N per-ticket round-trips into one.
    raw_traversals: dict[str, list[tuple]] = {ident: [] for ident in ident_to_node}
    all_traversed_node_ids: set[str] = set()

    node_id_to_ident = {str(gn.id): ident for ident, gn in ident_to_node.items()}
    start_ids = list(node_id_to_ident.keys())

    bulk_traverse_stmt = text("""
        SELECT t.start_id::text AS start_id,
               tg.node_id, tg.entity_type, tg.name, tg.properties,
               tg.edge_relationship_type, tg.depth, tg.path
        FROM unnest(CAST(:start_ids AS uuid[])) AS t(start_id)
        CROSS JOIN LATERAL traverse_graph(
            t.start_id,
            CAST(:workspace_id AS uuid),
            CAST(:max_depth AS int),
            'both'::text,
            NULL::text[],
            NULL::text[]
        ) AS tg
    """)
    bulk_result = await session.execute(
        bulk_traverse_stmt,
        {
            "start_ids": start_ids,
            "workspace_id": str(workspace_id),
            "max_depth": 1,
        },
    )
    for row in bulk_result.fetchall():
        start_id = row[0]
        ident = node_id_to_ident.get(start_id)
        if ident is None:
            continue
        # Drop the start_id prefix to keep downstream tuple shape unchanged.
        traversal_row = row[1:]
        raw_traversals[ident].append(traversal_row)
        all_traversed_node_ids.add(str(traversal_row[0]))

    # Phase 2: bulk-fetch GraphNode records for filtering.
    # traverse_graph() doesn't return source_type, so we need the actual rows.
    # Also filter out neighbor Ticket nodes that aren't real tickets (e.g. text-extracted
    # references like "DLVR-01" that don't exist in Linear/Jira).
    blocked_node_ids: set[str] = set()
    root_node_ids = {str(gn.id) for gn in ident_to_node.values()}

    if all_traversed_node_ids:
        src_stmt = select(GraphNode.id, GraphNode.source_type, GraphNode.entity_type, GraphNode.name).where(
            GraphNode.id.in_(all_traversed_node_ids),
        )
        src_result = await session.execute(src_stmt)
        neighbor_ticket_names: dict[str, str] = {}  # node_id -> identifier
        for row in src_result:
            nid = str(row[0])
            src_type = row[1]
            entity_type = row[2]
            # Block nodes from disconnected integrations
            if src_type and src_type not in allowed_src:
                blocked_node_ids.add(nid)
            # Collect neighbor Ticket nodes for validation
            if entity_type == "Ticket" and nid not in root_node_ids:
                name = row[3] or ""
                neighbor_ticket_names[nid] = name.split(":")[0].strip()

        # Validate neighbor tickets against real ticket tables
        if neighbor_ticket_names:
            valid_neighbor_ids = await _validate_ticket_identifiers(
                session, workspace_id, set(neighbor_ticket_names.values()), provider
            )
            for nid, ident in neighbor_ticket_names.items():
                if ident not in valid_neighbor_ids:
                    blocked_node_ids.add(nid)

    # Phase 3: build clusters with source filtering applied.
    all_node_map: dict[str, dict] = {}  # node_id -> node data (lowest depth wins)
    all_edge_set: dict[str, GraphEdgeResponse] = {}  # dedup key -> edge
    clusters: list[TicketCluster] = []

    for ident, graph_node in ident_to_node.items():
        rows = raw_traversals[ident]

        cluster_node_map: dict[str, dict] = {}
        for row in rows:
            node_id = str(row[0])
            node_depth = row[5]
            # Filter: skip nodes from disconnected integrations.
            # Depth-0 (the ticket itself) always passes.
            if node_depth > 0 and node_id in blocked_node_ids:
                continue
            node_data = {
                "id": node_id,
                "entity_type": row[1],
                "name": row[2],
                "depth": node_depth,
                "properties": row[3] if row[3] is not None else {},
            }
            if node_id not in cluster_node_map or node_depth < cluster_node_map[node_id]["depth"]:
                cluster_node_map[node_id] = node_data
            if node_id not in all_node_map or node_depth < all_node_map[node_id]["depth"]:
                all_node_map[node_id] = node_data

        # Get edges within cluster
        cluster_node_ids = list(cluster_node_map.keys())
        if cluster_node_ids:
            edge_stmt = select(GraphEdge).where(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.source_node_id.in_(cluster_node_ids),
                GraphEdge.target_node_id.in_(cluster_node_ids),
                GraphEdge.deleted_at.is_(None),
            )
            edge_result = await session.execute(edge_stmt)
            cluster_edges_raw = edge_result.scalars().all()
        else:
            cluster_edges_raw = []

        cluster_nodes = [
            GraphNodeResponse(**n) for n in cluster_node_map.values()
        ]
        cluster_edges = [
            GraphEdgeResponse(
                source=str(e.source_node_id),
                target=str(e.target_node_id),
                relationship_type=e.relationship_type,
                properties=e.properties if e.properties else {},
            )
            for e in cluster_edges_raw
        ]

        for e in cluster_edges:
            key = f"{e.source}-{e.target}-{e.relationship_type}"
            all_edge_set[key] = e

        ticket_props = graph_node.properties or {}

        clusters.append(TicketCluster(
            ticket_identifier=ident,
            ticket_node_id=str(graph_node.id),
            ticket_name=graph_node.name,
            ticket_state=ticket_props.get("state"),
            ticket_priority=ticket_props.get("priority"),
            nodes=cluster_nodes,
            edges=cluster_edges,
        ))

    # Cap total nodes
    sorted_nodes = sorted(
        all_node_map.values(),
        key=lambda n: (n["depth"], n["entity_type"] != "Ticket"),
    )
    if len(sorted_nodes) > max_total_nodes:
        sorted_nodes = sorted_nodes[:max_total_nodes]

    capped_ids = {n["id"] for n in sorted_nodes}
    all_nodes = [GraphNodeResponse(**n) for n in sorted_nodes]
    all_edges = [e for e in all_edge_set.values() if e.source in capped_ids and e.target in capped_ids]

    return clusters, all_nodes, all_edges


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
    connected_providers = await _get_connected_providers(session, user.workspace_id)
    allowed_source_types = _allowed_source_types(connected_providers)

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
        ticket_identifiers = set()
        for n in ticket_nodes:
            if n.name:
                ticket_identifiers.add(n.name.split(":")[0].strip())
            ident = (n.properties or {}).get("identifier")
            if ident:
                ticket_identifiers.add(str(ident))

        provider = _detect_provider(connected_providers)
        real_identifiers = await _validate_ticket_identifiers(
            session, user.workspace_id, ticket_identifiers, provider
        )

        # Also validate Jira if both are connected
        if "jira" in connected_providers and "linear" in connected_providers:
            jira_valid = await _validate_ticket_identifiers(
                session, user.workspace_id, ticket_identifiers, "jira"
            )
            real_identifiers |= jira_valid

        # Filter: keep ticket nodes only if their identifier exists in real tickets
        def _is_real_ticket(n: GraphNode) -> bool:
            name_id = n.name.split(":")[0].strip()
            prop_id = (n.properties or {}).get("identifier")
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
    # Nodes from connected integrations with a real source_type are always
    # shown (they're validated at ingestion). Text-extracted nodes (no
    # source_type) only shown if they have edges.
    def _should_include(n: GraphNode) -> bool:
        if not _node_passes_source_filter(n, allowed_source_types):
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


@router.get("/lens/my-work")
async def get_my_work_graph(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LensGraphResponse:
    """Get the knowledge graph centered on tickets assigned to the current user."""
    connected, allowed_src, provider = await _lens_context(session, user.workspace_id)

    ticket_identifiers: list[str] = []

    if provider == "linear":
        settings = get_settings()
        try:
            access_token = await get_valid_access_token(
                session, user.workspace_id, user.user_id, settings
            )
            client = LinearGraphQLClient(access_token)
            try:
                data = await client.query(
                    """query($first: Int!) {
                        viewer {
                            assignedIssues(
                                first: $first,
                                filter: { state: { type: { nin: ["canceled", "completed"] } } },
                                orderBy: updatedAt
                            ) {
                                nodes { identifier }
                            }
                        }
                    }""",
                    variables={"first": 15},
                )
                nodes = (
                    data.get("data", {})
                    .get("viewer", {})
                    .get("assignedIssues", {})
                    .get("nodes", [])
                )
                ticket_identifiers = [n["identifier"] for n in nodes if n.get("identifier")]
            finally:
                await client.close()
        except Exception:
            logger.warning("Failed to fetch Linear assigned issues for user %s", user.user_id)

    elif provider == "jira":
        settings = get_settings()
        try:
            issues = await list_my_jira_issues(session, user.workspace_id, settings)
            ticket_identifiers = [i["key"] for i in issues[:15] if i.get("key")]
        except Exception:
            logger.warning("Failed to fetch Jira assigned issues for workspace %s", user.workspace_id)

    # Fallback: use graph edges if no provider or API call failed
    if not ticket_identifiers:
        # Try to find tickets assigned to this user via graph edges
        # Look up user's person node via identity mappings
        id_stmt = select(IdentityMapping.canonical_person_id).where(
            IdentityMapping.workspace_id == user.workspace_id,
            IdentityMapping.email == user.email,
            IdentityMapping.canonical_person_id.is_not(None),
        )
        id_result = await session.execute(id_stmt)
        person_ids = [row[0] for row in id_result if row[0]]

        if person_ids:
            # Find tickets connected to this person via assigned_to edges
            edge_stmt = select(GraphEdge).where(
                GraphEdge.workspace_id == user.workspace_id,
                GraphEdge.relationship_type == "assigned_to",
                GraphEdge.target_node_id.in_(person_ids),
                GraphEdge.deleted_at.is_(None),
            )
            edge_result = await session.execute(edge_stmt)
            assigned_edges = edge_result.scalars().all()

            if assigned_edges:
                ticket_node_ids = [str(e.source_node_id) for e in assigned_edges]
                ticket_stmt = select(GraphNode).where(
                    GraphNode.id.in_(ticket_node_ids),
                    GraphNode.entity_type == "Ticket",
                    GraphNode.deleted_at.is_(None),
                )
                ticket_result = await session.execute(ticket_stmt)
                for node in ticket_result.scalars().all():
                    ident = (node.properties or {}).get("identifier") or node.name.split(":")[0].strip()
                    ticket_identifiers.append(ident)
                ticket_identifiers = ticket_identifiers[:15]

    clusters, all_nodes, all_edges = await _build_ticket_clusters(
        session, user.workspace_id, ticket_identifiers, provider,
        max_total_nodes=50, allowed_src=allowed_src,
    )

    # Inject decisions connected to this user's Person node(s)
    all_nodes, all_edges = await _inject_user_decisions(
        session, user, all_nodes, all_edges,
    )

    return LensGraphResponse(
        lens="my_work",
        clusters=clusters,
        all_nodes=all_nodes,
        all_edges=all_edges,
        node_count=len(all_nodes),
        edge_count=len(all_edges),
        truncated=len(all_nodes) >= 50,
    )


@router.get("/lens/sprint")
async def get_sprint_graph(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LensGraphResponse:
    """Get the knowledge graph for the active sprint/cycle."""
    connected, allowed_src, provider = await _lens_context(session, user.workspace_id)

    sprint_name: str | None = None
    sprint_progress: float | None = None
    ticket_identifiers: list[str] = []

    if provider == "linear":
        sprint_data = await get_active_sprint(session, user.workspace_id, user.user_id)
        if sprint_data:
            cycle_label = sprint_data.get("cycle_name") or f"Cycle {sprint_data.get('cycle_number', '')}"
            sprint_name = f"{sprint_data['team_name']} — {cycle_label}"
            sprint_progress = sprint_data.get("progress")
            cycle_id = sprint_data.get("cycle_id")
            if cycle_id:
                ticket_identifiers = await get_sprint_ticket_identifiers(
                    session, user.workspace_id, user.user_id, cycle_id,
                    sprint_data=sprint_data,
                )

    # Jira sprint not yet supported
    elif provider == "jira":
        return LensGraphResponse(
            lens="sprint",
            clusters=[],
            all_nodes=[],
            all_edges=[],
            node_count=0,
            edge_count=0,
            truncated=False,
            sprint_name=None,
            sprint_progress=None,
        )

    clusters, all_nodes, all_edges = await _build_ticket_clusters(
        session, user.workspace_id, ticket_identifiers, provider,
        max_total_nodes=80, allowed_src=allowed_src,
    )

    return LensGraphResponse(
        lens="sprint",
        clusters=clusters,
        all_nodes=all_nodes,
        all_edges=all_edges,
        node_count=len(all_nodes),
        edge_count=len(all_edges),
        truncated=len(all_nodes) >= 80,
        sprint_name=sprint_name,
        sprint_progress=sprint_progress,
    )


@router.get("/lens/blocked")
async def get_blocked_graph(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LensGraphResponse:
    """Get the knowledge graph for blocked tickets."""
    connected, allowed_src, provider = await _lens_context(session, user.workspace_id)

    # Find all 'blocks' edges in workspace
    blocks_stmt = select(GraphEdge).where(
        GraphEdge.workspace_id == user.workspace_id,
        GraphEdge.relationship_type == "blocks",
        GraphEdge.deleted_at.is_(None),
    )
    blocks_result = await session.execute(blocks_stmt)
    blocks_edges = blocks_result.scalars().all()

    if not blocks_edges:
        return LensGraphResponse(
            lens="blocked",
            clusters=[],
            all_nodes=[],
            all_edges=[],
            node_count=0,
            edge_count=0,
            truncated=False,
        )

    # Collect all ticket node IDs involved in blocks
    blocked_node_ids = set()
    for edge in blocks_edges:
        blocked_node_ids.add(str(edge.source_node_id))
        blocked_node_ids.add(str(edge.target_node_id))

    # Look up these nodes to get ticket identifiers
    node_stmt = select(GraphNode).where(
        GraphNode.id.in_(blocked_node_ids),
        GraphNode.entity_type == "Ticket",
        GraphNode.workspace_id == user.workspace_id,
        GraphNode.deleted_at.is_(None),
    )
    node_result = await session.execute(node_stmt)
    ticket_identifiers = []
    for node in node_result.scalars().all():
        ident = (node.properties or {}).get("identifier") or node.name.split(":")[0].strip()
        ticket_identifiers.append(ident)

    clusters, all_nodes, all_edges = await _build_ticket_clusters(
        session, user.workspace_id, ticket_identifiers, provider,
        max_total_nodes=50, allowed_src=allowed_src,
    )

    return LensGraphResponse(
        lens="blocked",
        clusters=clusters,
        all_nodes=all_nodes,
        all_edges=all_edges,
        node_count=len(all_nodes),
        edge_count=len(all_edges),
        truncated=len(all_nodes) >= 50,
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
