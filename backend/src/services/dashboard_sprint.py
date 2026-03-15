"""Dashboard sprint progress service.

Queries the Linear API for the active cycle (sprint) of the workspace's
teams and returns progress data for the dashboard widget.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import get_settings
from src.models.integration import Provider, WorkspaceIntegration
from src.services.linear_graphql import LinearGraphQLClient
from src.services.linear_oauth import get_valid_access_token

logger = logging.getLogger(__name__)

ACTIVE_CYCLE_QUERY = """
query {
  teams {
    nodes {
      id
      name
      activeCycle {
        id
        name
        number
        startsAt
        endsAt
        completedScopeCount
        totalScopeCount
        progress
      }
    }
  }
}
"""


async def get_active_sprint(
    session: AsyncSession, workspace_id: UUID, user_id: UUID
) -> dict | None:
    """Get the active Linear cycle (sprint) for the workspace.

    Looks up the workspace's Linear integration, retrieves a valid
    access token, queries the Linear GraphQL API for active cycles,
    and returns the team with the cycle ending soonest.

    Returns None if Linear is not connected or no active cycle exists.
    """
    # Check if Linear is connected
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.LINEAR,
        WorkspaceIntegration.status == "connected",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None:
        return None

    # Get valid access token
    settings = get_settings()
    try:
        access_token = await get_valid_access_token(
            session, workspace_id, user_id, settings
        )
    except Exception:
        logger.warning(
            "Failed to get Linear access token for workspace %s", workspace_id
        )
        return None

    # Query Linear for active cycles
    client = LinearGraphQLClient(access_token)
    try:
        data = await client.query(ACTIVE_CYCLE_QUERY)
    except Exception:
        logger.warning("Failed to query Linear active cycles for workspace %s", workspace_id)
        return None
    finally:
        await client.close()

    # Find the team with the cycle ending soonest
    teams = data.get("data", {}).get("teams", {}).get("nodes", [])
    best = None
    best_ends_at = None

    for team in teams:
        cycle = team.get("activeCycle")
        if cycle is None:
            continue

        ends_at = cycle.get("endsAt")
        if best is None or (ends_at and (best_ends_at is None or ends_at < best_ends_at)):
            best = {
                "team_name": team.get("name"),
                "cycle_name": cycle.get("name"),
                "cycle_number": cycle.get("number"),
                "starts_at": cycle.get("startsAt"),
                "ends_at": ends_at,
                "completed": cycle.get("completedScopeCount", 0),
                "total": cycle.get("totalScopeCount", 0),
                "progress": cycle.get("progress", 0),
            }
            best_ends_at = ends_at

    return best
