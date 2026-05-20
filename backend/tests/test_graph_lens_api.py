"""Tests for graph lens API endpoints.

Covers:
- GET /api/graph/lens/my-work -- My Work lens (Linear, Jira, fallback)
- GET /api/graph/lens/sprint -- Sprint lens (Linear, Jira graceful fallback)
- GET /api/graph/lens/blocked -- Blocked lens (provider-agnostic)
- Route precedence: /lens/* doesn't clash with /{ticket_identifier}
- Integration source filtering in _build_ticket_clusters
- Empty state responses
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_WORKSPACE_ID, TEST_USER_ID, TEST_EMAIL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_membership() -> MagicMock:
    """Create mock workspace membership result (first DB call in auth)."""
    mock = MagicMock()
    mock.scalar_one_or_none.return_value = TEST_WORKSPACE_ID
    return mock


def _mock_provider_query(providers: list[str]) -> MagicMock:
    """Mock _detect_ticket_provider DB result."""
    integrations = []
    for p in providers:
        i = MagicMock()
        i.provider = p
        i.status = "connected"
        integrations.append(i)
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = integrations
    return mock


def _mock_connected_providers(providers: list[str]) -> MagicMock:
    """Mock _get_connected_providers DB result (same shape as provider query)."""
    return _mock_provider_query(providers)


def _mock_ticket_validation(identifiers: list[str]) -> MagicMock:
    """Mock _validate_ticket_identifiers DB result."""
    mock = MagicMock()
    mock.__iter__ = lambda self: iter([(i,) for i in identifiers])
    return mock


def _mock_fingerprint_nodes(ident_to_id: dict[str, UUID]) -> MagicMock:
    """Mock GraphNode fingerprint lookup."""
    from src.services.graph_ops import compute_fingerprint

    nodes = []
    for ident, node_id in ident_to_id.items():
        n = MagicMock()
        n.id = node_id
        n.fingerprint = compute_fingerprint("Ticket", ident)
        n.name = ident
        n.properties = {"identifier": ident}
        n.entity_type = "Ticket"
        nodes.append(n)
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = nodes
    return mock


def _make_traverse_row(
    node_id: UUID,
    entity_type: str,
    name: str,
    depth: int,
    properties: dict | None = None,
    edge_relationship_type: str | None = None,
) -> tuple:
    """Create a row tuple matching traverse_graph() output columns."""
    return (
        node_id,
        entity_type,
        name,
        properties or {},
        edge_relationship_type,
        depth,
        [str(node_id)],
    )


def _mock_traverse(rows: list[tuple]) -> MagicMock:
    """Mock traverse_graph SQL result."""
    mock = MagicMock()
    mock.fetchall.return_value = rows
    return mock


def _make_bulk_traverse_row(
    start_node_id: UUID,
    node_id: UUID,
    entity_type: str,
    name: str,
    depth: int,
    properties: dict | None = None,
    edge_relationship_type: str | None = None,
) -> tuple:
    """Row for the *bulk* traverse query.

    The current _build_ticket_clusters runs one unnest+LATERAL query whose
    SELECT prefixes every traverse_graph row with ``t.start_id::text``
    (src/routers/graph.py: ``start_id = row[0]`` then
    ``traversal_row = row[1:]``). So each mocked row needs the originating
    ticket node id (as str) prepended to the 7-col traverse tuple.
    """
    return (
        str(start_node_id),
        node_id,
        entity_type,
        name,
        properties or {},
        edge_relationship_type,
        depth,
        [str(node_id)],
    )


def _mock_source_type_lookup(
    id_to_info: dict[str, tuple[str | None, str, str]],
) -> MagicMock:
    """Mock the bulk GraphNode (id, source_type, entity_type, name) lookup.

    id_to_info maps node_id -> (source_type, entity_type, name).
    """
    mock = MagicMock()
    mock.__iter__ = lambda self: iter(
        [(UUID(nid), src, etype, name) for nid, (src, etype, name) in id_to_info.items()]
    )
    return mock


def _mock_edge(
    source_node_id: UUID,
    target_node_id: UUID,
    relationship_type: str = "mentions",
) -> MagicMock:
    edge = MagicMock()
    edge.source_node_id = source_node_id
    edge.target_node_id = target_node_id
    edge.relationship_type = relationship_type
    edge.properties = {}
    return edge


def _mock_edge_result(edges: list[MagicMock]) -> MagicMock:
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = edges
    return mock


def _mock_empty_result() -> MagicMock:
    """Mock an empty DB result."""
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = []
    mock.__iter__ = lambda self: iter([])
    return mock


def _stmt_signature(stmt) -> str:
    """Stable key for a session.execute() statement.

    The lens endpoints query the *same* ORM entity with several different
    shapes (e.g. select(GraphNode) for the fingerprint lookup vs
    select(GraphNode.id, GraphNode.source_type, ...) for the source-type
    probe), so entity name alone is ambiguous. We disambiguate by
    (entity name, number of selected column descriptions). Raw text()
    statements (traverse_graph) have no entity -> "TEXT".
    """
    from tests.conftest import _stmt_entity_name

    name = _stmt_entity_name(stmt)
    if name is None:
        return "TEXT"
    try:
        ncols = len(stmt.column_descriptions)
    except Exception:
        ncols = 0
    return f"{name}:{ncols}"


def _LensRouter(handlers: dict[str, list]):
    """Build a session.execute side-effect routed by statement signature.

    The current graph router collapsed N per-ticket traverse_graph round
    trips into ONE bulk unnest+LATERAL query and added a trailing
    _inject_user_decisions() pass (extra IdentityMapping / WorkspaceMember
    queries). Brittle ordered side_effect lists rot on both changes; this
    dispatcher keys on *what* is queried and serves a per-signature FIFO
    queue, defaulting to an inert empty result for anything unregistered
    (so the decisions pass never raises).

    Returns a plain ``async def`` closure (NOT a callable object): AsyncMock
    only auto-awaits function side_effects, not objects with an async
    ``__call__`` -- the latter leak an un-awaited coroutine.
    """
    queues = {k: list(v) for k, v in handlers.items()}

    def _empty():
        m = MagicMock()
        m.scalars.return_value.all.return_value = []
        m.scalar_one_or_none.return_value = None
        m.scalar_one.return_value = 0
        m.fetchall.return_value = []
        m.__iter__ = lambda self: iter([])
        return m

    async def _execute(stmt, *args, **kwargs):
        sig = _stmt_signature(stmt)
        queue = queues.get(sig)
        if not queue:
            return _empty()
        # Keep last entry sticky so repeated identical queries (e.g. the
        # per-cluster edge query, once per ticket) all get a result.
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return _execute


# Statement signatures (entity name : selected-column count).
SIG_MEMBER = "WorkspaceMember:1"          # auth membership lookup
SIG_INTEGRATION = "WorkspaceIntegration:1"  # _get_connected_providers
SIG_LINEAR_VALIDATE = "LinearTicket:1"    # _validate_ticket_identifiers (linear)
SIG_JIRA_VALIDATE = "JiraIssue:1"         # _validate_ticket_identifiers (jira)
SIG_NODE_FULL = "GraphNode:1"             # select(GraphNode) fingerprint/blocked lookup
SIG_NODE_SRC = "GraphNode:4"              # select(GraphNode.id, source_type, entity_type, name)
SIG_EDGE = "GraphEdge:1"                  # select(GraphEdge) blocks / per-cluster edges
SIG_TRAVERSE = "TEXT"                     # bulk traverse_graph text()
SIG_IDENTITY_FALLBACK = "IdentityMapping:1"   # my-work fallback id lookup
SIG_IDENTITY_DECISIONS = "IdentityMapping:2"  # _inject_user_decisions id+email


# Stable test IDs
TICKET_1_NODE = uuid4()
TICKET_2_NODE = uuid4()
PERSON_NODE = uuid4()
SLACK_NODE = uuid4()


# ---------------------------------------------------------------------------
# GET /api/graph/lens/my-work
# ---------------------------------------------------------------------------


def test_my_work_linear_happy_path(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """My Work lens with Linear returns assigned ticket clusters."""
    # Signature-routed (not order-based): _build_ticket_clusters now issues
    # ONE bulk traverse_graph text() query (was N), and the endpoint runs a
    # trailing _inject_user_decisions() pass. The router serves an inert
    # empty result for the (unregistered) IdentityMapping decisions query.
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query(["linear"])],
        SIG_LINEAR_VALIDATE: [_mock_ticket_validation(["CON-1"])],
        SIG_NODE_FULL: [_mock_fingerprint_nodes({"CON-1": TICKET_1_NODE})],
        SIG_TRAVERSE: [_mock_traverse([
            _make_bulk_traverse_row(TICKET_1_NODE, TICKET_1_NODE, "Ticket", "CON-1", 0),
            _make_bulk_traverse_row(TICKET_1_NODE, PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
        ])],
        SIG_NODE_SRC: [_mock_source_type_lookup({
            str(TICKET_1_NODE): ("linear_ticket", "Ticket", "CON-1"),
            str(PERSON_NODE): (None, "Person", "Alice"),
        })],
        SIG_EDGE: [_mock_edge_result([
            _mock_edge(TICKET_1_NODE, PERSON_NODE, "mentions"),
        ])],
    })

    # LinearGraphQLClient + get_valid_access_token are bound into
    # src.routers.graph at import time (module-level import), so they MUST
    # be patched there, not at their defining modules.
    with patch("src.routers.graph.get_valid_access_token", new_callable=AsyncMock, return_value="fake-token"), \
         patch("src.routers.graph.LinearGraphQLClient") as mock_client_cls:
        mock_linear = AsyncMock()
        mock_linear.query.return_value = {
            "data": {
                "viewer": {
                    "assignedIssues": {
                        "nodes": [{"identifier": "CON-1"}]
                    }
                }
            }
        }
        mock_linear.close = AsyncMock()
        mock_client_cls.return_value = mock_linear

        response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "my_work"
    assert data["node_count"] == 2
    assert data["edge_count"] == 1
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["ticket_identifier"] == "CON-1"
    assert len(data["clusters"][0]["nodes"]) == 2
    assert len(data["all_nodes"]) == 2
    assert len(data["all_edges"]) == 1


def test_my_work_jira_happy_path(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """My Work lens with Jira returns assigned issue clusters."""
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query(["jira"])],
        SIG_JIRA_VALIDATE: [_mock_ticket_validation(["PROJ-1"])],
        SIG_NODE_FULL: [_mock_fingerprint_nodes({"PROJ-1": TICKET_1_NODE})],
        SIG_TRAVERSE: [_mock_traverse([
            _make_bulk_traverse_row(TICKET_1_NODE, TICKET_1_NODE, "Ticket", "PROJ-1", 0),
        ])],
        SIG_NODE_SRC: [_mock_source_type_lookup({str(TICKET_1_NODE): ("jira_issue", "Ticket", "PROJ-1")})],
        SIG_EDGE: [_mock_edge_result([])],
    })

    # list_my_jira_issues is imported into src.routers.graph at module load.
    with patch("src.routers.graph.list_my_jira_issues", new_callable=AsyncMock) as mock_jira:
        mock_jira.return_value = [{"key": "PROJ-1", "summary": "Test issue"}]
        response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "my_work"
    assert data["node_count"] == 1
    assert data["clusters"][0]["ticket_identifier"] == "PROJ-1"


def test_my_work_no_provider_falls_back_to_identity(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """My Work lens with no provider falls back to identity mapping lookup."""
    # No provider -> fallback IdentityMapping lookup (1-col select) yields
    # nothing -> empty clusters. The trailing _inject_user_decisions pass
    # also queries IdentityMapping (2-col) and is served an empty result.
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query([])],
        SIG_IDENTITY_FALLBACK: [_mock_empty_result()],
        SIG_IDENTITY_DECISIONS: [_mock_empty_result()],
    })

    response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "my_work"
    assert data["node_count"] == 0
    assert data["clusters"] == []
    assert data["all_nodes"] == []


def test_my_work_linear_api_failure_falls_back(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """My Work lens gracefully handles Linear API failure."""
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query(["linear"])],
        SIG_IDENTITY_FALLBACK: [_mock_empty_result()],
        SIG_IDENTITY_DECISIONS: [_mock_empty_result()],
    })

    # Patch the name bound into src.routers.graph (module-level import).
    with patch("src.routers.graph.get_valid_access_token", new_callable=AsyncMock, side_effect=Exception("token expired")):
        response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["node_count"] == 0


# ---------------------------------------------------------------------------
# GET /api/graph/lens/sprint
# ---------------------------------------------------------------------------


def test_sprint_linear_happy_path(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Sprint lens with active Linear cycle returns sprint tickets."""
    # _build_ticket_clusters issues ONE bulk traverse_graph query covering
    # BOTH tickets (start_ids = [CON-10 node, CON-11 node]); the per-ticket
    # edge query then runs once per cluster (router replays SIG_EDGE).
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query(["linear"])],
        SIG_LINEAR_VALIDATE: [_mock_ticket_validation(["CON-10", "CON-11"])],
        SIG_NODE_FULL: [_mock_fingerprint_nodes({"CON-10": TICKET_1_NODE, "CON-11": TICKET_2_NODE})],
        SIG_TRAVERSE: [_mock_traverse([
            _make_bulk_traverse_row(TICKET_1_NODE, TICKET_1_NODE, "Ticket", "CON-10", 0),
            _make_bulk_traverse_row(TICKET_1_NODE, PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
            _make_bulk_traverse_row(TICKET_2_NODE, TICKET_2_NODE, "Ticket", "CON-11", 0),
        ])],
        SIG_NODE_SRC: [_mock_source_type_lookup({
            str(TICKET_1_NODE): ("linear_ticket", "Ticket", "CON-10"),
            str(PERSON_NODE): (None, "Person", "Alice"),
            str(TICKET_2_NODE): ("linear_ticket", "Ticket", "CON-11"),
        })],
        SIG_EDGE: [
            _mock_edge_result([_mock_edge(TICKET_1_NODE, PERSON_NODE, "mentions")]),
            _mock_edge_result([]),
        ],
    })

    # get_active_sprint / get_sprint_ticket_identifiers are imported into
    # src.routers.graph at module load -> patch there.
    with patch("src.routers.graph.get_active_sprint", new_callable=AsyncMock) as mock_sprint, \
         patch("src.routers.graph.get_sprint_ticket_identifiers", new_callable=AsyncMock) as mock_tickets:
        mock_sprint.return_value = {
            "team_name": "Engineering",
            "cycle_name": "Sprint 5",
            "cycle_number": 5,
            "cycle_id": "cycle-abc",
            "progress": 0.6,
        }
        mock_tickets.return_value = ["CON-10", "CON-11"]

        response = client.get("/api/graph/lens/sprint", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "sprint"
    assert data["sprint_name"] == "Engineering \u2014 Sprint 5"
    assert data["sprint_progress"] == 0.6
    assert len(data["clusters"]) == 2
    assert data["node_count"] == 3


def test_sprint_jira_returns_unsupported(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Sprint lens with Jira returns empty (not supported yet)."""
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["jira"]),
    ]

    response = client.get("/api/graph/lens/sprint", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "sprint"
    assert data["node_count"] == 0
    assert data["clusters"] == []
    assert data["sprint_name"] is None


def test_sprint_no_active_cycle(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Sprint lens with Linear but no active cycle returns empty."""
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query(["linear"])],
    })

    # get_active_sprint is bound into src.routers.graph at import time.
    with patch("src.routers.graph.get_active_sprint", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/graph/lens/sprint", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "sprint"
    assert data["node_count"] == 0
    assert data["sprint_name"] is None


# ---------------------------------------------------------------------------
# GET /api/graph/lens/blocked
# ---------------------------------------------------------------------------


def test_blocked_happy_path(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Blocked lens returns tickets involved in blocks edges."""
    blocker_node = uuid4()
    blocked_node = uuid4()

    # Build a proper mock for the GraphNode lookup
    def _blocked_node_result():
        n1 = MagicMock()
        n1.id = blocker_node
        n1.entity_type = "Ticket"
        n1.name = "CON-5"
        n1.properties = {"identifier": "CON-5"}
        n1.deleted_at = None
        n2 = MagicMock()
        n2.id = blocked_node
        n2.entity_type = "Ticket"
        n2.name = "CON-6"
        n2.properties = {"identifier": "CON-6"}
        n2.deleted_at = None
        m = MagicMock()
        m.scalars.return_value.all.return_value = [n1, n2]
        return m

    # GraphNode:1 (select(GraphNode)) is hit twice: first the blocked-ticket
    # lookup, then the fingerprint lookup inside _build_ticket_clusters --
    # so SIG_NODE_FULL is an ordered queue. GraphEdge:1 is hit for the
    # blocks-edge scan then once per cluster (replayed). Traverse is now a
    # single bulk query covering both ticket start nodes.
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query(["linear"])],
        SIG_NODE_FULL: [
            _blocked_node_result(),
            _mock_fingerprint_nodes({"CON-5": blocker_node, "CON-6": blocked_node}),
        ],
        SIG_LINEAR_VALIDATE: [_mock_ticket_validation(["CON-5", "CON-6"])],
        SIG_TRAVERSE: [_mock_traverse([
            _make_bulk_traverse_row(blocker_node, blocker_node, "Ticket", "CON-5", 0),
            _make_bulk_traverse_row(blocker_node, blocked_node, "Ticket", "CON-6", 1, edge_relationship_type="blocks"),
            _make_bulk_traverse_row(blocked_node, blocked_node, "Ticket", "CON-6", 0),
            _make_bulk_traverse_row(blocked_node, blocker_node, "Ticket", "CON-5", 1, edge_relationship_type="blocks"),
        ])],
        SIG_NODE_SRC: [_mock_source_type_lookup({
            str(blocker_node): ("linear_ticket", "Ticket", "CON-5"),
            str(blocked_node): ("linear_ticket", "Ticket", "CON-6"),
        })],
        SIG_EDGE: [
            _mock_edge_result([_mock_edge(blocker_node, blocked_node, "blocks")]),  # blocks scan
            _mock_edge_result([_mock_edge(blocker_node, blocked_node, "blocks")]),  # cluster 1
            _mock_edge_result([_mock_edge(blocker_node, blocked_node, "blocks")]),  # cluster 2
        ],
    })

    response = client.get("/api/graph/lens/blocked", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "blocked"
    assert len(data["clusters"]) == 2
    assert data["node_count"] == 2  # deduplicated across clusters
    assert data["edge_count"] == 1  # single blocks edge deduplicated


def test_blocked_no_blocks_edges(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Blocked lens with no blocks edges returns empty."""
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["linear"]),
        _mock_edge_result([]),  # no blocks edges
    ]

    response = client.get("/api/graph/lens/blocked", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["lens"] == "blocked"
    assert data["node_count"] == 0
    assert data["clusters"] == []


# ---------------------------------------------------------------------------
# Route precedence
# ---------------------------------------------------------------------------


def test_lens_routes_dont_match_ticket_identifier(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Verify /lens/my-work routes to the lens endpoint, not /{ticket_identifier}."""
    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query([])],
        SIG_IDENTITY_FALLBACK: [_mock_empty_result()],
        SIG_IDENTITY_DECISIONS: [_mock_empty_result()],
    })

    response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    assert response.json()["lens"] == "my_work"


# ---------------------------------------------------------------------------
# Integration source filtering in clusters
# ---------------------------------------------------------------------------


def test_build_clusters_filters_disconnected_sources(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Nodes from disconnected integrations are filtered from lens clusters."""
    notion_node = uuid4()

    mock_session.execute.side_effect = _LensRouter({
        SIG_MEMBER: [_mock_membership()],
        SIG_INTEGRATION: [_mock_provider_query(["linear"])],
        SIG_LINEAR_VALIDATE: [_mock_ticket_validation(["CON-1"])],
        SIG_NODE_FULL: [_mock_fingerprint_nodes({"CON-1": TICKET_1_NODE})],
        SIG_TRAVERSE: [_mock_traverse([
            _make_bulk_traverse_row(TICKET_1_NODE, TICKET_1_NODE, "Ticket", "CON-1", 0),
            _make_bulk_traverse_row(TICKET_1_NODE, PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
            _make_bulk_traverse_row(TICKET_1_NODE, notion_node, "NotionPage", "Design Doc", 1, edge_relationship_type="references"),
        ])],
        SIG_NODE_SRC: [_mock_source_type_lookup({
            str(TICKET_1_NODE): ("linear_ticket", "Ticket", "CON-1"),
            str(PERSON_NODE): (None, "Person", "Alice"),
            str(notion_node): ("notion_page", "NotionPage", "Design Doc"),  # Notion not connected -> filtered
        })],
        SIG_EDGE: [_mock_edge_result([
            _mock_edge(TICKET_1_NODE, PERSON_NODE, "mentions"),
        ])],
    })

    with patch("src.routers.graph.get_valid_access_token", new_callable=AsyncMock, return_value="fake-token"), \
         patch("src.routers.graph.LinearGraphQLClient") as mock_cls:
        mock_linear = AsyncMock()
        mock_linear.query.return_value = {
            "data": {"viewer": {"assignedIssues": {"nodes": [{"identifier": "CON-1"}]}}}
        }
        mock_linear.close = AsyncMock()
        mock_cls.return_value = mock_linear

        response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    node_types = {n["entity_type"] for n in data["all_nodes"]}
    assert "NotionPage" not in node_types
    assert data["node_count"] == 2  # Ticket + Person only
