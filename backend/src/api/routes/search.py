"""Search API routes.

Provides endpoints for semantic search across all connected sources.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SearchRequest(BaseModel):
    """Request body for semantic search."""

    query: str
    sources: list[str] | None = None
    limit: int = 10


class SearchResult(BaseModel):
    """A single search result."""

    id: str
    source: str
    title: str
    snippet: str
    score: float
    metadata: dict[str, Any] = {}


class SearchResponse(BaseModel):
    """Response containing search results."""

    results: list[SearchResult]
    total: int
    query: str


@router.post("", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Perform semantic search across all connected sources.

    Queries the vector store for relevant content from Slack, Notion,
    Linear, and meeting transcripts.

    Args:
        request: The search query and optional filters.

    Returns:
        Ranked search results with relevance scores.
    """
    # TODO: implement — query embeddings store and return ranked results
    return SearchResponse(
        results=[],
        total=0,
        query=request.query,
    )
