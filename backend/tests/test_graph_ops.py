"""Unit tests for graph_ops service: fingerprint and upsert operations."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.graph_ops import compute_fingerprint, upsert_edge, upsert_node


# ============================================================
# Fingerprint tests (pure function, no DB needed)
# ============================================================


class TestComputeFingerprint:
    """Tests for compute_fingerprint()."""

    def test_deterministic(self):
        """Same inputs always produce the same fingerprint."""
        fp1 = compute_fingerprint("Ticket", "ENG-123")
        fp2 = compute_fingerprint("Ticket", "ENG-123")
        assert fp1 == fp2

    def test_different_types_produce_different_fingerprints(self):
        """Different entity_type + external_id combos produce different hashes."""
        fp_ticket = compute_fingerprint("Ticket", "ENG-123")
        fp_person = compute_fingerprint("Person", "slack:U12345")
        assert fp_ticket != fp_person

    def test_different_ids_same_type(self):
        """Same entity_type with different external_ids produce different hashes."""
        fp1 = compute_fingerprint("Ticket", "ENG-123")
        fp2 = compute_fingerprint("Ticket", "ENG-456")
        assert fp1 != fp2

    def test_format_is_64_char_hex(self):
        """Output is a 64-character hex string (SHA-256 digest)."""
        fp = compute_fingerprint("Person", "slack:U12345")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_format_consistency(self):
        """Verify the fingerprint format is entity_type:external_id hashed."""
        import hashlib

        expected = hashlib.sha256("Ticket:ENG-123".encode()).hexdigest()
        actual = compute_fingerprint("Ticket", "ENG-123")
        assert actual == expected


# ============================================================
# Upsert tests (mock session, verify SQL statements)
# ============================================================


class TestUpsertNode:
    """Tests for upsert_node()."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession that returns a UUID on execute."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = uuid.uuid4()
        session.execute.return_value = mock_result
        return session

    @pytest.mark.asyncio
    async def test_upsert_node_calls_execute(self, mock_session):
        """upsert_node executes a statement against the session."""
        workspace_id = uuid.uuid4()
        result = await upsert_node(
            session=mock_session,
            workspace_id=workspace_id,
            entity_type="Ticket",
            external_id="ENG-123",
            name="Fix login bug",
        )
        assert isinstance(result, uuid.UUID)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_node_builds_correct_statement(self, mock_session):
        """Verify pg_insert is called with correct constraint for ON CONFLICT."""
        workspace_id = uuid.uuid4()

        with patch("src.services.graph_ops.pg_insert") as mock_pg_insert:
            # Chain: pg_insert(Model).values(**v).on_conflict_do_update(...).returning(...)
            mock_insert = MagicMock()
            mock_pg_insert.return_value = mock_insert
            mock_values = MagicMock()
            mock_insert.values.return_value = mock_values
            mock_values.on_conflict_do_update.return_value = mock_values
            mock_values.returning.return_value = mock_values
            mock_values.excluded = MagicMock()

            mock_result = MagicMock()
            mock_result.scalar_one.return_value = uuid.uuid4()
            mock_session.execute.return_value = mock_result

            await upsert_node(
                session=mock_session,
                workspace_id=workspace_id,
                entity_type="Ticket",
                external_id="ENG-123",
                name="Fix login bug",
                properties={"priority": "high"},
            )

            # Verify pg_insert was called with GraphNode
            from src.models.graph_node import GraphNode

            mock_pg_insert.assert_called_once_with(GraphNode)

            # Verify on_conflict_do_update was called with correct constraint
            conflict_call = mock_values.on_conflict_do_update.call_args
            assert conflict_call.kwargs["constraint"] == "graph_nodes_workspace_fingerprint_key"

            # Verify deleted_at=None is in the update set (restores soft-deleted)
            set_dict = conflict_call.kwargs["set_"]
            assert set_dict["deleted_at"] is None

    @pytest.mark.asyncio
    async def test_upsert_node_restores_soft_deleted(self, mock_session):
        """Verify that deleted_at=None is included in the ON CONFLICT update set."""
        with patch("src.services.graph_ops.pg_insert") as mock_pg_insert:
            mock_insert = MagicMock()
            mock_pg_insert.return_value = mock_insert
            mock_values = MagicMock()
            mock_insert.values.return_value = mock_values
            mock_values.on_conflict_do_update.return_value = mock_values
            mock_values.returning.return_value = mock_values
            mock_values.excluded = MagicMock()

            mock_result = MagicMock()
            mock_result.scalar_one.return_value = uuid.uuid4()
            mock_session.execute.return_value = mock_result

            await upsert_node(
                session=mock_session,
                workspace_id=uuid.uuid4(),
                entity_type="Person",
                external_id="slack:U999",
                name="Test User",
            )

            conflict_call = mock_values.on_conflict_do_update.call_args
            set_dict = conflict_call.kwargs["set_"]
            assert "deleted_at" in set_dict
            assert set_dict["deleted_at"] is None


class TestUpsertEdge:
    """Tests for upsert_edge()."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession that returns a UUID on execute."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = uuid.uuid4()
        session.execute.return_value = mock_result
        return session

    @pytest.mark.asyncio
    async def test_upsert_edge_calls_execute(self, mock_session):
        """upsert_edge executes a statement against the session."""
        result = await upsert_edge(
            session=mock_session,
            workspace_id=uuid.uuid4(),
            source_node_id=uuid.uuid4(),
            target_node_id=uuid.uuid4(),
            relationship_type="mentions",
        )
        assert isinstance(result, uuid.UUID)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_edge_builds_correct_statement(self, mock_session):
        """Verify pg_insert is called with correct constraint for ON CONFLICT."""
        with patch("src.services.graph_ops.pg_insert") as mock_pg_insert:
            mock_insert = MagicMock()
            mock_pg_insert.return_value = mock_insert
            mock_values = MagicMock()
            mock_insert.values.return_value = mock_values
            mock_values.on_conflict_do_update.return_value = mock_values
            mock_values.returning.return_value = mock_values
            mock_values.excluded = MagicMock()

            mock_result = MagicMock()
            mock_result.scalar_one.return_value = uuid.uuid4()
            mock_session.execute.return_value = mock_result

            await upsert_edge(
                session=mock_session,
                workspace_id=uuid.uuid4(),
                source_node_id=uuid.uuid4(),
                target_node_id=uuid.uuid4(),
                relationship_type="mentions",
                properties={"confidence": 0.9},
            )

            from src.models.graph_edge import GraphEdge

            mock_pg_insert.assert_called_once_with(GraphEdge)

            conflict_call = mock_values.on_conflict_do_update.call_args
            assert conflict_call.kwargs["constraint"] == "graph_edges_workspace_source_target_type_key"

            # Verify deleted_at=None is in the update set
            set_dict = conflict_call.kwargs["set_"]
            assert set_dict["deleted_at"] is None
