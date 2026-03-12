"""GitLab webhook event processor.

Handles real-time MR and note updates from GitLab webhooks.
Routes events by object_kind and processes them idempotently.

GitLab webhook verification uses X-Gitlab-Token header comparison
(not HMAC body signature like GitHub). This is simpler but requires
constant-time comparison to prevent timing attacks.

Per user decisions:
- Bot MRs filtered via is_bot_user
- Unmonitored projects skipped
- Notes stored as GitlabReview records
- WebhookDelivery used for idempotency
"""

import hmac
import logging
from uuid import UUID

import sqlalchemy.exc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import async_session
from src.models.gitlab import GitlabMergeRequest, GitlabReview
from src.models.integration import OAuthToken, Provider, WebhookDelivery
from src.services.gitlab_common import (
    is_bot_user,
    map_mr_state,
    parse_gitlab_timestamp,
)
from src.services.gitlab_linking import link_mr_to_ticket
from src.services.gitlab_repos import is_project_monitored

logger = logging.getLogger(__name__)


async def verify_webhook_token(request_token: str, settings) -> bool:
    """Verify the GitLab webhook secret token.

    Uses constant-time comparison to prevent timing attacks.
    GitLab sends the secret in the X-Gitlab-Token header.

    Args:
        request_token: Token from X-Gitlab-Token header.
        settings: Application settings with GITLAB_WEBHOOK_SECRET.

    Returns:
        True if the token matches.
    """
    expected = settings.GITLAB_WEBHOOK_SECRET
    if not expected:
        logger.warning("GITLAB_WEBHOOK_SECRET not configured")
        return False
    return hmac.compare_digest(request_token, expected)


async def _lookup_workspace_from_gitlab(
    project_id: int, session: AsyncSession
) -> UUID | None:
    """Look up workspace_id from a GitLab project_id.

    Searches workspace_integrations config JSONB for a workspace
    that has this project_id in their selected_projects list.

    Args:
        project_id: GitLab project ID from webhook payload.
        session: Async database session.

    Returns:
        The workspace UUID, or None if not found.
    """
    from sqlalchemy import text

    from src.models.integration import WorkspaceIntegration

    # Use PostgreSQL JSONB containment operator to filter at SQL level
    # instead of loading all rows and iterating in Python
    stmt = select(WorkspaceIntegration.workspace_id).where(
        WorkspaceIntegration.provider == Provider.GITLAB,
        WorkspaceIntegration.status == "connected",
        text("config->'selected_projects' @> :proj_json"),
    ).params(proj_json=f"[{project_id}]").limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def process_gitlab_event(
    payload: dict,
    session: AsyncSession,
    settings,
) -> None:
    """Main webhook event dispatcher.

    Routes the event to the appropriate handler based on object_kind.

    Args:
        payload: The full webhook payload from GitLab.
        session: Async database session.
        settings: Application settings.
    """
    object_kind = payload.get("object_kind", "")
    logger.info("Processing GitLab webhook: object_kind=%s", object_kind)

    # Extract project_id from payload
    project = payload.get("project", {})
    project_id = project.get("id")

    if not project_id:
        logger.warning("GitLab webhook missing project.id, skipping")
        return

    # Resolve workspace from project_id
    workspace_id = await _lookup_workspace_from_gitlab(project_id, session)
    if workspace_id is None:
        logger.warning(
            "No workspace found for GitLab project %s", project_id
        )
        return

    # Check idempotency
    obj_attrs = payload.get("object_attributes", {})
    delivery_id = f"gitlab_{object_kind}_{obj_attrs.get('id', '')}_{obj_attrs.get('updated_at', '')}"

    existing = await session.execute(
        select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
    )
    if existing.scalar_one_or_none():
        logger.debug("Duplicate webhook delivery %s, skipping", delivery_id)
        return

    try:
        if object_kind == "merge_request":
            await _handle_merge_request_event(payload, workspace_id, session)
        elif object_kind == "note":
            noteable_type = obj_attrs.get("noteable_type", "")
            if noteable_type == "MergeRequest":
                await _handle_note_event(payload, workspace_id, session)
            else:
                logger.debug("Ignoring note on %s", noteable_type)
        else:
            logger.info("Ignoring unhandled GitLab event: %s", object_kind)

        # Record delivery for idempotency
        delivery = WebhookDelivery(delivery_id=delivery_id, provider=Provider.GITLAB)
        session.add(delivery)

        await session.commit()

    except (sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError):
        logger.exception(
            "Error processing GitLab webhook object_kind=%s workspace=%s",
            object_kind,
            workspace_id,
        )
        await session.rollback()
        raise


async def _handle_merge_request_event(
    payload: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a merge_request webhook event.

    Processes MR state transitions: open, close, reopen, merge, update, approval.
    """
    obj_attrs = payload.get("object_attributes", {})
    project = payload.get("project", {})
    project_id = project.get("id")

    # Check if project is monitored
    if not await is_project_monitored(workspace_id, project_id, session):
        logger.debug("Project %s not monitored, skipping MR event", project_id)
        return

    # Filter bot authors — webhook payload has author in payload["user"], not obj_attrs
    author_data = payload.get("user", {})
    if is_bot_user(author_data):
        logger.debug("Skipping bot MR author")
        return

    gitlab_id = obj_attrs.get("id")
    if not gitlab_id:
        logger.warning("MR event missing object_attributes.id")
        return

    state = map_mr_state(obj_attrs.get("state", "opened"))
    project_path = project.get("path_with_namespace", "")

    # Extract reviewer usernames
    reviewers_data = payload.get("reviewers", [])
    reviewers = [r.get("username", "") for r in reviewers_data if isinstance(r, dict)] or None

    # Upsert GitlabMergeRequest
    stmt = select(GitlabMergeRequest).where(
        GitlabMergeRequest.workspace_id == workspace_id,
        GitlabMergeRequest.gitlab_id == gitlab_id,
    )
    result = await session.execute(stmt)
    existing_mr = result.scalar_one_or_none()

    if existing_mr:
        existing_mr.title = obj_attrs.get("title", existing_mr.title)
        existing_mr.description = obj_attrs.get("description")
        existing_mr.state = state
        existing_mr.is_draft = obj_attrs.get("draft", False) or obj_attrs.get("work_in_progress", False)
        existing_mr.reviewers = reviewers if reviewers else existing_mr.reviewers
        existing_mr.gitlab_updated_at = parse_gitlab_timestamp(obj_attrs.get("updated_at"))
        existing_mr.gitlab_merged_at = parse_gitlab_timestamp(obj_attrs.get("merged_at"))
        existing_mr.raw_data = payload
        existing_mr.deleted_at = None  # Restore if previously soft-deleted
        mr_record = existing_mr
    else:
        mr_record = GitlabMergeRequest(
            workspace_id=workspace_id,
            gitlab_id=gitlab_id,
            project_id=project_id,
            project_path=project_path,
            iid=obj_attrs.get("iid", 0),
            title=obj_attrs.get("title", ""),
            description=obj_attrs.get("description"),
            state=state,
            author=payload.get("user", {}).get("username", "unknown"),
            source_branch=obj_attrs.get("source_branch", ""),
            target_branch=obj_attrs.get("target_branch", ""),
            reviewers=reviewers,
            is_draft=obj_attrs.get("draft", False) or obj_attrs.get("work_in_progress", False),
            gitlab_created_at=parse_gitlab_timestamp(obj_attrs.get("created_at")),
            gitlab_updated_at=parse_gitlab_timestamp(obj_attrs.get("updated_at")),
            gitlab_merged_at=parse_gitlab_timestamp(obj_attrs.get("merged_at")),
            raw_data=payload,
        )
        session.add(mr_record)

    await session.flush()

    # Link MR to Linear ticket
    await link_mr_to_ticket(
        workspace_id, obj_attrs.get("source_branch", ""), mr_record.id, session
    )

    logger.info(
        "Upserted MR !%d (%s) state=%s for workspace %s",
        obj_attrs.get("iid", 0),
        project_path,
        state,
        workspace_id,
    )


async def _handle_note_event(
    payload: dict,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Handle a note webhook event on a MergeRequest.

    Finds the parent MR by iid + project_id and upserts the note
    into gitlab_reviews.
    """
    obj_attrs = payload.get("object_attributes", {})
    project = payload.get("project", {})
    project_id = project.get("id")
    mr_data = payload.get("merge_request", {})

    if not project_id:
        logger.warning("Note event missing project.id")
        return

    # Check if project is monitored
    if not await is_project_monitored(workspace_id, project_id, session):
        logger.debug("Project %s not monitored, skipping note event", project_id)
        return

    # Skip system notes
    if obj_attrs.get("system", False):
        logger.debug("Skipping system note")
        return

    gitlab_id = obj_attrs.get("id")
    if not gitlab_id:
        logger.warning("Note event missing object_attributes.id")
        return

    # Find parent MR by iid + project_id
    mr_iid = mr_data.get("iid")
    if not mr_iid:
        logger.warning("Note event missing merge_request.iid")
        return

    mr_stmt = select(GitlabMergeRequest).where(
        GitlabMergeRequest.workspace_id == workspace_id,
        GitlabMergeRequest.project_id == project_id,
        GitlabMergeRequest.iid == mr_iid,
    )
    mr_result = await session.execute(mr_stmt)
    mr_record = mr_result.scalar_one_or_none()

    if not mr_record:
        logger.warning(
            "Parent MR not found for note %s (project=%s, iid=%s)",
            gitlab_id, project_id, mr_iid,
        )
        return

    # Determine state
    body = obj_attrs.get("note", "")
    note_state = "note"
    if body and body.strip().lower() == "approved this merge request":
        note_state = "approved"

    # Extract file context from diff notes
    position = obj_attrs.get("position", {})
    file_path = position.get("new_path") or position.get("old_path")
    line_range = None
    new_line = position.get("new_line")
    old_line = position.get("old_line")
    if new_line is not None:
        line_range = str(new_line)
        if old_line is not None and old_line != new_line:
            line_range = f"{old_line}-{new_line}"

    # Upsert GitlabReview
    existing_stmt = select(GitlabReview).where(
        GitlabReview.workspace_id == workspace_id,
        GitlabReview.gitlab_id == gitlab_id,
    )
    existing_result = await session.execute(existing_stmt)
    existing_review = existing_result.scalar_one_or_none()

    # Webhook payload has author info in payload["user"], not obj_attrs
    note_author = payload.get("user", {})
    author_username = note_author.get("username", "unknown")
    submitted_at = parse_gitlab_timestamp(obj_attrs.get("created_at"))

    if existing_review:
        existing_review.body = body if body else None
        existing_review.state = note_state
        existing_review.author = author_username
        existing_review.file_path = file_path
        existing_review.line_range = line_range
        existing_review.raw_data = payload
    else:
        review = GitlabReview(
            workspace_id=workspace_id,
            merge_request_id=mr_record.id,
            gitlab_id=gitlab_id,
            author=author_username,
            state=note_state,
            body=body if body else None,
            file_path=file_path,
            line_range=line_range,
            gitlab_submitted_at=submitted_at,
            raw_data=payload,
        )
        session.add(review)

    await session.flush()

    logger.info(
        "Upserted note %s on MR !%d for workspace %s",
        gitlab_id, mr_iid, workspace_id,
    )
