"""Score decisions whose consequentiality gate never ran (LLM was unavailable).

Targets rows with consequentiality_score IS NULL: runs the writer's
consequentiality assessment, stores the score, and promotes 'tentative' rows
to 'active' (report semantics — imports stay visible regardless of score; low
scorers are for human review, not deletion). Appends a version row per change.

Usage:
    uv run python scripts/rescore_decisions.py            # dry run
    uv run python scripts/rescore_decisions.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import select  # noqa: E402

from src.db import async_session  # noqa: E402
from src.models.decision import Decision, DecisionVersion  # noqa: E402
from src.services.decision_writer import (  # noqa: E402
    DecisionDraft,
    _assess_consequentiality,
    _snapshot,
)

logger = logging.getLogger("rescore_decisions")


async def rescore(apply: bool) -> None:
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Decision).where(
                        Decision.consequentiality_score.is_(None),  # type: ignore[union-attr]
                        Decision.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"unscored decisions: {len(rows)}")
        if not apply:
            for d in rows:
                print(f"  would score: [{d.status}] {d.statement[:80]}")
            print("dry run — pass --apply to score")
            return

        scored = failed = 0
        for d in rows:
            draft = DecisionDraft(
                statement=d.statement, rationale=d.rationale, producer=d.producer
            )
            verdict = await _assess_consequentiality(draft, d.workspace_id)
            if verdict is None:
                failed += 1
                continue
            version = (
                await session.execute(
                    select(DecisionVersion.version)
                    .where(DecisionVersion.decision_id == d.id)
                    .order_by(DecisionVersion.version.desc())  # type: ignore[union-attr]
                    .limit(1)
                )
            ).scalar_one_or_none() or 0
            session.add(
                DecisionVersion(
                    decision_id=d.id,
                    workspace_id=d.workspace_id,
                    version=version + 1,
                    snapshot=_snapshot(d),
                    change_type="status_changed",
                    change_reason=f"rescored: consequentiality={verdict.score:.2f}",
                    actor="system:rescore",
                )
            )
            d.consequentiality_score = verdict.score
            if d.status == "tentative":
                d.status = "active"
            scored += 1
            print(f"  {verdict.score:.2f}  {d.statement[:70]}")
            await session.flush()

        await session.commit()
        print(f"scored: {scored}, llm_failures: {failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(rescore(args.apply))


if __name__ == "__main__":
    main()
