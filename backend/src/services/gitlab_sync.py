"""GitLab MR sync service with 60-day backfill.

Fetches merge requests and notes from the GitLab API for selected projects,
upserts them into the database, and links MRs to Linear tickets via
branch name pattern parsing.

Per user decisions:
- Sequential sync with rate limit awareness
- 60-day backfill window for initial sync
- Bot accounts filtered via is_bot_user
- Draft MRs included
- Unlinked MRs stored gracefully (null linear_ticket_id)
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import sqlalchemy.exc
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.gitlab import GitlabMergeRequest, GitlabReview
from src.models.integration import Provider, WorkspaceIntegration
from src.services.gitlab_common import (
    GITLAB_API_BASE,
    GitLabOAuthError,
    ensure_valid_token,
    gitlab_headers,
    is_bot_user,
    map_mr_state,
    parse_gitlab_timestamp,
    parse_link_next,
)
from src.services.gitlab_linking import link_mr_to_ticket
from src.services.sync_adapter import SyncRunLogger, update_cursor_status

logger = logging.getLogger(__name__)

# Backfill window: 60 days per user decision
BACKFILL_DAYS = 60


async def sync_projects(
    workspace_id: UUID,
    project_ids: list[int],
    session: AsyncSession,
    settings: Settings,
) -> dict:
    """Sync MRs for all selected projects sequentially.

    Processes projects sequentially for rate limit awareness.
    Tracks per-project sync status in workspace_integrations.config JSONB.

    Args:
        workspace_id: Workspace to sync MRs for.
        project_ids: List of numeric GitLab project IDs to sync.
        session: Async database session.
        settings: Application settings.

    Returns:
        Summary dict with total counts and per-project results.
    """
    total_mrs = 0
    total_reviews = 0
    results = {}

    async with SyncRunLogger("gitlab", workspace_id) as srl:
        for project_id in project_ids:
            try:
                await _update_project_sync_status(
                    session, workspace_id, project_id, "syncing", 0, 0
                )
                await update_cursor_status(
                    session, workspace_id, "gitlab", str(project_id),
                    sync_status="syncing",
                )

                mr_count, review_count = await sync_single_project(
                    workspace_id, project_id, session, settings
                )

                await _update_project_sync_status(
                    session, workspace_id, project_id, "synced", mr_count, mr_count
                )
                await update_cursor_status(
                    session, workspace_id, "gitlab", str(project_id),
                    sync_status="complete",
                    records_synced=mr_count,
                )

                total_mrs += mr_count
                total_reviews += review_count
                results[str(project_id)] = {
                    "status": "synced",
                    "mrs": mr_count,
                    "reviews": review_count,
                }

                srl.info("Synced project %d: %d MRs" % (project_id, mr_count))

            except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError) as e:
                srl.error("Sync failed for project %d: %s" % (project_id, e))
                await _update_project_sync_status(
                    session, workspace_id, project_id, "error", 0, 0
                )
                await update_cursor_status(
                    session, workspace_id, "gitlab", str(project_id),
                    sync_status="error",
                    error_message=str(e),
                )
                results[str(project_id)] = {"status": "error", "error": str(e)}

        srl.info(
            "GitLab sync complete: %d MRs across %d projects"
            % (total_mrs, len(project_ids))
        )

    return {
        "total_mrs": total_mrs,
        "total_reviews": total_reviews,
        "projects": results,
    }


async def sync_single_project(
    workspace_id: UUID,
    project_id: int,
    session: AsyncSession,
    settings: Settings,
) -> tuple[int, int]:
    """Sync MRs and notes for a single project.

    Fetches all MRs updated within the 60-day backfill window,
    filters bot accounts, upserts MR and review records, and
    attempts Linear ticket linking for each MR.

    Args:
        workspace_id: Workspace to sync into.
        project_id: Numeric GitLab project ID.
        session: Async database session.
        settings: Application settings.

    Returns:
        Tuple of (mr_count, review_count).
    """
    token = await ensure_valid_token(session, workspace_id, settings)

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=BACKFILL_DAYS)
    updated_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    mr_count = 0
    review_count = 0

    url: str | None = (
        f"{GITLAB_API_BASE}/projects/{project_id}/merge_requests"
        f"?state=all&order_by=updated_at&sort=desc&per_page=100"
        f"&updated_after={updated_after}"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            response = await client.get(url, headers=gitlab_headers(token))

            if response.status_code != 200:
                raise GitLabOAuthError(
                    f"GitLab API error fetching MRs for project {project_id}: "
                    f"{response.status_code} {response.text}"
                )

            mrs = response.json()

            for mr_data in mrs:
                # Filter bot accounts
                author_data = mr_data.get("author", {})
                if is_bot_user(author_data):
                    continue

                # Upsert the MR
                mr_record = await _upsert_mr(
                    session, workspace_id, project_id, mr_data
                )
                mr_count += 1

                # Fetch and upsert notes (skip system notes)
                iid = mr_data["iid"]
                notes = await _fetch_notes(
                    client, token, project_id, iid
                )
                for note_data in notes:
                    await _upsert_review(
                        session, workspace_id, mr_record.id, note_data
                    )
                    review_count += 1

                # Attempt Linear ticket linking
                await link_mr_to_ticket(
                    workspace_id, mr_data.get("source_branch", ""), mr_record.id, session
                )

            # Parse Link header for next page
            url = parse_link_next(response.headers.get("link"))

    await session.flush()

    # Enqueue embedding generation for synced MRs and reviews
    from src.services.embedding_worker import enqueue_embedding_job

    # Collect all MR and review IDs for this project
    mr_ids_stmt = select(GitlabMergeRequest.id).where(
        GitlabMergeRequest.workspace_id == workspace_id,
        GitlabMergeRequest.project_id == project_id,
    )
    mr_result = await session.execute(mr_ids_stmt)
    mr_ids = [row[0] for row in mr_result.fetchall()]

    review_ids_stmt = select(GitlabReview.id).where(
        GitlabReview.workspace_id == workspace_id,
    )
    review_result = await session.execute(review_ids_stmt)
    review_ids = [row[0] for row in review_result.fetchall()]

    if mr_ids:
        await enqueue_embedding_job(workspace_id, "gitlab_merge_request", mr_ids)
        logger.info("Enqueued %d gitlab_merge_request embeddings", len(mr_ids))
    if review_ids:
        await enqueue_embedding_job(workspace_id, "gitlab_review", review_ids)
        logger.info("Enqueued %d gitlab_review embeddings", len(review_ids))

    return mr_count, review_count


async def _upsert_mr(
    session: AsyncSession,
    workspace_id: UUID,
    project_id: int,
    mr_data: dict,
) -> GitlabMergeRequest:
    """Upsert a GitLab merge request record.

    Uses ON CONFLICT (workspace_id, gitlab_id) DO UPDATE for idempotent upserts.
    """
    gitlab_id = mr_data["id"]
    state = map_mr_state(mr_data.get("state", "opened"))

    # Extract project_path from references or path_with_namespace
    references = mr_data.get("references", {})
    full_ref = references.get("full", "")
    project_path = full_ref.rsplit("!", 1)[0] if "!" in full_ref else ""
    if not project_path:
        project_path = mr_data.get("web_url", "").split("/-/")[0].replace("https://gitlab.com/", "")

    # Extract reviewer usernames
    reviewers_data = mr_data.get("reviewers", [])
    reviewers = [r.get("username", "") for r in reviewers_data if isinstance(r, dict)] or None

    values = {
        "workspace_id": workspace_id,
        "gitlab_id": gitlab_id,
        "project_id": project_id,
        "project_path": project_path,
        "iid": mr_data["iid"],
        "title": mr_data.get("title", ""),
        "description": mr_data.get("description"),
        "state": state,
        "author": mr_data.get("author", {}).get("username", "unknown"),
        "source_branch": mr_data.get("source_branch", ""),
        "target_branch": mr_data.get("target_branch", ""),
        "reviewers": reviewers,
        "is_draft": mr_data.get("draft", False) or mr_data.get("work_in_progress", False),
        "gitlab_created_at": parse_gitlab_timestamp(mr_data.get("created_at")),
        "gitlab_updated_at": parse_gitlab_timestamp(mr_data.get("updated_at")),
        "gitlab_merged_at": parse_gitlab_timestamp(mr_data.get("merged_at")),
        "raw_data": mr_data,
    }

    stmt = insert(GitlabMergeRequest).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "gitlab_id"],
        set_={
            "project_id": stmt.excluded.project_id,
            "project_path": stmt.excluded.project_path,
            "iid": stmt.excluded.iid,
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "state": stmt.excluded.state,
            "author": stmt.excluded.author,
            "source_branch": stmt.excluded.source_branch,
            "target_branch": stmt.excluded.target_branch,
            "reviewers": stmt.excluded.reviewers,
            "is_draft": stmt.excluded.is_draft,
            "gitlab_created_at": stmt.excluded.gitlab_created_at,
            "gitlab_updated_at": stmt.excluded.gitlab_updated_at,
            "gitlab_merged_at": stmt.excluded.gitlab_merged_at,
            "raw_data": stmt.excluded.raw_data,
        },
    ).returning(GitlabMergeRequest.__table__.c.id)

    result = await session.execute(stmt)
    mr_uuid = result.scalar_one()
    await session.flush()

    # Fetch the full record for linking
    mr_stmt = select(GitlabMergeRequest).where(GitlabMergeRequest.id == mr_uuid)
    mr_result = await session.execute(mr_stmt)
    return mr_result.scalar_one()


async def _fetch_notes(
    client: httpx.AsyncClient,
    token: str,
    project_id: int,
    mr_iid: int,
) -> list[dict]:
    """Fetch non-system notes for a specific MR.

    Skips system notes (where system=true) as they are auto-generated
    by GitLab and not user comments.
    """
    url: str | None = (
        f"{GITLAB_API_BASE}/projects/{project_id}"
        f"/merge_requests/{mr_iid}/notes?per_page=100"
    )
    all_notes: list[dict] = []

    while url:
        response = await client.get(url, headers=gitlab_headers(token))

        if response.status_code != 200:
            logger.warning(
                "Failed to fetch notes for project %d MR !%d: %d",
                project_id, mr_iid, response.status_code,
            )
            return all_notes

        notes = response.json()
        for note in notes:
            # Skip system-generated notes
            if note.get("system", False):
                continue
            all_notes.append(note)

        url = parse_link_next(response.headers.get("link"))

    return all_notes


async def _upsert_review(
    session: AsyncSession,
    workspace_id: UUID,
    merge_request_id: UUID,
    note_data: dict,
) -> None:
    """Upsert a GitLab review/note record.

    Uses ON CONFLICT (workspace_id, gitlab_id) DO UPDATE for idempotent upserts.
    Maps note types: regular notes get state='note', approval-type get state='approved'.
    """
    gitlab_id = note_data["id"]

    # Determine state: regular notes vs approval notes
    body = note_data.get("body", "")
    state = "note"
    if body and body.strip().lower() == "approved this merge request":
        state = "approved"

    # Extract file context if available (from diff notes)
    position = note_data.get("position", {})
    file_path = position.get("new_path") or position.get("old_path")
    line_range = None
    new_line = position.get("new_line")
    old_line = position.get("old_line")
    if new_line is not None:
        line_range = str(new_line)
        if old_line is not None and old_line != new_line:
            line_range = f"{old_line}-{new_line}"

    values = {
        "workspace_id": workspace_id,
        "merge_request_id": merge_request_id,
        "gitlab_id": gitlab_id,
        "author": note_data.get("author", {}).get("username", "unknown"),
        "state": state,
        "body": body if body else None,
        "file_path": file_path,
        "line_range": line_range,
        "gitlab_submitted_at": parse_gitlab_timestamp(note_data.get("created_at")),
        "raw_data": note_data,
    }

    stmt = insert(GitlabReview).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "gitlab_id"],
        set_={
            "merge_request_id": stmt.excluded.merge_request_id,
            "author": stmt.excluded.author,
            "state": stmt.excluded.state,
            "body": stmt.excluded.body,
            "file_path": stmt.excluded.file_path,
            "line_range": stmt.excluded.line_range,
            "gitlab_submitted_at": stmt.excluded.gitlab_submitted_at,
            "raw_data": stmt.excluded.raw_data,
        },
    )

    await session.execute(stmt)
    await session.flush()


async def _update_project_sync_status(
    session: AsyncSession,
    workspace_id: UUID,
    project_id: int,
    status: str,
    synced: int,
    total: int,
) -> None:
    """Update per-project sync status in workspace_integrations.config JSONB."""
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        project_sync = config.get("project_sync_status", {})
        project_sync[str(project_id)] = {
            "status": status,
            "synced": synced,
            "total": total,
        }
        config["project_sync_status"] = project_sync
        integration.config = config
        await session.flush()
