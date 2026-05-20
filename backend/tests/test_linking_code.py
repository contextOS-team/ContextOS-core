"""Tests for code_chunk integration in the linking engine.

Covers:
- _lookup_source_summary correctly formats code_chunk titles and snippets
- Code chunks appear in hybrid search results alongside other source types
- find_related_content merges code_chunk items into the final LinkingResult
- Code chunks appear only under the "code" source, not duplicated under github/gitlab
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.models.ticket import LinearTicket
from src.services.linking import LinkedItem
from tests.conftest import TEST_WORKSPACE_ID, make_entity_execute, route_textual

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _scalars(rows: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


def _rows(rows: list) -> MagicMock:
    r = MagicMock()
    r.fetchall.return_value = rows
    return r


def _hybrid_router(general: list, code: list):
    """Route the shared hybrid_search text() by its bound source_type param.

    _find_hybrid_matches runs the same statement twice: a general search
    (source_type=None) and a dedicated code_chunk search
    (source_type="code_chunk"). Dispatch on the param instead of call
    order so the test can't rot when surrounding queries change.
    """

    def _route(params: dict) -> MagicMock:
        return _rows(code if params.get("source_type") == "code_chunk" else general)

    return route_textual(_route)


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

    # General hybrid_search returns the code_chunk; dedicated code search
    # returns empty (already covered). Bulk summary lookup resolves the
    # CodeChunk (Embedding metadata probe returns empty -> source-table
    # fallback).
    mock_session.execute.side_effect = make_entity_execute(
        {"CodeChunk": _scalars([chunk])},
        textual=_hybrid_router(
            general=[(uuid4(), "code_chunk", chunk_id, 0.78, 0.12, 0.55, {})],
            code=[],
        ),
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
    assert key[0] == "code_chunk"
    assert key[1] == chunk_id
    assert "hybrid_search" in items[key].signals
    # Score should be combined_score * WEIGHT_HYBRID = 0.55 * 0.8
    assert abs(items[key].relevance_score - 0.55 * 0.8) < 0.01


@pytest.mark.asyncio
async def test_dedicated_code_search_finds_chunks_when_general_search_is_full() -> None:
    """The actual bug: general hybrid search returns 10 non-code results,
    completely crowding out code chunks.  The dedicated code_chunk search
    must still find them.

    This is the scenario that triggered this fix — without the dedicated
    search, code chunks get zero slots when MRs/comments/messages dominate.
    """
    mock_session = AsyncMock()
    ticket = _make_ticket(
        identifier="HD-10544",
        title="Fix payment processing timeout",
        description="Payment service times out after 30s on large orders.",
    )

    # General search returns 10 non-code results (all slots consumed)
    general_hits = [
        (uuid4(), "gitlab_merge_request", uuid4(), 0.85, 0.20, 0.65, {})
        for _ in range(5)
    ] + [
        (uuid4(), "slack_message", uuid4(), 0.75, 0.15, 0.55, {})
        for _ in range(3)
    ] + [
        (uuid4(), "jira_comment", uuid4(), 0.70, 0.10, 0.50, {})
        for _ in range(2)
    ]
    assert len(general_hits) == 10  # All slots consumed, zero room for code

    # Dedicated code search finds 3 relevant code chunks
    code_chunk_ids = [uuid4() for _ in range(3)]
    code_hits = [
        (uuid4(), "code_chunk", code_chunk_ids[0], 0.72, 0.08, 0.48, {}),
        (uuid4(), "code_chunk", code_chunk_ids[1], 0.68, 0.05, 0.42, {}),
        (uuid4(), "code_chunk", code_chunk_ids[2], 0.65, 0.03, 0.38, {}),
    ]

    # Bulk-lookup source objects, one list per source_type group.
    mock_mr_objs = []
    for i, hit in enumerate(general_hits[:5]):
        mr = MagicMock()
        mr.id = hit[2]
        mr.iid = 100 + i
        mr.title = f"MR title {i}"
        mr.description = f"MR desc {i}"
        mock_mr_objs.append(mr)

    mock_slack_objs = []
    for i, hit in enumerate(general_hits[5:8]):
        msg = MagicMock()
        msg.id = hit[2]
        msg.text = f"Slack msg {i}"
        msg.user_name = "alice"
        msg.channel_name = "dev"
        mock_slack_objs.append(msg)

    mock_jira_objs = []
    for i, hit in enumerate(general_hits[8:10]):
        comment = MagicMock()
        comment.id = hit[2]
        comment.body = f"Jira comment {i}"
        comment.author_name = "bob"
        mock_jira_objs.append(comment)

    mock_chunk_objs = []
    for i, cid in enumerate(code_chunk_ids):
        chunk = _make_code_chunk(
            symbol_name=f"process_payment_{i}",
            symbol_type="function",
            repo_full_name="hivetaxi/client-app/ios",
            file_path=f"src/payments/handler_{i}.swift",
            content=f"func process_payment_{i}() {{ ... }}",
        )
        chunk.id = cid
        mock_chunk_objs.append(chunk)

    mock_session.execute.side_effect = make_entity_execute(
        {
            "GitlabMergeRequest": _scalars(mock_mr_objs),
            "SlackMessage": _scalars(mock_slack_objs),
            "JiraComment": _scalars(mock_jira_objs),
            "CodeChunk": _scalars(mock_chunk_objs),
        },
        textual=_hybrid_router(general=general_hits, code=code_hits),
    )

    mock_embedding = [0.1] * 768
    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import _find_hybrid_matches

        items = await _find_hybrid_matches(mock_session, WORKSPACE_ID, ticket)

    # Must have all 13 items: 10 general + 3 code chunks
    assert len(items) == 13, (
        f"Expected 13 items (10 general + 3 code), got {len(items)}"
    )

    # Verify all 3 code chunks are present
    code_items = {k: v for k, v in items.items() if k[0] == "code_chunk"}
    assert len(code_items) == 3, (
        f"Expected 3 code chunks from dedicated search, got {len(code_items)}"
    )
    found_code_ids = {k[1] for k in code_items}
    assert found_code_ids == set(code_chunk_ids), "Not all code chunk IDs found"

    # Verify non-code items are also present
    mr_items = {k: v for k, v in items.items() if k[0] == "gitlab_merge_request"}
    assert len(mr_items) == 5
    slack_items = {k: v for k, v in items.items() if k[0] == "slack_message"}
    assert len(slack_items) == 3
    jira_items = {k: v for k, v in items.items() if k[0] == "jira_comment"}
    assert len(jira_items) == 2


@pytest.mark.asyncio
async def test_code_chunk_in_both_searches_is_not_duplicated() -> None:
    """When a code chunk appears in both the general search AND the dedicated
    code search, it must appear exactly once in results — not doubled."""
    mock_session = AsyncMock()
    ticket = _make_ticket()

    chunk = _make_code_chunk()
    chunk_id = chunk.id
    slack_id = uuid4()

    # The same code chunk appears in BOTH the general search and the
    # dedicated code search; it must be de-duplicated to one item.
    general_hits = [
        (uuid4(), "code_chunk", chunk_id, 0.85, 0.15, 0.62, {}),
        (uuid4(), "slack_message", slack_id, 0.70, 0.10, 0.50, {}),
    ]
    code_hits = [
        (uuid4(), "code_chunk", chunk_id, 0.85, 0.15, 0.62, {}),
    ]

    mock_msg = MagicMock()
    mock_msg.id = slack_id
    mock_msg.text = "Some message"
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"

    mock_session.execute.side_effect = make_entity_execute(
        {
            "CodeChunk": _scalars([chunk]),
            "SlackMessage": _scalars([mock_msg]),
        },
        textual=_hybrid_router(general=general_hits, code=code_hits),
    )

    mock_embedding = [0.1] * 768
    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import _find_hybrid_matches

        items = await _find_hybrid_matches(mock_session, WORKSPACE_ID, ticket)

    # Must have exactly 2 items, not 3
    assert len(items) == 2, (
        f"Expected 2 items (chunk + slack), got {len(items)} — "
        f"duplicate code chunk from both searches?"
    )

    code_items = [v for k, v in items.items() if k[0] == "code_chunk"]
    assert len(code_items) == 1, "Code chunk was duplicated"
    assert code_items[0].source_id == chunk_id


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

    # The slack message is found by BOTH explicit ref (select SlackMessage
    # in _find_explicit_refs) and hybrid search; the code chunk only by
    # hybrid. SlackMessage result is reused for both the explicit query and
    # the hybrid bulk lookup since make_entity_execute dispatches by entity.
    mock_msg = MagicMock()
    mock_msg.id = slack_id
    mock_msg.text = "Working on CON-99 webhook handler"
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"

    general_hits = [
        (uuid4(), "code_chunk", chunk_id, 0.80, 0.10, 0.58, {}),
        (uuid4(), "slack_message", slack_id, 0.70, 0.15, 0.50, {}),
    ]

    mock_session.execute.side_effect = make_entity_execute(
        {
            "SlackMessage": _scalars([mock_msg]),
            "CodeChunk": _scalars([chunk]),
        },
        textual=_hybrid_router(general=general_hits, code=[]),
    )

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
    # Found by two signals -> its signals are merged. find_related_content
    # fuses with Reciprocal Rank Fusion normalised to [0, 1] (the old
    # additive "> 1.0" contract no longer holds), so assert the multi-signal
    # merge instead of an out-of-range score.
    assert len(slack_items[0].signals) >= 2
    assert 0.0 <= slack_items[0].relevance_score <= 1.0


@pytest.mark.asyncio
async def test_code_chunks_not_double_counted_across_providers() -> None:
    """When both github and gitlab are in connected_sources, code_chunk items
    must appear exactly once under the 'code' source group — not duplicated
    under both 'github' and 'gitlab'.

    This was the original bug: SOURCE_TYPE_MAP had 'code_chunk' listed under
    both 'github' and 'gitlab', so every code chunk appeared twice.
    """
    chunk_id = uuid4()

    # Build a fake merged dict with one code_chunk and one github PR
    merged = {
        ("code_chunk", chunk_id): LinkedItem(
            source_type="code_chunk",
            source_id=chunk_id,
            title="fn: process_data",
            snippet="def process_data(): ...",
            relevance_score=0.8,
            signals=["hybrid_search"],
        ),
        ("github_pull_request", uuid4()): LinkedItem(
            source_type="github_pull_request",
            source_id=uuid4(),
            title="PR: Add process_data",
            snippet="Adds the process_data function",
            relevance_score=0.7,
            signals=["explicit_ref"],
        ),
    }

    # Mock _find_explicit_refs to return empty, _find_hybrid_matches to return merged
    ticket = _make_ticket()

    with (
        patch("src.services.linking._find_explicit_refs", new_callable=AsyncMock, return_value={}),
        patch("src.services.linking._find_hybrid_matches", new_callable=AsyncMock, return_value=merged),
    ):
        from src.services.linking import find_content_by_source

        results: dict[str, list] = {}
        async for source_name, items, detail in find_content_by_source(
            AsyncMock(),
            WORKSPACE_ID,
            ticket,
            connected_sources={"github", "gitlab", "code"},
        ):
            results[source_name] = items

    # code_chunk must appear ONLY under "code", not under "github" or "gitlab"
    code_items = results.get("code", [])
    assert len(code_items) == 1, f"Expected 1 code item, got {len(code_items)}"
    assert code_items[0].source_id == chunk_id

    github_items = results.get("github", [])
    github_code = [i for i in github_items if i.source_type == "code_chunk"]
    assert len(github_code) == 0, (
        f"code_chunk appeared under 'github' — double counting bug is back"
    )

    gitlab_items = results.get("gitlab", [])
    gitlab_code = [i for i in gitlab_items if i.source_type == "code_chunk"]
    assert len(gitlab_code) == 0, (
        f"code_chunk appeared under 'gitlab' — double counting bug is back"
    )

    # github PR should still be under "github"
    assert len(github_items) == 1
    assert github_items[0].source_type == "github_pull_request"
