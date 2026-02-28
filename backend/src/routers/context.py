"""Context page and semantic search API endpoints.

Provides endpoints for generating, retrieving, and searching context pages
that synthesize information from Linear tickets, PRs, Slack, and meetings.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import async_session, get_session
from src.dependencies import UserContext, get_current_user
from src.models.context_page import ContextPage
from src.services.synthesis import generate_context_page

logger = logging.getLogger(__name__)

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


async def _generate_in_background(workspace_id, ticket_identifier: str) -> None:
    """Background task for context page generation with its own session."""
    async with async_session() as session:
        try:
            await generate_context_page(session, workspace_id, ticket_identifier)
            await session.commit()
        except Exception:
            logger.exception(
                "Background context generation failed for %s", ticket_identifier
            )
            await session.rollback()


@router.post("/{ticket_identifier}/generate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_context_generation(
    ticket_identifier: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Trigger context page generation for a ticket.

    Starts generation as a background task and returns 202 Accepted immediately.
    """
    background_tasks.add_task(
        _generate_in_background, user.workspace_id, ticket_identifier
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
    """Semantic search across all embedded content.

    Generates an embedding for the query text, then calls match_embeddings()
    to find the most similar content in the workspace.
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
        SELECT id, source_type, source_id, similarity, metadata
        FROM match_embeddings(
            CAST(:query_embedding AS vector),
            CAST(:workspace_id AS uuid),
            :source_type,
            0.5,
            :limit
        )
    """)

    result = await session.execute(
        match_stmt,
        {
            "query_embedding": str(query_embedding),
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
            "metadata": row[4],
        })

    return {
        "query": q,
        "results": results,
        "count": len(results),
    }
