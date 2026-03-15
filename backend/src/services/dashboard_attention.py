"""Dashboard attention items aggregation service.

Combines stale/empty context pages with open PRs/MRs awaiting review
into a unified attention list for the dashboard homepage widget.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.context_page import ContextPage
from src.models.github import GithubPullRequest
from src.models.gitlab import GitlabMergeRequest

logger = logging.getLogger(__name__)


def _relative_age(dt: datetime | None) -> str | None:
    """Return a human-readable relative age string from a datetime."""
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    # Ensure dt is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        return f"{hours}h ago" if hours > 0 else "just now"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


async def get_attention_items(
    session: AsyncSession, workspace_id: UUID
) -> list[dict]:
    """Aggregate attention items: stale contexts + open PRs/MRs.

    Returns a combined list of items needing attention, each with a
    'type' field indicating the kind of attention item.
    """
    items: list[dict] = []

    # 1. Stale or empty-sources context pages
    stmt = (
        select(ContextPage)
        .where(
            ContextPage.workspace_id == workspace_id,
            ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
            or_(
                ContextPage.status == "stale",
                ContextPage.sources == [],
            ),
        )
        .order_by(ContextPage.updated_at.desc())  # type: ignore[union-attr]
        .limit(10)
    )
    result = await session.execute(stmt)
    for cp in result.scalars().all():
        item_type = "stale_context" if cp.status == "stale" else "no_sources"
        items.append(
            {
                "type": item_type,
                "id": str(cp.id),
                "title": cp.title,
                "ticket_identifier": cp.ticket_identifier,
                "status": cp.status,
            }
        )

    # 2. Open GitHub PRs (non-draft, awaiting review)
    gh_stmt = (
        select(GithubPullRequest)
        .where(
            GithubPullRequest.workspace_id == workspace_id,
            GithubPullRequest.state == "open",
            GithubPullRequest.is_draft.is_(False),  # type: ignore[union-attr]
            GithubPullRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(GithubPullRequest.github_created_at.asc())  # type: ignore[union-attr]
        .limit(5)
    )
    result = await session.execute(gh_stmt)
    for pr in result.scalars().all():
        items.append(
            {
                "type": "pr_review",
                "id": str(pr.id),
                "title": pr.title,
                "repo_full_name": pr.repo_full_name,
                "number": pr.number,
                "author": pr.author,
                "age": _relative_age(pr.github_created_at),
            }
        )

    # 3. Open GitLab MRs (non-draft, awaiting review)
    gl_stmt = (
        select(GitlabMergeRequest)
        .where(
            GitlabMergeRequest.workspace_id == workspace_id,
            GitlabMergeRequest.state == "opened",
            GitlabMergeRequest.is_draft.is_(False),  # type: ignore[union-attr]
            GitlabMergeRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(GitlabMergeRequest.gitlab_created_at.asc())  # type: ignore[union-attr]
        .limit(5)
    )
    result = await session.execute(gl_stmt)
    for mr in result.scalars().all():
        items.append(
            {
                "type": "mr_review",
                "id": str(mr.id),
                "title": mr.title,
                "project_path": mr.project_path,
                "iid": mr.iid,
                "author": mr.author,
                "age": _relative_age(mr.gitlab_created_at),
            }
        )

    return items
