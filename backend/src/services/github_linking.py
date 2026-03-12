"""PR-to-ticket linking via branch name pattern parsing.

Parses GitHub PR branch names to extract ticket identifiers
(e.g., "feat/ENG-123-add-auth" -> "ENG-123") and links PRs to
matching Linear tickets or Jira issues in the database.

Tries Linear first, then Jira.  Unlinked PRs (no pattern match
or ticket not found) are stored gracefully with null FKs.
"""

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.github import GithubPullRequest
from src.models.jira import JiraIssue
from src.models.ticket import LinearTicket

logger = logging.getLogger(__name__)


def extract_ticket_id(
    branch_name: str,
    project_keys: list[str],
) -> str | None:
    """Parse branch name for a ticket identifier (KEY-123 format).

    Works for both Linear and Jira identifiers since both use the
    same KEY-NUMBER pattern.

    Supported patterns:
    - "feat/ENG-123-add-auth"   -> "ENG-123"
    - "ENG-123-add-auth"        -> "ENG-123"
    - "bugfix/PROJ-456"         -> "PROJ-456"
    - "my-feature-branch"       -> None (no match)

    Args:
        branch_name: The git branch name from the PR.
        project_keys: Known key prefixes (e.g., ["ENG", "PROJ"] or ["RD", "APP"]).

    Returns:
        The matched identifier (e.g., "ENG-123") or None.
    """
    if not project_keys or not branch_name:
        return None

    keys_pattern = "|".join(re.escape(key) for key in project_keys)
    pattern = rf"(?:^|[/\-_])({keys_pattern})-(\d+)"

    match = re.search(pattern, branch_name, re.IGNORECASE)
    if match:
        key = match.group(1).upper()
        number = match.group(2)
        return f"{key}-{number}"

    # Also try matching at the start of the string without a delimiter
    pattern_start = rf"^({keys_pattern})-(\d+)"
    match_start = re.search(pattern_start, branch_name, re.IGNORECASE)
    if match_start:
        key = match_start.group(1).upper()
        number = match_start.group(2)
        return f"{key}-{number}"

    return None


# Keep old name as alias so existing callers don't break
extract_linear_issue_id = extract_ticket_id


async def get_linear_team_keys(
    workspace_id: UUID,
    session: AsyncSession,
) -> list[str]:
    """Auto-detect Linear team keys from existing ticket identifiers.

    Queries the linear_tickets table for distinct team prefixes
    (e.g., "ENG" from "ENG-123").
    """
    from sqlalchemy import text as sa_text

    stmt = sa_text(
        "SELECT DISTINCT SPLIT_PART(identifier, '-', 1) AS prefix "
        "FROM linear_tickets "
        "WHERE workspace_id = :workspace_id AND deleted_at IS NULL"
    )
    result = await session.execute(stmt, {"workspace_id": workspace_id})
    rows = result.fetchall()

    return [row[0] for row in rows if row[0]]


async def get_jira_project_keys(
    workspace_id: UUID,
    session: AsyncSession,
) -> list[str]:
    """Auto-detect Jira project keys from existing issue keys.

    Queries the jira_issues table for distinct project prefixes
    (e.g., "RD" from "RD-123").
    """
    from sqlalchemy import text as sa_text

    stmt = sa_text(
        "SELECT DISTINCT SPLIT_PART(jira_key, '-', 1) AS prefix "
        "FROM jira_issues "
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
    """Attempt to link a PR to a Linear ticket or Jira issue via branch name.

    Tries Linear first, then Jira.  Sets pr.linear_ticket_id or
    pr.jira_issue_id accordingly.
    """
    # Try Linear first
    linear_keys = await get_linear_team_keys(workspace_id, session)
    if linear_keys:
        issue_id = extract_ticket_id(pr.branch_name, linear_keys)
        if issue_id:
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
                    pr.number, pr.branch_name, issue_id,
                )
                return

    # Try Jira
    jira_keys = await get_jira_project_keys(workspace_id, session)
    if jira_keys:
        issue_id = extract_ticket_id(pr.branch_name, jira_keys)
        if issue_id:
            stmt = select(JiraIssue).where(
                JiraIssue.workspace_id == workspace_id,
                JiraIssue.jira_key == issue_id,
                JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            result = await session.execute(stmt)
            jira_issue = result.scalar_one_or_none()
            if jira_issue:
                pr.jira_issue_id = jira_issue.id
                logger.info(
                    "Linked PR #%d (%s) to Jira issue %s",
                    pr.number, pr.branch_name, issue_id,
                )
                return

    logger.debug("No ticket match in branch '%s'", pr.branch_name)
