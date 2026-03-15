---
phase: 31-gitlab-github-sync-performance-optimization
plan: 03
subsystem: api
tags: [asyncio, concurrency, semaphore, code-indexing, performance]

requires:
  - phase: 28-gitlab-code-indexing
    provides: "GitLab code indexing with ensure_valid_token pattern"
  - phase: 07-github
    provides: "GitHub code indexing with index_repo function"
provides:
  - "Concurrent repo indexing with configurable parallelism (MAX_CONCURRENT_CLONES=3)"
  - "Per-repo timeout (REPO_INDEX_TIMEOUT=600s) preventing hung clones"
  - "Isolated DB sessions per concurrent task avoiding SQLAlchemy conflicts"
affects: [code-indexing, github, gitlab, sync-performance]

tech-stack:
  added: []
  patterns: ["asyncio.gather with Semaphore for bounded concurrency", "per-task async_session for DB isolation"]

key-files:
  created: []
  modified:
    - backend/src/services/code_indexer.py

key-decisions:
  - "Semaphore created inside each function (not module-level) to avoid cross-function interference"
  - "Each concurrent task creates its own async_session -- never shares caller session"
  - "TimeoutError caught separately from general Exception for specific error messaging"

patterns-established:
  - "Bounded concurrency: asyncio.Semaphore + asyncio.gather for parallel I/O tasks with resource limits"
  - "Session isolation: async_session() per concurrent task prevents SQLAlchemy session conflicts"

requirements-completed: [PERF-SYNC-03, PERF-SYNC-04]

duration: 2min
completed: 2026-03-15
---

# Phase 31 Plan 03: Concurrent Code Indexing Summary

**asyncio.gather-based concurrent repo indexing with Semaphore(3) parallelism, per-repo 10-minute timeouts, and isolated DB sessions per task**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-15T10:12:51Z
- **Completed:** 2026-03-15T10:14:19Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Both index_workspace_repos (GitHub) and index_gitlab_workspace_repos (GitLab) now process repos concurrently with asyncio.gather
- Configurable parallelism via MAX_CONCURRENT_CLONES=3 constant with asyncio.Semaphore
- Per-repo timeout of 600 seconds prevents hung clones from blocking the entire indexing run
- Each concurrent task uses its own async_session for complete DB session isolation
- Partial failures are logged and skipped without blocking other repos

## Task Commits

Each task was committed atomically:

1. **Task 1: Add concurrent repo indexing with semaphore and per-repo timeout** - `e8cd2fb` (feat)

## Files Created/Modified
- `backend/src/services/code_indexer.py` - Refactored both GitHub and GitLab indexing functions to use asyncio.gather with bounded concurrency, per-task DB sessions, and per-repo timeouts

## Decisions Made
- Semaphore created inside each function (not module-level) to avoid cross-function interference between GitHub and GitLab indexing
- Each concurrent task creates its own async_session to avoid SQLAlchemy session sharing across coroutines
- TimeoutError caught separately from general Exception for specific timeout error messages in results

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Concurrent code indexing ready for production use
- Works with existing embedding pipeline (changed_chunk_ids returned per repo as before)
- No migration or configuration changes needed

---
*Phase: 31-gitlab-github-sync-performance-optimization*
*Completed: 2026-03-15*
