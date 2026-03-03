"""Tests for _bulk_lookup_source_summaries in the linking engine.

Verifies:
1. Groups IDs by source_type and issues one query per type
2. Uses model_cls.id.in_(ids) for batch fetch
3. Returns correct (title, snippet) tuples for each (source_type, source_id) key
4. Handles missing records gracefully (fills with fallback)
5. Handles unknown source_types
6. Handles empty input
"""

from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID
from uuid import UUID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


@pytest.mark.asyncio
async def test_bulk_lookup_groups_by_source_type():
    """Should issue one SELECT per source_type, not one per ID."""
    mock_session = AsyncMock()

    chunk_id_1 = uuid4()
    chunk_id_2 = uuid4()
    slack_id = uuid4()

    # Mock code_chunk bulk query
    mock_chunk_1 = MagicMock()
    mock_chunk_1.id = chunk_id_1
    mock_chunk_1.symbol_type = "function"
    mock_chunk_1.symbol_name = "foo"
    mock_chunk_1.repo_full_name = "org/repo"
    mock_chunk_1.file_path = "src/foo.py"
    mock_chunk_1.content = "def foo(): pass"

    mock_chunk_2 = MagicMock()
    mock_chunk_2.id = chunk_id_2
    mock_chunk_2.symbol_type = "class"
    mock_chunk_2.symbol_name = "Bar"
    mock_chunk_2.repo_full_name = "org/repo"
    mock_chunk_2.file_path = "src/bar.py"
    mock_chunk_2.content = "class Bar: pass"

    mock_chunk_result = MagicMock()
    mock_chunk_result.scalars.return_value.all.return_value = [mock_chunk_1, mock_chunk_2]

    # Mock slack_message bulk query
    mock_msg = MagicMock()
    mock_msg.id = slack_id
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"
    mock_msg.text = "Working on the feature"

    mock_slack_result = MagicMock()
    mock_slack_result.scalars.return_value.all.return_value = [mock_msg]

    mock_session.execute.side_effect = [
        mock_chunk_result,  # code_chunk batch query
        mock_slack_result,  # slack_message batch query
    ]

    from src.services.linking import _bulk_lookup_source_summaries

    keys = [
        ("code_chunk", chunk_id_1),
        ("code_chunk", chunk_id_2),
        ("slack_message", slack_id),
    ]

    result = await _bulk_lookup_source_summaries(mock_session, keys)

    # Should have 3 results
    assert len(result) == 3

    # Verify code_chunk summaries
    title1, snippet1 = result[("code_chunk", chunk_id_1)]
    assert "function" in title1
    assert "foo" in title1
    assert "org/repo" in title1

    title2, snippet2 = result[("code_chunk", chunk_id_2)]
    assert "class" in title2
    assert "Bar" in title2

    # Verify slack summary
    title3, snippet3 = result[("slack_message", slack_id)]
    assert "alice" in title3
    assert "dev" in title3

    # Should have issued exactly 2 queries (one per source_type, not 3)
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_bulk_lookup_handles_missing_records():
    """Missing records should get fallback (source_type, '') tuple."""
    mock_session = AsyncMock()

    found_id = uuid4()
    missing_id = uuid4()

    mock_chunk = MagicMock()
    mock_chunk.id = found_id
    mock_chunk.symbol_type = "function"
    mock_chunk.symbol_name = "exists"
    mock_chunk.repo_full_name = "org/repo"
    mock_chunk.file_path = "src/exists.py"
    mock_chunk.content = "def exists(): pass"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_chunk]

    mock_session.execute.side_effect = [mock_result]

    from src.services.linking import _bulk_lookup_source_summaries

    keys = [
        ("code_chunk", found_id),
        ("code_chunk", missing_id),
    ]

    result = await _bulk_lookup_source_summaries(mock_session, keys)

    assert len(result) == 2
    # Found record has real title
    assert "exists" in result[("code_chunk", found_id)][0]
    # Missing record gets fallback
    assert result[("code_chunk", missing_id)] == ("code_chunk", "")


@pytest.mark.asyncio
async def test_bulk_lookup_handles_unknown_source_type():
    """Unknown source_type should get fallback without querying DB."""
    mock_session = AsyncMock()

    unknown_id = uuid4()

    from src.services.linking import _bulk_lookup_source_summaries

    keys = [("unknown_type", unknown_id)]

    result = await _bulk_lookup_source_summaries(mock_session, keys)

    assert result[("unknown_type", unknown_id)] == ("unknown_type", "")
    # Should NOT have queried the database for unknown types
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_lookup_empty_input():
    """Empty input should return empty dict without any queries."""
    mock_session = AsyncMock()

    from src.services.linking import _bulk_lookup_source_summaries

    result = await _bulk_lookup_source_summaries(mock_session, [])

    assert result == {}
    mock_session.execute.assert_not_called()
