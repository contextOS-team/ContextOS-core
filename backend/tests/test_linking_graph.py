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

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def test_provider_freshness_matrix_covers_source_families() -> None:
    from datetime import UTC, datetime, timedelta

    from src.services.graph_rag_freshness import calculate_freshness_state
    from src.services.graph_rag_types import FreshnessState, VerificationState

    now = datetime(2026, 5, 26, tzinfo=UTC)

    assert (
        calculate_freshness_state(
            "slack_message",
            {"slack_created_at": now - timedelta(days=2)},
            now=now,
        ).freshness_state
        == FreshnessState.FRESH
    )
    assert (
        calculate_freshness_state(
            "notion_page",
            {"notion_updated_at": now - timedelta(days=500)},
            now=now,
        ).freshness_state
        == FreshnessState.STALE
    )
    assert (
        calculate_freshness_state(
            "github_pull_request",
            {"github_merged_at": now - timedelta(days=3)},
            now=now,
        ).freshness_state
        == FreshnessState.FRESH
    )
    assert (
        calculate_freshness_state(
            "linear_ticket",
            {"linear_updated_at": now - timedelta(days=20)},
            now=now,
        ).freshness_state
        == FreshnessState.FRESH
    )
    assert (
        calculate_freshness_state(
            "meeting_transcript",
            {"meeting_date": now - timedelta(days=120)},
            now=now,
        ).freshness_state
        == FreshnessState.UNKNOWN
    )

    generated = calculate_freshness_state(
        "context_page",
        {"generated_at": now - timedelta(days=1)},
        verification_state=VerificationState.GENERATED_CONTEXT,
        now=now,
    )
    assert generated.source_originality == "generated_context"
    assert generated.freshness_state == FreshnessState.FRESH

    unknown = calculate_freshness_state("telegram_message", {}, now=now)
    assert unknown.freshness_state == FreshnessState.UNKNOWN

    old_confirmed = calculate_freshness_state(
        "decision",
        {"source_timestamp": now - timedelta(days=400)},
        verification_state=VerificationState.CONFIRMED_DECISION,
        now=now,
    )
    assert old_confirmed.freshness_state is not FreshnessState.FRESH


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

    # Mock source_id lookup for source-backed graph nodes
    mock_source_lookup = MagicMock()
    mock_source_lookup.fetchall.return_value = [
        (depth1_node_id, depth1_source_id),
        (depth2_node_id, depth2_source_id),
    ]

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

    # Phase 1 (embedding metadata lookup) returns no results → falls back to source tables
    mock_emb_result = MagicMock()
    mock_emb_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        mock_node_result,      # GraphNode fingerprint lookup
        mock_traverse_result,  # traverse_graph() SQL
        mock_source_lookup,    # GraphNode.source_id bulk lookup
        mock_emb_result,       # Embedding metadata Phase 1 (privacy-aware lookup)
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
        assert item.features.graph_depth in (1, 2)


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

    # Mock source_id lookup for source-backed graph nodes
    mock_source_lookup = MagicMock()
    mock_source_lookup.fetchall.return_value = [
        (row_d1.node_id, d1_source_id),
        (row_d2.node_id, d2_source_id),
    ]

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

    # Phase 1 (embedding metadata lookup) returns no results → falls back to source tables
    mock_emb_result = MagicMock()
    mock_emb_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        mock_node_result,
        mock_traverse_result,
        mock_source_lookup,
        mock_emb_result,       # Embedding metadata Phase 1 (privacy-aware lookup)
        mock_bulk1,
        mock_bulk2,
    ]

    with patch("src.services.linking.compute_fingerprint", return_value="fp"):
        from src.services.linking import DEPTH_DECAY, WEIGHT_GRAPH, _find_graph_results

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

    # Mock source_id lookup for source-backed graph nodes
    mock_source_lookup = MagicMock()
    mock_source_lookup.fetchall.return_value = [
        (slack_node_id, row_slack.source_id),
        (pr_node_id, pr_source_id),
    ]

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

    # Phase 1 (embedding metadata lookup) returns no results → falls back to source tables
    mock_emb_result = MagicMock()
    mock_emb_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        mock_node_result,
        mock_traverse_result,
        mock_source_lookup,
        mock_emb_result,       # Embedding metadata Phase 1 (privacy-aware lookup)
        mock_b1,
        mock_b2,
    ]

    with patch("src.services.linking.compute_fingerprint", return_value="fp"):
        from src.services.linking import DEPTH_DECAY, WEIGHT_GRAPH, _find_graph_results

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
    and graph, find_related_content() returns the item with merged signals and
    the highest RRF score, plus all unique items. Graph-only items are included.
    Result count reflects merged items."""
    from src.services.linking import LinkedItem

    mock_session = AsyncMock()
    ticket = _make_ticket()

    shared_id = uuid4()  # Appears in both explicit and graph

    # Use real LinkedItem objects so signals.extend() works correctly
    # Explicit: one slack message (shared_id)
    explicit_items = {
        ("slack_message", shared_id): LinkedItem(
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
        ("github_pull_request", hybrid_pr_id): LinkedItem(
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
        ("slack_message", shared_id): LinkedItem(
            source_type="slack_message",
            source_id=shared_id,
            title="Slack about auth",
            snippet="We need to fix auth",
            relevance_score=0.48,
            signals=["graph:SlackThread(discussed_in,d=1)"],
        ),
        ("decision", graph_decision_id): LinkedItem(
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
        patch("src.services.linking._fetch_communities_for_ticket", new_callable=AsyncMock, return_value=[]),
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(mock_session, WORKSPACE_ID, ticket)

    # 3 unique keys: shared slack, hybrid PR, graph-only Decision
    assert len(result.items) == 3

    # The shared item appears in both explicit and graph signals, so it gets the
    # highest RRF score (appears in 2 ranked lists) and is normalised to 1.0.
    shared_item = [i for i in result.items if i.source_id == shared_id][0]
    assert shared_item.relevance_score > 0.0
    assert len(shared_item.signals) >= 2  # explicit_reference + graph:...

    # Graph-only decision should be present
    decision_items = [i for i in result.items if i.source_type == "decision"]
    assert len(decision_items) == 1
    assert all(item.targets for item in result.items)


@pytest.mark.asyncio
async def test_find_related_content_filters_by_retrieval_target() -> None:
    """decision_receipts target should route to graph decisions only."""
    from src.services.graph_rag_types import RetrievalTarget
    from src.services.linking import LinkedItem

    mock_session = AsyncMock()
    ticket = _make_ticket()
    decision_id = uuid4()

    graph_items = {
        ("decision", decision_id): LinkedItem(
            source_type="decision",
            source_id=decision_id,
            title="Keep receipts bounded",
            snippet="[DECISION] Keep receipts bounded",
            relevance_score=0.8,
            signals=["graph:Decision(decided_in,d=1)"],
        ),
        ("slack_message", uuid4()): LinkedItem(
            source_type="slack_message",
            source_id=uuid4(),
            title="Source evidence",
            snippet="Slack source",
            relevance_score=0.7,
            signals=["graph:SlackThread(discussed_in,d=1)"],
        ),
    }

    with (
        patch(
            "src.services.linking._find_explicit_refs",
            new_callable=AsyncMock,
        ) as explicit,
        patch(
            "src.services.linking._find_hybrid_matches",
            new_callable=AsyncMock,
        ) as hybrid,
        patch(
            "src.services.linking._find_graph_results",
            new_callable=AsyncMock,
            return_value=graph_items,
        ),
        patch(
            "src.services.linking._fetch_communities_for_ticket",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(
            mock_session,
            WORKSPACE_ID,
            ticket,
            targets=[RetrievalTarget.DECISION_RECEIPTS],
        )

    explicit.assert_not_awaited()
    hybrid.assert_not_awaited()
    assert [item.source_type for item in result.items] == ["decision"]
    assert RetrievalTarget.DECISION_RECEIPTS in result.items[0].targets
    assert RetrievalTarget.SOURCE_EVIDENCE not in result.items[0].targets


def test_target_metadata_inference_covers_every_retrieval_target() -> None:
    from src.services.graph_rag_types import RetrievalTarget
    from src.services.linking import LinkedItem, _ensure_item_retrieval_metadata

    items = [
        LinkedItem(
            source_type="decision",
            source_id=uuid4(),
            title="Decision",
            snippet="[DECISION] Use receipts",
            relevance_score=1.0,
            signals=["graph:Decision(decided_in,d=1)"],
        ),
        LinkedItem(
            source_type="slack_message",
            source_id=uuid4(),
            title="Slack evidence",
            snippet="Source quote",
            relevance_score=1.0,
            signals=["explicit_reference"],
        ),
        LinkedItem(
            source_type="github_pull_request",
            source_id=uuid4(),
            title="Related PR",
            snippet="Related implementation",
            relevance_score=1.0,
            signals=["hybrid_search"],
        ),
    ]

    observed: set[RetrievalTarget] = set()
    for item in items:
        _ensure_item_retrieval_metadata(item)
        observed.update(item.targets)
        assert item.metadata["retrieval_targets"]

    assert observed == set(RetrievalTarget)


@pytest.mark.asyncio
async def test_find_related_content_rejects_invalid_targets() -> None:
    from src.services.linking import find_related_content

    mock_session = AsyncMock()
    ticket = _make_ticket()

    with pytest.raises(ValueError, match="cannot be empty"):
        await find_related_content(mock_session, WORKSPACE_ID, ticket, targets=[])

    with pytest.raises(ValueError, match="unsupported retrieval target"):
        await find_related_content(
            mock_session,
            WORKSPACE_ID,
            ticket,
            targets=["not-a-target"],  # type: ignore[list-item]
        )


@pytest.mark.asyncio
async def test_phase45_confirmed_decision_renders_source_backed_receipt() -> None:
    """Phase 45 promoted Decision properties should not degrade to Unknown."""
    from src.services.graph_rag_types import RetrievalTarget, VerificationState

    mock_session = AsyncMock()
    ticket = _make_ticket()
    graph_node = _make_graph_node()
    decision_id = uuid4()

    mock_node_result = MagicMock()
    mock_node_result.scalar_one_or_none.return_value = graph_node

    row_decision = _make_traverse_row(
        node_id=decision_id,
        entity_type="Decision",
        name="Keep generated context evidence bounded",
        properties={
            "person_name": "Daulet",
            "source_type": "slack_message",
            "source_link": "https://slack.example/archives/C1/p1",
            "source_quote": "We decided to keep generated context evidence bounded.",
            "affected_systems": ["context-pages"],
            "confidence": 0.91,
            "status": "confirmed",
        },
        edge_relationship_type="decided_in",
        depth=1,
        source_type=None,
    )
    mock_traverse_result = MagicMock()
    mock_traverse_result.fetchall.return_value = [row_decision]
    mock_session.execute.side_effect = [mock_node_result, mock_traverse_result]

    with patch("src.services.linking.compute_fingerprint", return_value="fp"):
        from src.services.linking import _find_graph_results

        items = await _find_graph_results(mock_session, WORKSPACE_ID, ticket)

    item = items[("decision", decision_id)]
    assert "By: Daulet" in item.snippet
    assert "In: slack_message" in item.snippet
    assert "Quote: We decided" in item.snippet
    assert item.url == "https://slack.example/archives/C1/p1"
    assert item.features.verification_state == VerificationState.CONFIRMED_DECISION
    assert RetrievalTarget.DECISION_RECEIPTS in item.targets
    assert RetrievalTarget.SOURCE_EVIDENCE in item.targets


@pytest.mark.asyncio
async def test_generated_context_decision_is_not_primary_source_evidence() -> None:
    from src.services.graph_rag_types import RetrievalTarget, VerificationState

    mock_session = AsyncMock()
    ticket = _make_ticket()
    graph_node = _make_graph_node()
    decision_id = uuid4()

    mock_node_result = MagicMock()
    mock_node_result.scalar_one_or_none.return_value = graph_node

    row_decision = _make_traverse_row(
        node_id=decision_id,
        entity_type="Decision",
        name="Generated summary says auth should change",
        properties={
            "source_type": "context_page",
            "status": "confirmed",
            "confidence": 0.5,
        },
        edge_relationship_type="summarized_in",
        depth=1,
        source_type=None,
    )
    mock_traverse_result = MagicMock()
    mock_traverse_result.fetchall.return_value = [row_decision]
    mock_session.execute.side_effect = [mock_node_result, mock_traverse_result]

    with patch("src.services.linking.compute_fingerprint", return_value="fp"):
        from src.services.linking import _find_graph_results

        items = await _find_graph_results(mock_session, WORKSPACE_ID, ticket)

    item = items[("decision", decision_id)]
    assert "In: generated_context" in item.snippet
    assert item.features.verification_state == VerificationState.GENERATED_CONTEXT
    assert RetrievalTarget.DECISION_RECEIPTS in item.targets
    assert RetrievalTarget.SOURCE_EVIDENCE not in item.targets


@pytest.mark.asyncio
async def test_confirmed_decision_drops_generated_context_duplicate() -> None:
    from src.services.graph_rag_types import (
        FreshnessState,
        RetrievalFeatures,
        RetrievalTarget,
        VerificationState,
    )
    from src.services.linking import LinkedItem

    mock_session = AsyncMock()
    ticket = _make_ticket()
    confirmed_id = uuid4()
    generated_id = uuid4()

    graph_items = {
        ("decision", confirmed_id): LinkedItem(
            source_type="decision",
            source_id=confirmed_id,
            title="Use source-path explanations",
            snippet="[DECISION] Use source-path explanations",
            relevance_score=0.5,
            signals=["graph:Decision(decided_in,d=1)"],
            targets=[RetrievalTarget.DECISION_RECEIPTS],
            features=RetrievalFeatures(
                freshness_state=FreshnessState.FRESH,
                verification_state=VerificationState.CONFIRMED_DECISION,
                source_originality="source_of_record",
            ),
        ),
        ("decision", generated_id): LinkedItem(
            source_type="decision",
            source_id=generated_id,
            title="Generated duplicate",
            snippet="[DECISION] Generated context repeats the same decision",
            relevance_score=1.0,
            signals=["graph:Decision(summarized_in,d=1)"],
            targets=[RetrievalTarget.DECISION_RECEIPTS],
            features=RetrievalFeatures(
                freshness_state=FreshnessState.FRESH,
                verification_state=VerificationState.GENERATED_CONTEXT,
                source_originality="generated_context",
            ),
        ),
    }

    with (
        patch("src.services.linking._find_graph_results", new_callable=AsyncMock, return_value=graph_items),
        patch("src.services.linking._fetch_communities_for_ticket", new_callable=AsyncMock, return_value=[]),
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(
            mock_session,
            WORKSPACE_ID,
            ticket,
            targets=[RetrievalTarget.DECISION_RECEIPTS],
        )

    assert [item.source_id for item in result.items] == [confirmed_id]
    assert result.items[0].why_selected
    assert result.dropped_items[0].source_id == generated_id
    assert (
        result.dropped_items[0].suppress_reason
        == "generated_context_not_primary_evidence"
    )


@pytest.mark.asyncio
async def test_stale_duplicate_is_dropped_with_reason() -> None:
    from src.services.graph_rag_types import (
        FreshnessState,
        RetrievalFeatures,
        RetrievalTarget,
        VerificationState,
    )
    from src.services.linking import LinkedItem

    mock_session = AsyncMock()
    ticket = _make_ticket()
    fresh_id = uuid4()
    stale_id = uuid4()

    explicit_items = {
        ("slack_message", fresh_id): LinkedItem(
            source_type="slack_message",
            source_id=fresh_id,
            title="Fresh source",
            snippet="Fresh source of record",
            relevance_score=0.7,
            signals=["explicit_reference"],
            targets=[RetrievalTarget.SOURCE_EVIDENCE],
            features=RetrievalFeatures(
                freshness_state=FreshnessState.FRESH,
                verification_state=VerificationState.SOURCE_EVIDENCE,
                source_originality="source_of_record",
            ),
        ),
        ("slack_message", stale_id): LinkedItem(
            source_type="slack_message",
            source_id=stale_id,
            title="Stale source",
            snippet="Old duplicate",
            relevance_score=1.0,
            signals=["explicit_reference"],
            targets=[RetrievalTarget.SOURCE_EVIDENCE],
            features=RetrievalFeatures(
                freshness_state=FreshnessState.STALE,
                verification_state=VerificationState.SOURCE_EVIDENCE,
                source_originality="source_of_record",
            ),
        ),
    }

    with (
        patch("src.services.linking._find_explicit_refs", new_callable=AsyncMock, return_value=explicit_items),
        patch("src.services.linking._find_hybrid_matches", new_callable=AsyncMock, return_value={}),
        patch("src.services.linking._find_graph_results", new_callable=AsyncMock, return_value={}),
        patch("src.services.linking._fetch_communities_for_ticket", new_callable=AsyncMock, return_value=[]),
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(
            mock_session,
            WORKSPACE_ID,
            ticket,
            targets=[RetrievalTarget.SOURCE_EVIDENCE],
        )

    assert [item.source_id for item in result.items] == [fresh_id]
    assert result.dropped_items[0].source_id == stale_id
    assert result.dropped_items[0].suppress_reason == "stale_duplicate"


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


class TestLinkingResultCommunities:
    """Verify LinkingResult exposes selected community contexts."""

    def test_community_context_dataclass_shape(self):
        from src.services.linking import CommunityContext
        cc = CommunityContext(
            community_id=1,
            label="Auth",
            summary="Owns auth.",
            person_count=2,
            ticket_count=3,
            member_count=5,
            top_member_names=["@alice", "@bob"],
            relevance_reason="assignee_primary",
        )
        assert cc.community_id == 1
        assert cc.relevance_reason == "assignee_primary"

    def test_select_communities_picks_assignee_primary_first(self):
        from src.services.linking import CommunityContext, _select_communities
        # 4 candidate communities, all valid; assignee_primary must be #1 in result.
        candidates = [
            CommunityContext(community_id=10, label="A", summary="a", person_count=2,
                             ticket_count=2, member_count=4, top_member_names=[],
                             relevance_reason="retrieved_member"),
            CommunityContext(community_id=20, label="B", summary="b", person_count=3,
                             ticket_count=3, member_count=6, top_member_names=[],
                             relevance_reason="assignee_primary"),
            CommunityContext(community_id=30, label="C", summary="c", person_count=2,
                             ticket_count=2, member_count=4, top_member_names=[],
                             relevance_reason="retrieved_member"),
            CommunityContext(community_id=40, label="D", summary="d", person_count=2,
                             ticket_count=2, member_count=4, top_member_names=[],
                             relevance_reason="retrieved_member"),
        ]
        chosen = _select_communities(candidates, max_communities=3)
        assert chosen[0].community_id == 20
        assert len(chosen) == 3

    def test_select_communities_caps_at_max(self):
        from src.services.linking import CommunityContext, _select_communities
        candidates = [
            CommunityContext(community_id=i, label=str(i), summary="s",
                             person_count=2, ticket_count=2, member_count=4,
                             top_member_names=[], relevance_reason="retrieved_member")
            for i in range(10)
        ]
        chosen = _select_communities(candidates, max_communities=3)
        assert len(chosen) == 3

    def test_select_communities_handles_empty_list(self):
        from src.services.linking import _select_communities
        assert _select_communities([], max_communities=3) == []
