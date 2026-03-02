"""Embedding generation service for semantic search.

Generates and stores 768-dimensional vector embeddings using OpenAI
text-embedding-3-small (with dimensions=768 to match DB schema).
Provides content-hash-based deduplication to skip unchanged records,
and bulk backfill for pending embeddings.
"""

import hashlib
import logging
import re
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
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.ticket import LinearComment, LinearTicket

logger = logging.getLogger(__name__)

# Maximum input length for text-embedding-3-small (8191 tokens ≈ ~30K chars)
MAX_INPUT_CHARS = 30_000

# Current model constants
EMBEDDING_MODEL_NAME = "text-embedding-3-small"
EMBEDDING_MODEL_VERSION = "v1"

# Batch size for embedding API calls (20-50 per CONTEXT.md; 25 is a safe middle ground)
BATCH_SIZE = 25

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
    "notion_page": (
        NotionPage,
        lambda r: f"{r.title}\n\n{r.content or ''}".strip(),
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


def _normalize_for_hash(text_content: str) -> str:
    """Normalize text for content hash comparison.

    Collapses all whitespace sequences (spaces, tabs, newlines) into
    single spaces and strips leading/trailing whitespace. This prevents
    trivial formatting changes from triggering re-embedding.

    Args:
        text_content: Raw text content.

    Returns:
        Normalized text string.
    """
    return re.sub(r'\s+', ' ', text_content).strip()


def _compute_content_hash(text_content: str) -> str:
    """Compute SHA-256 hash of normalized content for change detection.

    Normalizes whitespace before hashing so trivial formatting edits
    (spacing, line breaks) do not trigger re-embedding.
    """
    normalized = _normalize_for_hash(text_content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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


@observe(name="generate_embeddings_batch")
async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate 768-dimensional embeddings for multiple texts in one API call.

    OpenAI text-embedding-3-small supports list inputs natively.
    Results are returned in the same order as the input texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of 768-dimensional embedding vectors (same order as input).
    """
    if not texts:
        return []

    truncated = [t[:MAX_INPUT_CHARS] if t.strip() else "" for t in texts]
    client = _get_openai_client()
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=truncated,
        dimensions=768,
    )
    # OpenAI returns data sorted by index
    sorted_data = sorted(response.data, key=lambda d: d.index)
    return [list(d.embedding) for d in sorted_data]


async def queue_embedding_generation(
    session: AsyncSession,
    workspace_id: UUID,
    source_type: str,
    source_ids: list[UUID],
) -> None:
    """Generate and store embeddings for the given source records.

    Now processes records in batches of BATCH_SIZE for efficiency.
    Called after ticket/comment/PR sync or by the embedding worker.

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

    # Collect records that need embedding
    pending: list[tuple[UUID, str, str]] = []  # (source_id, text, content_hash)

    for source_id in source_ids:
        try:
            stmt = select(model_cls).where(model_cls.id == source_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                continue

            text_content = extract_text(record)
            if not text_content or not text_content.strip():
                continue

            content_hash = _compute_content_hash(text_content)

            # Check existing hash
            existing_stmt = select(Embedding.content_hash).where(
                Embedding.source_type == source_type,
                Embedding.source_id == source_id,
            )
            existing_result = await session.execute(existing_stmt)
            existing_hash = existing_result.scalar_one_or_none()

            if existing_hash == content_hash:
                continue

            pending.append((source_id, text_content, content_hash))
        except Exception:
            logger.exception(
                "Failed to prepare embedding for %s %s", source_type, source_id
            )

    if not pending:
        return

    # Process in batches
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        texts = [item[1] for item in batch]

        try:
            embeddings = await generate_embeddings_batch(texts)
        except Exception:
            logger.exception(
                "Batch embedding generation failed for %s (batch %d)",
                source_type, i // BATCH_SIZE,
            )
            continue

        for (source_id, _, content_hash), embedding_vector in zip(batch, embeddings):
            try:
                upsert_stmt = (
                    insert(Embedding)
                    .values(
                        workspace_id=workspace_id,
                        source_type=source_type,
                        source_id=source_id,
                        content_hash=content_hash,
                        embedding=embedding_vector,
                        model_name=EMBEDDING_MODEL_NAME,
                        model_version=EMBEDDING_MODEL_VERSION,
                    )
                    .on_conflict_do_update(
                        constraint="embeddings_source_type_source_id_key",
                        set_={
                            "content_hash": content_hash,
                            "embedding": embedding_vector,
                            "model_name": EMBEDDING_MODEL_NAME,
                            "model_version": EMBEDDING_MODEL_VERSION,
                            "deleted_at": None,
                        },
                    )
                )
                await session.execute(upsert_stmt)
                logger.info(
                    "Generated embedding for %s %s (hash=%s...)",
                    source_type, source_id, content_hash[:12],
                )
            except Exception:
                logger.exception(
                    "Failed to upsert embedding for %s %s",
                    source_type, source_id,
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
