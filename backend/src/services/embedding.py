"""Embedding generation service for semantic search.

Provides a decoupled interface for generating and storing vector embeddings.
In Phase 2, functions are stubs with correct signatures. Actual embedding
generation via Google GenAI (text-embedding-004, 768 dims) will be implemented
in Phase 4.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def queue_embedding_generation(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_ids: list[UUID],
) -> None:
    """Queue source records for embedding generation.

    Called after ticket/comment sync to mark records as needing embeddings.
    Currently a stub that logs the request. Background processing will be
    implemented in Phase 4.

    Args:
        session: Async database session.
        workspace_id: Workspace the sources belong to.
        source_type: Type of source (e.g. 'linear_ticket', 'linear_comment').
        source_ids: List of source record UUIDs to generate embeddings for.
    """
    logger.info(
        "Embedding generation queued: workspace=%s type=%s count=%d",
        workspace_id,
        source_type,
        len(source_ids),
    )
    # TODO: Store pending embedding jobs for background processing.
    # Phase 4 will implement actual embedding generation via Google GenAI.


async def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for the given text.

    Stub that returns an empty list. Will call Google GenAI
    text-embedding-004 model (768 dimensions matching the DB schema).

    Args:
        text: The text content to embed.

    Returns:
        768-dimensional embedding vector (empty list in stub).
    """
    # TODO: Implement using google-genai text-embedding-004 model.
    # Expected output: list of 768 floats.
    return []


async def process_pending_embeddings(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Process all pending embedding generation jobs for a workspace.

    Finds source records without embeddings and generates them.
    Returns the count of embeddings processed.

    Args:
        session: Async database session.
        workspace_id: Workspace to process embeddings for.

    Returns:
        Number of embeddings generated (0 in stub).
    """
    # TODO: Query embeddings table for source_ids without entries,
    # generate embeddings via generate_embedding(), and insert.
    logger.info(
        "Processing pending embeddings for workspace=%s (stub - no-op)",
        workspace_id,
    )
    return 0
