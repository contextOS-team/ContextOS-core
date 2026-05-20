"""Tests for empty Notion page fixes.

Covers:
- Hybrid search drops results whose source record is missing from the DB
- Hybrid search drops results whose source type is unknown
- Embedding extractor returns empty string for NULL content Notion pages
- queue_embedding_generation skips records with empty extracted text
- _soft_delete_empty_notion_embeddings marks orphaned embeddings as deleted
- Notion sync only enqueues embeddings for pages with actual content
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.models.ticket import LinearTicket
from tests.conftest import TEST_WORKSPACE_ID, make_entity_execute, route_textual

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _make_ticket(
    identifier: str = "RD-123",
    title: str = "Модалки накладываются друг на друга",
    description: str = "iOS modal stacking bug on unlock.",
) -> MagicMock:
    """Create a mock LinearTicket that passes isinstance checks."""
    ticket = MagicMock(spec=LinearTicket)
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = identifier
    ticket.title = title
    ticket.description = description
    return ticket


# ---------- Hybrid search drops missing source records ----------


@pytest.mark.asyncio
async def test_hybrid_search_drops_missing_source_records() -> None:
    """If hybrid_search returns an embedding hit whose source record no longer
    exists in the DB, _find_hybrid_matches should silently drop it instead of
    showing a garbage title like 'notion_page' or '[Missing notion_page]'.
    """
    mock_session = AsyncMock()
    ticket = _make_ticket()

    existing_page_id = uuid4()
    missing_page_id = uuid4()

    # _find_hybrid_matches (src/services/linking.py:361) now runs, in order:
    #   1. general hybrid_search()  -> text(), source_type=None
    #   2. dedicated code_chunk hybrid_search() -> text(), source_type="code_chunk"
    #   3. _bulk_lookup_source_summaries:
    #        Phase 1  select(Embedding)  (privacy metadata probe)
    #        Phase 2  select(NotionPage) (fallback to source table)
    # Brittle ordered side_effect lists rot whenever the bulk lookup adds a
    # query, so dispatch by entity / bound params instead.

    def _hybrid(rows):
        r = MagicMock()
        r.fetchall.return_value = rows
        return r

    # general search: 2 notion_page hits; code_chunk search: empty
    general_rows = [
        (uuid4(), "notion_page", existing_page_id, 0.40, 0.0, 0.28, {}),
        (uuid4(), "notion_page", missing_page_id, 0.35, 0.0, 0.25, {}),
    ]

    # Phase 1 Embedding metadata probe -> no rows, so it falls back to the
    # NotionPage source table (Phase 2). Phase 2 finds only the existing page;
    # the missing page is absent from the result map entirely.
    mock_existing_page = MagicMock()
    mock_existing_page.id = existing_page_id
    mock_existing_page.title = "Экран загрузки приложения"
    mock_existing_page.content = "Реальный контент страницы"

    emb_result = MagicMock()
    emb_result.scalars.return_value.all.return_value = []
    notion_result = MagicMock()
    notion_result.scalars.return_value.all.return_value = [mock_existing_page]

    mock_session.execute.side_effect = make_entity_execute(
        results={"Embedding": emb_result, "NotionPage": notion_result},
        textual=route_textual(
            lambda p: _hybrid([])
            if p.get("source_type") == "code_chunk"
            else _hybrid(general_rows)
        ),
    )

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import _find_hybrid_matches

        items = await _find_hybrid_matches(mock_session, WORKSPACE_ID, ticket)

    # Only the existing page should appear
    assert len(items) == 1
    key = list(items.keys())[0]
    assert key == ("notion_page", existing_page_id)
    assert items[key].title == "Экран загрузки приложения"

    # The missing page should NOT appear at all — no garbage titles
    missing_keys = [k for k in items if k[1] == missing_page_id]
    assert missing_keys == []


@pytest.mark.asyncio
async def test_hybrid_search_drops_unknown_source_type() -> None:
    """If hybrid_search returns a hit with an unrecognized source_type,
    _find_hybrid_matches should drop it (no crash, no garbage output).
    """
    mock_session = AsyncMock()
    ticket = _make_ticket()

    def _hybrid(rows):
        r = MagicMock()
        r.fetchall.return_value = rows
        return r

    # general hybrid_search returns one hit with a source_type that's not in
    # _SOURCE_SUMMARY_MAP; code_chunk search empty. _bulk_lookup_source_summaries
    # still runs its Phase 1 select(Embedding) probe (no metadata rows) but
    # skips Phase 2 for the unknown type, so the key never enters the result
    # map and the hit is dropped. Entity dispatch keeps this resilient to the
    # bulk-lookup query count.
    general_rows = [
        (uuid4(), "alien_artifact", uuid4(), 0.90, 0.5, 0.75, {}),
    ]
    emb_result = MagicMock()
    emb_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = make_entity_execute(
        results={"Embedding": emb_result},
        textual=route_textual(
            lambda p: _hybrid([])
            if p.get("source_type") == "code_chunk"
            else _hybrid(general_rows)
        ),
    )

    mock_embedding = [0.1] * 768

    with patch(
        "src.services.linking.generate_embedding",
        new_callable=AsyncMock,
        return_value=mock_embedding,
    ):
        from src.services.linking import _find_hybrid_matches

        items = await _find_hybrid_matches(mock_session, WORKSPACE_ID, ticket)

    assert len(items) == 0


@pytest.mark.asyncio
async def test_bulk_lookup_returns_only_found_records() -> None:
    """_bulk_lookup_source_summaries should only include records it actually
    found in the DB — missing IDs should not appear in the result dict.
    """
    mock_session = AsyncMock()

    found_id = uuid4()
    missing_id = uuid4()

    mock_page = MagicMock()
    mock_page.id = found_id
    mock_page.title = "Real Page"
    mock_page.content = "Real content"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_page]
    mock_session.execute.return_value = mock_result

    from src.services.linking import _bulk_lookup_source_summaries

    summaries = await _bulk_lookup_source_summaries(
        mock_session,
        [("notion_page", found_id), ("notion_page", missing_id)],
    )

    assert ("notion_page", found_id) in summaries
    assert ("notion_page", missing_id) not in summaries


# ---------- Embedding extractor for NULL content ----------


class TestEmbeddingExtractorNullContent:
    """Verify the notion_page extractor returns empty string for NULL content,
    which causes queue_embedding_generation to skip the record entirely.
    """

    def test_returns_empty_for_none_content(self):
        from src.services.embedding import SOURCE_TYPE_MAP

        _, extract_fn = SOURCE_TYPE_MAP["notion_page"]
        page = MagicMock()
        page.title = "Some Title"
        page.content = None

        assert extract_fn(page) == ""

    def test_returns_content_for_real_page(self):
        from src.services.embedding import SOURCE_TYPE_MAP

        _, extract_fn = SOURCE_TYPE_MAP["notion_page"]
        page = MagicMock()
        page.title = "My Page"
        page.content = "Real content here"

        result = extract_fn(page)
        assert "My Page" in result
        assert "Real content here" in result

    def test_returns_title_only_for_empty_string_content(self):
        """Content that is empty string (not None) should still use title."""
        from src.services.embedding import SOURCE_TYPE_MAP

        _, extract_fn = SOURCE_TYPE_MAP["notion_page"]
        page = MagicMock()
        page.title = "Title Only"
        page.content = ""

        result = extract_fn(page)
        # Empty string is falsy, so should return ""
        assert result == ""


@pytest.mark.asyncio
async def test_queue_embedding_generation_skips_empty_text() -> None:
    """queue_embedding_generation must skip records where extracted text is empty.
    This is the safety net for Notion pages with NULL content.
    """
    from src.services.embedding import queue_embedding_generation

    mock_session = AsyncMock()
    page_id = uuid4()

    # Mock source record with no content
    mock_page = MagicMock()
    mock_page.id = page_id
    mock_page.title = "Empty Page"
    mock_page.content = None  # NULL content

    mock_source_result = MagicMock()
    mock_source_result.scalars.return_value.all.return_value = [mock_page]

    # Mock existing hashes (none)
    mock_hash_result = MagicMock()
    mock_hash_result.fetchall.return_value = []

    mock_session.execute.side_effect = [mock_source_result, mock_hash_result]

    with patch(
        "src.services.embedding.generate_embeddings_batch",
        new_callable=AsyncMock,
    ) as mock_gen:
        await queue_embedding_generation(
            mock_session, WORKSPACE_ID, "notion_page", [page_id]
        )

    # Should NOT have called the embedding API — nothing to embed
    mock_gen.assert_not_called()


# ---------- _soft_delete_empty_notion_embeddings ----------


@pytest.mark.asyncio
async def test_soft_delete_empty_notion_embeddings() -> None:
    """_soft_delete_empty_notion_embeddings should execute an UPDATE that
    sets deleted_at on embedding rows whose notion_page has NULL content.
    """
    from src.services.embedding import _soft_delete_empty_notion_embeddings

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 3
    mock_session.execute.return_value = mock_result

    count = await _soft_delete_empty_notion_embeddings(mock_session, WORKSPACE_ID)

    assert count == 3
    # Verify execute was called with the UPDATE statement
    mock_session.execute.assert_called_once()
    call_args = mock_session.execute.call_args
    sql_text = str(call_args[0][0])
    assert "UPDATE embeddings" in sql_text
    assert "content IS NULL" in sql_text
    # Verify workspace_id was passed as parameter
    params = call_args[0][1]
    assert params["workspace_id"] == WORKSPACE_ID


@pytest.mark.asyncio
async def test_soft_delete_returns_zero_when_no_orphans() -> None:
    """When there are no embeddings to clean up, should return 0."""
    from src.services.embedding import _soft_delete_empty_notion_embeddings

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute.return_value = mock_result

    count = await _soft_delete_empty_notion_embeddings(mock_session, WORKSPACE_ID)

    assert count == 0
