"""Tests for generate_context_page_stream — source detection, sync awareness, and SSE events.

Covers the fixes for:
- Bug 1: Linear was hardcoded as always-connected; now dynamic based on ticket type
- Bug 2: GitLab was missing from the source pipeline
- Bug 3: Sync-in-progress detection used wrong status string ("in_progress" vs "syncing")
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_WORKSPACE_ID

WORKSPACE_ID = UUID(TEST_WORKSPACE_ID)


def _make_jira_issue() -> MagicMock:
    """Create a mock JiraIssue."""
    issue = MagicMock()
    issue.id = uuid4()
    issue.workspace_id = WORKSPACE_ID
    issue.jira_key = "RD-123"
    issue.summary = "Fix modal overlay on device unlock"
    issue.description = "Modals stack on each other when unlocking the device."
    issue.status = "In Progress"
    issue.assignee_display_name = "Bob"
    issue.priority = "High"
    issue.labels = ["bug", "ios"]
    issue.issue_type = "Bug"
    return issue


def _make_linear_ticket() -> MagicMock:
    """Create a mock LinearTicket."""
    ticket = MagicMock()
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = "CON-42"
    ticket.title = "Add search to dashboard"
    ticket.description = "Users need full-text search."
    ticket.status = "In Progress"
    ticket.assignee_name = "Alice"
    ticket.priority = 2
    ticket.labels = ["feature"]
    return ticket


def _mock_execute_returning(return_map: list):
    """Build a side_effect list for session.execute() from return specs.

    Each entry is either:
    - ("scalar_one_or_none", value): for .scalar_one_or_none()
    - ("fetchall", rows): for .fetchall() — rows is a list of tuples
    """
    results = []
    for kind, value in return_map:
        mock_result = MagicMock()
        if kind == "scalar_one_or_none":
            mock_result.scalar_one_or_none.return_value = value
        elif kind == "fetchall":
            mock_result.fetchall.return_value = value
        else:
            raise ValueError(f"Unknown kind: {kind}")
        results.append(mock_result)
    return results


def _make_llm_response() -> MagicMock:
    response = MagicMock()
    response.text = "# Context\n\nGenerated context."
    response.model = "gemini-3-flash-preview"
    response.total_tokens = 500
    response.prompt_tokens = 400
    response.completion_tokens = 100
    return response


async def _collect_events(stream):
    """Drain an async generator into a list."""
    events = []
    async for event in stream:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Test 1: Jira ticket → connected_sources has "jira", NOT "linear"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jira_ticket_shows_jira_not_linear():
    """When the ticket is a Jira issue, the start event should list 'jira'
    and must NOT list 'linear'."""
    session = AsyncMock()
    jira_issue = _make_jira_issue()

    # session.execute call sequence for Jira path:
    # 1. LinearTicket lookup → None
    # 2. JiraIssue lookup → jira_issue
    # 3. OAuthToken providers → [("jira",), ("notion",)]
    # 4. WorkspaceIntegration providers → []
    # 5. SyncCursor sync check → []
    # 6. ContextPage lookup → None (new page)
    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", None),          # 1. No LinearTicket
        ("scalar_one_or_none", jira_issue),    # 2. JiraIssue found
        ("fetchall", [("jira",), ("notion",)]),  # 3. OAuth tokens
        ("fetchall", []),                       # 4. WorkspaceIntegrations
        ("fetchall", []),                       # 5. No syncing providers
        ("scalar_one_or_none", None),          # 6. No existing context page
    ])

    async def _empty_find_content(*args, **kwargs):
        # Yield jira and notion with empty results (matching connected_sources)
        yield "jira", [], "No items found"
        yield "notion", [], "No pages found"
        # Also yield linear — should be filtered out
        yield "linear", [], "No comments found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _empty_find_content),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "RD-123")
        )

    # Find the start event
    start_events = [e for e in events if e.get("event") == "start"]
    assert len(start_events) == 1
    steps = start_events[0]["steps"]

    assert "jira" in steps, f"'jira' missing from steps: {steps}"
    assert "notion" in steps, f"'notion' missing from steps: {steps}"
    assert "linear" not in steps, f"'linear' should NOT be in steps: {steps}"
    assert "synthesize" in steps

    # Verify linear step_complete was NOT emitted
    step_sources = [e["source"] for e in events if e.get("event") == "step_complete"]
    assert "linear" not in step_sources


# ---------------------------------------------------------------------------
# Test 2: Linear ticket → connected_sources has "linear", NOT "jira"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_linear_ticket_shows_linear_not_jira():
    """When the ticket is a Linear ticket, the start event should list 'linear'
    and must NOT list 'jira' (unless Jira is also connected as OAuth)."""
    session = AsyncMock()
    linear_ticket = _make_linear_ticket()

    # Linear path: only one execute for ticket lookup (found on first try)
    # 1. LinearTicket lookup → found
    # 2. OAuthToken providers → [("slack",)]
    # 3. WorkspaceIntegration providers → []
    # 4. SyncCursor sync check → []
    # 5. ContextPage lookup → None
    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", linear_ticket),  # 1. LinearTicket found
        ("fetchall", [("slack",)]),              # 2. OAuth tokens
        ("fetchall", []),                        # 3. WorkspaceIntegrations
        ("fetchall", []),                        # 4. No syncing
        ("scalar_one_or_none", None),           # 5. No existing page
    ])

    async def _empty_find_content(*args, **kwargs):
        yield "linear", [], "No comments found"
        yield "slack", [], "No messages found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _empty_find_content),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "CON-42")
        )

    start = [e for e in events if e.get("event") == "start"][0]
    steps = start["steps"]

    assert "linear" in steps
    assert "slack" in steps
    assert "jira" not in steps


# ---------------------------------------------------------------------------
# Test 3: GitLab appears when connected via OAuth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gitlab_appears_when_connected():
    """GitLab should appear in steps when an OAuth token exists for it."""
    session = AsyncMock()
    jira_issue = _make_jira_issue()

    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", None),           # 1. No LinearTicket
        ("scalar_one_or_none", jira_issue),     # 2. JiraIssue found
        ("fetchall", [("jira",), ("gitlab",)]),  # 3. OAuth: jira + gitlab
        ("fetchall", []),                        # 4. No WorkspaceIntegrations
        ("fetchall", []),                        # 5. No syncing
        ("scalar_one_or_none", None),           # 6. No existing page
    ])

    async def _find_with_gitlab(*args, **kwargs):
        yield "jira", [], "No items found"
        yield "gitlab", [], "No MRs or reviews found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _find_with_gitlab),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "RD-123")
        )

    start = [e for e in events if e.get("event") == "start"][0]
    assert "gitlab" in start["steps"]

    # Verify gitlab step_complete was emitted
    gitlab_completes = [
        e for e in events
        if e.get("event") == "step_complete" and e.get("source") == "gitlab"
    ]
    assert len(gitlab_completes) == 1


# ---------------------------------------------------------------------------
# Test 4: Sync-in-progress detection uses "syncing" (not "in_progress")
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_syncing_notion_shows_sync_warning():
    """When Notion has a SyncCursor with sync_status='syncing' and 0 results,
    the step_complete should have syncing=True and an appropriate detail message."""
    session = AsyncMock()
    jira_issue = _make_jira_issue()

    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", None),           # 1. No LinearTicket
        ("scalar_one_or_none", jira_issue),     # 2. JiraIssue found
        ("fetchall", [("jira",), ("notion",)]),  # 3. OAuth tokens
        ("fetchall", []),                        # 4. No WorkspaceIntegrations
        ("fetchall", [("notion", "syncing")]),   # 5. Notion is syncing!
        ("scalar_one_or_none", None),           # 6. No existing page
    ])

    async def _empty_find_content(*args, **kwargs):
        yield "jira", [], "No items found"
        yield "notion", [], "No pages found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _empty_find_content),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "RD-123")
        )

    # Find the notion step_complete
    notion_completes = [
        e for e in events
        if e.get("event") == "step_complete" and e.get("source") == "notion"
    ]
    assert len(notion_completes) == 1
    notion_event = notion_completes[0]

    assert notion_event["syncing"] is True
    assert "Sync in progress" in notion_event["detail"]
    assert notion_event["count"] == 0


# ---------------------------------------------------------------------------
# Test 5: No syncing flag when sync is complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_syncing_flag_when_complete():
    """When no providers are syncing, step_complete should NOT have syncing key."""
    session = AsyncMock()
    jira_issue = _make_jira_issue()

    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", None),
        ("scalar_one_or_none", jira_issue),
        ("fetchall", [("jira",), ("notion",)]),
        ("fetchall", []),
        ("fetchall", []),                        # No syncing providers
        ("scalar_one_or_none", None),
    ])

    async def _empty_find_content(*args, **kwargs):
        yield "jira", [], "No items found"
        yield "notion", [], "No pages found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _empty_find_content),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "RD-123")
        )

    notion_completes = [
        e for e in events
        if e.get("event") == "step_complete" and e.get("source") == "notion"
    ]
    assert len(notion_completes) == 1
    notion_event = notion_completes[0]

    # syncing key should NOT be present
    assert "syncing" not in notion_event
    assert notion_event["detail"] == "No pages found"


# ---------------------------------------------------------------------------
# Test 6: Syncing provider with SOME results still shows syncing flag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_syncing_with_partial_results():
    """When a provider is syncing but has some results, syncing=True should
    still be set, but the detail should show the actual count (not the
    'Sync in progress' override, which only applies to 0-result case)."""
    session = AsyncMock()
    jira_issue = _make_jira_issue()

    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", None),
        ("scalar_one_or_none", jira_issue),
        ("fetchall", [("jira",), ("notion",)]),
        ("fetchall", []),
        ("fetchall", [("notion", "syncing")]),   # Notion syncing
        ("scalar_one_or_none", None),
    ])

    # Notion has 2 pages already indexed (out of 300)
    mock_item_1 = MagicMock()
    mock_item_1.source_type = "notion_page"
    mock_item_2 = MagicMock()
    mock_item_2.source_type = "notion_page"

    async def _find_with_partial(*args, **kwargs):
        yield "jira", [], "No items found"
        yield "notion", [mock_item_1, mock_item_2], "Found 2 pages"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _find_with_partial),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "RD-123")
        )

    notion_event = [
        e for e in events
        if e.get("event") == "step_complete" and e.get("source") == "notion"
    ][0]

    assert notion_event["syncing"] is True
    assert notion_event["count"] == 2
    # Detail should be the original "Found 2 pages", NOT "Sync in progress"
    assert notion_event["detail"] == "Found 2 pages"


# ---------------------------------------------------------------------------
# Test 7: Jira ticket sets jira_issue_id FK on new context page
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jira_ticket_sets_jira_issue_id_on_new_page():
    """When generating from a Jira ticket, the ContextPage must have
    jira_issue_id set to the JiraIssue's UUID, and ticket_id must be None."""
    session = AsyncMock()
    jira_issue = _make_jira_issue()

    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", None),          # 1. No LinearTicket
        ("scalar_one_or_none", jira_issue),    # 2. JiraIssue found
        ("fetchall", [("jira",)]),             # 3. OAuth tokens
        ("fetchall", []),                       # 4. WorkspaceIntegrations
        ("fetchall", []),                       # 5. No syncing
        ("scalar_one_or_none", None),          # 6. No existing context page
    ])

    async def _empty_find_content(*args, **kwargs):
        yield "jira", [], "No items found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _empty_find_content),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "RD-123")
        )

    # Verify generation completed
    assert any(e.get("event") == "complete" for e in events)

    # session.add was called with the new ContextPage
    add_calls = session.add.call_args_list
    assert len(add_calls) == 1
    context_page = add_calls[0][0][0]

    assert context_page.jira_issue_id == jira_issue.id
    assert context_page.ticket_id is None
    assert context_page.ticket_identifier == "RD-123"


# ---------------------------------------------------------------------------
# Test 8: Linear ticket sets ticket_id FK, NOT jira_issue_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_linear_ticket_sets_ticket_id_not_jira():
    """When generating from a Linear ticket, the ContextPage must have
    ticket_id set and jira_issue_id must be None."""
    session = AsyncMock()
    linear_ticket = _make_linear_ticket()

    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", linear_ticket),  # 1. LinearTicket found
        ("fetchall", [("slack",)]),              # 2. OAuth tokens
        ("fetchall", []),                        # 3. WorkspaceIntegrations
        ("fetchall", []),                        # 4. No syncing
        ("scalar_one_or_none", None),           # 5. No existing page
    ])

    async def _empty_find_content(*args, **kwargs):
        yield "linear", [], "No items found"
        yield "slack", [], "No messages found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _empty_find_content),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "CON-42")
        )

    assert any(e.get("event") == "complete" for e in events)

    add_calls = session.add.call_args_list
    assert len(add_calls) == 1
    context_page = add_calls[0][0][0]

    assert context_page.ticket_id == linear_ticket.id
    assert context_page.jira_issue_id is None
    assert context_page.ticket_identifier == "CON-42"


# ---------------------------------------------------------------------------
# Test 9: Regenerating Jira page backfills jira_issue_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regenerate_jira_page_backfills_jira_issue_id():
    """When regenerating a Jira context page that was created before the
    jira_issue_id fix, the FK should be backfilled."""
    session = AsyncMock()
    jira_issue = _make_jira_issue()

    # Simulate an existing context page with jira_issue_id=None (pre-fix)
    existing_page = MagicMock()
    existing_page.jira_issue_id = None
    existing_page.id = uuid4()
    existing_page.status = "ready"

    session.execute.side_effect = _mock_execute_returning([
        ("scalar_one_or_none", None),          # 1. No LinearTicket
        ("scalar_one_or_none", jira_issue),    # 2. JiraIssue found
        ("fetchall", [("jira",)]),             # 3. OAuth tokens
        ("fetchall", []),                       # 4. WorkspaceIntegrations
        ("fetchall", []),                       # 5. No syncing
        ("scalar_one_or_none", existing_page), # 6. Existing page found!
    ])

    async def _empty_find_content(*args, **kwargs):
        yield "jira", [], "No items found"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=_make_llm_response())

    with (
        patch("src.services.synthesis.find_content_by_source", _empty_find_content),
        patch("src.services.synthesis.get_llm_client", return_value=mock_llm),
    ):
        from src.services.synthesis import generate_context_page_stream

        events = await _collect_events(
            generate_context_page_stream(session, WORKSPACE_ID, "RD-123")
        )

    assert any(e.get("event") == "complete" for e in events)

    # session.add should NOT be called (existing page was updated in-place)
    assert session.add.call_count == 0

    # The existing page's jira_issue_id should have been backfilled
    assert existing_page.jira_issue_id == jira_issue.id
    # Status ends as "ready" after successful generation (not "generating")
    assert existing_page.status == "ready"
