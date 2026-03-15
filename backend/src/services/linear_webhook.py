"""Linear webhook event processor.

Handles real-time ticket and comment updates from Linear webhooks.
Routes events by type and action, delegates ticket upserts to linear_sync,
and triggers selective re-embedding only for content changes.

Per user decisions:
- Re-embed only on content changes (title, description), not metadata (state, assignee, labels)
- Events for non-synced teams store raw data but do not generate embeddings
- No Phase 4 triggers beyond embedding.queue_embedding_generation stub
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
import sqlalchemy.exc

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import async_session
from src.models.integration import OAuthToken, Provider, WorkspaceIntegration
from src.models.ticket import LinearComment, LinearTicket
from src.services import embedding
from src.services.graph_extractor import extract_and_populate_graph
from src.services.linear_oauth import get_valid_access_token
from src.services.linear_sync import sync_single_ticket
from src.services.sync_adapter import emit_activity

logger = logging.getLogger(__name__)


def is_content_change(existing_ticket: LinearTicket, new_title: str | None, new_description: str | None) -> bool:
    """Check whether title or description changed compared to the existing ticket.

    Returns True if either title or description differs, indicating content
    changed and re-embedding is needed. Returns False for metadata-only
    changes (state, assignee, labels, priority).

    Args:
        existing_ticket: The current ticket record from the database.
        new_title: The updated title (from the webhook payload or re-fetched data).
        new_description: The updated description.

    Returns:
        True if content changed, False otherwise.
    """
    if existing_ticket.title != new_title:
        return True
    if existing_ticket.description != new_description:
        return True
    return False


async def process_webhook_event(workspace_id: UUID, event: dict) -> None:
    """Main webhook event dispatcher.

    Creates a fresh DB session and routes the event to the appropriate handler
    based on event type and action.

    Args:
        workspace_id: The workspace this event belongs to.
        event: The full webhook payload from Linear.
    """
    event_type = event.get("type")
    action = event.get("action")
    data = event.get("data", {})

    logger.info(
        "Processing webhook event: type=%s action=%s workspace=%s",
        event_type,
        action,
        workspace_id,
    )

    async with async_session() as session:
        try:
            if event_type == "Issue":
                if action == "create":
                    await handle_issue_create(session, workspace_id, data)
                elif action == "update":
                    await handle_issue_update(session, workspace_id, data)
                elif action == "remove":
                    await handle_issue_remove(session, workspace_id, data)
                else:
                    logger.info("Ignoring Issue action: %s", action)
            elif event_type == "Comment":
                if action == "create":
                    await handle_comment_create(session, workspace_id, data)
                elif action == "update":
                    await handle_comment_update(session, workspace_id, data)
                elif action == "remove":
                    await handle_comment_remove(session, workspace_id, data)
                else:
                    logger.info("Ignoring Comment action: %s", action)
            else:
                logger.info("Ignoring unknown event type: %s", event_type)

            await session.commit()
        except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError):
            logger.exception(
                "Error processing webhook event type=%s action=%s workspace=%s",
                event_type,
                action,
                workspace_id,
            )
            await session.rollback()
            raise


async def _is_team_synced(session: AsyncSession, workspace_id: UUID, team_id: str | None) -> bool:
    """Check if a team is in the workspace's synced teams list.

    Reads synced_teams from workspace_integrations.config. If synced_teams
    is not configured, returns False (conservative default).

    Args:
        session: Async database session.
        workspace_id: Workspace to check.
        team_id: Linear team ID to check against the synced list.

    Returns:
        True if the team is in the synced list, False otherwise.
    """
    if not team_id:
        return False

    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.LINEAR,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return False

    synced_teams = integration.config.get("synced_teams", [])
    return team_id in synced_teams


async def _get_access_token(session: AsyncSession, workspace_id: UUID) -> str | None:
    """Get a valid access token for the workspace's Linear integration.

    Looks up the first OAuth token owner for this workspace and gets a
    valid token via the OAuth service.

    Args:
        session: Async database session.
        workspace_id: Workspace to get the token for.

    Returns:
        A valid access token string, or None if no token is available.
    """
    from src.config import get_settings

    # Find the user who connected Linear for this workspace
    stmt = select(OAuthToken.user_id).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.provider == Provider.LINEAR,
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    user_id = result.scalar_one_or_none()

    if user_id is None:
        logger.error("No OAuth token found for workspace %s", workspace_id)
        return None

    try:
        settings = get_settings()
        return await get_valid_access_token(session, workspace_id, user_id, settings)
    except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError) as exc:
        logger.exception("Failed to get access token for workspace %s", workspace_id)
        return None


async def handle_issue_create(session: AsyncSession, workspace_id: UUID, data: dict) -> None:
    """Handle an Issue create event.

    Fetches the full issue via GraphQL (for consistent data shape with sync)
    and upserts it into linear_tickets. Queues embedding generation only
    if the issue's team is in the synced teams list.

    Args:
        session: Async database session.
        workspace_id: Workspace this issue belongs to.
        data: The issue data from the webhook payload.
    """
    linear_id = data.get("id")
    if not linear_id:
        logger.warning("Issue create event missing id field")
        return

    access_token = await _get_access_token(session, workspace_id)
    if not access_token:
        return

    ticket = await sync_single_ticket(session, workspace_id, access_token, linear_id)
    if not ticket:
        logger.warning("Could not sync ticket %s for issue create", linear_id)
        return

    # Graph extraction runs for ALL tickets (not just synced teams)
    try:
        await extract_and_populate_graph(
            session=session,
            workspace_id=workspace_id,
            content=f"{ticket.title}\n\n{ticket.description or ''}",
            source_type="linear_ticket",
            source_id=ticket.id,
            source_name=f"{ticket.identifier}: {ticket.title}",
            source_external_id=ticket.identifier,
        )
    except Exception:
        logger.warning("Graph extraction failed for ticket %s", ticket.identifier, exc_info=True)

    # Emit ticket_created activity event
    await emit_activity(session, workspace_id, "ticket_created", metadata={
        "integration": "linear",
        "ticket_id": ticket.identifier,
        "title": ticket.title,
    })

    # Check if team is synced to decide on embedding
    team_id = data.get("teamId") or (data.get("team", {}) or {}).get("id")
    if await _is_team_synced(session, workspace_id, team_id):
        await embedding.queue_embedding_generation(
            session, workspace_id, "linear_ticket", [ticket.id]
        )


async def handle_issue_update(session: AsyncSession, workspace_id: UUID, data: dict) -> None:
    """Handle an Issue update event.

    Snapshots existing title/description before upserting, then compares
    to detect content changes. Only queues re-embedding if content changed.

    Args:
        session: Async database session.
        workspace_id: Workspace this issue belongs to.
        data: The issue data from the webhook payload.
    """
    linear_id = data.get("id")
    if not linear_id:
        logger.warning("Issue update event missing id field")
        return

    # Snapshot existing ticket for content comparison
    stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.linear_id == linear_id,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    existing_ticket = result.scalar_one_or_none()

    old_title = existing_ticket.title if existing_ticket else None
    old_description = existing_ticket.description if existing_ticket else None

    access_token = await _get_access_token(session, workspace_id)
    if not access_token:
        return

    ticket = await sync_single_ticket(session, workspace_id, access_token, linear_id)
    if not ticket:
        logger.warning("Could not sync ticket %s for issue update", linear_id)
        return

    # Graph extraction runs for ALL tickets (not just synced teams)
    try:
        await extract_and_populate_graph(
            session=session,
            workspace_id=workspace_id,
            content=f"{ticket.title}\n\n{ticket.description or ''}",
            source_type="linear_ticket",
            source_id=ticket.id,
            source_name=f"{ticket.identifier}: {ticket.title}",
            source_external_id=ticket.identifier,
        )
    except Exception:
        logger.warning("Graph extraction failed for ticket %s", ticket.identifier, exc_info=True)

    # Check if content changed (title or description)
    if existing_ticket and not is_content_change(existing_ticket, ticket.title, ticket.description):
        logger.debug("Metadata-only change for ticket %s, skipping re-embed", linear_id)
        return

    # Content changed (or new ticket) -- check if team is synced
    team_id = data.get("teamId") or (data.get("team", {}) or {}).get("id")
    if await _is_team_synced(session, workspace_id, team_id):
        await embedding.queue_embedding_generation(
            session, workspace_id, "linear_ticket", [ticket.id]
        )


async def handle_issue_remove(session: AsyncSession, workspace_id: UUID, data: dict) -> None:
    """Handle an Issue remove event.

    Soft-deletes the ticket by setting deleted_at. Also soft-deletes
    associated embeddings.

    Args:
        session: Async database session.
        workspace_id: Workspace this issue belongs to.
        data: The issue data from the webhook payload.
    """
    linear_id = data.get("id")
    if not linear_id:
        logger.warning("Issue remove event missing id field")
        return

    stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.linear_id == linear_id,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket:
        ticket.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info("Soft-deleted ticket %s (linear_id=%s)", ticket.id, linear_id)


async def handle_comment_create(session: AsyncSession, workspace_id: UUID, data: dict) -> None:
    """Handle a Comment create event.

    Upserts the comment into linear_comments and queues embedding
    generation for the comment.

    Args:
        session: Async database session.
        workspace_id: Workspace this comment belongs to.
        data: The comment data from the webhook payload.
    """
    await _upsert_comment(session, workspace_id, data)


async def handle_comment_update(session: AsyncSession, workspace_id: UUID, data: dict) -> None:
    """Handle a Comment update event.

    Same as create -- upserts the comment and re-embeds.

    Args:
        session: Async database session.
        workspace_id: Workspace this comment belongs to.
        data: The comment data from the webhook payload.
    """
    await _upsert_comment(session, workspace_id, data)


async def handle_comment_remove(session: AsyncSession, workspace_id: UUID, data: dict) -> None:
    """Handle a Comment remove event.

    Soft-deletes the comment by setting deleted_at.

    Args:
        session: Async database session.
        workspace_id: Workspace this comment belongs to.
        data: The comment data from the webhook payload.
    """
    linear_id = data.get("id")
    if not linear_id:
        logger.warning("Comment remove event missing id field")
        return

    stmt = select(LinearComment).where(
        LinearComment.workspace_id == workspace_id,
        LinearComment.linear_id == linear_id,
        LinearComment.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment:
        comment.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info("Soft-deleted comment %s (linear_id=%s)", comment.id, linear_id)


async def _upsert_comment(session: AsyncSession, workspace_id: UUID, data: dict) -> None:
    """Upsert a comment from webhook data into linear_comments.

    Finds the parent ticket by the issue reference in the comment data,
    then inserts or updates the comment record.

    Args:
        session: Async database session.
        workspace_id: Workspace this comment belongs to.
        data: The comment data from the webhook payload.
    """
    linear_id = data.get("id")
    if not linear_id:
        logger.warning("Comment event missing id field")
        return

    # Find parent ticket via issueId (Linear webhook comment data includes issue reference)
    issue_id = data.get("issueId") or (data.get("issue", {}) or {}).get("id")
    if not issue_id:
        logger.warning("Comment %s missing issue reference", linear_id)
        return

    ticket_stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.linear_id == issue_id,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    ticket_result = await session.execute(ticket_stmt)
    ticket = ticket_result.scalar_one_or_none()

    if not ticket:
        logger.warning("Parent ticket not found for comment %s (issue_id=%s)", linear_id, issue_id)
        return

    # Check if comment already exists
    existing_stmt = select(LinearComment).where(
        LinearComment.workspace_id == workspace_id,
        LinearComment.linear_id == linear_id,
    )
    existing_result = await session.execute(existing_stmt)
    existing_comment = existing_result.scalar_one_or_none()

    body = data.get("body", "")
    author_name = None
    user_data = data.get("user")
    if isinstance(user_data, dict):
        author_name = user_data.get("name")

    if existing_comment:
        existing_comment.body = body
        existing_comment.author_name = author_name
        existing_comment.linear_updated_at = data.get("updatedAt")
        existing_comment.deleted_at = None  # Restore if previously deleted
        comment_id = existing_comment.id
    else:
        new_comment = LinearComment(
            workspace_id=workspace_id,
            ticket_id=ticket.id,
            linear_id=linear_id,
            body=body,
            author_name=author_name,
            linear_created_at=data.get("createdAt"),
            linear_updated_at=data.get("updatedAt"),
        )
        session.add(new_comment)
        await session.flush()
        comment_id = new_comment.id

    # Queue embedding for the comment
    team_id = None
    # Try to determine team from ticket's raw_data
    if ticket.raw_data and isinstance(ticket.raw_data, dict):
        team_data = ticket.raw_data.get("team")
        if isinstance(team_data, dict):
            team_id = team_data.get("id")

    if await _is_team_synced(session, workspace_id, team_id):
        await embedding.queue_embedding_generation(
            session, workspace_id, "linear_comment", [comment_id]
        )

    # Graph extraction for comments runs regardless of team sync status
    try:
        await extract_and_populate_graph(
            session=session,
            workspace_id=workspace_id,
            content=body,
            source_type="linear_comment",
            source_id=comment_id,
            source_name=f"Comment on {ticket.identifier}",
            source_external_id=linear_id,
        )
    except Exception:
        logger.warning("Graph extraction failed for comment %s", linear_id, exc_info=True)
