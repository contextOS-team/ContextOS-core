"""Polling fallback scheduler for catching missed webhook events.

Runs reconciliation checks every 15 minutes for all connected providers
to catch webhook deliveries that were lost or failed.

Per CONTEXT.md: Webhook-first with polling fallback for all providers
that support webhooks (Notion, GitHub, Linear).
"""

import asyncio
import logging
from uuid import UUID

from sqlmodel import select

from src.db import async_session
from src.models.integration import Provider, WorkspaceIntegration
from src.services.sync_adapter import SyncRunLogger

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60  # 15 minutes per CONTEXT.md decision


async def _get_connected_workspaces(provider: Provider) -> list[UUID]:
    """Get all workspace IDs with a connected integration for the given provider."""
    async with async_session() as session:
        stmt = select(WorkspaceIntegration.workspace_id).where(
            WorkspaceIntegration.provider == provider,
            WorkspaceIntegration.status == "connected",
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]


async def reconcile_notion(workspace_id: UUID) -> None:
    """Polling fallback for Notion: check for pages updated since last sync.

    Fetches the search API and compares last_edited_time against stored
    notion_updated_at to find pages that changed but didn't trigger a webhook.
    """
    from src.services.notion_oauth import get_valid_access_token
    from src.services.notion_client import NotionClient
    from src.services.notion_sync import sync_single_page
    from src.services.embedding_worker import enqueue_embedding_job
    import src.config as config_module

    settings = config_module.get_settings()

    async with SyncRunLogger("notion", workspace_id) as srl:
        try:
            async with async_session() as session:
                # Get any user_id for this workspace
                from src.models.user import WorkspaceMember

                stmt = (
                    select(WorkspaceMember.user_id)
                    .where(
                        WorkspaceMember.workspace_id == workspace_id,
                        WorkspaceMember.deleted_at.is_(None),
                    )
                    .limit(1)
                )
                result = await session.execute(stmt)
                user_id = result.scalar_one_or_none()

                if user_id is None:
                    srl.warning("No active user found for workspace, skipping reconcile")
                    return

                access_token = await get_valid_access_token(
                    session, workspace_id, user_id, settings
                )

            async with NotionClient(access_token) as client:
                # Fetch recent pages (just first page of search results)
                response = await client.search_pages(page_size=100)
                pages = response.get("results", [])

                updated_count = 0
                async with async_session() as session:
                    from src.models.notion import NotionPage
                    from sqlmodel import select as sm_select

                    for page_data in pages:
                        notion_id = page_data.get("id", "")
                        notion_last_edited = page_data.get("last_edited_time")

                        # Check if we need to re-sync this page
                        check_stmt = sm_select(NotionPage.notion_updated_at).where(
                            NotionPage.workspace_id == workspace_id,
                            NotionPage.notion_id == notion_id,
                        )
                        check_result = await session.execute(check_stmt)
                        stored_updated = check_result.scalar_one_or_none()

                        if notion_last_edited and stored_updated:
                            from src.routers.notion import _parse_notion_datetime

                            new_updated = _parse_notion_datetime(notion_last_edited)
                            if new_updated and stored_updated >= new_updated:
                                continue  # Up to date

                        # Page needs re-sync
                        page_record = await sync_single_page(
                            session, client, workspace_id, page_data
                        )
                        await enqueue_embedding_job(
                            workspace_id, "notion_page", [page_record.id]
                        )
                        updated_count += 1

                    if updated_count > 0:
                        await session.commit()
                        srl.info("Reconciled %d Notion pages" % updated_count)
                    else:
                        srl.info("No Notion pages need reconciliation")

        except Exception:
            srl.exception("Notion reconciliation failed")


async def run_polling_fallback() -> None:
    """Run the polling fallback loop indefinitely.

    Checks all connected providers every 15 minutes for missed webhook
    events. Designed to be started as a background task on application startup.
    """
    logger.info("Polling fallback scheduler started (interval=%ds)", POLL_INTERVAL_SECONDS)

    while True:
        try:
            # Notion reconciliation
            notion_workspaces = await _get_connected_workspaces(Provider.NOTION)
            for ws_id in notion_workspaces:
                try:
                    await reconcile_notion(ws_id)
                except Exception:
                    logger.exception(
                        "Notion reconciliation failed for workspace %s", ws_id
                    )

            # Linear and GitHub reconciliation stubs
            # (can be implemented when those providers have
            # incremental sync support via updatedAt filters)

        except Exception:
            logger.exception("Polling fallback scheduler error")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
