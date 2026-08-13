"""Harvest human labels into eval gold cases.

Every review click is an implicit label. This exporter turns two sources into
JSONL gold cases the eval runners can score against:

  - decision_feedback rows -> decision-quality labels
      correct        -> true consequential decision
      wrong / not_important -> not a (consequential) decision
      duplicate      -> duplicate of an existing decision
      superseded     -> a superseded decision
      missing_evidence / minor -> weak/low-value decision
  - drifts.feedback_verdict -> drift-quality labels
      confirmed -> true drift; false_positive/etc -> not a meaningful drift

Output is append-safe JSONL with provenance (labeler, workspace, captured
timestamp) so gold sets built from customer data stay auditable.

Usage:
    uv run python scripts/export_gold_cases.py \
        --out evals/datasets/decisions/harvested.jsonl
    uv run python scripts/export_gold_cases.py --kind drift \
        --out evals/datasets/drifts/harvested.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text  # noqa: E402

from src.db import async_session  # noqa: E402

_DECISION_LABEL = {
    "correct": "true_consequential_decision",
    "wrong": "not_a_decision",
    "not_important": "not_consequential",
    "duplicate": "duplicate_decision",
    "superseded": "superseded_decision",
    "missing_evidence": "weak_evidence",
    "minor": "minor_decision",
}


async def _export_decisions(out: Path) -> int:
    async with async_session() as session:
        rows = (
            await session.execute(
                sa_text(
                    """
                    SELECT f.verdict, f.note, f.created_at, f.user_id,
                           f.workspace_id, d.statement, d.rationale,
                           d.consequentiality_score, d.producer
                    FROM decision_feedback f
                    JOIN decisions d ON d.id = f.decision_id
                    WHERE d.deleted_at IS NULL
                    ORDER BY f.created_at
                    """
                )
            )
        ).fetchall()

    written = 0
    with out.open("a") as fh:
        for r in rows:
            verdict = r[0]
            case = {
                "kind": "decision",
                "label": _DECISION_LABEL.get(verdict, verdict),
                "statement": r[5],
                "rationale": r[6],
                "consequentiality_score": r[7],
                "producer": r[8],
                "provenance": {
                    "verdict": verdict,
                    "note": r[1],
                    "labeler": str(r[3]),
                    "workspace_id": str(r[4]),
                    "captured_at": r[2].isoformat() if r[2] else None,
                },
            }
            fh.write(json.dumps(case) + "\n")
            written += 1
    return written


async def _export_drifts(out: Path) -> int:
    async with async_session() as session:
        rows = (
            await session.execute(
                sa_text(
                    """
                    SELECT dr.feedback_verdict, dr.summary, dr.severity,
                           dr.verifier_verdict, dr.workspace_id, dr.updated_at,
                           d.statement, ec.expected_state
                    FROM drifts dr
                    JOIN decisions d ON d.id = dr.decision_id
                    LEFT JOIN expected_consequences ec
                        ON ec.id = dr.expected_consequence_id
                    WHERE dr.feedback_verdict IS NOT NULL
                      AND dr.deleted_at IS NULL
                    ORDER BY dr.updated_at
                    """
                )
            )
        ).fetchall()

    written = 0
    with out.open("a") as fh:
        for r in rows:
            verdict = r[0]
            case = {
                "kind": "drift",
                "label": "true_drift" if verdict == "confirmed" else "not_drift",
                "decision_statement": r[6],
                "expected_state": r[7],
                "drift_summary": r[1],
                "severity": r[2],
                "verifier_verdict": r[3],
                "provenance": {
                    "verdict": verdict,
                    "workspace_id": str(r[4]),
                    "captured_at": r[5].isoformat() if r[5] else None,
                },
            }
            fh.write(json.dumps(case) + "\n")
            written += 1
    return written


async def run(kind: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if kind == "decision":
        n = await _export_decisions(out)
    elif kind == "drift":
        n = await _export_drifts(out)
    else:
        raise SystemExit(f"unknown kind: {kind}")
    print(f"harvested {n} {kind} gold case(s) -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["decision", "drift"], default="decision")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.kind, args.out))


if __name__ == "__main__":
    main()
