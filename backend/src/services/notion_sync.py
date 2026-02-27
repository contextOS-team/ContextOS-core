"""Notion page sync orchestration.

Handles initial full-sync backfill and individual page re-sync for
webhook-triggered updates. Creates its own DB session for background
task isolation (same pattern as linear_webhook.py, slack_events.py).
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import async_session
from src.models.integration import Provider, WorkspaceIntegration
from src.models.notion import NotionPage
from src.services import embedding
from src.services.notion_client import NotionClient
from src.services.notion_oauth import get_valid_access_token

import src.config as config_module

logger = logging.getLogger(__name__)


def _extract_title(properties: dict) -> str:
    """Extract the page title from Notion page properties.

    Notion pages store titles in the 'properties' dict. The title property
    can have various names but is always of type 'title'. Iterates all
    properties to find the one with type 'title'.

    Args:
        properties: Properties dict from the Notion page API response.

    Returns:
        Page title string, or 'Untitled' if not found.
    """
    for prop in properties.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if title_parts:
                return "".join(
                    item.get("plain_text", "") for item in title_parts
                )
    return "Untitled"


async def sync_single_page(
    session: AsyncSession,
    client: NotionClient,
    workspace_id: UUID,
    page_data: dict,
) -> NotionPage:
    """Sync a single Notion page: extract metadata, fetch markdown, upsert.

    Extracts page metadata from the Notion API response, fetches full page
    content as markdown via the client, and upserts into the notion_pages table
    using PostgreSQL ON CONFLICT.

    Args:
        session: Async database session.
        client: Authenticated NotionClient instance.
        workspace_id: Workspace to associate the page with.
        page_data: Raw Notion page API response dict.

    Returns:
        The upserted NotionPage record (with id populated).
    """
    notion_id = page_data.get("id", "")
    properties = page_data.get("properties", {})
    title = _extract_title(properties)
    page_url = page_data.get("url", "")
    last_edited_by_data = page_data.get("last_edited_by", {})
    last_edited_by = last_edited_by_data.get("id", "") if last_edited_by_data else ""
    notion_created = page_data.get("created_time")
    notion_updated = page_data.get("last_edited_time")

    # Determine page type from parent
    parent = page_data.get("parent", {})
    parent_type = parent.get("type", "")
    if parent_type == "database_id":
        page_type = "database_entry"
    else:
        page_type = "page"

    # Get parent ID
    parent_id = (
        parent.get("page_id")
        or parent.get("database_id")
        or parent.get("workspace")
    )

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
    values = {
        "workspace_id": workspace_id,
        "notion_id": notion_id,
        "title": title,
        "content": content_md,
        "page_type": page_type,
        "parent_id": str(parent_id) if parent_id else None,
        "url": page_url,
        "last_edited_by": last_edited_by,
        "notion_created_at": notion_created,
        "notion_updated_at": notion_updated,
        "raw_data": page_data,
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
    page_uuid = result.scalar_one()

    # Build a lightweight NotionPage-like object with the id for callers
    page = NotionPage(
        id=page_uuid,
        workspace_id=workspace_id,
        notion_id=notion_id,
        title=title,
    )
    return page


async def run_full_sync(workspace_id: UUID, user_id: UUID) -> None:
    """Background task: full sync of all Notion pages for a workspace.

    Creates its own session for background task isolation. Fetches all
    pages via the Notion search API, upserts each into the database,
    and queues embedding generation for all synced pages.

    Updates integration config with sync progress and status.

    Args:
        workspace_id: Workspace to sync pages for.
        user_id: User who initiated the sync.
    """
    settings = config_module.get_settings()
    logger.info("Starting Notion full sync for workspace %s", workspace_id)

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

            await _update_sync_config(
                session,
                workspace_id,
                {"sync_status": "syncing", "pages_total": len(pages)},
            )

            page_ids: list[UUID] = []
            synced_count = 0

            for page_data in pages:
                page_record = await sync_single_page(
                    session, client, workspace_id, page_data
                )
                page_ids.append(page_record.id)
                synced_count += 1

            await session.flush()

            # Queue embedding generation for all synced pages
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
                    "pages_synced": synced_count,
                },
            )

            await session.commit()
            logger.info(
                "Notion full sync complete for workspace %s: %d pages synced",
                workspace_id,
                synced_count,
            )

        except Exception:
            logger.exception(
                "Notion full sync failed for workspace %s", workspace_id
            )
            try:
                await _update_sync_config(
                    session,
                    workspace_id,
                    {"sync_status": "error", "sync_error": "sync failed"},
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to update sync error status")


async def sync_page_by_id(
    workspace_id: UUID, user_id: UUID, notion_page_id: str
) -> None:
    """Re-sync a single Notion page by its Notion ID.

    Creates its own session for background task isolation. Fetches the
    page metadata, calls sync_single_page, and queues embedding
    regeneration for the updated page. Used by the webhook handler
    for individual page re-sync on content updates.

    Args:
        workspace_id: Workspace the page belongs to.
        user_id: User whose token to use for API access.
        notion_page_id: Notion page UUID to re-sync.
    """
    settings = config_module.get_settings()
    logger.info(
        "Re-syncing Notion page %s for workspace %s",
        notion_page_id,
        workspace_id,
    )

    async with async_session() as session:
        try:
            # Get access token
            access_token = await get_valid_access_token(
                session, workspace_id, user_id, settings
            )

            # Fetch page metadata
            client = NotionClient(access_token)
            page_data = await client.get_page(notion_page_id)

            # Sync the page
            page_record = await sync_single_page(
                session, client, workspace_id, page_data
            )

            # Queue embedding regeneration for this page
            await embedding.queue_embedding_generation(
                session, workspace_id, "notion_page", [page_record.id]
            )

            await session.commit()
            logger.info(
                "Re-sync complete for Notion page %s (db id=%s)",
                notion_page_id,
                page_record.id,
            )

        except Exception:
            logger.exception(
                "Failed to re-sync Notion page %s for workspace %s",
                notion_page_id,
                workspace_id,
            )


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
