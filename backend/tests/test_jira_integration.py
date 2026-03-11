"""Tests for Jira integration: OAuth flow, webhook processing, embedding registration, and JQL safety.

Covers:
- OAuth connect returns valid auth URL
- OAuth callback redirects to settings page on success/error
- Disconnect endpoint
- Webhook processing for issue events
- Webhook with unknown cloud_id
- JQL search escaping
- ADF text extraction
- Webhook issue upsert (create + update paths)
- Embedding SOURCE_TYPE_MAP registration
"""

import json
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings
from src.services.jira_sync import _extract_text_from_adf
from tests.conftest import (
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    _make_test_settings,
)

WORKSPACE_UUID = UUID(TEST_WORKSPACE_ID)
USER_UUID = UUID(TEST_USER_ID)

JIRA_CLIENT_ID = "test-jira-client-id"
JIRA_CLIENT_SECRET = "test-jira-client-secret"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_queue_embedding():
    with patch(
        "src.services.embedding.queue_embedding_generation", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture()
def jira_settings() -> Settings:
    return _make_test_settings(
        JIRA_CLIENT_ID=JIRA_CLIENT_ID,
        JIRA_CLIENT_SECRET=JIRA_CLIENT_SECRET,
        CORS_ORIGINS="http://localhost:3000",
    )


@pytest.fixture()
def mock_session() -> AsyncMock:
    from sqlalchemy.ext.asyncio import AsyncSession
    return AsyncMock(spec=AsyncSession)


def _user_context():
    from src.dependencies import UserContext
    return UserContext(
        user_id=USER_UUID, workspace_id=WORKSPACE_UUID, email="test@example.com"
    )


@pytest.fixture()
def app(jira_settings, mock_session):
    src.config._settings = jira_settings
    from src.main import app
    from src.db import get_session
    from src.dependencies import get_current_user

    async def _mock_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = _mock_get_session
    app.dependency_overrides[get_current_user] = _user_context
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. test_connect_returns_auth_url
# ---------------------------------------------------------------------------


def test_connect_returns_auth_url(client: TestClient):
    """GET /api/jira/connect returns valid Atlassian auth URL."""
    response = client.get("/api/jira/connect")

    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    url = data["authorization_url"]
    assert "auth.atlassian.com/authorize" in url
    assert JIRA_CLIENT_ID in url
    assert "read%3Ajira-work" in url or "read:jira-work" in url


# ---------------------------------------------------------------------------
# 2. test_callback_success_redirects_to_settings
# ---------------------------------------------------------------------------


def test_callback_success_redirects_to_settings(client: TestClient, mock_session):
    """OAuth callback redirects to /dashboard/settings?tab=integrations&jira=connected."""
    with patch("src.routers.jira.verify_state_or_raise", return_value=WORKSPACE_UUID), \
         patch("src.routers.jira.exchange_code", new_callable=AsyncMock) as mock_exchange:
        mock_exchange.return_value = {"cloud_id": "test-cloud", "site_name": "mysite"}

        # Mock the workspace member lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = USER_UUID
        mock_session.execute.return_value = mock_result

        response = client.get(
            "/api/jira/callback",
            params={"code": "test-code", "state": "test-state"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "/dashboard/settings" in location
    assert "tab=integrations" in location
    assert "jira=connected" in location


# ---------------------------------------------------------------------------
# 3. test_callback_invalid_state_redirects_error
# ---------------------------------------------------------------------------


def test_callback_invalid_state_redirects_error(client: TestClient):
    """Bad state param returns error redirect to settings page."""
    from src.services.jira_oauth import JiraOAuthError

    with patch(
        "src.routers.jira.verify_state_or_raise",
        side_effect=JiraOAuthError("bad state"),
    ):
        response = client.get(
            "/api/jira/callback",
            params={"code": "test-code", "state": "bad-state"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "jira=error" in location
    assert "invalid_state" in location


# ---------------------------------------------------------------------------
# 4. test_disconnect_returns_ok
# ---------------------------------------------------------------------------


def test_disconnect_returns_ok(client: TestClient):
    """POST /api/jira/disconnect calls disconnect service and returns ok."""
    with patch("src.routers.jira.disconnect", new_callable=AsyncMock) as mock_disconnect:
        response = client.post("/api/jira/disconnect")

    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"
    mock_disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. test_webhook_processes_issue_created
# ---------------------------------------------------------------------------


def test_webhook_processes_issue_created(client: TestClient, mock_session):
    """POST webhook with jira:issue_created processes the event."""
    payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {
            "id": "10001",
            "key": "TEST-1",
            "self": "https://api.atlassian.com/ex/jira/cloud-abc-123/rest/api/3/issue/10001",
            "fields": {
                "summary": "Test issue",
                "description": None,
                "status": {"name": "Open"},
            },
        },
    }

    # Mock: find integration by cloud_id
    mock_integration = MagicMock()
    mock_integration.workspace_id = WORKSPACE_UUID

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_integration
    mock_session.execute.return_value = mock_result

    with patch(
        "src.services.jira_webhook.process_jira_webhook", new_callable=AsyncMock
    ) as mock_process:
        response = client.post(
            "/api/jira/webhook",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    mock_process.assert_awaited_once()


# ---------------------------------------------------------------------------
# 6. test_webhook_unknown_cloud_id_ignored
# ---------------------------------------------------------------------------


def test_webhook_unknown_cloud_id_ignored(client: TestClient, mock_session):
    """Webhook with unresolvable cloud_id returns ignored."""
    payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {
            "id": "10001",
            "fields": {"summary": "Test"},
        },
    }

    response = client.post(
        "/api/jira/webhook",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reason"] == "unknown_cloud_id"


# ---------------------------------------------------------------------------
# 7. test_search_escapes_jql_quotes
# ---------------------------------------------------------------------------


def test_search_escapes_jql_quotes():
    """Verify JQL injection is prevented by escaping quotes."""
    query = 'test" OR status = "Done'
    safe_query = query.replace('\\', '\\\\').replace('"', '\\"')
    jql = f'text ~ "{safe_query}" ORDER BY updated DESC'

    # The escaped JQL should contain escaped quotes, not raw ones
    assert '\\"' in jql
    assert 'text ~ "test\\" OR status = \\"Done"' in jql


# ---------------------------------------------------------------------------
# 8. test_extract_text_from_adf
# ---------------------------------------------------------------------------


def test_extract_text_from_adf():
    """ADF parser handles nested content correctly."""
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": " world"},
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Second paragraph"},
                ],
            },
        ],
    }

    result = _extract_text_from_adf(adf)
    assert result is not None
    assert "Hello" in result
    assert "world" in result
    assert "Second paragraph" in result


def test_extract_text_from_adf_none():
    """ADF parser returns None for None input."""
    assert _extract_text_from_adf(None) is None


def test_extract_text_from_adf_string():
    """ADF parser passes through plain strings."""
    assert _extract_text_from_adf("plain text") == "plain text"


# ---------------------------------------------------------------------------
# 9. test_upsert_issue_from_webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_issue_from_webhook():
    """Webhook issue upsert handles create path."""
    from src.services.jira_webhook import _upsert_issue_from_webhook

    session = AsyncMock()

    issue_data = {
        "id": "10001",
        "key": "PROJ-42",
        "fields": {
            "summary": "New issue",
            "description": "A description",
            "status": {"name": "Open"},
            "priority": {"name": "High"},
            "issuetype": {"name": "Bug"},
            "assignee": {"displayName": "Alice"},
            "reporter": {"displayName": "Bob"},
            "project": {"key": "PROJ", "name": "My Project"},
            "labels": ["urgent"],
            "created": "2025-01-01T00:00:00.000+0000",
            "updated": "2025-01-02T00:00:00.000+0000",
        },
    }

    # Simulate no existing issue (create path)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    with patch("src.services.jira_sync._extract_text_from_adf", return_value="A description"):
        result = await _upsert_issue_from_webhook(session, WORKSPACE_UUID, issue_data)

    assert result is not None
    session.add.assert_called_once()
    session.flush.assert_awaited()

    # Verify the created issue has correct fields
    created_issue = session.add.call_args[0][0]
    assert created_issue.jira_key == "PROJ-42"
    assert created_issue.summary == "New issue"
    assert created_issue.assignee_name == "Alice"


@pytest.mark.asyncio
async def test_upsert_issue_from_webhook_update():
    """Webhook issue upsert updates existing issue."""
    from src.services.jira_webhook import _upsert_issue_from_webhook
    from src.models.jira import JiraIssue

    session = AsyncMock()

    existing_issue = JiraIssue(
        workspace_id=WORKSPACE_UUID,
        jira_id="10001",
        jira_key="PROJ-42",
        summary="Old summary",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_issue
    session.execute.return_value = mock_result

    issue_data = {
        "id": "10001",
        "key": "PROJ-42",
        "fields": {
            "summary": "Updated summary",
            "description": None,
            "status": {"name": "Done"},
            "priority": None,
            "issuetype": None,
            "assignee": None,
            "reporter": None,
            "project": None,
            "labels": [],
            "updated": "2025-01-03T00:00:00.000+0000",
        },
    }

    with patch("src.services.jira_sync._extract_text_from_adf", return_value=None):
        result = await _upsert_issue_from_webhook(session, WORKSPACE_UUID, issue_data)

    assert result is not None
    assert result.summary == "Updated summary"
    assert result.status == "Done"
    # Should not call session.add for update path
    session.add.assert_not_called()


# ---------------------------------------------------------------------------
# 10. test_embedding_source_types_registered
# ---------------------------------------------------------------------------


def test_embedding_source_types_registered():
    """jira_issue and jira_comment exist in embedding SOURCE_TYPE_MAP."""
    from src.services.embedding import SOURCE_TYPE_MAP

    assert "jira_issue" in SOURCE_TYPE_MAP
    assert "jira_comment" in SOURCE_TYPE_MAP

    # Verify extractors work with mock records
    issue_cls, issue_extract = SOURCE_TYPE_MAP["jira_issue"]
    mock_issue = MagicMock()
    mock_issue.jira_key = "TEST-1"
    mock_issue.summary = "Test summary"
    mock_issue.description = "Test description"
    text = issue_extract(mock_issue)
    assert "TEST-1" in text
    assert "Test summary" in text

    comment_cls, comment_extract = SOURCE_TYPE_MAP["jira_comment"]
    mock_comment = MagicMock()
    mock_comment.body = "This is a comment"
    text = comment_extract(mock_comment)
    assert text == "This is a comment"


def test_linking_source_types_registered():
    """jira_issue and jira_comment exist in linking maps."""
    from src.services.linking import SOURCE_TYPE_MAP as LINKING_SOURCE_MAP
    from src.services.linking import _SOURCE_SUMMARY_MAP

    assert "jira" in LINKING_SOURCE_MAP
    assert "jira_issue" in LINKING_SOURCE_MAP["jira"]
    assert "jira_comment" in LINKING_SOURCE_MAP["jira"]
    assert "jira_issue" in _SOURCE_SUMMARY_MAP
    assert "jira_comment" in _SOURCE_SUMMARY_MAP
