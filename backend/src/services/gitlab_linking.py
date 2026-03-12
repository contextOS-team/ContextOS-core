"""MR-to-ticket linking via branch name pattern parsing.

Parses GitLab MR source branch names to extract ticket identifiers
(e.g., "feat/ENG-123-add-auth" -> "ENG-123") and links MRs to
matching Linear tickets or Jira issues in the database.

Reuses extract_ticket_id, get_linear_team_keys, and
get_jira_project_keys from github_linking — branch name patterns
are provider-agnostic.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.gitlab import GitlabMergeRequest
from src.models.jira import JiraIssue
from src.models.ticket import LinearTicket
from src.services.github_linking import (
    extract_ticket_id,
    get_jira_project_keys,
    get_linear_team_keys,
)

logger = logging.getLogger(__name__)


async def link_mr_to_ticket(
    workspace_id: UUID,
    source_branch: str,
    mr_id: UUID,
    session: AsyncSession,
) -> UUID | None:
    """Attempt to link a GitLab MR to a Linear ticket or Jira issue via branch name.

    Tries Linear first, then Jira.  Returns the linked ticket/issue UUID or None.
    """
    # Try Linear first
    linear_keys = await get_linear_team_keys(workspace_id, session)
    if linear_keys:
        issue_id = extract_ticket_id(source_branch, linear_keys)
        if issue_id:
            stmt = select(LinearTicket).where(
                LinearTicket.workspace_id == workspace_id,
                LinearTicket.identifier == issue_id,
                LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            result = await session.execute(stmt)
            ticket = result.scalar_one_or_none()
            if ticket:
                mr_stmt = select(GitlabMergeRequest).where(GitlabMergeRequest.id == mr_id)
                mr_result = await session.execute(mr_stmt)
                mr_record = mr_result.scalar_one_or_none()
                if mr_record:
                    mr_record.linear_ticket_id = ticket.id
                    logger.info(
                        "Linked GitLab MR %s (branch '%s') to Linear ticket %s",
                        mr_id, source_branch, issue_id,
                    )
                    return ticket.id

    # Try Jira
    jira_keys = await get_jira_project_keys(workspace_id, session)
    if jira_keys:
        issue_id = extract_ticket_id(source_branch, jira_keys)
        if issue_id:
            stmt = select(JiraIssue).where(
                JiraIssue.workspace_id == workspace_id,
                JiraIssue.jira_key == issue_id,
                JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            result = await session.execute(stmt)
            jira_issue = result.scalar_one_or_none()
            if jira_issue:
                mr_stmt = select(GitlabMergeRequest).where(GitlabMergeRequest.id == mr_id)
                mr_result = await session.execute(mr_stmt)
                mr_record = mr_result.scalar_one_or_none()
                if mr_record:
                    mr_record.jira_issue_id = jira_issue.id
                    logger.info(
                        "Linked GitLab MR %s (branch '%s') to Jira issue %s",
                        mr_id, source_branch, issue_id,
                    )
                    return jira_issue.id

    logger.debug("No ticket match in branch '%s'", source_branch)
    return None
