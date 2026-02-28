"""Tests for the context page synthesis service.

Covers:
- Context page generation with mocked LLM
- Stale marking
- Prompt building from ticket and sources
- Upsert behavior (create and update)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _make_mock_ticket() -> MagicMock:
    """Create a mock LinearTicket."""
    ticket = MagicMock()
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = "CON-16"
    ticket.title = "Implement context synthesis"
    ticket.description = "Build the AI context page generation pipeline."
    ticket.status = "In Progress"
    ticket.assignee_name = "Alice"
    ticket.priority = 2
    ticket.labels = ["feature", "ai"]
    return ticket


def _make_mock_llm_response() -> MagicMock:
    """Create a mock LLMResponse."""
    response = MagicMock()
    response.text = "# Context: Implement context synthesis\n\nThis is the generated context."
    response.model = "gemini-3-flash-preview"
    response.total_tokens = 1500
    response.prompt_tokens = 1000
    response.completion_tokens = 500
    return response


@pytest.mark.asyncio
async def test_generate_context_page_creates_new() -> None:
    """Should create a new context page when none exists."""
    mock_session = AsyncMock()
    ticket = _make_mock_ticket()

    # Mock ticket lookup
    mock_ticket_result = MagicMock()
    mock_ticket_result.scalar_one_or_none.return_value = ticket

    # Mock existing context page lookup (none exists)
    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_ticket_result,
        mock_existing_result,
    ]

    # Mock linking engine
    mock_linking_result = MagicMock()
    mock_linking_result.items = []

    mock_llm_response = _make_mock_llm_response()

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_llm_response)

    with (
        patch(
            "src.services.synthesis.find_related_content",
            new_callable=AsyncMock,
            return_value=mock_linking_result,
        ),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page

        result = await generate_context_page(mock_session, WORKSPACE_ID, "CON-16")

    # Verify new page was added to session
    mock_session.add.assert_called_once()
    assert result.title == "Context: Implement context synthesis"
    assert result.status == "ready"
    assert result.generation_model == "gemini-3-flash-preview"
    assert result.generation_tokens_used == 1500


@pytest.mark.asyncio
async def test_generate_context_page_updates_existing() -> None:
    """Should update an existing context page rather than creating a new one."""
    mock_session = AsyncMock()
    ticket = _make_mock_ticket()

    # Mock ticket lookup
    mock_ticket_result = MagicMock()
    mock_ticket_result.scalar_one_or_none.return_value = ticket

    # Mock existing context page
    existing_page = MagicMock()
    existing_page.status = "stale"
    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = existing_page

    mock_session.execute.side_effect = [
        mock_ticket_result,
        mock_existing_result,
    ]

    mock_linking_result = MagicMock()
    mock_linking_result.items = []

    mock_llm_response = _make_mock_llm_response()
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_llm_response)

    with (
        patch(
            "src.services.synthesis.find_related_content",
            new_callable=AsyncMock,
            return_value=mock_linking_result,
        ),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page

        result = await generate_context_page(mock_session, WORKSPACE_ID, "CON-16")

    # Should NOT add a new record (updates existing)
    mock_session.add.assert_not_called()
    assert existing_page.status == "ready"
    assert existing_page.generation_model == "gemini-3-flash-preview"


@pytest.mark.asyncio
async def test_generate_context_page_ticket_not_found() -> None:
    """Should raise ValueError when ticket doesn't exist."""
    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session.execute.return_value = mock_result

    from src.services.synthesis import generate_context_page

    with pytest.raises(ValueError, match="Ticket CON-99 not found"):
        await generate_context_page(mock_session, WORKSPACE_ID, "CON-99")


@pytest.mark.asyncio
async def test_generate_context_page_includes_sources() -> None:
    """Should include source information in the generated context page."""
    mock_session = AsyncMock()
    ticket = _make_mock_ticket()

    mock_ticket_result = MagicMock()
    mock_ticket_result.scalar_one_or_none.return_value = ticket

    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_ticket_result,
        mock_existing_result,
    ]

    # Create mock linked items
    mock_item = MagicMock()
    mock_item.source_type = "slack_message"
    mock_item.source_id = uuid4()
    mock_item.title = "Slack message by Alice"
    mock_item.snippet = "We should use embeddings for search"
    mock_item.relevance_score = 0.85
    mock_item.signals = ["explicit_reference", "semantic_similarity"]

    mock_linking_result = MagicMock()
    mock_linking_result.items = [mock_item]

    mock_llm_response = _make_mock_llm_response()
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_llm_response)

    with (
        patch(
            "src.services.synthesis.find_related_content",
            new_callable=AsyncMock,
            return_value=mock_linking_result,
        ),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page

        result = await generate_context_page(mock_session, WORKSPACE_ID, "CON-16")

    added_page = mock_session.add.call_args[0][0]
    assert len(added_page.sources) == 1
    assert added_page.sources[0]["type"] == "slack_message"
    assert added_page.sources[0]["relevance_score"] == 0.85


@pytest.mark.asyncio
async def test_mark_context_stale() -> None:
    """Should set context page status to 'stale'."""
    mock_session = AsyncMock()
    ticket_id = uuid4()

    mock_page = MagicMock()
    mock_page.status = "ready"
    mock_page.ticket_identifier = "CON-16"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_page

    mock_session.execute.return_value = mock_result

    from src.services.synthesis import mark_context_stale

    await mark_context_stale(mock_session, WORKSPACE_ID, ticket_id)

    assert mock_page.status == "stale"


@pytest.mark.asyncio
async def test_mark_context_stale_no_page() -> None:
    """Should be a no-op when no context page exists."""
    mock_session = AsyncMock()
    ticket_id = uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session.execute.return_value = mock_result

    from src.services.synthesis import mark_context_stale

    # Should not raise
    await mark_context_stale(mock_session, WORKSPACE_ID, ticket_id)


@pytest.mark.asyncio
async def test_prompt_includes_ticket_details() -> None:
    """The LLM prompt should include ticket identifier, title, and description."""
    mock_session = AsyncMock()
    ticket = _make_mock_ticket()

    mock_ticket_result = MagicMock()
    mock_ticket_result.scalar_one_or_none.return_value = ticket

    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_ticket_result,
        mock_existing_result,
    ]

    mock_linking_result = MagicMock()
    mock_linking_result.items = []

    mock_llm_response = _make_mock_llm_response()
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_llm_response)

    with (
        patch(
            "src.services.synthesis.find_related_content",
            new_callable=AsyncMock,
            return_value=mock_linking_result,
        ),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page

        await generate_context_page(mock_session, WORKSPACE_ID, "CON-16")

    # Check the prompt passed to LLM
    call_kwargs = mock_llm.generate.call_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "CON-16" in prompt
    assert "Implement context synthesis" in prompt
    assert "Build the AI context page generation pipeline" in prompt
    assert "Alice" in prompt
