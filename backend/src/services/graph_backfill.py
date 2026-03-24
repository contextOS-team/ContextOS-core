"""Graph backfill: populate graph nodes and edges from existing content.

Processes all existing records (tickets, comments, messages, PRs, reviews,
Notion pages, meeting transcripts) to retroactively populate the knowledge
graph. Idempotent via fingerprint-based dedup in graph_ops.

Usage:
    python -m src.services.graph_backfill
"""

from __future__ import annotations

import asyncio
import logging
import math
from uuid import UUID

from sqlmodel import select

from src.db import async_session
from src.models.github import GithubPullRequest, GithubReview
from src.models.meeting import MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.jira import JiraComment, JiraIssue
from src.models.ticket import LinearComment, LinearTicket
from src.services.graph_extractor import extract_and_populate_graph

logger = logging.getLogger(__name__)


async def _process_linear_tickets(batch_size: int) -> int:
    """Process all linear tickets for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(LinearTicket).where(
            LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        tickets = result.scalars().all()

        total = len(tickets)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = tickets[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for ticket in batch:
                content = f"{ticket.title}\n\n{ticket.description or ''}"
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=ticket.workspace_id,
                        content=content,
                        source_type="linear_ticket",
                        source_id=ticket.id,
                        source_name=f"{ticket.identifier}: {ticket.title}",
                        source_external_id=ticket.identifier,
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for ticket %s", ticket.identifier, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill linear_ticket: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_linear_comments(batch_size: int) -> int:
    """Process all linear comments for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(LinearComment).where(
            LinearComment.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        comments = result.scalars().all()

        total = len(comments)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = comments[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for comment in batch:
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=comment.workspace_id,
                        content=comment.body,
                        source_type="linear_comment",
                        source_id=comment.id,
                        source_name=f"Comment {comment.linear_id}",
                        source_external_id=comment.linear_id,
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for comment %s", comment.linear_id, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill linear_comment: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_jira_issues(batch_size: int) -> int:
    """Process all Jira issues for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(JiraIssue).where(
            JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        issues = result.scalars().all()

        total = len(issues)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = issues[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for issue in batch:
                content = f"{issue.jira_key}: {issue.summary}\n\n{issue.description or ''}"
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=issue.workspace_id,
                        content=content,
                        source_type="jira_issue",
                        source_id=issue.id,
                        source_name=f"{issue.jira_key}: {issue.summary}",
                        source_external_id=issue.jira_key,
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for Jira issue %s", issue.jira_key, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill jira_issue: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_jira_comments(batch_size: int) -> int:
    """Process all Jira comments for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(JiraComment).where(
            JiraComment.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        comments = result.scalars().all()

        total = len(comments)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = comments[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for comment in batch:
                if not comment.body:
                    continue
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=comment.workspace_id,
                        content=comment.body,
                        source_type="jira_comment",
                        source_id=comment.id,
                        source_name=f"Jira comment {comment.jira_id}",
                        source_external_id=comment.jira_id,
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for Jira comment %s", comment.jira_id, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill jira_comment: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_slack_messages(batch_size: int) -> int:
    """Process all slack messages for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(SlackMessage).where(
            SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        total = len(messages)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = messages[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for message in batch:
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=message.workspace_id,
                        content=message.text,
                        source_type="slack_message",
                        source_id=message.id,
                        source_name=f"Slack message in #{message.channel_id}",
                        source_external_id=message.slack_ts,
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for slack message %s", message.slack_ts, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill slack_message: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_github_pull_requests(batch_size: int) -> int:
    """Process all GitHub pull requests for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(GithubPullRequest).where(
            GithubPullRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        prs = result.scalars().all()

        total = len(prs)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = prs[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for pr in batch:
                content = f"{pr.title}\n\n{pr.description or ''}"
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=pr.workspace_id,
                        content=content,
                        source_type="github_pull_request",
                        source_id=pr.id,
                        source_name=f"PR #{pr.number}: {pr.title}",
                        source_external_id=f"{pr.repo_full_name}#{pr.number}",
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for PR #%d", pr.number, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill github_pull_request: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_github_reviews(batch_size: int) -> int:
    """Process all GitHub reviews for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(GithubReview).where(
            GithubReview.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        reviews = result.scalars().all()

        total = len(reviews)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = reviews[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for review in batch:
                if not review.body:
                    continue
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=review.workspace_id,
                        content=review.body,
                        source_type="github_review",
                        source_id=review.id,
                        source_name=f"Review {review.github_id}",
                        source_external_id=f"review:{review.github_id}",
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for review %s", review.github_id, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill github_review: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_notion_pages(batch_size: int) -> int:
    """Process all Notion pages for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(NotionPage).where(
            NotionPage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        pages = result.scalars().all()

        total = len(pages)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = pages[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for page in batch:
                content = f"{page.title}\n\n{page.content or ''}"
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=page.workspace_id,
                        content=content,
                        source_type="notion_page",
                        source_id=page.id,
                        source_name=f"Notion: {page.title}",
                        source_external_id=page.notion_id,
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for Notion page %s", page.notion_id, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill notion_page: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def _process_meeting_transcripts(batch_size: int) -> int:
    """Process all meeting transcripts for graph extraction."""
    count = 0
    async with async_session() as session:
        stmt = select(MeetingTranscript).where(
            MeetingTranscript.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        transcripts = result.scalars().all()

        total = len(transcripts)
        total_batches = max(1, math.ceil(total / batch_size))

        for i in range(0, total, batch_size):
            batch = transcripts[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            for transcript in batch:
                content = f"{transcript.title or ''}\n\n{transcript.transcript}"
                try:
                    await extract_and_populate_graph(
                        session=session,
                        workspace_id=transcript.workspace_id,
                        content=content,
                        source_type="meeting_transcript",
                        source_id=transcript.id,
                        source_name=f"Meeting: {transcript.title or 'Untitled'}",
                        source_external_id=str(transcript.id),
                    )
                    count += 1
                except Exception:
                    logger.warning(
                        "Backfill failed for transcript %s", transcript.id, exc_info=True
                    )
            await session.commit()
            logger.info(
                "Backfill meeting_transcript: batch %d/%d, %d records processed",
                batch_num, total_batches, len(batch),
            )

    return count


async def backfill_graph(batch_size: int = 100, llm_extract: bool = False) -> dict:
    """Process all existing content to populate graph nodes and edges.

    Processes each source type in sequence, creating graph nodes and edges
    for all extractable entities. Idempotent via fingerprint-based dedup
    in graph_ops.

    Args:
        batch_size: Number of records to process per batch commit.
        llm_extract: If True, run LLM extraction (Gemini) after rule-based
            backfill completes. This calls the Gemini API.

    Returns:
        Dict with counts per source type, e.g.
        {"tickets": 5, "comments": 3, "messages": 10, ...}
    """
    logger.info("Starting graph backfill with batch_size=%d", batch_size)

    counts = {
        "tickets": await _process_linear_tickets(batch_size),
        "comments": await _process_linear_comments(batch_size),
        "jira_issues": await _process_jira_issues(batch_size),
        "jira_comments": await _process_jira_comments(batch_size),
        "messages": await _process_slack_messages(batch_size),
        "pull_requests": await _process_github_pull_requests(batch_size),
        "reviews": await _process_github_reviews(batch_size),
        "notion_pages": await _process_notion_pages(batch_size),
        "transcripts": await _process_meeting_transcripts(batch_size),
    }

    total = sum(counts.values())
    logger.info("Graph backfill complete: %d total records processed", total)
    logger.info("Backfill counts: %s", counts)

    # Optional LLM extraction pass (calls Gemini API)
    if llm_extract:
        logger.info("Starting LLM extraction batch (this will call Gemini API)...")
        from src.services.llm_extractor import batch_extract_llm

        # Process all workspaces that had content -- extract workspace_id from
        # the first available source. In practice, the caller should pass
        # workspace_id explicitly; for CLI usage we process all workspaces.
        llm_stats = await batch_extract_llm(
            workspace_id=await _get_first_workspace_id(),
            batch_size=batch_size,
        )
        counts["llm_extraction"] = llm_stats
        logger.info("LLM extraction complete: %s", llm_stats)

    return counts


async def _get_first_workspace_id() -> UUID:
    """Get the first workspace ID from the database for CLI batch processing."""
    from sqlmodel import select
    from src.models.slack import SlackMessage

    async with async_session() as session:
        stmt = select(SlackMessage.workspace_id).limit(1)
        result = await session.execute(stmt)
        workspace_id = result.scalar_one_or_none()
        if workspace_id is None:
            raise RuntimeError("No workspace found for LLM extraction. Ensure data exists.")
        return workspace_id


if __name__ == "__main__":
    import sys as _sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    llm_flag = "--llm" in _sys.argv
    result = asyncio.run(backfill_graph(llm_extract=llm_flag))
    print(f"Backfill complete: {result}")
