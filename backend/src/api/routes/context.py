"""Context pages API routes.

Provides endpoints for retrieving and generating context pages
associated with development tickets.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ContextPage(BaseModel):
    """Structured context page for a ticket."""

    ticket_id: str
    title: str
    summary: str
    slack_threads: list[dict[str, Any]]
    notion_docs: list[dict[str, Any]]
    linear_activity: list[dict[str, Any]]
    meeting_references: list[dict[str, Any]]
    synthesized_context: str


class GenerateContextRequest(BaseModel):
    """Request body for triggering context generation."""

    force_refresh: bool = False
    sources: list[str] | None = None


class GenerateContextResponse(BaseModel):
    """Response after triggering context generation."""

    task_id: str
    status: str


@router.get("/{ticket_id}", response_model=ContextPage)
async def get_context_page(ticket_id: str) -> ContextPage:
    """Retrieve the context page for a given ticket.

    Args:
        ticket_id: The unique identifier of the ticket.

    Returns:
        The synthesized context page with data from all sources.
    """
    # TODO: implement — fetch context page from database
    return ContextPage(
        ticket_id=ticket_id,
        title="",
        summary="",
        slack_threads=[],
        notion_docs=[],
        linear_activity=[],
        meeting_references=[],
        synthesized_context="",
    )


@router.post("/{ticket_id}/generate", response_model=GenerateContextResponse)
async def generate_context_page(
    ticket_id: str,
    request: GenerateContextRequest,
) -> GenerateContextResponse:
    """Trigger context generation for a given ticket.

    Enqueues a background task to gather data from all configured sources
    and synthesize a context page using Claude.

    Args:
        ticket_id: The unique identifier of the ticket.
        request: Configuration for the generation request.

    Returns:
        A response containing the task ID and initial status.
    """
    # TODO: implement — enqueue Celery task for context generation
    return GenerateContextResponse(
        task_id="placeholder-task-id",
        status="queued",
    )
