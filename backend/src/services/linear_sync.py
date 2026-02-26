"""Linear ticket sync orchestration service.

Fetches teams and tickets from Linear via GraphQL, upserts into the database,
and queues embedding generation as a decoupled background step.

Per user decisions:
- Pull all tickets except Cancelled (Done/Completed included for historical context)
- Embedding generation is decoupled from sync
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from src.config import Settings
from src.models.integration import WorkspaceIntegration
from src.models.ticket import LinearComment, LinearTicket
from src.services import embedding
from src.services.linear_graphql import LinearGraphQLClient
from src.services.linear_oauth import get_valid_access_token

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
                assignee { name }
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
        assignee { name }
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

    # Update sync status to in_progress
    await _update_sync_status(session, workspace_id, "in_progress", 0)

    client = LinearGraphQLClient(access_token)
    total_tickets = 0
    total_comments = 0
    synced_team_names: list[str] = []

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

            total_tickets += len(ticket_ids)
            total_comments += comment_count

            # Update progress after each team
            await _update_sync_status(session, workspace_id, "in_progress", total_tickets)

        # Queue embedding generation for synced tickets
        if ticket_ids_list := list(ticket_ids.values()):
            await embedding.queue_embedding_generation(
                session, workspace_id, "linear_ticket", ticket_ids_list
            )

        # Update sync status to complete
        await _update_sync_status(
            session, workspace_id, "complete", total_tickets, team_ids
        )

    except Exception:
        await _update_sync_status(session, workspace_id, "error", total_tickets)
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
            "linear_created_at": issue.get("createdAt"),
            "linear_updated_at": issue.get("updatedAt"),
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
                "linear_created_at": comment.get("createdAt"),
                "linear_updated_at": comment.get("updatedAt"),
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
        WorkspaceIntegration.provider == "linear",
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
