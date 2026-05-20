"""Tests for Jira ticket support in the context generation pipeline.

Covers:
- TicketProxy field mapping from JiraIssue
- Priority label passthrough for string priorities
- generate_context_page falls back to Jira when Linear lookup misses
- generate_context_page raises ValueError when both miss
- ContextPage.ticket_id is None for Jira-sourced pages (FK only valid for Linear)
- _jql_search response parsing and error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _added_context_page(mock_session):
    """Return the ContextPage passed to session.add().

    generate_context_page now side-writes an AuditLog (log_audit_event ->
    session.add(AuditLog(...))) in addition to the ContextPage placeholder
    (synthesis.py:577, 824-836). Selecting mock_session.add.call_args[0][0]
    would grab the *last* add call (the AuditLog), so filter add() calls by
    ContextPage type instead of relying on call order.
    """
    from src.models.context_page import ContextPage

    for call in mock_session.add.call_args_list:
        arg = call[0][0]
        if isinstance(arg, ContextPage):
            return arg
    raise AssertionError("ContextPage was never added to the session")


# ---------------------------------------------------------------------------
# TicketProxy
# ---------------------------------------------------------------------------


class TestTicketProxy:
    def test_from_jira_maps_fields(self):
        from src.services.synthesis import TicketProxy

        issue = MagicMock()
        issue.id = uuid4()
        issue.jira_key = "PROJ-42"
        issue.summary = "Fix login bug"
        issue.description = "Users can't log in"
        issue.status = "In Progress"
        issue.assignee_name = "Bob"
        issue.priority = "High"
        issue.labels = ["bug", "auth"]

        proxy = TicketProxy.from_jira(issue)

        assert proxy.id == issue.id
        assert proxy.identifier == "PROJ-42"
        assert proxy.title == "Fix login bug"
        assert proxy.description == "Users can't log in"
        assert proxy.status == "In Progress"
        assert proxy.assignee_name == "Bob"
        assert proxy.priority == "High"  # string passthrough, not int
        assert proxy.labels == ["bug", "auth"]

    def test_from_jira_none_priority(self):
        from src.services.synthesis import TicketProxy

        issue = MagicMock()
        issue.id = uuid4()
        issue.jira_key = "PROJ-1"
        issue.summary = "No priority"
        issue.description = None
        issue.status = None
        issue.assignee_name = None
        issue.priority = None
        issue.labels = None

        proxy = TicketProxy.from_jira(issue)
        assert proxy.priority is None
        assert proxy.labels is None


# ---------------------------------------------------------------------------
# _priority_label
# ---------------------------------------------------------------------------


class TestPriorityLabel:
    def test_linear_int_priorities(self):
        from src.services.synthesis import _priority_label

        assert _priority_label(1) == "Urgent"
        assert _priority_label(2) == "High"
        assert _priority_label(3) == "Normal"
        assert _priority_label(4) == "Low"
        assert _priority_label(0) == "None"

    def test_jira_string_priorities(self):
        from src.services.synthesis import _priority_label

        assert _priority_label("High") == "High"
        assert _priority_label("Medium") == "Medium"
        assert _priority_label("Lowest") == "Lowest"

    def test_none_priority(self):
        from src.services.synthesis import _priority_label

        assert _priority_label(None) == "None"


# ---------------------------------------------------------------------------
# generate_context_page — Jira fallback
# ---------------------------------------------------------------------------


def _make_jira_issue():
    issue = MagicMock()
    issue.id = uuid4()
    issue.jira_key = "PROJ-42"
    issue.summary = "Fix login bug"
    issue.description = "Users can't log in via SSO"
    issue.status = "In Progress"
    issue.assignee_name = "Bob"
    issue.priority = "High"
    issue.labels = ["bug"]
    return issue


@pytest.mark.asyncio
async def test_generate_context_page_jira_fallback():
    """When Linear lookup returns None, should fall back to JiraIssue."""
    mock_session = AsyncMock()
    jira_issue = _make_jira_issue()

    # First call: LinearTicket lookup -> None
    linear_result = MagicMock()
    linear_result.scalar_one_or_none.return_value = None

    # Second call: JiraIssue lookup -> found
    jira_result = MagicMock()
    jira_result.scalar_one_or_none.return_value = jira_issue

    # Third call: existing ContextPage -> None
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [linear_result, jira_result, existing_result]

    mock_linking = MagicMock()
    mock_linking.items = []

    mock_llm_response = MagicMock()
    mock_llm_response.text = "Generated context for Jira issue."
    mock_llm_response.model = "test-model"
    mock_llm_response.total_tokens = 100
    mock_llm_response.prompt_tokens = 50
    mock_llm_response.completion_tokens = 50

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_llm_response)

    with (
        patch("src.services.synthesis.find_related_content", new_callable=AsyncMock, return_value=mock_linking),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page

        result = await generate_context_page(mock_session, WORKSPACE_ID, "PROJ-42")

    # ContextPage was added with ticket_id=None (no Linear FK)
    added_page = _added_context_page(mock_session)
    assert added_page.ticket_id is None
    assert added_page.ticket_identifier == "PROJ-42"
    assert result.title == "Context: Fix login bug"

    # LLM prompt should contain Jira priority string, not a mapped int
    prompt = mock_llm.generate.call_args.kwargs["prompt"]
    assert "High" in prompt
    assert "PROJ-42" in prompt
    assert "Fix login bug" in prompt


@pytest.mark.asyncio
async def test_generate_context_page_both_miss():
    """When both Linear and Jira lookups return None, should raise ValueError."""
    mock_session = AsyncMock()

    none_result = MagicMock()
    none_result.scalar_one_or_none.return_value = None

    # Both Linear and Jira return None
    mock_session.execute.side_effect = [none_result, none_result]

    from src.services.synthesis import generate_context_page

    with pytest.raises(ValueError, match="Ticket NOPE-1 not found"):
        await generate_context_page(mock_session, WORKSPACE_ID, "NOPE-1")


# ---------------------------------------------------------------------------
# _jql_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jql_search_parses_response():
    """_jql_search should parse Jira API response into normalised dicts."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "issues": [
            {
                "id": "10001",
                "key": "PROJ-1",
                "fields": {
                    "summary": "Test issue",
                    "status": {"name": "Done"},
                    "assignee": {"displayName": "Alice"},
                    "issuetype": {"name": "Bug"},
                },
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.services.jira_sync.httpx.AsyncClient", return_value=mock_client):
        from src.services.jira_sync import _jql_search

        results = await _jql_search("token", "cloud-id", "ORDER BY updated DESC")

    assert len(results) == 1
    assert results[0]["key"] == "PROJ-1"
    assert results[0]["summary"] == "Test issue"
    assert results[0]["status"] == "Done"
    assert results[0]["assignee"] == "Alice"
    assert results[0]["issue_type"] == "Bug"


@pytest.mark.asyncio
async def test_jql_search_returns_empty_on_error():
    """_jql_search should return [] on non-200 response, not crash."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad JQL"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.services.jira_sync.httpx.AsyncClient", return_value=mock_client):
        from src.services.jira_sync import _jql_search

        results = await _jql_search("token", "cloud-id", "invalid jql")

    assert results == []


@pytest.mark.asyncio
async def test_jql_search_handles_null_fields():
    """_jql_search should handle issues with null status/assignee/issuetype."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "issues": [
            {
                "id": "10002",
                "key": "PROJ-2",
                "fields": {
                    "summary": "Bare issue",
                    "status": None,
                    "assignee": None,
                    "issuetype": None,
                },
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.services.jira_sync.httpx.AsyncClient", return_value=mock_client):
        from src.services.jira_sync import _jql_search

        results = await _jql_search("token", "cloud-id", "key = PROJ-2")

    assert results[0]["status"] is None
    assert results[0]["assignee"] is None
    assert results[0]["issue_type"] is None
