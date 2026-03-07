"""Tests for graph section in synthesis prompt.

Covers:
- GRAPH-SECTION: Graph connections formatted as separate section in synthesis prompt
- DECISION-FMT: Decision nodes render with [DECISION] highlighting format
- E2E-MERGE: generate_context_page includes both Related Content and Graph Connections
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _make_linked_item(
    *,
    source_type: str = "slack_message",
    title: str = "Test item",
    snippet: str = "Test snippet",
    relevance_score: float = 0.5,
    signals: list[str] | None = None,
) -> MagicMock:
    """Create a mock LinkedItem."""
    item = MagicMock()
    item.source_type = source_type
    item.source_id = uuid4()
    item.title = title
    item.snippet = snippet
    item.relevance_score = relevance_score
    item.signals = signals or ["explicit_link"]
    return item


@pytest.mark.asyncio
async def test_format_graph_section() -> None:
    """Given 3 LinkedItems with graph signals (one Decision, one SlackThread,
    one Person), _format_graph_section() returns a string containing
    '### Graph Connections' header, the decision item formatted with
    '[DECISION]' prefix, path strings, and entity types."""
    from src.services.synthesis import _format_graph_section

    items = [
        _make_linked_item(
            source_type="Decision",
            title="Use PostgreSQL for graph",
            snippet="[DECISION] Use PostgreSQL | By: Alice | In: Slack | Affects: CON-16 | Confidence: 0.9",
            relevance_score=0.48,
            signals=["graph:Ticket->decided_in->Decision"],
        ),
        _make_linked_item(
            source_type="slack_message",
            title="Discussion about graph",
            snippet="We should use...",
            relevance_score=0.48,
            signals=["graph:Ticket->discussed_in->SlackThread"],
        ),
        _make_linked_item(
            source_type="Person",
            title="Alice",
            snippet="Graph node: Alice (engineer)",
            relevance_score=0.3,
            signals=["graph:Ticket->assigned_to->Person"],
        ),
    ]

    result = _format_graph_section(items)

    assert "### Graph Connections" in result
    assert "[DECISION]" in result
    assert "graph:Ticket->discussed_in->SlackThread" in result


@pytest.mark.asyncio
async def test_decision_node_format() -> None:
    """Decision nodes should render with special highlighting:
    [DECISION] description | By: person | In: source | Affects: tickets | Confidence: X.X"""
    from src.services.synthesis import _format_decision_node

    result = _format_decision_node(
        "Use PostgreSQL for graph",
        {
            "person_name": "Alice",
            "source_type": "Slack",
            "ticket_refs": ["CON-16", "CON-17"],
            "confidence": 0.9,
        },
    )

    assert result == "[DECISION] Use PostgreSQL for graph | By: Alice | In: Slack | Affects: CON-16, CON-17 | Confidence: 0.9"


@pytest.mark.asyncio
async def test_generate_includes_graph() -> None:
    """Given a mocked find_related_content() returning items with graph
    signals, generate_context_page() produces a prompt that includes
    both '### Related Content' and '### Graph Connections' sections."""
    mock_session = AsyncMock()

    # Mock ticket
    ticket = MagicMock()
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = "CON-16"
    ticket.title = "Implement graph retrieval"
    ticket.description = "Add graph-enhanced retrieval to linking engine."
    ticket.status = "In Progress"
    ticket.assignee_name = "Alice"
    ticket.priority = 2
    ticket.labels = ["feature"]

    mock_ticket_result = MagicMock()
    mock_ticket_result.scalar_one_or_none.return_value = ticket

    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_ticket_result,
        mock_existing_result,
    ]

    # Create linked items: mix of non-graph and graph items
    non_graph_item = _make_linked_item(
        source_type="slack_message",
        title="Slack by Alice in #dev",
        snippet="We discussed the graph approach",
        relevance_score=1.0,
        signals=["explicit_reference"],
    )

    graph_item = _make_linked_item(
        source_type="Decision",
        title="Use PostgreSQL for graph",
        snippet="[DECISION] Use PostgreSQL | By: Alice | In: Slack | Affects: CON-16 | Confidence: 0.9",
        relevance_score=0.48,
        signals=["graph:Ticket->decided_in->Decision"],
    )

    mock_linking_result = MagicMock()
    mock_linking_result.items = [non_graph_item, graph_item]

    mock_llm_response = MagicMock()
    mock_llm_response.text = "# Context page content"
    mock_llm_response.model = "gemini-3-flash-preview"
    mock_llm_response.total_tokens = 1500

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_llm_response)

    with (
        patch(
            "src.services.synthesis.find_related_content",
            new_callable=AsyncMock,
            return_value=mock_linking_result,
        ),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page

        await generate_context_page(mock_session, WORKSPACE_ID, "CON-16")

    # Check the prompt passed to LLM contains both sections
    call_kwargs = mock_llm.generate.call_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "### Related Content" in prompt
    assert "### Graph Connections" in prompt
