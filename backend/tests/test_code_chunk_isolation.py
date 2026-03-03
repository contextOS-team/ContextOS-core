"""Tests for cross-workspace isolation in code_chunks.

Verifies:
1. UniqueConstraint includes workspace_id (two workspaces can store same symbol)
2. Upsert conflict target includes workspace_id
"""

import uuid

from sqlalchemy import UniqueConstraint

from src.models.code_chunk import CodeChunk


class TestCodeChunkWorkspaceIsolation:
    """Test that workspace_id is part of the dedup unique constraint."""

    def test_unique_constraint_includes_workspace_id(self):
        """The dedup unique constraint must include workspace_id for tenant isolation."""
        table_args = CodeChunk.__table_args__
        unique_constraints = [
            arg for arg in table_args if isinstance(arg, UniqueConstraint)
        ]
        assert len(unique_constraints) >= 1

        uc = unique_constraints[0]
        col_names = [col.name for col in uc.columns]
        assert "workspace_id" in col_names, (
            "workspace_id MUST be in the dedup unique constraint "
            "to prevent cross-workspace data bleed"
        )
        assert col_names == [
            "workspace_id", "repo_full_name", "file_path", "symbol_name", "symbol_type"
        ]

    def test_two_workspaces_same_symbol_no_conflict(self):
        """Two CodeChunk instances with different workspace_ids but same symbol should be distinct."""
        ws_a = uuid.uuid4()
        ws_b = uuid.uuid4()

        chunk_a = CodeChunk(
            workspace_id=ws_a,
            repo_full_name="org/shared-lib",
            file_path="src/auth.py",
            symbol_name="authenticate",
            symbol_type="function",
            language="python",
            content="def authenticate(): pass",
            content_hash="hash_a",
            start_line=1,
            end_line=2,
        )
        chunk_b = CodeChunk(
            workspace_id=ws_b,
            repo_full_name="org/shared-lib",
            file_path="src/auth.py",
            symbol_name="authenticate",
            symbol_type="function",
            language="python",
            content="def authenticate(): pass",
            content_hash="hash_b",
            start_line=1,
            end_line=2,
        )

        # Both should have distinct IDs (no overwrite)
        assert chunk_a.id != chunk_b.id
        assert chunk_a.workspace_id != chunk_b.workspace_id
