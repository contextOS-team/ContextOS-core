"""Linking engine for finding content related to a Linear ticket.

Combines three signals with weighted scores to find and rank related content:
- Explicit references (weight 1.0): PRs linked via FK, Slack messages containing
  ticket identifier, comments via ticket_id FK
- Semantic similarity (weight 0.7): Embedding cosine similarity via match_embeddings()
- Keyword/trigram (weight 0.4): pg_trgm similarity() on text fields
"""

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.github import GithubPullRequest, GithubReview
from src.models.meeting import MeetingTranscript
from src.models.slack import SlackMessage
from src.models.ticket import LinearComment, LinearTicket
from src.services.embedding import generate_embedding

logger = logging.getLogger(__name__)

# Signal weights for combined scoring
WEIGHT_EXPLICIT = 1.0
WEIGHT_SEMANTIC = 0.7
WEIGHT_KEYWORD = 0.4

# Semantic similarity threshold
SEMANTIC_THRESHOLD = 0.65


@dataclass
class LinkedItem:
    """A piece of content linked to a ticket with relevance scoring."""

    source_type: str
    source_id: UUID
    title: str
    snippet: str
    relevance_score: float
    signals: list[str] = field(default_factory=list)


@dataclass
class LinkingResult:
    """Result of finding related content for a ticket."""

    ticket_id: UUID
    ticket_identifier: str
    items: list[LinkedItem] = field(default_factory=list)


async def _find_explicit_refs(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find content with explicit references to the ticket."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    # 1. PRs linked via linear_ticket_id FK
    pr_stmt = select(GithubPullRequest).where(
        GithubPullRequest.workspace_id == workspace_id,
        GithubPullRequest.linear_ticket_id == ticket.id,
        GithubPullRequest.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    pr_result = await session.execute(pr_stmt)
    for pr in pr_result.scalars().all():
        key = ("github_pull_request", pr.id)
        items[key] = LinkedItem(
            source_type="github_pull_request",
            source_id=pr.id,
            title=f"PR #{pr.number}: {pr.title}",
            snippet=(pr.description or "")[:200],
            relevance_score=WEIGHT_EXPLICIT,
            signals=["explicit_link"],
        )

        # Also find reviews on linked PRs
        review_stmt = select(GithubReview).where(
            GithubReview.pull_request_id == pr.id,
            GithubReview.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        review_result = await session.execute(review_stmt)
        for review in review_result.scalars().all():
            if review.body:
                rkey = ("github_review", review.id)
                items[rkey] = LinkedItem(
                    source_type="github_review",
                    source_id=review.id,
                    title=f"Review by {review.author} ({review.state})",
                    snippet=(review.body or "")[:200],
                    relevance_score=WEIGHT_EXPLICIT,
                    signals=["explicit_link"],
                )

    # 2. Comments on this ticket via ticket_id FK
    comment_stmt = select(LinearComment).where(
        LinearComment.ticket_id == ticket.id,
        LinearComment.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    comment_result = await session.execute(comment_stmt)
    for comment in comment_result.scalars().all():
        key = ("linear_comment", comment.id)
        items[key] = LinkedItem(
            source_type="linear_comment",
            source_id=comment.id,
            title=f"Comment by {comment.author_name or 'Unknown'}",
            snippet=comment.body[:200],
            relevance_score=WEIGHT_EXPLICIT,
            signals=["explicit_link"],
        )

    # 3. Slack messages containing the ticket identifier
    slack_stmt = select(SlackMessage).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.text.ilike(f"%{ticket.identifier}%"),  # type: ignore[union-attr]
        SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    slack_result = await session.execute(slack_stmt)
    for msg in slack_result.scalars().all():
        key = ("slack_message", msg.id)
        items[key] = LinkedItem(
            source_type="slack_message",
            source_id=msg.id,
            title=f"Slack message by {msg.user_name or 'Unknown'} in #{msg.channel_name or 'unknown'}",
            snippet=msg.text[:200],
            relevance_score=WEIGHT_EXPLICIT,
            signals=["explicit_reference"],
        )

    return items


async def _find_semantic_matches(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find semantically similar content via embedding cosine similarity."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    query_text = f"{ticket.title}\n\n{ticket.description or ''}"
    try:
        query_embedding = await generate_embedding(query_text)
    except Exception:
        logger.warning("Failed to generate query embedding for %s", ticket.identifier)
        return items

    if not query_embedding or all(v == 0.0 for v in query_embedding):
        return items

    # Call match_embeddings() SQL function
    # Use CAST instead of :: to avoid asyncpg parameter conflicts
    match_stmt = text("""
        SELECT id, source_type, source_id, similarity, metadata
        FROM match_embeddings(
            CAST(:query_embedding AS vector),
            CAST(:workspace_id AS uuid),
            NULL,
            :threshold,
            20
        )
    """)

    result = await session.execute(
        match_stmt,
        {
            "query_embedding": str(query_embedding),
            "workspace_id": str(workspace_id),
            "threshold": SEMANTIC_THRESHOLD,
        },
    )

    for row in result.fetchall():
        source_type = row[1]
        source_id = row[2]
        similarity = row[3]

        # Skip self-matches (the ticket's own embedding)
        if source_type == "linear_ticket" and source_id == ticket.id:
            continue

        key = (source_type, source_id)
        score = similarity * WEIGHT_SEMANTIC

        # Look up a title/snippet for the match
        title, snippet = await _lookup_source_summary(
            session, source_type, source_id
        )

        items[key] = LinkedItem(
            source_type=source_type,
            source_id=source_id,
            title=title,
            snippet=snippet,
            relevance_score=score,
            signals=["semantic_similarity"],
        )

    return items


async def _find_keyword_matches(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find content with keyword/trigram similarity to ticket title."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    # Extract key terms from title (skip very short words)
    terms = [w for w in ticket.title.split() if len(w) > 3]
    if not terms:
        return items

    search_phrase = " ".join(terms[:8])  # Limit to first 8 meaningful words

    # Trigram similarity on slack_messages.text
    slack_stmt = text("""
        SELECT id, text, user_name, channel_name,
               similarity(text, :phrase) AS sim
        FROM slack_messages
        WHERE workspace_id = :workspace_id
          AND deleted_at IS NULL
          AND similarity(text, :phrase) > 0.15
        ORDER BY sim DESC
        LIMIT 10
    """)

    try:
        slack_result = await session.execute(
            slack_stmt,
            {"phrase": search_phrase, "workspace_id": str(workspace_id)},
        )
        for row in slack_result.fetchall():
            key = ("slack_message", row[0])
            items[key] = LinkedItem(
                source_type="slack_message",
                source_id=row[0],
                title=f"Slack message by {row[2] or 'Unknown'} in #{row[3] or 'unknown'}",
                snippet=str(row[1])[:200],
                relevance_score=float(row[4]) * WEIGHT_KEYWORD,
                signals=["keyword_match"],
            )
    except Exception:
        logger.debug("Trigram search on slack_messages failed (pg_trgm may not be enabled)")

    # Trigram similarity on meeting_transcripts.title
    meeting_stmt = text("""
        SELECT id, title, transcript,
               similarity(COALESCE(title, ''), :phrase) AS sim
        FROM meeting_transcripts
        WHERE workspace_id = :workspace_id
          AND deleted_at IS NULL
          AND similarity(COALESCE(title, ''), :phrase) > 0.15
        ORDER BY sim DESC
        LIMIT 5
    """)

    try:
        meeting_result = await session.execute(
            meeting_stmt,
            {"phrase": search_phrase, "workspace_id": str(workspace_id)},
        )
        for row in meeting_result.fetchall():
            key = ("meeting_transcript", row[0])
            items[key] = LinkedItem(
                source_type="meeting_transcript",
                source_id=row[0],
                title=f"Meeting: {row[1] or 'Untitled'}",
                snippet=str(row[2])[:200],
                relevance_score=float(row[3]) * WEIGHT_KEYWORD,
                signals=["keyword_match"],
            )
    except Exception:
        logger.debug("Trigram search on meeting_transcripts failed")

    return items


async def _lookup_source_summary(
    session: AsyncSession,
    source_type: str,
    source_id: UUID,
) -> tuple[str, str]:
    """Look up a human-readable title and snippet for a source record."""
    model_map = {
        "linear_ticket": (LinearTicket, lambda r: (r.title, (r.description or "")[:200])),
        "linear_comment": (
            LinearComment,
            lambda r: (f"Comment by {r.author_name or 'Unknown'}", r.body[:200]),
        ),
        "slack_message": (
            SlackMessage,
            lambda r: (
                f"Slack by {r.user_name or 'Unknown'} in #{r.channel_name or 'unknown'}",
                r.text[:200],
            ),
        ),
        "meeting_transcript": (
            MeetingTranscript,
            lambda r: (f"Meeting: {r.title or 'Untitled'}", r.transcript[:200]),
        ),
        "github_pull_request": (
            GithubPullRequest,
            lambda r: (f"PR #{r.number}: {r.title}", (r.description or "")[:200]),
        ),
        "github_review": (
            GithubReview,
            lambda r: (
                f"Review by {r.author} ({r.state})",
                (r.body or "")[:200],
            ),
        ),
    }

    if source_type not in model_map:
        return (source_type, "")

    model_cls, extract = model_map[source_type]
    stmt = select(model_cls).where(model_cls.id == source_id)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        return (source_type, "")
    return extract(record)


async def find_related_content(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> LinkingResult:
    """Find all content related to a Linear ticket using multi-signal search.

    Combines explicit references, semantic similarity, and keyword/trigram
    matching with weighted scores to produce a ranked list of related items.

    Args:
        session: Async database session.
        workspace_id: Workspace to search within.
        ticket: The LinearTicket to find related content for.

    Returns:
        LinkingResult with ranked list of LinkedItem objects.
    """
    # Gather signals from all three sources
    explicit = await _find_explicit_refs(session, workspace_id, ticket)
    semantic = await _find_semantic_matches(session, workspace_id, ticket)
    keyword = await _find_keyword_matches(session, workspace_id, ticket)

    # Merge results: combine scores for items found by multiple signals
    merged: dict[tuple[str, UUID], LinkedItem] = {}

    for source, signal_items in [
        ("explicit", explicit),
        ("semantic", semantic),
        ("keyword", keyword),
    ]:
        for key, item in signal_items.items():
            if key in merged:
                existing = merged[key]
                existing.relevance_score = max(
                    existing.relevance_score + item.relevance_score, 0.0
                )
                existing.signals.extend(item.signals)
            else:
                merged[key] = item

    # Sort by relevance score descending
    sorted_items = sorted(merged.values(), key=lambda x: x.relevance_score, reverse=True)

    return LinkingResult(
        ticket_id=ticket.id,
        ticket_identifier=ticket.identifier,
        items=sorted_items,
    )
