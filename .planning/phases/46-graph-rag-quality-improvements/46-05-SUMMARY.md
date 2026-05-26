---
phase: 46-graph-rag-quality-improvements
plan: "05"
subsystem: suggestions
tags: [suggestion-quality, action-hints, provenance, no-write-boundary]
requires:
  - phase: 46-01
    provides: Suggestion quality contracts
  - phase: 46-03
    provides: Retrieval provenance vocabulary
provides:
  - Source-grounded suggestion explanation fields
  - Action hint grounding metadata
  - No-write boundary provenance for Phase 47 handoff
affects: [suggestions, missed-decisions, evals]
tech-stack:
  added: []
  patterns: [quality gates, source-backed action metadata, nested eval completeness]
key-files:
  created: []
  modified:
    - backend/src/services/suggestion_quality.py
    - backend/src/services/missed_decision_suggestions.py
    - backend/src/services/missed_decision_actions.py
    - backend/src/evals/missed_decisions.py
    - backend/evals/datasets/missed_decisions/golden.jsonl
    - backend/tests/test_suggestions.py
    - backend/tests/test_missed_decision_candidates.py
    - backend/tests/test_missed_decision_actions.py
    - backend/tests/test_missed_decision_evals.py
requirements-completed: [GRAG-02, GRAG-04]
duration: 8min
completed: 2026-05-26
---

# Phase 46 Plan 05 Summary

**Suggestion and action-hint payloads now carry deterministic source grounding without adding external writes**

## Performance

- **Started:** 2026-05-26T12:44:00Z
- **Completed:** 2026-05-26T12:52:00Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added shared `grounding_state`, source ref, retrieval signal, required evidence, confidence, and validator fields to suggestion explanations and quality gates.
- Added source-backed action-hint grounding metadata with the explicit `phase_46_metadata_only` no-write boundary.
- Updated missed-decision suggestions to require action-hint grounding when action hints exist, and to preserve quote/link/source/candidate provenance.
- Updated confirmed Decision promotion to preserve candidate ID, source quote/link, action hints, grounding explanation, retrieval signals, and no-write boundary metadata.
- Tightened missed-decision eval payload completeness to require nested explanation and retrieval-signal fields.
- Updated the golden eval action-hint fixture to model the new grounding/no-write payload contract.

## Decisions Made

- Action hints remain inert metadata; Phase 46 records grounding and no-write labels only.
- The shared suggestion quality contract owns action-hint grounding so suggestion publication and Decision promotion use the same vocabulary.
- Suppressed or unsafe suggestions remain testable through the quality assessment helper instead of creating user-visible suggestion rows.

## Deviations from Plan

None - plan scope was executed as written.

## Issues Encountered

- The bundled golden eval fixture initially passed by average threshold while one action-hint case used the old payload shape. The fixture was updated so per-case payload completeness is 1.0.

## Verification

- `uv run --directory backend pytest tests/test_missed_decision_candidates.py tests/test_missed_decision_actions.py tests/test_suggestions.py tests/test_missed_decision_evals.py -q` - passed
- `uv run --directory backend ruff check src/services/suggestion_quality.py src/services/suggestions.py src/services/missed_decision_suggestions.py src/services/missed_decision_actions.py tests/test_suggestions.py tests/test_missed_decision_candidates.py tests/test_missed_decision_actions.py tests/test_missed_decision_evals.py src/evals/missed_decisions.py` - passed
- `uv run --directory backend python -m src.evals.missed_decisions --dataset evals/datasets/missed_decisions/golden.jsonl --json` - passed with payload completeness 1.0
- `rg -n "post_message|create_issue|create_task|send_message|post_comment|external write" backend/src/services/missed_decision_actions.py backend/src/services/missed_decision_suggestions.py` - no matches
- `git diff --check` - passed

## User Setup Required

None.

## Next Phase Readiness

Plan 46-06 can now audit docs, roadmap state, and eval gates against stable retrieval-trace and suggestion/action grounding contracts.

---
*Phase: 46-graph-rag-quality-improvements*
*Completed: 2026-05-26*
