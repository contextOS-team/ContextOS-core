"""Tests for Linear webhook receiver and event processor.

Covers:
- HMAC-SHA256 signature verification (valid, invalid, missing)
- Idempotent duplicate delivery detection
- Issue create/update/remove event handling
- Comment create/update/remove event handling
- Selective re-embedding for content vs metadata changes
- Non-synced team behavior (store but no embedding)
- Unknown event types safely ignored
- is_content_change helper unit tests
"""

import hashlib
import hmac
import json
import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings
from tests.conftest import TEST_WORKSPACE_ID, _make_test_settings

# Webhook secret used across tests
TEST_WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture(autouse=True)
def _patch_queue_embedding():
    with patch("src.services.embedding.queue_embedding_generation", new_callable=AsyncMock):
        yield


@pytest.fixture()
def webhook_settings() -> Settings:
    """Create test settings with LINEAR_WEBHOOK_SECRET configured."""
    return _make_test_settings(LINEAR_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET)


@pytest.fixture()
def webhook_app(webhook_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with webhook-specific settings and mocked DB session."""
    src.config._settings = webhook_settings

    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session

    yield fastapi_app

    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def webhook_client(webhook_app) -> Generator[TestClient, None, None]:
    """Provide a sync TestClient for webhook endpoint tests.

    Patches process_webhook_event to prevent background tasks from
    opening real DB sessions. Endpoint tests verify routing, signature
    verification, and idempotency; the service is tested separately.
    """
    with patch("src.services.linear_webhook.process_webhook_event"):
        with TestClient(webhook_app) as c:
            yield c


def _make_payload(
    action: str = "create",
    event_type: str = "Issue",
    data: dict | None = None,
    organization_id: str = "org-123",
) -> dict:
    """Build a minimal Linear webhook payload."""
    return {
        "action": action,
        "type": event_type,
        "data": data or {"id": str(uuid4()), "title": "Test Issue"},
        "organizationId": organization_id,
        "webhookTimestamp": int(time.time() * 1000),
        "webhookId": str(uuid4()),
    }


def _sign(body: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Compute HMAC-SHA256 signature for webhook body."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Endpoint tests: Signature verification
# ---------------------------------------------------------------------------


def test_webhook_valid_signature_accepted(
    webhook_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    """POST with correct HMAC signature returns 200."""
    payload = _make_payload()
    body = json.dumps(payload).encode()
    sig = _sign(body)

    # Mock session: no existing delivery, workspace found
    mock_result_delivery = MagicMock()
    mock_result_delivery.scalar_one_or_none.return_value = None  # Not a duplicate

    mock_result_workspace = MagicMock()
    mock_result_workspace.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

    mock_session.execute.side_effect = [mock_result_delivery, mock_result_workspace]

    response = webhook_client.post(
        "/api/webhooks/linear",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Linear-Signature": sig,
            "Linear-Delivery": str(uuid4()),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_webhook_invalid_signature_rejected(
    webhook_client: TestClient,
) -> None:
    """POST with wrong HMAC signature returns 400."""
    payload = _make_payload()
    body = json.dumps(payload).encode()

    response = webhook_client.post(
        "/api/webhooks/linear",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Linear-Signature": "invalid-signature",
            "Linear-Delivery": str(uuid4()),
        },
    )
    assert response.status_code == 400
    assert "Invalid signature" in response.json()["detail"]


def test_webhook_missing_signature_rejected(
    webhook_client: TestClient,
) -> None:
    """POST without signature header returns 400."""
    payload = _make_payload()
    body = json.dumps(payload).encode()

    response = webhook_client.post(
        "/api/webhooks/linear",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Linear-Delivery": str(uuid4()),
        },
    )
    assert response.status_code == 400
    assert "Missing Linear-Signature" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Endpoint tests: Idempotency
# ---------------------------------------------------------------------------


def test_webhook_duplicate_delivery_skipped(
    webhook_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    """Same delivery UUID should be skipped on second attempt."""
    payload = _make_payload()
    body = json.dumps(payload).encode()
    sig = _sign(body)

    # Mock session: delivery already exists
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()  # Existing delivery

    mock_session.execute.return_value = mock_result

    response = webhook_client.post(
        "/api/webhooks/linear",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Linear-Signature": sig,
            "Linear-Delivery": str(uuid4()),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "already_processed"


def test_webhook_missing_delivery_header_rejected(
    webhook_client: TestClient,
) -> None:
    """POST without Linear-Delivery header returns 400."""
    payload = _make_payload()
    body = json.dumps(payload).encode()
    sig = _sign(body)

    response = webhook_client.post(
        "/api/webhooks/linear",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Linear-Signature": sig,
        },
    )
    assert response.status_code == 400
    assert "Missing Linear-Delivery" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Service tests: Issue events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_create_inserts_ticket() -> None:
    """Issue create event syncs ticket via sync_single_ticket."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    issue_id = str(uuid4())
    ticket_uuid = uuid4()
    data = {"id": issue_id, "teamId": "team-1"}
    event = _make_payload(action="create", event_type="Issue", data=data)

    mock_ticket = MagicMock()
    mock_ticket.id = ticket_uuid
    mock_ticket.title = "Test"
    mock_ticket.description = "Desc"

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
        patch("src.services.linear_webhook._get_access_token", return_value="token-123"),
        patch("src.services.linear_webhook.sync_single_ticket", return_value=mock_ticket) as mock_sync,
        patch("src.services.linear_webhook._is_team_synced", return_value=True),
        patch("src.services.linear_webhook.embedding") as mock_embedding,
    ):
        mock_embedding.queue_embedding_generation = AsyncMock()
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        mock_sync.assert_called_once_with(mock_session, workspace_id, "token-123", issue_id)
        mock_embedding.queue_embedding_generation.assert_called_once_with(
            mock_session, workspace_id, "linear_ticket", [ticket_uuid]
        )


@pytest.mark.asyncio
async def test_issue_update_content_change_triggers_reembed() -> None:
    """Issue update with changed title triggers re-embedding."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    issue_id = str(uuid4())
    ticket_uuid = uuid4()
    data = {"id": issue_id, "teamId": "team-1"}
    event = _make_payload(action="update", event_type="Issue", data=data)

    # Existing ticket with old title
    existing_ticket = MagicMock()
    existing_ticket.title = "Old Title"
    existing_ticket.description = "Same description"

    # Updated ticket with new title
    updated_ticket = MagicMock()
    updated_ticket.id = ticket_uuid
    updated_ticket.title = "New Title"
    updated_ticket.description = "Same description"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_ticket

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
        patch("src.services.linear_webhook._get_access_token", return_value="token-123"),
        patch("src.services.linear_webhook.sync_single_ticket", return_value=updated_ticket),
        patch("src.services.linear_webhook._is_team_synced", return_value=True),
        patch("src.services.linear_webhook.embedding") as mock_embedding,
    ):
        mock_embedding.queue_embedding_generation = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        mock_embedding.queue_embedding_generation.assert_called_once_with(
            mock_session, workspace_id, "linear_ticket", [ticket_uuid]
        )


@pytest.mark.asyncio
async def test_issue_update_metadata_only_skips_reembed() -> None:
    """Issue update with only state change does NOT trigger re-embedding."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    issue_id = str(uuid4())
    ticket_uuid = uuid4()
    data = {"id": issue_id, "teamId": "team-1"}
    event = _make_payload(action="update", event_type="Issue", data=data)

    # Existing ticket -- title and description unchanged
    existing_ticket = MagicMock()
    existing_ticket.title = "Same Title"
    existing_ticket.description = "Same description"

    # Updated ticket -- same content, only state changed
    updated_ticket = MagicMock()
    updated_ticket.id = ticket_uuid
    updated_ticket.title = "Same Title"
    updated_ticket.description = "Same description"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_ticket

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
        patch("src.services.linear_webhook._get_access_token", return_value="token-123"),
        patch("src.services.linear_webhook.sync_single_ticket", return_value=updated_ticket),
        patch("src.services.linear_webhook._is_team_synced", return_value=True),
        patch("src.services.linear_webhook.embedding") as mock_embedding,
    ):
        mock_embedding.queue_embedding_generation = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        # Embedding should NOT be called
        mock_embedding.queue_embedding_generation.assert_not_called()


@pytest.mark.asyncio
async def test_issue_remove_soft_deletes() -> None:
    """Issue remove event sets deleted_at on the ticket."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    issue_id = str(uuid4())
    data = {"id": issue_id}
    event = _make_payload(action="remove", event_type="Issue", data=data)

    existing_ticket = MagicMock()
    existing_ticket.deleted_at = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_ticket

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
    ):
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        assert existing_ticket.deleted_at is not None


# ---------------------------------------------------------------------------
# Service tests: Comment events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comment_create_inserts_comment() -> None:
    """Comment create event inserts a new comment."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    comment_id = str(uuid4())
    issue_id = str(uuid4())
    ticket_uuid = uuid4()

    data = {
        "id": comment_id,
        "body": "A new comment",
        "issueId": issue_id,
        "user": {"name": "Test User"},
        "createdAt": "2026-01-01T00:00:00Z",
    }
    event = _make_payload(action="create", event_type="Comment", data=data)

    mock_ticket = MagicMock()
    mock_ticket.id = ticket_uuid
    mock_ticket.raw_data = {"team": {"id": "team-1"}}

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = mock_ticket

    comment_result = MagicMock()
    comment_result.scalar_one_or_none.return_value = None

    integration_result = MagicMock()
    mock_integration = MagicMock()
    mock_integration.config = {"synced_teams": ["team-1"]}
    integration_result.scalar_one_or_none.return_value = mock_integration

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
    ):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # session.add() is synchronous
        mock_session.execute.side_effect = [ticket_result, comment_result, integration_result]
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_comment_create_queues_embedding() -> None:
    """Comment create event queues embedding generation for the comment."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    comment_linear_id = str(uuid4())
    issue_id = str(uuid4())
    ticket_uuid = uuid4()

    data = {
        "id": comment_linear_id,
        "body": "A comment to embed",
        "issueId": issue_id,
        "user": {"name": "User"},
    }
    event = _make_payload(action="create", event_type="Comment", data=data)

    mock_ticket = MagicMock()
    mock_ticket.id = ticket_uuid
    mock_ticket.raw_data = {"team": {"id": "team-synced"}}

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = mock_ticket

    comment_result = MagicMock()
    comment_result.scalar_one_or_none.return_value = None

    integration_result = MagicMock()
    mock_integration = MagicMock()
    mock_integration.config = {"synced_teams": ["team-synced"]}
    integration_result.scalar_one_or_none.return_value = mock_integration

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
        patch("src.services.linear_webhook.embedding") as mock_embedding,
    ):
        mock_embedding.queue_embedding_generation = AsyncMock()
        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # session.add() is synchronous
        mock_session.execute.side_effect = [ticket_result, comment_result, integration_result]
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        mock_embedding.queue_embedding_generation.assert_called_once()
        call_args = mock_embedding.queue_embedding_generation.call_args
        assert call_args[0][2] == "linear_comment"


@pytest.mark.asyncio
async def test_comment_remove_soft_deletes() -> None:
    """Comment remove event sets deleted_at on the comment."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    comment_linear_id = str(uuid4())
    data = {"id": comment_linear_id}
    event = _make_payload(action="remove", event_type="Comment", data=data)

    existing_comment = MagicMock()
    existing_comment.deleted_at = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_comment

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
    ):
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        assert existing_comment.deleted_at is not None


# ---------------------------------------------------------------------------
# Service tests: Non-synced teams and unknown events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_outside_synced_teams_stores_raw_only() -> None:
    """Event for unsynced team syncs ticket but does NOT queue embedding."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    issue_id = str(uuid4())
    ticket_uuid = uuid4()
    data = {"id": issue_id, "teamId": "unsynced-team"}
    event = _make_payload(action="create", event_type="Issue", data=data)

    mock_ticket = MagicMock()
    mock_ticket.id = ticket_uuid

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
        patch("src.services.linear_webhook._get_access_token", return_value="token-123"),
        patch("src.services.linear_webhook.sync_single_ticket", return_value=mock_ticket),
        patch("src.services.linear_webhook._is_team_synced", return_value=False),
        patch("src.services.linear_webhook.embedding") as mock_embedding,
    ):
        mock_embedding.queue_embedding_generation = AsyncMock()
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        mock_embedding.queue_embedding_generation.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_event_type_ignored() -> None:
    """Unknown event types (e.g., Reaction) are logged and safely ignored."""
    workspace_id = UUID(TEST_WORKSPACE_ID)
    event = _make_payload(action="create", event_type="Reaction", data={"id": "abc"})

    with (
        patch("src.services.linear_webhook.async_session") as mock_session_ctx,
        patch("src.services.linear_webhook.embedding") as mock_embedding,
    ):
        mock_embedding.queue_embedding_generation = AsyncMock()
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.linear_webhook import process_webhook_event

        await process_webhook_event(workspace_id, event)

        mock_embedding.queue_embedding_generation.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests: is_content_change helper
# ---------------------------------------------------------------------------


def test_is_content_change_detects_title_change() -> None:
    """is_content_change returns True when title differs."""
    from src.services.linear_webhook import is_content_change

    ticket = MagicMock()
    ticket.title = "Old Title"
    ticket.description = "Same description"

    assert is_content_change(ticket, "New Title", "Same description") is True


def test_is_content_change_detects_description_change() -> None:
    """is_content_change returns True when description differs."""
    from src.services.linear_webhook import is_content_change

    ticket = MagicMock()
    ticket.title = "Same Title"
    ticket.description = "Old description"

    assert is_content_change(ticket, "Same Title", "New description") is True


def test_is_content_change_ignores_state_change() -> None:
    """is_content_change returns False when title and description are the same."""
    from src.services.linear_webhook import is_content_change

    ticket = MagicMock()
    ticket.title = "Same Title"
    ticket.description = "Same description"

    assert is_content_change(ticket, "Same Title", "Same description") is False


def test_is_content_change_both_none() -> None:
    """is_content_change returns False when both old and new description are None."""
    from src.services.linear_webhook import is_content_change

    ticket = MagicMock()
    ticket.title = "Same Title"
    ticket.description = None

    assert is_content_change(ticket, "Same Title", None) is False
