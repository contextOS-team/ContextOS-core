"""Tests for Notion webhook receiver and event processor.

Covers:
- HMAC-SHA256 signature verification (valid, invalid, missing)
- Idempotent duplicate delivery detection
- Unknown workspace handling
"""

import hashlib
import hmac
import json
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import src.config
from src.config import Settings
from tests.conftest import TEST_WORKSPACE_ID, _make_test_settings

# Webhook secret used across tests
TEST_NOTION_WEBHOOK_SECRET = "test-notion-webhook-secret"


@pytest.fixture()
def notion_webhook_settings() -> Settings:
    """Create test settings with NOTION_WEBHOOK_SECRET configured."""
    return _make_test_settings(NOTION_WEBHOOK_SECRET=TEST_NOTION_WEBHOOK_SECRET)


@pytest.fixture()
def notion_webhook_app(
    notion_webhook_settings: Settings, mock_session: AsyncMock
):
    """Create a FastAPI app with webhook-specific settings and mocked DB session."""
    src.config._settings = notion_webhook_settings

    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session

    yield fastapi_app

    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def notion_webhook_client(
    notion_webhook_app,
) -> Generator[TestClient, None, None]:
    """Provide a sync TestClient for Notion webhook endpoint tests.

    Patches process_notion_webhook_event to prevent background tasks from
    opening real DB sessions.
    """
    with patch("src.services.notion_webhook.process_notion_webhook_event"):
        with TestClient(notion_webhook_app) as c:
            yield c


def _make_notion_payload(
    event_type: str = "page.content_updated",
    page_id: str = "abc12345-def6-7890-abcd-ef1234567890",
    workspace_id: str = "notion-ws-123",
    timestamp: str = "2026-02-27T16:00:00Z",
) -> dict:
    """Build a minimal Notion webhook payload."""
    return {
        "type": event_type,
        "entity": {"id": page_id},
        "workspace_id": workspace_id,
        "timestamp": timestamp,
    }


def _sign_notion(
    body: bytes, secret: str = TEST_NOTION_WEBHOOK_SECRET
) -> str:
    """Compute HMAC-SHA256 signature for Notion webhook."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Endpoint tests: Signature verification
# ---------------------------------------------------------------------------


def test_webhook_valid_signature(
    notion_webhook_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    """POST with correct HMAC signature returns 200 accepted."""
    payload = _make_notion_payload()
    body = json.dumps(payload).encode()
    sig = _sign_notion(body)

    # Mock session: no existing delivery, then workspace lookup succeeds
    mock_delivery_result = MagicMock()
    mock_delivery_result.scalar_one_or_none.return_value = None

    mock_ws_result = MagicMock()
    mock_ws_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_delivery_result
        return mock_ws_result

    mock_session.execute = AsyncMock(side_effect=side_effect)
    mock_session.add = MagicMock()

    response = notion_webhook_client.post(
        "/api/webhooks/notion",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Notion-Signature": sig,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_webhook_missing_signature(
    notion_webhook_client: TestClient,
) -> None:
    """POST without X-Notion-Signature header returns 400."""
    payload = _make_notion_payload()
    body = json.dumps(payload).encode()

    response = notion_webhook_client.post(
        "/api/webhooks/notion",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "Missing X-Notion-Signature" in response.json()["detail"]


def test_webhook_invalid_signature(
    notion_webhook_client: TestClient,
) -> None:
    """POST with wrong HMAC signature returns 400."""
    payload = _make_notion_payload()
    body = json.dumps(payload).encode()

    response = notion_webhook_client.post(
        "/api/webhooks/notion",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Notion-Signature": "invalid-signature-value",
        },
    )
    assert response.status_code == 400
    assert "Invalid signature" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Endpoint tests: Idempotency
# ---------------------------------------------------------------------------


def test_webhook_duplicate_delivery(
    notion_webhook_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    """Same payload should return already_processed on second delivery."""
    payload = _make_notion_payload()
    body = json.dumps(payload).encode()
    sig = _sign_notion(body)

    # Mock session: delivery already exists
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()  # Existing delivery

    mock_session.execute.return_value = mock_result

    response = notion_webhook_client.post(
        "/api/webhooks/notion",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Notion-Signature": sig,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "already_processed"


# ---------------------------------------------------------------------------
# Endpoint tests: Unknown workspace
# ---------------------------------------------------------------------------


def test_webhook_unknown_workspace(
    notion_webhook_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    """Valid signature but unknown workspace_id returns unknown_workspace."""
    payload = _make_notion_payload(workspace_id="unknown-ws-999")
    body = json.dumps(payload).encode()
    sig = _sign_notion(body)

    # Mock session: no existing delivery, workspace lookup returns None
    mock_delivery_result = MagicMock()
    mock_delivery_result.scalar_one_or_none.return_value = None

    mock_ws_result = MagicMock()
    mock_ws_result.scalar_one_or_none.return_value = None

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_delivery_result
        return mock_ws_result

    mock_session.execute = AsyncMock(side_effect=side_effect)
    mock_session.add = MagicMock()

    response = notion_webhook_client.post(
        "/api/webhooks/notion",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Notion-Signature": sig,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "unknown_workspace"
