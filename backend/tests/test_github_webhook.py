"""Tests for GitHub webhook receiver and event processor.

Covers:
- HMAC-SHA256 signature verification (valid, invalid, missing)
- Idempotent duplicate delivery detection
- PR open/close/merge state mapping
- Bot PR filtering (dependabot, renovate, github-actions)
- Unmonitored repo skipping
- Review submitted event processing
- Review comment with file/line context
- Installation-to-workspace lookup
"""

import hashlib
import hmac
import json
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, get_settings
from tests.conftest import TEST_WORKSPACE_ID, _make_test_settings

# Webhook secret used across tests
TEST_GITHUB_WEBHOOK_SECRET = "test-github-webhook-secret"


@pytest.fixture()
def gh_webhook_settings() -> Settings:
    """Create test settings with GITHUB_WEBHOOK_SECRET configured."""
    return _make_test_settings(GITHUB_WEBHOOK_SECRET=TEST_GITHUB_WEBHOOK_SECRET)


@pytest.fixture()
def gh_webhook_app(gh_webhook_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with webhook-specific settings and mocked DB session."""
    get_settings.cache_clear()

    import src.auth
    import src.config

    old_config = src.config.get_settings
    old_auth = src.auth.get_settings

    src.config.get_settings = lambda: gh_webhook_settings  # type: ignore[assignment]
    src.auth.get_settings = lambda: gh_webhook_settings  # type: ignore[assignment]

    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session

    yield fastapi_app

    fastapi_app.dependency_overrides.clear()
    src.config.get_settings = old_config  # type: ignore[assignment]
    src.auth.get_settings = old_auth  # type: ignore[assignment]
    get_settings.cache_clear()


@pytest.fixture()
def gh_webhook_client(gh_webhook_app) -> Generator[TestClient, None, None]:
    """Provide a sync TestClient for GitHub webhook endpoint tests.

    Patches process_github_event to prevent background tasks from
    opening real DB sessions.
    """
    with patch("src.services.github_webhook.process_github_event"):
        with TestClient(gh_webhook_app) as c:
            yield c


def _make_github_payload(
    event_type: str = "pull_request",
    action: str = "opened",
    installation_id: int = 12345,
    extra: dict | None = None,
) -> dict:
    """Build a minimal GitHub webhook payload."""
    payload = {
        "action": action,
        "installation": {"id": installation_id},
    }
    if extra:
        payload.update(extra)
    return payload


def _sign_github(
    body: bytes, secret: str = TEST_GITHUB_WEBHOOK_SECRET
) -> str:
    """Compute HMAC-SHA256 signature in GitHub format: sha256=<hex>."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Endpoint tests: Signature verification
# ---------------------------------------------------------------------------


def test_github_webhook_valid_signature_accepted(
    gh_webhook_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    """POST with correct HMAC signature returns 200."""
    payload = _make_github_payload()
    body = json.dumps(payload).encode()
    sig = _sign_github(body)

    # Mock session: no existing delivery
    mock_result_delivery = MagicMock()
    mock_result_delivery.scalar_one_or_none.return_value = None

    mock_session.execute.return_value = mock_result_delivery

    response = gh_webhook_client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": str(uuid4()),
            "X-GitHub-Event": "pull_request",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_github_webhook_invalid_signature_rejected(
    gh_webhook_client: TestClient,
) -> None:
    """POST with wrong HMAC signature returns 401."""
    payload = _make_github_payload()
    body = json.dumps(payload).encode()

    response = gh_webhook_client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Delivery": str(uuid4()),
            "X-GitHub-Event": "pull_request",
        },
    )
    assert response.status_code == 401
    assert "Invalid signature" in response.json()["detail"]


def test_github_webhook_missing_signature_rejected(
    gh_webhook_client: TestClient,
) -> None:
    """POST without X-Hub-Signature-256 header returns 401."""
    payload = _make_github_payload()
    body = json.dumps(payload).encode()

    response = gh_webhook_client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Delivery": str(uuid4()),
            "X-GitHub-Event": "pull_request",
        },
    )
    assert response.status_code == 401
    assert "Missing X-Hub-Signature-256" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Endpoint tests: Idempotency
# ---------------------------------------------------------------------------


def test_github_webhook_duplicate_delivery_skipped(
    gh_webhook_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    """Same X-GitHub-Delivery UUID should be skipped on second attempt."""
    payload = _make_github_payload()
    body = json.dumps(payload).encode()
    sig = _sign_github(body)

    # Mock session: delivery already exists
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()  # Existing delivery

    mock_session.execute.return_value = mock_result

    response = gh_webhook_client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": str(uuid4()),
            "X-GitHub-Event": "pull_request",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "already_processed"


# ---------------------------------------------------------------------------
# Service tests: PR events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_pull_request_opened() -> None:
    """PR opened event should upsert a PR record with state=open."""
    workspace_id = UUID(TEST_WORKSPACE_ID)

    pr_payload = {
        "action": "opened",
        "installation": {"id": 123},
        "pull_request": {
            "id": 99001,
            "number": 42,
            "title": "Add feature",
            "body": "Description here",
            "state": "open",
            "draft": False,
            "merged": False,
            "user": {"login": "developer"},
            "head": {"ref": "feat/ENG-123-add-feature"},
            "base": {"ref": "main"},
            "requested_reviewers": [],
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-01-15T10:00:00Z",
            "merged_at": None,
        },
        "repository": {"full_name": "org/repo"},
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # session.add() is synchronous
    # is_repo_monitored: returns True
    mock_integration = MagicMock()
    mock_integration.config = {"selected_repos": ["org/repo"]}
    mock_int_result = MagicMock()
    mock_int_result.scalar_one_or_none.return_value = mock_integration

    # Existing PR: not found
    mock_pr_result = MagicMock()
    mock_pr_result.scalar_one_or_none.return_value = None

    # link_pr_to_ticket: get_linear_team_keys returns empty
    mock_team_result = MagicMock()
    mock_team_result.fetchall.return_value = []

    mock_session.execute.side_effect = [
        mock_int_result,  # is_repo_monitored
        mock_pr_result,  # existing PR lookup
        mock_team_result,  # get_linear_team_keys
    ]

    from src.services.github_webhook import handle_pull_request_event

    await handle_pull_request_event("opened", pr_payload, workspace_id, mock_session)

    # Verify PR was added to session
    mock_session.add.assert_called_once()
    added_pr = mock_session.add.call_args[0][0]
    assert added_pr.state == "open"
    assert added_pr.title == "Add feature"
    assert added_pr.author == "developer"
    assert added_pr.number == 42


@pytest.mark.asyncio
async def test_handle_pull_request_closed_merged() -> None:
    """PR closed with merged=True should set state='merged'."""
    workspace_id = UUID(TEST_WORKSPACE_ID)

    pr_payload = {
        "action": "closed",
        "installation": {"id": 123},
        "pull_request": {
            "id": 99002,
            "number": 43,
            "title": "Merge feature",
            "body": None,
            "state": "closed",
            "draft": False,
            "merged": True,
            "user": {"login": "developer"},
            "head": {"ref": "feat/something"},
            "base": {"ref": "main"},
            "requested_reviewers": [],
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-01-16T10:00:00Z",
            "merged_at": "2026-01-16T10:00:00Z",
        },
        "repository": {"full_name": "org/repo"},
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # session.add() is synchronous

    mock_integration = MagicMock()
    mock_integration.config = {"selected_repos": ["org/repo"]}
    mock_int_result = MagicMock()
    mock_int_result.scalar_one_or_none.return_value = mock_integration

    # Existing PR: found
    existing_pr = MagicMock()
    existing_pr.title = "Old title"
    existing_pr.reviewers = []
    mock_pr_result = MagicMock()
    mock_pr_result.scalar_one_or_none.return_value = existing_pr

    mock_team_result = MagicMock()
    mock_team_result.fetchall.return_value = []

    mock_session.execute.side_effect = [
        mock_int_result,
        mock_pr_result,
        mock_team_result,
    ]

    from src.services.github_webhook import handle_pull_request_event

    await handle_pull_request_event("closed", pr_payload, workspace_id, mock_session)

    # Existing PR should be updated with state='merged'
    assert existing_pr.state == "merged"


@pytest.mark.asyncio
async def test_handle_pull_request_bot_filtered() -> None:
    """Bot-authored PRs (dependabot) should be skipped."""
    workspace_id = UUID(TEST_WORKSPACE_ID)

    pr_payload = {
        "action": "opened",
        "installation": {"id": 123},
        "pull_request": {
            "id": 99003,
            "number": 44,
            "title": "Bump deps",
            "body": None,
            "user": {"login": "dependabot[bot]"},
            "head": {"ref": "dependabot/npm"},
            "base": {"ref": "main"},
        },
        "repository": {"full_name": "org/repo"},
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # session.add() is synchronous
    mock_integration = MagicMock()
    mock_integration.config = {"selected_repos": ["org/repo"]}
    mock_int_result = MagicMock()
    mock_int_result.scalar_one_or_none.return_value = mock_integration

    mock_session.execute.return_value = mock_int_result

    from src.services.github_webhook import handle_pull_request_event

    await handle_pull_request_event("opened", pr_payload, workspace_id, mock_session)

    # PR should NOT be added (bot filtered)
    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_handle_pull_request_unmonitored_repo_skipped() -> None:
    """PRs from unmonitored repos should be skipped."""
    workspace_id = UUID(TEST_WORKSPACE_ID)

    pr_payload = {
        "action": "opened",
        "installation": {"id": 123},
        "pull_request": {
            "id": 99004,
            "number": 45,
            "title": "Feature",
            "body": None,
            "user": {"login": "developer"},
            "head": {"ref": "feat/thing"},
            "base": {"ref": "main"},
        },
        "repository": {"full_name": "org/unmonitored-repo"},
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # session.add() is synchronous
    # is_repo_monitored returns False (repo not in selected_repos)
    mock_integration = MagicMock()
    mock_integration.config = {"selected_repos": ["org/other-repo"]}
    mock_int_result = MagicMock()
    mock_int_result.scalar_one_or_none.return_value = mock_integration

    mock_session.execute.return_value = mock_int_result

    from src.services.github_webhook import handle_pull_request_event

    await handle_pull_request_event("opened", pr_payload, workspace_id, mock_session)

    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()


# ---------------------------------------------------------------------------
# Service tests: Review events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_review_submitted() -> None:
    """Review submitted event should upsert a GithubReview with state."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    pr_record_id = uuid4()

    review_payload = {
        "action": "submitted",
        "installation": {"id": 123},
        "review": {
            "id": 55001,
            "user": {"login": "reviewer"},
            "state": "approved",
            "body": "LGTM!",
            "submitted_at": "2026-01-15T12:00:00Z",
        },
        "pull_request": {
            "id": 99001,
            "number": 42,
        },
        "repository": {"full_name": "org/repo"},
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # session.add() is synchronous

    # is_repo_monitored: True
    mock_integration = MagicMock()
    mock_integration.config = {"selected_repos": ["org/repo"]}
    mock_int_result = MagicMock()
    mock_int_result.scalar_one_or_none.return_value = mock_integration

    # Parent PR lookup
    mock_pr = MagicMock()
    mock_pr.id = pr_record_id
    mock_pr.number = 42
    mock_pr_result = MagicMock()
    mock_pr_result.scalar_one_or_none.return_value = mock_pr

    # Existing review: not found
    mock_review_result = MagicMock()
    mock_review_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_int_result,
        mock_pr_result,
        mock_review_result,
    ]

    from src.services.github_webhook import handle_review_event

    await handle_review_event("submitted", review_payload, workspace_id, mock_session)

    mock_session.add.assert_called_once()
    added_review = mock_session.add.call_args[0][0]
    assert added_review.state == "approved"
    assert added_review.author == "reviewer"
    assert added_review.body == "LGTM!"
    assert added_review.pull_request_id == pr_record_id


# ---------------------------------------------------------------------------
# Service tests: Review comment events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_review_comment_with_file_context() -> None:
    """Review comment should store file_path and line_range."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    pr_record_id = uuid4()

    comment_payload = {
        "action": "created",
        "installation": {"id": 123},
        "comment": {
            "id": 77001,
            "user": {"login": "reviewer"},
            "body": "Consider refactoring this.",
            "path": "src/services/auth.py",
            "line": 42,
            "original_line": 38,
            "created_at": "2026-01-15T14:00:00Z",
        },
        "pull_request": {
            "id": 99001,
            "number": 42,
        },
        "repository": {"full_name": "org/repo"},
    }

    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # session.add() is synchronous

    # is_repo_monitored: True
    mock_integration = MagicMock()
    mock_integration.config = {"selected_repos": ["org/repo"]}
    mock_int_result = MagicMock()
    mock_int_result.scalar_one_or_none.return_value = mock_integration

    # Parent PR
    mock_pr = MagicMock()
    mock_pr.id = pr_record_id
    mock_pr.number = 42
    mock_pr_result = MagicMock()
    mock_pr_result.scalar_one_or_none.return_value = mock_pr

    # Existing comment: not found
    mock_comment_result = MagicMock()
    mock_comment_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_int_result,
        mock_pr_result,
        mock_comment_result,
    ]

    from src.services.github_webhook import handle_review_comment_event

    await handle_review_comment_event(
        "created", comment_payload, workspace_id, mock_session
    )

    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert added.file_path == "src/services/auth.py"
    assert added.line_range == "38-42"
    assert added.body == "Consider refactoring this."
    assert added.author == "reviewer"
    assert added.state == "commented"


# ---------------------------------------------------------------------------
# Service tests: Workspace lookup from installation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_workspace_from_installation_id() -> None:
    """Should find workspace_id by installation_id in OAuthToken metadata."""
    from src.services.github_webhook import _lookup_workspace_from_installation

    workspace_id = UUID(TEST_WORKSPACE_ID)
    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = workspace_id

    mock_session.execute.return_value = mock_result

    result = await _lookup_workspace_from_installation(12345, mock_session)
    assert result == workspace_id


@pytest.mark.asyncio
async def test_lookup_workspace_not_found_returns_none() -> None:
    """Should return None when no matching installation_id found."""
    from src.services.github_webhook import _lookup_workspace_from_installation

    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session.execute.return_value = mock_result

    result = await _lookup_workspace_from_installation(99999, mock_session)
    assert result is None
