"""Tests for the linking engine.

Covers:
- Explicit reference finding (PRs, comments, Slack messages)
- Hybrid search (vector + full-text) matching
- Combined multi-signal scoring and ranking

These tests dispatch ``session.execute`` by the ORM entity being queried
(via ``make_entity_execute``) rather than by positional ``side_effect``
order. Adding a new ``select(Model)`` to the linking engine therefore can
not silently break a test that doesn't care about that model — it just
receives the empty default.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.models.ticket import LinearTicket

from tests.conftest import TEST_WORKSPACE_ID, make_entity_execute

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _make_ticket(
    identifier: str = "CON-16",
    title: str = "Implement context synthesis",
    description: str = "Build the AI context page generation pipeline.",
) -> MagicMock:
    """Create a mock LinearTicket that passes isinstance checks."""
    ticket = MagicMock(spec=LinearTicket)
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = identifier
    ticket.title = title
    ticket.description = description
    return ticket


def _scalars(rows: list) -> MagicMock:
    """Wrap rows in a result whose .scalars().all() yields them."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


def _hybrid(rows: list) -> MagicMock:
    """Wrap rows in a result whose .fetchall() yields them (text() SQL)."""
    r = MagicMock()
    r.fetchall.return_value = rows
    return r


@pytest.fixture(autouse=True)
def _no_slack_permalink_io():
    """Linking unit tests assert on scoring, not Slack plumbing.

    _find_explicit_refs() reads the Slack bot token and resolves each
    message's canonical permalink via chat.getPermalink. Stub both so the
    bare-URL fallback is exercised and no Vault/HTTP work happens here;
    permalink behaviour is covered by the Slack suites.
    """
    with patch(
        "src.services.slack_oauth.get_bot_token",
        new_callable=AsyncMock,
        return_value="xoxb-test",
    ), patch(
        "src.services.slack_events.resolve_slack_permalink",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


@pytest.mark.asyncio
async def test_find_explicit_refs_linked_prs() -> None:
    """Should find PRs linked via linear_ticket_id FK."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    mock_pr = MagicMock()
    mock_pr.id = uuid4()
    mock_pr.number = 42
    mock_pr.title = "Implement synthesis"
    mock_pr.description = "PR description"

    mock_session.execute.side_effect = make_entity_execute(
        {"GithubPullRequest": _scalars([mock_pr])}
    )

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

    mock_msg = MagicMock()
    mock_msg.id = uuid4()
    mock_msg.text = "Hey, have you seen CON-42? We need to prioritize it."
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "engineering"

    mock_session.execute.side_effect = make_entity_execute(
        {"SlackMessage": _scalars([mock_msg])}
    )

    from src.services.linking import _find_explicit_refs

    items = await _find_explicit_refs(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 1
    key = list(items.keys())[0]
    assert key[0] == "slack_message"
    assert "explicit_reference" in items[key].signals


@pytest.mark.asyncio
async def test_find_hybrid_matches() -> None:
    """Should find related content via hybrid vector + full-text search."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    other_id = uuid4()
    mock_msg = MagicMock()
    mock_msg.id = other_id
    mock_msg.text = "We discussed the context page approach"
    mock_msg.user_name = "bob"
    mock_msg.channel_name = "dev"

    # hybrid_search() is raw text() SQL -> routed via `textual`. The bulk
    # summary lookup selects Embedding (none) then SlackMessage (fallback).
    mock_session.execute.side_effect = make_entity_execute(
        {"SlackMessage": _scalars([mock_msg])},
        textual=_hybrid([(uuid4(), "slack_message", other_id, 0.82, 0.15, 0.619, {})]),
    )

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
    assert key[0] == "slack_message"
    assert "hybrid_search" in items[key].signals
    # Score should be combined_score * WEIGHT_HYBRID = 0.619 * 0.8
    assert abs(items[key].relevance_score - 0.619 * 0.8) < 0.01


@pytest.mark.asyncio
async def test_find_hybrid_matches_skips_self() -> None:
    """Should skip the ticket's own embedding in hybrid matches."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    mock_session.execute.side_effect = make_entity_execute(
        textual=_hybrid([(uuid4(), "linear_ticket", ticket.id, 1.0, 0.5, 0.85, {})]),
    )

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import _find_hybrid_matches

        items = await _find_hybrid_matches(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 0


@pytest.mark.asyncio
async def test_combined_scoring_multi_signal() -> None:
    """Items found by multiple signals should have combined scores."""
    mock_session = AsyncMock()
    ticket = _make_ticket(identifier="CON-16")

    shared_id = uuid4()
    mock_msg = MagicMock()
    mock_msg.id = shared_id
    mock_msg.text = "Working on CON-16 context synthesis"
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"

    # Same Slack message surfaces via explicit ref (select SlackMessage)
    # and via hybrid search (text() -> bulk SlackMessage fallback).
    mock_session.execute.side_effect = make_entity_execute(
        {"SlackMessage": _scalars([mock_msg])},
        textual=_hybrid([(uuid4(), "slack_message", shared_id, 0.85, 0.2, 0.655, {})]),
    )

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import find_related_content

        result = await find_related_content(mock_session, WORKSPACE_ID, ticket)

    assert len(result.items) >= 1
    top_item = result.items[0]
    assert top_item.source_id == shared_id
    # Found by both explicit and hybrid signals — signals are merged.
    assert len(top_item.signals) >= 2
    # find_related_content fuses signals with Reciprocal Rank Fusion and
    # normalises the result to [0, 1] (max rank -> 1.0), so a multi-signal
    # item that tops every list scores exactly 1.0. (The old additive
    # "> 1.0" contract no longer holds after the RRF rewrite.)
    assert top_item.relevance_score == pytest.approx(1.0)
    assert all(0.0 <= it.relevance_score <= 1.0 for it in result.items)


@pytest.mark.asyncio
async def test_find_content_by_source_skips_disconnected() -> None:
    """Only connected sources should be yielded when connected_sources is provided."""
    mock_session = AsyncMock()
    ticket = _make_ticket(identifier="CON-50")

    mock_comment = MagicMock()
    mock_comment.id = uuid4()
    mock_comment.body = "A linear comment"
    mock_comment.author_name = "alice"

    slack_id = uuid4()
    mock_slack_msg = MagicMock()
    mock_slack_msg.id = slack_id
    mock_slack_msg.text = "Slack about CON-50"
    mock_slack_msg.user_name = "bob"
    mock_slack_msg.channel_name = "dev"

    mock_session.execute.side_effect = make_entity_execute(
        {
            "LinearComment": _scalars([mock_comment]),
            "SlackMessage": _scalars([mock_slack_msg]),
        },
        textual=_hybrid([(uuid4(), "slack_message", slack_id, 0.80, 0.10, 0.55, {})]),
    )

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import find_content_by_source

        yielded_sources: list[str] = []
        async for source_name, items, detail in find_content_by_source(
            mock_session, WORKSPACE_ID, ticket, connected_sources={"linear"}
        ):
            yielded_sources.append(source_name)

    # Only "linear" should be yielded — slack, github, etc. skipped
    assert "linear" in yielded_sources
    assert "slack" not in yielded_sources
    assert "github" not in yielded_sources


@pytest.mark.asyncio
async def test_find_content_by_source_none_returns_all() -> None:
    """When connected_sources is None, all sources should be yielded."""
    mock_session = AsyncMock()
    ticket = _make_ticket(identifier="CON-51")

    # All entity queries return empty; hybrid_search returns no rows.
    mock_session.execute.side_effect = make_entity_execute(
        textual=_hybrid([]),
    )

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import find_content_by_source

        yielded_sources: list[str] = []
        async for source_name, items, detail in find_content_by_source(
            mock_session, WORKSPACE_ID, ticket, connected_sources=None
        ):
            yielded_sources.append(source_name)

    from src.services.linking import SOURCE_TYPE_MAP

    for source_name in SOURCE_TYPE_MAP:
        assert source_name in yielded_sources, f"{source_name} missing from yielded sources"
