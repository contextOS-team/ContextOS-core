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
    mock_session.execute.side_effect = [
        _mock_membership(),  # auth
        _mock_provider_query(["linear"]),  # _get_connected_providers (endpoint)
        # _build_ticket_clusters calls (allowed_src passed in, skips provider query):
        _mock_ticket_validation(["CON-1"]),
        _mock_fingerprint_nodes({"CON-1": TICKET_1_NODE}),
        _mock_traverse([
            _make_traverse_row(TICKET_1_NODE, "Ticket", "CON-1", 0),
            _make_traverse_row(PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
        ]),
        _mock_source_type_lookup({
            str(TICKET_1_NODE): ("linear_ticket", "Ticket", "CON-1"),
            str(PERSON_NODE): (None, "Person", "Alice"),
        }),
        _mock_edge_result([
            _mock_edge(TICKET_1_NODE, PERSON_NODE, "mentions"),
        ]),
    ]

    # Patch at source module paths (lazy imports inside function bodies)
    with patch("src.services.linear_oauth.get_valid_access_token", new_callable=AsyncMock, return_value="fake-token"), \
         patch("src.services.linear_graphql.LinearGraphQLClient") as mock_client_cls:
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
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["jira"]),
        # _build_ticket_clusters calls (allowed_src passed in):
        _mock_ticket_validation(["PROJ-1"]),
        _mock_fingerprint_nodes({"PROJ-1": TICKET_1_NODE}),
        _mock_traverse([
            _make_traverse_row(TICKET_1_NODE, "Ticket", "PROJ-1", 0),
        ]),
        _mock_source_type_lookup({str(TICKET_1_NODE): ("jira_issue", "Ticket", "PROJ-1")}),
        _mock_edge_result([]),
    ]

    with patch("src.services.jira_sync.list_my_jira_issues", new_callable=AsyncMock) as mock_jira:
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
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query([]),  # no ticket providers
        # Fallback: identity mapping lookup returns no person_ids
        _mock_empty_result(),
    ]

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
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["linear"]),
        # Linear API will fail, fallback runs:
        _mock_empty_result(),  # IdentityMapping query
    ]

    with patch("src.services.linear_oauth.get_valid_access_token", new_callable=AsyncMock, side_effect=Exception("token expired")):
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
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["linear"]),
        # _build_ticket_clusters (allowed_src passed in):
        _mock_ticket_validation(["CON-10", "CON-11"]),
        _mock_fingerprint_nodes({"CON-10": TICKET_1_NODE, "CON-11": TICKET_2_NODE}),
        _mock_traverse([
            _make_traverse_row(TICKET_1_NODE, "Ticket", "CON-10", 0),
            _make_traverse_row(PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
        ]),
        _mock_traverse([
            _make_traverse_row(TICKET_2_NODE, "Ticket", "CON-11", 0),
        ]),
        _mock_source_type_lookup({
            str(TICKET_1_NODE): ("linear_ticket", "Ticket", "CON-10"),
            str(PERSON_NODE): (None, "Person", "Alice"),
            str(TICKET_2_NODE): ("linear_ticket", "Ticket", "CON-11"),
        }),
        _mock_edge_result([_mock_edge(TICKET_1_NODE, PERSON_NODE, "mentions")]),
        _mock_edge_result([]),
    ]

    with patch("src.services.dashboard_sprint.get_active_sprint", new_callable=AsyncMock) as mock_sprint, \
         patch("src.services.dashboard_sprint.get_sprint_ticket_identifiers", new_callable=AsyncMock) as mock_tickets:
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
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["linear"]),
    ]

    with patch("src.services.dashboard_sprint.get_active_sprint", new_callable=AsyncMock, return_value=None):
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

    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["linear"]),
        _mock_edge_result([_mock_edge(blocker_node, blocked_node, "blocks")]),
        _blocked_node_result(),
        # _build_ticket_clusters (allowed_src passed in):
        _mock_ticket_validation(["CON-5", "CON-6"]),
        _mock_fingerprint_nodes({"CON-5": blocker_node, "CON-6": blocked_node}),
        _mock_traverse([
            _make_traverse_row(blocker_node, "Ticket", "CON-5", 0),
            _make_traverse_row(blocked_node, "Ticket", "CON-6", 1, edge_relationship_type="blocks"),
        ]),
        _mock_traverse([
            _make_traverse_row(blocked_node, "Ticket", "CON-6", 0),
            _make_traverse_row(blocker_node, "Ticket", "CON-5", 1, edge_relationship_type="blocks"),
        ]),
        _mock_source_type_lookup({
            str(blocker_node): ("linear_ticket", "Ticket", "CON-5"),
            str(blocked_node): ("linear_ticket", "Ticket", "CON-6"),
        }),
        _mock_edge_result([_mock_edge(blocker_node, blocked_node, "blocks")]),
        _mock_edge_result([_mock_edge(blocker_node, blocked_node, "blocks")]),
    ]

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
    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query([]),
        _mock_empty_result(),  # fallback identity mapping
    ]

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

    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["linear"]),
        # _build_ticket_clusters (allowed_src passed in):
        _mock_ticket_validation(["CON-1"]),
        _mock_fingerprint_nodes({"CON-1": TICKET_1_NODE}),
        _mock_traverse([
            _make_traverse_row(TICKET_1_NODE, "Ticket", "CON-1", 0),
            _make_traverse_row(PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
            _make_traverse_row(notion_node, "NotionPage", "Design Doc", 1, edge_relationship_type="references"),
        ]),
        _mock_source_type_lookup({
            str(TICKET_1_NODE): ("linear_ticket", "Ticket", "CON-1"),
            str(PERSON_NODE): (None, "Person", "Alice"),
            str(notion_node): ("notion_page", "NotionPage", "Design Doc"),  # Notion not connected -> filtered
        }),
        _mock_edge_result([
            _mock_edge(TICKET_1_NODE, PERSON_NODE, "mentions"),
        ]),
    ]

    with patch("src.services.linear_oauth.get_valid_access_token", new_callable=AsyncMock, return_value="fake-token"), \
         patch("src.services.linear_graphql.LinearGraphQLClient") as mock_cls:
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
