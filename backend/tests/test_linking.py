"""Tests for the linking engine.

Covers:
- Explicit reference finding (PRs, comments, Slack messages)
- Semantic similarity matching
- Keyword/trigram matching
- Combined multi-signal scoring and ranking
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


@pytest.mark.asyncio
async def test_find_explicit_refs_linked_prs() -> None:
    """Should find PRs linked via linear_ticket_id FK."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    # Mock PR query
    mock_pr = MagicMock()
    mock_pr.id = uuid4()
    mock_pr.number = 42
    mock_pr.title = "Implement synthesis"
    mock_pr.description = "PR description"

    mock_pr_result = MagicMock()
    mock_pr_result.scalars.return_value.all.return_value = [mock_pr]

    # Mock review query (no reviews)
    mock_review_result = MagicMock()
    mock_review_result.scalars.return_value.all.return_value = []

    # Mock comment query (no comments)
    mock_comment_result = MagicMock()
    mock_comment_result.scalars.return_value.all.return_value = []

    # Mock Slack query (no messages)
    mock_slack_result = MagicMock()
    mock_slack_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        mock_pr_result,
        mock_review_result,
        mock_comment_result,
        mock_slack_result,
    ]

    from src.services.linking import _find_explicit_refs

    items = await _find_explicit_refs(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 1
    key = list(items.keys())[0]
    assert key[0] == "github_pull_request"
    assert items[key].relevance_score == 1.0
    assert "explicit_link" in items[key].signals


@pytest.mark.asyncio
async def test_find_explicit_refs_slack_mentions() -> None:
    """Should find Slack messages containing the ticket identifier."""
    mock_session = AsyncMock()
    ticket = _make_ticket(identifier="CON-42")

    # Mock PR query (no PRs)
    mock_pr_result = MagicMock()
    mock_pr_result.scalars.return_value.all.return_value = []

    # Mock comment query (no comments)
    mock_comment_result = MagicMock()
    mock_comment_result.scalars.return_value.all.return_value = []

    # Mock Slack query
    mock_msg = MagicMock()
    mock_msg.id = uuid4()
    mock_msg.text = "Hey, have you seen CON-42? We need to prioritize it."
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "engineering"

    mock_slack_result = MagicMock()
    mock_slack_result.scalars.return_value.all.return_value = [mock_msg]

    mock_session.execute.side_effect = [
        mock_pr_result,
        mock_comment_result,
        mock_slack_result,
    ]

    from src.services.linking import _find_explicit_refs

    items = await _find_explicit_refs(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 1
    key = list(items.keys())[0]
    assert key[0] == "slack_message"
    assert "explicit_reference" in items[key].signals


@pytest.mark.asyncio
async def test_find_semantic_matches() -> None:
    """Should find semantically similar content via embeddings."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    # Mock match_embeddings result
    other_id = uuid4()
    mock_match_result = MagicMock()
    mock_match_result.fetchall.return_value = [
        (uuid4(), "slack_message", other_id, 0.82, {}),
    ]

    # Mock source lookup for the matched item
    mock_msg = MagicMock()
    mock_msg.text = "We discussed the context page approach"
    mock_msg.user_name = "bob"
    mock_msg.channel_name = "dev"
    mock_source_result = MagicMock()
    mock_source_result.scalar_one_or_none.return_value = mock_msg

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
        from src.services.linking import _find_semantic_matches

        items = await _find_semantic_matches(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 1
    key = list(items.keys())[0]
    assert key[0] == "slack_message"
    assert "semantic_similarity" in items[key].signals
    # Score should be similarity * WEIGHT_SEMANTIC = 0.82 * 0.7
    assert abs(items[key].relevance_score - 0.82 * 0.7) < 0.01


@pytest.mark.asyncio
async def test_find_semantic_matches_skips_self() -> None:
    """Should skip the ticket's own embedding in semantic matches."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    # Match result includes the ticket itself
    mock_match_result = MagicMock()
    mock_match_result.fetchall.return_value = [
        (uuid4(), "linear_ticket", ticket.id, 1.0, {}),  # self-match
    ]

    mock_session.execute.side_effect = [mock_match_result]

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import _find_semantic_matches

        items = await _find_semantic_matches(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 0


@pytest.mark.asyncio
async def test_combined_scoring_multi_signal() -> None:
    """Items found by multiple signals should have combined scores."""
    mock_session = AsyncMock()
    ticket = _make_ticket(identifier="CON-16")

    shared_id = uuid4()

    # --- Mock explicit refs ---
    # PR: none
    mock_pr_result = MagicMock()
    mock_pr_result.scalars.return_value.all.return_value = []
    # Comments: none
    mock_comment_result = MagicMock()
    mock_comment_result.scalars.return_value.all.return_value = []
    # Slack: one message mentioning CON-16
    mock_msg = MagicMock()
    mock_msg.id = shared_id
    mock_msg.text = "Working on CON-16 context synthesis"
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"
    mock_slack_result = MagicMock()
    mock_slack_result.scalars.return_value.all.return_value = [mock_msg]

    # --- Mock semantic matches ---
    mock_match_result = MagicMock()
    mock_match_result.fetchall.return_value = [
        (uuid4(), "slack_message", shared_id, 0.85, {}),
    ]
    mock_source_result = MagicMock()
    mock_source_result.scalar_one_or_none.return_value = mock_msg

    # --- Mock keyword matches ---
    mock_keyword_slack_result = MagicMock()
    mock_keyword_slack_result.fetchall.return_value = []
    mock_keyword_meeting_result = MagicMock()
    mock_keyword_meeting_result.fetchall.return_value = []

    mock_session.execute.side_effect = [
        # Explicit refs
        mock_pr_result,       # PRs
        mock_comment_result,  # Comments
        mock_slack_result,    # Slack mentions
        # Semantic matches
        mock_match_result,    # match_embeddings
        mock_source_result,   # source lookup
        # Keyword matches
        mock_keyword_slack_result,    # trigram on slack
        mock_keyword_meeting_result,  # trigram on meetings
    ]

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(mock_session, WORKSPACE_ID, ticket)

    assert len(result.items) >= 1
    # The slack message found by both explicit + semantic should have combined score
    top_item = result.items[0]
    assert top_item.source_id == shared_id
    assert len(top_item.signals) >= 2
    # Score should be explicit (1.0) + semantic (0.85 * 0.7) > 1.0
    assert top_item.relevance_score > 1.0
