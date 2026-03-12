"""Asynchronous code index worker consuming from Redis Streams.

Reads code indexing jobs from a Redis Stream and processes them.
Sync services and webhook handlers push jobs via enqueue_code_index_job()
for async decoupling. Follows the exact pattern of embedding_worker.py.

Usage:
    # From webhook handler or API endpoint:
    await enqueue_code_index_job(workspace_id, repo_full_name)

    # For full workspace re-index:
    await enqueue_workspace_index_job(workspace_id)

    # Worker process (run as background task):
    await run_code_index_worker()
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
from src.services.code_indexer import index_gitlab_workspace_repos, index_repo, index_workspace_repos
from src.services.embedding_worker import enqueue_embedding_job

logger = logging.getLogger(__name__)

STREAM_KEY = "code_index:jobs"
GROUP_NAME = "code-index-workers"
CONSUMER_NAME = f"worker-{socket.gethostname()}-{os.getpid()}"
BATCH_READ_COUNT = 5  # Fewer than embedding worker -- indexing is heavier
BLOCK_MS = 10000  # 10s block (indexing happens less frequently)


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


async def enqueue_code_index_job(
    workspace_id: UUID,
    repo_full_name: str,
) -> None:
    """Push a single-repo code index job to the Redis Stream.

    Called by webhook handlers and API endpoints for async decoupling.
    The code index worker will pick up the job and process it.

    Args:
        workspace_id: Workspace that owns the repo.
        repo_full_name: Full repo name (e.g., "org/repo").
    """
    r = _get_redis()
    try:
        payload = json.dumps({
            "workspace_id": str(workspace_id),
            "repo_full_name": repo_full_name,
        })
        await r.xadd(STREAM_KEY, {"data": payload})
        logger.info(
            "Enqueued code index job: repo=%s workspace=%s",
            repo_full_name, workspace_id,
        )
    finally:
        await r.aclose()


async def enqueue_workspace_index_job(
    workspace_id: UUID,
    provider: str = "github",
) -> None:
    """Push a full-workspace code index job to the Redis Stream.

    The worker treats repo_full_name="__all__" as a signal to call
    index_workspace_repos() instead of index_repo().

    Args:
        workspace_id: Workspace to re-index all monitored repos for.
        provider: "github" or "gitlab" (default: "github").
    """
    r = _get_redis()
    try:
        payload = json.dumps({
            "workspace_id": str(workspace_id),
            "repo_full_name": "__all__",
            "provider": provider,
        })
        await r.xadd(STREAM_KEY, {"data": payload})
        logger.info(
            "Enqueued workspace code index job: workspace=%s",
            workspace_id,
        )
    finally:
        await r.aclose()


async def _process_index_message(message_data: dict) -> None:
    """Process a single code index job from the stream.

    Parses the job, creates a DB session, calls the appropriate indexer
    (single repo or full workspace), then enqueues embedding jobs for
    all new/updated code chunks.
    """
    raw = message_data.get("data", "{}")
    try:
        job = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in code index job: %s", raw[:200])
        return

    workspace_id = UUID(job["workspace_id"])
    repo_full_name = job["repo_full_name"]
    provider = job.get("provider", "github")
    settings = get_settings()

    changed_chunk_ids: list = []

    async with async_session() as session:
        if repo_full_name == "__all__":
            if provider == "gitlab":
                results = await index_gitlab_workspace_repos(workspace_id, session, settings)
            else:
                results = await index_workspace_repos(workspace_id, session, settings)
            # Collect changed IDs from all repo results
            for r in results:
                changed_chunk_ids.extend(r.get("changed_chunk_ids", []))
            total_created = sum(r.get("chunks_created", 0) for r in results)
            total_updated = sum(r.get("chunks_updated", 0) for r in results)
            logger.info(
                "Workspace index complete: workspace=%s provider=%s repos=%d created=%d updated=%d",
                workspace_id, provider, len(results), total_created, total_updated,
            )
        else:
            result = await index_repo(workspace_id, repo_full_name, session, settings, provider=provider)
            changed_chunk_ids = result.get("changed_chunk_ids", [])
            logger.info(
                "Repo index complete: repo=%s provider=%s created=%d updated=%d deleted=%d",
                repo_full_name, provider,
                result.get("chunks_created", 0),
                result.get("chunks_updated", 0),
                result.get("chunks_deleted", 0),
            )

        await session.commit()

    # Enqueue embedding jobs only for created/updated chunks (delta-only)
    if changed_chunk_ids:
        await enqueue_embedding_job(workspace_id, "code_chunk", changed_chunk_ids)
        logger.info(
            "Enqueued %d changed chunk embeddings for workspace=%s",
            len(changed_chunk_ids), workspace_id,
        )


async def run_code_index_worker() -> None:
    """Run the code index worker loop.

    Reads from the Redis Stream consumer group, processes code indexing
    jobs, and acknowledges completed messages. Runs indefinitely.
    """
    r = _get_redis()
    await _ensure_consumer_group(r)

    logger.info("Code index worker started (stream=%s, group=%s)", STREAM_KEY, GROUP_NAME)

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
                            await _process_index_message(msg_data)
                            await r.xack(STREAM_KEY, GROUP_NAME, msg_id)
                        except Exception:
                            logger.exception(
                                "Failed to process code index job %s", msg_id
                            )

            except Exception:
                logger.exception("Code index worker loop error, retrying in 5s")
                await asyncio.sleep(5)

    finally:
        await r.aclose()
