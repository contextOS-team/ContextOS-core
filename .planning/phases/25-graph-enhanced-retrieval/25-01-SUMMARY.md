---
phase: 25-graph-enhanced-retrieval
plan: 01
subsystem: api
tags: [graph, retrieval, linking, depth-decay, same-as, traverse-graph]

# Dependency graph
requires:
  - phase: 22-graph-foundation-rule-based-extraction
    provides: "GraphNode/GraphEdge models, graph_ops.py, traverse_graph() SQL function"
  - phase: 23-identity-resolution
    provides: "same_as edges between identity-resolved person nodes"
provides:
  - "_find_graph_results() async function for graph traversal signal"
  - "CONTEXT_TOKEN_BUDGET and GRAPH_MAX_DEPTH config constants"
  - "WEIGHT_GRAPH and DEPTH_DECAY scoring constants"
  - "Entity type mapping for source-backed and graph-only entities"
  - "Test scaffolds for synthesis graph section (Plan 02)"
affects: [25-02-PLAN, 26-context-page-enhancements]

# Tech tracking
tech-stack:
  added: []
  patterns: ["fail-silent graph traversal", "exponential depth-decay scoring", "same_as transparent edge following", "graph provenance metadata in signals"]

key-files:
  created:
    - backend/tests/test_linking_graph.py
    - backend/tests/test_synthesis_graph.py
  modified:
    - backend/src/config.py
    - backend/src/services/linking.py

key-decisions:
  - "Exponential decay (DEPTH_DECAY^depth) for graph scoring -- depth-1 items score 0.48, depth-2 score 0.288"
  - "same_as nodes skipped as results but tracked for path-based depth adjustment"
  - "Graph results capped at 20 to prevent same_as expansion explosion"
  - "Graph-only entities use node_id as source_id with inline title/snippet"
  - "Decision nodes get special [DECISION] highlighting format with metadata fields"

patterns-established:
  - "Graph provenance: signals contain 'graph:EntityType(relationship,d=N)' for debugging"
  - "same_as transparency: count same_as ancestors in path, reduce effective depth"
  - "Graph entity mapping: _GRAPH_ENTITY_TO_SOURCE for source-backed, _GRAPH_ONLY_ENTITIES for inline"

requirements-completed: [GRAPH-SIGNAL, GRAPH-FALLBACK, GRAPH-ERROR, DEPTH-DECAY, SAME-AS]

# Metrics
duration: 7min
completed: 2026-03-08
---

# Phase 25 Plan 01: Graph Signal Summary

**Graph traversal as third retrieval signal with exponential depth-decay scoring, same_as edge transparency, and fail-silent fallback**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-07T23:11:09Z
- **Completed:** 2026-03-07T23:18:11Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Implemented `_find_graph_results()` function that traverses the knowledge graph from a ticket's node and returns scored LinkedItems with graph provenance metadata
- Added CONTEXT_TOKEN_BUDGET=2000 and GRAPH_MAX_DEPTH=2 config constants for Phase 25
- Created 5 passing tests covering all graph signal requirements (signal, fallback, error, depth-decay, same-as)
- Created 3 stub tests for synthesis graph section (Plan 02 scope)

## Task Commits

Each task was committed atomically:

1. **Task 1: Merge graph branch and add config constants** - `8c43c39` (feat)
2. **Task 2 RED: Add failing tests** - `cc2a7c1` (test)
3. **Task 2 GREEN: Implement _find_graph_results()** - `66f49bc` (feat)

## Files Created/Modified
- `backend/src/config.py` - Added CONTEXT_TOKEN_BUDGET=2000 and GRAPH_MAX_DEPTH=2 module-level constants
- `backend/src/services/linking.py` - Added WEIGHT_GRAPH, DEPTH_DECAY, entity mappings, and _find_graph_results() function
- `backend/tests/test_linking_graph.py` - 5 tests for graph signal: basic, no-node, error-silent, depth-decay, same-as
- `backend/tests/test_synthesis_graph.py` - 3 stub tests for Plan 02 (format_graph_section, decision_node_format, generate_includes_graph)

## Decisions Made
- Exponential decay formula: `WEIGHT_GRAPH * (DEPTH_DECAY ** effective_depth)` -- gives depth-1 score 0.48, depth-2 score 0.288
- same_as edges are skipped as results but their node_ids are tracked; when a result's path contains same_as nodes, effective_depth is reduced by the count of same_as ancestors
- Graph results capped at 20 items via _GRAPH_MAX_RESULTS to prevent same_as expansion explosion
- Graph-only entities (Person, Decision, Blocker, Feature, Component) get inline title/snippet from node name and properties, using node_id as source_id
- Decision nodes formatted with `[DECISION] name | By: person | In: source | Affects: tickets | Confidence: X.X`
- Graph branch merge was a no-op since b5b2ab3 was already ancestor of main (Phases 22-24 previously executed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Aborted in-progress rebase to work from main**
- **Found during:** Task 1 (merge graph branch)
- **Issue:** HEAD was in a detached rebase state replaying v1.2 commits onto origin/main. Graph branch merge impossible from detached state.
- **Fix:** Aborted rebase, confirmed graph branch was already ancestor of main, cherry-picked Phase 25 planning commits from reflog onto main.
- **Files modified:** None (git state only)
- **Verification:** All graph files accessible, planning docs restored

**2. [Rule 1 - Bug] Fixed same_as test to set explicit path arrays**
- **Found during:** Task 2 GREEN (implementing _find_graph_results)
- **Issue:** Test mock for PR reached via same_as used auto-generated random paths that didn't include the same_as node's ID, so path-based depth adjustment couldn't detect the same_as ancestor.
- **Fix:** Set explicit node_ids and paths in the test: PR path includes same_as node_id so the implementation correctly reduces effective_depth.
- **Files modified:** backend/tests/test_linking_graph.py
- **Verification:** test_same_as_transparent passes with expected score 0.48

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for correct execution. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `_find_graph_results()` is ready to be integrated into `find_related_content()` (Plan 02 scope)
- Token budget trimming and signal blending still needed (Plan 02)
- Synthesis prompt graph section formatting still needed (Plan 02, stub tests exist)
- All prerequisites for Plan 02 are met

---
*Phase: 25-graph-enhanced-retrieval*
*Completed: 2026-03-08*
