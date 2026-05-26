---
phase: 46-graph-rag-quality-improvements
plan: "03"
subsystem: graph-rag
tags: [freshness, ranking, provenance, evals]
requires:
  - phase: 46-00
    provides: Shared Graph RAG eval and trace contracts
  - phase: 46-02
    provides: Target-aware retrieval and Decision receipt metadata
provides:
  - Provider freshness matrix
  - Feature-aware ranking policy
  - Selected and dropped retrieval trace conversion
  - Ranking regression eval coverage
affects: [linking, graph-rag-evals, source-provenance]
tech-stack:
  added: []
  patterns: [provider freshness policy, feature-weighted RRF, dropped evidence reasons]
key-files:
  created:
    - backend/src/services/graph_rag_freshness.py
  modified:
    - backend/src/services/linking.py
    - backend/evals/datasets/graph_rag/golden.jsonl
    - backend/tests/test_linking_graph.py
    - backend/tests/test_graph_rag_evals.py
    - backend/tests/test_linking_bulk_lookup.py
requirements-completed: [GRAG-01, GRAG-02, GRAG-03, GRAG-04]
duration: 6min
completed: 2026-05-26
---

# Phase 46 Plan 03 Summary

**Retrieval ranking now exposes freshness, verification, source originality, score, and drop-reason features**

## Performance

- **Started:** 2026-05-26T12:31:08Z
- **Completed:** 2026-05-26T12:37:48Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `ProviderFreshnessPolicy`, `FreshnessAssessment`, and `calculate_freshness_state(...)` for provider-specific timestamp semantics.
- Attached freshness, verification state, source timestamp, source originality, graph depth, RRF score, and rerank score to retrieval candidates.
- Added feature-aware ranking adjustments so confirmed source-backed Decisions and primary source evidence outrank stale or generated-context evidence.
- Added dropped evidence tracking on `LinkingResult` with deterministic reasons including `stale_duplicate`, `superseded_decision`, `generated_context_not_primary_evidence`, `workspace_mismatch`, and `token_budget`.
- Added `linked_item_to_trace(...)` to map selected or dropped linked items into the shared `RetrievalTraceItem` contract.
- Extended the golden Graph RAG dataset to 21 cases with a complete ranking feature bundle case.

## Decisions Made

- Confirmation authority is represented by `verification_state`, not by forcing old source timestamps to appear fresh.
- Context pages can be temporally fresh but still carry `source_originality="generated_context"` and are dropped when primary source evidence exists.
- Bulk summary lookup now returns `SourceSummary` objects so feature metadata can travel with title, snippet, and URL resolution.

## Deviations from Plan

- `backend/tests/test_linking_bulk_lookup.py` was updated in addition to the listed plan files because the internal bulk lookup contract now returns feature-aware `SourceSummary` values.

## Issues Encountered

- Full-file ruff still has legacy line-length findings in large prompt/template files. The focused `F,I` gate passed for touched 46-03 files.

## Verification

- `uv run --directory backend pytest tests/test_linking_graph.py tests/test_graph_rag_evals.py -q` - passed
- `uv run --directory backend pytest tests/test_linking_bulk_lookup.py tests/test_empty_notion_fixes.py -q` - passed
- `uv run --directory backend pytest tests/test_linking.py tests/test_linking_code.py tests/test_linking_bulk_lookup.py tests/test_empty_notion_fixes.py tests/test_linking_graph.py tests/test_graph_rag_evals.py -q` - passed
- `uv run --directory backend python -m src.evals.graph_rag --dataset evals/datasets/graph_rag/golden.jsonl --json` - passed
- `uv run --directory backend ruff check --select F,I src/services/graph_rag_freshness.py src/services/linking.py tests/test_linking_graph.py tests/test_graph_rag_evals.py tests/test_linking_bulk_lookup.py` - passed

## User Setup Required

None.

## Next Phase Readiness

Plan 46-04 can persist and expose retrieval explanations using selected/dropped item metadata, source originality, freshness state, and trace conversion.

---
*Phase: 46-graph-rag-quality-improvements*
*Completed: 2026-05-26*
