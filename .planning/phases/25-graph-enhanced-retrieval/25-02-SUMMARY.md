---
phase: 25-graph-enhanced-retrieval
plan: 02
subsystem: api
tags: [graph, retrieval, linking, synthesis, token-budget, signal-diversity, decision-highlighting]

# Dependency graph
requires:
  - phase: 25-graph-enhanced-retrieval
    plan: 01
    provides: "_find_graph_results() function, CONTEXT_TOKEN_BUDGET config, WEIGHT_GRAPH/DEPTH_DECAY constants"
provides:
  - "3-way merge in find_related_content() combining explicit + hybrid + graph signals"
  - "_apply_token_budget() with signal diversity guarantee under 2000 token limit"
  - "_format_graph_section() and _format_decision_node() for synthesis prompt"
  - "Separate Graph Connections section in synthesis template"
affects: [26-context-page-enhancements]

# Tech tracking
tech-stack:
  added: []
  patterns: ["token budget trimming with signal diversity", "graph section separation in synthesis prompt", "additive multi-signal scoring"]

key-files:
  created: []
  modified:
    - backend/src/services/linking.py
    - backend/src/services/synthesis.py
    - backend/tests/test_linking_graph.py
    - backend/tests/test_synthesis_graph.py

key-decisions:
  - "Token estimation heuristic: (char_length + 50) // 4 for simple per-item budget calculation"
  - "Signal diversity first: reserve top-1 from each signal group before filling by score"
  - "Graph items separated in synthesis by checking for 'graph:' prefix in signals list"
  - "SYNTHESIS_TEMPLATE updated with {graph_section} placeholder -- empty string when no graph items"

patterns-established:
  - "Signal normalization: graph:*, explicit_link/explicit_reference, hybrid_search mapped to 3 categories"
  - "Budget-first trimming: diversity guarantee -> fill by score -> sort by relevance"
  - "Conditional prompt sections: empty string for absent signal types"

requirements-completed: [MERGE-3WAY, TOKEN-BUDGET, TOKEN-DIVERSITY, GRAPH-SECTION, DECISION-FMT, E2E-MERGE]

# Metrics
duration: 6min
completed: 2026-03-08
---

# Phase 25 Plan 02: 3-Way Merge and Synthesis Integration Summary

**3-signal merge with additive scoring, unified 2000-token budget with signal diversity, and separate Graph Connections section in synthesis prompt with decision node highlighting**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-07T23:21:49Z
- **Completed:** 2026-03-07T23:28:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Wired graph signal as third retrieval source in find_related_content() with additive scoring for overlapping items
- Implemented _apply_token_budget() with signal diversity guarantee ensuring at least 1 result from each signal type
- Added _format_graph_section() and _format_decision_node() for separate Graph Connections section in synthesis prompt
- Updated SYNTHESIS_TEMPLATE with conditional {graph_section} placeholder
- All 11 phase tests green (8 linking graph + 3 synthesis graph), full suite of 519 tests passing

## Task Commits

Each task was committed atomically (TDD: test -> feat):

1. **Task 1 RED: Failing tests for 3-way merge and token budget** - `f97b469` (test)
2. **Task 1 GREEN: Implement 3-way merge and token budget** - `bbd87be` (feat)
3. **Task 2 RED: Failing tests for graph section in synthesis** - `6ebb23c` (test)
4. **Task 2 GREEN: Graph section formatting and synthesis integration** - `8f886d5` (feat)

## Files Created/Modified
- `backend/src/services/linking.py` - Added _estimate_tokens(), _normalize_signal(), _apply_token_budget(); wired graph into find_related_content() 3-way merge
- `backend/src/services/synthesis.py` - Added _format_decision_node(), _format_graph_section(), GRAPH_SECTION_TEMPLATE; updated SYNTHESIS_TEMPLATE and generate_context_page()
- `backend/tests/test_linking_graph.py` - Added 3 tests: test_three_signal_merge, test_token_budget_basic, test_token_budget_diversity
- `backend/tests/test_synthesis_graph.py` - Replaced 3 stubs with real tests: test_format_graph_section, test_decision_node_format, test_generate_includes_graph

## Decisions Made
- Token estimation uses simple heuristic (char_length + 50) // 4 rather than actual tokenizer -- good enough for budget trimming, avoids dependency
- Signal normalization maps graph:* to "graph", explicit_link/explicit_reference to "explicit", hybrid_search to "hybrid" for grouping
- Graph items identified by checking for "graph:" prefix in signals list -- clean separation without type flag
- SYNTHESIS_TEMPLATE gets {graph_section} as empty string when no graph items -- no visible "Graph Connections" header in non-graph prompts

## Deviations from Plan

### Skipped Items

**1. find_content_by_source() wiring (not applicable)**
- **Reason:** Function `find_content_by_source()` referenced in plan does not exist in the codebase. The plan's interfaces section listed it but it was never implemented.
- **Impact:** None -- function doesn't exist, so no wiring needed.

**2. generate_context_page_stream() update (not applicable)**
- **Reason:** Function `generate_context_page_stream()` referenced in plan does not exist in the codebase. Only `generate_context_page()` exists and was updated.
- **Impact:** None -- when streaming is implemented in the future, it will need to include graph section logic.

---

**Total deviations:** 2 skipped items (referenced functions don't exist)
**Impact on plan:** No functional impact. All existing functions updated correctly. Future implementations will need graph section logic.

## Issues Encountered
None -- plan executed cleanly after accounting for missing functions.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 25 (Graph-Enhanced Retrieval) is fully complete
- All 6 requirements met: MERGE-3WAY, TOKEN-BUDGET, TOKEN-DIVERSITY, GRAPH-SECTION, DECISION-FMT, E2E-MERGE
- Graph results now flow from discovery through scoring, budget trimming, and into synthesis prompt
- Ready for Phase 26 (Context Page Enhancements) which builds on this retrieval foundation

## Self-Check: PASSED

All 4 modified files verified on disk. All 4 commit hashes verified in git log.

---
*Phase: 25-graph-enhanced-retrieval*
*Completed: 2026-03-08*
