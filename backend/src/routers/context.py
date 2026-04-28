"""Context page and semantic search API endpoints.

Provides endpoints for generating, retrieving, and searching context pages
that synthesize information from Linear tickets, PRs, Slack, and meetings.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sse_starlette import EventSourceResponse, ServerSentEvent

from src.config import Settings, get_settings
from src.db import async_session, get_session
from src.dependencies import UserContext, get_current_user
from src.models.context_page import ContextPage
from src.models.ticket import LinearTicket
from src.services.synthesis import generate_context_page, generate_context_page_stream

logger = logging.getLogger(__name__)

# SEC-01: JQL injection prevention -- only valid Jira/Linear ticket identifiers pass
TICKET_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def _validate_ticket_identifier(identifier: str) -> str:
    """Validate ticket identifier matches KEY-123 format.

    Prevents JQL injection by rejecting any identifier that does not
    match the strict allowlist pattern.

    Raises:
        HTTPException(400): If identifier format is invalid.
    """
    if not TICKET_ID_PATTERN.match(identifier):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticket identifier format. Expected KEY-123.",
        )
    return identifier


router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("/{ticket_identifier}")
async def get_context_page(
    ticket_identifier: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the context page for a ticket.

    Returns the most recent context page for the given ticket identifier.
    Returns 404 if no context page exists.
    """
    stmt = select(ContextPage).where(
        ContextPage.workspace_id == user.workspace_id,
        ContextPage.ticket_identifier == ticket_identifier,
        ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    page = result.scalar_one_or_none()

    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No context page found for {ticket_identifier}",
        )

    return {
        "id": str(page.id),
        "ticket_identifier": page.ticket_identifier,
        "title": page.title,
        "content": page.content,
        "summary": page.summary,
        "status": page.status,
        "sources": page.sources,
        "generated_at": page.generated_at.isoformat() if page.generated_at else None,
        "generation_model": page.generation_model,
        "generation_tokens_used": page.generation_tokens_used,
        "created_at": page.created_at.isoformat() if page.created_at else None,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }


@router.get("/{ticket_identifier}/generate-stream")
async def stream_context_generation(
    ticket_identifier: str,
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    linear_issue_id: str | None = Query(default=None),
    jira_issue_id: str | None = Query(default=None),
):
    """Stream context generation progress via SSE.

    CRITICAL: Create a dedicated session INSIDE the generator, not via Depends.
    FastAPI closes Depends sessions when the response object is returned,
    which for SSE is immediately -- before the stream ends.
    """

    # SEC-01: Validate before any JQL interpolation
    _validate_ticket_identifier(ticket_identifier)

    async def event_generator():
        async with async_session() as session:
            try:
                # Check for concurrent generation — but treat pages stuck in
                # "generating" for more than 5 minutes as stale (the previous
                # attempt likely crashed without updating status).
                stmt = select(ContextPage).where(
                    ContextPage.workspace_id == user.workspace_id,
                    ContextPage.ticket_identifier == ticket_identifier,
                    ContextPage.status == "generating",
                    ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
                )
                result = await session.execute(stmt)
                generating_page = result.scalar_one_or_none()
                if generating_page:
                    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
                    page_updated_at = generating_page.updated_at
                    if page_updated_at is not None and page_updated_at.tzinfo is None:
                        page_updated_at = page_updated_at.replace(tzinfo=timezone.utc)
                    if page_updated_at and page_updated_at > stale_cutoff:
                        yield ServerSentEvent(
                            data=json.dumps({"event": "error", "message": "Generation already in progress"}),
                            event="error",
                        )
                        return
                    # Stale — reset status so generation can proceed
                    logger.info(
                        "Resetting stale generating status for %s (stuck since %s)",
                        ticket_identifier, generating_page.updated_at,
                    )
                    generating_page.status = "error"
                    await session.flush()

                # Sync ticket if not found locally
                if linear_issue_id:
                    ticket_stmt = select(LinearTicket).where(
                        LinearTicket.workspace_id == user.workspace_id,
                        LinearTicket.identifier == ticket_identifier,
                        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                    ticket_result = await session.execute(ticket_stmt)
                    if ticket_result.scalar_one_or_none() is None:
                        from src.services.linear_sync import sync_single_ticket
                        from src.services.linear_oauth import get_valid_access_token

                        logger.info(
                            "SSE: Ticket %s not found locally, syncing from Linear",
                            ticket_identifier,
                        )
                        access_token = await get_valid_access_token(
                            session, user.workspace_id, user.user_id, settings
                        )
                        await sync_single_ticket(
                            session, user.workspace_id, access_token, linear_issue_id
                        )
                        await session.commit()
                elif jira_issue_id:
                    from src.models.jira import JiraIssue
                    jira_stmt = select(JiraIssue).where(
                        JiraIssue.workspace_id == user.workspace_id,
                        JiraIssue.jira_id == jira_issue_id,
                        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                    jira_result = await session.execute(jira_stmt)
                    if jira_result.scalar_one_or_none() is None:
                        try:
                            from src.services.jira_sync import sync_jira_issues
                            safe_key = ticket_identifier.replace('\\', '').replace('"', '')
                            await sync_jira_issues(
                                session, user.workspace_id, settings,
                                jql=f'key = "{safe_key}"',
                            )
                            await session.commit()
                        except Exception:
                            logger.warning(
                                "SSE: Failed to sync Jira issue %s",
                                ticket_identifier, exc_info=True,
                            )

                async for event in generate_context_page_stream(
                    session, user.workspace_id, ticket_identifier
                ):
                    yield ServerSentEvent(
                        data=json.dumps(event),
                        event=event["event"],
                    )

                await session.commit()
            except Exception as e:
                logger.exception("SSE generation failed for %s", ticket_identifier)
                await session.rollback()
                yield ServerSentEvent(
                    data=json.dumps({"event": "error", "message": str(e)}),
                    event="error",
                )

    return EventSourceResponse(event_generator())


async def _generate_in_background(
    workspace_id: UUID,
    user_id: UUID,
    ticket_identifier: str,
    linear_issue_id: str | None,
    jira_issue_id: str | None,
    settings: Settings,
) -> None:
    """Background task for context page generation with its own session.

    If the ticket doesn't exist locally, syncs it from the appropriate
    provider (Linear or Jira) before generating the context page.
    """
    async with async_session() as session:
        try:
            if linear_issue_id:
                stmt = select(LinearTicket).where(
                    LinearTicket.workspace_id == workspace_id,
                    LinearTicket.identifier == ticket_identifier,
                    LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
                )
                result = await session.execute(stmt)
                if result.scalar_one_or_none() is None:
                    from src.services.linear_sync import sync_single_ticket
                    from src.services.linear_oauth import get_valid_access_token

                    logger.info(
                        "Ticket %s not found locally, syncing from Linear (issue_id=%s)",
                        ticket_identifier,
                        linear_issue_id,
                    )
                    access_token = await get_valid_access_token(
                        session, workspace_id, user_id, settings
                    )
                    await sync_single_ticket(
                        session, workspace_id, access_token, linear_issue_id
                    )
                    await session.commit()
            elif jira_issue_id:
                from src.models.jira import JiraIssue
                jira_stmt = select(JiraIssue).where(
                    JiraIssue.workspace_id == workspace_id,
                    JiraIssue.jira_id == jira_issue_id,
                    JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
                )
                jira_result = await session.execute(jira_stmt)
                if jira_result.scalar_one_or_none() is None:
                    try:
                        from src.services.jira_sync import sync_jira_issues
                        safe_key = ticket_identifier.replace('\\', '').replace('"', '')
                        await sync_jira_issues(
                            session, workspace_id, settings,
                            jql=f'key = "{safe_key}"',
                        )
                        await session.commit()
                    except Exception:
                        logger.warning(
                            "Background: Failed to sync Jira issue %s",
                            ticket_identifier, exc_info=True,
                        )

            await generate_context_page(session, workspace_id, ticket_identifier)
            await session.commit()
        except Exception:
            logger.exception(
                "Background context generation failed for %s", ticket_identifier
            )
            await session.rollback()


class GenerateRequest(PydanticBaseModel):
    """Optional body for POST /{ticket_identifier}/generate."""

    linear_issue_id: str | None = None
    jira_issue_id: str | None = None


@router.post("/{ticket_identifier}/generate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_context_generation(
    ticket_identifier: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    body: GenerateRequest | None = None,
) -> dict:
    """Trigger context page generation for a ticket.

    Starts generation as a background task and returns 202 Accepted immediately.
    If linear_issue_id is provided and the ticket doesn't exist locally,
    it will be synced from Linear first.
    """
    # SEC-01: Validate before any JQL interpolation
    _validate_ticket_identifier(ticket_identifier)

    background_tasks.add_task(
        _generate_in_background,
        user.workspace_id,
        user.user_id,
        ticket_identifier,
        body.linear_issue_id if body else None,
        body.jira_issue_id if body else None,
        settings,
    )

    return {
        "status": "accepted",
        "message": f"Context generation started for {ticket_identifier}",
        "ticket_identifier": ticket_identifier,
    }


@router.get("/", include_in_schema=True)
async def search_context(
    q: Annotated[str, Query(min_length=1, max_length=500)],
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    source_type: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Hybrid search across all embedded content.

    Generates an embedding for the query text, then calls hybrid_search()
    to find the most relevant content using both vector similarity and
    full-text search.
    """
    from src.services.embedding import generate_embedding

    try:
        query_embedding = await generate_embedding(q)
    except Exception:
        logger.exception("Failed to generate search embedding")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate search embedding",
        )

    match_stmt = text("""
        SELECT id, source_type, source_id, similarity, keyword_rank, combined_score, metadata
        FROM hybrid_search(
            CAST(:query_embedding AS vector),
            :query_text,
            CAST(:workspace_id AS uuid),
            :source_type,
            0.7,
            0.3,
            0.5,
            :limit
        )
    """)

    result = await session.execute(
        match_stmt,
        {
            "query_embedding": str(query_embedding),
            "query_text": q,
            "workspace_id": str(user.workspace_id),
            "source_type": source_type,
            "limit": limit,
        },
    )

    results = []
    for row in result.fetchall():
        results.append({
            "id": str(row[0]),
            "source_type": row[1],
            "source_id": str(row[2]),
            "similarity": round(float(row[3]), 4),
            "keyword_rank": round(float(row[4]), 4),
            "combined_score": round(float(row[5]), 4),
            "metadata": row[6],
        })

    return {
        "query": q,
        "results": results,
        "count": len(results),
    }
