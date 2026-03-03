"""Tests for the embedding pipeline: normalization, batching, Redis Streams."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.embedding import (
    BATCH_SIZE,
    generate_embeddings_batch,
)
from src.utils.hashing import compute_content_hash, normalize_for_hash
from src.services.embedding_worker import (
    STREAM_KEY,
    enqueue_embedding_job,
)


# --- Content hash normalization tests ---


def testnormalize_for_hash_collapses_whitespace():
    """Whitespace sequences (spaces, tabs, newlines) collapse to single space."""
    assert normalize_for_hash("hello  \n\t  world") == "hello world"


def testnormalize_for_hash_strips():
    """Leading and trailing whitespace is stripped."""
    assert normalize_for_hash("  hello  ") == "hello"


def testcompute_content_hash_ignores_whitespace_changes():
    """Same hash for text differing only in whitespace."""
    hash_a = compute_content_hash("a b")
    hash_b = compute_content_hash("a  b")
    hash_c = compute_content_hash("a\n\tb")
    assert hash_a == hash_b == hash_c


def testcompute_content_hash_different_for_real_changes():
    """Different hash for text with actual content differences."""
    hash_a = compute_content_hash("a b")
    hash_b = compute_content_hash("a c")
    assert hash_a != hash_b


# --- Batch embedding tests ---


@pytest.mark.asyncio
async def test_generate_embeddings_batch_returns_correct_count():
    """Batch function returns one embedding per input text."""
    mock_embedding_1 = MagicMock()
    mock_embedding_1.index = 0
    mock_embedding_1.embedding = [0.1] * 768

    mock_embedding_2 = MagicMock()
    mock_embedding_2.index = 1
    mock_embedding_2.embedding = [0.2] * 768

    mock_response = MagicMock()
    mock_response.data = [mock_embedding_2, mock_embedding_1]  # Out of order

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    with patch("src.services.embedding._get_openai_client", return_value=mock_client):
        result = await generate_embeddings_batch(["text one", "text two"])

    assert len(result) == 2
    # Should be sorted by index, so index 0 comes first
    assert result[0][0] == pytest.approx(0.1)
    assert result[1][0] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_generate_embeddings_batch_empty_input():
    """Empty list input returns empty list without calling API."""
    result = await generate_embeddings_batch([])
    assert result == []


# --- Redis Streams enqueue test ---


@pytest.mark.asyncio
async def test_enqueue_embedding_job_adds_to_stream():
    """enqueue_embedding_job calls xadd with correct payload."""
    workspace_id = uuid4()
    source_ids = [uuid4(), uuid4()]

    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with patch("src.services.embedding_worker._get_redis", return_value=mock_redis):
        await enqueue_embedding_job(workspace_id, "notion_page", source_ids)

    mock_redis.xadd.assert_called_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == STREAM_KEY

    payload = json.loads(call_args[0][1]["data"])
    assert payload["workspace_id"] == str(workspace_id)
    assert payload["source_type"] == "notion_page"
    assert len(payload["source_ids"]) == 2
    assert payload["source_ids"][0] == str(source_ids[0])


@pytest.mark.asyncio
async def test_enqueue_embedding_job_skips_empty_ids():
    """enqueue_embedding_job does nothing when source_ids is empty."""
    mock_redis = AsyncMock()

    with patch("src.services.embedding_worker._get_redis", return_value=mock_redis):
        await enqueue_embedding_job(uuid4(), "notion_page", [])

    mock_redis.xadd.assert_not_called()


# --- Constants test ---


def test_batch_size_constant():
    """BATCH_SIZE is between 20 and 50 per CONTEXT.md decision."""
    assert 20 <= BATCH_SIZE <= 50
