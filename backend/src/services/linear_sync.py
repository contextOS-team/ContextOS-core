"""Linear ticket sync orchestration service.

Fetches teams and tickets from Linear via GraphQL, upserts into the database,
and queues embedding generation as a decoupled background step.

Per user decisions:
- Pull all tickets except Cancelled (Done/Completed included for historical context)
- Embedding generation is decoupled from sync
"""

import logging
import time
from datetime import datetime, timezone
from uuid import UUID

import httpx
import sqlalchemy.exc


def _parse_iso(iso_str: str | None) -> datetime | None:
    """Parse ISO-8601 string to naive UTC datetime."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from src.config import Settings
from src.models.integration import Provider, WorkspaceIntegration
from src.models.ticket import LinearComment, LinearTicket
from src.services.embedding_worker import enqueue_embedding_job
from src.services.linear_graphql import LinearGraphQLClient
from src.services.linear_oauth import get_valid_access_token
from src.services.sync_adapter import (
    SyncAdapter,
    SyncRunLogger,
    emit_activity,
    update_cursor_status,
)

logger = logging.getLogger(__name__)

# GraphQL query for fetching teams
TEAMS_QUERY = """
query {
    teams {
        nodes {
            id
            name
            key
        }
    }
}
"""

# GraphQL query for fetching issues with cursor-based pagination
# Excludes cancelled tickets per user decision
ISSUES_QUERY = """
query($teamId: String!, $after: String) {
    team(id: $teamId) {
        issues(first: 50, after: $after, filter: { state: { type: { nin: ["canceled"] } } }) {
            pageInfo { hasNextPage endCursor }
            nodes {
                id identifier title description
                state { name type }
                priority
                assignee { id name }
                team { name }
                project { name }
                labels { nodes { name } }
                comments { nodes { id body user { name } createdAt updatedAt } }
                createdAt updatedAt
            }
        }
    }
}
"""

# GraphQL query for fetching a single issue by ID
SINGLE_ISSUE_QUERY = """
query($issueId: String!) {
    issue(id: $issueId) {
        id identifier title description
        state { name type }
        priority
        assignee { id name }
        team { name }
        project { name }
        labels { nodes { name } }
        comments { nodes { id body user { name } createdAt updatedAt } }
        createdAt updatedAt
    }
}
"""


async def fetch_teams(access_token: str) -> list[dict]:
    """Fetch the list of Linear teams for the authenticated organization.

    Args:
        access_token: Valid Linear access token.

    Returns:
        List of team dicts with id, name, and key fields.
    """
    client = LinearGraphQLClient(access_token)
    try:
        data = await client.query(TEAMS_QUERY)
        return data.get("data", {}).get("teams", {}).get("nodes", [])
    finally:
        await client.close()


async def sync_tickets_for_teams(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    team_ids: list[str],
    settings: Settings,
) -> dict:
    """Sync all non-cancelled tickets for the given teams from Linear.

    Main sync entry point. For each team:
    1. Fetches all issues (excluding cancelled) with cursor-based pagination
    2. Upserts tickets into linear_tickets
    3. Upserts comments into linear_comments
    4. Queues embedding generation for synced tickets

    Also persists selected team_ids and sync metadata in workspace_integrations.config.
    Writes to sync_cursors for structured state tracking.

    Args:
        session: Async database session.
        workspace_id: Workspace to sync tickets for.
        user_id: User who initiated the sync.
        team_ids: List of Linear team IDs to sync.
        settings: Application settings.

    Returns:
        Summary dict: {"tickets_synced": N, "comments_synced": M, "teams": [...]}
    """
    access_token = await get_valid_access_token(session, workspace_id, user_id, settings)

    # Update sync status to in_progress (both JSONB and sync_cursors)
    await _update_sync_status(session, workspace_id, "in_progress", 0)
    await update_cursor_status(
        session, workspace_id, "linear", "default",
        sync_status="syncing",
    )

    client = LinearGraphQLClient(access_token)
    total_tickets = 0
    total_comments = 0
    synced_team_names: list[str] = []

    _sync_t0 = time.monotonic()
    all_issues: list[dict] = []

    async with SyncRunLogger("linear", workspace_id) as srl:
        await emit_activity(session, workspace_id, "sync_started", metadata={"integration": "linear"})
        try:
            for team_id in team_ids:
                # Fetch all issues for this team with pagination
                issues = await client.fetch_all_pages(
                    ISSUES_QUERY,
                    {"teamId": team_id},
                    ["team", "issues"],
                )

                team_name = issues[0]["team"]["name"] if issues else None
                if team_name:
                    synced_team_names.append(team_name)

                # Upsert tickets and comments
                ticket_ids = await _upsert_tickets(session, workspace_id, issues)
                comment_count = await _upsert_comments(session, workspace_id, issues, ticket_ids)

                # Create graph nodes for synced tickets
                graph_count = await _extract_graph_for_tickets(session, workspace_id, issues, ticket_ids)
                logger.info("Created graph nodes for %d tickets in team %s", graph_count, team_id)

                all_issues.extend(issues)

                total_tickets += len(ticket_ids)
                total_comments += comment_count

                # Update progress after each team
                await _update_sync_status(session, workspace_id, "in_progress", total_tickets)

            # Queue embedding generation for synced tickets
            if ticket_ids_list := list(ticket_ids.values()):
                await enqueue_embedding_job(
                    workspace_id, "linear_ticket", ticket_ids_list
                )

            # Update sync status to complete (both JSONB and sync_cursors)
            await _update_sync_status(
                session, workspace_id, "complete", total_tickets, team_ids
            )
            await update_cursor_status(
                session, workspace_id, "linear", "default",
                sync_status="complete",
                records_synced=total_tickets,
            )

            _sync_duration_ms = int((time.monotonic() - _sync_t0) * 1000)
            await emit_activity(session, workspace_id, "sync_completed", metadata={
                "integration": "linear",
                "items_count": total_tickets,
                "duration_ms": _sync_duration_ms,
            })

            srl.info(
                "Linear sync complete: %d tickets synced" % total_tickets,
            )

            # Seed Linear roster for identity resolution (fail-silent)
            roster_seeded = False
            try:
                from src.services.identity_resolution import fetch_linear_roster, seed_roster

                members = await fetch_linear_roster(session, workspace_id, user_id, settings)
                seeded = await seed_roster(session, workspace_id, "linear", members)
                roster_seeded = True
                logger.info(
                    "Linear roster seeding: %d members for workspace %s",
                    seeded,
                    workspace_id,
                )
            except Exception:
                logger.warning(
                    "Linear roster seeding failed for workspace %s — "
                    "assignee linking will be skipped (identity mappings may not exist)",
                    workspace_id,
                    exc_info=True,
                )

            # Link ticket assignees to Person graph nodes (fail-silent)
            # Only attempt if roster was seeded, since this depends on
            # identity_mappings being populated with canonical_person_ids.
            if roster_seeded:
                try:
                    await _link_ticket_assignees(session, workspace_id, all_issues)
                except Exception:
                    logger.warning(
                        "Ticket assignee linking failed for workspace %s (non-blocking)",
                        workspace_id,
                        exc_info=True,
                    )
            else:
                logger.info(
                    "Skipping ticket assignee linking for workspace %s — "
                    "roster seeding did not complete",
                    workspace_id,
                )

        except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError) as e:
            await emit_activity(session, workspace_id, "sync_completed", metadata={
                "integration": "linear",
                "error": True,
                "error_message": str(e)[:200],
            })
            await _update_sync_status(session, workspace_id, "error", total_tickets)
            await update_cursor_status(
                session, workspace_id, "linear", "default",
                sync_status="error",
                error_message="sync failed",
            )
            srl.exception("Linear sync failed")
            raise
        finally:
            await client.close()

    return {
        "tickets_synced": total_tickets,
        "comments_synced": total_comments,
        "teams": synced_team_names,
    }


async def sync_single_ticket(
    session: AsyncSession,
    workspace_id: UUID,
    access_token: str,
    linear_issue_id: str,
) -> LinearTicket | None:
    """Fetch and upsert a single ticket by Linear issue ID.

    Used by the webhook handler (Plan 02-03) for real-time updates.

    Args:
        session: Async database session.
        workspace_id: Workspace to store the ticket in.
        access_token: Valid Linear access token.
        linear_issue_id: Linear issue UUID.

    Returns:
        The upserted LinearTicket, or None if the issue was not found.
    """
    client = LinearGraphQLClient(access_token)
    try:
        data = await client.query(SINGLE_ISSUE_QUERY, {"issueId": linear_issue_id})
        issue = data.get("data", {}).get("issue")
        if not issue:
            return None

        ticket_ids = await _upsert_tickets(session, workspace_id, [issue])
        await _upsert_comments(session, workspace_id, [issue], ticket_ids)

        # Create graph nodes for the synced ticket
        await _extract_graph_for_tickets(session, workspace_id, [issue], ticket_ids)

        # Return the upserted ticket
        linear_id = issue["id"]
        ticket_uuid = ticket_ids.get(linear_id)
        if ticket_uuid:
            stmt = select(LinearTicket).where(LinearTicket.id == ticket_uuid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        return None
    finally:
        await client.close()


async def _upsert_tickets(
    session: AsyncSession,
    workspace_id: UUID,
    issues: list[dict],
) -> dict[str, UUID]:
    """Upsert Linear issues into the linear_tickets table.

    Uses ON CONFLICT (workspace_id, linear_id) DO UPDATE for idempotent upserts.

    Args:
        session: Async database session.
        workspace_id: Workspace to associate tickets with.
        issues: List of issue dicts from Linear GraphQL response.

    Returns:
        Mapping of linear_id -> ticket UUID (from DB).
    """
    ticket_id_map: dict[str, UUID] = {}

    for issue in issues:
        linear_id = issue["id"]
        labels = [l["name"] for l in issue.get("labels", {}).get("nodes", [])]

        values = {
            "workspace_id": workspace_id,
            "linear_id": linear_id,
            "identifier": issue["identifier"],
            "title": issue["title"],
            "description": issue.get("description"),
            "status": issue.get("state", {}).get("name") if issue.get("state") else None,
            "priority": issue.get("priority"),
            "assignee_name": issue.get("assignee", {}).get("name") if issue.get("assignee") else None,
            "team_name": issue.get("team", {}).get("name") if issue.get("team") else None,
            "project_name": issue.get("project", {}).get("name") if issue.get("project") else None,
            "labels": labels if labels else None,
            "linear_created_at": _parse_iso(issue.get("createdAt")),
            "linear_updated_at": _parse_iso(issue.get("updatedAt")),
            "raw_data": issue,
        }

        stmt = insert(LinearTicket).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["workspace_id", "linear_id"],
            set_={
                "identifier": stmt.excluded.identifier,
                "title": stmt.excluded.title,
                "description": stmt.excluded.description,
                "status": stmt.excluded.status,
                "priority": stmt.excluded.priority,
                "assignee_name": stmt.excluded.assignee_name,
                "team_name": stmt.excluded.team_name,
                "project_name": stmt.excluded.project_name,
                "labels": stmt.excluded.labels,
                "linear_created_at": stmt.excluded.linear_created_at,
                "linear_updated_at": stmt.excluded.linear_updated_at,
                "raw_data": stmt.excluded.raw_data,
            },
        ).returning(LinearTicket.id)

        result = await session.execute(stmt)
        ticket_uuid = result.scalar_one()
        ticket_id_map[linear_id] = ticket_uuid

    await session.flush()
    return ticket_id_map


async def _link_ticket_assignees(
    session: AsyncSession,
    workspace_id: UUID,
    issues: list[dict],
) -> int:
    """Create assigned_to graph edges from ticket nodes to person nodes.

    For each issue with an assignee, looks up the identity mapping by
    Linear user ID and creates an assigned_to edge from the ticket's
    graph node to the canonical Person node.

    Fail-silent: logs errors but never raises.
    """
    from src.models.identity_mapping import IdentityMapping
    from src.services.graph_ops import compute_fingerprint, upsert_edge

    linked = 0
    for issue in issues:
        assignee = issue.get("assignee")
        if not assignee or not assignee.get("id"):
            continue

        identifier = issue.get("identifier")
        if not identifier:
            continue

        try:
            # Look up identity mapping for this Linear user
            im_stmt = select(IdentityMapping).where(
                IdentityMapping.workspace_id == workspace_id,
                IdentityMapping.platform == "linear",
                IdentityMapping.platform_user_id == assignee["id"],
                IdentityMapping.canonical_person_id.is_not(None),
            )
            im_result = await session.execute(im_stmt)
            mapping = im_result.scalar_one_or_none()
            if not mapping:
                continue

            # Look up ticket graph node
            fp = compute_fingerprint("Ticket", identifier)
            from src.models.graph_node import GraphNode

            node_stmt = select(GraphNode.id).where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.fingerprint == fp,
                GraphNode.deleted_at.is_(None),
            )
            node_result = await session.execute(node_stmt)
            ticket_node_id = node_result.scalar_one_or_none()
            if not ticket_node_id:
                continue

            await upsert_edge(
                session, workspace_id,
                ticket_node_id, mapping.canonical_person_id,
                "assigned_to",
            )
            linked += 1
        except Exception:
            logger.debug(
                "Failed to link assignee for %s (non-blocking)",
                identifier,
                exc_info=True,
            )

    if linked:
        logger.info(
            "Linked %d ticket assignees to Person nodes for workspace %s",
            linked, workspace_id,
        )
    return linked


async def _extract_graph_for_tickets(
    session: AsyncSession,
    workspace_id: UUID,
    issues: list[dict],
    ticket_id_map: dict[str, UUID],
) -> int:
    """Create graph nodes and extract entities for synced tickets."""
    from src.services.graph_extractor import extract_and_populate_graph

    count = 0
    for issue in issues:
        linear_id = issue["id"]
        ticket_uuid = ticket_id_map.get(linear_id)
        if not ticket_uuid:
            continue

        identifier = issue.get("identifier", "")
        title = issue.get("title", "")
        description = issue.get("description") or ""
        content = f"{identifier}: {title}\n\n{description}"

        await extract_and_populate_graph(
            session=session,
            workspace_id=workspace_id,
            content=content,
            source_type="linear_ticket",
            source_id=ticket_uuid,
            source_name=f"{identifier}: {title}",
            source_external_id=identifier,
        )
        count += 1

    return count


async def _upsert_comments(
    session: AsyncSession,
    workspace_id: UUID,
    issues: list[dict],
    ticket_id_map: dict[str, UUID],
) -> int:
    """Upsert Linear comments into the linear_comments table.

    Uses ON CONFLICT (workspace_id, linear_id) DO UPDATE for idempotent upserts.

    Args:
        session: Async database session.
        workspace_id: Workspace to associate comments with.
        issues: List of issue dicts containing nested comments.
        ticket_id_map: Mapping of linear_id -> ticket UUID for FK resolution.

    Returns:
        Total number of comments upserted.
    """
    comment_count = 0

    for issue in issues:
        linear_id = issue["id"]
        ticket_uuid = ticket_id_map.get(linear_id)
        if not ticket_uuid:
            continue

        comments = issue.get("comments", {}).get("nodes", [])
        for comment in comments:
            values = {
                "workspace_id": workspace_id,
                "ticket_id": ticket_uuid,
                "linear_id": comment["id"],
                "body": comment["body"],
                "author_name": comment.get("user", {}).get("name") if comment.get("user") else None,
                "linear_created_at": _parse_iso(comment.get("createdAt")),
                "linear_updated_at": _parse_iso(comment.get("updatedAt")),
            }

            stmt = insert(LinearComment).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["workspace_id", "linear_id"],
                set_={
                    "body": stmt.excluded.body,
                    "author_name": stmt.excluded.author_name,
                    "linear_updated_at": stmt.excluded.linear_updated_at,
                },
            )

            await session.execute(stmt)
            comment_count += 1

    await session.flush()
    return comment_count


async def _update_sync_status(
    session: AsyncSession,
    workspace_id: UUID,
    status: str,
    tickets_synced: int,
    team_ids: list[str] | None = None,
) -> None:
    """Update the sync progress in workspace_integrations.config.

    Args:
        session: Async database session.
        workspace_id: Workspace to update.
        status: Sync status (in_progress, complete, error).
        tickets_synced: Number of tickets synced so far.
        team_ids: Selected team IDs (stored on completion).
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.LINEAR,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        config["sync_status"] = status
        config["tickets_synced"] = tickets_synced
        config["last_sync_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        if team_ids is not None:
            config["synced_teams"] = team_ids
        integration.config = config
        await session.flush()


class LinearSyncService:
    """Linear sync service conforming to the SyncAdapter protocol."""

    provider: str = "linear"

    async def full_sync(
        self, session: AsyncSession, workspace_id: UUID, **kwargs
    ) -> dict:
        """Run a full Linear sync. Delegates to sync_tickets_for_teams."""
        user_id = kwargs.get("user_id")
        team_ids = kwargs.get("team_ids", [])
        settings = kwargs.get("settings")
        if user_id is None or settings is None:
            raise ValueError("user_id and settings are required for Linear full_sync")
        return await sync_tickets_for_teams(
            session, workspace_id, user_id, team_ids, settings
        )

    async def handle_webhook(
        self, session: AsyncSession, workspace_id: UUID, payload: dict
    ) -> None:
        """Process a Linear webhook event (stub for future implementation)."""
        return None

    async def reconcile(
        self, session: AsyncSession, workspace_id: UUID
    ) -> dict:
        """Reconcile local state with Linear API (stub for Plan 10-03)."""
        return {"status": "not_implemented"}


assert isinstance(LinearSyncService(), SyncAdapter)
