"""Linking engine for finding content related to a Linear ticket.

Combines two signals with weighted scores to find and rank related content:
- Explicit references (weight 1.0): PRs linked via FK, Slack messages containing
  ticket identifier, comments via ticket_id FK
- Hybrid search (weight 0.8): Combined vector similarity + full-text search
  via hybrid_search() SQL function
"""

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.github import GithubPullRequest, GithubReview
from src.models.meeting import MeetingSegment, MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.ticket import LinearComment, LinearTicket
from src.services.embedding import generate_embedding

logger = logging.getLogger(__name__)

# Signal weights for combined scoring
WEIGHT_EXPLICIT = 1.0
WEIGHT_HYBRID = 0.8

# Semantic similarity threshold (used by hybrid_search match_threshold)
SEMANTIC_THRESHOLD = 0.5


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


async def _find_hybrid_matches(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find related content via hybrid vector + full-text search."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    query_text = f"{ticket.title}\n\n{ticket.description or ''}"
    try:
        query_embedding = await generate_embedding(query_text)
    except Exception:
        logger.warning("Failed to generate query embedding for %s", ticket.identifier)
        return items

    if not query_embedding or all(v == 0.0 for v in query_embedding):
        return items

    # Call hybrid_search() SQL function
    match_stmt = text("""
        SELECT id, source_type, source_id, similarity, keyword_rank, combined_score, metadata
        FROM hybrid_search(
            CAST(:query_embedding AS vector),
            :query_text,
            CAST(:workspace_id AS uuid),
            NULL,
            0.7,
            0.3,
            :threshold,
            20
        )
    """)

    result = await session.execute(
        match_stmt,
        {
            "query_embedding": str(query_embedding),
            "query_text": ticket.title,
            "workspace_id": str(workspace_id),
            "threshold": SEMANTIC_THRESHOLD,
        },
    )

    for row in result.fetchall():
        source_type = row[1]
        source_id = row[2]
        combined_score = row[5]

        # Skip self-matches (the ticket's own embedding)
        if source_type == "linear_ticket" and source_id == ticket.id:
            continue

        key = (source_type, source_id)
        score = combined_score * WEIGHT_HYBRID

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
            signals=["hybrid_search"],
        )

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
        "meeting_segment": (
            MeetingSegment,
            lambda r: (
                f"Segment by {r.speaker_name or 'Unknown'}",
                r.text[:200],
            ),
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
        "notion_page": (
            NotionPage,
            lambda r: (r.title, (r.content or "")[:200]),
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

    Combines explicit references and hybrid search (vector + full-text)
    with weighted scores to produce a ranked list of related items.

    Args:
        session: Async database session.
        workspace_id: Workspace to search within.
        ticket: The LinearTicket to find related content for.

    Returns:
        LinkingResult with ranked list of LinkedItem objects.
    """
    # Gather signals from both sources
    explicit = await _find_explicit_refs(session, workspace_id, ticket)
    hybrid = await _find_hybrid_matches(session, workspace_id, ticket)

    # Merge results: combine scores for items found by multiple signals
    merged: dict[tuple[str, UUID], LinkedItem] = {}

    for source, signal_items in [
        ("explicit", explicit),
        ("hybrid", hybrid),
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
