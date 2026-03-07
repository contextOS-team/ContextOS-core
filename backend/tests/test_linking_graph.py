"""Tests for graph signal in the linking engine.

Covers:
- GRAPH-SIGNAL: Graph traversal returns LinkedItems with provenance paths
- GRAPH-FALLBACK: Missing graph node returns empty dict silently
- GRAPH-ERROR: Database errors return empty dict with warning logged
- DEPTH-DECAY: Depth-1 scores higher than depth-2 via exponential decay
- SAME-AS: same_as edges followed without counting as traversal hop
- MERGE-3WAY: 3-way merge of explicit + hybrid + graph with additive scoring
- TOKEN-BUDGET: Token budget trimming enforces limit
- TOKEN-DIVERSITY: Token budget guarantees signal diversity
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
    same_as_node_id = uuid4()
    pr_source_id = uuid4()
    pr_node_id = uuid4()
    slack_node_id = uuid4()

    row_slack = _make_traverse_row(
        node_id=slack_node_id,
        entity_type="SlackThread",
        edge_relationship_type="discussed_in",
        depth=1,
        path=[start_node_id, slack_node_id],
        source_type="slack_message",
        source_id=uuid4(),
    )
    row_same_as = _make_traverse_row(
        node_id=same_as_node_id,
        entity_type="Ticket",
        edge_relationship_type="same_as",
        depth=1,
        path=[start_node_id, same_as_node_id],
        source_type="linear_ticket",
        source_id=same_as_source_id,
    )
    row_via_same_as = _make_traverse_row(
        node_id=pr_node_id,
        entity_type="PR",
        name="PR through same_as",
        edge_relationship_type="implements",
        depth=2,
        path=[start_node_id, same_as_node_id, pr_node_id],
        source_type="github_pull_request",
        source_id=pr_source_id,
    )

    mock_traverse_result = MagicMock()
    mock_traverse_result.fetchall.return_value = [row_slack, row_same_as, row_via_same_as]

    # Mock bulk lookups (same_as node is skipped, so only slack + PR lookups)
    mock_slack_obj = MagicMock()
    mock_slack_obj.id = row_slack.source_id
    mock_slack_obj.text = "Thread"
    mock_slack_obj.user_name = "u"
    mock_slack_obj.channel_name = "c"
    mock_b1 = MagicMock()
    mock_b1.scalars.return_value.all.return_value = [mock_slack_obj]

    mock_pr_obj = MagicMock()
    mock_pr_obj.id = pr_source_id
    mock_pr_obj.number = 50
    mock_pr_obj.title = "PR via alias"
    mock_pr_obj.description = "desc"
    mock_b2 = MagicMock()
    mock_b2.scalars.return_value.all.return_value = [mock_pr_obj]

    mock_session.execute.side_effect = [
        mock_node_result,
        mock_traverse_result,
        mock_b1,
        mock_b2,
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


# ---------------------------------------------------------------------------
# 3-way merge and token budget tests (Plan 02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_signal_merge() -> None:
    """Given items from all 3 signals where one item appears in both explicit
    and graph, find_related_content() returns the item with combined score
    (additive) and both signals in its signals list. Graph-only items are
    included. Result count reflects merged items."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    shared_id = uuid4()  # Appears in both explicit and graph

    # Explicit: one slack message (shared_id)
    explicit_items = {
        ("slack_message", shared_id): MagicMock(
            source_type="slack_message",
            source_id=shared_id,
            title="Slack about auth",
            snippet="We need to fix auth",
            relevance_score=1.0,
            signals=["explicit_reference"],
        ),
    }

    # Hybrid: one PR (unique)
    hybrid_pr_id = uuid4()
    hybrid_items = {
        ("github_pull_request", hybrid_pr_id): MagicMock(
            source_type="github_pull_request",
            source_id=hybrid_pr_id,
            title="PR #10: Hybrid match",
            snippet="Hybrid matched PR",
            relevance_score=0.5,
            signals=["hybrid_search"],
        ),
    }

    # Graph: shared_id (also found via graph) + one graph-only Decision
    graph_decision_id = uuid4()
    graph_items = {
        ("slack_message", shared_id): MagicMock(
            source_type="slack_message",
            source_id=shared_id,
            title="Slack about auth",
            snippet="We need to fix auth",
            relevance_score=0.48,
            signals=["graph:SlackThread(discussed_in,d=1)"],
        ),
        ("decision", graph_decision_id): MagicMock(
            source_type="decision",
            source_id=graph_decision_id,
            title="Use PostgreSQL",
            snippet="[DECISION] Use PostgreSQL | By: Alice | In: Slack | Affects: CON-16 | Confidence: 0.9",
            relevance_score=0.48,
            signals=["graph:Decision(decided_in,d=1)"],
        ),
    }

    with (
        patch("src.services.linking._find_explicit_refs", new_callable=AsyncMock, return_value=explicit_items),
        patch("src.services.linking._find_hybrid_matches", new_callable=AsyncMock, return_value=hybrid_items),
        patch("src.services.linking._find_graph_results", new_callable=AsyncMock, return_value=graph_items),
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(mock_session, WORKSPACE_ID, ticket)

    # 3 unique keys: shared slack, hybrid PR, graph-only Decision
    assert len(result.items) == 3

    # The shared item should have additive score: 1.0 + 0.48 = 1.48
    shared_item = [i for i in result.items if i.source_id == shared_id][0]
    assert abs(shared_item.relevance_score - 1.48) < 0.01
    assert len(shared_item.signals) >= 2  # explicit_reference + graph:...

    # Graph-only decision should be present
    decision_items = [i for i in result.items if i.source_type == "decision"]
    assert len(decision_items) == 1


@pytest.mark.asyncio
async def test_token_budget_basic() -> None:
    """Given 10 LinkedItems totaling ~4000 tokens, _apply_token_budget()
    with budget=500 returns a subset fitting within 500 tokens."""
    from src.services.linking import LinkedItem, _apply_token_budget

    items = []
    for i in range(10):
        items.append(
            LinkedItem(
                source_type="slack_message",
                source_id=uuid4(),
                title=f"Message {i}",
                snippet="x" * 400,  # ~400 chars => ~112 estimated tokens each
                relevance_score=1.0 - i * 0.05,
                signals=["explicit_link"],
            )
        )

    result = _apply_token_budget(items, budget_tokens=500)

    assert len(result) < len(items)
    # Estimate total tokens in result
    total = sum(
        (len(it.title) + len(it.snippet) + sum(len(s) for s in it.signals) + 50) // 4
        for it in result
    )
    assert total <= 500


@pytest.mark.asyncio
async def test_token_budget_diversity() -> None:
    """Given items with 3 different primary signal types (explicit, hybrid,
    graph), _apply_token_budget() guarantees at least 1 item from each signal
    type even if a lower-scored item from a minority signal is included over
    a higher-scored item from a majority signal."""
    from src.services.linking import LinkedItem, _apply_token_budget

    items = [
        # 3 explicit items (high scores)
        LinkedItem(
            source_type="slack_message",
            source_id=uuid4(),
            title="Explicit 1",
            snippet="Short snippet",
            relevance_score=1.0,
            signals=["explicit_link"],
        ),
        LinkedItem(
            source_type="slack_message",
            source_id=uuid4(),
            title="Explicit 2",
            snippet="Short snippet",
            relevance_score=0.9,
            signals=["explicit_link"],
        ),
        LinkedItem(
            source_type="slack_message",
            source_id=uuid4(),
            title="Explicit 3",
            snippet="Short snippet",
            relevance_score=0.85,
            signals=["explicit_link"],
        ),
        # 1 hybrid item (medium score)
        LinkedItem(
            source_type="github_pull_request",
            source_id=uuid4(),
            title="Hybrid PR",
            snippet="Short snippet",
            relevance_score=0.5,
            signals=["hybrid_search"],
        ),
        # 1 graph item (lowest score)
        LinkedItem(
            source_type="decision",
            source_id=uuid4(),
            title="Graph Decision",
            snippet="Short snippet",
            relevance_score=0.3,
            signals=["graph:Decision(decided_in,d=1)"],
        ),
    ]

    # Budget allowing roughly 3 items (each ~30 tokens, budget=100)
    result = _apply_token_budget(items, budget_tokens=100)

    # Should have at least 1 from each signal type
    signal_types = set()
    for it in result:
        for s in it.signals:
            if s.startswith("graph:"):
                signal_types.add("graph")
            elif s in ("explicit_link", "explicit_reference"):
                signal_types.add("explicit")
            elif s == "hybrid_search":
                signal_types.add("hybrid")

    assert "explicit" in signal_types, "Missing explicit signal in budget result"
    assert "hybrid" in signal_types, "Missing hybrid signal in budget result"
    assert "graph" in signal_types, "Missing graph signal in budget result"
