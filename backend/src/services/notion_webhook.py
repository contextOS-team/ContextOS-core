"""Notion webhook event processor.

Handles page.content_updated events by triggering a full page re-sync
(re-fetch content + regenerate embedding). Creates its own DB session
for background task isolation.
"""

import logging
from uuid import UUID

from sqlmodel import select

from src.db import async_session
from src.models.notion import NotionPage
from src.models.user import WorkspaceMember
from src.services.graph_extractor import extract_and_populate_graph
from src.services.notion_sync import sync_page_by_id

logger = logging.getLogger(__name__)


async def process_notion_webhook_event(
    workspace_id: UUID, payload: dict
) -> None:
    """Process a Notion webhook event.

    For page.content_updated events, triggers a single-page re-sync
    which re-fetches content and regenerates the embedding. Unrecognized
    event types are logged and skipped.

    Args:
        workspace_id: Workspace that received the webhook.
        payload: Parsed JSON webhook payload from Notion.
    """
    event_type = payload.get("type", "")

    if event_type == "page.content_updated":
        # Extract page_id from payload -- Notion sends entity info
        entity = payload.get("entity", {})
        page_id = entity.get("id") or payload.get("data", {}).get("id")

        if not page_id:
            logger.warning(
                "Notion page.content_updated event missing page_id: %s",
                payload,
            )
            return

        try:
            # Look up a user_id for this workspace
            async with async_session() as session:
                stmt = select(WorkspaceMember.user_id).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
                )
                result = await session.execute(stmt)
                user_id = result.scalar_one_or_none()

            if user_id is None:
                logger.error(
                    "No workspace member found for workspace %s, cannot re-sync page",
                    workspace_id,
                )
                return

            await sync_page_by_id(workspace_id, user_id, page_id)
            logger.info("Processed Notion page update: %s", page_id)

            # Graph extraction for the synced page
            try:
                async with async_session() as graph_session:
                    stmt = select(NotionPage).where(
                        NotionPage.workspace_id == workspace_id,
                        NotionPage.notion_id == page_id,
                        NotionPage.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                    result = await graph_session.execute(stmt)
                    page = result.scalar_one_or_none()

                    if page:
                        content = f"{page.title}\n\n{page.content or ''}"
                        await extract_and_populate_graph(
                            session=graph_session,
                            workspace_id=workspace_id,
                            content=content,
                            source_type="notion_page",
                            source_id=page.id,
                            source_name=f"Notion: {page.title}",
                            source_external_id=page.notion_id,
                        )
                        await graph_session.commit()
            except Exception:
                logger.warning(
                    "Graph extraction failed for Notion page %s", page_id, exc_info=True
                )

        except Exception:
            logger.exception(
                "Failed to process Notion page.content_updated for page %s",
                page_id,
            )
    else:
        logger.info(
            "Skipping unrecognized Notion webhook event type: %s", event_type
        )
