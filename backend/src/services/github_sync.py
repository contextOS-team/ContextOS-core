"""GitHub PR sync service with 60-day backfill.

Fetches pull requests and reviews from the GitHub API for selected repos,
upserts them into the database, and links PRs to Linear tickets via
branch name pattern parsing.

Per user decisions:
- Sequential sync with rate limit awareness
- 60-day backfill window for initial sync
- Bot accounts filtered (dependabot[bot], renovate[bot], github-actions[bot])
- Draft PRs included
- Unlinked PRs stored gracefully (null linear_ticket_id)
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import sqlalchemy.exc
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.github import GithubPullRequest, GithubReview
from src.models.integration import Provider, WorkspaceIntegration
from src.services import embedding
from src.services.github_common import (
    GITHUB_API_BASE,
    check_rate_limit,
    github_headers,
    is_bot_author,
    map_pr_state,
    map_review_state,
    parse_github_timestamp,
    parse_link_next,
)
from src.services.github_linking import link_pr_to_ticket
from src.services.github_oauth import GitHubOAuthError, get_installation_token
from src.services.sync_adapter import (
    SyncAdapter,
    SyncRunLogger,
    update_cursor_status,
)

logger = logging.getLogger(__name__)

# Backfill window: 60 days per user decision
BACKFILL_DAYS = 60


async def sync_repos(
    workspace_id: UUID,
    selected_repos: list[str],
    session: AsyncSession,
    settings: Settings,
) -> dict:
    """Sync PRs for all selected repos sequentially.

    Processes repos sequentially per user decision (rate limit awareness).
    Tracks per-repo sync status in workspace_integrations.config JSONB.
    Also writes to sync_cursors per repo for structured state tracking.

    Args:
        workspace_id: Workspace to sync PRs for.
        selected_repos: List of repo full_name strings to sync.
        session: Async database session.
        settings: Application settings.

    Returns:
        Summary dict with total counts and per-repo results.
    """
    total_prs = 0
    total_reviews = 0
    results = {}

    async with SyncRunLogger("github", workspace_id) as srl:
        for repo in selected_repos:
            try:
                # Update both JSONB and sync_cursors
                await _update_repo_sync_status(
                    session, workspace_id, repo, "syncing", 0, 0
                )
                await update_cursor_status(
                    session, workspace_id, "github", repo,
                    sync_status="syncing",
                )

                pr_count, review_count = await sync_single_repo(
                    workspace_id, repo, session, settings
                )

                # Update both JSONB and sync_cursors
                await _update_repo_sync_status(
                    session, workspace_id, repo, "synced", pr_count, pr_count
                )
                await update_cursor_status(
                    session, workspace_id, "github", repo,
                    sync_status="complete",
                    records_synced=pr_count,
                )

                total_prs += pr_count
                total_reviews += review_count
                results[repo] = {"status": "synced", "prs": pr_count, "reviews": review_count}

                srl.info("Synced repo %s: %d PRs" % (repo, pr_count))

            except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError) as e:
                srl.error("Sync failed for repo %s: %s" % (repo, e))
                await _update_repo_sync_status(
                    session, workspace_id, repo, "error", 0, 0
                )
                await update_cursor_status(
                    session, workspace_id, "github", repo,
                    sync_status="error",
                    error_message=str(e),
                )
                results[repo] = {"status": "error", "error": str(e)}

        srl.info("GitHub sync complete: %d PRs across %d repos" % (total_prs, len(selected_repos)))

    return {
        "total_prs": total_prs,
        "total_reviews": total_reviews,
        "repos": results,
    }


async def sync_single_repo(
    workspace_id: UUID,
    repo_full_name: str,
    session: AsyncSession,
    settings: Settings,
) -> tuple[int, int]:
    """Sync PRs and reviews for a single repo.

    Fetches all PRs updated within the 60-day backfill window,
    filters bot accounts, upserts PR and review records, and
    attempts Linear ticket linking for each PR.

    Args:
        workspace_id: Workspace to sync into.
        repo_full_name: Full name of the repo (e.g., "org/repo").
        session: Async database session.
        settings: Application settings.

    Returns:
        Tuple of (pr_count, review_count).
    """
    token = await get_installation_token(workspace_id, session, settings)

    owner, repo = repo_full_name.split("/", 1)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=BACKFILL_DAYS)

    pr_count = 0
    review_count = 0

    url: str | None = (
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        f"?state=all&sort=updated&direction=desc&per_page=100"
    )

    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, headers=github_headers(token))

            if response.status_code != 200:
                raise GitHubOAuthError(
                    f"GitHub API error fetching PRs for {repo_full_name}: "
                    f"{response.status_code} {response.text}"
                )

            await check_rate_limit(response)

            prs = response.json()
            reached_cutoff = False

            for pr_data in prs:
                # Check if PR is older than backfill window
                updated_at = parse_github_timestamp(pr_data.get("updated_at"))
                if updated_at and updated_at < cutoff:
                    reached_cutoff = True
                    break

                # Filter bot accounts
                author = pr_data.get("user", {}).get("login", "")
                if is_bot_author(author):
                    continue

                # Upsert the PR
                pr_record = await _upsert_pr(
                    session, workspace_id, repo_full_name, pr_data
                )
                pr_count += 1

                # Fetch and upsert reviews
                pr_number = pr_data["number"]
                reviews = await _fetch_reviews(
                    client, token, owner, repo, pr_number
                )
                for review_data in reviews:
                    await _upsert_review(
                        session, workspace_id, pr_record.id, review_data
                    )
                    review_count += 1

                # Attempt Linear ticket linking
                await link_pr_to_ticket(pr_record, workspace_id, session)

                # Update progress
                await _update_repo_sync_status(
                    session, workspace_id, repo_full_name,
                    "syncing", pr_count, 0
                )

            if reached_cutoff:
                break

            # Parse Link header for next page
            url = parse_link_next(response.headers.get("link"))

    await session.flush()

    # Queue embedding generation stub for PR descriptions
    if pr_count > 0:
        stmt = select(GithubPullRequest.id).where(
            GithubPullRequest.workspace_id == workspace_id,
            GithubPullRequest.repo_full_name == repo_full_name,
        )
        result = await session.execute(stmt)
        pr_ids = [row[0] for row in result.fetchall()]
        if pr_ids:
            await embedding.queue_embedding_generation(
                session, workspace_id, "github_pr", pr_ids
            )

    return pr_count, review_count


async def _upsert_pr(
    session: AsyncSession,
    workspace_id: UUID,
    repo_full_name: str,
    pr_data: dict,
) -> GithubPullRequest:
    """Upsert a GitHub pull request record.

    Uses ON CONFLICT (workspace_id, github_id) DO UPDATE for idempotent upserts.
    """
    github_id = pr_data["id"]
    merged_at = pr_data.get("merged_at")
    state = map_pr_state(pr_data.get("state", "open"), merged_at)

    # Extract reviewer logins from requested_reviewers
    reviewers = [
        r.get("login", "") for r in pr_data.get("requested_reviewers", [])
    ] or None

    head = pr_data.get("head", {})
    base = pr_data.get("base", {})

    values = {
        "workspace_id": workspace_id,
        "github_id": github_id,
        "repo_full_name": repo_full_name,
        "number": pr_data["number"],
        "title": pr_data.get("title", ""),
        "description": pr_data.get("body"),
        "state": state,
        "author": pr_data.get("user", {}).get("login", "unknown"),
        "branch_name": head.get("ref", ""),
        "base_branch": base.get("ref", ""),
        "reviewers": reviewers,
        "is_draft": pr_data.get("draft", False),
        "github_created_at": parse_github_timestamp(pr_data.get("created_at")),
        "github_updated_at": parse_github_timestamp(pr_data.get("updated_at")),
        "github_merged_at": parse_github_timestamp(merged_at),
        "raw_data": pr_data,
    }

    stmt = insert(GithubPullRequest).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "github_id"],
        set_={
            "repo_full_name": stmt.excluded.repo_full_name,
            "number": stmt.excluded.number,
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "state": stmt.excluded.state,
            "author": stmt.excluded.author,
            "branch_name": stmt.excluded.branch_name,
            "base_branch": stmt.excluded.base_branch,
            "reviewers": stmt.excluded.reviewers,
            "is_draft": stmt.excluded.is_draft,
            "github_created_at": stmt.excluded.github_created_at,
            "github_updated_at": stmt.excluded.github_updated_at,
            "github_merged_at": stmt.excluded.github_merged_at,
            "raw_data": stmt.excluded.raw_data,
        },
    ).returning(GithubPullRequest.__table__.c.id)

    result = await session.execute(stmt)
    pr_uuid = result.scalar_one()
    await session.flush()

    # Fetch the full record for linking
    pr_stmt = select(GithubPullRequest).where(GithubPullRequest.id == pr_uuid)
    pr_result = await session.execute(pr_stmt)
    return pr_result.scalar_one()


async def _fetch_reviews(
    client: httpx.AsyncClient,
    token: str,
    owner: str,
    repo: str,
    pr_number: int,
) -> list[dict]:
    """Fetch reviews for a specific PR."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    response = await client.get(url, headers=github_headers(token))

    if response.status_code != 200:
        logger.warning(
            "Failed to fetch reviews for %s/%s#%d: %d",
            owner, repo, pr_number, response.status_code,
        )
        return []

    await check_rate_limit(response)
    return response.json()


async def _upsert_review(
    session: AsyncSession,
    workspace_id: UUID,
    pull_request_id: UUID,
    review_data: dict,
) -> None:
    """Upsert a GitHub review record.

    Uses ON CONFLICT (workspace_id, github_id) DO UPDATE for idempotent upserts.
    """
    github_id = review_data["id"]
    state = map_review_state(review_data.get("state", "COMMENTED"))

    values = {
        "workspace_id": workspace_id,
        "pull_request_id": pull_request_id,
        "github_id": github_id,
        "author": review_data.get("user", {}).get("login", "unknown"),
        "state": state,
        "body": review_data.get("body"),
        "github_submitted_at": parse_github_timestamp(review_data.get("submitted_at")),
        "raw_data": review_data,
    }

    stmt = insert(GithubReview).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "github_id"],
        set_={
            "pull_request_id": stmt.excluded.pull_request_id,
            "author": stmt.excluded.author,
            "state": stmt.excluded.state,
            "body": stmt.excluded.body,
            "github_submitted_at": stmt.excluded.github_submitted_at,
            "raw_data": stmt.excluded.raw_data,
        },
    )

    await session.execute(stmt)
    await session.flush()


async def _update_repo_sync_status(
    session: AsyncSession,
    workspace_id: UUID,
    repo_full_name: str,
    status: str,
    synced: int,
    total: int,
) -> None:
    """Update per-repo sync status in workspace_integrations.config JSONB."""
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITHUB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        repo_sync = config.get("repo_sync_status", {})
        repo_sync[repo_full_name] = {
            "status": status,
            "synced": synced,
            "total": total,
        }
        config["repo_sync_status"] = repo_sync
        integration.config = config
        await session.flush()


class GitHubSyncService:
    """GitHub sync service conforming to the SyncAdapter protocol."""

    provider: str = "github"

    async def full_sync(
        self, session: AsyncSession, workspace_id: UUID, **kwargs
    ) -> dict:
        """Run a full GitHub sync. Delegates to sync_repos."""
        selected_repos = kwargs.get("selected_repos", [])
        settings = kwargs.get("settings")
        if settings is None:
            raise ValueError("settings is required for GitHub full_sync")
        return await sync_repos(workspace_id, selected_repos, session, settings)

    async def handle_webhook(
        self, session: AsyncSession, workspace_id: UUID, payload: dict
    ) -> None:
        """Process a GitHub webhook event (stub for future implementation)."""
        return None

    async def reconcile(
        self, session: AsyncSession, workspace_id: UUID
    ) -> dict:
        """Reconcile local state with GitHub API (stub for Plan 10-03)."""
        return {"status": "not_implemented"}


assert isinstance(GitHubSyncService(), SyncAdapter)
