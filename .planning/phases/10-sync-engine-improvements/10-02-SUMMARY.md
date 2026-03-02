---
phase: 10-sync-engine-improvements
plan: 02
subsystem: api, database, infra
tags: [openai, redis-streams, embeddings, batch-api, content-hashing, async-worker]

# Dependency graph
requires:
  - phase: 10-sync-engine-improvements
    provides: sync_cursors table and SyncAdapter protocol from plan 01
provides:
  - Batch embedding generation (generate_embeddings_batch) for 25-text-per-API-call efficiency
  - Redis Streams embedding worker (enqueue_embedding_job, run_embedding_worker) for async decoupling
  - Content hash normalization (_normalize_for_hash) to prevent trivial re-embedding
  - Model version tracking (model_name, model_version) on embeddings table
  - BATCH_SIZE, EMBEDDING_MODEL_NAME, EMBEDDING_MODEL_VERSION constants
affects: [10-sync-engine-improvements plan 03, sync services, embedding pipeline consumers]

# Tech tracking
tech-stack:
  added: [httpx[http2], redis.asyncio (Redis Streams)]
  patterns: [batch API calls with configurable BATCH_SIZE, Redis Streams consumer group pattern, whitespace-normalized content hashing]

key-files:
  created:
    - backend/src/services/embedding_worker.py
    - backend/tests/test_embedding_pipeline.py
    - supabase/migrations/00008_embedding_model_version.sql
  modified:
    - backend/src/services/embedding.py
    - backend/src/models/embedding.py
    - backend/pyproject.toml

key-decisions:
  - "BATCH_SIZE=25 chosen as safe middle ground within 20-50 range from CONTEXT.md"
  - "Redis Streams consumer group pattern with BUSYGROUP-tolerant group creation"
  - "Whitespace normalization via re.sub(r'\\s+', ' ', text).strip() before SHA-256 hashing"
  - "enqueue_embedding_job creates and closes Redis connection per call for simplicity"

patterns-established:
  - "Batch embedding: collect pending records first, then process in BATCH_SIZE chunks"
  - "Redis Streams: XADD for enqueue, XREADGROUP with consumer groups for dequeue, XACK after processing"
  - "Content hash normalization: collapse whitespace before hashing to avoid trivial re-embedding"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-03-02
---

# Phase 10 Plan 02: Embedding Pipeline Optimization Summary

**Batch OpenAI embedding API (25 texts/call), Redis Streams async worker, whitespace-normalized content hashing, and model version tracking on embeddings table**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-02T05:05:00Z
- **Completed:** 2026-03-02T05:10:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Batch embedding generation sends up to 25 texts per OpenAI API call instead of one-at-a-time, reducing API round trips
- Redis Streams-based embedding worker decouples embedding generation from sync -- syncs can complete without waiting for OpenAI
- Content hash normalization prevents re-embedding when only whitespace/formatting changes occur
- Model version columns (model_name, model_version) enable future selective re-embedding on model upgrades
- 9 new tests covering normalization, batching, Redis enqueue, and constant validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add model version columns and normalize content hashing** - `fff7900` (feat) -- merged with Task 2 since Task 1 changes were pre-applied by plan 10-01 executor
2. **Task 2: Implement batch embedding generation and Redis Streams decoupling** - `fff7900` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `supabase/migrations/00008_embedding_model_version.sql` - Add model_name and model_version columns to embeddings table
- `backend/src/models/embedding.py` - Add model_name and model_version fields to Embedding SQLModel
- `backend/src/services/embedding.py` - Batch generation, content hash normalization, BATCH_SIZE constant, model version constants
- `backend/src/services/embedding_worker.py` - Redis Streams consumer with enqueue_embedding_job and run_embedding_worker
- `backend/pyproject.toml` - httpx upgraded to httpx[http2] for HTTP/2 support
- `backend/tests/test_embedding_pipeline.py` - 9 tests for normalization, batching, Redis enqueue, constants

## Decisions Made
- BATCH_SIZE=25 chosen as safe middle ground within the 20-50 range specified in CONTEXT.md
- Redis Streams consumer group pattern with BUSYGROUP-tolerant group creation for idempotent startup
- Whitespace normalization uses `re.sub(r'\s+', ' ', text).strip()` before SHA-256 hashing
- enqueue_embedding_job creates and closes Redis connection per call (simple, no connection pool needed yet)
- queue_embedding_generation refactored to collect-then-batch pattern: gather all pending records first, then process in BATCH_SIZE chunks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 10-02-01 changes pre-applied by plan 10-01 executor**
- **Found during:** Task 1 (model version columns and content hashing)
- **Issue:** The plan 10-01 executor had already committed the migration, model changes, and content hash normalization as part of its sync adapter commit, but those changes were lost when the commit was recreated without them
- **Fix:** Changes were still in the working tree; included them in the combined Task 1+2 commit
- **Files modified:** backend/src/models/embedding.py, backend/src/services/embedding.py, supabase/migrations/00008_embedding_model_version.sql
- **Verification:** Model imports work, normalization function tested, migration file exists
- **Committed in:** fff7900 (combined commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor -- Task 1 and Task 2 were combined into a single commit since Task 1 was partially pre-applied. No scope creep.

## Issues Encountered
- Plan 10-01 executor had over-committed embedding changes that belong to plan 10-02, but those changes were lost during a commit rewrite. The working tree still had the correct state, so no re-implementation was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Embedding pipeline is fully optimized with batching and async worker
- Plan 10-03 can proceed with concurrency controls, HTTP/2 tuning, and connection pool configuration
- Sync services can be rewired to use enqueue_embedding_job() instead of queue_embedding_generation() directly (as noted in plan)

## Self-Check: PASSED

- FOUND: supabase/migrations/00008_embedding_model_version.sql
- FOUND: backend/src/services/embedding_worker.py
- FOUND: backend/tests/test_embedding_pipeline.py
- FOUND: .planning/phases/10-sync-engine-improvements/10-02-SUMMARY.md
- FOUND: commit fff7900

---
*Phase: 10-sync-engine-improvements*
*Completed: 2026-03-02*
