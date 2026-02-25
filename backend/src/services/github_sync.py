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

import asyncio
import logging
import time
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.github import GithubPullRequest, GithubReview
from src.models.integration import WorkspaceIntegration
from src.services import embedding
from src.services.github_linking import link_pr_to_ticket
from src.services.github_oauth import GitHubOAuthError, get_installation_token

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"

# GitHub API version header
GITHUB_API_VERSION = "2022-11-28"

# Backfill window: 60 days per user decision
BACKFILL_DAYS = 60

# Bot accounts to filter per user decision
BOT_ACCOUNTS = frozenset({
    "dependabot[bot]",
    "renovate[bot]",
    "github-actions[bot]",
})

# Rate limit threshold: pause when remaining < this value
RATE_LIMIT_THRESHOLD = 100


def _github_headers(token: str) -> dict[str, str]:
    """Build standard GitHub API request headers."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def _parse_link_next(link_header: str | None) -> str | None:
    """Parse GitHub Link header to extract the 'next' page URL."""
    if not link_header:
        return None
    import re
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    return match.group(1) if match else None


async def _check_rate_limit(response: httpx.Response) -> None:
    """Check GitHub API rate limit headers and sleep if needed.

    Monitors X-RateLimit-Remaining and X-RateLimit-Reset headers.
    If remaining requests < RATE_LIMIT_THRESHOLD, sleeps until the
    reset timestamp.

    Args:
        response: The httpx response to check headers on.
    """
    remaining = response.headers.get("x-ratelimit-remaining")
    reset_at = response.headers.get("x-ratelimit-reset")

    if remaining is not None and int(remaining) < RATE_LIMIT_THRESHOLD:
        if reset_at:
            reset_timestamp = int(reset_at)
            wait_seconds = max(reset_timestamp - int(time.time()), 1)
            logger.warning(
                "GitHub rate limit low (%s remaining), sleeping %d seconds",
                remaining,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)


def _map_pr_state(state: str, merged_at: str | None) -> str:
    """Map GitHub PR state to our model's state enum.

    GitHub uses 'open' and 'closed', but we distinguish 'merged'.
    A closed PR with a merged_at timestamp is 'merged'.

    Args:
        state: GitHub PR state ('open' or 'closed').
        merged_at: ISO timestamp if the PR was merged, None otherwise.

    Returns:
        One of 'open', 'closed', or 'merged'.
    """
    if state == "closed" and merged_at:
        return "merged"
    return state


def _parse_datetime(iso_str: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string to naive UTC datetime.

    Args:
        iso_str: ISO 8601 datetime string (e.g., "2024-01-01T00:00:00Z").

    Returns:
        Naive UTC datetime, or None if input is None/empty.
    """
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)  # Naive UTC per project convention
    except (ValueError, AttributeError):
        return None


def _map_review_state(state: str) -> str:
    """Map GitHub review state to our model's state enum.

    GitHub review states: APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING

    Args:
        state: GitHub review state string.

    Returns:
        Lowercase state matching the DB check constraint.
    """
    state_map = {
        "APPROVED": "approved",
        "CHANGES_REQUESTED": "changes_requested",
        "COMMENTED": "commented",
        "DISMISSED": "dismissed",
    }
    return state_map.get(state, "commented")


async def sync_repos(
    workspace_id: UUID,
    selected_repos: list[str],
    session: AsyncSession,
    settings: Settings,
) -> dict:
    """Sync PRs for all selected repos sequentially.

    Processes repos sequentially per user decision (rate limit awareness).
    Tracks per-repo sync status in workspace_integrations.config JSONB.

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

    for repo in selected_repos:
        try:
            await _update_repo_sync_status(
                session, workspace_id, repo, "syncing", 0, 0
            )

            pr_count, review_count = await sync_single_repo(
                workspace_id, repo, session, settings
            )

            await _update_repo_sync_status(
                session, workspace_id, repo, "synced", pr_count, pr_count
            )

            total_prs += pr_count
            total_reviews += review_count
            results[repo] = {"status": "synced", "prs": pr_count, "reviews": review_count}

        except Exception as e:
            logger.error("Sync failed for repo %s: %s", repo, e)
            await _update_repo_sync_status(
                session, workspace_id, repo, "error", 0, 0
            )
            results[repo] = {"status": "error", "error": str(e)}

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
    cutoff = datetime.utcnow() - timedelta(days=BACKFILL_DAYS)

    pr_count = 0
    review_count = 0

    url: str | None = (
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        f"?state=all&sort=updated&direction=desc&per_page=100"
    )

    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, headers=_github_headers(token))

            if response.status_code != 200:
                raise GitHubOAuthError(
                    f"GitHub API error fetching PRs for {repo_full_name}: "
                    f"{response.status_code} {response.text}"
                )

            await _check_rate_limit(response)

            prs = response.json()
            reached_cutoff = False

            for pr_data in prs:
                # Check if PR is older than backfill window
                updated_at = _parse_datetime(pr_data.get("updated_at"))
                if updated_at and updated_at < cutoff:
                    reached_cutoff = True
                    break

                # Filter bot accounts
                author = pr_data.get("user", {}).get("login", "")
                if author in BOT_ACCOUNTS:
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
            url = _parse_link_next(response.headers.get("link"))

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

    Args:
        session: Async database session.
        workspace_id: Workspace to associate the PR with.
        repo_full_name: Full repo name.
        pr_data: Raw PR data from GitHub API.

    Returns:
        The upserted GithubPullRequest record.
    """
    github_id = pr_data["id"]
    merged_at = pr_data.get("merged_at")
    state = _map_pr_state(pr_data.get("state", "open"), merged_at)

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
        "github_created_at": _parse_datetime(pr_data.get("created_at")),
        "github_updated_at": _parse_datetime(pr_data.get("updated_at")),
        "github_merged_at": _parse_datetime(merged_at),
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
    """Fetch reviews for a specific PR.

    Args:
        client: Reusable httpx client.
        token: GitHub installation access token.
        owner: Repo owner.
        repo: Repo name.
        pr_number: PR number.

    Returns:
        List of review dicts from GitHub API.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    response = await client.get(url, headers=_github_headers(token))

    if response.status_code != 200:
        logger.warning(
            "Failed to fetch reviews for %s/%s#%d: %d",
            owner, repo, pr_number, response.status_code,
        )
        return []

    await _check_rate_limit(response)
    return response.json()


async def _upsert_review(
    session: AsyncSession,
    workspace_id: UUID,
    pull_request_id: UUID,
    review_data: dict,
) -> None:
    """Upsert a GitHub review record.

    Uses ON CONFLICT (workspace_id, github_id) DO UPDATE for idempotent upserts.

    Args:
        session: Async database session.
        workspace_id: Workspace to associate the review with.
        pull_request_id: UUID of the parent PR record.
        review_data: Raw review data from GitHub API.
    """
    github_id = review_data["id"]
    state = _map_review_state(review_data.get("state", "COMMENTED"))

    values = {
        "workspace_id": workspace_id,
        "pull_request_id": pull_request_id,
        "github_id": github_id,
        "author": review_data.get("user", {}).get("login", "unknown"),
        "state": state,
        "body": review_data.get("body"),
        "github_submitted_at": _parse_datetime(review_data.get("submitted_at")),
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
    """Update per-repo sync status in workspace_integrations.config JSONB.

    Stores sync progress under config.repo_sync_status.{repo_full_name}.

    Args:
        session: Async database session.
        workspace_id: Workspace to update.
        repo_full_name: Full repo name.
        status: Sync status (syncing, synced, error).
        synced: Number of PRs synced so far.
        total: Total PRs expected (0 if unknown).
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
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
