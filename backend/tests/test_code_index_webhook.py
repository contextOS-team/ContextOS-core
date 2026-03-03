"""Tests for code index worker (Redis Streams) and push webhook handler.

Verifies:
1. enqueue_code_index_job() adds a message to the code_index:jobs Redis stream
2. _process_index_message() calls index_repo() with correct args
3. process_push_event() enqueues a code index job for monitored repos
4. process_push_event() skips unmonitored repos (does not enqueue)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import src.config
from src.config import Settings


WORKSPACE_ID = uuid4()
REPO_FULL_NAME = "acme/backend"
INSTALLATION_ID = 12345


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
async def test_enqueue_code_index_job_calls_xadd():
    """enqueue_code_index_job() adds a message to the code_index:jobs stream."""
    _inject_test_settings()

    from src.services.code_index_worker import enqueue_code_index_job, STREAM_KEY

    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with patch("src.services.code_index_worker._get_redis", return_value=mock_redis):
        await enqueue_code_index_job(WORKSPACE_ID, REPO_FULL_NAME)

    mock_redis.xadd.assert_called_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == STREAM_KEY

    payload = json.loads(call_args[0][1]["data"])
    assert payload["workspace_id"] == str(WORKSPACE_ID)
    assert payload["repo_full_name"] == REPO_FULL_NAME
    mock_redis.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_process_index_message_calls_index_repo():
    """_process_index_message() calls index_repo() with correct workspace_id and repo_full_name."""
    _inject_test_settings()

    from src.services.code_index_worker import _process_index_message

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_settings = MagicMock()

    message_data = {
        "data": json.dumps({
            "workspace_id": str(WORKSPACE_ID),
            "repo_full_name": REPO_FULL_NAME,
        })
    }

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    with (
        patch("src.services.code_index_worker.async_session") as mock_session_ctx,
        patch("src.services.code_index_worker.get_settings", return_value=mock_settings),
        patch("src.services.code_index_worker.index_repo", new_callable=AsyncMock) as mock_index_repo,
        patch("src.services.code_index_worker.enqueue_embedding_job", new_callable=AsyncMock),
    ):
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_index_repo.return_value = {
            "repo": REPO_FULL_NAME,
            "files_scanned": 5,
            "chunks_created": 10,
            "chunks_updated": 2,
            "chunks_deleted": 1,
        }

        await _process_index_message(message_data)

    mock_index_repo.assert_called_once_with(
        WORKSPACE_ID, REPO_FULL_NAME, mock_session, mock_settings
    )


@pytest.mark.asyncio
async def test_process_push_event_enqueues_for_monitored_repo():
    """process_push_event() enqueues a code index job for monitored repos."""
    _inject_test_settings()

    from src.services.github_webhook import process_push_event

    payload = {
        "installation": {"id": INSTALLATION_ID},
        "repository": {"full_name": REPO_FULL_NAME},
        "ref": "refs/heads/main",
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("src.services.github_webhook.async_session") as mock_session_ctx,
        patch(
            "src.services.github_webhook._lookup_workspace_from_installation",
            new_callable=AsyncMock,
            return_value=WORKSPACE_ID,
        ),
        patch(
            "src.services.github_webhook.is_repo_monitored",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.services.github_webhook.enqueue_code_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await process_push_event(payload)

    mock_enqueue.assert_called_once_with(WORKSPACE_ID, REPO_FULL_NAME)


@pytest.mark.asyncio
async def test_process_push_event_skips_unmonitored_repo():
    """process_push_event() does NOT enqueue for unmonitored repos."""
    _inject_test_settings()

    from src.services.github_webhook import process_push_event

    payload = {
        "installation": {"id": INSTALLATION_ID},
        "repository": {"full_name": "acme/unmonitored-repo"},
        "ref": "refs/heads/main",
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("src.services.github_webhook.async_session") as mock_session_ctx,
        patch(
            "src.services.github_webhook._lookup_workspace_from_installation",
            new_callable=AsyncMock,
            return_value=WORKSPACE_ID,
        ),
        patch(
            "src.services.github_webhook.is_repo_monitored",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.services.github_webhook.enqueue_code_index_job",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await process_push_event(payload)

    mock_enqueue.assert_not_called()
