"""PR-to-Linear ticket linking via branch name pattern parsing.

Parses GitHub PR branch names to extract Linear issue identifiers
(e.g., "feat/ENG-123-add-auth" -> "ENG-123") and links PRs to
matching Linear tickets in the database.

Unlinked PRs (no pattern match or ticket not found) are stored
gracefully with null linear_ticket_id per user decision.
"""

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from src.models.github import GithubPullRequest
from src.models.ticket import LinearTicket

logger = logging.getLogger(__name__)


def extract_linear_issue_id(
    branch_name: str,
    team_keys: list[str],
) -> str | None:
    """Parse branch name for a Linear issue identifier.

    Searches the branch name for a pattern matching any of the provided
    team keys followed by a hyphen and one or more digits.

    Supported patterns:
    - "feat/ENG-123-add-auth"   -> "ENG-123"
    - "ENG-123-add-auth"        -> "ENG-123"
    - "bugfix/PROJ-456"         -> "PROJ-456"
    - "my-feature-branch"       -> None (no match)

    Args:
        branch_name: The git branch name from the PR.
        team_keys: List of known Linear team key prefixes (e.g., ["ENG", "PROJ"]).

    Returns:
        The matched issue identifier (e.g., "ENG-123") or None if no match.
    """
    if not team_keys or not branch_name:
        return None

    # Build regex pattern: match any team key followed by hyphen and digits
    # Escape keys for safety and join with alternation
    keys_pattern = "|".join(re.escape(key) for key in team_keys)
    pattern = rf"(?:^|[/\-_])({keys_pattern})-(\d+)"

    match = re.search(pattern, branch_name, re.IGNORECASE)
    if match:
        # Return the matched identifier in uppercase (Linear convention)
        team_key = match.group(1).upper()
        number = match.group(2)
        return f"{team_key}-{number}"

    # Also try matching at the start of the string without a delimiter
    pattern_start = rf"^({keys_pattern})-(\d+)"
    match_start = re.search(pattern_start, branch_name, re.IGNORECASE)
    if match_start:
        team_key = match_start.group(1).upper()
        number = match_start.group(2)
        return f"{team_key}-{number}"

    return None


async def get_linear_team_keys(
    workspace_id: UUID,
    session: AsyncSession,
) -> list[str]:
    """Auto-detect Linear team keys from existing ticket identifiers.

    Queries the linear_tickets table for distinct team prefixes.
    Extracts the prefix part from the identifier column
    (e.g., "ENG" from "ENG-123").

    Args:
        workspace_id: Workspace to query tickets for.
        session: Async database session.

    Returns:
        List of unique team key strings (e.g., ["ENG", "PROJ"]).
    """
    # Extract unique prefixes: split identifier on '-' and take the first part
    # Using SQL SPLIT_PART for efficiency
    from sqlalchemy import text as sa_text

    stmt = sa_text(
        "SELECT DISTINCT SPLIT_PART(identifier, '-', 1) AS prefix "
        "FROM linear_tickets "
        "WHERE workspace_id = :workspace_id AND deleted_at IS NULL"
    )
    result = await session.execute(stmt, {"workspace_id": workspace_id})
    rows = result.fetchall()

    return [row[0] for row in rows if row[0]]


async def link_pr_to_ticket(
    pr: GithubPullRequest,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Attempt to link a PR to a Linear ticket via branch name.

    Extracts the Linear issue identifier from the PR branch name,
    then looks up the matching ticket in the database. If found,
    sets pr.linear_ticket_id. If not found, leaves it as None
    (unlinked per user decision).

    Args:
        pr: The GithubPullRequest record to attempt linking for.
        workspace_id: Workspace to search tickets in.
        session: Async database session.
    """
    team_keys = await get_linear_team_keys(workspace_id, session)

    if not team_keys:
        logger.debug("No Linear team keys found for workspace %s, skipping linking", workspace_id)
        return

    issue_id = extract_linear_issue_id(pr.branch_name, team_keys)

    if not issue_id:
        logger.debug("No Linear issue ID found in branch '%s'", pr.branch_name)
        return

    # Look up the ticket by identifier
    stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.identifier == issue_id,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket:
        pr.linear_ticket_id = ticket.id
        logger.info(
            "Linked PR #%d (%s) to Linear ticket %s",
            pr.number,
            pr.branch_name,
            issue_id,
        )
    else:
        logger.debug(
            "Linear ticket %s not found for branch '%s'",
            issue_id,
            pr.branch_name,
        )
