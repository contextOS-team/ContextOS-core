"""Tests for code_chunk integration in the linking engine.

Covers:
- _lookup_source_summary correctly formats code_chunk titles and snippets
- Code chunks appear in hybrid search results alongside other source types
- find_related_content merges code_chunk items into the final LinkingResult
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _make_ticket(
    identifier: str = "CON-16",
    title: str = "Implement context synthesis",
    description: str = "Build the AI context page generation pipeline.",
) -> MagicMock:
    """Create a mock LinearTicket."""
    ticket = MagicMock()
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = identifier
    ticket.title = title
    ticket.description = description
    return ticket


def _make_code_chunk(
    symbol_name: str = "generate_context_page",
    symbol_type: str = "function",
    repo_full_name: str = "acme/backend",
    file_path: str = "src/services/synthesis.py",
    content: str = "async def generate_context_page(session, workspace_id, ticket_identifier):\n    ...",
) -> MagicMock:
    """Create a mock CodeChunk record."""
    chunk = MagicMock()
    chunk.id = uuid4()
    chunk.workspace_id = WORKSPACE_ID
    chunk.symbol_name = symbol_name
    chunk.symbol_type = symbol_type
    chunk.repo_full_name = repo_full_name
    chunk.file_path = file_path
    chunk.content = content
    chunk.language = "python"
    chunk.content_hash = "abc123"
    chunk.start_line = 1
    chunk.end_line = 10
    chunk.metadata_ = {}
    return chunk


@pytest.mark.asyncio
async def test_lookup_source_summary_code_chunk() -> None:
    """_lookup_source_summary for source_type='code_chunk' returns title with symbol and file, content snippet."""
    mock_session = AsyncMock()

    chunk = _make_code_chunk(
        symbol_name="calculate_score",
        symbol_type="function",
        repo_full_name="acme/backend",
        file_path="src/scoring.py",
        content="def calculate_score(items):\n    return sum(i.score for i in items)\n",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = chunk
    mock_session.execute.return_value = mock_result

    from src.services.linking import _lookup_source_summary

    title, snippet = await _lookup_source_summary(mock_session, "code_chunk", chunk.id)

    assert "function" in title
    assert "calculate_score" in title
    assert "acme/backend" in title
    assert "src/scoring.py" in title
    assert "calculate_score" in snippet


@pytest.mark.asyncio
async def test_find_hybrid_matches_includes_code_chunks() -> None:
    """_find_hybrid_matches includes code_chunk results when hybrid_search returns them."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    chunk = _make_code_chunk()
    chunk_id = chunk.id

    # Mock hybrid_search result including a code_chunk
    mock_match_result = MagicMock()
    mock_match_result.fetchall.return_value = [
        (uuid4(), "code_chunk", chunk_id, 0.78, 0.12, 0.55, {}),
    ]

    # Mock source lookup for code_chunk
    mock_source_result = MagicMock()
    mock_source_result.scalar_one_or_none.return_value = chunk

    mock_session.execute.side_effect = [
        mock_match_result,
        mock_source_result,
    ]

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import _find_hybrid_matches

        items = await _find_hybrid_matches(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 1
    key = list(items.keys())[0]
    assert key[0] == "code_chunk"
    assert key[1] == chunk_id
    assert "hybrid_search" in items[key].signals
    # Score should be combined_score * WEIGHT_HYBRID = 0.55 * 0.8
    assert abs(items[key].relevance_score - 0.55 * 0.8) < 0.01


@pytest.mark.asyncio
async def test_find_related_content_merges_code_chunks() -> None:
    """find_related_content merges code_chunk items into the final LinkingResult alongside other source types."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    ticket = _make_ticket(identifier="CON-99")

    chunk = _make_code_chunk(
        symbol_name="handle_webhook",
        symbol_type="function",
        repo_full_name="acme/api",
        file_path="src/webhooks.py",
    )
    chunk_id = chunk.id

    slack_id = uuid4()

    # --- Mock explicit refs ---
    # PR: none
    mock_pr_result = MagicMock()
    mock_pr_result.scalars.return_value.all.return_value = []
    # Comments: none
    mock_comment_result = MagicMock()
    mock_comment_result.scalars.return_value.all.return_value = []
    # Slack: one message
    mock_msg = MagicMock()
    mock_msg.id = slack_id
    mock_msg.text = "Working on CON-99 webhook handler"
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"
    mock_slack_result = MagicMock()
    mock_slack_result.scalars.return_value.all.return_value = [mock_msg]

    # --- Mock hybrid matches ---
    # Returns both a code_chunk and the same slack message
    mock_match_result = MagicMock()
    mock_match_result.fetchall.return_value = [
        (uuid4(), "code_chunk", chunk_id, 0.80, 0.10, 0.58, {}),
        (uuid4(), "slack_message", slack_id, 0.70, 0.15, 0.50, {}),
    ]

    # Source lookups for both hybrid matches
    mock_chunk_source = MagicMock()
    mock_chunk_source.scalar_one_or_none.return_value = chunk

    mock_slack_source = MagicMock()
    mock_slack_source.scalar_one_or_none.return_value = mock_msg

    mock_session.execute.side_effect = [
        # Explicit refs
        mock_pr_result,       # PRs
        mock_comment_result,  # Comments
        mock_slack_result,    # Slack mentions
        # Hybrid matches
        mock_match_result,    # hybrid_search
        mock_chunk_source,    # code_chunk source lookup
        mock_slack_source,    # slack source lookup
    ]

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(mock_session, WORKSPACE_ID, ticket)

    # Should have at least 2 items: the slack message and the code_chunk
    assert len(result.items) >= 2

    # Verify code_chunk is present in the results
    code_items = [item for item in result.items if item.source_type == "code_chunk"]
    assert len(code_items) == 1
    assert code_items[0].source_id == chunk_id

    # Verify slack message is also present (found by both explicit + hybrid)
    slack_items = [item for item in result.items if item.source_type == "slack_message"]
    assert len(slack_items) == 1
    assert slack_items[0].source_id == slack_id
    # Slack found by both signals should have combined score > either alone
    assert slack_items[0].relevance_score > 1.0
