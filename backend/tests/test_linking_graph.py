"""Tests for graph signal in the linking engine.

Covers:
- GRAPH-SIGNAL: Graph traversal returns LinkedItems with provenance paths
- GRAPH-FALLBACK: Missing graph node returns empty dict silently
- GRAPH-ERROR: Database errors return empty dict with warning logged
- DEPTH-DECAY: Depth-1 scores higher than depth-2 via exponential decay
- SAME-AS: same_as edges followed without counting as traversal hop
"""

import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _make_ticket(
    identifier: str = "ENG-42",
    title: str = "Fix auth flow",
    description: str = "The OAuth flow is broken for GitHub.",
) -> MagicMock:
    """Create a mock LinearTicket for graph tests."""
    ticket = MagicMock()
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = identifier
    ticket.title = title
    ticket.description = description
    return ticket


def _make_traverse_row(
    *,
    node_id: UUID | None = None,
    entity_type: str = "SlackThread",
    name: str = "Thread about auth",
    properties: dict | None = None,
    edge_relationship_type: str = "discussed_in",
    depth: int = 1,
    path: list[UUID] | None = None,
    source_type: str | None = "slack_message",
    source_id: UUID | None = None,
) -> MagicMock:
    """Create a mock row from traverse_graph() SQL function."""
    row = MagicMock()
    row.node_id = node_id or uuid4()
    row.entity_type = entity_type
    row.name = name
    row.properties = properties or {}
    row.edge_relationship_type = edge_relationship_type
    row.depth = depth
    row.path = path or [uuid4(), row.node_id]
    row.source_type = source_type
    row.source_id = source_id or uuid4()
    return row


def _make_graph_node(
    *, node_id: UUID | None = None, fingerprint: str = "abc123"
) -> MagicMock:
    """Create a mock GraphNode model object."""
    node = MagicMock()
    node.id = node_id or uuid4()
    node.fingerprint = fingerprint
    return node


@pytest.mark.asyncio
async def test_find_graph_results_basic() -> None:
    """Given a ticket with a graph node and neighbors at depth 1 and 2,
    returns LinkedItems with correct provenance paths and depth-1 scoring
    higher than depth-2."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    start_node_id = uuid4()
    graph_node = _make_graph_node(node_id=start_node_id)

    # Mock GraphNode query (finding the ticket's graph node by fingerprint)
    mock_node_result = MagicMock()
    mock_node_result.scalar_one_or_none.return_value = graph_node

    # Create traverse_graph results (depth-1 and depth-2 neighbors)
    depth1_node_id = uuid4()
    depth2_node_id = uuid4()
    depth1_source_id = uuid4()
    depth2_source_id = uuid4()

    row_d1 = _make_traverse_row(
        node_id=depth1_node_id,
        entity_type="SlackThread",
        name="Discussion about auth",
        edge_relationship_type="discussed_in",
        depth=1,
        path=[start_node_id, depth1_node_id],
        source_type="slack_message",
        source_id=depth1_source_id,
    )
    row_d2 = _make_traverse_row(
        node_id=depth2_node_id,
        entity_type="PR",
        name="PR #99: Fix OAuth",
        edge_relationship_type="implements",
        depth=2,
        path=[start_node_id, depth1_node_id, depth2_node_id],
        source_type="github_pull_request",
        source_id=depth2_source_id,
    )

    mock_traverse_result = MagicMock()
    mock_traverse_result.fetchall.return_value = [row_d1, row_d2]

    # Mock bulk lookup summaries
    mock_bulk_result = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = depth1_source_id
    mock_msg.text = "We talked about the auth flow issue"
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"
    mock_pr = MagicMock()
    mock_pr.id = depth2_source_id
    mock_pr.number = 99
    mock_pr.title = "Fix OAuth"
    mock_pr.description = "OAuth fix PR"
    mock_bulk_result.scalars.return_value.all.return_value = [mock_msg]

    mock_bulk_result2 = MagicMock()
    mock_bulk_result2.scalars.return_value.all.return_value = [mock_pr]

    mock_session.execute.side_effect = [
        mock_node_result,      # GraphNode fingerprint lookup
        mock_traverse_result,  # traverse_graph() SQL
        mock_bulk_result,      # bulk lookup for slack_message
        mock_bulk_result2,     # bulk lookup for github_pull_request
    ]

    with patch("src.services.linking.compute_fingerprint", return_value="fake_fp"):
        from src.services.linking import _find_graph_results

        items = await _find_graph_results(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 2

    # Check that depth-1 item scores higher than depth-2
    scores = {item.source_type: item.relevance_score for item in items.values()}
    assert scores["slack_message"] > scores["github_pull_request"]

    # Check provenance paths contain "graph:" prefix
    for item in items.values():
        assert any(s.startswith("graph:") for s in item.signals)


@pytest.mark.asyncio
async def test_find_graph_results_no_node() -> None:
    """Given a ticket with no graph node (fingerprint not found),
    returns empty dict without error."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    # GraphNode query returns None
    mock_node_result = MagicMock()
    mock_node_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_node_result]

    with patch("src.services.linking.compute_fingerprint", return_value="missing_fp"):
        from src.services.linking import _find_graph_results

        items = await _find_graph_results(mock_session, WORKSPACE_ID, ticket)

    assert items == {}


@pytest.mark.asyncio
async def test_find_graph_results_error_silent() -> None:
    """Given a database error during traversal, returns empty dict
    and logs a warning."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    # First call (GraphNode query) raises an exception
    mock_session.execute.side_effect = Exception("DB connection lost")

    with patch("src.services.linking.compute_fingerprint", return_value="fp"):
        from src.services.linking import _find_graph_results

        with patch("src.services.linking.logger") as mock_logger:
            items = await _find_graph_results(mock_session, WORKSPACE_ID, ticket)

            assert items == {}
            mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_depth_decay_scoring() -> None:
    """Depth-1 result has score WEIGHT_GRAPH * DEPTH_DECAY^1 = 0.48,
    depth-2 has WEIGHT_GRAPH * DEPTH_DECAY^2 = 0.288."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    start_node_id = uuid4()
    graph_node = _make_graph_node(node_id=start_node_id)

    mock_node_result = MagicMock()
    mock_node_result.scalar_one_or_none.return_value = graph_node

    d1_source_id = uuid4()
    d2_source_id = uuid4()

    row_d1 = _make_traverse_row(
        entity_type="SlackThread",
        edge_relationship_type="discussed_in",
        depth=1,
        source_type="slack_message",
        source_id=d1_source_id,
    )
    row_d2 = _make_traverse_row(
        entity_type="NotionPage",
        edge_relationship_type="references",
        depth=2,
        source_type="notion_page",
        source_id=d2_source_id,
    )

    mock_traverse_result = MagicMock()
    mock_traverse_result.fetchall.return_value = [row_d1, row_d2]

    # Mock bulk lookups
    mock_slack = MagicMock()
    mock_slack.id = d1_source_id
    mock_slack.text = "Discussion"
    mock_slack.user_name = "bob"
    mock_slack.channel_name = "eng"
    mock_bulk1 = MagicMock()
    mock_bulk1.scalars.return_value.all.return_value = [mock_slack]

    mock_notion = MagicMock()
    mock_notion.id = d2_source_id
    mock_notion.title = "Design Doc"
    mock_notion.content = "Some content"
    mock_bulk2 = MagicMock()
    mock_bulk2.scalars.return_value.all.return_value = [mock_notion]

    mock_session.execute.side_effect = [
        mock_node_result,
        mock_traverse_result,
        mock_bulk1,
        mock_bulk2,
    ]

    with patch("src.services.linking.compute_fingerprint", return_value="fp"):
        from src.services.linking import _find_graph_results, WEIGHT_GRAPH, DEPTH_DECAY

        items = await _find_graph_results(mock_session, WORKSPACE_ID, ticket)

    expected_d1 = WEIGHT_GRAPH * (DEPTH_DECAY ** 1)  # 0.48
    expected_d2 = WEIGHT_GRAPH * (DEPTH_DECAY ** 2)  # 0.288

    scores = list(items.values())
    d1_item = [i for i in scores if i.source_type == "slack_message"][0]
    d2_item = [i for i in scores if i.source_type == "notion_page"][0]

    assert abs(d1_item.relevance_score - expected_d1) < 0.001
    assert abs(d2_item.relevance_score - expected_d2) < 0.001


@pytest.mark.asyncio
async def test_same_as_transparent() -> None:
    """When traversal includes a same_as edge, the node reached via same_as
    is treated as if at the same depth (depth not incremented for same_as hop)."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    start_node_id = uuid4()
    graph_node = _make_graph_node(node_id=start_node_id)

    mock_node_result = MagicMock()
    mock_node_result.scalar_one_or_none.return_value = graph_node

    # Traversal goes: Ticket --(discussed_in)--> SlackThread (depth=1)
    #                 Ticket --(same_as)--> AliasTicket (depth=1, same_as)
    #                 AliasTicket --(implements)--> PR (depth=2, but effective=1 because same_as)
    same_as_source_id = uuid4()
    pr_source_id = uuid4()

    row_slack = _make_traverse_row(
        entity_type="SlackThread",
        edge_relationship_type="discussed_in",
        depth=1,
        source_type="slack_message",
        source_id=uuid4(),
    )
    row_same_as = _make_traverse_row(
        entity_type="Ticket",
        edge_relationship_type="same_as",
        depth=1,
        source_type="linear_ticket",
        source_id=same_as_source_id,
    )
    row_via_same_as = _make_traverse_row(
        entity_type="PR",
        name="PR through same_as",
        edge_relationship_type="implements",
        depth=2,
        source_type="github_pull_request",
        source_id=pr_source_id,
    )

    mock_traverse_result = MagicMock()
    mock_traverse_result.fetchall.return_value = [row_slack, row_same_as, row_via_same_as]

    # Mock bulk lookups
    mock_slack_obj = MagicMock()
    mock_slack_obj.id = row_slack.source_id
    mock_slack_obj.text = "Thread"
    mock_slack_obj.user_name = "u"
    mock_slack_obj.channel_name = "c"
    mock_b1 = MagicMock()
    mock_b1.scalars.return_value.all.return_value = [mock_slack_obj]

    mock_ticket_obj = MagicMock()
    mock_ticket_obj.id = same_as_source_id
    mock_ticket_obj.title = "Alias"
    mock_ticket_obj.description = "desc"
    mock_b2 = MagicMock()
    mock_b2.scalars.return_value.all.return_value = [mock_ticket_obj]

    mock_pr_obj = MagicMock()
    mock_pr_obj.id = pr_source_id
    mock_pr_obj.number = 50
    mock_pr_obj.title = "PR via alias"
    mock_pr_obj.description = "desc"
    mock_b3 = MagicMock()
    mock_b3.scalars.return_value.all.return_value = [mock_pr_obj]

    mock_session.execute.side_effect = [
        mock_node_result,
        mock_traverse_result,
        mock_b1,
        mock_b2,
        mock_b3,
    ]

    with patch("src.services.linking.compute_fingerprint", return_value="fp"):
        from src.services.linking import _find_graph_results, WEIGHT_GRAPH, DEPTH_DECAY

        items = await _find_graph_results(mock_session, WORKSPACE_ID, ticket)

    # The PR reached via same_as should have effective_depth=1 (not 2)
    # So its score should be WEIGHT_GRAPH * DEPTH_DECAY^1 = 0.48
    pr_items = [i for i in items.values() if i.source_type == "github_pull_request"]
    assert len(pr_items) == 1
    expected_score = WEIGHT_GRAPH * (DEPTH_DECAY ** 1)  # 0.48, not 0.288
    assert abs(pr_items[0].relevance_score - expected_score) < 0.001
