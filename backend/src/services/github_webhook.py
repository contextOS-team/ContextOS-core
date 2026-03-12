"""GitHub webhook event processor.

Handles real-time PR and review updates from GitHub webhooks.
Routes events by type (pull_request, pull_request_review,
pull_request_review_comment) and processes them idempotently.

Per user decisions:
- Bot PRs (dependabot[bot], renovate[bot], github-actions[bot]) are filtered
- Unmonitored repos are skipped
- Review comments stored as GithubReview records with file_path and line_range
- Creates its own async session for background processing isolation
"""

import logging
from uuid import UUID

import httpx
import sqlalchemy.exc

from sqlalchemy import cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import async_session
from src.models.github import GithubPullRequest, GithubReview
from src.models.integration import OAuthToken, Provider
from src.services.github_common import (
    is_bot_author,
    map_pr_state,
    map_review_state,
    parse_github_timestamp,
)
from src.services.code_index_worker import enqueue_code_index_job
from src.services.embedding import queue_embedding_generation
from src.services.github_linking import link_pr_to_ticket
from src.services.github_repos import is_repo_monitored
from src.services.graph_extractor import extract_and_populate_graph

logger = logging.getLogger(__name__)


async def _lookup_workspace_from_installation(
    installation_id: int, session: AsyncSession
) -> UUID | None:
    """Look up workspace_id from a GitHub App installation_id.

    Uses a JSONB query to find the OAuthToken with matching installation_id
    in the metadata column, avoiding an O(N) Python-side scan.

    Args:
        installation_id: GitHub App installation ID from webhook payload.
        session: Async database session.

    Returns:
        The workspace UUID, or None if not found.
    """
    stmt = select(OAuthToken.workspace_id).where(
        OAuthToken.provider == Provider.GITHUB,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
        OAuthToken.metadata_["installation_id"].as_string() == str(installation_id),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def process_github_event(
    event_type: str, payload: dict, workspace_id: UUID | None = None
) -> None:
    """Main webhook event dispatcher.

    Creates a fresh DB session and routes the event to the appropriate handler
    based on event type.

    Args:
        event_type: The X-GitHub-Event header value.
        payload: The full webhook payload from GitHub.
        workspace_id: Optional pre-resolved workspace ID. If None, resolves
                      from installation.id in the payload.
    """
    logger.info("Processing GitHub webhook: event=%s", event_type)

    async with async_session() as session:
        try:
            # Resolve workspace from installation_id if not provided
            if workspace_id is None:
                installation = payload.get("installation", {})
                installation_id = installation.get("id") if isinstance(installation, dict) else None
                if installation_id is None:
                    logger.warning("GitHub webhook missing installation.id, skipping")
                    return

                workspace_id = await _lookup_workspace_from_installation(
                    installation_id, session
                )
                if workspace_id is None:
                    logger.warning(
                        "No workspace found for GitHub installation %s",
                        installation_id,
                    )
                    return

            action = payload.get("action", "")

            if event_type == "pull_request":
                await handle_pull_request_event(action, payload, workspace_id, session)
            elif event_type == "pull_request_review":
                await handle_review_event(action, payload, workspace_id, session)
            elif event_type == "pull_request_review_comment":
                await handle_review_comment_event(action, payload, workspace_id, session)
            elif event_type == "push":
                await handle_push_event(payload, workspace_id, session)
            else:
                logger.info("Ignoring unhandled GitHub event type: %s", event_type)

            await session.commit()
        except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError):
            logger.exception(
                "Error processing GitHub webhook event=%s workspace=%s",
                event_type,
                workspace_id,
            )
            await session.rollback()
            raise


async def handle_pull_request_event(
    action: str,
    payload: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a pull_request webhook event.

    Actions: opened, closed, reopened, edited, converted_to_draft, ready_for_review.
    """
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    repo_full_name = repo_data.get("full_name", "")

    # 1. Check if repo is monitored
    if not await is_repo_monitored(workspace_id, repo_full_name, session):
        logger.debug("Repo %s not monitored, skipping PR event", repo_full_name)
        return

    # 2. Filter bot authors
    author_login = pr_data.get("user", {}).get("login", "")
    if is_bot_author(author_login):
        logger.debug("Skipping bot PR author: %s", author_login)
        return

    # 3. Extract PR data
    github_id = pr_data.get("id")
    if not github_id:
        logger.warning("PR event missing pull_request.id")
        return

    # 4. Map state using unified mapper
    state = map_pr_state(
        action if action in ("closed", "reopened") else pr_data.get("state", "open"),
        pr_data.get("merged_at"),
        merged=pr_data.get("merged", False),
    )

    # Parse timestamps
    github_created_at = parse_github_timestamp(pr_data.get("created_at"))
    github_updated_at = parse_github_timestamp(pr_data.get("updated_at"))
    github_merged_at = parse_github_timestamp(pr_data.get("merged_at"))

    # Extract reviewers
    requested_reviewers = pr_data.get("requested_reviewers", [])
    reviewers = [r.get("login", "") for r in requested_reviewers if isinstance(r, dict)]

    # Upsert GithubPullRequest (on conflict: workspace_id + github_id)
    stmt = select(GithubPullRequest).where(
        GithubPullRequest.workspace_id == workspace_id,
        GithubPullRequest.github_id == github_id,
    )
    result = await session.execute(stmt)
    existing_pr = result.scalar_one_or_none()

    head = pr_data.get("head", {})
    base = pr_data.get("base", {})

    if existing_pr:
        existing_pr.title = pr_data.get("title", existing_pr.title)
        existing_pr.description = pr_data.get("body")
        existing_pr.state = state
        existing_pr.is_draft = pr_data.get("draft", False)
        existing_pr.reviewers = reviewers if reviewers else existing_pr.reviewers
        existing_pr.github_updated_at = github_updated_at
        existing_pr.github_merged_at = github_merged_at
        existing_pr.raw_data = pr_data
        existing_pr.deleted_at = None  # Restore if previously soft-deleted
        pr_record = existing_pr
    else:
        pr_record = GithubPullRequest(
            workspace_id=workspace_id,
            github_id=github_id,
            repo_full_name=repo_full_name,
            number=pr_data.get("number", 0),
            title=pr_data.get("title", ""),
            description=pr_data.get("body"),
            state=state,
            author=author_login,
            branch_name=head.get("ref", ""),
            base_branch=base.get("ref", ""),
            reviewers=reviewers if reviewers else None,
            is_draft=pr_data.get("draft", False),
            github_created_at=github_created_at,
            github_updated_at=github_updated_at,
            github_merged_at=github_merged_at,
            raw_data=pr_data,
        )
        session.add(pr_record)

    await session.flush()

    # 5. Link PR to Linear ticket
    await link_pr_to_ticket(pr_record, workspace_id, session)

    # 6. Queue embedding generation for the PR
    await queue_embedding_generation(
        session, workspace_id, "github_pull_request", [pr_record.id]
    )

    # 7. Graph extraction for the PR
    try:
        await extract_and_populate_graph(
            session=session,
            workspace_id=workspace_id,
            content=f"{pr_record.title}\n\n{pr_record.description or ''}",
            source_type="github_pull_request",
            source_id=pr_record.id,
            source_name=f"PR #{pr_record.number}: {pr_record.title}",
            source_external_id=f"{repo_full_name}#{pr_record.number}",
        )
    except Exception:
        logger.warning(
            "Graph extraction failed for PR #%d", pr_record.number, exc_info=True
        )

    logger.info(
        "Upserted PR #%d (%s) state=%s for workspace %s",
        pr_data.get("number", 0),
        repo_full_name,
        state,
        workspace_id,
    )


async def handle_review_event(
    action: str,
    payload: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a pull_request_review webhook event.

    Action: submitted.
    """
    if action != "submitted":
        logger.debug("Ignoring review action: %s", action)
        return

    repo_data = payload.get("repository", {})
    repo_full_name = repo_data.get("full_name", "")

    if not await is_repo_monitored(workspace_id, repo_full_name, session):
        logger.debug("Repo %s not monitored, skipping review event", repo_full_name)
        return

    review_data = payload.get("review", {})
    pr_data = payload.get("pull_request", {})

    github_id = review_data.get("id")
    if not github_id:
        logger.warning("Review event missing review.id")
        return

    # Look up parent PR
    pr_github_id = pr_data.get("id")
    pr_record = None
    if pr_github_id:
        pr_stmt = select(GithubPullRequest).where(
            GithubPullRequest.workspace_id == workspace_id,
            GithubPullRequest.github_id == pr_github_id,
        )
        pr_result = await session.execute(pr_stmt)
        pr_record = pr_result.scalar_one_or_none()

    if not pr_record:
        logger.warning(
            "Parent PR not found for review %s (pr_github_id=%s)",
            github_id,
            pr_github_id,
        )
        return

    # Upsert GithubReview
    stmt = select(GithubReview).where(
        GithubReview.workspace_id == workspace_id,
        GithubReview.github_id == github_id,
    )
    result = await session.execute(stmt)
    existing_review = result.scalar_one_or_none()

    review_state = map_review_state(review_data.get("state", "COMMENTED"))
    review_body = review_data.get("body")
    review_author = review_data.get("user", {}).get("login", "")
    submitted_at = parse_github_timestamp(review_data.get("submitted_at"))

    review_record: GithubReview
    if existing_review:
        existing_review.state = review_state
        existing_review.body = review_body
        existing_review.author = review_author
        existing_review.github_submitted_at = submitted_at
        existing_review.raw_data = review_data
        review_record = existing_review
    else:
        review_record = GithubReview(
            workspace_id=workspace_id,
            pull_request_id=pr_record.id,
            github_id=github_id,
            author=review_author,
            state=review_state,
            body=review_body,
            github_submitted_at=submitted_at,
            raw_data=review_data,
        )
        session.add(review_record)

    await session.flush()

    # Queue embedding generation for the review
    if review_record.body:
        await queue_embedding_generation(
            session, workspace_id, "github_review", [review_record.id]
        )

    # Graph extraction for the review
    if review_record.body:
        try:
            await extract_and_populate_graph(
                session=session,
                workspace_id=workspace_id,
                content=review_record.body,
                source_type="github_review",
                source_id=review_record.id,
                source_name=f"Review on PR #{pr_record.number}",
                source_external_id=f"review:{github_id}",
            )
        except Exception:
            logger.warning(
                "Graph extraction failed for review %s", github_id, exc_info=True
            )

    logger.info(
        "Upserted review %s (state=%s) for PR #%d",
        github_id,
        review_state,
        pr_record.number,
    )


async def handle_review_comment_event(
    action: str,
    payload: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a pull_request_review_comment webhook event.

    Action: created.
    """
    if action != "created":
        logger.debug("Ignoring review comment action: %s", action)
        return

    repo_data = payload.get("repository", {})
    repo_full_name = repo_data.get("full_name", "")

    if not await is_repo_monitored(workspace_id, repo_full_name, session):
        logger.debug("Repo %s not monitored, skipping review comment", repo_full_name)
        return

    comment_data = payload.get("comment", {})
    pr_data = payload.get("pull_request", {})

    github_id = comment_data.get("id")
    if not github_id:
        logger.warning("Review comment event missing comment.id")
        return

    # Look up parent PR
    pr_github_id = pr_data.get("id")
    pr_record = None
    if pr_github_id:
        pr_stmt = select(GithubPullRequest).where(
            GithubPullRequest.workspace_id == workspace_id,
            GithubPullRequest.github_id == pr_github_id,
        )
        pr_result = await session.execute(pr_stmt)
        pr_record = pr_result.scalar_one_or_none()

    if not pr_record:
        logger.warning(
            "Parent PR not found for review comment %s (pr_github_id=%s)",
            github_id,
            pr_github_id,
        )
        return

    # Extract file context
    file_path = comment_data.get("path")
    line = comment_data.get("line")
    original_line = comment_data.get("original_line")
    line_range = None
    if line is not None:
        line_range = str(line)
        if original_line is not None and original_line != line:
            line_range = f"{original_line}-{line}"

    comment_body = comment_data.get("body")
    comment_author = comment_data.get("user", {}).get("login", "")
    submitted_at = parse_github_timestamp(comment_data.get("created_at"))

    # Upsert GithubReview with file context
    stmt = select(GithubReview).where(
        GithubReview.workspace_id == workspace_id,
        GithubReview.github_id == github_id,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    review_comment_record: GithubReview
    if existing:
        existing.body = comment_body
        existing.file_path = file_path
        existing.line_range = line_range
        existing.author = comment_author
        existing.raw_data = comment_data
        review_comment_record = existing
    else:
        review_comment_record = GithubReview(
            workspace_id=workspace_id,
            pull_request_id=pr_record.id,
            github_id=github_id,
            author=comment_author,
            state="commented",
            body=comment_body,
            file_path=file_path,
            line_range=line_range,
            github_submitted_at=submitted_at,
            raw_data=comment_data,
        )
        session.add(review_comment_record)

    await session.flush()

    # Queue embedding generation for the review comment
    if review_comment_record.body:
        await queue_embedding_generation(
            session, workspace_id, "github_review", [review_comment_record.id]
        )

    # Graph extraction for the review comment
    if review_comment_record.body:
        try:
            await extract_and_populate_graph(
                session=session,
                workspace_id=workspace_id,
                content=review_comment_record.body,
                source_type="github_review",
                source_id=review_comment_record.id,
                source_name=f"Review comment on PR #{pr_record.number}",
                source_external_id=f"review-comment:{github_id}",
            )
        except Exception:
            logger.warning(
                "Graph extraction failed for review comment %s", github_id, exc_info=True
            )

    logger.info(
        "Upserted review comment %s on %s:%s for PR #%d",
        github_id,
        file_path,
        line_range,
        pr_record.number,
    )


async def handle_push_event(
    payload: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a push webhook event by enqueuing incremental code re-indexing.

    Checks if the pushed repo is monitored, and if so, enqueues a code
    index job for async processing by the code index worker.

    Args:
        payload: The full GitHub push event payload.
        workspace_id: Resolved workspace ID.
        session: Async database session.
    """
    repo_full_name = payload.get("repository", {}).get("full_name", "")
    if not repo_full_name:
        logger.warning("Push event missing repository.full_name")
        return

    if not await is_repo_monitored(workspace_id, repo_full_name, session):
        logger.debug("Repo %s not monitored, skipping push event", repo_full_name)
        return

    await enqueue_code_index_job(workspace_id, repo_full_name)
    logger.info(
        "Push event received for %s, enqueued code re-index",
        repo_full_name,
    )


async def process_push_event(payload: dict) -> None:
    """Standalone push event processor (creates its own session).

    Can be called directly from tests or webhook handlers that don't
    have an existing session context.

    Args:
        payload: The full GitHub push event payload.
    """
    installation = payload.get("installation", {})
    installation_id = installation.get("id") if isinstance(installation, dict) else None
    if installation_id is None:
        logger.warning("Push event missing installation.id, skipping")
        return

    async with async_session() as session:
        workspace_id = await _lookup_workspace_from_installation(
            installation_id, session
        )
        if workspace_id is None:
            logger.warning(
                "No workspace found for GitHub installation %s",
                installation_id,
            )
            return

        await handle_push_event(payload, workspace_id, session)
