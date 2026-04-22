"""Polling fallback scheduler for catching missed webhook events.

Runs reconciliation checks every 15 minutes for all connected providers
to catch webhook deliveries that were lost or failed. Also runs periodic
code re-indexing every 60 minutes as a freshness fallback. Emits daily
message digests for messaging integrations (Slack, Telegram).

Per CONTEXT.md: Webhook-first with polling fallback for all providers
that support webhooks (Notion, GitHub, Linear).
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from datetime import timedelta

from sqlalchemy import update
from sqlmodel import select

from src.db import async_session
from src.models.context_page import ContextPage
from src.models.integration import Provider, WorkspaceIntegration
from src.services.slack_messages import poll_user_messages
from src.services.sync_adapter import SyncRunLogger

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60  # 15 minutes per CONTEXT.md decision
CODE_INDEX_INTERVAL_SECONDS = 60 * 60  # 60 minutes for code re-indexing
STALE_GENERATION_MINUTES = 5  # Pages stuck in "generating" longer than this are marked as error


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
                            from src.utils.datetime import parse_notion_datetime

                            new_updated = parse_notion_datetime(notion_last_edited)
                            # Normalize to naive UTC for comparison
                            cmp_stored = stored_updated
                            if cmp_stored.tzinfo is not None:
                                cmp_stored = cmp_stored.replace(tzinfo=None)
                            if new_updated and cmp_stored >= new_updated:
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


async def _check_code_index_freshness(workspace_id: UUID) -> None:
    """Check if code index needs re-indexing based on last indexed timestamp.

    If the last code index was more than CODE_INDEX_INTERVAL_SECONDS ago
    (or never indexed), enqueue a full workspace code index job.
    """
    from src.services.code_index_worker import enqueue_workspace_index_job

    async with async_session() as session:
        stmt = select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.provider == Provider.GITHUB,
            WorkspaceIntegration.status == "connected",
        )
        result = await session.execute(stmt)
        integration = result.scalar_one_or_none()

        if not integration or not integration.config:
            return

        config = integration.config

        # Skip if already indexing to prevent duplicate queue storms
        if config.get("code_index_status") == "indexing":
            logger.debug(
                "Skipping code index for workspace %s: already indexing", workspace_id
            )
            return

        code_index_last = config.get("code_index_last_at")
        now = datetime.now(timezone.utc)

        if code_index_last:
            try:
                last_dt = datetime.fromisoformat(code_index_last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                elapsed = (now - last_dt).total_seconds()
                if elapsed < CODE_INDEX_INTERVAL_SECONDS:
                    return  # Still fresh
            except (ValueError, TypeError):
                pass  # Invalid timestamp, re-index

        await enqueue_workspace_index_job(workspace_id)
        logger.info(
            "Polling fallback: enqueued code re-index for workspace %s",
            workspace_id,
        )


async def _expire_stale_generations() -> None:
    """Mark context pages stuck in 'generating' for too long as 'error'.

    If a generation crashes without updating status, the page stays in
    'generating' forever — blocking regeneration and showing incorrect
    status in the feed.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_GENERATION_MINUTES)
    async with async_session() as session:
        stmt = (
            update(ContextPage)
            .where(
                ContextPage.status == "generating",
                ContextPage.updated_at < cutoff,
                ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .values(status="error")
        )
        result = await session.execute(stmt)
        if result.rowcount:  # type: ignore[union-attr]
            logger.info("Expired %d stale generating context pages", result.rowcount)
        await session.commit()


async def _emit_daily_digest(workspace_id: UUID, integration: str) -> None:
    """Generate and emit an LLM-powered daily digest for a messaging integration.

    Deduplication is handled inside generate_digest (20h cooldown), so this
    can safely be called every polling cycle — it will no-op if a recent
    digest already exists.
    """
    from src.services.digest import generate_digest

    async with async_session() as session:
        result = await generate_digest(session, workspace_id, integration)
        if result:
            await session.commit()
            logger.info(
                "%s daily digest: %d messages for workspace %s",
                integration.capitalize(), result["message_count"], workspace_id,
            )


async def run_polling_fallback() -> None:
    """Run the polling fallback loop indefinitely.

    Checks all connected providers every 15 minutes for missed webhook
    events. Designed to be started as a background task on application startup.
    """
    logger.info("Polling fallback scheduler started (interval=%ds)", POLL_INTERVAL_SECONDS)

    # Expire stale generations immediately on startup
    try:
        await _expire_stale_generations()
    except Exception:
        logger.exception("Initial stale generation cleanup failed")

    while True:
        try:
            # Expire stale context page generations
            await _expire_stale_generations()

            # Notion reconciliation
            notion_workspaces = await _get_connected_workspaces(Provider.NOTION)
            for ws_id in notion_workspaces:
                try:
                    await reconcile_notion(ws_id)
                except Exception:
                    logger.exception(
                        "Notion reconciliation failed for workspace %s", ws_id
                    )

            # GitHub code index freshness check (every 60 min)
            github_workspaces = await _get_connected_workspaces(Provider.GITHUB)
            for ws_id in github_workspaces:
                try:
                    await _check_code_index_freshness(ws_id)
                except Exception:
                    logger.exception(
                        "Code index freshness check failed for workspace %s", ws_id
                    )

            # Slack DM polling (user-token) per Phase 39. Channels still use
            # the bot Events API webhook path — this only covers im/mpim.
            slack_workspaces = await _get_connected_workspaces(Provider.SLACK)
            for ws_id in slack_workspaces:
                try:
                    async with async_session() as session:
                        result = await poll_user_messages(session, ws_id)
                    if result.get("reason") is None and result.get("ingested", 0) > 0:
                        logger.info(
                            "Slack DM poll for workspace %s: ingested=%d skipped=%d",
                            ws_id,
                            result["ingested"],
                            result["skipped"],
                        )
                    elif result.get("reason") not in (None, "dms_disabled"):
                        logger.warning(
                            "Slack DM poll for workspace %s reason=%s",
                            ws_id,
                            result["reason"],
                        )
                except Exception:
                    logger.exception(
                        "Slack DM poll crashed for workspace %s", ws_id
                    )

            # Daily digests for messaging integrations (dedup handled inside generate_digest)
            for provider, integration_name in [
                (Provider.SLACK, "slack"),
                (Provider.TELEGRAM, "telegram"),
            ]:
                workspaces = await _get_connected_workspaces(provider)
                for ws_id in workspaces:
                    try:
                        await _emit_daily_digest(ws_id, integration_name)
                    except Exception:
                        logger.exception(
                            "%s daily digest failed for workspace %s",
                            integration_name.capitalize(), ws_id,
                        )

            # Linear reconciliation stub
            # (can be implemented when Linear has incremental sync
            # support via updatedAt filters)

        except Exception:
            logger.exception("Polling fallback scheduler error")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
