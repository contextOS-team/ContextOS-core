"""Deterministic Graph RAG eval runner.

The runner scores local JSONL retrieval fixtures. It is intentionally CI-safe:
it does not call a database, embedding service, network, or live model.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.services.graph_rag_types import (
    FreshnessState,
    GraphRagResult,
    RetrievalTraceItem,
)


@dataclass(frozen=True)
class EvalThresholds:
    """Quality gates for deterministic Graph RAG evals."""

    min_recall_at_5: float = 0.85
    min_source_link_accuracy: float = 0.90
    max_stale_violation_rate: float = 0.0
    max_noise_false_positive_rate: float = 0.05
    min_provenance_completeness: float = 0.90
    min_workspace_safety: float = 1.0
    min_stream_parity: float = 1.0
    min_action_grounding: float = 1.0


@dataclass(frozen=True)
class GraphRagEvalCase:
    """One deterministic Graph RAG fixture."""

    id: str
    tags: list[str]
    result: GraphRagResult
    expected_source_ids: list[str] = field(default_factory=list)
    expected_decision_ids: list[str] = field(default_factory=list)
    expected_source_links: dict[str, str] = field(default_factory=dict)
    forbidden_source_ids: list[str] = field(default_factory=list)
    stream_result: GraphRagResult | None = None
    require_action_grounding: bool = False
    require_no_stale_selected: bool = False


@dataclass(frozen=True)
class GraphRagCaseResult:
    """Per-case metric results."""

    id: str
    tags: list[str]
    recall_at_5: float
    source_link_accuracy: float
    stale_violation_rate: float
    noise_false_positive_rate: float
    provenance_completeness: float
    workspace_safety: float
    stream_parity: float
    action_grounding: float
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tags": self.tags,
            "recall_at_5": self.recall_at_5,
            "source_link_accuracy": self.source_link_accuracy,
            "stale_violation_rate": self.stale_violation_rate,
            "noise_false_positive_rate": self.noise_false_positive_rate,
            "provenance_completeness": self.provenance_completeness,
            "workspace_safety": self.workspace_safety,
            "stream_parity": self.stream_parity,
            "action_grounding": self.action_grounding,
            "passed": self.passed,
            "failures": self.failures,
        }


@dataclass(frozen=True)
class GraphRagEvalReport:
    """Aggregate eval report."""

    case_count: int
    passed: bool
    thresholds: EvalThresholds
    recall_at_5: float
    source_link_accuracy: float
    stale_violation_rate: float
    noise_false_positive_rate: float
    provenance_completeness: float
    workspace_safety: float
    stream_parity: float
    action_grounding: float
    cases: list[GraphRagCaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "passed": self.passed,
            "thresholds": {
                "min_recall_at_5": self.thresholds.min_recall_at_5,
                "min_source_link_accuracy": self.thresholds.min_source_link_accuracy,
                "max_stale_violation_rate": self.thresholds.max_stale_violation_rate,
                "max_noise_false_positive_rate": (
                    self.thresholds.max_noise_false_positive_rate
                ),
                "min_provenance_completeness": (
                    self.thresholds.min_provenance_completeness
                ),
                "min_workspace_safety": self.thresholds.min_workspace_safety,
                "min_stream_parity": self.thresholds.min_stream_parity,
                "min_action_grounding": self.thresholds.min_action_grounding,
            },
            "recall_at_5": self.recall_at_5,
            "source_link_accuracy": self.source_link_accuracy,
            "stale_violation_rate": self.stale_violation_rate,
            "noise_false_positive_rate": self.noise_false_positive_rate,
            "provenance_completeness": self.provenance_completeness,
            "workspace_safety": self.workspace_safety,
            "stream_parity": self.stream_parity,
            "action_grounding": self.action_grounding,
            "cases": [case.to_dict() for case in self.cases],
        }


def _case_from_json(value: dict[str, Any]) -> GraphRagEvalCase:
    return GraphRagEvalCase(
        id=value["id"],
        tags=list(value.get("tags", [])),
        expected_source_ids=list(value.get("expected_source_ids", [])),
        expected_decision_ids=list(value.get("expected_decision_ids", [])),
        expected_source_links=dict(value.get("expected_source_links", {})),
        forbidden_source_ids=list(value.get("forbidden_source_ids", [])),
        stream_result=(
            GraphRagResult.model_validate(value["stream_result"])
            if value.get("stream_result")
            else None
        ),
        require_action_grounding=bool(value.get("require_action_grounding", False)),
        require_no_stale_selected=bool(value.get("require_no_stale_selected", False)),
        result=GraphRagResult.model_validate(value["result"]),
    )


def load_dataset(path: Path) -> list[GraphRagEvalCase]:
    """Load newline-delimited Graph RAG eval cases."""
    cases: list[GraphRagEvalCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(_case_from_json(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"Invalid Graph RAG eval case at {path}:{line_number}") from exc
    return cases


def _recall_at_5(case: GraphRagEvalCase, selected: list[RetrievalTraceItem]) -> float:
    expected = set(case.expected_source_ids) | set(case.expected_decision_ids)
    if not expected:
        return 1.0
    top_ids = {item.source_id for item in selected[:5]}
    return len(expected & top_ids) / len(expected)


def _source_link_accuracy(
    expected_links: dict[str, str],
    selected: list[RetrievalTraceItem],
) -> float:
    if not expected_links:
        return 1.0
    by_id = {item.source_id: item for item in selected}
    matches = 0
    for source_id, expected_link in expected_links.items():
        item = by_id.get(source_id)
        if item is not None and item.source_link == expected_link:
            matches += 1
    return matches / len(expected_links)


def _stale_violation_rate(
    case: GraphRagEvalCase,
    selected: list[RetrievalTraceItem],
) -> float:
    if not selected or not case.require_no_stale_selected:
        return 0.0
    stale_count = sum(
        1
        for item in selected
        if item.features.freshness_state
        in (FreshnessState.STALE, FreshnessState.SUPERSEDED)
    )
    return stale_count / len(selected)


def _noise_false_positive_rate(
    forbidden_ids: list[str],
    selected: list[RetrievalTraceItem],
) -> float:
    if not selected:
        return 0.0
    forbidden = set(forbidden_ids)
    return sum(1 for item in selected if item.source_id in forbidden) / len(selected)


def _trace_is_complete(item: RetrievalTraceItem) -> bool:
    if not item.targets or not item.signals:
        return False
    if item.features.verification_state.value == "unknown":
        return False
    if item.features.freshness_state.value == "unknown":
        return False
    if item.selected:
        return bool(item.why_selected and item.source_link)
    return bool(item.suppress_reason)


def _provenance_completeness(result: GraphRagResult) -> float:
    if not result.trace:
        return 1.0
    complete = sum(1 for item in result.trace if _trace_is_complete(item))
    return complete / len(result.trace)


def _workspace_safety(selected: list[RetrievalTraceItem]) -> float:
    if not selected:
        return 1.0
    matches = sum(1 for item in selected if item.features.workspace_match)
    return matches / len(selected)


def _stream_parity(case: GraphRagEvalCase, selected: list[RetrievalTraceItem]) -> float:
    if case.stream_result is None:
        return 1.0
    expected = [item.source_id for item in selected if item.selected]
    actual = [item.source_id for item in case.stream_result.selected_items]
    return 1.0 if expected == actual else 0.0


def _action_grounding(case: GraphRagEvalCase, selected: list[RetrievalTraceItem]) -> float:
    if not case.require_action_grounding:
        return 1.0
    action_items = [
        item
        for item in selected
        if item.metadata.get("action_hint") or item.metadata.get("action_prompt")
    ]
    if not action_items:
        return 0.0
    grounded = sum(
        1
        for item in action_items
        if item.metadata.get("action_grounded") is True
        and bool(item.source_link)
        and bool(item.snippet)
    )
    return grounded / len(action_items)


def evaluate_case(
    case: GraphRagEvalCase,
    *,
    thresholds: EvalThresholds | None = None,
) -> GraphRagCaseResult:
    """Score one deterministic Graph RAG case."""
    thresholds = thresholds or EvalThresholds()
    selected = case.result.selected_items
    recall_at_5 = _recall_at_5(case, selected)
    source_link_accuracy = _source_link_accuracy(case.expected_source_links, selected)
    stale_violation_rate = _stale_violation_rate(case, selected)
    noise_false_positive_rate = _noise_false_positive_rate(
        case.forbidden_source_ids,
        selected,
    )
    provenance_completeness = _provenance_completeness(case.result)
    workspace_safety = _workspace_safety(selected)
    stream_parity = _stream_parity(case, selected)
    action_grounding = _action_grounding(case, selected)

    failures: list[str] = []
    if recall_at_5 < thresholds.min_recall_at_5:
        failures.append("recall_at_5")
    if source_link_accuracy < thresholds.min_source_link_accuracy:
        failures.append("source_link_accuracy")
    if stale_violation_rate > thresholds.max_stale_violation_rate:
        failures.append("stale_violation_rate")
    if noise_false_positive_rate > thresholds.max_noise_false_positive_rate:
        failures.append("noise_false_positive_rate")
    if provenance_completeness < thresholds.min_provenance_completeness:
        failures.append("provenance_completeness")
    if workspace_safety < thresholds.min_workspace_safety:
        failures.append("workspace_safety")
    if stream_parity < thresholds.min_stream_parity:
        failures.append("stream_parity")
    if action_grounding < thresholds.min_action_grounding:
        failures.append("action_grounding")

    return GraphRagCaseResult(
        id=case.id,
        tags=case.tags,
        recall_at_5=recall_at_5,
        source_link_accuracy=source_link_accuracy,
        stale_violation_rate=stale_violation_rate,
        noise_false_positive_rate=noise_false_positive_rate,
        provenance_completeness=provenance_completeness,
        workspace_safety=workspace_safety,
        stream_parity=stream_parity,
        action_grounding=action_grounding,
        failures=failures,
    )


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 1.0


def evaluate_dataset(
    cases: list[GraphRagEvalCase],
    *,
    thresholds: EvalThresholds,
) -> GraphRagEvalReport:
    """Score a Graph RAG eval dataset against the supplied thresholds."""
    case_results = [evaluate_case(case, thresholds=thresholds) for case in cases]
    recall_at_5 = _average([case.recall_at_5 for case in case_results])
    source_link_accuracy = _average(
        [case.source_link_accuracy for case in case_results]
    )
    stale_violation_rate = _average(
        [case.stale_violation_rate for case in case_results]
    )
    noise_false_positive_rate = _average(
        [case.noise_false_positive_rate for case in case_results]
    )
    provenance_completeness = _average(
        [case.provenance_completeness for case in case_results]
    )
    workspace_safety = _average([case.workspace_safety for case in case_results])
    stream_parity = _average([case.stream_parity for case in case_results])
    action_grounding = _average([case.action_grounding for case in case_results])
    passed = all(case.passed for case in case_results)
    return GraphRagEvalReport(
        case_count=len(case_results),
        passed=passed,
        thresholds=thresholds,
        recall_at_5=recall_at_5,
        source_link_accuracy=source_link_accuracy,
        stale_violation_rate=stale_violation_rate,
        noise_false_positive_rate=noise_false_positive_rate,
        provenance_completeness=provenance_completeness,
        workspace_safety=workspace_safety,
        stream_parity=stream_parity,
        action_grounding=action_grounding,
        cases=case_results,
    )


def _print_text_report(report: GraphRagEvalReport) -> None:
    status = "PASS" if report.passed else "FAIL"
    print(f"graph_rag_eval={status}")
    print(f"cases={report.case_count}")
    print(f"recall_at_5={report.recall_at_5:.3f}")
    print(f"source_link_accuracy={report.source_link_accuracy:.3f}")
    print(f"stale_violation_rate={report.stale_violation_rate:.3f}")
    print(f"noise_false_positive_rate={report.noise_false_positive_rate:.3f}")
    print(f"provenance_completeness={report.provenance_completeness:.3f}")
    print(f"workspace_safety={report.workspace_safety:.3f}")
    print(f"stream_parity={report.stream_parity:.3f}")
    print(f"action_grounding={report.action_grounding:.3f}")
    for case in report.cases:
        print(
            f"- {case.id}: recall@5={case.recall_at_5:.3f} "
            f"provenance={case.provenance_completeness:.3f} "
            f"failures={','.join(case.failures) or 'none'}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/graph_rag/golden.jsonl"),
        help="Path to a Graph RAG JSONL eval dataset.",
    )
    parser.add_argument("--min-recall-at-5", type=float, default=0.85)
    parser.add_argument("--min-source-link-accuracy", type=float, default=0.90)
    parser.add_argument("--max-stale-violation-rate", type=float, default=0.0)
    parser.add_argument("--max-noise-false-positive-rate", type=float, default=0.05)
    parser.add_argument("--min-provenance-completeness", type=float, default=0.90)
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args(argv)

    thresholds = EvalThresholds(
        min_recall_at_5=args.min_recall_at_5,
        min_source_link_accuracy=args.min_source_link_accuracy,
        max_stale_violation_rate=args.max_stale_violation_rate,
        max_noise_false_positive_rate=args.max_noise_false_positive_rate,
        min_provenance_completeness=args.min_provenance_completeness,
    )
    report = evaluate_dataset(load_dataset(args.dataset), thresholds=thresholds)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
