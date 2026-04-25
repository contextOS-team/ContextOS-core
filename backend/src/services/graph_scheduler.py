"""Nightly scheduler for knowledge-graph community rebuilds.

Runs once per workspace per night at 03:00 UTC. Also performs an on-startup
backfill: any workspace that has graph_nodes but no graph_communities row
gets rebuilt immediately (without blocking startup).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import select

from src.db import async_session
from src.models.graph_community import GraphCommunity
from src.models.graph_node import GraphNode
from src.services.graph_communities import rebuild_communities
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

NIGHTLY_HOUR_UTC = 3
INTER_WORKSPACE_PAUSE_SECONDS = 5  # gentle pacing between workspaces
OUTER_LOOP_COOLDOWN_SECONDS = 300  # if the outer loop crashes, sleep 5 min before retrying


def seconds_until_next_03_utc() -> int:
    """Seconds remaining until the next 03:00 UTC firing.

    If we're at exactly 03:00:00 UTC, returns a full 24h to avoid double-fire.
    """
    now = datetime.now(timezone.utc)
    target = now.replace(hour=NIGHTLY_HOUR_UTC, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return int((target - now).total_seconds())


async def fetch_workspaces_with_graph_nodes() -> list[UUID]:
    """Workspaces with at least one non-deleted graph_node."""
    async with async_session() as session:
        stmt = select(GraphNode.workspace_id).where(
            GraphNode.deleted_at.is_(None),
        ).distinct()
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]


async def _fetch_workspaces_with_communities() -> set[UUID]:
    """Workspaces that already have at least one graph_communities row."""
    async with async_session() as session:
        stmt = select(GraphCommunity.workspace_id).distinct()
        result = await session.execute(stmt)
        return {row[0] for row in result.fetchall()}


async def _rebuild_for_workspace(workspace_id: UUID) -> None:
    """Single-workspace rebuild with its own session and LLM client."""
    llm = get_llm_client()
    async with async_session() as session:
        await rebuild_communities(session, workspace_id, llm_client=llm)


async def backfill_missing_workspaces() -> None:
    """Run rebuild_communities for any workspace lacking a snapshot yet."""
    have_nodes = await fetch_workspaces_with_graph_nodes()
    have_snapshots = await _fetch_workspaces_with_communities()
    missing = [ws for ws in have_nodes if ws not in have_snapshots]
    logger.info("Community backfill: %d workspaces missing snapshots", len(missing))
    for ws in missing:
        try:
            await _rebuild_for_workspace(ws)
        except Exception:
            logger.exception("Backfill rebuild failed for %s", ws)


async def run_community_rebuild_loop() -> None:
    """Forever: sleep until 03:00 UTC, rebuild every workspace, repeat."""
    while True:
        try:
            await asyncio.sleep(seconds_until_next_03_utc())
            workspaces = await fetch_workspaces_with_graph_nodes()
            logger.info("Nightly community rebuild starting for %d workspaces", len(workspaces))
            for ws in workspaces:
                try:
                    await _rebuild_for_workspace(ws)
                except Exception:
                    logger.exception("Community rebuild failed for %s", ws)
                # Gentle pacing — keeps DB load and LLM concurrency in check.
                await asyncio.sleep(INTER_WORKSPACE_PAUSE_SECONDS)
        except Exception:
            logger.exception("Community scheduler outer loop error")
            await asyncio.sleep(OUTER_LOOP_COOLDOWN_SECONDS)
