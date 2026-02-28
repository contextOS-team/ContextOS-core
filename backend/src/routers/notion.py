"""Notion OAuth and sync integration endpoints.

Provides connect, callback, disconnect, status, sync, and re-sync
endpoints for managing the Notion workspace integration.
"""

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
from src.services import embedding
from src.services.notion_client import NotionClient
from src.services.notion_oauth import (
    NotionOAuthError,
    build_auth_url,
    disconnect,
    exchange_code,
    get_valid_access_token,
)
from src.services.oauth_common import sign_oauth_state, verify_state_or_raise

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

        stmt = select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
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
        "pages_count": pages_count,
        "last_sync_at": config.get("last_sync_at"),
    }


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def start_sync(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Start a background full sync of Notion pages.

    Validates that the Notion integration is connected, then runs the
    sync as a FastAPI background task. Returns immediately with 202 status.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.NOTION,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion integration is not connected. Complete OAuth flow first.",
        )

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
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
        WorkspaceIntegration.provider == Provider.NOTION,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion integration is not connected. Complete OAuth flow first.",
        )

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


async def _run_sync(
    workspace_id: UUID, user_id: UUID, settings: Settings
) -> None:
    """Background task: fetch all Notion pages and upsert into DB.

    Creates its own session for background task isolation (same pattern
    as webhook services). Updates integration config with sync status.

    Args:
        workspace_id: Workspace to sync pages for.
        user_id: User who initiated the sync.
        settings: Application settings.
    """
    logger.info("Starting Notion sync for workspace %s", workspace_id)

    async with async_session() as session:
        try:
            # Update sync status
            await _update_sync_config(
                session, workspace_id, {"sync_status": "syncing"}
            )

            # Get access token
            access_token = await get_valid_access_token(
                session, workspace_id, user_id, settings
            )

            # Fetch all pages
            client = NotionClient(access_token)
            pages = await client.get_all_pages()

            page_ids: list = []

            for page_data in pages:
                notion_id = page_data.get("id", "")
                title = _extract_title(page_data)
                page_url = page_data.get("url", "")
                last_edited_by_data = page_data.get("last_edited_by", {})
                last_edited_by = last_edited_by_data.get("id", "") if last_edited_by_data else ""
                notion_created = _parse_notion_datetime(page_data.get("created_time"))
                notion_updated = _parse_notion_datetime(page_data.get("last_edited_time"))

                # Determine page type
                parent = page_data.get("parent", {})
                parent_type = parent.get("type", "")
                if parent_type == "database_id":
                    page_type = "database_entry"
                elif parent_type == "page_id":
                    page_type = "page"
                else:
                    page_type = "page"

                # Get parent ID
                parent_id = parent.get("page_id") or parent.get("database_id") or parent.get("workspace")

                # Fetch page content as markdown
                try:
                    content_md = await client.get_page_markdown(notion_id)
                except Exception:
                    logger.warning(
                        "Failed to fetch content for page %s, storing without content",
                        notion_id,
                    )
                    content_md = None

                # Upsert into notion_pages
                page_uuid = await _upsert_page(
                    session,
                    workspace_id=workspace_id,
                    notion_id=notion_id,
                    title=title,
                    content=content_md,
                    page_type=page_type,
                    parent_id=str(parent_id) if parent_id else None,
                    url=page_url,
                    last_edited_by=last_edited_by,
                    notion_created_at=notion_created,
                    notion_updated_at=notion_updated,
                    raw_data=page_data,
                )
                page_ids.append(page_uuid)

            await session.flush()

            # Queue embedding generation
            if page_ids:
                await embedding.queue_embedding_generation(
                    session, workspace_id, "notion_page", page_ids
                )

            # Update sync status to complete
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

            await session.commit()
            logger.info(
                "Notion sync complete for workspace %s: %d pages synced",
                workspace_id,
                len(page_ids),
            )

        except Exception:
            logger.exception(
                "Notion sync failed for workspace %s", workspace_id
            )
            try:
                await _update_sync_config(
                    session, workspace_id, {"sync_status": "error"}
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to update sync error status")


def _parse_notion_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string from the Notion API.

    Notion returns timestamps like '2025-06-03T05:29:00.000Z'.
    asyncpg requires actual datetime objects, not raw strings.

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
    notion_created_at: str | None,
    notion_updated_at: str | None,
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
    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "notion_id"],
        set_={
            "title": stmt.excluded.title,
            "content": stmt.excluded.content,
            "page_type": stmt.excluded.page_type,
            "parent_id": stmt.excluded.parent_id,
            "url": stmt.excluded.url,
            "last_edited_by": stmt.excluded.last_edited_by,
            "notion_created_at": stmt.excluded.notion_created_at,
            "notion_updated_at": stmt.excluded.notion_updated_at,
            "raw_data": stmt.excluded.raw_data,
        },
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
