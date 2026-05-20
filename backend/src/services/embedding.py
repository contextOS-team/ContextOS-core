"""Embedding generation service for semantic search.

Generates and stores 768-dimensional vector embeddings using Google Gemini
gemini-embedding-2-preview (with output_dimensionality=768 to match DB schema).
Provides content-hash-based deduplication to skip unchanged records,
and bulk backfill for pending embeddings.
"""

import logging
from uuid import UUID

from google import genai
from google.genai import types
from lmnr import observe
from src.observability.langfuse_client import langfuse_observe, update_generation
from sqlalchemy import or_, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.code_chunk import CodeChunk
from src.models.context_page import ContextPage
from src.models.embedding import Embedding
from src.models.github import GithubPullRequest, GithubReview
from src.models.gitlab import GitlabMergeRequest, GitlabReview
from src.models.meeting import MeetingSegment, MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.telegram import TelegramMessage
from src.models.jira import JiraComment, JiraIssue
from src.models.ticket import LinearComment, LinearTicket
from src.utils.hashing import compute_content_hash

logger = logging.getLogger(__name__)

# Maximum input length for Gemini embeddings
MAX_INPUT_CHARS = 30_000

# Current model constants
EMBEDDING_MODEL_NAME = "gemini-embedding-2-preview"
EMBEDDING_MODEL_VERSION = "v1"

# Output dimensions (matching DB schema)
EMBEDDING_DIMENSIONS = 768

# Batch size for embedding API calls
BATCH_SIZE = 25

# Maximum IDs per IN clause to avoid oversized SQL queries
IN_CLAUSE_LIMIT = 500

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
        # Base extractor (single message). For threaded messages this is
        # replaced by a thread-aware text built in _enrich_slack_thread_text
        # so each vector carries the surrounding discussion — a lone
        # "ок, задача не крит" embeds nowhere near its ticket otherwise.
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
    "gitlab_merge_request": (
        GitlabMergeRequest,
        lambda r: f"{r.title}\n\n{r.description or ''}".strip(),
    ),
    "gitlab_review": (
        GitlabReview,
        lambda r: r.body or "",
    ),
    "notion_page": (
        NotionPage,
        # Return empty string for pages without content — this causes
        # queue_embedding_generation to skip them, preventing generic
        # embeddings that pollute hybrid search results.
        lambda r: f"{r.title}\n\n{r.content}".strip() if r.content else "",
    ),
    "context_page": (
        ContextPage,
        lambda r: f"{r.title}\n\n{r.content}".strip(),
    ),
    "code_chunk": (
        CodeChunk,
        lambda r: f"# {r.symbol_type} {r.symbol_name} in {r.file_path}\n\n{r.content}".strip(),
    ),
    "telegram_message": (
        TelegramMessage,
        lambda r: r.text,
    ),
    "jira_issue": (
        JiraIssue,
        lambda r: f"{r.jira_key}: {r.summary}\n\n{r.description or ''}".strip(),
    ),
    "jira_comment": (
        JiraComment,
        lambda r: r.body or "",
    ),
}

def _slack_archive_url(channel_id: str | None, slack_ts: str | None) -> str | None:
    """Indirection to ``slack_events.slack_archive_url``.

    Inlined here to avoid a top-level import cycle (slack_events imports
    this module to enqueue embeddings on ingest).
    """
    from src.services.slack_events import slack_archive_url

    return slack_archive_url(channel_id, slack_ts)


# Map source_type to (title_extractor, snippet_extractor, url_extractor) for privacy-safe
# metadata storage. Stored in embedding metadata so raw source content can be deleted.
_SUMMARY_EXTRACT_MAP: dict[str, tuple] = {
    "linear_ticket": (
        lambda r: r.title,
        lambda r: (r.description or "")[:300],
        lambda r: f"https://linear.app/issue/{r.identifier}",
    ),
    "linear_comment": (
        lambda r: f"Comment by {r.author_name or 'Unknown'}",
        lambda r: (r.body or "")[:300],
        lambda r: None,
    ),
    "slack_message": (
        lambda r: f"Slack by {r.user_name or 'Unknown'} in #{r.channel_name or 'unknown'}",
        lambda r: r.text[:300],
        lambda r: _slack_archive_url(r.channel_id, r.slack_ts),
    ),
    "meeting_transcript": (
        lambda r: f"Meeting: {r.title or 'Untitled'}",
        lambda r: (r.transcript or "")[:300],
        lambda r: None,
    ),
    "meeting_segment": (
        lambda r: f"Segment by {r.speaker_name or 'Unknown'}",
        lambda r: r.text[:300],
        lambda r: None,
    ),
    "github_pull_request": (
        lambda r: f"PR #{r.number}: {r.title}",
        lambda r: f"State: {'merged' if r.github_merged_at else r.state} | Author: {r.author}\n{(r.description or '')[:200]}",
        lambda r: f"https://github.com/{r.repo_full_name}/pull/{r.number}",
    ),
    "github_review": (
        lambda r: f"Review by {r.author} ({r.state})",
        lambda r: (r.body or "")[:300],
        lambda r: None,
    ),
    "gitlab_merge_request": (
        lambda r: f"MR !{r.iid}: {r.title}",
        lambda r: f"State: {'merged' if r.gitlab_merged_at else r.state} | Author: {r.author}\n{(r.description or '')[:200]}",
        lambda r: f"https://gitlab.com/{r.project_path}/-/merge_requests/{r.iid}",
    ),
    "gitlab_review": (
        lambda r: f"Review by {r.author} ({r.state})",
        lambda r: (r.body or "")[:300],
        lambda r: None,
    ),
    "notion_page": (
        lambda r: r.title,
        lambda r: (r.content or "")[:300],
        lambda r: r.url if hasattr(r, "url") else None,
    ),
    "code_chunk": (
        lambda r: f"{r.symbol_type}: {r.symbol_name} ({r.repo_full_name}:{r.file_path})",
        lambda r: r.content[:300],
        lambda r: None,
    ),
    "telegram_message": (
        lambda r: f"Telegram by {r.from_first_name or r.from_username or 'Unknown'} in {r.chat_title or 'DM'}",
        lambda r: r.text[:300],
        lambda r: None,
    ),
    "jira_issue": (
        lambda r: f"{r.jira_key}: {r.summary}",
        lambda r: (r.description or "")[:300],
        lambda r: None,
    ),
    "jira_comment": (
        lambda r: f"Jira comment by {r.author_name or 'Unknown'}",
        lambda r: (r.body or "")[:300],
        lambda r: None,
    ),
    "context_page": (
        lambda r: r.title,
        lambda r: (r.content or "")[:300],
        lambda r: None,
    ),
}


def _extract_summary_metadata(source_type: str, record: object) -> dict:
    """Extract title/snippet/url from a source record for embedding metadata."""
    if source_type not in _SUMMARY_EXTRACT_MAP:
        return {}
    title_fn, snippet_fn, url_fn = _SUMMARY_EXTRACT_MAP[source_type]
    try:
        return {
            "title": title_fn(record),
            "snippet": snippet_fn(record),
            "url": url_fn(record),
        }
    except Exception:
        return {}


# Lazy singleton for the Gemini client
_gemini_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    """Return a cached Gemini client."""
    global _gemini_client  # noqa: PLW0603
    if _gemini_client is None:
        from src.config import get_settings
        settings = get_settings()
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


@langfuse_observe(name="generate_embedding", as_type="embedding")
@observe(name="generate_embedding")
async def generate_embedding(text_content: str) -> list[float]:
    """Generate a 768-dimensional vector embedding for the given text.

    Uses Gemini gemini-embedding-2-preview with output_dimensionality=768
    to match the DB schema. Input is truncated to MAX_INPUT_CHARS.

    Args:
        text_content: The text content to embed.

    Returns:
        768-dimensional embedding vector as a list of floats.
    """
    if not text_content.strip():
        return [0.0] * EMBEDDING_DIMENSIONS

    truncated = text_content[:MAX_INPUT_CHARS]

    update_generation(model=EMBEDDING_MODEL_NAME)

    client = _get_gemini_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL_NAME,
        contents=truncated,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    return list(response.embeddings[0].values)


@langfuse_observe(name="generate_embeddings_batch", as_type="embedding")
@observe(name="generate_embeddings_batch")
async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate 768-dimensional embeddings for multiple texts in one API call.

    Gemini embed_content supports list inputs natively.
    Results are returned in the same order as the input texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of 768-dimensional embedding vectors (same order as input).
    """
    if not texts:
        return []

    truncated = [t[:MAX_INPUT_CHARS] if t.strip() else "" for t in texts]

    update_generation(
        model=EMBEDDING_MODEL_NAME,
        usage={"input": len(texts)},
    )

    client = _get_gemini_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL_NAME,
        contents=truncated,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    return [list(e.values) for e in response.embeddings]


# Max sibling replies (newest-first, then re-ordered) folded into a
# threaded message's embedding text. Enough to carry the discussion's
# gist without diluting the focal message's own signal.
_SLACK_THREAD_CONTEXT_LIMIT = 12


async def _build_slack_thread_texts(
    session: AsyncSession,
    records: list[SlackMessage],
) -> dict[UUID, str]:
    """Build thread-aware embedding text for Slack messages.

    A Slack message embedded in isolation is often a few words
    ("да", "поэтапно") that share no vocabulary with the ticket that
    should retrieve them. We anchor each threaded message to its thread:
    the root message plus chronologically-prior siblings, so the vector
    lands near the discussion topic instead of in noise.

    Returns {source_id: thread_text}. Messages with no thread (thread_ts
    NULL and not a parent) are omitted — the caller keeps the plain text.
    """
    # Group the focal records by their thread key. For a reply that's
    # parent_ts; for a parent it's its own slack_ts; standalone messages
    # have neither and are skipped.
    thread_keys: dict[tuple[UUID, str], list[SlackMessage]] = {}
    for r in records:
        key_ts = r.parent_ts or (
            r.slack_ts if (r.thread_ts and r.thread_ts == r.slack_ts) else None
        )
        if not key_ts:
            continue
        thread_keys.setdefault((r.workspace_id, key_ts), []).append(r)

    if not thread_keys:
        return {}

    result: dict[UUID, str] = {}
    for (ws_id, root_ts), focal_msgs in thread_keys.items():
        # Pull the whole thread: the root (slack_ts == root_ts) plus every
        # reply (parent_ts == root_ts), oldest first.
        stmt = (
            select(SlackMessage)
            .where(
                SlackMessage.workspace_id == ws_id,
                SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
                or_(
                    SlackMessage.slack_ts == root_ts,
                    SlackMessage.parent_ts == root_ts,
                ),
            )
            .order_by(SlackMessage.slack_created_at)
        )
        thread_msgs = list((await session.execute(stmt)).scalars().all())
        if not thread_msgs:
            continue

        root = next(
            (m for m in thread_msgs if m.slack_ts == root_ts), None
        )
        for focal in focal_msgs:
            # Prior siblings = thread messages strictly before this one.
            prior = [
                m
                for m in thread_msgs
                if m.slack_created_at
                and focal.slack_created_at
                and m.slack_created_at < focal.slack_created_at
                and m.id != focal.id
            ][-_SLACK_THREAD_CONTEXT_LIMIT:]

            lines: list[str] = []
            if root is not None and root.id != focal.id:
                who = root.user_name or "Unknown"
                lines.append(f"[thread] {who}: {root.text}")
            for m in prior:
                if root is not None and m.id == root.id:
                    continue
                who = m.user_name or "Unknown"
                lines.append(f"{who}: {m.text}")
            who_f = focal.user_name or "Unknown"
            lines.append(f">>> {who_f}: {focal.text}")
            result[focal.id] = "\n".join(lines).strip()

    return result


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

    # --- Bulk-load source records (chunked to avoid oversized IN clauses) ---
    records_by_id: dict[UUID, object] = {}
    for i in range(0, len(source_ids), IN_CLAUSE_LIMIT):
        batch_ids = source_ids[i:i + IN_CLAUSE_LIMIT]
        source_stmt = select(model_cls).where(model_cls.id.in_(batch_ids))  # type: ignore[union-attr]
        source_result = await session.execute(source_stmt)
        for r in source_result.scalars().all():
            records_by_id[r.id] = r

    # --- Bulk-load existing embedding hashes (chunked) ---
    existing_hashes: dict[UUID, str] = {}
    for i in range(0, len(source_ids), IN_CLAUSE_LIMIT):
        batch_ids = source_ids[i:i + IN_CLAUSE_LIMIT]
        existing_hash_stmt = select(Embedding.source_id, Embedding.content_hash).where(
            Embedding.source_type == source_type,
            Embedding.source_id.in_(batch_ids),  # type: ignore[union-attr]
        )
        existing_result = await session.execute(existing_hash_stmt)
        for row in existing_result.fetchall():
            existing_hashes[row[0]] = row[1]

    # --- Slack: build thread-aware text so each vector carries the
    # surrounding discussion, not just an isolated fragment. ---
    slack_thread_texts: dict[UUID, str] = {}
    if source_type == "slack_message":
        try:
            slack_thread_texts = await _build_slack_thread_texts(
                session, list(records_by_id.values())
            )
        except Exception:
            logger.exception(
                "Slack thread-context build failed; falling back to "
                "per-message text for this batch"
            )

    # --- Diff in-memory ---
    pending: list[tuple[UUID, str, str]] = []  # (source_id, text, content_hash)

    for source_id in source_ids:
        try:
            record = records_by_id.get(source_id)
            if record is None:
                continue

            text_content = slack_thread_texts.get(source_id) or extract_text(
                record
            )
            if not text_content or not text_content.strip():
                continue

            content_hash = compute_content_hash(text_content)

            if existing_hashes.get(source_id) == content_hash:
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

        for (source_id, text_content, content_hash), embedding_vector in zip(batch, embeddings):
            try:
                search_content = text_content[:MAX_INPUT_CHARS]

                # Extract title/snippet/url for privacy-safe metadata.
                # This allows raw source content to be deleted later
                # while preserving display-ready summaries.
                record = records_by_id.get(source_id)
                summary_meta = _extract_summary_metadata(source_type, record) if record else {}

                upsert_stmt = (
                    insert(Embedding)
                    .values(
                        workspace_id=workspace_id,
                        source_type=source_type,
                        source_id=source_id,
                        content_hash=content_hash,
                        embedding=embedding_vector,
                        search_content=search_content,
                        metadata_=summary_meta,
                        model_name=EMBEDDING_MODEL_NAME,
                        model_version=EMBEDDING_MODEL_VERSION,
                    )
                    .on_conflict_do_update(
                        constraint="embeddings_source_type_source_id_key",
                        set_={
                            "content_hash": content_hash,
                            "embedding": embedding_vector,
                            "search_content": search_content,
                            "metadata": summary_meta,
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

    # Clean up embeddings for Notion pages that have no content — these
    # produce generic vectors that pollute hybrid search results.
    cleaned = await _soft_delete_empty_notion_embeddings(session, workspace_id)
    if cleaned:
        logger.info(
            "Soft-deleted %d embeddings for content-less Notion pages in workspace %s",
            cleaned, workspace_id,
        )

    logger.info(
        "Processed %d pending embeddings for workspace %s",
        count,
        workspace_id,
    )
    return count


async def _soft_delete_empty_notion_embeddings(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Soft-delete embeddings for Notion pages that have NULL content.

    These pages produce weak/generic embedding vectors that match
    everything with moderate similarity, polluting search results.

    Returns the number of embeddings soft-deleted.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    update_stmt = text("""
        UPDATE embeddings
        SET deleted_at = :now
        WHERE workspace_id = :workspace_id
          AND source_type = 'notion_page'
          AND deleted_at IS NULL
          AND source_id IN (
              SELECT id FROM notion_pages
              WHERE workspace_id = :workspace_id
                AND content IS NULL
                AND deleted_at IS NULL
          )
    """)
    result = await session.execute(
        update_stmt,
        {"now": now, "workspace_id": workspace_id},
    )
    return result.rowcount


async def backfill_search_content(
    session: AsyncSession,
    workspace_id: UUID,
    batch_size: int = 100,
) -> int:
    """Backfill search_content for embeddings that have NULL search_content.

    Looks up the original source record for each embedding, extracts the
    text content, and updates the search_content column.

    Args:
        session: Async database session.
        workspace_id: Workspace to backfill.
        batch_size: Number of embeddings to process per batch.

    Returns:
        Number of embeddings updated.
    """
    stmt = (
        select(Embedding)
        .where(
            Embedding.workspace_id == workspace_id,
            Embedding.search_content.is_(None),  # type: ignore[union-attr]
            Embedding.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(batch_size)
    )
    result = await session.execute(stmt)
    embeddings = result.scalars().all()

    updated = 0
    for emb in embeddings:
        if emb.source_type not in SOURCE_TYPE_MAP:
            continue

        model_cls, extract_text = SOURCE_TYPE_MAP[emb.source_type]
        source_stmt = select(model_cls).where(model_cls.id == emb.source_id)
        source_result = await session.execute(source_stmt)
        record = source_result.scalar_one_or_none()

        if record is None:
            continue

        text_content = extract_text(record)
        if not text_content or not text_content.strip():
            continue

        emb.search_content = text_content[:MAX_INPUT_CHARS]
        session.add(emb)
        updated += 1

    logger.info(
        "Backfilled search_content for %d embeddings in workspace %s",
        updated,
        workspace_id,
    )
    return updated
