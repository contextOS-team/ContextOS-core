"""Tests for code-to-discussion graph linking (CODE-01, CODE-02, CODE-03).

CODE-01: Slack file path mentions create 'mentions' edges to matching code_chunks graph nodes.
CODE-02: PRs linked to tickets create transitive 'discussed_in' edges from CodeChunk to discussion nodes.
CODE-03: Code provenance annotations in synthesis _format_related_content().

Production functions use lazy imports inside function bodies. Tests mock
session.execute for DB queries and patch graph_ops for graph operations.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.services.graph_extractor import ExtractedEntity


# ============================================================
# Test helpers
# ============================================================

WORKSPACE_ID = UUID("22222222-2222-2222-2222-222222222222")


def _make_code_chunk_entity(file_path: str) -> ExtractedEntity:
    """Create a CodeChunk ExtractedEntity for testing."""
    return ExtractedEntity(
        entity_type="CodeChunk",
        external_id=f"path:{file_path}",
        name=file_path,
        properties={"file_path": file_path},
        relationship_type="references",
    )


def _make_mock_code_chunk(chunk_id: UUID, file_path: str, symbol_name: str = "func",
                           symbol_type: str = "function"):
    """Create a mock code_chunks table record."""
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.workspace_id = WORKSPACE_ID
    chunk.file_path = file_path
    chunk.symbol_name = symbol_name
    chunk.symbol_type = symbol_type
    chunk.deleted_at = None
    return chunk


def _make_linked_item(
    source_type: str = "slack_message",
    title: str = "Test",
    snippet: str = "snippet",
    relevance_score: float = 0.8,
    signals: list[str] | None = None,
    source_id: UUID | None = None,
) -> MagicMock:
    """Create a mock LinkedItem for synthesis tests."""
    item = MagicMock()
    item.source_type = source_type
    item.source_id = source_id or uuid4()
    item.title = title
    item.snippet = snippet
    item.relevance_score = relevance_score
    item.signals = signals or ["hybrid_search"]
    return item


# ============================================================
# CODE-01: link_code_mentions_to_chunks
# ============================================================


class TestLinkCodeMentionsToChunks:
    """Tests for link_code_mentions_to_chunks() -- CODE-01."""

    @pytest.mark.asyncio
    async def test_slack_file_path_creates_edge(self):
        """When a Slack message mentions src/services/auth.py and a matching
        code_chunk exists, a 'mentions' edge is created from the source node
        to a CodeChunk graph node backed by that code_chunk record."""
        from src.services.graph_extractor import link_code_mentions_to_chunks

        session = AsyncMock()
        source_node_id = uuid4()
        chunk_id = uuid4()
        chunk_node_id = uuid4()

        # Mock code_chunks query result
        mock_chunk = _make_mock_code_chunk(
            chunk_id, "backend/src/services/auth.py", "authenticate_user"
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_chunk]
        session.execute.return_value = mock_result

        entities = [_make_code_chunk_entity("src/services/auth.py")]

        with (
            patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock,
                  return_value=chunk_node_id) as mock_upsert_node,
            patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge,
        ):
            await link_code_mentions_to_chunks(
                session, WORKSPACE_ID, source_node_id, entities
            )

        # Verify CodeChunk graph node created with chunk: prefix
        mock_upsert_node.assert_called_once_with(
            session=session,
            workspace_id=WORKSPACE_ID,
            entity_type="CodeChunk",
            external_id=f"chunk:{chunk_id}",
            name="function: authenticate_user",
            source_type="code_chunk",
            source_id=chunk_id,
        )

        # Verify 'mentions' edge created
        mock_upsert_edge.assert_called_once_with(
            session=session,
            workspace_id=WORKSPACE_ID,
            source_node_id=source_node_id,
            target_node_id=chunk_node_id,
            relationship_type="mentions",
            properties={"matched_path": "src/services/auth.py"},
        )

    @pytest.mark.asyncio
    async def test_bare_filename_no_edge(self):
        """File path 'config.py' with no directory segment does NOT create edges
        (requires at least 1 '/' in path to avoid false positives)."""
        from src.services.graph_extractor import link_code_mentions_to_chunks

        session = AsyncMock()
        source_node_id = uuid4()

        entities = [_make_code_chunk_entity("config.py")]

        with (
            patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock) as mock_upsert_node,
            patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge,
        ):
            await link_code_mentions_to_chunks(
                session, WORKSPACE_ID, source_node_id, entities
            )

        # No graph operations should have been called
        mock_upsert_node.assert_not_called()
        mock_upsert_edge.assert_not_called()
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_chunks_multiple_edges(self):
        """A file path matching 3 code_chunks creates 3 edges (one per symbol)."""
        from src.services.graph_extractor import link_code_mentions_to_chunks

        session = AsyncMock()
        source_node_id = uuid4()

        chunks = [
            _make_mock_code_chunk(uuid4(), "src/auth.py", "User", "class"),
            _make_mock_code_chunk(uuid4(), "src/auth.py", "login", "function"),
            _make_mock_code_chunk(uuid4(), "src/auth.py", "logout", "function"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        session.execute.return_value = mock_result

        entities = [_make_code_chunk_entity("src/auth.py")]

        with (
            patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock,
                  return_value=uuid4()) as mock_upsert_node,
            patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge,
        ):
            await link_code_mentions_to_chunks(
                session, WORKSPACE_ID, source_node_id, entities
            )

        assert mock_upsert_node.call_count == 3
        assert mock_upsert_edge.call_count == 3

    @pytest.mark.asyncio
    async def test_fail_silent_on_db_error(self):
        """Database error during code linking is caught and logged, does not raise."""
        from src.services.graph_extractor import link_code_mentions_to_chunks

        session = AsyncMock()
        session.execute.side_effect = RuntimeError("DB connection lost")
        source_node_id = uuid4()

        entities = [_make_code_chunk_entity("src/auth.py")]

        # Should NOT raise
        await link_code_mentions_to_chunks(
            session, WORKSPACE_ID, source_node_id, entities
        )


# ============================================================
# CODE-02: link_pr_code_to_discussions
# ============================================================


class TestLinkPRCodeToDiscussions:
    """Tests for link_pr_code_to_discussions() -- CODE-02."""

    @pytest.mark.asyncio
    async def test_pr_code_to_discussion_edges(self):
        """When a PR's source node has CodeChunk entity neighbors and the PR
        is linked to a ticket that has SlackThread discussion neighbors,
        transitive 'discussed_in' edges are created from CodeChunk nodes
        to those SlackThread nodes."""
        from src.services.graph_extractor import link_pr_code_to_discussions

        session = AsyncMock()
        source_node_id = uuid4()
        source_id = uuid4()  # PR record ID
        ticket_id = uuid4()

        # Mock PR lookup -- has linear_ticket_id
        mock_pr = MagicMock()
        mock_pr.linear_ticket_id = ticket_id

        # Mock ticket lookup -- has identifier
        mock_ticket = MagicMock()
        mock_ticket.identifier = "CON-42"

        code_chunk_node_id_1 = uuid4()
        code_chunk_node_id_2 = uuid4()
        discussion_node_id_1 = uuid4()
        discussion_node_id_2 = uuid4()

        # Build mock return sequence for session.execute calls
        # Call 1: PR lookup
        mock_pr_result = MagicMock()
        mock_pr_result.scalar_one_or_none.return_value = mock_pr

        # Call 2: Ticket lookup
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalar_one_or_none.return_value = mock_ticket

        # Call 3: Ticket graph node lookup
        mock_ticket_node = MagicMock()
        mock_ticket_node.id = uuid4()
        mock_ticket_node_result = MagicMock()
        mock_ticket_node_result.scalar_one_or_none.return_value = mock_ticket_node

        # Call 4: CodeChunk neighbors of source_node
        mock_cc_edge_1 = MagicMock()
        mock_cc_edge_1.target_node_id = code_chunk_node_id_1
        mock_cc_edge_2 = MagicMock()
        mock_cc_edge_2.target_node_id = code_chunk_node_id_2
        mock_cc_edges_result = MagicMock()
        mock_cc_edges_result.scalars.return_value.all.return_value = [mock_cc_edge_1, mock_cc_edge_2]

        # Call 5: Discussion neighbors of ticket node
        mock_disc_node_1 = MagicMock()
        mock_disc_node_1.id = discussion_node_id_1
        mock_disc_node_2 = MagicMock()
        mock_disc_node_2.id = discussion_node_id_2
        mock_disc_result = MagicMock()
        mock_disc_result.scalars.return_value.all.return_value = [mock_disc_node_1, mock_disc_node_2]

        session.execute.side_effect = [
            mock_pr_result,
            mock_ticket_result,
            mock_ticket_node_result,
            mock_cc_edges_result,
            mock_disc_result,
        ]

        with patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge:
            await link_pr_code_to_discussions(
                session, WORKSPACE_ID, source_node_id, source_id
            )

        # 2 CodeChunk nodes x 2 discussion nodes = 4 edges
        assert mock_upsert_edge.call_count == 4
        # All edges should be 'discussed_in'
        for call in mock_upsert_edge.call_args_list:
            assert call.kwargs["relationship_type"] == "discussed_in"

    @pytest.mark.asyncio
    async def test_pr_no_ticket_link_skips(self):
        """PR with no linear_ticket_id FK skips transitive linking."""
        from src.services.graph_extractor import link_pr_code_to_discussions

        session = AsyncMock()
        source_node_id = uuid4()
        source_id = uuid4()

        # Mock PR with no ticket link
        mock_pr = MagicMock()
        mock_pr.linear_ticket_id = None

        mock_pr_result = MagicMock()
        mock_pr_result.scalar_one_or_none.return_value = mock_pr

        session.execute.return_value = mock_pr_result

        with patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge:
            await link_pr_code_to_discussions(
                session, WORKSPACE_ID, source_node_id, source_id
            )

        mock_upsert_edge.assert_not_called()


# ============================================================
# CODE-03: Code provenance annotations in synthesis
# ============================================================


class TestFormatRelatedContentProvenance:
    """Tests for _format_related_content() with code_provenance (CODE-03)."""

    def test_code_chunk_with_provenance_annotated(self):
        """code_chunk items with code_provenance get 'Discussed in:' annotation."""
        from src.services.synthesis import _format_related_content

        chunk_id = uuid4()
        item = _make_linked_item(
            source_type="code_chunk",
            title="function: auth (backend:src/auth.py)",
            snippet="def auth(token): pass",
            source_id=chunk_id,
        )

        provenance = {
            chunk_id: ["#backend-chat by @alex (Jan 15)"]
        }

        result = _format_related_content([item], code_provenance=provenance)

        assert "```" in result
        assert "def auth(token): pass" in result
        assert "Discussed in:" in result
        assert "#backend-chat by @alex (Jan 15)" in result

    def test_code_chunk_without_provenance_no_annotation(self):
        """code_chunk items without code_provenance render identically to current behavior."""
        from src.services.synthesis import _format_related_content

        item = _make_linked_item(
            source_type="code_chunk",
            title="function: auth (backend:src/auth.py)",
            snippet="def auth(token): pass",
        )

        # No provenance parameter
        result_no_param = _format_related_content([item])
        # Provenance=None
        result_none = _format_related_content([item], code_provenance=None)

        # Neither should contain "Discussed in:"
        assert "Discussed in:" not in result_no_param
        assert "Discussed in:" not in result_none
        # Both should still have fenced code block
        assert "```" in result_no_param
        assert "```" in result_none

    def test_code_chunk_not_in_provenance_no_annotation(self):
        """code_chunk item NOT in the provenance dict renders without annotation."""
        from src.services.synthesis import _format_related_content

        item = _make_linked_item(
            source_type="code_chunk",
            title="function: auth (backend:src/auth.py)",
            snippet="def auth(token): pass",
        )

        # Provenance exists but for a different source_id
        provenance = {uuid4(): ["#other-chat"]}

        result = _format_related_content([item], code_provenance=provenance)

        assert "Discussed in:" not in result
        assert "```" in result

    def test_multiple_discussions_joined(self):
        """Multiple discussions for the same code_chunk are joined with semicolons."""
        from src.services.synthesis import _format_related_content

        chunk_id = uuid4()
        item = _make_linked_item(
            source_type="code_chunk",
            title="fn: foo",
            snippet="def foo(): pass",
            source_id=chunk_id,
        )

        provenance = {
            chunk_id: ["#backend-chat by @alex", "Meeting: Sprint Review"]
        }

        result = _format_related_content([item], code_provenance=provenance)

        assert "Discussed in:" in result
        assert "#backend-chat by @alex" in result
        assert "Meeting: Sprint Review" in result
        assert ";" in result  # joined with semicolons


class TestGetCodeProvenance:
    """Tests for _get_code_provenance() helper (CODE-03)."""

    @pytest.mark.asyncio
    async def test_returns_dict_for_code_chunks(self):
        """_get_code_provenance() queries graph edges for code_chunk items
        and returns dict mapping source_id to discussion annotation strings."""
        from src.services.synthesis import _get_code_provenance

        chunk_id = uuid4()
        item = _make_linked_item(
            source_type="code_chunk",
            title="fn: auth",
            snippet="def auth(): pass",
            source_id=chunk_id,
        )

        session = AsyncMock()

        # The fingerprint computed for this chunk
        chunk_fp = f"fp:CodeChunk:chunk:{chunk_id}"

        # Mock 1: GraphNode lookup for CodeChunk fingerprints
        mock_chunk_node = MagicMock()
        mock_chunk_node.id = uuid4()
        mock_chunk_node.entity_type = "CodeChunk"
        mock_chunk_node.fingerprint = chunk_fp  # Must match computed fingerprint
        mock_chunk_nodes_result = MagicMock()
        mock_chunk_nodes_result.scalars.return_value.all.return_value = [mock_chunk_node]

        # Mock 2: GraphEdge lookup for edges pointing TO the chunk node
        disc_source_node_id = uuid4()
        mock_edge = MagicMock()
        mock_edge.source_node_id = disc_source_node_id
        mock_edge.target_node_id = mock_chunk_node.id  # edge points TO chunk
        mock_edges_result = MagicMock()
        mock_edges_result.scalars.return_value.all.return_value = [mock_edge]

        # Mock 3: Discussion source node lookup
        mock_disc_node = MagicMock()
        mock_disc_node.id = disc_source_node_id
        mock_disc_node.entity_type = "SlackThread"
        mock_disc_node.name = "#backend-chat"
        mock_disc_nodes_result = MagicMock()
        mock_disc_nodes_result.scalars.return_value.all.return_value = [mock_disc_node]

        session.execute.side_effect = [
            mock_chunk_nodes_result,
            mock_edges_result,
            mock_disc_nodes_result,
        ]

        with patch("src.services.synthesis.compute_fingerprint",
                    side_effect=lambda et, eid: f"fp:{et}:{eid}"):
            result = await _get_code_provenance(session, WORKSPACE_ID, [item])

        assert chunk_id in result
        assert len(result[chunk_id]) == 1
        assert "#backend-chat" in result[chunk_id][0]

    @pytest.mark.asyncio
    async def test_no_code_chunks_returns_empty(self):
        """_get_code_provenance() with no code_chunk items returns empty dict."""
        from src.services.synthesis import _get_code_provenance

        session = AsyncMock()
        item = _make_linked_item(source_type="slack_message")

        result = await _get_code_provenance(session, WORKSPACE_ID, [item])

        assert result == {}
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_fail_silent_returns_empty(self):
        """_get_code_provenance() returns empty dict on error, never raises."""
        from src.services.synthesis import _get_code_provenance

        session = AsyncMock()
        session.execute.side_effect = RuntimeError("DB error")

        item = _make_linked_item(
            source_type="code_chunk",
            source_id=uuid4(),
        )

        with patch("src.services.synthesis.compute_fingerprint",
                    side_effect=lambda et, eid: f"fp:{et}:{eid}"):
            result = await _get_code_provenance(session, WORKSPACE_ID, [item])

        assert result == {}


class TestGenerateContextPageProvenance:
    """Tests for generate_context_page() passing code provenance to _format_related_content()."""

    @pytest.mark.asyncio
    async def test_generate_passes_provenance_to_format(self):
        """generate_context_page() calls _get_code_provenance() and passes
        the result to _format_related_content() for non-graph code_chunk items."""
        from tests.conftest import TEST_WORKSPACE_ID

        WS_ID = UUID(TEST_WORKSPACE_ID)
        mock_session = AsyncMock()

        # Mock ticket
        ticket = MagicMock()
        ticket.id = uuid4()
        ticket.workspace_id = WS_ID
        ticket.identifier = "CON-16"
        ticket.title = "Auth refactor"
        ticket.description = "Refactor the auth module."
        ticket.status = "In Progress"
        ticket.assignee_name = "Alice"
        ticket.priority = 2
        ticket.labels = ["feature"]

        mock_ticket_result = MagicMock()
        mock_ticket_result.scalar_one_or_none.return_value = ticket
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None
        mock_session.execute.side_effect = [mock_ticket_result, mock_existing_result]

        # Create code_chunk linked item (non-graph)
        chunk_id = uuid4()
        code_item = _make_linked_item(
            source_type="code_chunk",
            title="fn: auth",
            snippet="def auth(): pass",
            source_id=chunk_id,
            signals=["hybrid_search"],
        )

        mock_linking_result = MagicMock()
        mock_linking_result.items = [code_item]

        mock_provenance = {chunk_id: ["#backend-chat by @alex"]}

        mock_llm_response = MagicMock()
        mock_llm_response.text = "# Context"
        mock_llm_response.model = "gemini-3-flash-preview"
        mock_llm_response.total_tokens = 500
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=mock_llm_response)

        # Capture calls to _format_related_content by replacing it with
        # a recording wrapper that calls the real function
        format_calls = []
        from src.services.synthesis import _format_related_content as real_format

        def _recording_format(*args, **kwargs):
            format_calls.append((args, kwargs))
            return real_format(*args, **kwargs)

        with (
            patch("src.services.synthesis.find_related_content",
                  new_callable=AsyncMock, return_value=mock_linking_result),
            patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
            patch("src.services.synthesis._get_code_provenance",
                  new_callable=AsyncMock, return_value=mock_provenance) as mock_get_prov,
            patch("src.services.synthesis._format_related_content",
                  side_effect=_recording_format),
        ):
            from src.services.synthesis import generate_context_page
            await generate_context_page(mock_session, WS_ID, "CON-16")

        # Verify _get_code_provenance was called
        mock_get_prov.assert_called_once()
        # Verify _format_related_content was called with code_provenance
        assert len(format_calls) == 1
        _, kwargs = format_calls[0]
        assert kwargs.get("code_provenance") == mock_provenance
