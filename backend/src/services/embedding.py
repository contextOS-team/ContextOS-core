"""Embedding generation service for semantic search.

Generates and stores 768-dimensional vector embeddings using OpenAI
text-embedding-3-small (with dimensions=768 to match DB schema).
Provides content-hash-based deduplication to skip unchanged records,
and bulk backfill for pending embeddings.
"""

import hashlib
import logging
from uuid import UUID

from lmnr import observe
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.context_page import ContextPage
from src.models.embedding import Embedding
from src.models.github import GithubPullRequest, GithubReview
from src.models.meeting import MeetingSegment, MeetingTranscript
from src.models.slack import SlackMessage
from src.models.ticket import LinearComment, LinearTicket

logger = logging.getLogger(__name__)

# Maximum input length for text-embedding-3-small (8191 tokens ≈ ~30K chars)
MAX_INPUT_CHARS = 30_000

# Map source_type strings to (model class, text extraction function)
SOURCE_TYPE_MAP: dict[str, tuple[type, callable]] = {
    "linear_ticket": (
        LinearTicket,
        lambda r: f"{r.title}\n\n{r.description or ''}".strip(),
    ),
    "linear_comment": (
        LinearComment,
        lambda r: r.body,
    ),
    "slack_message": (
        SlackMessage,
        lambda r: r.text,
    ),
    "meeting_transcript": (
        MeetingTranscript,
        lambda r: f"{r.title or ''}\n\n{r.transcript}".strip(),
    ),
    "meeting_segment": (
        MeetingSegment,
        lambda r: f"{r.speaker_name or 'Unknown'}: {r.text}",
    ),
    "github_pull_request": (
        GithubPullRequest,
        lambda r: f"{r.title}\n\n{r.description or ''}".strip(),
    ),
    "github_review": (
        GithubReview,
        lambda r: r.body or "",
    ),
    "context_page": (
        ContextPage,
        lambda r: f"{r.title}\n\n{r.content}".strip(),
    ),
}

# Lazy singleton for the OpenAI async client
_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client."""
    global _openai_client  # noqa: PLW0603
    if _openai_client is None:
        from src.config import get_settings
        settings = get_settings()
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _compute_content_hash(text_content: str) -> str:
    """Compute SHA-256 hash of content for change detection."""
    return hashlib.sha256(text_content.encode("utf-8")).hexdigest()


@observe(name="generate_embedding")
async def generate_embedding(text_content: str) -> list[float]:
    """Generate a 768-dimensional vector embedding for the given text.

    Uses OpenAI text-embedding-3-small with dimensions=768 to match
    the DB schema. Input is truncated to MAX_INPUT_CHARS.

    Args:
        text_content: The text content to embed.

    Returns:
        768-dimensional embedding vector as a list of floats.
    """
    if not text_content.strip():
        return [0.0] * 768

    truncated = text_content[:MAX_INPUT_CHARS]
    client = _get_openai_client()
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=truncated,
        dimensions=768,
    )
    return list(response.data[0].embedding)


async def queue_embedding_generation(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_ids: list[UUID],
) -> None:
    """Generate and store embeddings for the given source records.

    Called after ticket/comment/PR sync. For each source record:
    1. Looks up the record by ID
    2. Extracts text content
    3. Computes content hash (SHA-256)
    4. Skips if existing embedding has same hash (content unchanged)
    5. Generates embedding via text-embedding-004
    6. Upserts into embeddings table

    Args:
        session: Async database session.
        workspace_id: Workspace the sources belong to.
        source_type: Type of source (e.g. 'linear_ticket', 'linear_comment').
        source_ids: List of source record UUIDs to generate embeddings for.
    """
    if source_type not in SOURCE_TYPE_MAP:
        logger.warning("Unknown source_type for embedding: %s", source_type)
        return

    model_cls, extract_text = SOURCE_TYPE_MAP[source_type]

    for source_id in source_ids:
        try:
            # Look up source record
            stmt = select(model_cls).where(model_cls.id == source_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                logger.warning(
                    "Source record not found: type=%s id=%s", source_type, source_id
                )
                continue

            # Extract text content
            text_content = extract_text(record)
            if not text_content or not text_content.strip():
                logger.debug("Empty content for %s %s, skipping", source_type, source_id)
                continue

            # Compute content hash
            content_hash = _compute_content_hash(text_content)

            # Check if existing embedding has same hash
            existing_stmt = select(Embedding.content_hash).where(
                Embedding.source_type == source_type,
                Embedding.source_id == source_id,
            )
            existing_result = await session.execute(existing_stmt)
            existing_hash = existing_result.scalar_one_or_none()

            if existing_hash == content_hash:
                logger.debug(
                    "Content unchanged for %s %s, skipping embedding",
                    source_type,
                    source_id,
                )
                continue

            # Generate embedding
            embedding_vector = await generate_embedding(text_content)

            # Upsert into embeddings table
            upsert_stmt = (
                insert(Embedding)
                .values(
                    workspace_id=workspace_id,
                    source_type=source_type,
                    source_id=source_id,
                    content_hash=content_hash,
                    embedding=embedding_vector,
                )
                .on_conflict_do_update(
                    constraint="embeddings_source_type_source_id_key",
                    set_={
                        "content_hash": content_hash,
                        "embedding": embedding_vector,
                        "deleted_at": None,
                    },
                )
            )
            await session.execute(upsert_stmt)

            logger.info(
                "Generated embedding for %s %s (hash=%s…)",
                source_type,
                source_id,
                content_hash[:12],
            )
        except Exception:
            logger.exception(
                "Failed to generate embedding for %s %s",
                source_type,
                source_id,
            )


async def process_pending_embeddings(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Process all source records without embeddings for a workspace.

    Finds records across all source types that don't have a corresponding
    embedding row, then generates embeddings for them.

    Args:
        session: Async database session.
        workspace_id: Workspace to process embeddings for.

    Returns:
        Number of embeddings generated.
    """
    count = 0

    for source_type, (model_cls, _) in SOURCE_TYPE_MAP.items():
        # Skip context_page — those are generated, not source data
        if source_type == "context_page":
            continue

        # Find source records without embeddings
        if hasattr(model_cls, "workspace_id"):
            # Subquery: source_ids that already have embeddings
            existing_ids_stmt = select(Embedding.source_id).where(
                Embedding.source_type == source_type,
                Embedding.workspace_id == workspace_id,
                Embedding.deleted_at.is_(None),  # type: ignore[union-attr]
            )

            missing_stmt = (
                select(model_cls.id)
                .where(
                    model_cls.workspace_id == workspace_id,
                    model_cls.id.notin_(existing_ids_stmt),  # type: ignore[union-attr]
                )
            )

            # Filter out soft-deleted records
            if hasattr(model_cls, "deleted_at"):
                missing_stmt = missing_stmt.where(
                    model_cls.deleted_at.is_(None)  # type: ignore[union-attr]
                )

            result = await session.execute(missing_stmt)
            missing_ids = [row[0] for row in result.fetchall()]

            if missing_ids:
                logger.info(
                    "Backfilling %d %s embeddings for workspace %s",
                    len(missing_ids),
                    source_type,
                    workspace_id,
                )
                await queue_embedding_generation(
                    session, workspace_id, source_type, missing_ids
                )
                count += len(missing_ids)

    logger.info(
        "Processed %d pending embeddings for workspace %s",
        count,
        workspace_id,
    )
    return count
