"""Dashboard weekly summary aggregation service.

Aggregates activity counts, context page updates, and merged PRs/MRs
grouped by day for the last 7 days.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Date, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.context_page import ContextPage
from src.models.github import GithubPullRequest
from src.models.gitlab import GitlabMergeRequest

logger = logging.getLogger(__name__)


async def get_weekly_summary(
    session: AsyncSession, workspace_id: UUID
) -> list[dict]:
    """Aggregate daily counts for the last 7 days.

    Returns a list of dicts sorted by date DESC:
    [{date, activity_count, contexts_updated, prs_merged}]
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Initialize all 7 days with zero counts
    day_data: dict[date, dict] = {}
    for i in range(7):
        d = (now - timedelta(days=i)).date()
        day_data[d] = {
            "date": d.isoformat(),
            "activity_count": 0,
            "contexts_updated": 0,
            "prs_merged": 0,
        }

    # 1. Activity events count by day
    activity_result = await session.execute(
        text(
            """
            SELECT created_at::date AS day, COUNT(*) AS cnt
            FROM activity_events
            WHERE workspace_id = :wid AND created_at >= :since
            GROUP BY day
            """
        ),
        {"wid": str(workspace_id), "since": seven_days_ago},
    )
    for row in activity_result:
        d = row[0] if isinstance(row[0], date) else row[0].date()
        if d in day_data:
            day_data[d]["activity_count"] = row[1]

    # 2. Context pages updated by day
    ctx_stmt = (
        select(
            func.cast(ContextPage.updated_at, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(
            ContextPage.workspace_id == workspace_id,
            ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
            ContextPage.updated_at >= seven_days_ago,  # type: ignore[operator]
        )
        .group_by(text("1"))
    )
    ctx_result = await session.execute(ctx_stmt)
    for row in ctx_result:
        d = row[0] if isinstance(row[0], date) else row[0].date() if row[0] else None
        if d and d in day_data:
            day_data[d]["contexts_updated"] = row[1]

    # 3. GitHub PRs merged by day
    gh_stmt = (
        select(
            func.cast(GithubPullRequest.github_merged_at, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(
            GithubPullRequest.workspace_id == workspace_id,
            GithubPullRequest.github_merged_at.is_not(None),  # type: ignore[union-attr]
            GithubPullRequest.github_merged_at >= seven_days_ago,  # type: ignore[operator]
            GithubPullRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(text("1"))
    )
    gh_result = await session.execute(gh_stmt)
    for row in gh_result:
        d = row[0] if isinstance(row[0], date) else row[0].date() if row[0] else None
        if d and d in day_data:
            day_data[d]["prs_merged"] = row[1]

    # 4. GitLab MRs merged by day (add to prs_merged)
    gl_stmt = (
        select(
            func.cast(GitlabMergeRequest.gitlab_merged_at, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(
            GitlabMergeRequest.workspace_id == workspace_id,
            GitlabMergeRequest.gitlab_merged_at.is_not(None),  # type: ignore[union-attr]
            GitlabMergeRequest.gitlab_merged_at >= seven_days_ago,  # type: ignore[operator]
            GitlabMergeRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(text("1"))
    )
    gl_result = await session.execute(gl_stmt)
    for row in gl_result:
        d = row[0] if isinstance(row[0], date) else row[0].date() if row[0] else None
        if d and d in day_data:
            day_data[d]["prs_merged"] += row[1]

    # Sort by date descending
    return sorted(day_data.values(), key=lambda x: x["date"], reverse=True)
