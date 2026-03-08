"""Tests for code-to-discussion graph linking (CODE-01, CODE-02, CODE-03).

CODE-01: Slack file path mentions create 'mentions' edges to matching code_chunks graph nodes.
CODE-02: PRs linked to tickets create transitive 'discussed_in' edges from CodeChunk to discussion nodes.
CODE-03: Code provenance annotations in synthesis _format_related_content().

Uses sys.modules pre-population pattern (from Phase 24-02) to avoid sqlmodel import chain.
"""

import sys
import types as _types
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# ============================================================
# sys.modules pre-population to avoid sqlmodel import chain
# ============================================================

# The production code uses lazy imports (from src.services import graph_ops,
# from src.models.code_chunk import CodeChunk, etc.). We pre-populate
# sys.modules so these imports resolve to lightweight mocks instead of
# triggering the full sqlmodel/SQLAlchemy dependency chain.

# Ensure src.models is a proper "package" (has __path__) so
# `from src.models.X import Y` works
if "src.models" not in sys.modules:
    _mock_models = _types.ModuleType("src.models")
    _mock_models.__path__ = []  # type: ignore[attr-defined]
    sys.modules["src.models"] = _mock_models

# graph_ops mock
_mock_graph_ops = _types.ModuleType("src.services.graph_ops")
_mock_graph_ops.upsert_node = AsyncMock()  # type: ignore[attr-defined]
_mock_graph_ops.upsert_edge = AsyncMock()  # type: ignore[attr-defined]
_mock_graph_ops.compute_fingerprint = MagicMock(  # type: ignore[attr-defined]
    side_effect=lambda et, eid: f"fp:{et}:{eid}"
)
if "src.services.graph_ops" not in sys.modules:
    sys.modules["src.services.graph_ops"] = _mock_graph_ops
    import src.services
    src.services.graph_ops = _mock_graph_ops  # type: ignore[attr-defined]


# Pre-populate model modules used by graph_extractor.py lazy imports.
# We use MagicMock() classes since the production code's sqlmodel.select()
# calls are intercepted by patching session.execute. The `select(...).where()`
# chain is replaced by a mock_select that returns a chainable mock.
_model_mocks_map = {
    "src.models.graph_node": {"GraphNode": MagicMock()},
    "src.models.graph_edge": {"GraphEdge": MagicMock()},
    "src.models.code_chunk": {"CodeChunk": MagicMock()},
    "src.models.github": {"GithubPullRequest": MagicMock(), "GithubReview": MagicMock()},
    "src.models.ticket": {"LinearTicket": MagicMock(), "LinearComment": MagicMock()},
}

for mod_path, classes in _model_mocks_map.items():
    if mod_path not in sys.modules:
        _mod = _types.ModuleType(mod_path)
        for cls_name, cls_mock in classes.items():
            cls_mock.__name__ = cls_name
            setattr(_mod, cls_name, cls_mock)
        sys.modules[mod_path] = _mod
        parent_attr = mod_path.rsplit(".", 1)[1]
        setattr(sys.modules["src.models"], parent_attr, _mod)

# Mock sqlmodel.select to return a chainable mock (avoids SQLAlchemy coercion errors)
_original_select = None
if "sqlmodel" in sys.modules:
    import sqlmodel as _sm
    _original_select = _sm.select


def _mock_select(*args, **kwargs):
    """A mock select() that returns a chainable mock with .where() etc."""
    mock_stmt = MagicMock()
    mock_stmt.where.return_value = mock_stmt  # chainable
    mock_stmt.union.return_value = mock_stmt
    return mock_stmt


# Patch sqlmodel.select at module level so lazy imports inside production
# functions get the mock version. This is restored after tests via fixture.
import sqlmodel as _sqlmodel
_sqlmodel_original_select = _sqlmodel.select
_sqlmodel.select = _mock_select  # type: ignore[assignment]

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

        # Mock graph queries:
        # 1. PR record lookup
        # 2. Ticket record lookup
        # 3. Ticket graph node lookup (by fingerprint)
        # 4. CodeChunk neighbors of PR (graph edges where source_node_id == source_node_id, entity_type == CodeChunk)
        # 5. Discussion neighbors of ticket (graph edges from ticket node, entity_type in SlackThread/Meeting)
        code_chunk_node_id_1 = uuid4()
        code_chunk_node_id_2 = uuid4()
        discussion_node_id_1 = uuid4()
        discussion_node_id_2 = uuid4()

        # Build mock return sequence
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

        # Call 4: CodeChunk neighbors of source_node (edges from source node to CodeChunk nodes)
        mock_cc_edge_1 = MagicMock()
        mock_cc_edge_1.target_node_id = code_chunk_node_id_1
        mock_cc_edge_2 = MagicMock()
        mock_cc_edge_2.target_node_id = code_chunk_node_id_2
        mock_cc_edges_result = MagicMock()
        mock_cc_edges_result.scalars.return_value.all.return_value = [mock_cc_edge_1, mock_cc_edge_2]

        # Call 5: Discussion neighbors of ticket node (edges to SlackThread/Meeting)
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
