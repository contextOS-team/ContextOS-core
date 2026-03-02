---
phase: 10-sync-engine-improvements
plan: 03
subsystem: api, infra
tags: [asyncio, semaphore, http2, httpx, jitter, retry, incremental-sync, polling, redis-streams]

# Dependency graph
requires:
  - phase: 10-sync-engine-improvements (plan 01)
    provides: SyncRunLogger, SyncAdapter protocol, update_cursor_status
  - phase: 10-sync-engine-improvements (plan 02)
    provides: enqueue_embedding_job(), run_embedding_worker(), BATCH_SIZE, _normalize_for_hash()
provides:
  - Per-provider asyncio.Semaphore concurrency limits (Notion=3, GitHub=10, Linear=5)
  - HTTP/2 enabled on all httpx API clients
  - Jittered retry backoff on all providers
  - Connection pool tuning per provider
  - Metadata-only incremental Notion sync (skip body refetch on unchanged pages)
  - 15-minute polling fallback scheduler for missed webhooks
  - Background worker startup in FastAPI lifespan
  - Redis Streams embedding decoupling across all sync call sites
affects: [sync-engine, notion-sync, linear-sync, github-sync, embedding-pipeline]

# Tech tracking
tech-stack:
  added: [h2 (via httpx[http2])]
  patterns: [asyncio.Semaphore per-provider, jittered exponential backoff, incremental sync via timestamp comparison, polling fallback scheduler, FastAPI lifespan background tasks]

key-files:
  created:
    - backend/src/services/sync_scheduler.py
    - backend/tests/test_sync_concurrency.py
  modified:
    - backend/src/services/notion_client.py
    - backend/src/services/linear_graphql.py
    - backend/src/services/github_common.py
    - backend/src/services/github_sync.py
    - backend/src/routers/notion.py
    - backend/src/services/notion_sync.py
    - backend/src/services/linear_sync.py
    - backend/src/main.py
    - backend/src/services/embedding.py

key-decisions:
  - "Semaphore wraps individual HTTP calls, not entire sync operations, for fine-grained concurrency control"
  - "Jitter formula uses 0.5 + random.random() for 50-150% range per CONTEXT.md specification"
  - "Incremental sync compares last_edited_time before content refetch to skip unchanged pages"
  - "Polling fallback checks first 100 pages per workspace (single search API page)"
  - "Background workers use asyncio.create_task with CancelledError handling for graceful shutdown"

patterns-established:
  - "Per-provider semaphore pattern: module-level asyncio.Semaphore wrapping API calls"
  - "create_github_client() factory function for consistent GitHub httpx configuration"
  - "enqueue_embedding_job() as the single entry point for sync services to queue embeddings"
  - "FastAPI lifespan background tasks with graceful cancellation on shutdown"

requirements-completed: []

# Metrics
duration: 7min
completed: 2026-03-02
---

# Phase 10 Plan 03: Concurrency Controls, HTTP/2, Jittered Retry, Connection Pools, and Incremental Sync Summary

**Per-provider asyncio.Semaphore concurrency limits, HTTP/2 on all httpx clients, jittered retry backoff, Notion incremental sync via timestamp comparison, 15-min polling fallback scheduler, and embedding worker startup in FastAPI lifespan**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-02T05:14:38Z
- **Completed:** 2026-03-02T05:22:34Z
- **Tasks:** 4
- **Files modified:** 12

## Accomplishments
- All three API clients (Notion, Linear, GitHub) now have HTTP/2, connection pool limits, concurrency semaphores, and jittered retry
- Notion sync skips expensive content refetch when page metadata is unchanged (comparing last_edited_time)
- Polling fallback scheduler runs every 15 minutes to catch missed webhook events
- Embedding worker and polling scheduler launch automatically on app startup with graceful shutdown
- All sync services now push to Redis Streams via enqueue_embedding_job() instead of calling queue_embedding_generation() directly

## Task Commits

Each task was committed atomically:

1. **Task 1: Add HTTP/2, connection pools, semaphores, and jittered retry to all API clients** - `3bdb5aa` (feat)
2. **Task 2: Implement incremental sync for Notion and polling fallback scheduler** - `a920afc` (feat)
3. **Task 3: Wire enqueue_embedding_job() into all sync call sites** - `13e73f9` (refactor)
4. **Task 4: Wire startup of embedding worker and polling fallback in main.py lifespan** - `cb52303` (feat)

## Files Created/Modified
- `backend/src/services/notion_client.py` - HTTP/2, Semaphore(3), connection pool, jittered retry
- `backend/src/services/linear_graphql.py` - HTTP/2, Semaphore(5), connection pool, jittered retry
- `backend/src/services/github_common.py` - Semaphore(10), create_github_client(), jittered rate limit sleep
- `backend/src/services/github_sync.py` - Uses create_github_client(), _github_semaphore, enqueue_embedding_job
- `backend/src/routers/notion.py` - Incremental sync timestamp comparison, enqueue_embedding_job
- `backend/src/services/notion_sync.py` - enqueue_embedding_job instead of queue_embedding_generation
- `backend/src/services/linear_sync.py` - enqueue_embedding_job instead of queue_embedding_generation
- `backend/src/services/sync_scheduler.py` - NEW: 15-min polling fallback with reconcile_notion()
- `backend/src/main.py` - Lifespan launches embedding worker and polling fallback as background tasks
- `backend/src/services/embedding.py` - Merge conflict resolved (keep batched approach from 10-02)
- `backend/tests/test_sync_concurrency.py` - NEW: 9 tests for semaphores, HTTP/2, jitter, incremental sync, poll interval

## Decisions Made
- Semaphore wraps individual HTTP calls, not entire sync operations, for fine-grained concurrency control
- Jitter formula uses `0.5 + random.random()` producing 50-150% of base delay per CONTEXT.md specification
- Incremental sync in _run_sync Phase 2 compares last_edited_time before content refetch to skip unchanged pages
- Polling fallback fetches first 100 pages per workspace (single search API call, not full pagination)
- Background workers use asyncio.create_task in FastAPI lifespan with CancelledError handling for graceful shutdown

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Resolved merge conflict in embedding.py**
- **Found during:** Task 3
- **Issue:** embedding.py had unresolved merge conflict markers between the old single-record approach and the new batched approach from Plan 10-02
- **Fix:** Kept the HEAD (batched) approach, removed conflict markers and duplicate import/SOURCE_TYPE_MAP entry
- **Files modified:** backend/src/services/embedding.py
- **Committed in:** 13e73f9 (part of Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix to unblock committing. No scope creep.

## Issues Encountered
- Pre-existing merge conflict in embedding.py blocked the Task 3 commit; resolved by keeping the 10-02 batched approach

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 10 (Sync Engine Improvements) is now complete with all 3 plans delivered
- Sync state management, embedding batching, concurrency controls, incremental sync, and polling fallback all in place
- Ready for Phase 9 (Notion Integration UI Polish) or further development

---
*Phase: 10-sync-engine-improvements*
*Completed: 2026-03-02*
