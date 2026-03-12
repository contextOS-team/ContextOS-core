---
phase: 22-graph-foundation-rule-based-extraction
plan: 01
subsystem: database
tags: [postgres, graph, sqlmodel, rls, recursive-cte, fingerprint, upsert]

# Dependency graph
requires: []
provides:
  - graph_nodes and graph_edges tables with RLS and indexes
  - traverse_graph() SECURITY DEFINER recursive CTE function
  - GraphNode and GraphEdge SQLModel models
  - compute_fingerprint(), upsert_node(), upsert_edge() in graph_ops service
affects: [22-02, 22-03, 23-rule-based-extraction, 24-llm-extraction, 25-graph-search-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [fingerprint-based deduplication, ON CONFLICT upsert with soft-delete restore, SECURITY DEFINER traversal]

key-files:
  created:
    - supabase/migrations/00017_graph_tables.sql
    - supabase/migrations/00018_traverse_graph_function.sql
    - backend/src/models/graph_node.py
    - backend/src/models/graph_edge.py
    - backend/src/services/graph_ops.py
    - backend/tests/test_graph_ops.py
  modified:
    - backend/src/models/__init__.py

key-decisions:
  - "SHA-256 fingerprint from entity_type:external_id for deterministic dedup"
  - "ON CONFLICT upsert clears deleted_at to restore soft-deleted records"
  - "Recursive CTE with path array cycle detection and is_cycle flag filtering"

patterns-established:
  - "Graph fingerprint: hash(entity_type + external_id) for workspace-scoped uniqueness"
  - "Graph upsert: pg_insert ON CONFLICT with named constraints and RETURNING id"
  - "Traversal: SECURITY DEFINER validates workspace once, recursive CTE with direction/depth/type filters"

requirements-completed: [GRAPH-01, GRAPH-02, GRAPH-03]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 22 Plan 01: Graph Schema Foundation Summary

**graph_nodes + graph_edges tables with fingerprint dedup, RLS, recursive CTE traversal, and Python upsert service with 10 passing tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-06T19:54:09Z
- **Completed:** 2026-03-06T19:58:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- graph_nodes table with 11 entity types, fingerprint uniqueness, composite indexes, RLS, moddatetime triggers
- graph_edges table with 11 relationship types, composite unique constraint, traversal indexes, RLS
- traverse_graph() SECURITY DEFINER function with recursive CTE, cycle detection, direction control, depth limiting, entity/relationship type filters
- GraphNode and GraphEdge SQLModel models with JSONB properties and named unique constraints
- graph_ops service with compute_fingerprint(), upsert_node(), upsert_edge() using pg_insert ON CONFLICT
- 10 unit tests all passing: fingerprint determinism, format, uniqueness; upsert statement construction and soft-delete restore

## Task Commits

Each task was committed atomically:

1. **Task 1: Create graph SQL migrations** - `cc0f7da` (feat)
2. **Task 2: Create GraphNode/GraphEdge models and graph_ops service** - `937b2ae` (feat)

## Files Created/Modified
- `supabase/migrations/00017_graph_tables.sql` - graph_nodes and graph_edges DDL with RLS, indexes, triggers
- `supabase/migrations/00018_traverse_graph_function.sql` - traverse_graph() SECURITY DEFINER with recursive CTE
- `backend/src/models/graph_node.py` - GraphNode SQLModel with fingerprint uniqueness
- `backend/src/models/graph_edge.py` - GraphEdge SQLModel with composite unique constraint
- `backend/src/services/graph_ops.py` - Fingerprint computation and async upsert operations
- `backend/tests/test_graph_ops.py` - 10 unit tests for fingerprint and upsert logic
- `backend/src/models/__init__.py` - Added GraphNode and GraphEdge exports

## Decisions Made
- SHA-256 fingerprint from `entity_type:external_id` string for deterministic deduplication across re-ingestion
- ON CONFLICT upsert sets `deleted_at=None` to automatically restore soft-deleted records on re-encounter
- Recursive CTE uses path array for cycle detection with `is_cycle` flag, filtered out in final SELECT

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock chain in upsert tests**
- **Found during:** Task 2 (unit tests)
- **Issue:** MagicMock chain did not account for `.values()` returning a new mock; `on_conflict_do_update.call_args` was None
- **Fix:** Explicitly chained `mock_insert.values.return_value = mock_values` so `on_conflict_do_update` is tracked on the correct mock
- **Files modified:** backend/tests/test_graph_ops.py
- **Verification:** All 10 tests pass
- **Committed in:** 937b2ae (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test fix only, no scope creep.

## Issues Encountered
None beyond the mock chain fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Graph schema foundation complete, ready for rule-based extractors (Plan 02+)
- Tables, models, traversal function, and upsert operations all in place
- All 11 entity types and 11 relationship types supported from day one

---
*Phase: 22-graph-foundation-rule-based-extraction*
*Completed: 2026-03-07*
