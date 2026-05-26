"""Tests for deterministic Graph RAG contracts and eval scoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.evals.graph_rag import EvalThresholds, evaluate_case, evaluate_dataset, load_dataset
from src.services.graph_rag_types import (
    FreshnessState,
    GraphRagResult,
    RetrievalFeatures,
    RetrievalTarget,
    RetrievalTraceItem,
    VerificationState,
)


def _trace_item(
    source_id: str = "decision-1",
    *,
    selected: bool = True,
    source_link: str = "/dashboard/source-reference?source_id=decision-1",
    workspace_match: bool = True,
) -> RetrievalTraceItem:
    return RetrievalTraceItem(
        source_type="decision",
        source_id=source_id,
        title="Decision receipt",
        snippet="We decided to keep source-backed receipts.",
        source_link=source_link,
        targets=[RetrievalTarget.DECISION_RECEIPTS],
        signals=["graph_traversal"],
        features=RetrievalFeatures(
            workspace_match=workspace_match,
            freshness_state=FreshnessState.FRESH,
            verification_state=VerificationState.CONFIRMED_DECISION,
        ),
        selected=selected,
        why_selected="Confirmed Decision with exact source link." if selected else None,
        suppress_reason=None if selected else "stale_duplicate",
    )


def test_retrieval_target_values_are_locked() -> None:
    assert {target.value for target in RetrievalTarget} == {
        "decision_receipts",
        "source_evidence",
        "graph_neighborhood",
        "related_work",
    }

    with pytest.raises(ValidationError):
        RetrievalTraceItem(
            source_type="decision",
            source_id="decision-1",
            title="Decision",
            targets=["unknown_target"],
            signals=["graph_traversal"],
        )


def test_retrieval_trace_validation_requires_signals_and_drop_reasons() -> None:
    with pytest.raises(ValidationError, match="at least one signal"):
        RetrievalTraceItem(
            source_type="decision",
            source_id="decision-1",
            title="Decision",
            targets=[RetrievalTarget.DECISION_RECEIPTS],
            signals=[],
        )

    with pytest.raises(ValidationError, match="dropped retrieval trace"):
        RetrievalTraceItem(
            source_type="decision",
            source_id="decision-1",
            title="Decision",
            targets=[RetrievalTarget.DECISION_RECEIPTS],
            signals=["graph_traversal"],
            selected=False,
        )

    with pytest.raises(ValidationError, match="selected retrieval trace"):
        RetrievalTraceItem(
            source_type="decision",
            source_id="decision-1",
            title="Decision",
            targets=[RetrievalTarget.DECISION_RECEIPTS],
            signals=["graph_traversal"],
            selected=True,
            suppress_reason="stale",
        )


def test_workspace_mismatch_fails_workspace_safety_metric() -> None:
    case = {
        "id": "cross-workspace-selected",
        "tags": ["workspace_boundary"],
        "expected_source_ids": ["decision-1"],
        "result": {
            "query_id": "q-1",
            "trace": [_trace_item(workspace_match=False).model_dump(mode="json")],
        },
    }

    result = evaluate_case(load_dataset(_write_jsonl(case))[0])

    assert result.workspace_safety == 0.0
    assert "workspace_safety" in result.failures


def test_eval_runner_fails_broken_source_links_and_missing_expected_ids(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "graph-rag.jsonl"
    rows = [
        {
            "id": "broken-link",
            "tags": ["source_link_accuracy"],
            "expected_source_ids": ["decision-1", "source-2"],
            "expected_source_links": {
                "decision-1": "/dashboard/source-reference?source_id=decision-1"
            },
            "result": {
                "query_id": "q-1",
                "trace": [
                    _trace_item(
                        "decision-1",
                        source_link="/dashboard/source-reference?source_id=wrong",
                    ).model_dump(mode="json")
                ],
            },
        }
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = evaluate_dataset(load_dataset(dataset_path), thresholds=EvalThresholds())

    assert report.passed is False
    assert report.cases[0].recall_at_5 == 0.5
    assert report.cases[0].source_link_accuracy == 0.0
    assert set(report.cases[0].failures) >= {"recall_at_5", "source_link_accuracy"}


def test_bundled_graph_rag_golden_dataset_passes_thresholds() -> None:
    dataset_path = Path("evals/datasets/graph_rag/golden.jsonl")

    cases = load_dataset(dataset_path)
    report = evaluate_dataset(cases, thresholds=EvalThresholds())

    assert report.case_count >= 20
    assert report.passed is True
    assert report.recall_at_5 >= 0.85
    assert report.source_link_accuracy >= 0.90
    assert report.provenance_completeness >= 0.90
    assert report.workspace_safety == 1.0
    assert report.stream_parity == 1.0
    assert report.action_grounding == 1.0

    tags = {tag for case in cases for tag in case.tags}
    assert {
        "decision_recall",
        "source_link_accuracy",
        "stale_avoidance",
        "workspace_boundary",
        "action_grounding",
        "noise_control",
        "stream_parity",
        "generated_context_downranking",
    }.issubset(tags)


def _write_jsonl(row: dict) -> Path:
    path = Path("/tmp/contextos-graph-rag-test.jsonl")
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    return path
