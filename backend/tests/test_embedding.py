"""Tests for the embedding generation service.

Covers:
- generate_embedding with mocked OpenAI API
- queue_embedding_generation with content hash deduplication
- Skip-unchanged behavior when content hash matches
- process_pending_embeddings bulk backfill
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _mock_openai_response(dims: int = 768) -> MagicMock:
    """Create a mock OpenAI embeddings response."""
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1] * dims

    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    return mock_response


@pytest.mark.asyncio
async def test_generate_embedding_calls_openai() -> None:
    """generate_embedding should call text-embedding-3-small and return 768 floats."""
    mock_response = _mock_openai_response()

    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    with patch("src.services.embedding._get_openai_client", return_value=mock_client):
        from src.services.embedding import generate_embedding

        result = await generate_embedding("test text")

    assert len(result) == 768
    assert result[0] == 0.1
    mock_client.embeddings.create.assert_called_once()
    call_kwargs = mock_client.embeddings.create.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["dimensions"] == 768


@pytest.mark.asyncio
async def test_generate_embedding_empty_text() -> None:
    """generate_embedding with empty text should return zero vector."""
    from src.services.embedding import generate_embedding

    result = await generate_embedding("   ")
    assert len(result) == 768
    assert all(v == 0.0 for v in result)


@pytest.mark.asyncio
async def test_generate_embedding_truncates_long_text() -> None:
    """generate_embedding should truncate input to MAX_INPUT_CHARS."""
    mock_response = _mock_openai_response()

    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    with patch("src.services.embedding._get_openai_client", return_value=mock_client):
        from src.services.embedding import generate_embedding

        long_text = "a" * 50_000
        await generate_embedding(long_text)

    call_kwargs = mock_client.embeddings.create.call_args.kwargs
    actual_text = call_kwargs["input"]
    assert len(actual_text) == 30_000


@pytest.mark.asyncio
async def test_queue_embedding_generation_creates_embedding() -> None:
    """queue_embedding_generation should generate and upsert an embedding."""
    mock_session = AsyncMock()
    source_id = uuid4()

    # Mock: source record lookup
    mock_ticket = MagicMock()
    mock_ticket.id = source_id
    mock_ticket.title = "Test ticket"
    mock_ticket.description = "Test description"
    mock_record_result = MagicMock()
    mock_record_result.scalar_one_or_none.return_value = mock_ticket

    # Mock: existing embedding hash lookup (none exists)
    mock_hash_result = MagicMock()
    mock_hash_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_record_result,  # source record lookup
        mock_hash_result,  # existing hash lookup
        MagicMock(),  # upsert result
    ]

    mock_response = _mock_openai_response()
    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    with patch("src.services.embedding._get_openai_client", return_value=mock_client):
        from src.services.embedding import queue_embedding_generation

        await queue_embedding_generation(
            mock_session, WORKSPACE_ID, "linear_ticket", [source_id]
        )

    # Should have been called 3 times: record lookup, hash check, upsert
    assert mock_session.execute.call_count == 3


@pytest.mark.asyncio
async def test_queue_embedding_skips_unchanged_content() -> None:
    """queue_embedding_generation should skip when content hash matches."""
    import hashlib

    mock_session = AsyncMock()
    source_id = uuid4()

    # Source record
    mock_ticket = MagicMock()
    mock_ticket.id = source_id
    mock_ticket.title = "Test ticket"
    mock_ticket.description = "Same description"
    mock_record_result = MagicMock()
    mock_record_result.scalar_one_or_none.return_value = mock_ticket

    # Compute expected hash
    content = "Test ticket\n\nSame description"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Existing embedding has same hash
    mock_hash_result = MagicMock()
    mock_hash_result.scalar_one_or_none.return_value = expected_hash

    mock_session.execute.side_effect = [
        mock_record_result,
        mock_hash_result,
    ]

    from src.services.embedding import queue_embedding_generation

    await queue_embedding_generation(
        mock_session, WORKSPACE_ID, "linear_ticket", [source_id]
    )

    # Should only call execute twice: record lookup + hash check (no upsert)
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_queue_embedding_unknown_source_type() -> None:
    """queue_embedding_generation with unknown source_type should log and return."""
    mock_session = AsyncMock()

    from src.services.embedding import queue_embedding_generation

    await queue_embedding_generation(
        mock_session, WORKSPACE_ID, "unknown_type", [uuid4()]
    )

    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_content_hash_deterministic() -> None:
    """_compute_content_hash should be deterministic for same input."""
    from src.services.embedding import _compute_content_hash

    hash1 = _compute_content_hash("test content")
    hash2 = _compute_content_hash("test content")
    hash3 = _compute_content_hash("different content")

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64  # SHA-256 hex digest
