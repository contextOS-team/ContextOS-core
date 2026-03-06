"""Integration tests for graph extraction orchestrator and backfill.

Tests verify that extract_and_populate_graph creates correct graph nodes
and edges, handles failures silently, deduplicates via fingerprint, and
operates without any LLM calls. Backfill tests verify batch processing
and idempotency.

All tests use mocked graph_ops (upsert_node, upsert_edge) to avoid
database dependencies while verifying orchestration logic.
"""

import ast
import importlib
import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.graph_extractor import extract_and_populate_graph


# ============================================================
# extract_and_populate_graph Tests
# ============================================================


class TestExtractAndPopulateGraph:
    """Tests for the extract_and_populate_graph orchestrator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up common test fixtures."""
        self.workspace_id = uuid.uuid4()
        self.source_id = uuid.uuid4()
        self.session = AsyncMock()

    @pytest.mark.asyncio
    async def test_creates_source_node_and_entity_nodes(self):
        """Content with ENG-123 creates source node + Ticket entity node + edge."""
        source_node_id = uuid.uuid4()
        entity_node_id = uuid.uuid4()
        edge_id = uuid.uuid4()

        with patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock) as mock_upsert_node, \
             patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge:

            mock_upsert_node.side_effect = [source_node_id, entity_node_id]
            mock_upsert_edge.return_value = edge_id

            await extract_and_populate_graph(
                session=self.session,
                workspace_id=self.workspace_id,
                content="Fix bug in ENG-123",
                source_type="slack_message",
                source_id=self.source_id,
                source_name="Slack message in #dev",
                source_external_id="1234567890.123456",
            )

            # Source node + entity node = 2 upsert_node calls
            assert mock_upsert_node.call_count == 2

            # First call: source node (SlackThread for slack_message)
            source_call = mock_upsert_node.call_args_list[0]
            assert source_call.kwargs["entity_type"] == "SlackThread"
            assert source_call.kwargs["external_id"] == "1234567890.123456"
            assert source_call.kwargs["source_type"] == "slack_message"

            # Second call: entity node (Ticket for ENG-123)
            entity_call = mock_upsert_node.call_args_list[1]
            assert entity_call.kwargs["entity_type"] == "Ticket"
            assert entity_call.kwargs["external_id"] == "ENG-123"

            # One edge: source -> entity
            assert mock_upsert_edge.call_count == 1
            edge_call = mock_upsert_edge.call_args_list[0]
            assert edge_call.kwargs["source_node_id"] == source_node_id
            assert edge_call.kwargs["target_node_id"] == entity_node_id
            assert edge_call.kwargs["relationship_type"] == "references"

    @pytest.mark.asyncio
    async def test_empty_content_creates_source_node_only(self):
        """Content with no extractable references still creates the source node."""
        source_node_id = uuid.uuid4()

        with patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock) as mock_upsert_node, \
             patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge:

            mock_upsert_node.return_value = source_node_id

            await extract_and_populate_graph(
                session=self.session,
                workspace_id=self.workspace_id,
                content="Just a regular message with no references",
                source_type="slack_message",
                source_id=self.source_id,
                source_name="Slack message in #general",
            )

            # Only source node created
            assert mock_upsert_node.call_count == 1
            source_call = mock_upsert_node.call_args_list[0]
            assert source_call.kwargs["entity_type"] == "SlackThread"

            # No edges created (no entities extracted)
            assert mock_upsert_edge.call_count == 0

    @pytest.mark.asyncio
    async def test_multiple_entities_creates_all_nodes_and_edges(self):
        """Content with ENG-123 and <@U12345ABC> creates source + 2 entity nodes + 2 edges."""
        source_node_id = uuid.uuid4()
        ticket_node_id = uuid.uuid4()
        person_node_id = uuid.uuid4()
        edge1_id = uuid.uuid4()
        edge2_id = uuid.uuid4()

        with patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock) as mock_upsert_node, \
             patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge:

            mock_upsert_node.side_effect = [source_node_id, ticket_node_id, person_node_id]
            mock_upsert_edge.side_effect = [edge1_id, edge2_id]

            await extract_and_populate_graph(
                session=self.session,
                workspace_id=self.workspace_id,
                content="Hey <@U12345ABC> please look at ENG-123",
                source_type="slack_message",
                source_id=self.source_id,
                source_name="Slack message in #dev",
            )

            # Source node + Ticket node + Person node = 3 upsert_node calls
            assert mock_upsert_node.call_count == 3

            # 2 edges: source -> ticket, source -> person
            assert mock_upsert_edge.call_count == 2

            # Verify entity types
            entity_types = {
                call.kwargs["entity_type"]
                for call in mock_upsert_node.call_args_list[1:]
            }
            assert entity_types == {"Ticket", "Person"}

    @pytest.mark.asyncio
    async def test_failure_does_not_raise(self):
        """extract_and_populate_graph logs warning but never raises on failure."""
        with patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock) as mock_upsert_node:
            mock_upsert_node.side_effect = Exception("DB connection lost")

            # Should NOT raise
            await extract_and_populate_graph(
                session=self.session,
                workspace_id=self.workspace_id,
                content="Fix ENG-123",
                source_type="linear_ticket",
                source_id=self.source_id,
                source_name="ENG-123: Fix the bug",
            )

            # Verify it attempted the call
            assert mock_upsert_node.call_count == 1

    @pytest.mark.asyncio
    async def test_dedup_via_fingerprint(self):
        """Calling twice with same content uses same fingerprint inputs (dedup at DB level)."""
        source_node_id = uuid.uuid4()
        entity_node_id = uuid.uuid4()
        edge_id = uuid.uuid4()

        with patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock) as mock_upsert_node, \
             patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock) as mock_upsert_edge:

            mock_upsert_node.side_effect = [source_node_id, entity_node_id] * 2
            mock_upsert_edge.return_value = edge_id

            # Call twice with identical inputs
            for _ in range(2):
                await extract_and_populate_graph(
                    session=self.session,
                    workspace_id=self.workspace_id,
                    content="Fix ENG-123",
                    source_type="linear_ticket",
                    source_id=self.source_id,
                    source_name="ENG-123: Fix the bug",
                    source_external_id="ENG-123",
                )

            # Both calls use the same external_id for source node
            first_source_call = mock_upsert_node.call_args_list[0]
            second_source_call = mock_upsert_node.call_args_list[2]
            assert first_source_call.kwargs["external_id"] == second_source_call.kwargs["external_id"]
            assert first_source_call.kwargs["external_id"] == "ENG-123"

            # Both calls use the same external_id for entity node
            first_entity_call = mock_upsert_node.call_args_list[1]
            second_entity_call = mock_upsert_node.call_args_list[3]
            assert first_entity_call.kwargs["external_id"] == second_entity_call.kwargs["external_id"]

    @pytest.mark.asyncio
    async def test_source_external_id_fallback(self):
        """When source_external_id is not provided, falls back to str(source_id)."""
        source_node_id = uuid.uuid4()

        with patch("src.services.graph_ops.upsert_node", new_callable=AsyncMock) as mock_upsert_node, \
             patch("src.services.graph_ops.upsert_edge", new_callable=AsyncMock):

            mock_upsert_node.return_value = source_node_id

            await extract_and_populate_graph(
                session=self.session,
                workspace_id=self.workspace_id,
                content="No refs here",
                source_type="slack_message",
                source_id=self.source_id,
                source_name="Slack message",
                # source_external_id not provided
            )

            source_call = mock_upsert_node.call_args_list[0]
            assert source_call.kwargs["external_id"] == str(self.source_id)


class TestNoLLMCalls:
    """Verify that graph extraction is LLM-free."""

    def test_no_llm_imports_in_extraction(self):
        """extract_and_populate_graph module does not import LLM clients."""
        source = inspect.getsource(
            importlib.import_module("src.services.graph_extractor")
        )
        tree = ast.parse(source)

        llm_modules = {"openai", "anthropic", "google.generativeai", "litellm", "langchain"}
        imported_modules: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.split(".")[0])

        overlap = imported_modules & llm_modules
        assert not overlap, f"LLM modules found in graph_extractor: {overlap}"


# ============================================================
# Backfill Script Tests
# ============================================================


class TestBackfillGraph:
    """Tests for the graph backfill script."""

    @pytest.mark.asyncio
    async def test_backfill_handles_empty_tables(self):
        """Backfill with empty tables returns zero counts and no errors."""
        from src.services.graph_backfill import backfill_graph

        mock_session = AsyncMock()
        # Mock the session to return empty results for all queries
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("src.services.graph_backfill.async_session") as mock_session_factory:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_session
            mock_ctx.__aexit__.return_value = False
            mock_session_factory.return_value = mock_ctx

            counts = await backfill_graph(batch_size=10)

            # All counts should be 0
            assert isinstance(counts, dict)
            for key, value in counts.items():
                assert value == 0, f"Expected 0 for {key}, got {value}"

    @pytest.mark.asyncio
    async def test_backfill_is_idempotent(self):
        """Running backfill twice produces the same calls (dedup at DB level)."""
        from src.services.graph_backfill import backfill_graph

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("src.services.graph_backfill.async_session") as mock_session_factory:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_session
            mock_ctx.__aexit__.return_value = False
            mock_session_factory.return_value = mock_ctx

            counts1 = await backfill_graph(batch_size=10)
            counts2 = await backfill_graph(batch_size=10)

            # Same result both times
            assert counts1 == counts2
