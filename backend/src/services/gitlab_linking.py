"""MR-to-Linear ticket linking via branch name pattern parsing.

Parses GitLab MR source branch names to extract Linear issue identifiers
(e.g., "feat/ENG-123-add-auth" -> "ENG-123") and links MRs to
matching Linear tickets in the database.

Reuses extract_linear_issue_id and get_linear_team_keys from
github_linking -- branch name patterns are provider-agnostic.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.gitlab import GitlabMergeRequest
from src.models.ticket import LinearTicket
from src.services.github_linking import extract_linear_issue_id, get_linear_team_keys

logger = logging.getLogger(__name__)


async def link_mr_to_ticket(
    workspace_id: UUID,
    source_branch: str,
    mr_id: UUID,
    session: AsyncSession,
) -> UUID | None:
    """Attempt to link a GitLab MR to a Linear ticket via branch name.

    Reuses extract_linear_issue_id from github_linking for the actual
    parsing logic -- branch name patterns are provider-agnostic.

    Args:
        workspace_id: Workspace to search tickets in.
        source_branch: The MR source branch name.
        mr_id: UUID of the GitlabMergeRequest record.
        session: Async database session.

    Returns:
        The linear_ticket_id UUID if linked, or None.
    """
    team_keys = await get_linear_team_keys(workspace_id, session)

    if not team_keys:
        logger.debug(
            "No Linear team keys found for workspace %s, skipping linking",
            workspace_id,
        )
        return None

    issue_id = extract_linear_issue_id(source_branch, team_keys)

    if not issue_id:
        logger.debug("No Linear issue ID found in branch '%s'", source_branch)
        return None

    # Look up the ticket by identifier
    stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.identifier == issue_id,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket:
        # Update the MR record with the linked ticket ID
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
    else:
        logger.debug(
            "Linear ticket %s not found for branch '%s'",
            issue_id, source_branch,
        )

    return None
