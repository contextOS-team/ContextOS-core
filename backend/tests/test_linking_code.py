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
from tests.conftest import TEST_WORKSPACE_ID

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

    # Dedicated code_chunk search returns empty (chunk already in general results)
    mock_code_result = MagicMock()
    mock_code_result.fetchall.return_value = []

    # Mock bulk source lookup for code_chunk
    mock_bulk_result = MagicMock()
    mock_bulk_result.scalars.return_value.all.return_value = [chunk]

    mock_session.execute.side_effect = [
        mock_match_result,
        mock_code_result,
        mock_bulk_result,
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

    mock_general_result = MagicMock()
    mock_general_result.fetchall.return_value = general_hits

    # Dedicated code search finds 3 relevant code chunks
    code_chunk_ids = [uuid4() for _ in range(3)]
    code_hits = [
        (uuid4(), "code_chunk", code_chunk_ids[0], 0.72, 0.08, 0.48, {}),
        (uuid4(), "code_chunk", code_chunk_ids[1], 0.68, 0.05, 0.42, {}),
        (uuid4(), "code_chunk", code_chunk_ids[2], 0.65, 0.03, 0.38, {}),
    ]
    mock_code_result = MagicMock()
    mock_code_result.fetchall.return_value = code_hits

    # Bulk lookups — one per source_type group in the hits
    # MRs
    mock_mr_objs = []
    for i, hit in enumerate(general_hits[:5]):
        mr = MagicMock()
        mr.id = hit[2]
        mr.iid = 100 + i
        mr.title = f"MR title {i}"
        mr.description = f"MR desc {i}"
        mock_mr_objs.append(mr)
    mock_mr_bulk = MagicMock()
    mock_mr_bulk.scalars.return_value.all.return_value = mock_mr_objs

    # Slack messages
    mock_slack_objs = []
    for i, hit in enumerate(general_hits[5:8]):
        msg = MagicMock()
        msg.id = hit[2]
        msg.text = f"Slack msg {i}"
        msg.user_name = "alice"
        msg.channel_name = "dev"
        mock_slack_objs.append(msg)
    mock_slack_bulk = MagicMock()
    mock_slack_bulk.scalars.return_value.all.return_value = mock_slack_objs

    # Jira comments
    mock_jira_objs = []
    for i, hit in enumerate(general_hits[8:10]):
        comment = MagicMock()
        comment.id = hit[2]
        comment.body = f"Jira comment {i}"
        comment.author_name = "bob"
        mock_jira_objs.append(comment)
    mock_jira_bulk = MagicMock()
    mock_jira_bulk.scalars.return_value.all.return_value = mock_jira_objs

    # Code chunks
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
    mock_chunk_bulk = MagicMock()
    mock_chunk_bulk.scalars.return_value.all.return_value = mock_chunk_objs

    mock_session.execute.side_effect = [
        mock_general_result,   # 1. General hybrid_search (10 non-code results)
        mock_code_result,      # 2. Dedicated code_chunk hybrid_search
        mock_mr_bulk,          # 3. Bulk lookup: gitlab_merge_request
        mock_slack_bulk,       # 4. Bulk lookup: slack_message
        mock_jira_bulk,        # 5. Bulk lookup: jira_comment
        mock_chunk_bulk,       # 6. Bulk lookup: code_chunk
    ]

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

    # General search includes this code chunk (it scored high enough)
    mock_general_result = MagicMock()
    mock_general_result.fetchall.return_value = [
        (uuid4(), "code_chunk", chunk_id, 0.85, 0.15, 0.62, {}),
        (uuid4(), "slack_message", uuid4(), 0.70, 0.10, 0.50, {}),
    ]

    # Dedicated code search ALSO returns the same chunk (it's the top code result)
    mock_code_result = MagicMock()
    mock_code_result.fetchall.return_value = [
        (uuid4(), "code_chunk", chunk_id, 0.85, 0.15, 0.62, {}),
    ]

    # Bulk lookups
    mock_chunk_bulk = MagicMock()
    mock_chunk_bulk.scalars.return_value.all.return_value = [chunk]

    mock_msg = MagicMock()
    mock_msg.id = mock_general_result.fetchall.return_value[1][2]
    mock_msg.text = "Some message"
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"
    mock_slack_bulk = MagicMock()
    mock_slack_bulk.scalars.return_value.all.return_value = [mock_msg]

    mock_session.execute.side_effect = [
        mock_general_result,
        mock_code_result,
        mock_chunk_bulk,
        mock_slack_bulk,
    ]

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

    # Dedicated code_chunk search returns empty (chunk already in general results)
    mock_code_search_result = MagicMock()
    mock_code_search_result.fetchall.return_value = []

    # Bulk source lookups for hybrid matches (grouped by source_type)
    mock_chunk_bulk = MagicMock()
    mock_chunk_bulk.scalars.return_value.all.return_value = [chunk]

    mock_slack_bulk = MagicMock()
    mock_slack_bulk.scalars.return_value.all.return_value = [mock_msg]

    # Mock GitLab MR query (no MRs)
    mock_gl_mr_result = MagicMock()
    mock_gl_mr_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        # _find_explicit_refs for LinearTicket:
        mock_pr_result,            # 1. GitHub PRs
        mock_gl_mr_result,         # 2. GitLab MRs
        mock_comment_result,       # 3. Linear comments
        mock_slack_result,         # 4. Slack mentions
        # _find_hybrid_matches:
        mock_match_result,         # 5. hybrid_search SQL (general)
        mock_code_search_result,   # 6. hybrid_search SQL (code_chunk dedicated)
        mock_chunk_bulk,           # 7. bulk code_chunk lookup
        mock_slack_bulk,           # 8. bulk slack_message lookup
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
