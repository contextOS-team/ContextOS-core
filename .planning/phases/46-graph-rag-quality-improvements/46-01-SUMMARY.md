---
phase: 46-graph-rag-quality-improvements
plan: "01"
subsystem: ai-evals
tags: [suggestions, missed-decisions, provenance, evals]
requires:
  - phase: 44-suggestion-system-and-dismissals
    provides: Generic suggestion lifecycle and Needs review surface
  - phase: 45-post-sync-missed-decision-detection
    provides: Missed-decision candidates and suggestion publishing
provides:
  - Shared suggestion-family quality contracts
  - Extended missed-decision deterministic eval metrics
  - Provenance-preserving candidate-to-suggestion quality gates
affects: [suggestion-quality, missed-decision-suggestions, action-grounding]
tech-stack:
  added: []
  patterns: [jsonb quality gates, fixture-only eval metrics]
key-files:
  created:
    - backend/src/services/suggestion_quality.py
    - backend/src/evals/missed_decisions.py
    - backend/evals/datasets/missed_decisions/golden.jsonl
    - backend/tests/test_missed_decision_evals.py
  modified:
    - backend/src/services/suggestions.py
    - backend/src/services/missed_decision_suggestions.py
    - backend/tests/test_suggestions.py
    - backend/tests/test_missed_decision_candidates.py
key-decisions:
  - "Suggestion quality data stays in existing evidence/details/provenance JSONB fields; no schema change."
  - "Prompt-injection-like source text suppresses suggestion surfacing at the shared quality-contract layer."
  - "Missed-decision evals now score source-link accuracy and suggestion payload completeness, not only extraction precision/recall."
patterns-established:
  - "SuggestionFamilyAssessment exposes explanation() and quality_gate() payloads for JSONB persistence."
  - "Deterministic eval reports include product-output quality fields alongside extraction metrics."
requirements-completed: [GRAG-02, GRAG-04]
duration: 5min
completed: 2026-05-26
---

# Phase 46 Plan 01 Summary

**Suggestion and missed-decision outputs now carry deterministic family quality gates and source-backed eval metrics**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-26T12:13:00Z
- **Completed:** 2026-05-26T12:17:36Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added shared `SuggestionFamily`, `SuggestionGroundingTrace`, and `SuggestionFamilyAssessment` contracts.
- Wired missing-source and missed-decision suggestions to structured explanation and quality-gate payloads.
- Extended missed-decision evals with source-link accuracy, invalid-drop count, payload completeness, and richer golden cases.

## Task Commits

1. **Task 1: Create shared suggestion-family quality contracts** - `be56863` (feat)
2. **Task 2: Extend missed-decision deterministic evals** - `07a9358` (feat)
3. **Task 3: Gate candidate-to-suggestion provenance quality** - `a9f1386` (feat)

## Files Created/Modified

- `backend/src/services/suggestion_quality.py` - Shared family policy and grounding validators.
- `backend/src/services/suggestions.py` - Missing-source explanation and quality-gate payloads.
- `backend/src/services/missed_decision_suggestions.py` - Candidate suggestion provenance quality gate.
- `backend/src/evals/missed_decisions.py` - Extended deterministic eval metrics and JSON output.
- `backend/evals/datasets/missed_decisions/golden.jsonl` - Golden cases for true/negative/payload quality.
- `backend/tests/test_suggestions.py` - Family assessment, injection suppression, and serializer coverage.
- `backend/tests/test_missed_decision_candidates.py` - Candidate-to-suggestion payload and schema checkpoint tests.
- `backend/tests/test_missed_decision_evals.py` - Eval metric and dataset threshold tests.

## Decisions Made

- Used family-specific policies instead of new suggestion SQLModel fields so Phase 44 storage remains stable.
- Kept action prompts in the quality contract now, but no external write behavior was introduced.
- Counted duplicate fixture collapse as an invalid-drop signal in deterministic eval output.

## Deviations from Plan

None - plan scope was executed as written.

## Issues Encountered

None.

## Verification

- `uv run --directory backend pytest tests/test_missed_decision_evals.py tests/test_suggestions.py tests/test_missed_decision_candidates.py tests/test_missed_decision_actions.py tests/test_graph_rag_evals.py -q` - passed
- `uv run --directory backend python -m src.evals.missed_decisions --dataset evals/datasets/missed_decisions/golden.jsonl --json` - passed
- `uv run --directory backend ruff check ...` for changed backend/test files - passed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 0 is complete. Plan 46-02 can now import the Graph RAG types and rely on suggestion-family quality contracts for downstream provenance work.

---
*Phase: 46-graph-rag-quality-improvements*
*Completed: 2026-05-26*
