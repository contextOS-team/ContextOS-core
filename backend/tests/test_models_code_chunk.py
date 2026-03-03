"""Tests for CodeChunk model.

Covers:
- CodeChunk instantiation with all required fields
- JSONB metadata_ field defaults to empty dict
- Unique constraint on (repo_full_name, file_path, symbol_name, symbol_type)
"""

import uuid

import pytest

from src.models.code_chunk import CodeChunk


class TestCodeChunkModel:
    """Test CodeChunk SQLModel mapping."""

    def test_instantiation_with_all_required_fields(self):
        """CodeChunk model can be instantiated with all required fields."""
        chunk = CodeChunk(
            workspace_id=uuid.uuid4(),
            repo_full_name="org/repo",
            file_path="src/services/auth.py",
            symbol_name="authenticate_user",
            symbol_type="function",
            language="python",
            content="def authenticate_user(token: str) -> User:\n    pass",
            content_hash="abc123hash",
            start_line=10,
            end_line=12,
        )
        assert chunk.repo_full_name == "org/repo"
        assert chunk.file_path == "src/services/auth.py"
        assert chunk.symbol_name == "authenticate_user"
        assert chunk.symbol_type == "function"
        assert chunk.language == "python"
        assert chunk.content == "def authenticate_user(token: str) -> User:\n    pass"
        assert chunk.content_hash == "abc123hash"
        assert chunk.start_line == 10
        assert chunk.end_line == 12
        assert chunk.workspace_id is not None
        # BaseModel provides id
        assert chunk.id is not None

    def test_metadata_defaults_to_empty_dict(self):
        """CodeChunk metadata_ field defaults to empty dict."""
        chunk = CodeChunk(
            workspace_id=uuid.uuid4(),
            repo_full_name="org/repo",
            file_path="src/main.py",
            symbol_name="main",
            symbol_type="function",
            language="python",
            content="def main():\n    pass",
            content_hash="def456hash",
            start_line=1,
            end_line=2,
        )
        assert chunk.metadata_ == {}

    def test_unique_constraint_in_table_args(self):
        """Unique constraint on (repo_full_name, file_path, symbol_name, symbol_type) exists."""
        table_args = CodeChunk.__table_args__
        # Find the UniqueConstraint
        from sqlalchemy import UniqueConstraint

        unique_constraints = [
            arg for arg in table_args if isinstance(arg, UniqueConstraint)
        ]
        assert len(unique_constraints) >= 1

        # Check the constraint columns
        uc = unique_constraints[0]
        col_names = [col.name for col in uc.columns]
        assert "repo_full_name" in col_names
        assert "file_path" in col_names
        assert "symbol_name" in col_names
        assert "symbol_type" in col_names

    def test_tablename_is_code_chunks(self):
        """CodeChunk maps to the code_chunks table."""
        assert CodeChunk.__tablename__ == "code_chunks"
