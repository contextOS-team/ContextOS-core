"""Webhook receiver routes.

Handles incoming webhooks from Linear and Slack, dispatching
them to background workers for processing.
"""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class WebhookResponse(BaseModel):
    """Standard response for webhook receivers."""

    status: str
    message: str


@router.post("/linear", response_model=WebhookResponse)
async def linear_webhook(request: Request) -> WebhookResponse:
    """Handle incoming Linear webhook events.

    Receives issue creation, update, and comment events from Linear
    and enqueues them for background processing.

    Args:
        request: The raw incoming HTTP request from Linear.

    Returns:
        Acknowledgement response.
    """
    payload: dict[str, Any] = await request.json()

    # TODO: implement — validate webhook signature
    # TODO: implement — enqueue process_linear_webhook Celery task
    _ = payload  # suppress unused variable warning

    return WebhookResponse(
        status="accepted",
        message="Linear webhook received",
    )


@router.post("/slack", response_model=WebhookResponse)
async def slack_webhook(request: Request) -> WebhookResponse:
    """Handle incoming Slack event subscription callbacks.

    Receives message, reaction, and thread events from Slack
    and enqueues them for background processing.

    Args:
        request: The raw incoming HTTP request from Slack.

    Returns:
        Acknowledgement response.
    """
    payload: dict[str, Any] = await request.json()

    # Handle Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return WebhookResponse(
            status="ok",
            message=payload.get("challenge", ""),
        )

    # TODO: implement — validate Slack request signature
    # TODO: implement — enqueue process_slack_event Celery task

    return WebhookResponse(
        status="accepted",
        message="Slack event received",
    )
