"""Notion OAuth and sync integration endpoints.

Provides connect, callback, disconnect, status, sync, and re-sync
endpoints for managing the Notion workspace integration.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from src.config import Settings, get_settings
from src.db import async_session, get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import Provider, WorkspaceIntegration
from src.models.notion import NotionPage
from src.services.embedding_worker import enqueue_embedding_job
from src.services.notion_client import NotionClient
from src.services.notion_oauth import (
    NotionOAuthError,
    build_auth_url,
    disconnect,
    exchange_code,
    get_valid_access_token,
)
from src.services.oauth_common import sign_oauth_state, verify_state_or_raise
from src.services.sync_adapter import SyncRunLogger, update_cursor_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notion", tags=["notion"])


@router.get("/connect")
async def connect(
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Generate a Notion OAuth authorization URL.

    Returns a JSON object with the authorization URL that the frontend
    should redirect the user to.
    """
    state = sign_oauth_state(user.workspace_id, settings.NOTION_CLIENT_SECRET)
    authorization_url = build_auth_url(state, settings)
    return {"authorization_url": authorization_url}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Handle Notion OAuth callback.

    Validates the state parameter, exchanges the authorization code for
    tokens, stores them in Vault, and redirects to the frontend.

    This endpoint is NOT auth-protected because Notion redirects here
    directly. The state parameter provides CSRF protection.
    """
    frontend_url = settings.CORS_ORIGINS.split(",")[0].strip()

    try:
        workspace_id = verify_state_or_raise(
            state, settings.NOTION_CLIENT_SECRET, NotionOAuthError
        )
    except NotionOAuthError as e:
        logger.error("Notion OAuth state verification failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?notion=error&reason=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        # Look up user_id from workspace membership (same pattern as linear.py)
        from src.models.user import WorkspaceMember

        stmt = (
            select(WorkspaceMember.user_id)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        user_id = result.scalar_one_or_none()

        if user_id is None:
            return RedirectResponse(
                url=f"{frontend_url}/dashboard?notion=error&reason=workspace_not_found",
                status_code=status.HTTP_302_FOUND,
            )

        ws_info = await exchange_code(code, session, workspace_id, user_id, settings)
        ws_name = ws_info.get("workspace_name", "")

        return RedirectResponse(
            url=f"{frontend_url}/dashboard?notion=connected&workspace={ws_name}",
            status_code=status.HTTP_302_FOUND,
        )
    except NotionOAuthError as e:
        logger.error("Notion OAuth code exchange failed: %s", e)
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?notion=error&reason=exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/disconnect")
async def disconnect_notion(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect the Notion integration.

    Soft-deletes OAuth tokens and marks the integration as disconnected.
    Existing page data is preserved.
    """
    await disconnect(session, user.workspace_id, user.user_id)
    return {"status": "disconnected"}


@router.get("/status")
async def get_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current Notion integration status.

    Returns connection state, workspace name, page count, and last sync time.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.NOTION,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status == "disconnected":
        return {
            "connected": False,
            "workspace_name": None,
            "status": "disconnected",
            "pages_count": 0,
            "last_sync_at": None,
        }

    # Count pages
    count_stmt = select(func.count()).select_from(NotionPage).where(
        NotionPage.workspace_id == user.workspace_id,
        NotionPage.deleted_at.is_(None),
    )
    count_result = await session.execute(count_stmt)
    pages_count = count_result.scalar_one()

    config = integration.config or {}
    return {
        "connected": integration.status == "connected",
        "workspace_name": config.get("external_name"),
        "status": integration.status,
        "sync_status": config.get("sync_status"),
        "pages_count": pages_count,
        "last_sync_at": config.get("last_sync_at"),
    }


async def _check_sync_preconditions(
    session: AsyncSession, workspace_id: UUID
) -> WorkspaceIntegration:
    """Validate integration is connected and not already syncing.

    Returns the integration record on success.
    Raises HTTPException on failure.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.NOTION,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion integration is not connected. Complete OAuth flow first.",
        )

    config = integration.config or {}
    if config.get("sync_status") == "syncing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sync is already in progress.",
        )

    return integration


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def start_sync(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Start a background full sync of Notion pages.

    Validates that the Notion integration is connected and not already
    syncing, then runs the sync as a FastAPI background task.
    Returns immediately with 202 status.
    """
    await _check_sync_preconditions(session, user.workspace_id)

    await _update_sync_config(session, user.workspace_id, {"sync_status": "syncing"})
    await session.commit()

    background_tasks.add_task(
        _run_sync, user.workspace_id, user.user_id, settings
    )

    return {"status": "sync_started"}


@router.post("/resync", status_code=status.HTTP_202_ACCEPTED)
async def resync(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Trigger a manual re-sync of Notion pages.

    Same as sync but intended for manual re-import. Returns 202.
    """
    await _check_sync_preconditions(session, user.workspace_id)

    # Set sync_status immediately so the frontend can start polling
    await _update_sync_config(session, user.workspace_id, {"sync_status": "syncing"})
    await session.commit()

    background_tasks.add_task(
        _run_sync, user.workspace_id, user.user_id, settings
    )

    return {"status": "sync_started"}


PAGE_SIZE_DEFAULT = 10
PAGE_SIZE_MAX = 100


class NotionPageItem(PydanticBaseModel):
    id: str
    notion_id: str
    title: str
    page_type: str | None
    url: str | None


class NotionPagesResponse(PydanticBaseModel):
    pages: list[NotionPageItem]
    total: int
    page: int
    page_size: int


@router.get("/pages", response_model=NotionPagesResponse)
async def list_pages(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
) -> NotionPagesResponse:
    """List synced Notion pages for the current workspace.

    Returns paginated lightweight page metadata (no content or raw_data)
    for display in the integration card UI.
    """
    where_clause = (
        NotionPage.workspace_id == user.workspace_id,
        NotionPage.deleted_at.is_(None),
    )

    # Total count
    count_stmt = select(func.count()).select_from(NotionPage).where(*where_clause)
    total = (await session.execute(count_stmt)).scalar_one()

    # Clamp page to valid range
    max_page = max(1, -(-total // page_size))  # ceil division
    page = min(page, max_page)

    offset = (page - 1) * page_size
    stmt = (
        select(
            NotionPage.id,
            NotionPage.notion_id,
            NotionPage.title,
            NotionPage.page_type,
            NotionPage.url,
        )
        .where(*where_clause)
        .order_by(NotionPage.title.asc())
        .limit(page_size)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).all()

    pages = [
        NotionPageItem(
            id=str(row.id),
            notion_id=row.notion_id,
            title=row.title,
            page_type=row.page_type,
            url=row.url,
        )
        for row in rows
    ]

    return NotionPagesResponse(
        pages=pages,
        total=total,
        page=page,
        page_size=page_size,
    )


CONTENT_BATCH_SIZE = 10


async def _run_sync(
    workspace_id: UUID, user_id: UUID, settings: Settings
) -> None:
    """Background task: sync Notion pages in three phases.

    Uses short-lived DB sessions to avoid holding long transactions that
    block other requests. Also writes to sync_cursors for structured
    state tracking alongside the existing JSONB config updates.

    Phase 1 (fast): Fetch page metadata from the Search API and upsert
    all pages without content. Soft-delete pages no longer in Notion.

    Phase 2 (slow): Fetch block content per page, write content and
    queue embeddings in batches of CONTENT_BATCH_SIZE.

    Phase 3: Mark sync complete.
    """
    async with SyncRunLogger("notion", workspace_id) as srl:
        try:
            # Get access token (short session)
            async with async_session() as session:
                access_token = await get_valid_access_token(
                    session, workspace_id, user_id, settings
                )
                # Mark syncing in sync_cursors
                await update_cursor_status(
                    session, workspace_id, "notion", "default",
                    sync_status="syncing",
                )
                await session.commit()

            # ── Phase 1: fetch all metadata from Notion API ──
            async with NotionClient(access_token) as client:
                all_pages: list[dict] = []
                cursor: str | None = None
                while True:
                    response = await client.search_pages(start_cursor=cursor)
                    all_pages.extend(response.get("results", []))
                    if not response.get("has_more"):
                        break
                    cursor = response.get("next_cursor")
                    if not cursor:
                        break

                srl.info(
                    "Notion API returned %d pages" % len(all_pages),
                )

                # Upsert all metadata in one short transaction
                async with async_session() as session:
                    page_ids: list[UUID] = []
                    synced_notion_ids: set[str] = set()
                    for page_data in all_pages:
                        page_uuid = await _upsert_page_metadata(
                            session, workspace_id, page_data
                        )
                        page_ids.append(page_uuid)
                        synced_notion_ids.add(page_data.get("id", ""))

                    # Soft-delete pages no longer returned by the Notion API
                    await _soft_delete_removed_pages(
                        session, workspace_id, synced_notion_ids
                    )

                    await _update_sync_config(
                        session,
                        workspace_id,
                        {"sync_status": "syncing", "pages_synced": len(page_ids)},
                    )
                    await session.commit()

                srl.info(
                    "Phase 1 done: %d pages indexed" % len(page_ids),
                )

                # ── Phase 2: fetch content & queue embeddings in batches ──
                # Collect (notion_id, content) pairs, then flush in batches.
                batch_contents: list[tuple[str, str | None]] = []
                batch_db_ids: list[UUID] = []

                for i, page_data in enumerate(all_pages):
                    notion_id = page_data.get("id", "")
                    notion_last_edited = page_data.get("last_edited_time")

                    # Check if content needs refetching by comparing last_edited_time
                    should_refetch_content = True
                    if notion_last_edited:
                        async with async_session() as check_session:
                            check_stmt = select(
                                NotionPage.notion_updated_at, NotionPage.content
                            ).where(
                                NotionPage.workspace_id == workspace_id,
                                NotionPage.notion_id == notion_id,
                            )
                            check_result = await check_session.execute(check_stmt)
                            row = check_result.one_or_none()
                            if row and row.content is not None:
                                stored_updated = row.notion_updated_at
                                new_updated = _parse_notion_datetime(notion_last_edited)
                                # Normalize both to naive UTC for comparison
                                if stored_updated and stored_updated.tzinfo is not None:
                                    stored_updated = stored_updated.replace(tzinfo=None)
                                if stored_updated and new_updated and stored_updated >= new_updated:
                                    should_refetch_content = False
                                    srl.info(
                                        "Skipping content refetch for page %s (unchanged since %s)"
                                        % (notion_id, stored_updated),
                                    )

                    if should_refetch_content:
                        try:
                            content_md = await client.get_page_markdown(notion_id)
                        except Exception:
                            srl.warning(
                                "Failed to fetch content for page %s" % notion_id,
                            )
                            content_md = None
                    else:
                        content_md = None  # Keep existing content

                    batch_contents.append((notion_id, content_md))
                    batch_db_ids.append(page_ids[i])

                    is_batch_full = len(batch_contents) >= CONTENT_BATCH_SIZE
                    is_last = i == len(all_pages) - 1

                    if is_batch_full or is_last:
                        async with async_session() as session:
                            for nid, content in batch_contents:
                                if content is not None:
                                    stmt = select(NotionPage).where(
                                        NotionPage.workspace_id == workspace_id,
                                        NotionPage.notion_id == nid,
                                    )
                                    row = (
                                        await session.execute(stmt)
                                    ).scalar_one_or_none()
                                    if row:
                                        row.content = content

                            if batch_db_ids:
                                await enqueue_embedding_job(
                                    workspace_id,
                                    "notion_page",
                                    batch_db_ids,
                                )
                            await session.commit()

                        srl.info(
                            "Phase 2: %d/%d pages" % (i + 1, len(all_pages)),
                        )
                        batch_contents = []
                        batch_db_ids = []

            # ── Phase 3: mark complete (both JSONB and sync_cursors) ──
            async with async_session() as session:
                now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                await _update_sync_config(
                    session,
                    workspace_id,
                    {
                        "sync_status": "complete",
                        "last_sync_at": now,
                        "pages_synced": len(page_ids),
                    },
                )
                await update_cursor_status(
                    session, workspace_id, "notion", "default",
                    sync_status="complete",
                    records_synced=len(page_ids),
                )
                await session.commit()

            srl.info(
                "Notion sync complete: %d pages" % len(page_ids),
            )

        except Exception:
            srl.exception("Notion sync failed")
            try:
                async with async_session() as session:
                    await _update_sync_config(
                        session, workspace_id, {"sync_status": "idle"}
                    )
                    await update_cursor_status(
                        session, workspace_id, "notion", "default",
                        sync_status="error",
                        error_message="sync failed",
                    )
                    await session.commit()
            except Exception:
                srl.exception("Failed to update sync error status")


async def _upsert_page_metadata(
    session: AsyncSession,
    workspace_id: UUID,
    page_data: dict,
) -> UUID:
    """Upsert a page using only data from the search response (no content fetch)."""
    notion_id = page_data.get("id", "")
    title = _extract_title(page_data)
    page_url = page_data.get("url", "")
    last_edited_by_data = page_data.get("last_edited_by", {})
    last_edited_by = last_edited_by_data.get("id", "") if last_edited_by_data else ""
    notion_created = _parse_notion_datetime(page_data.get("created_time"))
    notion_updated = _parse_notion_datetime(page_data.get("last_edited_time"))

    parent = page_data.get("parent", {})
    parent_type = parent.get("type", "")
    page_type = "database_entry" if parent_type == "database_id" else "page"
    parent_id = parent.get("page_id") or parent.get("database_id") or parent.get("workspace")

    return await _upsert_page(
        session,
        workspace_id=workspace_id,
        notion_id=notion_id,
        title=title,
        content=None,  # Content fetched in phase 2
        page_type=page_type,
        parent_id=str(parent_id) if parent_id else None,
        url=page_url,
        last_edited_by=last_edited_by,
        notion_created_at=notion_created,
        notion_updated_at=notion_updated,
        raw_data=page_data,
    )


def _parse_notion_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string from the Notion API.

    Notion returns timestamps like '2025-06-03T05:29:00.000Z'.
    asyncpg requires actual datetime objects, not raw strings.
    Returns naive UTC datetime for SQLModel compatibility.

    Returns:
        Parsed naive datetime (UTC), or None if value is falsy.
    """
    if not value:
        return None
    # Replace only trailing 'Z' (Zulu time) with an explicit UTC offset
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).replace(tzinfo=None)


def _extract_title(page_data: dict) -> str:
    """Extract the page title from Notion page properties.

    Notion pages store titles in the 'properties' dict. The title property
    can have various names but is always of type 'title'.

    Args:
        page_data: Raw Notion page API response.

    Returns:
        Page title string, or 'Untitled' if not found.
    """
    properties = page_data.get("properties", {})
    for prop in properties.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if title_parts:
                return "".join(
                    item.get("plain_text", "") for item in title_parts
                )
    return "Untitled"


async def _soft_delete_removed_pages(
    session: AsyncSession,
    workspace_id: UUID,
    synced_notion_ids: set[str],
) -> None:
    """Mark pages that are no longer in the Notion API response as deleted.

    Any page in the DB for this workspace whose notion_id is NOT in
    synced_notion_ids (and isn't already soft-deleted) gets deleted_at set.
    """
    if not synced_notion_ids:
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stmt = select(NotionPage).where(
        NotionPage.workspace_id == workspace_id,
        NotionPage.deleted_at.is_(None),
        NotionPage.notion_id.notin_(synced_notion_ids),
    )
    result = await session.execute(stmt)
    stale_pages = result.scalars().all()

    for page in stale_pages:
        page.deleted_at = now

    if stale_pages:
        logger.info(
            "Soft-deleted %d pages no longer in Notion for workspace %s",
            len(stale_pages), workspace_id,
        )


async def _upsert_page(
    session: AsyncSession,
    workspace_id: UUID,
    notion_id: str,
    title: str,
    content: str | None,
    page_type: str | None,
    parent_id: str | None,
    url: str | None,
    last_edited_by: str | None,
    notion_created_at: datetime | None,
    notion_updated_at: datetime | None,
    raw_data: dict,
) -> UUID:
    """Upsert a NotionPage record using ON CONFLICT.

    Uses the (workspace_id, notion_id) unique constraint for idempotent upserts.

    Returns:
        The UUID of the upserted page record.
    """
    from sqlalchemy.dialects.postgresql import insert

    values = {
        "workspace_id": workspace_id,
        "notion_id": notion_id,
        "title": title,
        "content": content,
        "page_type": page_type,
        "parent_id": parent_id,
        "url": url,
        "last_edited_by": last_edited_by,
        "notion_created_at": notion_created_at,
        "notion_updated_at": notion_updated_at,
        "raw_data": raw_data,
    }

    stmt = insert(NotionPage).values(**values)

    # Only overwrite content when a value is provided (phase 1 passes None).
    # Always clear deleted_at so previously soft-deleted pages are restored.
    update_set: dict = {
        "title": stmt.excluded.title,
        "page_type": stmt.excluded.page_type,
        "parent_id": stmt.excluded.parent_id,
        "url": stmt.excluded.url,
        "last_edited_by": stmt.excluded.last_edited_by,
        "notion_created_at": stmt.excluded.notion_created_at,
        "notion_updated_at": stmt.excluded.notion_updated_at,
        "raw_data": stmt.excluded.raw_data,
        "deleted_at": None,
    }
    if content is not None:
        update_set["content"] = stmt.excluded.content

    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "notion_id"],
        set_=update_set,
    ).returning(NotionPage.id)

    result = await session.execute(stmt)
    return result.scalar_one()


async def _update_sync_config(
    session: AsyncSession,
    workspace_id: UUID,
    config_update: dict,
) -> None:
    """Update the sync config in workspace_integrations.config.

    Merges new keys into existing config dict.

    Args:
        session: Async database session.
        workspace_id: Workspace to update.
        config_update: Dict of config keys to merge.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.NOTION,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        config.update(config_update)
        integration.config = config
        await session.flush()
