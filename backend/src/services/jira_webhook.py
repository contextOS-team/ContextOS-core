"""Jira webhook event processor.

Handles real-time issue and comment updates from Jira webhooks.
Routes events by type (jira:issue_created, jira:issue_updated, etc.),
upserts or soft-deletes records, and triggers selective re-embedding.

Webhook signature verification uses HMAC-SHA256 with X-Hub-Signature
header (sha256= prefix, same as GitHub pattern).
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import Provider, WorkspaceIntegration
from src.models.jira import JiraComment, JiraIssue
from src.services import embedding
from src.services.jira_sync import _parse_iso
from src.services.sync_adapter import emit_activity

logger = logging.getLogger(__name__)


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify Jira webhook HMAC-SHA256 signature.

    Jira webhooks use X-Hub-Signature header with "sha256=" prefix,
    following the same pattern as GitHub webhooks.

    Args:
        raw_body: Raw request body bytes.
        signature_header: Value of X-Hub-Signature header.
        secret: Webhook signing secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header[7:]  # Strip "sha256=" prefix

    computed = hmac.new(
        secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected_signature)


async def process_jira_webhook(
    session: AsyncSession,
    payload: dict,
    workspace_id: UUID,
) -> None:
    """Main webhook event dispatcher.

    Routes the event to the appropriate handler based on webhookEvent type.

    Args:
        session: Async database session.
        workspace_id: The workspace this event belongs to.
        payload: The full webhook payload from Jira.
    """
    event_type = payload.get("webhookEvent", "")

    logger.info(
        "Processing Jira webhook event: type=%s workspace=%s",
        event_type,
        workspace_id,
    )

    try:
        if event_type == "jira:issue_created":
            await _handle_issue_created(session, workspace_id, payload)
        elif event_type == "jira:issue_updated":
            await _handle_issue_updated(session, workspace_id, payload)
        elif event_type == "jira:issue_deleted":
            await _handle_issue_deleted(session, workspace_id, payload)
        elif event_type == "comment_created":
            await _handle_comment_created(session, workspace_id, payload)
        elif event_type == "comment_updated":
            await _handle_comment_updated(session, workspace_id, payload)
        elif event_type == "comment_deleted":
            await _handle_comment_deleted(session, workspace_id, payload)
        else:
            logger.info("Ignoring Jira webhook event type: %s", event_type)
    except Exception:
        logger.exception(
            "Error processing Jira webhook event type=%s workspace=%s",
            event_type,
            workspace_id,
        )
        raise


async def _handle_issue_created(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Handle jira:issue_created event.

    Upserts the issue from webhook payload data.
    """
    issue_data = payload.get("issue", {})
    if not issue_data:
        logger.warning("issue_created event missing issue field")
        return

    issue = await _upsert_issue_from_webhook(session, workspace_id, issue_data)
    if issue:
        await embedding.queue_embedding_generation(
            session, workspace_id, "jira_issue", [issue.id]
        )

        # Extract graph nodes
        await _extract_graph_for_issue(session, workspace_id, issue)

        # Emit ticket_created activity event
        await emit_activity(session, workspace_id, "ticket_created", metadata={
            "integration": "jira",
            "ticket_id": issue.jira_key,
            "title": issue.summary,
        })


async def _handle_issue_updated(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Handle jira:issue_updated event.

    Upserts the issue and re-embeds only if content (summary/description) changed.
    """
    issue_data = payload.get("issue", {})
    if not issue_data:
        logger.warning("issue_updated event missing issue field")
        return

    jira_id = str(issue_data.get("id", ""))

    # Snapshot existing issue for content comparison
    stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.jira_id == jira_id,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    old_summary = existing.summary if existing else None
    old_description = existing.description if existing else None

    issue = await _upsert_issue_from_webhook(session, workspace_id, issue_data)
    if not issue:
        return

    # Only re-embed on content changes (summary or description)
    if existing and issue.summary == old_summary and issue.description == old_description:
        logger.debug("Metadata-only change for Jira issue %s, skipping re-embed", jira_id)
        return

    await embedding.queue_embedding_generation(
        session, workspace_id, "jira_issue", [issue.id]
    )

    # Re-extract graph nodes on content change
    await _extract_graph_for_issue(session, workspace_id, issue)


async def _handle_issue_deleted(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Handle jira:issue_deleted event.

    Soft-deletes the issue by setting deleted_at.
    """
    issue_data = payload.get("issue", {})
    jira_id = str(issue_data.get("id", ""))
    if not jira_id:
        logger.warning("issue_deleted event missing issue id")
        return

    stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.jira_id == jira_id,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    issue = result.scalar_one_or_none()

    if issue:
        issue.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info("Soft-deleted Jira issue %s (jira_id=%s)", issue.id, jira_id)


async def _handle_comment_created(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Handle comment_created event."""
    await _upsert_comment_from_webhook(session, workspace_id, payload)


async def _handle_comment_updated(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Handle comment_updated event."""
    await _upsert_comment_from_webhook(session, workspace_id, payload)


async def _handle_comment_deleted(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Handle comment_deleted event.

    Soft-deletes the comment by setting deleted_at.
    """
    comment_data = payload.get("comment", {})
    jira_comment_id = str(comment_data.get("id", ""))
    if not jira_comment_id:
        logger.warning("comment_deleted event missing comment id")
        return

    stmt = select(JiraComment).where(
        JiraComment.workspace_id == workspace_id,
        JiraComment.jira_id == jira_comment_id,
        JiraComment.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment:
        comment.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info("Soft-deleted Jira comment %s (jira_id=%s)", comment.id, jira_comment_id)


async def _upsert_issue_from_webhook(
    session: AsyncSession,
    workspace_id: UUID,
    issue_data: dict,
) -> JiraIssue | None:
    """Upsert a Jira issue from webhook payload data.

    Args:
        session: Async database session.
        workspace_id: Workspace to associate the issue with.
        issue_data: Issue dict from webhook payload.

    Returns:
        The upserted JiraIssue, or None if data is invalid.
    """
    from src.services.jira_sync import _extract_text_from_adf

    jira_id = str(issue_data.get("id", ""))
    if not jira_id:
        logger.warning("Webhook issue data missing id field")
        return None

    fields = issue_data.get("fields", {})
    labels = [l["name"] if isinstance(l, dict) else l for l in fields.get("labels", [])]

    # Check if issue already exists
    stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.jira_id == jira_id,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    summary = fields.get("summary", "")
    description = _extract_text_from_adf(fields.get("description"))
    status_name = fields.get("status", {}).get("name") if fields.get("status") else None
    priority_name = fields.get("priority", {}).get("name") if fields.get("priority") else None
    issue_type = fields.get("issuetype", {}).get("name") if fields.get("issuetype") else None
    assignee_name = fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None
    reporter_name = fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None
    project_key = fields.get("project", {}).get("key") if fields.get("project") else None
    project_name = fields.get("project", {}).get("name") if fields.get("project") else None

    if existing:
        existing.jira_key = issue_data.get("key", existing.jira_key)
        existing.summary = summary
        existing.description = description
        existing.status = status_name
        existing.priority = priority_name
        existing.issue_type = issue_type
        existing.assignee_name = assignee_name
        existing.reporter_name = reporter_name
        existing.project_key = project_key
        existing.project_name = project_name
        existing.labels = labels if labels else None
        existing.jira_updated_at = _parse_iso(fields.get("updated"))
        existing.raw_data = issue_data
        existing.deleted_at = None  # Restore if previously deleted
        await session.flush()
        return existing
    else:
        new_issue = JiraIssue(
            workspace_id=workspace_id,
            jira_id=jira_id,
            jira_key=issue_data.get("key", ""),
            summary=summary,
            description=description,
            status=status_name,
            priority=priority_name,
            issue_type=issue_type,
            assignee_name=assignee_name,
            reporter_name=reporter_name,
            project_key=project_key,
            project_name=project_name,
            labels=labels if labels else None,
            jira_created_at=_parse_iso(fields.get("created")),
            jira_updated_at=_parse_iso(fields.get("updated")),
            raw_data=issue_data,
        )
        session.add(new_issue)
        await session.flush()
        return new_issue


async def _upsert_comment_from_webhook(
    session: AsyncSession,
    workspace_id: UUID,
    payload: dict,
) -> None:
    """Upsert a comment from Jira webhook payload.

    Finds the parent issue by the issue reference in the payload,
    then inserts or updates the comment record.
    """
    from src.services.jira_sync import _extract_text_from_adf

    comment_data = payload.get("comment", {})
    jira_comment_id = str(comment_data.get("id", ""))
    if not jira_comment_id:
        logger.warning("Comment event missing comment id")
        return

    # Find parent issue via issue data in payload
    issue_data = payload.get("issue", {})
    issue_jira_id = str(issue_data.get("id", ""))
    if not issue_jira_id:
        logger.warning("Comment %s missing issue reference", jira_comment_id)
        return

    issue_stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.jira_id == issue_jira_id,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    issue_result = await session.execute(issue_stmt)
    issue = issue_result.scalar_one_or_none()

    if not issue:
        logger.warning(
            "Parent issue not found for Jira comment %s (issue_id=%s)",
            jira_comment_id,
            issue_jira_id,
        )
        return

    # Check if comment already exists
    existing_stmt = select(JiraComment).where(
        JiraComment.workspace_id == workspace_id,
        JiraComment.jira_id == jira_comment_id,
    )
    existing_result = await session.execute(existing_stmt)
    existing_comment = existing_result.scalar_one_or_none()

    body = _extract_text_from_adf(comment_data.get("body"))
    author_name = None
    author_data = comment_data.get("author") or comment_data.get("updateAuthor")
    if isinstance(author_data, dict):
        author_name = author_data.get("displayName")

    if existing_comment:
        existing_comment.body = body
        existing_comment.author_name = author_name
        existing_comment.jira_updated_at = _parse_iso(comment_data.get("updated"))
        existing_comment.deleted_at = None  # Restore if previously deleted
        comment_id = existing_comment.id
    else:
        new_comment = JiraComment(
            workspace_id=workspace_id,
            issue_id=issue.id,
            jira_id=jira_comment_id,
            body=body,
            author_name=author_name,
            jira_created_at=_parse_iso(comment_data.get("created")),
            jira_updated_at=_parse_iso(comment_data.get("updated")),
        )
        session.add(new_comment)
        await session.flush()
        comment_id = new_comment.id

    # Queue embedding for the comment
    await embedding.queue_embedding_generation(
        session, workspace_id, "jira_comment", [comment_id]
    )


async def register_webhooks(
    cloud_id: str,
    access_token: str,
    callback_url: str,
    jql_filter: str = "",
) -> dict:
    """Register Jira webhooks for issue and comment events.

    Args:
        cloud_id: Atlassian cloud ID.
        access_token: Valid Jira access token.
        callback_url: URL to receive webhook events.
        jql_filter: Optional JQL filter for webhook scope.

    Returns:
        Webhook registration response data.
    """
    import httpx

    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/webhook"

    payload = {
        "url": callback_url,
        "webhooks": [
            {
                "jqlFilter": jql_filter or "project is not EMPTY",
                "events": [
                    "jira:issue_created",
                    "jira:issue_updated",
                    "jira:issue_deleted",
                    "comment_created",
                    "comment_updated",
                    "comment_deleted",
                ],
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )

    if response.status_code not in (200, 201):
        logger.error("Failed to register Jira webhooks: %s", response.text)
        return {"error": response.text}

    return response.json()


async def refresh_webhooks(
    cloud_id: str,
    access_token: str,
    webhook_ids: list[int],
) -> dict:
    """Refresh Jira webhook expiry.

    Jira webhooks expire after 30 days. This extends their lifetime.

    Args:
        cloud_id: Atlassian cloud ID.
        access_token: Valid Jira access token.
        webhook_ids: List of webhook IDs to refresh.

    Returns:
        Refresh response data.
    """
    import httpx

    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/webhook/refresh"

    async with httpx.AsyncClient() as client:
        response = await client.put(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"webhookIds": webhook_ids},
            timeout=15.0,
        )

    if response.status_code != 200:
        logger.error("Failed to refresh Jira webhooks: %s", response.text)
        return {"error": response.text}

    return response.json()


async def _extract_graph_for_issue(
    session: AsyncSession,
    workspace_id: UUID,
    issue: JiraIssue,
) -> None:
    """Extract graph nodes for a single Jira issue."""
    from src.services.graph_extractor import extract_and_populate_graph

    content = f"{issue.jira_key}: {issue.summary}\n\n{issue.description or ''}"
    try:
        await extract_and_populate_graph(
            session=session,
            workspace_id=workspace_id,
            content=content,
            source_type="jira_issue",
            source_id=issue.id,
            source_name=f"{issue.jira_key}: {issue.summary}",
            source_external_id=issue.jira_key,
        )
    except Exception:
        logger.warning("Graph extraction failed for Jira issue %s", issue.jira_key, exc_info=True)
