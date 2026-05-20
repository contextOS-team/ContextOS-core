"""Tests for the embedding generation service.

Covers:
- generate_embedding with mocked Gemini API
- queue_embedding_generation with content hash deduplication
- Skip-unchanged behavior when content hash matches
- process_pending_embeddings bulk backfill

NOTE: src.services.embedding migrated OpenAI -> Google Gemini. The current
contract (see src/services/embedding.py:235-297) is:

    client = _get_gemini_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL_NAME,            # "gemini-embedding-2-preview"
        contents=truncated,                    # str (single) or list[str] (batch)
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(response.embeddings[0].values)               # single
    return [list(e.values) for e in response.embeddings]      # batch

So mocks patch ``src.services.embedding._get_gemini_client`` and shape the
response as ``response.embeddings == [obj(.values=[...]), ...]``.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _mock_gemini_response(*vectors: list[float], dims: int = 768) -> MagicMock:
    """Create a mock Gemini embed_content response.

    Each positional arg is one embedding vector; with no args a single
    768-d vector of 0.1 is returned (the common single-text case).
    """
    if not vectors:
        vectors = ([0.1] * dims,)

    embeddings = []
    for vec in vectors:
        item = MagicMock()
        item.values = list(vec)
        embeddings.append(item)

    mock_response = MagicMock()
    mock_response.embeddings = embeddings
    return mock_response


def _mock_gemini_client(response: MagicMock) -> MagicMock:
    """Build a mock Gemini client whose aio.models.embed_content returns response."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_generate_embedding_calls_gemini() -> None:
    """generate_embedding should call gemini-embedding-2-preview and return 768 floats.

    Provider migrated OpenAI -> Gemini; the behavioral intent (right model,
    768 dims, returns the vector) is preserved against the new contract:
    ``client.aio.models.embed_content(model=..., contents=...,
    config=EmbedContentConfig(output_dimensionality=768))``.
    """
    mock_response = _mock_gemini_response()
    mock_client = _mock_gemini_client(mock_response)

    with patch(
        "src.services.embedding._get_gemini_client", return_value=mock_client
    ):
        from src.services.embedding import (
            EMBEDDING_DIMENSIONS,
            EMBEDDING_MODEL_NAME,
            generate_embedding,
        )

        result = await generate_embedding("test text")

    assert len(result) == 768
    assert result[0] == 0.1
    mock_client.aio.models.embed_content.assert_called_once()
    call_kwargs = mock_client.aio.models.embed_content.call_args.kwargs
    assert call_kwargs["model"] == EMBEDDING_MODEL_NAME == "gemini-embedding-2-preview"
    assert call_kwargs["contents"] == "test text"
    assert (
        call_kwargs["config"].output_dimensionality
        == EMBEDDING_DIMENSIONS
        == 768
    )


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
    mock_response = _mock_gemini_response()
    mock_client = _mock_gemini_client(mock_response)

    with patch(
        "src.services.embedding._get_gemini_client", return_value=mock_client
    ):
        from src.services.embedding import generate_embedding

        long_text = "a" * 50_000
        await generate_embedding(long_text)

    # Current contract truncates to MAX_INPUT_CHARS and passes via `contents=`.
    call_kwargs = mock_client.aio.models.embed_content.call_args.kwargs
    actual_text = call_kwargs["contents"]
    assert len(actual_text) == 30_000


@pytest.mark.asyncio
async def test_queue_embedding_generation_creates_embedding() -> None:
    """queue_embedding_generation should generate and upsert an embedding."""
    mock_session = AsyncMock()
    source_id = uuid4()

    # Mock: bulk source record lookup (scalars().all())
    mock_ticket = MagicMock()
    mock_ticket.id = source_id
    mock_ticket.title = "Test ticket"
    mock_ticket.description = "Test description"
    mock_record_result = MagicMock()
    mock_record_result.scalars.return_value.all.return_value = [mock_ticket]

    # Mock: bulk existing embedding hash lookup (fetchall() returns empty)
    mock_hash_result = MagicMock()
    mock_hash_result.fetchall.return_value = []

    mock_session.execute.side_effect = [
        mock_record_result,  # bulk source record lookup
        mock_hash_result,    # bulk existing hash lookup
        MagicMock(),         # upsert result
    ]

    # queue_embedding_generation -> generate_embeddings_batch (batch path):
    # one input text -> response.embeddings must have one item with .values.
    mock_response = _mock_gemini_response([0.1] * 768)
    mock_client = _mock_gemini_client(mock_response)

    with patch(
        "src.services.embedding._get_gemini_client", return_value=mock_client
    ):
        from src.services.embedding import queue_embedding_generation

        await queue_embedding_generation(
            mock_session, WORKSPACE_ID, "linear_ticket", [source_id]
        )

    # Should have been called 3 times: bulk record lookup, bulk hash check, upsert
    assert mock_session.execute.call_count == 3


@pytest.mark.asyncio
async def test_queue_embedding_skips_unchanged_content() -> None:
    """queue_embedding_generation should skip when content hash matches."""
    mock_session = AsyncMock()
    source_id = uuid4()

    # Source record (bulk lookup)
    mock_ticket = MagicMock()
    mock_ticket.id = source_id
    mock_ticket.title = "Test ticket"
    mock_ticket.description = "Same description"
    mock_record_result = MagicMock()
    mock_record_result.scalars.return_value.all.return_value = [mock_ticket]

    # Compute expected hash using shared utility
    from src.utils.hashing import compute_content_hash
    content = "Test ticket\n\nSame description"
    expected_hash = compute_content_hash(content)

    # Existing embedding has same hash (bulk fetchall)
    mock_hash_result = MagicMock()
    mock_hash_result.fetchall.return_value = [(source_id, expected_hash)]

    mock_session.execute.side_effect = [
        mock_record_result,
        mock_hash_result,
    ]

    from src.services.embedding import queue_embedding_generation

    await queue_embedding_generation(
        mock_session, WORKSPACE_ID, "linear_ticket", [source_id]
    )

    # Should only call execute twice: bulk record lookup + bulk hash check (no upsert)
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
async def test_queue_embedding_stores_search_content() -> None:
    """queue_embedding_generation should include search_content in upsert values."""
    mock_session = AsyncMock()
    source_id = uuid4()

    # Mock: bulk source record lookup
    mock_ticket = MagicMock()
    mock_ticket.id = source_id
    mock_ticket.title = "Test ticket"
    mock_ticket.description = "Test description"
    mock_record_result = MagicMock()
    mock_record_result.scalars.return_value.all.return_value = [mock_ticket]

    # Mock: bulk existing embedding hash lookup (none exists)
    mock_hash_result = MagicMock()
    mock_hash_result.fetchall.return_value = []

    mock_session.execute.side_effect = [
        mock_record_result,  # bulk source record lookup
        mock_hash_result,    # bulk existing hash lookup
        MagicMock(),         # upsert result
    ]

    mock_response = _mock_gemini_response([0.1] * 768)
    mock_client = _mock_gemini_client(mock_response)

    with patch(
        "src.services.embedding._get_gemini_client", return_value=mock_client
    ):
        from src.services.embedding import queue_embedding_generation

        await queue_embedding_generation(
            mock_session, WORKSPACE_ID, "linear_ticket", [source_id]
        )

    # The third execute call is the upsert — inspect the statement
    upsert_call = mock_session.execute.call_args_list[2]
    upsert_stmt = upsert_call[0][0]
    # Check that the compiled parameters include search_content
    compiled = upsert_stmt.compile()
    param_keys = list(compiled.params.keys())
    assert any("search_content" in k for k in param_keys), (
        f"search_content not found in upsert params: {param_keys}"
    )


@pytest.mark.asyncio
async def test_content_hash_deterministic() -> None:
    """compute_content_hash should be deterministic for same input."""
    from src.utils.hashing import compute_content_hash

    hash1 = compute_content_hash("test content")
    hash2 = compute_content_hash("test content")
    hash3 = compute_content_hash("different content")

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64  # SHA-256 hex digest
