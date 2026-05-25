"""Regression tests for FastAPI lifespan background task wiring."""

from __future__ import annotations

import ast
import asyncio
import time
from pathlib import Path


async def test_background_shutdown_wait_is_bounded(mock_settings) -> None:
    """Shutdown must not hang forever if a worker is slow to cancel."""
    from src.main import _cancel_background_tasks

    async def stubborn_worker() -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None:
                current.uncancel()
            await asyncio.sleep(60)
            raise

    task = asyncio.create_task(stubborn_worker(), name="stubborn-worker")
    await asyncio.sleep(0)
    started = time.perf_counter()

    await _cancel_background_tasks([task], timeout=0.01)

    assert time.perf_counter() - started < 0.5
    assert not task.done()

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def test_community_backfill_is_not_restart_supervised() -> None:
    """The startup-only community backfill must not run in the forever supervisor."""
    source = (Path(__file__).parents[1] / "src/main.py").read_text()
    tree = ast.parse(source)

    supervised_backfill_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_supervised":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if (
            isinstance(first_arg, ast.Constant)
            and first_arg.value == "community_backfill"
        ):
            supervised_backfill_calls.append(node)

    assert supervised_backfill_calls == []
