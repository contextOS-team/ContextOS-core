"""Jira issue sync orchestration service.

Fetches issues and comments from Jira via REST API v3, upserts into the
database, and queues embedding generation as a decoupled background step.

Uses the modern /search/jql endpoint with nextPageToken pagination
(NOT the deprecated /search with startAt).
"""

import logging
import time
from datetime import datetime, timezone
from uuid import UUID

import httpx
import sqlalchemy.exc

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import Provider, WorkspaceIntegration
from src.models.jira import JiraComment, JiraIssue
from src.services.embedding_worker import enqueue_embedding_job
from src.services.jira_oauth import JiraOAuthError, get_valid_token
from src.services.sync_adapter import (
    SyncAdapter,
    SyncRunLogger,
    emit_activity,
    update_cursor_status,
)

logger = logging.getLogger(__name__)

# Fields to request from Jira search
JIRA_ISSUE_FIELDS = [
    "summary", "description", "status", "priority", "assignee",
    "reporter", "project", "labels", "comment", "created", "updated",
    "issuetype",
]


def _api_url(cloud_id: str, path: str) -> str:
    """Build a Jira REST API v3 URL for the given cloud site.

    Args:
        cloud_id: Atlassian cloud ID for the Jira site.
        path: API path (without leading slash).

    Returns:
        Full API URL.
    """
    return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/{path}"


def _parse_iso(iso_str: str | None) -> datetime | None:
    """Parse ISO-8601 string to naive UTC datetime."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _extract_text_from_adf(adf: dict | str | None) -> str | None:
    """Extract plain text from Atlassian Document Format (ADF).

    Jira REST API v3 returns descriptions in ADF format (a JSON structure).
    This extracts readable text content from the document tree.

    Args:
        adf: ADF document dict, plain string, or None.

    Returns:
        Extracted plain text, or None if empty.
    """
    if adf is None:
        return None
    if isinstance(adf, str):
        return adf

    if not isinstance(adf, dict):
        return None

    parts: list[str] = []

    def _walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf)
    text_content = " ".join(parts).strip()
    return text_content if text_content else None


async def sync_jira_issues(
    session: AsyncSession,
    workspace_id: UUID,
    settings: Settings,
    jql: str | None = None,
) -> dict:
    """Sync Jira issues via the modern /search/jql endpoint.

    Uses nextPageToken pagination (NOT the deprecated startAt approach).

    Args:
        session: Async database session.
        workspace_id: Workspace to sync issues for.
        settings: Application settings.
        jql: Optional JQL query. Defaults to "ORDER BY updated DESC".

    Returns:
        Summary dict: {"issues_synced": N, "comments_synced": M}
    """
    access_token, cloud_id = await get_valid_token(session, workspace_id, settings)

    # Update sync status to in_progress
    await _update_sync_status(session, workspace_id, "in_progress", 0)
    await update_cursor_status(
        session, workspace_id, "jira", "default",
        sync_status="syncing",
    )

    total_issues = 0
    total_comments = 0
    _sync_t0 = time.monotonic()

    async with SyncRunLogger("jira", workspace_id) as srl:
        await emit_activity(session, workspace_id, "sync_started", metadata={"integration": "jira"})
        try:
            jql_query = jql or "assignee = currentUser() ORDER BY updated DESC"
            next_page_token: str | None = None

            async with httpx.AsyncClient() as client:
                while True:
                    # Build request body for POST /search/jql
                    body: dict = {
                        "jql": jql_query,
                        "fields": JIRA_ISSUE_FIELDS,
                        "maxResults": 50,
                    }
                    if next_page_token:
                        body["nextPageToken"] = next_page_token

                    response = await client.post(
                        _api_url(cloud_id, "search/jql"),
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                        timeout=30.0,
                    )

                    if response.status_code != 200:
                        raise JiraOAuthError(
                            f"Jira search failed ({response.status_code}): {response.text}"
                        )

                    data = response.json()
                    issues = data.get("issues", [])

                    if not issues:
                        break

                    # Upsert issues and comments
                    issue_ids = await _upsert_issues(session, workspace_id, issues)
                    comment_count = await _upsert_comments(
                        session, workspace_id, issues, issue_ids
                    )

                    # Extract graph nodes for synced issues
                    await _extract_graph_for_issues(
                        session, workspace_id, issues, issue_ids
                    )

                    total_issues += len(issue_ids)
                    total_comments += comment_count

                    # Update progress
                    await _update_sync_status(
                        session, workspace_id, "in_progress", total_issues
                    )

                    # Check for next page
                    next_page_token = data.get("nextPageToken")
                    if not next_page_token:
                        break

            # Queue embedding generation for synced issues
            if total_issues > 0:
                # Collect all issue UUIDs for embedding
                stmt = select(JiraIssue.id).where(
                    JiraIssue.workspace_id == workspace_id,
                    JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
                )
                result = await session.execute(stmt)
                all_issue_uuids = list(result.scalars().all())
                if all_issue_uuids:
                    await enqueue_embedding_job(
                        workspace_id, "jira_issue", all_issue_uuids
                    )

            # Update sync status to complete
            await _update_sync_status(
                session, workspace_id, "complete", total_issues
            )
            await update_cursor_status(
                session, workspace_id, "jira", "default",
                sync_status="complete",
                records_synced=total_issues,
            )

            # Seed Jira roster for identity resolution (fail-silent)
            roster_seeded = False
            try:
                from src.services.identity_resolution import fetch_jira_roster, seed_roster

                members = await fetch_jira_roster(session, workspace_id)
                await seed_roster(session, workspace_id, "jira", members)
                roster_seeded = True
                logger.info("Jira roster seeding: %d members for workspace %s", len(members), workspace_id)
            except Exception:
                logger.warning("Jira roster seeding failed for workspace %s", workspace_id, exc_info=True)

            # Link ticket assignees to Person graph nodes (fail-silent)
            if roster_seeded:
                try:
                    await _link_jira_assignees(session, workspace_id)
                except Exception:
                    logger.warning("Jira assignee linking failed for workspace %s", workspace_id, exc_info=True)

            _sync_duration_ms = int((time.monotonic() - _sync_t0) * 1000)
            await emit_activity(session, workspace_id, "sync_completed", metadata={
                "integration": "jira",
                "items_count": total_issues,
                "duration_ms": _sync_duration_ms,
            })

            srl.info("Jira sync complete: %d issues, %d comments" % (total_issues, total_comments))

        except (httpx.HTTPError, sqlalchemy.exc.SQLAlchemyError, KeyError, ValueError) as e:
            await emit_activity(session, workspace_id, "sync_completed", metadata={
                "integration": "jira",
                "error": True,
                "error_message": str(e)[:200],
            })
            await _update_sync_status(session, workspace_id, "error", total_issues)
            await update_cursor_status(
                session, workspace_id, "jira", "default",
                sync_status="error",
                error_message="sync failed",
            )
            srl.exception("Jira sync failed")
            raise

    return {
        "issues_synced": total_issues,
        "comments_synced": total_comments,
    }


async def _jql_search(
    access_token: str,
    cloud_id: str,
    jql: str,
    *,
    max_results: int = 50,
) -> list[dict]:
    """Execute a JQL search and return normalised issue dicts.

    Single place that owns the Jira ``/search/jql`` HTTP call, header
    construction, response parsing, and error handling.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _api_url(cloud_id, "search/jql"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "jql": jql,
                "fields": ["summary", "status", "assignee", "issuetype"],
                "maxResults": max_results,
            },
            timeout=15.0,
        )

    if response.status_code != 200:
        logger.error("Jira JQL search failed (%s): %s", response.status_code, response.text)
        return []

    data = response.json()
    results: list[dict] = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        results.append({
            "jira_id": issue["id"],
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "status": fields.get("status", {}).get("name") if fields.get("status") else None,
            "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            "issue_type": fields.get("issuetype", {}).get("name") if fields.get("issuetype") else None,
        })
    return results


async def list_my_jira_issues(
    session: AsyncSession,
    workspace_id: UUID,
    settings: Settings,
) -> list[dict]:
    """Return open issues assigned to the current user, most recently updated first."""
    access_token, cloud_id = await get_valid_token(session, workspace_id, settings)
    return await _jql_search(
        access_token, cloud_id,
        "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC",
        max_results=50,
    )


async def search_jira_issues(
    session: AsyncSession,
    workspace_id: UUID,
    settings: Settings,
    query: str,
) -> list[dict]:
    """Search Jira issues by text for UI autocomplete."""
    access_token, cloud_id = await get_valid_token(session, workspace_id, settings)
    safe_query = query.replace('\\', '\\\\').replace('"', '\\"')
    return await _jql_search(
        access_token, cloud_id,
        f'text ~ "{safe_query}" ORDER BY updated DESC',
        max_results=20,
    )


async def _extract_graph_for_issues(
    session: AsyncSession,
    workspace_id: UUID,
    issues: list[dict],
    issue_id_map: dict[str, UUID],
) -> int:
    """Create graph nodes and extract entities for synced Jira issues."""
    from src.services.graph_extractor import extract_and_populate_graph

    count = 0
    for issue in issues:
        jira_id = issue["id"]
        issue_uuid = issue_id_map.get(jira_id)
        if not issue_uuid:
            continue

        key = issue.get("key", "")
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        description = _extract_text_from_adf(fields.get("description"))
        content = f"{key}: {summary}\n\n{description or ''}"

        try:
            await extract_and_populate_graph(
                session=session,
                workspace_id=workspace_id,
                content=content,
                source_type="jira_issue",
                source_id=issue_uuid,
                source_name=f"{key}: {summary}",
                source_external_id=key,
            )
            count += 1
        except Exception:
            logger.warning("Graph extraction failed for Jira issue %s", key, exc_info=True)

    return count


async def _link_jira_assignees(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Create assigned_to and reported_by edges from Jira tickets to Person nodes.

    Batch-fetches identity mappings and graph nodes to avoid N+1 queries,
    then links both assignees and reporters.
    """
    from src.models.identity_mapping import IdentityMapping
    from src.models.jira import JiraIssue
    from src.models.graph_node import GraphNode
    from src.services.graph_ops import compute_fingerprint, upsert_edge

    # 1. Fetch all issues
    stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    issues = result.scalars().all()

    # 2. Batch-fetch all Jira identity mappings with canonical Person
    im_stmt = select(IdentityMapping).where(
        IdentityMapping.workspace_id == workspace_id,
        IdentityMapping.platform == "jira",
        IdentityMapping.canonical_person_id.is_not(None),
        IdentityMapping.deleted_at.is_(None),
    )
    im_result = await session.execute(im_stmt)
    account_to_person: dict[str, UUID] = {
        m.platform_user_id: m.canonical_person_id
        for m in im_result.scalars().all()
        if m.canonical_person_id
    }

    # 3. Batch-fetch all ticket graph nodes by fingerprint
    fps = {issue.jira_key: compute_fingerprint("Ticket", issue.jira_key) for issue in issues}
    fp_values = list(fps.values())
    if fp_values:
        node_stmt = select(GraphNode.id, GraphNode.fingerprint).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.fingerprint.in_(fp_values),
            GraphNode.deleted_at.is_(None),
        )
        node_result = await session.execute(node_stmt)
        fp_to_node_id = {row.fingerprint: row.id for row in node_result}
    else:
        fp_to_node_id = {}

    # 4. Link assignees and reporters
    linked = 0
    for issue in issues:
        ticket_fp = fps.get(issue.jira_key)
        ticket_node_id = fp_to_node_id.get(ticket_fp) if ticket_fp else None
        if not ticket_node_id:
            continue

        raw = issue.raw_data or {}
        fields = raw.get("fields", {})

        for role, edge_type in (("assignee", "assigned_to"), ("reporter", "authored_by")):
            person = fields.get(role)
            if not person or not isinstance(person, dict):
                continue
            account_id = person.get("accountId")
            if not account_id:
                continue
            person_node_id = account_to_person.get(account_id)
            if not person_node_id:
                continue

            try:
                await upsert_edge(
                    session, workspace_id,
                    ticket_node_id, person_node_id,
                    edge_type,
                )
                linked += 1
            except Exception:
                logger.debug("Failed to link %s for %s", role, issue.jira_key, exc_info=True)

    if linked:
        logger.info("Linked %d Jira ticket→Person edges for workspace %s", linked, workspace_id)
    return linked


async def _upsert_issues(
    session: AsyncSession,
    workspace_id: UUID,
    issues: list[dict],
) -> dict[str, UUID]:
    """Upsert Jira issues into the jira_issues table.

    Uses ON CONFLICT (workspace_id, jira_id) DO UPDATE for idempotent upserts.

    Args:
        session: Async database session.
        workspace_id: Workspace to associate issues with.
        issues: List of issue dicts from Jira REST API response.

    Returns:
        Mapping of jira_id -> issue UUID (from DB).
    """
    issue_id_map: dict[str, UUID] = {}

    for issue in issues:
        jira_id = issue["id"]
        fields = issue.get("fields", {})
        labels = [l["name"] if isinstance(l, dict) else l for l in fields.get("labels", [])]

        values = {
            "workspace_id": workspace_id,
            "jira_id": jira_id,
            "jira_key": issue["key"],
            "summary": fields.get("summary", ""),
            "description": _extract_text_from_adf(fields.get("description")),
            "status": fields.get("status", {}).get("name") if fields.get("status") else None,
            "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
            "issue_type": fields.get("issuetype", {}).get("name") if fields.get("issuetype") else None,
            "assignee_name": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            "reporter_name": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
            "project_key": fields.get("project", {}).get("key") if fields.get("project") else None,
            "project_name": fields.get("project", {}).get("name") if fields.get("project") else None,
            "labels": labels if labels else None,
            "jira_created_at": _parse_iso(fields.get("created")),
            "jira_updated_at": _parse_iso(fields.get("updated")),
            "raw_data": issue,
        }

        stmt = insert(JiraIssue).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["workspace_id", "jira_id"],
            set_={
                "jira_key": stmt.excluded.jira_key,
                "summary": stmt.excluded.summary,
                "description": stmt.excluded.description,
                "status": stmt.excluded.status,
                "priority": stmt.excluded.priority,
                "issue_type": stmt.excluded.issue_type,
                "assignee_name": stmt.excluded.assignee_name,
                "reporter_name": stmt.excluded.reporter_name,
                "project_key": stmt.excluded.project_key,
                "project_name": stmt.excluded.project_name,
                "labels": stmt.excluded.labels,
                "jira_created_at": stmt.excluded.jira_created_at,
                "jira_updated_at": stmt.excluded.jira_updated_at,
                "raw_data": stmt.excluded.raw_data,
            },
        ).returning(JiraIssue.id)

        result = await session.execute(stmt)
        issue_uuid = result.scalar_one()
        issue_id_map[jira_id] = issue_uuid

    await session.flush()
    return issue_id_map


async def _upsert_comments(
    session: AsyncSession,
    workspace_id: UUID,
    issues: list[dict],
    issue_id_map: dict[str, UUID],
) -> int:
    """Upsert Jira comments into the jira_comments table.

    Uses ON CONFLICT (workspace_id, jira_id) DO UPDATE for idempotent upserts.

    Args:
        session: Async database session.
        workspace_id: Workspace to associate comments with.
        issues: List of issue dicts containing nested comments.
        issue_id_map: Mapping of jira_id -> issue UUID for FK resolution.

    Returns:
        Total number of comments upserted.
    """
    comment_count = 0

    for issue in issues:
        jira_id = issue["id"]
        issue_uuid = issue_id_map.get(jira_id)
        if not issue_uuid:
            continue

        fields = issue.get("fields", {})
        comment_data = fields.get("comment", {})
        comments = comment_data.get("comments", [])

        for comment in comments:
            body_text = _extract_text_from_adf(comment.get("body"))

            values = {
                "workspace_id": workspace_id,
                "issue_id": issue_uuid,
                "jira_id": comment["id"],
                "body": body_text,
                "author_name": (
                    comment.get("author", {}).get("displayName")
                    if comment.get("author")
                    else None
                ),
                "jira_created_at": _parse_iso(comment.get("created")),
                "jira_updated_at": _parse_iso(comment.get("updated")),
            }

            stmt = insert(JiraComment).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["workspace_id", "jira_id"],
                set_={
                    "body": stmt.excluded.body,
                    "author_name": stmt.excluded.author_name,
                    "jira_updated_at": stmt.excluded.jira_updated_at,
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
    issues_synced: int,
) -> None:
    """Update the sync progress in workspace_integrations.config.

    Args:
        session: Async database session.
        workspace_id: Workspace to update.
        status: Sync status (in_progress, complete, error).
        issues_synced: Number of issues synced so far.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.JIRA,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        config["sync_status"] = status
        config["issues_synced"] = issues_synced
        config["last_sync_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        integration.config = config
        await session.flush()


class JiraSyncService:
    """Jira sync service conforming to the SyncAdapter protocol."""

    provider: str = "jira"

    async def full_sync(
        self, session: AsyncSession, workspace_id: UUID, **kwargs
    ) -> dict:
        """Run a full Jira sync. Delegates to sync_jira_issues."""
        settings = kwargs.get("settings")
        jql = kwargs.get("jql")
        if settings is None:
            raise ValueError("settings is required for Jira full_sync")
        return await sync_jira_issues(session, workspace_id, settings, jql=jql)

    async def handle_webhook(
        self, session: AsyncSession, workspace_id: UUID, payload: dict
    ) -> None:
        """Process a Jira webhook event (delegates to jira_webhook)."""
        from src.services.jira_webhook import process_jira_webhook
        await process_jira_webhook(session, payload, workspace_id)

    async def reconcile(
        self, session: AsyncSession, workspace_id: UUID
    ) -> dict:
        """Reconcile local state with Jira API (stub for future)."""
        return {"status": "not_implemented"}


assert isinstance(JiraSyncService(), SyncAdapter)
