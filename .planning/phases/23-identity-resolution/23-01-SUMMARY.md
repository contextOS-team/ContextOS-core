---
phase: 23-identity-resolution
plan: 01
subsystem: database, api
tags: [identity-resolution, graph, postgres, sqlmodel, same_as, canonical-person]

# Dependency graph
requires:
  - phase: 22-graph-foundation-rule-based-extraction
    provides: graph_nodes/graph_edges tables, upsert_node/upsert_edge, extract_and_populate_graph pipeline, MentionExtractor creating Person nodes
provides:
  - identity_mappings table with workspace-scoped RLS and email/platform indexes
  - IdentityMapping SQLModel for cross-platform person mapping
  - resolve_by_email for email-based deterministic matching to canonical Person nodes
  - create_canonical_person for canonical Person graph node creation
  - lookup_mapping for platform identity lookup
  - resolve_identity_inline hook in extract_and_populate_graph for real-time resolution
affects: [23-02-roster-seeding, 24-llm-extraction, 25-graph-enriched-search]

# Tech tracking
tech-stack:
  added: []
  patterns: [canonical-person-node, same_as-edge-linking, inline-identity-resolution, email-based-deterministic-matching]

key-files:
  created:
    - supabase/migrations/00019_identity_mappings.sql
    - backend/src/models/identity_mapping.py
    - backend/src/services/identity_resolution.py
    - backend/tests/test_identity_resolution.py
  modified:
    - backend/src/models/__init__.py
    - backend/src/services/graph_extractor.py

key-decisions:
  - "Canonical Person nodes use external_id='canonical:{UUID}' for stable fingerprint decoupled from email changes"
  - "resolve_by_email groups by email and assigns shared canonical_person_id to all mappings in group"
  - "_create_same_as_edge looks up platform Person nodes by computed fingerprint for edge creation"
  - "Inline resolution is fail-silent matching Phase 22-03 pattern -- errors logged but never raised"

patterns-established:
  - "Canonical Person pattern: hash('Person:canonical:{UUID}') fingerprint for canonical nodes with properties.canonical=True"
  - "Inline resolution hook: lazy import inside extract_and_populate_graph for Person entity types"
  - "Email-based grouping: deterministic matching anchored on email, never auto-merge on name alone"

requirements-completed: [IDENT-01]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 23 Plan 01: Identity Resolution Foundation Summary

**Email-based deterministic identity resolution with canonical Person nodes, same_as edges, and inline resolution hook in graph extraction pipeline**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T15:19:25Z
- **Completed:** 2026-03-07T15:24:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created identity_mappings table with workspace-scoped RLS, fingerprint deduplication on (workspace_id, platform, platform_user_id), and email/canonical indexes
- Implemented email-based deterministic matching that groups same-email mappings under one canonical Person graph node with same_as edges
- Hooked inline resolution into extract_and_populate_graph so Person entities are automatically linked to canonical nodes during content extraction
- Full graph test suite passes: 67 tests (9 new identity + 58 existing), zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create identity_mappings migration, model, and core resolution service** (TDD)
   - `27ea7e1` (test: add failing tests for identity resolution)
   - `7835143` (feat: implement identity mappings table, model, and resolution service)
2. **Task 2: Hook inline resolution into extract_and_populate_graph** - `42e0639` (feat)

## Files Created/Modified
- `supabase/migrations/00019_identity_mappings.sql` - Identity mappings table DDL with RLS, indexes, moddatetime trigger
- `backend/src/models/identity_mapping.py` - IdentityMapping SQLModel with workspace-scoped unique constraint
- `backend/src/models/__init__.py` - Added IdentityMapping export
- `backend/src/services/identity_resolution.py` - Core resolution: resolve_by_email, create_canonical_person, lookup_mapping, resolve_identity_inline
- `backend/src/services/graph_extractor.py` - Added inline identity resolution hook after Person entity node creation
- `backend/tests/test_identity_resolution.py` - 9 unit tests covering all resolution functions

## Decisions Made
- Canonical Person nodes use `external_id='canonical:{UUID}'` so fingerprint is stable even if email changes (UUID comes from mapping table)
- `_create_same_as_edge` computes expected platform Person fingerprint from `platform:platform_user_id` to find the platform node for edge creation
- Inline resolution uses lazy import inside the function to match existing graph_ops import pattern in extract_and_populate_graph
- `resolve_identity_inline` is fail-silent (try/except with logging), matching the Phase 22-03 pattern where graph extraction never blocks core ingestion

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tests needed _create_same_as_edge patched in resolve_by_email tests**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** resolve_by_email calls `_create_same_as_edge` which calls `session.execute` for platform node lookup, but test mock side_effects only provided results for the group-by and fetch queries
- **Fix:** Added patch for `_create_same_as_edge` in resolve_by_email tests since those tests focus on email grouping logic, not edge creation details
- **Files modified:** backend/tests/test_identity_resolution.py
- **Verification:** All 6 tests pass after fix
- **Committed in:** 7835143 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test mock adjustment. No scope creep.

## Issues Encountered
None beyond the test mock issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Identity mapping infrastructure ready for roster seeding (Plan 23-02)
- `resolve_by_email` ready to be called after roster pulls from Linear, Slack, GitHub
- Inline resolution automatically links Person entities to canonical nodes as content arrives
- `lookup_mapping` available for any service needing to check if a platform user has an identity mapping

## Self-Check: PASSED

All 7 files verified on disk. All 3 commits verified in git log.

---
*Phase: 23-identity-resolution*
*Completed: 2026-03-07*
