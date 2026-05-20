"""Tests for _bulk_lookup_source_summaries in the linking engine.

Verifies the *current* contract (post privacy-aware rewrite):
1. Groups IDs by source_type and issues one fallback query per type
   (preceded by a single type-agnostic Embedding metadata probe), never
   one query per ID.
2. Returns ``(title, snippet, url)`` 3-tuples keyed by
   ``(source_type, source_id)`` for records that are found.
3. Missing records are simply absent from the result map (callers treat
   absence as "no summary"); there is no synthetic fallback tuple.
4. Unknown source_types issue no source-table query and are absent.
5. Empty input issues no queries at all.

session.execute is dispatched by ORM entity (make_entity_execute) so the
tests don't rot when the lookup grows another internal query.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID, make_entity_execute

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _scalars(rows: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


@pytest.mark.asyncio
async def test_bulk_lookup_groups_by_source_type():
    """Should issue one SELECT per source_type, not one per ID."""
    mock_session = AsyncMock()

    chunk_id_1 = uuid4()
    chunk_id_2 = uuid4()
    slack_id = uuid4()

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

    mock_msg = MagicMock()
    mock_msg.id = slack_id
    mock_msg.user_name = "alice"
    mock_msg.channel_name = "dev"
    mock_msg.text = "Working on the feature"

    # Embedding metadata probe returns nothing -> falls through to the
    # per-source-type batch queries.
    mock_session.execute.side_effect = make_entity_execute(
        {
            "CodeChunk": _scalars([mock_chunk_1, mock_chunk_2]),
            "SlackMessage": _scalars([mock_msg]),
        }
    )

    from src.services.linking import _bulk_lookup_source_summaries

    keys = [
        ("code_chunk", chunk_id_1),
        ("code_chunk", chunk_id_2),
        ("slack_message", slack_id),
    ]

    result = await _bulk_lookup_source_summaries(mock_session, keys)

    assert len(result) == 3

    # Values are (title, snippet, url) 3-tuples.
    title1, _snippet1, _url1 = result[("code_chunk", chunk_id_1)]
    assert "function" in title1
    assert "foo" in title1
    assert "org/repo" in title1

    title2, _snippet2, _url2 = result[("code_chunk", chunk_id_2)]
    assert "class" in title2
    assert "Bar" in title2

    title3, _snippet3, _url3 = result[("slack_message", slack_id)]
    assert "alice" in title3
    assert "dev" in title3

    # Batched by source_type, not per-ID: 3 keys must not yield 3
    # source-table queries. One Embedding probe + one fallback query per
    # source_type present (2) = 3 total, far below one-per-id.
    assert mock_session.execute.call_count == 3


@pytest.mark.asyncio
async def test_bulk_lookup_handles_missing_records():
    """Records not found are absent from the map (no synthetic fallback)."""
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

    mock_session.execute.side_effect = make_entity_execute(
        {"CodeChunk": _scalars([mock_chunk])}
    )

    from src.services.linking import _bulk_lookup_source_summaries

    keys = [
        ("code_chunk", found_id),
        ("code_chunk", missing_id),
    ]

    result = await _bulk_lookup_source_summaries(mock_session, keys)

    # Only the found record is present; the missing one is simply omitted
    # so callers can treat absence as "no summary available".
    assert set(result.keys()) == {("code_chunk", found_id)}
    assert "exists" in result[("code_chunk", found_id)][0]
    assert ("code_chunk", missing_id) not in result


@pytest.mark.asyncio
async def test_bulk_lookup_handles_unknown_source_type():
    """Unknown source_type: no source-table query, absent from result.

    The privacy-aware Phase-1 metadata probe (one type-agnostic Embedding
    query) still runs, but there must be no per-type fallback query for a
    source_type that isn't in _SOURCE_SUMMARY_MAP, and the unknown key
    must not appear in the result map.
    """
    mock_session = AsyncMock()

    unknown_id = uuid4()

    captured_entities: list[str | None] = []
    base_execute = make_entity_execute()

    async def _spy(stmt, *args, **kwargs):
        from tests.conftest import _stmt_entity_name

        captured_entities.append(_stmt_entity_name(stmt))
        return await base_execute(stmt, *args, **kwargs)

    mock_session.execute.side_effect = _spy

    from src.services.linking import _bulk_lookup_source_summaries

    keys = [("unknown_type", unknown_id)]

    result = await _bulk_lookup_source_summaries(mock_session, keys)

    assert ("unknown_type", unknown_id) not in result
    assert result == {}
    # Only the type-agnostic Embedding probe may run; no source table is
    # queried for an unknown source_type.
    assert captured_entities == ["Embedding"]


@pytest.mark.asyncio
async def test_bulk_lookup_empty_input():
    """Empty input should return empty dict without any queries."""
    mock_session = AsyncMock()

    from src.services.linking import _bulk_lookup_source_summaries

    result = await _bulk_lookup_source_summaries(mock_session, [])

    assert result == {}
    mock_session.execute.assert_not_called()
