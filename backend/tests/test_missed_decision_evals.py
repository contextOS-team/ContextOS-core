"""Tests for missed-decision evaluation datasets and scoring."""

from __future__ import annotations

import json
from pathlib import Path

from src.evals.missed_decisions import EvalThresholds, evaluate_dataset, load_dataset


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_eval_runner_scores_expected_candidates_and_invalid_drops(
    tmp_path: Path,
) -> None:
    workspace_id = "11111111-1111-4111-8111-111111111111"
    source_id = "22222222-2222-4222-8222-222222222222"
    source_link = (
        "/dashboard/source-reference?source_type=slack_message"
        f"&source_id={source_id}&workspace_id={workspace_id}"
        "&source_timestamp=2026-05-25T09%3A30%3A00%2B00%3A00"
    )
    dataset_path = tmp_path / "missed-decisions.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "id": "valid-source-backed-decision",
                "source": {
                    "workspace_id": workspace_id,
                    "source_type": "slack_message",
                    "source_id": source_id,
                    "text": (
                        "We decided to keep the dashboard Needs review rail "
                        "bounded so confirmed decisions remain primary."
                    ),
                    "source_link": source_link,
                    "source_created_at": "2026-05-25T09:30:00+00:00",
                    "metadata": {"channel_id": "C123"},
                },
                "expected": [
                    {
                        "inferred_decision": (
                            "Keep the dashboard Needs review rail bounded"
                        ),
                        "source_quote": (
                            "We decided to keep the dashboard Needs review rail bounded"
                        ),
                        "source_link": source_link,
                    }
                ],
                "model_output": {
                    "candidates": [
                        {
                            "source_quote": (
                                "We decided to keep the dashboard Needs review rail "
                                "bounded"
                            ),
                            "inferred_decision": (
                                "Keep the dashboard Needs review rail bounded"
                            ),
                            "inferred_rationale": (
                                "Confirmed decisions remain the primary surface."
                            ),
                            "source_link": source_link,
                            "confidence": 0.84,
                            "people": ["Daulet"],
                            "affected_systems": ["dashboard"],
                            "supporting_sources": [],
                        }
                    ]
                },
                "suggestion_payload": {
                    "evidence": {
                        "source_quote": (
                            "We decided to keep the dashboard Needs review rail bounded"
                        ),
                        "source_link": source_link,
                    },
                    "details": {
                        "candidate_id": "candidate-1",
                        "confidence": "high",
                        "match_status": "no_match",
                        "explanation": {
                            "selected_because": "Source backed.",
                            "grounding_state": "source_backed",
                        },
                    },
                    "provenance": {
                        "generator": "missed_decision:v1",
                        "candidate_id": "candidate-1",
                        "quality_gate": {"passed": True},
                        "retrieval_signals": ["missed_decision_candidate"],
                    },
                },
            },
            {
                "id": "hallucinated-quote-is-dropped",
                "source": {
                    "workspace_id": workspace_id,
                    "source_type": "slack_message",
                    "source_id": source_id,
                    "text": "Maybe we can revisit the sync UI later.",
                    "source_link": source_link,
                    "source_created_at": "2026-05-25T10:30:00+00:00",
                    "metadata": {},
                },
                "expected": [],
                "model_output": {
                    "candidates": [
                        {
                            "source_quote": "We decided to ship evals tonight.",
                            "inferred_decision": "Ship evals tonight",
                            "inferred_rationale": "The team needs confidence.",
                            "source_link": source_link,
                            "confidence": 0.91,
                            "people": [],
                            "affected_systems": [],
                            "supporting_sources": [],
                        }
                    ]
                },
            },
        ],
    )

    report = evaluate_dataset(load_dataset(dataset_path), thresholds=EvalThresholds())

    assert report.case_count == 2
    assert report.expected_count == 1
    assert report.actual_count == 1
    assert report.true_positive_count == 1
    assert report.false_positive_count == 0
    assert report.false_negative_count == 0
    assert report.invalid_candidate_count == 1
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.source_link_accuracy == 1.0
    assert report.payload_completeness == 1.0
    assert report.passed is True


def test_bundled_missed_decision_golden_dataset_passes_thresholds() -> None:
    dataset_path = Path("evals/datasets/missed_decisions/golden.jsonl")

    report = evaluate_dataset(load_dataset(dataset_path), thresholds=EvalThresholds())

    assert report.case_count >= 3
    assert report.passed is True
    assert report.precision >= 0.85
    assert report.recall >= 0.7
    assert report.source_link_accuracy >= 0.9
    assert report.invalid_candidate_count >= 1
    assert report.payload_completeness >= 0.85
