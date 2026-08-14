"""Offline eval for Decision Guard's check_action.

Scores the LLM conflict assessment against a golden set that deliberately
pairs each conflict with a NON-conflicting hard negative on the same decision
(optimize-postgres vs add-mongodb), so a Guard that cries wolf fails the
no-false-alarm gate even if it catches every real conflict.

Live-model runner (unlike the deterministic missed-decision evals): it calls
the Guard assessment against inline decisions, so it exercises the real prompt.
Run manually / nightly, not in the CI-safe gate.

Usage:
    uv run python -m src.evals.guard --dataset evals/datasets/guard/golden.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from src.services.decision_guard import (
    _GUARD_SYSTEM,
    _VALID,
    STATUS_NO_CONFLICT,
    GuardAssessment,
)
from src.services.llm_client import get_llm_client


@dataclass(frozen=True)
class GuardThresholds:
    # Of real conflicts, how many must we flag (recall).
    min_conflict_recall: float = 0.75
    # Of non-conflicts, how many must we leave alone (no cry-wolf).
    min_no_false_alarm_rate: float = 0.75


class GuardCase(BaseModel):
    id: str
    action: str
    active_decisions: list[str]
    expected_status: str


def _is_conflict(status: str) -> bool:
    return status != STATUS_NO_CONFLICT


async def _assess(case: GuardCase) -> str:
    if not case.active_decisions:
        return STATUS_NO_CONFLICT
    listing = "\n".join(f"- {d}" for d in case.active_decisions)
    prompt = (
        f"Proposed action:\n{case.action}\n\nScope: {{}}\n\n"
        f"Active decisions that may be relevant:\n{listing}\n\nAssess the conflict."
    )
    client = get_llm_client()
    verdict: GuardAssessment = await client.generate_json(
        prompt, GuardAssessment, system_prompt=_GUARD_SYSTEM
    )
    return verdict.status if verdict.status in _VALID else "requires_review"


async def evaluate_dataset(path: Path) -> dict:
    cases = [
        GuardCase(**json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    conflict_total = conflict_hit = clean_total = clean_ok = 0
    rows = []
    for case in cases:
        got = await _assess(case)
        expected_conflict = _is_conflict(case.expected_status)
        got_conflict = _is_conflict(got)
        if expected_conflict:
            conflict_total += 1
            conflict_hit += int(got_conflict)
        else:
            clean_total += 1
            clean_ok += int(not got_conflict)
        rows.append(
            {"id": case.id, "expected": case.expected_status, "got": got}
        )
    recall = conflict_hit / conflict_total if conflict_total else 1.0
    no_false_alarm = clean_ok / clean_total if clean_total else 1.0
    return {
        "conflict_recall": recall,
        "no_false_alarm_rate": no_false_alarm,
        "cases": rows,
    }


def _gate(report: dict, t: GuardThresholds) -> bool:
    return (
        report["conflict_recall"] >= t.min_conflict_recall
        and report["no_false_alarm_rate"] >= t.min_no_false_alarm_rate
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(evaluate_dataset(args.dataset))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"conflict_recall:     {report['conflict_recall']:.2f}")
        print(f"no_false_alarm_rate: {report['no_false_alarm_rate']:.2f}")
        for r in report["cases"]:
            mark = "ok" if (r["expected"] == r["got"]) else "x"
            print(f"  [{mark}] {r['id']}: expected {r['expected']}, got {r['got']}")
    sys.exit(0 if _gate(report, GuardThresholds()) else 1)


if __name__ == "__main__":
    main()
