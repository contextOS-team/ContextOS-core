"""Run a Decision Drift scan: infer -> check -> verify -> drift.

Usage:
    uv run python scripts/run_drift_scan.py                      # all workspaces
    uv run python scripts/run_drift_scan.py --workspace-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text  # noqa: E402

from src.db import async_session  # noqa: E402
from src.services.drift_engine import scan_workspace_for_drift  # noqa: E402


async def run(workspace_id: UUID | None) -> None:
    async with async_session() as session:
        if workspace_id is not None:
            workspace_ids = [workspace_id]
        else:
            rows = await session.execute(
                sa_text(
                    "SELECT id FROM workspaces WHERE deleted_at IS NULL"
                    " ORDER BY created_at"
                )
            )
            workspace_ids = [row[0] for row in rows.fetchall()]

        for ws in workspace_ids:
            stats = await scan_workspace_for_drift(session, ws)
            await session.commit()
            print(
                f"workspace {ws}: inferred={stats.decisions_inferred} "
                f"consequences={stats.consequences_created} "
                f"checked={stats.consequences_checked} "
                f"inconsistent={stats.inconsistent_found} "
                f"killed={stats.killed_by_verifier} "
                f"drifts={stats.drifts_created}"
            )
            for reason in stats.kill_reasons:
                print(f"  kill: {reason[:100]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=UUID, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(run(args.workspace_id))


if __name__ == "__main__":
    main()
