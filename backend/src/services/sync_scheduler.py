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
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import update
from sqlmodel import select

from src.config import get_settings
from src.db import async_session
from src.models.context_page import ContextPage
from src.models.integration import Provider, WorkspaceIntegration
from src.models.missed_decision import MissedDecisionScanRun, MissedDecisionScanState
from src.models.telegram import TelegramChatWorkspace
from src.services.missed_decision_scanner import (
    SCAN_STATUS_QUEUED,
    SCAN_STATUS_RUNNING,
    STALE_RUNNING_SCAN_AFTER,
    drain_queued_missed_decision_scans,
    enqueue_missed_decision_scan,
)
from src.services.slack_messages import poll_user_messages
from src.services.sync_adapter import SyncRunLogger

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60  # 15 minutes per CONTEXT.md decision
CODE_INDEX_INTERVAL_SECONDS = 60 * 60  # 60 minutes for code re-indexing
# Pages stuck in "generating" longer than this are marked as error.
STALE_GENERATION_MINUTES = 5
MISSED_DECISION_BACKSTOP_INTERVAL = timedelta(days=1)
MISSED_DECISION_BACKSTOP_SOURCES = {
    Provider.NOTION: "notion_page",
    Provider.SLACK: "slack_message",
    Provider.TELEGRAM: "telegram_message",
    Provider.FATHOM: "fathom_transcript",
}

# Daily digest gate
# ---------------------------------------------------------------------
# generate_digest()'s internal _has_recent_digest is a non-locking SELECT,
# so two workers running it concurrently would both pass dedup and emit
# duplicate activity events. We use a Redis SET NX EX lock here so only
# one worker per (workspace, integration) enters the function per ~23h
# window. SET NX is atomic across workers; this is also the dedup gate
# that saves the wasted DB round-trips on every poll cycle.
DIGEST_LOCK_TTL_SECONDS = 23 * 60 * 60
_DIGEST_LOCK_KEY_PREFIX = "digest:lock:"

_redis_client: aioredis.Redis | None = None
_DIGEST_REDIS_RETRY_COOLDOWN_SECONDS = 30.0
_redis_retry_after: float = 0.0


async def _get_redis() -> aioredis.Redis | None:
    """Lazy Redis connection for digest locks. None if unreachable (with cooldown)."""
    global _redis_client, _redis_retry_after
    if _redis_client is not None:
        return _redis_client
    now = monotonic()
    if now < _redis_retry_after:
        return None
    try:
        settings = get_settings()
        if not settings.REDIS_URL:
            _redis_retry_after = now + _DIGEST_REDIS_RETRY_COOLDOWN_SECONDS
            return None
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        logger.warning("digest_redis_connect_failed", exc_info=True)
        _redis_retry_after = now + _DIGEST_REDIS_RETRY_COOLDOWN_SECONDS
        return None


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
    import src.config as config_module
    from src.services.embedding_worker import enqueue_embedding_job
    from src.services.notion_client import NotionClient
    from src.services.notion_oauth import get_valid_access_token
    from src.services.notion_sync import sync_single_page

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
                    srl.warning(
                        "No active user found for workspace, skipping reconcile"
                    )
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
                    from sqlmodel import select as sm_select

                    from src.models.notion import NotionPage

                    notion_ids = [p.get("id", "") for p in pages if p.get("id")]
                    stored_map: dict[str, object] = {}
                    if notion_ids:
                        prefetch_stmt = sm_select(
                            NotionPage.notion_id, NotionPage.notion_updated_at
                        ).where(
                            NotionPage.workspace_id == workspace_id,
                            NotionPage.notion_id.in_(notion_ids),  # type: ignore[attr-defined]
                        )
                        prefetch_result = await session.execute(prefetch_stmt)
                        stored_map = {
                            row[0]: row[1] for row in prefetch_result.fetchall()
                        }

                    for page_data in pages:
                        notion_id = page_data.get("id", "")
                        notion_last_edited = page_data.get("last_edited_time")

                        stored_updated = stored_map.get(notion_id)

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
                        srl.info(f"Reconciled {updated_count} Notion pages")
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
        now = datetime.now(UTC)

        if code_index_last:
            try:
                last_dt = datetime.fromisoformat(code_index_last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=UTC)
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
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        minutes=STALE_GENERATION_MINUTES
    )
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

    generate_digest() has its own DB-based dedup, but it costs ~9 round-trips
    per workspace per cycle and is non-locking, so concurrent workers would
    both pass it. We gate the call with a Redis SET NX EX lock so only one
    worker per (workspace, integration) enters the function per 23h window.
    If Redis is unavailable we fall through and rely on the DB dedup —
    worst case is the prior behavior (a wasted check, possibly a duplicate
    digest under high concurrency).
    """
    from src.services.digest import generate_digest

    redis = await _get_redis()
    lock_key = f"{_DIGEST_LOCK_KEY_PREFIX}{workspace_id}:{integration}"
    if redis is not None:
        try:
            acquired = await redis.set(
                lock_key, "1", nx=True, ex=DIGEST_LOCK_TTL_SECONDS
            )
        except Exception:
            logger.warning("digest_lock_acquire_failed", exc_info=True)
            acquired = True  # fail open: let DB dedup take over
        if not acquired:
            return  # Another worker (or earlier run) holds the lock; skip cleanly.

    async with async_session() as session:
        try:
            result = await generate_digest(session, workspace_id, integration)
        except Exception:
            # Release on EXCEPTION only so a transient failure doesn't lock
            # out for 23h. We deliberately do NOT release on a None return:
            # generate_digest returns None both when its DB-based dedup tripped
            # (a digest was already emitted recently) and when there were no
            # messages to digest. In both cases the right answer is to keep
            # the lock held — releasing would just have the next 15-minute
            # poll cycle re-run the same wasted check.
            if redis is not None:
                try:
                    await redis.delete(lock_key)
                except Exception:
                    pass
            raise

        if result:
            await enqueue_missed_decision_scan(
                session,
                workspace_id,
                f"{integration}_message",
            )
            await session.commit()
            logger.info(
                "%s daily digest: %d messages for workspace %s",
                integration.capitalize(),
                result["message_count"],
                workspace_id,
            )


async def _drain_missed_decision_scans() -> None:
    async with async_session() as session:
        processed = await drain_queued_missed_decision_scans(session)
        if processed:
            await session.commit()
            logger.info(
                "Drained %d missed-decision scan run(s)",
                processed,
            )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def _has_active_missed_decision_scan(
    session,
    workspace_id: UUID,
    source_type: str,
) -> bool:
    stale_started_before = datetime.now(UTC) - STALE_RUNNING_SCAN_AFTER
    stmt = (
        select(MissedDecisionScanRun)
        .where(
            MissedDecisionScanRun.workspace_id == workspace_id,
            MissedDecisionScanRun.source_type == source_type,
            (
                (MissedDecisionScanRun.status == SCAN_STATUS_QUEUED)
                | (
                    (MissedDecisionScanRun.status == SCAN_STATUS_RUNNING)
                    & (
                        (MissedDecisionScanRun.started_at.is_(None))  # type: ignore[union-attr]
                        | (MissedDecisionScanRun.started_at >= stale_started_before)
                    )
                )
            ),
            MissedDecisionScanRun.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _missed_decision_backstop_due(
    session,
    workspace_id: UUID,
    source_type: str,
    now: datetime,
) -> bool:
    stmt = select(MissedDecisionScanState).where(
        MissedDecisionScanState.workspace_id == workspace_id,
        MissedDecisionScanState.source_type == source_type,
        MissedDecisionScanState.source_resource_id.is_(None),  # type: ignore[union-attr]
        MissedDecisionScanState.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    state = result.scalar_one_or_none()
    if state is not None and state.last_missed_decision_scan_at is not None:
        last_scan_at = _aware_utc(state.last_missed_decision_scan_at)
        if now - last_scan_at < MISSED_DECISION_BACKSTOP_INTERVAL:
            return False
    return not await _has_active_missed_decision_scan(
        session,
        workspace_id,
        source_type,
    )


async def _enqueue_missed_decision_backstop(
    workspaces_by_provider: dict[Provider, list[UUID]],
    *,
    now: datetime | None = None,
) -> int:
    """Queue stale safety scans for connected sources when event enqueue was missed."""
    completed_at = now or datetime.now(UTC)
    enqueued = 0
    async with async_session() as session:
        for provider, source_type in MISSED_DECISION_BACKSTOP_SOURCES.items():
            for workspace_id in workspaces_by_provider.get(provider, []):
                if not await _missed_decision_backstop_due(
                    session,
                    workspace_id,
                    source_type,
                    completed_at,
                ):
                    continue
                run = await enqueue_missed_decision_scan(
                    session,
                    workspace_id,
                    source_type,
                    sync_completed_at=completed_at,
                )
                if run is not None:
                    enqueued += 1
        if enqueued:
            await session.commit()
            logger.info(
                "Queued %d missed-decision backstop scan(s)",
                enqueued,
            )
    return enqueued


async def _run_polling_cycle() -> None:
    try:
        # Expire stale context page generations
        await _expire_stale_generations()

        # Single batched query for all connected workspaces grouped by
        # provider — avoids 4× sequential round-trips to Supabase.
        polled_providers = [
            Provider.NOTION,
            Provider.GITHUB,
            Provider.SLACK,
            Provider.TELEGRAM,
            Provider.FATHOM,
        ]
        workspaces_by_provider: dict[Provider, list[UUID]] = {
            p: [] for p in polled_providers
        }
        async with async_session() as session:
            stmt = select(
                WorkspaceIntegration.workspace_id,
                WorkspaceIntegration.provider,
            ).where(
                WorkspaceIntegration.status == "connected",
                WorkspaceIntegration.provider.in_(polled_providers),  # type: ignore[attr-defined]
            )
            result = await session.execute(stmt)
            for ws_id, provider in result.fetchall():
                workspaces_by_provider.setdefault(provider, []).append(ws_id)

            tg_stmt = (
                select(TelegramChatWorkspace.workspace_id)
                .where(TelegramChatWorkspace.removed_at.is_(None))  # type: ignore[union-attr]
                .distinct()
            )
            tg_result = await session.execute(tg_stmt)
            telegram_workspaces = workspaces_by_provider.setdefault(
                Provider.TELEGRAM,
                [],
            )
            for (ws_id,) in tg_result.fetchall():
                if ws_id not in telegram_workspaces:
                    telegram_workspaces.append(ws_id)

        # Missed-decision scan backstops must not wait behind provider polling.
        # Slack history polling can spend minutes in rate-limit sleeps; enqueue
        # stale/missing scans first so review candidates are not starved by API
        # catch-up work.
        await _enqueue_missed_decision_backstop(workspaces_by_provider)
        try:
            await _drain_missed_decision_scans()
        except Exception:
            logger.exception("Missed-decision scan drain failed")

        # Notion reconciliation
        notion_workspaces = workspaces_by_provider.get(Provider.NOTION, [])
        for ws_id in notion_workspaces:
            try:
                await reconcile_notion(ws_id)
            except Exception:
                logger.exception("Notion reconciliation failed for workspace %s", ws_id)

        # GitHub code index freshness check (every 60 min)
        github_workspaces = workspaces_by_provider.get(Provider.GITHUB, [])
        for ws_id in github_workspaces:
            try:
                await _check_code_index_freshness(ws_id)
            except Exception:
                logger.exception(
                    "Code index freshness check failed for workspace %s", ws_id
                )

        # Slack user-token polling covers DMs, group DMs, and readable channels.
        # The Events API path is still idempotent for future message delivery.
        slack_workspaces = workspaces_by_provider.get(Provider.SLACK, [])
        for ws_id in slack_workspaces:
            try:
                async with async_session() as session:
                    result = await poll_user_messages(session, ws_id)
                    if result.get("reason") is None and result.get("ingested", 0) > 0:
                        await enqueue_missed_decision_scan(
                            session,
                            ws_id,
                            "slack_message",
                        )
                        await session.commit()
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
                logger.exception("Slack DM poll crashed for workspace %s", ws_id)

        # Daily digests for messaging integrations.
        # Dedup is handled inside generate_digest.
        for provider, integration_name in [
            (Provider.SLACK, "slack"),
            (Provider.TELEGRAM, "telegram"),
        ]:
            workspaces = workspaces_by_provider.get(provider, [])
            for ws_id in workspaces:
                try:
                    await _emit_daily_digest(ws_id, integration_name)
                except Exception:
                    logger.exception(
                        "%s daily digest failed for workspace %s",
                        integration_name.capitalize(),
                        ws_id,
                    )

    except Exception:
        logger.exception("Polling fallback scheduler error")


async def run_polling_fallback() -> None:
    """Run the polling fallback loop indefinitely.

    Checks all connected providers every 15 minutes for missed webhook
    events. Designed to be started as a background task on application startup.
    """
    logger.info(
        "Polling fallback scheduler started (interval=%ds)",
        POLL_INTERVAL_SECONDS,
    )

    # Expire stale generations immediately on startup
    try:
        await _expire_stale_generations()
    except Exception:
        logger.exception("Initial stale generation cleanup failed")

    while True:
        await _run_polling_cycle()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
