"""Asynchronous embedding worker consuming from Redis Streams.

Reads embedding jobs from a Redis Stream and processes them in batches.
Sync services push jobs via enqueue_embedding_job() instead of calling
queue_embedding_generation() directly (for async decoupling).

Usage:
    # From sync services:
    await enqueue_embedding_job(workspace_id, source_type, source_ids)

    # Worker process (run as background task or standalone):
    await run_embedding_worker()
"""

import asyncio
import json
import logging
from uuid import UUID

import redis.asyncio as aioredis

from src.config import get_settings
from src.db import async_session
from src.services.embedding import queue_embedding_generation

logger = logging.getLogger(__name__)

STREAM_KEY = "embedding:jobs"
GROUP_NAME = "embedding-workers"
CONSUMER_NAME = "worker-1"
BATCH_READ_COUNT = 10  # Number of stream messages to read at once
BLOCK_MS = 5000  # Block for 5s waiting for new messages


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


async def enqueue_embedding_job(
    workspace_id: UUID,
    source_type: str,
    source_ids: list[UUID],
) -> None:
    """Push an embedding job to the Redis Stream.

    Called by sync services instead of queue_embedding_generation()
    for async decoupling. The embedding worker will pick up the job
    and process it asynchronously.

    Args:
        workspace_id: Workspace the sources belong to.
        source_type: Type of source (e.g. 'notion_page').
        source_ids: List of source record UUIDs.
    """
    if not source_ids:
        return

    r = _get_redis()
    try:
        payload = json.dumps({
            "workspace_id": str(workspace_id),
            "source_type": source_type,
            "source_ids": [str(sid) for sid in source_ids],
        })
        await r.xadd(STREAM_KEY, {"data": payload})
        logger.info(
            "Enqueued embedding job: type=%s count=%d workspace=%s",
            source_type, len(source_ids), workspace_id,
        )
    finally:
        await r.aclose()


async def _process_message(message_data: dict) -> None:
    """Process a single embedding job from the stream."""
    raw = message_data.get("data", "{}")
    try:
        job = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in embedding job: %s", raw[:200])
        return

    workspace_id = UUID(job["workspace_id"])
    source_type = job["source_type"]
    source_ids = [UUID(sid) for sid in job["source_ids"]]

    async with async_session() as session:
        await queue_embedding_generation(
            session, workspace_id, source_type, source_ids
        )
        await session.commit()


async def run_embedding_worker() -> None:
    """Run the embedding worker loop.

    Reads from the Redis Stream consumer group, processes embedding
    jobs, and acknowledges completed messages. Runs indefinitely.
    """
    r = _get_redis()
    await _ensure_consumer_group(r)

    logger.info("Embedding worker started (stream=%s, group=%s)", STREAM_KEY, GROUP_NAME)

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
                            await _process_message(msg_data)
                            await r.xack(STREAM_KEY, GROUP_NAME, msg_id)
                        except Exception:
                            logger.exception(
                                "Failed to process embedding job %s", msg_id
                            )

            except Exception:
                logger.exception("Embedding worker loop error, retrying in 5s")
                await asyncio.sleep(5)

    finally:
        await r.aclose()
