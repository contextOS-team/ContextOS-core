"""Webhook receiver endpoints for third-party integrations.

Supports Linear and GitHub webhooks with HMAC-SHA256 signature verification,
idempotent delivery tracking, and replay protection via webhook timestamp
validation (Linear) or X-Hub-Signature-256 header (GitHub).
"""

import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import src.config as config_module
from src.db import get_session
from src.models.integration import WebhookDelivery, WorkspaceIntegration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Maximum allowed age of a webhook timestamp (seconds) to guard against replays.
_MAX_WEBHOOK_AGE_SECONDS = 60


@router.post("/linear")
async def receive_linear_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Receive and process a webhook event from Linear.

    This endpoint is NOT JWT-protected -- webhooks come from Linear directly.
    Security is provided by HMAC-SHA256 signature verification.

    Steps:
    1. Read raw body bytes (HMAC must be computed on exact bytes Linear sent)
    2. Verify HMAC-SHA256 signature from Linear-Signature header
    3. Validate webhook timestamp to guard against replay attacks
    4. Check Linear-Delivery header UUID for idempotent duplicate detection
    5. Determine workspace from organizationId in payload
    6. Delegate event processing to background task for fast response
    """
    settings = config_module.get_settings()

    # 1. Read raw body bytes
    raw_body = await request.body()

    # 2. Verify HMAC-SHA256 signature
    signature = request.headers.get("Linear-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Linear-Signature header",
        )

    expected_signature = hmac.new(
        settings.LINEAR_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    # Parse payload after signature verification
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # 3. Validate webhook timestamp (replay protection)
    webhook_timestamp = payload.get("webhookTimestamp")
    if webhook_timestamp is not None:
        # Linear sends timestamp in milliseconds
        now_ms = int(time.time() * 1000)
        age_seconds = abs(now_ms - webhook_timestamp) / 1000
        if age_seconds > _MAX_WEBHOOK_AGE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook timestamp too old",
            )

    # 4. Check idempotency via Linear-Delivery header
    delivery_id = request.headers.get("Linear-Delivery")
    if not delivery_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Linear-Delivery header",
        )

    # Check if we already processed this delivery
    stmt = select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Already processed -- return 200 without re-processing
        return {"status": "already_processed"}

    # Record this delivery for idempotency
    delivery = WebhookDelivery(delivery_id=delivery_id, provider="linear")
    session.add(delivery)
    await session.commit()

    # 5. Determine workspace from organizationId
    organization_id = payload.get("organizationId")
    workspace_id = None

    if organization_id:
        ws_stmt = select(WorkspaceIntegration.workspace_id).where(
            WorkspaceIntegration.provider == "linear",
            WorkspaceIntegration.external_id == organization_id,
        )
        ws_result = await session.execute(ws_stmt)
        workspace_id = ws_result.scalar_one_or_none()

    if workspace_id is None:
        logger.warning(
            "Webhook for unknown organization %s (delivery=%s)",
            organization_id,
            delivery_id,
        )
        return {"status": "unknown_organization"}

    # 6. Delegate event processing to background task
    from src.services.linear_webhook import process_webhook_event

    background_tasks.add_task(process_webhook_event, workspace_id, payload)

    return {"status": "accepted"}


@router.post("/github")
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Receive and process a webhook event from GitHub.

    This endpoint is NOT JWT-protected -- webhooks come from GitHub directly.
    Security is provided by HMAC-SHA256 signature verification via
    the X-Hub-Signature-256 header.

    Steps:
    1. Read raw body bytes (HMAC must be computed on exact bytes GitHub sent)
    2. Verify HMAC-SHA256 signature from X-Hub-Signature-256 header
    3. Check X-GitHub-Delivery header UUID for idempotent duplicate detection
    4. Look up workspace from installation.id in payload
    5. Delegate event processing to background task for fast response
    """
    settings = config_module.get_settings()

    # 1. Read raw body bytes
    raw_body = await request.body()

    # 2. Verify HMAC-SHA256 signature
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header",
        )

    # GitHub sends signature as "sha256=<hex digest>"
    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature format",
        )

    expected_signature = "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature_header, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # 3. Check idempotency via X-GitHub-Delivery header
    delivery_id = request.headers.get("X-GitHub-Delivery")
    if delivery_id:
        # Check if we already processed this delivery
        stmt = select(WebhookDelivery).where(
            WebhookDelivery.delivery_id == delivery_id
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return {"status": "already_processed"}

        # Record this delivery for idempotency
        delivery = WebhookDelivery(delivery_id=delivery_id, provider="github")
        session.add(delivery)
        await session.commit()

    # Parse JSON body
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # 4. Extract event type from X-GitHub-Event header
    event_type = request.headers.get("X-GitHub-Event", "")

    # 5. Delegate to background task for fast response
    from src.services.github_webhook import process_github_event

    background_tasks.add_task(process_github_event, event_type, payload)

    return {"status": "accepted"}
