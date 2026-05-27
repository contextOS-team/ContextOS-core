"""Deterministic missed-decision eval runner.

This runner scores labeled source fixtures against structured candidate output.
It is intentionally CI-safe: the bundled dataset does not call a live model.
Live-model replay can feed the same schema later.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from src.services.missed_decision_extractor import (
    RawMissedDecisionCandidate,
    RawMissedDecisionExtractionResult,
    validate_missed_decision_candidates,
)
from src.services.missed_decision_sources import MissedDecisionSourceRecord

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class EvalThresholds:
    """Quality gates for deterministic missed-decision evals."""

    min_precision: float = 0.85
    min_recall: float = 0.70
    min_source_link_accuracy: float = 0.90
    min_payload_completeness: float = 0.85


@dataclass(frozen=True)
class ExpectedCandidate:
    inferred_decision: str
    source_quote: str
    source_link: str | None = None


@dataclass(frozen=True)
class MissedDecisionEvalCase:
    id: str
    source: MissedDecisionSourceRecord
    expected: list[ExpectedCandidate]
    model_output: RawMissedDecisionExtractionResult
    suggestion_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class CaseEvalResult:
    id: str
    expected_count: int
    actual_count: int
    raw_candidate_count: int
    true_positive_count: int
    false_positive_count: int
    false_negative_count: int
    invalid_candidate_count: int
    source_link_match_count: int
    payload_completeness: float

    @property
    def precision(self) -> float:
        denominator = self.true_positive_count + self.false_positive_count
        if denominator == 0:
            return 1.0
        return self.true_positive_count / denominator

    @property
    def recall(self) -> float:
        if self.expected_count == 0:
            return 1.0
        return self.true_positive_count / self.expected_count

    @property
    def source_link_accuracy(self) -> float:
        if self.true_positive_count == 0:
            return 1.0 if self.expected_count == 0 else 0.0
        return self.source_link_match_count / self.true_positive_count

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "expected_count": self.expected_count,
            "actual_count": self.actual_count,
            "raw_candidate_count": self.raw_candidate_count,
            "true_positive_count": self.true_positive_count,
            "false_positive_count": self.false_positive_count,
            "false_negative_count": self.false_negative_count,
            "invalid_candidate_count": self.invalid_candidate_count,
            "precision": self.precision,
            "recall": self.recall,
            "source_link_accuracy": self.source_link_accuracy,
            "payload_completeness": self.payload_completeness,
        }


@dataclass(frozen=True)
class EvalReport:
    case_count: int
    expected_count: int
    actual_count: int
    raw_candidate_count: int
    true_positive_count: int
    false_positive_count: int
    false_negative_count: int
    invalid_candidate_count: int
    precision: float
    recall: float
    source_link_accuracy: float
    payload_completeness: float
    passed: bool
    thresholds: EvalThresholds
    cases: list[CaseEvalResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_count": self.case_count,
            "expected_count": self.expected_count,
            "actual_count": self.actual_count,
            "raw_candidate_count": self.raw_candidate_count,
            "true_positive_count": self.true_positive_count,
            "false_positive_count": self.false_positive_count,
            "false_negative_count": self.false_negative_count,
            "invalid_candidate_count": self.invalid_candidate_count,
            "precision": self.precision,
            "recall": self.recall,
            "source_link_accuracy": self.source_link_accuracy,
            "payload_completeness": self.payload_completeness,
            "passed": self.passed,
            "thresholds": {
                "min_precision": self.thresholds.min_precision,
                "min_recall": self.thresholds.min_recall,
                "min_source_link_accuracy": self.thresholds.min_source_link_accuracy,
                "min_payload_completeness": self.thresholds.min_payload_completeness,
            },
            "cases": [case.to_dict() for case in self.cases],
        }


def _normalize(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.lower()))


def _candidate_key(inferred_decision: str, source_quote: str) -> tuple[str, str]:
    return (_normalize(inferred_decision), _normalize(source_quote))


def _source_from_json(value: dict[str, Any]) -> MissedDecisionSourceRecord:
    return MissedDecisionSourceRecord(
        workspace_id=UUID(value["workspace_id"]),
        source_type=value["source_type"],
        source_id=UUID(value["source_id"]),
        text=value["text"],
        source_link=value["source_link"],
        source_created_at=datetime.fromisoformat(value["source_created_at"]),
        metadata=value.get("metadata", {}),
    )


def _case_from_json(value: dict[str, Any]) -> MissedDecisionEvalCase:
    raw_candidates = [
        RawMissedDecisionCandidate(**candidate)
        for candidate in value["model_output"].get("candidates", [])
    ]
    expected = [
        ExpectedCandidate(
            inferred_decision=candidate["inferred_decision"],
            source_quote=candidate["source_quote"],
            source_link=candidate.get("source_link"),
        )
        for candidate in value.get("expected", [])
    ]
    return MissedDecisionEvalCase(
        id=value["id"],
        source=_source_from_json(value["source"]),
        expected=expected,
        model_output=RawMissedDecisionExtractionResult(candidates=raw_candidates),
        suggestion_payload=value.get("suggestion_payload"),
    )


def load_dataset(path: Path) -> list[MissedDecisionEvalCase]:
    """Load newline-delimited missed-decision eval cases."""
    cases: list[MissedDecisionEvalCase] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            cases.append(_case_from_json(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"Invalid eval case at {path}:{line_number}") from exc
    return cases


def evaluate_case(case: MissedDecisionEvalCase) -> CaseEvalResult:
    """Score one case after running source-backed candidate validation."""
    actual = validate_missed_decision_candidates(case.source, case.model_output)
    expected_by_key = {
        _candidate_key(item.inferred_decision, item.source_quote): item
        for item in case.expected
    }
    expected_keys = set(expected_by_key)
    actual_keys = {
        _candidate_key(item.inferred_decision, item.source_quote)
        for item in actual
    }
    true_positive_count = len(expected_keys & actual_keys)
    false_positive_count = len(actual_keys - expected_keys)
    false_negative_count = len(expected_keys - actual_keys)
    raw_candidate_count = len(case.model_output.candidates)
    source_link_match_count = 0
    actual_by_key = {
        _candidate_key(item.inferred_decision, item.source_quote): item
        for item in actual
    }
    for key in expected_keys & actual_keys:
        expected = expected_by_key[key]
        expected_link = expected.source_link or case.source.source_link
        if actual_by_key[key].source_link == expected_link:
            source_link_match_count += 1
    return CaseEvalResult(
        id=case.id,
        expected_count=len(expected_keys),
        actual_count=len(actual_keys),
        raw_candidate_count=raw_candidate_count,
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        false_negative_count=false_negative_count,
        invalid_candidate_count=raw_candidate_count - len(actual_keys),
        source_link_match_count=source_link_match_count,
        payload_completeness=_payload_completeness(
            case.suggestion_payload,
            expected_count=len(expected_keys),
        ),
    )


def _payload_completeness(
    payload: dict[str, Any] | None,
    *,
    expected_count: int,
) -> float:
    """Score source-backed suggestion payload fields when provided."""
    if payload is None:
        return 0.0 if expected_count > 0 else 1.0
    required_paths = [
        ("evidence", "source_quote"),
        ("evidence", "source_link"),
        ("details", "candidate_id"),
        ("details", "confidence"),
        ("details", "match_status"),
        ("details", "explanation"),
        ("details", "explanation", "selected_because"),
        ("details", "explanation", "grounding_state"),
        ("provenance", "generator"),
        ("provenance", "candidate_id"),
        ("provenance", "quality_gate"),
        ("provenance", "quality_gate", "passed"),
        ("provenance", "retrieval_signals"),
    ]
    present = 0
    for path in required_paths:
        value = _path_value(payload, path)
        if value not in (None, "", [], {}):
            present += 1
    return present / len(required_paths)


def _path_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def evaluate_dataset(
    cases: list[MissedDecisionEvalCase],
    *,
    thresholds: EvalThresholds,
) -> EvalReport:
    """Score a missed-decision eval dataset against the supplied thresholds."""
    case_results = [evaluate_case(case) for case in cases]
    expected_count = sum(case.expected_count for case in case_results)
    actual_count = sum(case.actual_count for case in case_results)
    raw_candidate_count = sum(case.raw_candidate_count for case in case_results)
    true_positive_count = sum(case.true_positive_count for case in case_results)
    false_positive_count = sum(case.false_positive_count for case in case_results)
    false_negative_count = sum(case.false_negative_count for case in case_results)
    invalid_candidate_count = sum(case.invalid_candidate_count for case in case_results)
    precision_denominator = true_positive_count + false_positive_count
    precision = (
        1.0
        if precision_denominator == 0
        else true_positive_count / precision_denominator
    )
    recall = 1.0 if expected_count == 0 else true_positive_count / expected_count
    source_link_denominator = sum(
        case.true_positive_count for case in case_results
    )
    source_link_accuracy = (
        1.0
        if source_link_denominator == 0
        else sum(case.source_link_match_count for case in case_results)
        / source_link_denominator
    )
    payload_completeness = (
        sum(case.payload_completeness for case in case_results) / len(case_results)
        if case_results
        else 1.0
    )
    passed = (
        precision >= thresholds.min_precision
        and recall >= thresholds.min_recall
        and source_link_accuracy >= thresholds.min_source_link_accuracy
        and payload_completeness >= thresholds.min_payload_completeness
    )
    return EvalReport(
        case_count=len(case_results),
        expected_count=expected_count,
        actual_count=actual_count,
        raw_candidate_count=raw_candidate_count,
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        false_negative_count=false_negative_count,
        invalid_candidate_count=invalid_candidate_count,
        precision=precision,
        recall=recall,
        source_link_accuracy=source_link_accuracy,
        payload_completeness=payload_completeness,
        passed=passed,
        thresholds=thresholds,
        cases=case_results,
    )


def _print_text_report(report: EvalReport) -> None:
    status = "PASS" if report.passed else "FAIL"
    print(f"missed_decisions_eval={status}")
    print(f"cases={report.case_count}")
    print(f"precision={report.precision:.3f}")
    print(f"recall={report.recall:.3f}")
    print(f"source_link_accuracy={report.source_link_accuracy:.3f}")
    print(f"payload_completeness={report.payload_completeness:.3f}")
    print(f"invalid_candidates={report.invalid_candidate_count}")
    for case in report.cases:
        print(
            f"- {case.id}: precision={case.precision:.3f} "
            f"recall={case.recall:.3f} invalid={case.invalid_candidate_count}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/missed_decisions/golden.jsonl"),
        help="Path to a missed-decision JSONL eval dataset.",
    )
    parser.add_argument("--min-precision", type=float, default=0.85)
    parser.add_argument("--min-recall", type=float, default=0.70)
    parser.add_argument("--min-source-link-accuracy", type=float, default=0.90)
    parser.add_argument("--min-payload-completeness", type=float, default=0.85)
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args(argv)

    report = evaluate_dataset(
        load_dataset(args.dataset),
        thresholds=EvalThresholds(
            min_precision=args.min_precision,
            min_recall=args.min_recall,
            min_source_link_accuracy=args.min_source_link_accuracy,
            min_payload_completeness=args.min_payload_completeness,
        ),
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
