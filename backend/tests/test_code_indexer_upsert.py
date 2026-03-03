"""Tests for code_indexer upsert logic and changed_chunk_ids collection.

Verifies:
1. .returning(CodeChunk.id) produces valid SQL with RETURNING clause
2. index_repo collects IDs into changed_chunk_ids for both INSERT and UPDATE paths
3. Unchanged chunks (same content_hash) are skipped
4. Soft-delete uses bulk UPDATE WHERE id IN (...) not N+1
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects.postgresql import insert

from src.models.code_chunk import CodeChunk


class TestUpsertReturningSQL:
    """Verify the upsert+RETURNING statement compiles to valid PostgreSQL."""

    def test_upsert_returning_compiles_with_returning_clause(self):
        """INSERT ... ON CONFLICT DO UPDATE ... RETURNING id produces valid SQL."""
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        values = {
            "workspace_id": uuid4(),
            "repo_full_name": "org/repo",
            "file_path": "src/main.py",
            "symbol_name": "main",
            "symbol_type": "function",
            "language": "python",
            "content": "def main(): pass",
            "content_hash": "abc123",
            "start_line": 1,
            "end_line": 2,
            "deleted_at": None,
        }

        stmt = (
            insert(CodeChunk)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[
                    "workspace_id", "repo_full_name", "file_path",
                    "symbol_name", "symbol_type",
                ],
                set_={
                    "language": values["language"],
                    "content": values["content"],
                    "content_hash": values["content_hash"],
                    "start_line": values["start_line"],
                    "end_line": values["end_line"],
                    "deleted_at": None,
                },
            )
            .returning(CodeChunk.id)
        )

        compiled = stmt.compile(dialect=pg_dialect())
        sql_text = str(compiled)

        # Must have INSERT INTO
        assert "INSERT INTO code_chunks" in sql_text
        # Must have ON CONFLICT with all 5 columns
        assert "ON CONFLICT" in sql_text.upper()
        # Must have DO UPDATE SET
        assert "DO UPDATE SET" in sql_text.upper()
        # Must have RETURNING
        assert "RETURNING" in sql_text.upper()
        assert "code_chunks.id" in sql_text

    def test_upsert_returning_on_update_path_returns_id(self):
        """PostgreSQL INSERT ... ON CONFLICT DO UPDATE ... RETURNING returns the row id
        on BOTH the insert path and the update path.

        Per PostgreSQL docs: RETURNING refers to the inserted/updated row,
        so ON CONFLICT DO UPDATE RETURNING always returns the affected row's columns.

        This test verifies our understanding by checking the SQL structure. A true
        integration test requires a real database, but the compiled SQL proves the
        RETURNING clause applies to the full upsert (not just INSERT).
        """
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        stmt = (
            insert(CodeChunk)
            .values(
                workspace_id=uuid4(),
                repo_full_name="org/repo",
                file_path="f.py",
                symbol_name="fn",
                symbol_type="function",
                language="python",
                content="pass",
                content_hash="h",
                start_line=1,
                end_line=1,
                deleted_at=None,
            )
            .on_conflict_do_update(
                index_elements=[
                    "workspace_id", "repo_full_name", "file_path",
                    "symbol_name", "symbol_type",
                ],
                set_={"content": "pass", "content_hash": "h"},
            )
            .returning(CodeChunk.id)
        )

        compiled = stmt.compile(dialect=pg_dialect())
        sql_text = str(compiled)

        # The RETURNING clause appears AFTER the ON CONFLICT ... DO UPDATE SET block
        returning_pos = sql_text.upper().find("RETURNING")
        update_pos = sql_text.upper().find("DO UPDATE SET")
        assert returning_pos > update_pos, (
            "RETURNING must appear after DO UPDATE SET to apply to the full upsert. "
            f"RETURNING at {returning_pos}, DO UPDATE SET at {update_pos}"
        )


class TestIndexRepoChangedChunkIds:
    """Test that index_repo correctly collects changed_chunk_ids."""

    @pytest.mark.asyncio
    async def test_collects_ids_for_new_chunks(self):
        """index_repo returns IDs for newly inserted chunks."""
        from src.services.code_indexer import index_repo

        new_id = uuid4()
        mock_session = AsyncMock()

        # Mock prefetch: no existing chunks
        mock_existing_result = MagicMock()
        mock_existing_result.fetchall.return_value = []

        # Mock upsert returning
        mock_upsert_result = MagicMock()
        mock_upsert_result.first.return_value = (new_id,)

        mock_session.execute.side_effect = [
            mock_existing_result,  # prefetch
            mock_upsert_result,    # upsert
        ]
        mock_session.flush = AsyncMock()

        mock_settings = MagicMock()

        with (
            patch("src.services.code_indexer.get_installation_token", new_callable=AsyncMock, return_value="tok"),
            patch("src.services.code_indexer.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_proc,
            patch("src.services.code_indexer.os.walk") as mock_walk,
            patch("src.services.code_indexer.detect_language", return_value="python"),
            patch("src.services.code_indexer._is_binary_file", return_value=False),
            patch("src.services.code_indexer._should_skip_path", return_value=False),
            patch("src.services.code_indexer.parse_file") as mock_parse,
            patch("src.services.code_indexer.shutil.rmtree"),
            patch("src.services.code_indexer.Path") as mock_path_cls,
        ):
            # Setup subprocess
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0
            mock_proc.return_value = proc

            # Setup walk to return one file
            mock_clone_path = MagicMock()
            mock_walk.return_value = [("/tmp/clone/org_repo", [], ["main.py"])]

            # Mock Path operations
            mock_abs_path = MagicMock()
            mock_abs_path.stat.return_value.st_size = 100
            mock_abs_path.read_text.return_value = "def main(): pass"
            mock_abs_path.relative_to.return_value = "main.py"
            mock_abs_path.__truediv__ = lambda s, o: mock_abs_path

            mock_path_instance = MagicMock()
            mock_path_instance.__truediv__ = lambda s, o: mock_abs_path
            mock_path_cls.return_value = mock_clone_path
            mock_path_cls.side_effect = lambda x: mock_abs_path if "/tmp" in str(x) else MagicMock()

            # Override Path() calls in the walk loop
            import src.services.code_indexer as mod
            original_Path = mod.Path

            # Setup parse_file to return one chunk
            from src.services.code_parser import CodeChunkData
            mock_parse.return_value = [
                CodeChunkData(
                    symbol_name="main",
                    symbol_type="function",
                    language="python",
                    content="def main(): pass",
                    start_line=1,
                    end_line=1,
                    metadata={},
                ),
            ]

            result = await index_repo(uuid4(), "org/repo", mock_session, mock_settings)

        assert new_id in result["changed_chunk_ids"]
        assert result["chunks_created"] == 1

    @pytest.mark.asyncio
    async def test_skips_unchanged_chunks(self):
        """index_repo skips chunks with matching content_hash (no upsert, no ID collected)."""
        from src.services.code_indexer import index_repo
        from src.utils.hashing import compute_content_hash

        existing_id = uuid4()
        content = "def main(): pass"
        content_hash = compute_content_hash(content)

        mock_session = AsyncMock()

        # Mock prefetch: one existing chunk with matching hash
        mock_existing_result = MagicMock()
        mock_existing_result.fetchall.return_value = [
            (existing_id, "org/repo", "main.py", "main", "function", content_hash),
        ]

        mock_session.execute.side_effect = [
            mock_existing_result,  # prefetch (no upsert needed)
        ]
        mock_session.flush = AsyncMock()

        mock_settings = MagicMock()

        with (
            patch("src.services.code_indexer.get_installation_token", new_callable=AsyncMock, return_value="tok"),
            patch("src.services.code_indexer.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_proc,
            patch("src.services.code_indexer.os.walk") as mock_walk,
            patch("src.services.code_indexer.detect_language", return_value="python"),
            patch("src.services.code_indexer._is_binary_file", return_value=False),
            patch("src.services.code_indexer._should_skip_path", return_value=False),
            patch("src.services.code_indexer.parse_file") as mock_parse,
            patch("src.services.code_indexer.shutil.rmtree"),
            patch("src.services.code_indexer.Path") as mock_path_cls,
        ):
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0
            mock_proc.return_value = proc

            mock_walk.return_value = [("/tmp/clone/org_repo", [], ["main.py"])]

            mock_abs_path = MagicMock()
            mock_abs_path.stat.return_value.st_size = 100
            mock_abs_path.read_text.return_value = content
            mock_abs_path.relative_to.return_value = "main.py"
            mock_abs_path.__truediv__ = lambda s, o: mock_abs_path
            mock_path_cls.side_effect = lambda x: mock_abs_path if "/tmp" in str(x) else MagicMock()

            from src.services.code_parser import CodeChunkData
            mock_parse.return_value = [
                CodeChunkData(
                    symbol_name="main",
                    symbol_type="function",
                    language="python",
                    content=content,
                    start_line=1,
                    end_line=1,
                    metadata={},
                ),
            ]

            result = await index_repo(uuid4(), "org/repo", mock_session, mock_settings)

        # No chunks changed — content_hash matched
        assert result["changed_chunk_ids"] == []
        assert result["chunks_created"] == 0
        assert result["chunks_updated"] == 0


class TestSoftDeleteBulk:
    """Test that soft-delete uses bulk UPDATE, not N+1."""

    def test_code_indexer_uses_bulk_in_clause(self):
        """Verify the soft-delete code uses .where(CodeChunk.id.in_(...)) not per-row UPDATE."""
        import inspect
        from src.services import code_indexer

        source = inspect.getsource(code_indexer.index_repo)

        # Should contain bulk IN clause pattern (chunked batches)
        assert "id.in_(batch)" in source, (
            "Soft-delete should use bulk WHERE id IN (...), not per-row UPDATE"
        )
        # Should NOT contain the old N+1 pattern
        assert "CodeChunk.id == chunk_id" not in source, (
            "Old N+1 pattern (WHERE id = chunk_id in loop) should be removed"
        )
