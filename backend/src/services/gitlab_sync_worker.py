"""Asynchronous GitLab MR sync worker consuming from Redis Streams.

Reads MR sync jobs from a Redis Stream and processes them.
API endpoints and auto-triggers push jobs via enqueue_gitlab_sync_job()
for async decoupling and crash resilience.

Usage:
    # From API endpoint or auto-trigger on repo selection:
    await enqueue_gitlab_sync_job(workspace_id, project_ids)

    # Worker process (run as background task):
    await run_gitlab_sync_worker()
"""

import asyncio
import json
import logging
import os
import socket
from uuid import UUID

import redis.asyncio as aioredis

from src.config import get_settings
from src.db import async_session

logger = logging.getLogger(__name__)

STREAM_KEY = "gitlab_sync:jobs"
GROUP_NAME = "gitlab-sync-workers"
CONSUMER_NAME = f"worker-{socket.gethostname()}-{os.getpid()}"
BATCH_READ_COUNT = 1  # One sync at a time -- heavy API + DB workload
BLOCK_MS = 10000  # 10s block


def _get_redis() -> aioredis.Redis:
    """Create a Redis async client from settings."""
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def _ensure_consumer_group(r: aioredis.Redis) -> None:
    """Create the consumer group if it doesn't exist."""
    try:
        await r.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def enqueue_gitlab_sync_job(
    workspace_id: UUID,
    project_ids: list[int],
    state_filter: str = "all",
) -> None:
    """Push a GitLab MR sync job to the Redis Stream.

    Args:
        workspace_id: Workspace to sync MRs for.
        project_ids: List of numeric GitLab project IDs to sync.
        state_filter: MR state filter (all, opened, closed, merged).
    """
    r = _get_redis()
    try:
        payload = json.dumps({
            "workspace_id": str(workspace_id),
            "project_ids": project_ids,
            "state_filter": state_filter,
        })
        await r.xadd(STREAM_KEY, {"data": payload})
        logger.info(
            "Enqueued GitLab sync job: workspace=%s projects=%d",
            workspace_id, len(project_ids),
        )
    finally:
        await r.aclose()


async def _process_sync_message(message_data: dict) -> None:
    """Process a single GitLab MR sync job from the stream."""
    from src.services.gitlab_sync import sync_projects

    raw = message_data.get("data", "{}")
    try:
        job = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in GitLab sync job: %s", raw[:200])
        return

    workspace_id = UUID(job["workspace_id"])
    project_ids = job["project_ids"]
    state_filter = job.get("state_filter", "all")
    settings = get_settings()

    async with async_session() as session:
        result = await sync_projects(
            workspace_id, project_ids, session, settings,
            state_filter=state_filter,
        )

    logger.info(
        "GitLab sync complete: workspace=%s mrs=%d reviews=%d",
        workspace_id,
        result.get("total_mrs", 0),
        result.get("total_reviews", 0),
    )


async def run_gitlab_sync_worker() -> None:
    """Run the GitLab MR sync worker loop.

    Reads from the Redis Stream consumer group, processes sync
    jobs, and acknowledges completed messages. Runs indefinitely.
    """
    r = _get_redis()
    await _ensure_consumer_group(r)

    logger.info("GitLab sync worker started (stream=%s, group=%s)", STREAM_KEY, GROUP_NAME)

    try:
        while True:
            try:
                messages = await r.xreadgroup(
                    GROUP_NAME,
                    CONSUMER_NAME,
                    {STREAM_KEY: ">"},
                    count=BATCH_READ_COUNT,
                    block=BLOCK_MS,
                )

                if not messages:
                    continue

                for stream_name, entries in messages:
                    for msg_id, msg_data in entries:
                        try:
                            await _process_sync_message(msg_data)
                            await r.xack(STREAM_KEY, GROUP_NAME, msg_id)
                        except Exception:
                            logger.exception(
                                "Failed to process GitLab sync job %s", msg_id
                            )

            except Exception:
                logger.exception("GitLab sync worker loop error, retrying in 5s")
                await asyncio.sleep(5)

    finally:
        await r.aclose()
