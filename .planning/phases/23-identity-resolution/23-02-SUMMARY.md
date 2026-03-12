---
phase: 23-identity-resolution
plan: 02
subsystem: api, database
tags: [identity-resolution, roster-seeding, rapidfuzz, fuzzy-matching, slack, linear, github, same_as]

# Dependency graph
requires:
  - phase: 23-identity-resolution
    provides: identity_mappings table, IdentityMapping model, resolve_by_email, create_canonical_person, lookup_mapping, resolve_identity_inline
provides:
  - fetch_linear_roster for Linear GraphQL users query
  - fetch_slack_roster for Slack users.list with cursor pagination
  - fetch_github_roster for GitHub collaborators with per-user email lookup
  - upsert_identity_mapping with ON CONFLICT pattern
  - seed_roster orchestrator (upsert + resolve + fuzzy + backfill)
  - compute_name_similarity using rapidfuzz token_sort_ratio
  - find_fuzzy_candidates for candidate same_as edges with confidence scores
  - backfill_identity_resolution for retroactive Person node linking
  - SLACK_BOT_SCOPES updated with users:read.email
  - Roster seeding wired into Linear sync, GitHub sync, and Slack OAuth connect
affects: [24-llm-extraction, 25-graph-enriched-search]

# Tech tracking
tech-stack:
  added: [rapidfuzz>=3.0]
  patterns: [roster-seeding-after-sync, fail-silent-roster-try-except, fuzzy-candidate-edges, confidence-scoring]

key-files:
  created: []
  modified:
    - backend/pyproject.toml
    - backend/src/services/identity_resolution.py
    - backend/src/services/slack_oauth.py
    - backend/src/services/linear_sync.py
    - backend/src/services/github_sync.py
    - backend/tests/test_identity_resolution.py

key-decisions:
  - "Lazy imports for roster functions inside sync flows to avoid circular imports and keep sync modules focused"
  - "Roster seeding is fail-silent with try/except -- integration sync never fails due to identity resolution errors"
  - "Fuzzy name matching uses rapidfuzz token_sort_ratio with threshold 80 and confidence 0.5-0.9"
  - "GitHub roster collects collaborators across all selected repos then deduplicates before per-user email lookup"
  - "Backfill identity resolution only links Person nodes that have platform info in properties"

patterns-established:
  - "Roster seeding pattern: fetch roster -> upsert mappings -> resolve_by_email -> find_fuzzy_candidates -> backfill"
  - "Fail-silent sync integration: lazy import + try/except wrapping roster seeding in all 3 sync flows"
  - "Confidence scoring: normalize name similarity 80-100 to confidence 0.5-0.9, never 1.0 for name-only"
  - "Candidate edge pattern: same_as edges with properties.status=candidate and properties.match_type=fuzzy_name"

requirements-completed: [IDENT-02, IDENT-03]

# Metrics
duration: 8min
completed: 2026-03-07
---

# Phase 23 Plan 02: Roster Seeding and Fuzzy Matching Summary

**Roster seeding from Linear, Slack, and GitHub APIs with rapidfuzz fuzzy name matching, candidate same_as edges, and fail-silent wiring into all sync flows**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-07T15:27:46Z
- **Completed:** 2026-03-07T15:35:28Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Implemented 3 platform roster fetch functions: Linear (GraphQL users query), Slack (users.list with cursor pagination), GitHub (collaborators with per-user email lookup and deduplication across repos)
- Added rapidfuzz-based fuzzy name matching with token_sort_ratio, threshold 80, and confidence scoring 0.5-0.9 for candidate same_as edges
- Wired roster seeding into all 3 sync flows (Linear, GitHub, Slack OAuth) with fail-silent try/except patterns
- Added backfill_identity_resolution to retroactively link pre-existing Person nodes to canonical nodes
- Full test suite passes: 83 tests across 4 test files (25 identity + 58 graph), zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add rapidfuzz dependency, roster fetch functions, and fuzzy name matching** (TDD)
   - `2b69c37` (test: add failing tests for roster fetch, fuzzy matching, and seed_roster)
   - `595e58e` (feat: implement roster fetch, fuzzy matching, and seed_roster orchestration)
2. **Task 2: Wire roster seeding into sync flows, update Slack scopes, and add backfill** - `3589de5` (feat)

## Files Created/Modified
- `backend/pyproject.toml` - Added rapidfuzz>=3.0 dependency
- `backend/src/services/identity_resolution.py` - Added 8 new functions: fetch_linear_roster, fetch_slack_roster, fetch_github_roster, upsert_identity_mapping, seed_roster, compute_name_similarity, find_fuzzy_candidates, backfill_identity_resolution
- `backend/src/services/slack_oauth.py` - Updated SLACK_BOT_SCOPES with users:read.email, added roster seeding after OAuth connect
- `backend/src/services/linear_sync.py` - Added roster seeding after ticket sync completion
- `backend/src/services/github_sync.py` - Added roster seeding after PR sync completion
- `backend/tests/test_identity_resolution.py` - 25 tests total (16 new): roster fetch, fuzzy matching, seed_roster, backfill, Slack scopes

## Decisions Made
- Lazy imports inside sync flow try/except blocks to avoid circular imports and keep sync modules decoupled from identity resolution
- GitHub roster fetches collaborators for ALL selected repos then deduplicates by login before per-user email lookup to minimize API calls
- Fuzzy name matching uses token_sort_ratio (order-insensitive) so "John Smith" and "Smith, John" correctly match
- Confidence scores normalized from 80-100 name score to 0.5-0.9 range, capped at 0.9 since name-only matching has inherent uncertainty
- Backfill only processes Person nodes that have platform/platform_user_id in their properties (not all Person nodes)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock ordering for GitHub deduplication test**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Test mock side_effect order assumed per-user email lookups happened interleaved with collaborator fetches, but the implementation collects all collaborators first then does email lookups
- **Fix:** Reordered mock side_effect to match actual call sequence: [collab_resp1, collab_resp2, alice_resp]
- **Files modified:** backend/tests/test_identity_resolution.py
- **Verification:** All 22 tests pass after fix
- **Committed in:** 595e58e (Task 1 GREEN commit)

**2. [Rule 3 - Blocking] Fixed test patches to use source module paths for lazy imports**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Tests patched `src.services.identity_resolution.get_valid_access_token` but lazy imports inside functions read from source modules, making patches at the identity_resolution module level ineffective
- **Fix:** Changed all test patches to target source modules: `src.services.linear_oauth.get_valid_access_token`, `src.services.slack_oauth.get_bot_token`, etc.
- **Files modified:** backend/tests/test_identity_resolution.py
- **Verification:** All tests correctly intercept lazy imports
- **Committed in:** 595e58e (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes were necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the test mock issues documented above.

## User Setup Required
None - no external service configuration required.

Note: Existing Slack integrations will need re-authorization to gain the `users:read.email` scope. New integrations will automatically request it.

## Next Phase Readiness
- Identity resolution fully operational: roster seeding + email matching + fuzzy candidates + backfill
- All 3 platform sync flows automatically seed rosters on initial sync
- Phase 23 (Identity Resolution) complete -- both plans executed
- Ready for Phase 24 (LLM Extraction) and Phase 25 (Graph-Enriched Search)

## Self-Check: PASSED

All 6 files verified on disk. All 3 task commits verified in git log.

---
*Phase: 23-identity-resolution*
*Completed: 2026-03-07*
