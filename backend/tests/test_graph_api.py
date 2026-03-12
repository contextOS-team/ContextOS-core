"""Tests for graph explorer API endpoint.

Covers:
- GET /api/graph/{ticket_identifier} -- retrieve graph neighborhood
- 404 handling when ticket not found
- Empty 200 when ticket exists but has no graph node
- Authentication required
- Node cap truncation with metadata
- Query param depth/limit respected
- Node deduplication (same node via multiple paths)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_WORKSPACE_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_membership() -> MagicMock:
    """Create mock workspace membership result (first DB call in auth)."""
    mock = MagicMock()
    mock.scalar_one_or_none.return_value = TEST_WORKSPACE_ID
    return mock


def _mock_ticket(identifier: str = "ENG-123") -> MagicMock:
    """Create a mock LinearTicket record."""
    ticket = MagicMock()
    ticket.identifier = identifier
    ticket.workspace_id = UUID(TEST_WORKSPACE_ID) if isinstance(TEST_WORKSPACE_ID, str) else TEST_WORKSPACE_ID
    return ticket


def _mock_graph_node(node_id: UUID | None = None) -> MagicMock:
    """Create a mock GraphNode record."""
    node = MagicMock()
    node.id = node_id or uuid4()
    return node


def _make_traverse_row(
    node_id: UUID,
    entity_type: str,
    name: str,
    depth: int,
    properties: dict | None = None,
    edge_relationship_type: str | None = None,
) -> tuple:
    """Create a row tuple matching traverse_graph() output columns.

    Columns: node_id, entity_type, name, properties, edge_relationship_type, depth, path
    """
    return (
        node_id,
        entity_type,
        name,
        properties or {},
        edge_relationship_type,
        depth,
        [str(node_id)],  # path
    )


def _mock_edge(
    source_node_id: UUID,
    target_node_id: UUID,
    relationship_type: str = "mentions",
    properties: dict | None = None,
) -> MagicMock:
    """Create a mock GraphEdge record."""
    edge = MagicMock()
    edge.source_node_id = source_node_id
    edge.target_node_id = target_node_id
    edge.relationship_type = relationship_type
    edge.properties = properties or {}
    return edge


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

# Stable UUIDs for test data
ROOT_NODE_ID = uuid4()
PERSON_NODE_1_ID = uuid4()
PERSON_NODE_2_ID = uuid4()
SLACK_NODE_ID = uuid4()
EXTRA_NODE_1_ID = uuid4()
EXTRA_NODE_2_ID = uuid4()


# ---------------------------------------------------------------------------
# GET /api/graph/{ticket_identifier}
# ---------------------------------------------------------------------------


def test_get_graph_neighborhood_success(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/graph/ENG-123 returns nodes + edges for a ticket with graph data."""
    # DB call 1: workspace membership (auth)
    membership = _mock_membership()

    # DB call 2: ticket lookup
    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = _mock_ticket("ENG-123")

    # DB call 3: graph node lookup by fingerprint
    graph_node = _mock_graph_node(ROOT_NODE_ID)
    graph_node_result = MagicMock()
    graph_node_result.scalar_one_or_none.return_value = graph_node

    # DB call 4: traverse_graph() -- returns rows
    traverse_rows = [
        _make_traverse_row(ROOT_NODE_ID, "Ticket", "ENG-123", 0),
        _make_traverse_row(PERSON_NODE_1_ID, "Person", "Alice", 1, edge_relationship_type="assigned_to"),
        _make_traverse_row(PERSON_NODE_2_ID, "Person", "Bob", 1, edge_relationship_type="mentioned_by"),
        _make_traverse_row(SLACK_NODE_ID, "SlackThread", "thread-123", 2, edge_relationship_type="discussed_in"),
    ]
    traverse_result = MagicMock()
    traverse_result.fetchall.return_value = traverse_rows

    # DB call 5: edge query
    edges = [
        _mock_edge(ROOT_NODE_ID, PERSON_NODE_1_ID, "assigned_to"),
        _mock_edge(ROOT_NODE_ID, PERSON_NODE_2_ID, "mentioned_by"),
        _mock_edge(PERSON_NODE_1_ID, SLACK_NODE_ID, "discussed_in"),
    ]
    edge_result = MagicMock()
    edge_result.scalars.return_value.all.return_value = edges

    mock_session.execute.side_effect = [
        membership,
        ticket_result,
        graph_node_result,
        traverse_result,
        edge_result,
    ]

    response = client.get("/api/graph/ENG-123", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["ticket_identifier"] == "ENG-123"
    assert data["node_count"] == 4
    assert data["edge_count"] == 3
    assert data["truncated"] is False
    assert len(data["nodes"]) == 4
    assert len(data["edges"]) == 3

    # Root node should have depth 0
    root_nodes = [n for n in data["nodes"] if n["depth"] == 0]
    assert len(root_nodes) == 1
    assert root_nodes[0]["entity_type"] == "Ticket"
    assert root_nodes[0]["name"] == "ENG-123"

    # Edges should have source, target, relationship_type
    for edge in data["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "relationship_type" in edge
        assert "properties" in edge


def test_get_graph_neighborhood_ticket_not_found(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/graph/NONEXISTENT returns 404 when ticket not in linear_tickets."""
    membership = _mock_membership()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [membership, ticket_result]

    response = client.get("/api/graph/NONEXISTENT", headers=valid_auth_header)

    assert response.status_code == 404
    assert "NONEXISTENT" in response.json()["detail"]


def test_get_graph_neighborhood_no_graph_data(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/graph/ENG-123 returns empty 200 when ticket exists but no graph node."""
    membership = _mock_membership()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = _mock_ticket("ENG-123")

    graph_node_result = MagicMock()
    graph_node_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [membership, ticket_result, graph_node_result]

    response = client.get("/api/graph/ENG-123", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["node_count"] == 0
    assert data["edge_count"] == 0
    assert data["truncated"] is False


def test_get_graph_neighborhood_requires_auth(
    client: TestClient,
) -> None:
    """GET /api/graph/ENG-123 without Authorization header returns 401/403."""
    response = client.get("/api/graph/ENG-123")
    assert response.status_code in (401, 403)


def test_get_graph_neighborhood_truncation(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/graph/ENG-123?limit=2 truncates nodes and reports total_available."""
    membership = _mock_membership()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = _mock_ticket("ENG-123")

    graph_node = _mock_graph_node(ROOT_NODE_ID)
    graph_node_result = MagicMock()
    graph_node_result.scalar_one_or_none.return_value = graph_node

    # 5 nodes total (root + 4 neighbors)
    traverse_rows = [
        _make_traverse_row(ROOT_NODE_ID, "Ticket", "ENG-123", 0),
        _make_traverse_row(PERSON_NODE_1_ID, "Person", "Alice", 1, edge_relationship_type="assigned_to"),
        _make_traverse_row(PERSON_NODE_2_ID, "Person", "Bob", 1, edge_relationship_type="mentioned_by"),
        _make_traverse_row(SLACK_NODE_ID, "SlackThread", "thread-1", 2, edge_relationship_type="discussed_in"),
        _make_traverse_row(EXTRA_NODE_1_ID, "SlackThread", "thread-2", 2, edge_relationship_type="discussed_in"),
    ]
    traverse_result = MagicMock()
    traverse_result.fetchall.return_value = traverse_rows

    # Edges between all nodes
    edges = [
        _mock_edge(ROOT_NODE_ID, PERSON_NODE_1_ID, "assigned_to"),
        _mock_edge(ROOT_NODE_ID, PERSON_NODE_2_ID, "mentioned_by"),
        _mock_edge(PERSON_NODE_1_ID, SLACK_NODE_ID, "discussed_in"),
        _mock_edge(PERSON_NODE_2_ID, EXTRA_NODE_1_ID, "discussed_in"),
    ]
    edge_result = MagicMock()
    edge_result.scalars.return_value.all.return_value = edges

    mock_session.execute.side_effect = [
        membership,
        ticket_result,
        graph_node_result,
        traverse_result,
        edge_result,
    ]

    response = client.get("/api/graph/ENG-123?limit=2", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["truncated"] is True
    assert data["total_available"] == 5
    # limit=2 caps at 2 nodes total
    assert len(data["nodes"]) == 2
    assert data["node_count"] == 2

    # Edges should only reference nodes present in the response
    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids


def test_get_graph_neighborhood_query_params(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """GET /api/graph/ENG-123?depth=1&limit=100 passes params to traverse_graph."""
    membership = _mock_membership()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = _mock_ticket("ENG-123")

    graph_node = _mock_graph_node(ROOT_NODE_ID)
    graph_node_result = MagicMock()
    graph_node_result.scalar_one_or_none.return_value = graph_node

    # Only root + 1 neighbor at depth 1
    traverse_rows = [
        _make_traverse_row(ROOT_NODE_ID, "Ticket", "ENG-123", 0),
        _make_traverse_row(PERSON_NODE_1_ID, "Person", "Alice", 1, edge_relationship_type="assigned_to"),
    ]
    traverse_result = MagicMock()
    traverse_result.fetchall.return_value = traverse_rows

    edges = [
        _mock_edge(ROOT_NODE_ID, PERSON_NODE_1_ID, "assigned_to"),
    ]
    edge_result = MagicMock()
    edge_result.scalars.return_value.all.return_value = edges

    mock_session.execute.side_effect = [
        membership,
        ticket_result,
        graph_node_result,
        traverse_result,
        edge_result,
    ]

    response = client.get(
        "/api/graph/ENG-123?depth=1&limit=100", headers=valid_auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert data["depth"] == 1
    assert data["node_count"] == 2

    # Verify traverse_graph was called with max_depth=1
    # The 4th execute call is traverse_graph (index 3)
    traverse_call = mock_session.execute.call_args_list[3]
    # call_args_list[n] is call(positional_args...) -- the params dict is the 2nd positional arg
    call_args = traverse_call[0]  # positional args tuple
    params = call_args[1] if len(call_args) > 1 else {}
    assert params.get("max_depth") == 1


def test_get_graph_neighborhood_deduplication(
    client: TestClient,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Same node reachable via two paths appears once with minimum depth."""
    membership = _mock_membership()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = _mock_ticket("ENG-123")

    graph_node = _mock_graph_node(ROOT_NODE_ID)
    graph_node_result = MagicMock()
    graph_node_result.scalar_one_or_none.return_value = graph_node

    # PERSON_NODE_1_ID appears at depth=1 and depth=2 (two different paths)
    traverse_rows = [
        _make_traverse_row(ROOT_NODE_ID, "Ticket", "ENG-123", 0),
        _make_traverse_row(PERSON_NODE_1_ID, "Person", "Alice", 1, edge_relationship_type="assigned_to"),
        _make_traverse_row(PERSON_NODE_2_ID, "Person", "Bob", 1, edge_relationship_type="mentioned_by"),
        _make_traverse_row(PERSON_NODE_1_ID, "Person", "Alice", 2, edge_relationship_type="collaborated_with"),
    ]
    traverse_result = MagicMock()
    traverse_result.fetchall.return_value = traverse_rows

    edges = [
        _mock_edge(ROOT_NODE_ID, PERSON_NODE_1_ID, "assigned_to"),
        _mock_edge(ROOT_NODE_ID, PERSON_NODE_2_ID, "mentioned_by"),
        _mock_edge(PERSON_NODE_2_ID, PERSON_NODE_1_ID, "collaborated_with"),
    ]
    edge_result = MagicMock()
    edge_result.scalars.return_value.all.return_value = edges

    mock_session.execute.side_effect = [
        membership,
        ticket_result,
        graph_node_result,
        traverse_result,
        edge_result,
    ]

    response = client.get("/api/graph/ENG-123", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()

    # PERSON_NODE_1_ID should appear only once
    alice_nodes = [n for n in data["nodes"] if n["name"] == "Alice"]
    assert len(alice_nodes) == 1

    # With minimum depth (1, not 2)
    assert alice_nodes[0]["depth"] == 1

    # Total nodes: 3 (root + Alice + Bob), not 4
    assert data["node_count"] == 3
