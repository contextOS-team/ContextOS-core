"""Tests for delta-only embedding enqueue in code index worker.

Verifies:
1. Worker enqueues only changed_chunk_ids (not all non-deleted chunks)
2. Worker enqueues nothing when no chunks changed
3. Workspace index collects changed IDs from all repos
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import src.config
from src.config import Settings


WORKSPACE_ID = uuid4()
REPO_FULL_NAME = "acme/backend"


def _inject_test_settings():
    """Inject minimal test settings into the config singleton."""
    if src.config._settings is None:
        src.config._settings = Settings(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test",
            SUPABASE_JWT_SECRET="test-secret",
            ENVIRONMENT="dev",
            NGROK_DOMAIN="",
            BACKEND_URL="http://localhost:8000",
            LINEAR_REDIRECT_URI="",
            SLACK_REDIRECT_URI="",
            GITHUB_REDIRECT_URI="",
            NOTION_REDIRECT_URI="",
            REDIS_URL="redis://localhost:6379/0",
        )


@pytest.mark.asyncio
async def test_worker_enqueues_only_changed_chunk_ids():
    """Worker should enqueue only IDs returned in changed_chunk_ids, not query all chunks."""
    _inject_test_settings()

    from src.services.code_index_worker import _process_index_message

    changed_id_1 = uuid4()
    changed_id_2 = uuid4()

    mock_session = AsyncMock()
    mock_settings = MagicMock()

    message_data = {
        "data": json.dumps({
            "workspace_id": str(WORKSPACE_ID),
            "repo_full_name": REPO_FULL_NAME,
        })
    }

    with (
        patch("src.services.code_index_worker.async_session") as mock_session_ctx,
        patch("src.services.code_index_worker.get_settings", return_value=mock_settings),
        patch("src.services.code_index_worker.index_repo", new_callable=AsyncMock) as mock_index_repo,
        patch("src.services.code_index_worker.enqueue_embedding_job", new_callable=AsyncMock) as mock_enqueue,
    ):
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_index_repo.return_value = {
            "repo": REPO_FULL_NAME,
            "files_scanned": 5,
            "chunks_created": 1,
            "chunks_updated": 1,
            "chunks_deleted": 0,
            "changed_chunk_ids": [changed_id_1, changed_id_2],
        }

        await _process_index_message(message_data)

    # Should enqueue exactly the changed IDs
    mock_enqueue.assert_called_once_with(
        WORKSPACE_ID, "code_chunk", [changed_id_1, changed_id_2]
    )


@pytest.mark.asyncio
async def test_worker_skips_enqueue_when_no_changes():
    """Worker should NOT enqueue embeddings when no chunks changed."""
    _inject_test_settings()

    from src.services.code_index_worker import _process_index_message

    mock_session = AsyncMock()
    mock_settings = MagicMock()

    message_data = {
        "data": json.dumps({
            "workspace_id": str(WORKSPACE_ID),
            "repo_full_name": REPO_FULL_NAME,
        })
    }

    with (
        patch("src.services.code_index_worker.async_session") as mock_session_ctx,
        patch("src.services.code_index_worker.get_settings", return_value=mock_settings),
        patch("src.services.code_index_worker.index_repo", new_callable=AsyncMock) as mock_index_repo,
        patch("src.services.code_index_worker.enqueue_embedding_job", new_callable=AsyncMock) as mock_enqueue,
    ):
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_index_repo.return_value = {
            "repo": REPO_FULL_NAME,
            "files_scanned": 5,
            "chunks_created": 0,
            "chunks_updated": 0,
            "chunks_deleted": 0,
            "changed_chunk_ids": [],
        }

        await _process_index_message(message_data)

    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_workspace_index_collects_all_changed_ids():
    """Workspace __all__ job should collect changed IDs from all repo results."""
    _inject_test_settings()

    from src.services.code_index_worker import _process_index_message

    changed_id_a = uuid4()
    changed_id_b = uuid4()

    mock_session = AsyncMock()
    mock_settings = MagicMock()

    message_data = {
        "data": json.dumps({
            "workspace_id": str(WORKSPACE_ID),
            "repo_full_name": "__all__",
        })
    }

    with (
        patch("src.services.code_index_worker.async_session") as mock_session_ctx,
        patch("src.services.code_index_worker.get_settings", return_value=mock_settings),
        patch(
            "src.services.code_index_worker.index_workspace_repos",
            new_callable=AsyncMock,
        ) as mock_index_workspace,
        patch("src.services.code_index_worker.enqueue_embedding_job", new_callable=AsyncMock) as mock_enqueue,
    ):
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_index_workspace.return_value = [
            {"chunks_created": 1, "chunks_updated": 0, "changed_chunk_ids": [changed_id_a]},
            {"chunks_created": 0, "chunks_updated": 1, "changed_chunk_ids": [changed_id_b]},
        ]

        await _process_index_message(message_data)

    mock_enqueue.assert_called_once_with(
        WORKSPACE_ID, "code_chunk", [changed_id_a, changed_id_b]
    )
