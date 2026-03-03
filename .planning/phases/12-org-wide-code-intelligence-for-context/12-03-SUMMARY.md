---
phase: 12-org-wide-code-intelligence-for-context
plan: 03
subsystem: api, infra
tags: [redis-streams, webhooks, background-worker, code-indexing, polling-fallback]

# Dependency graph
requires:
  - phase: 12-org-wide-code-intelligence-for-context
    provides: code_chunks table, tree-sitter parsing, code_indexer.py orchestrator
provides:
  - Redis Streams code index worker (enqueue_code_index_job, run_code_index_worker)
  - Push webhook handler for incremental re-indexing
  - POST /api/github/index endpoint for manual workspace indexing
  - POST /api/github/index/{repo} endpoint for single-repo indexing
  - GET /api/github/index/status endpoint with per-repo chunk counts
  - Polling fallback for code re-indexing every 60 minutes
affects: [context-generation, embedding-service, frontend-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [Redis Streams consumer group for code indexing, webhook-to-queue pattern, polling freshness check]

key-files:
  created:
    - backend/src/services/code_index_worker.py
    - backend/tests/test_code_index_webhook.py
  modified:
    - backend/src/services/github_webhook.py
    - backend/src/routers/github.py
    - backend/src/main.py
    - backend/src/services/sync_scheduler.py
    - backend/src/services/code_indexer.py

key-decisions:
  - "Redis Streams consumer follows exact embedding_worker.py pattern (STREAM_KEY, GROUP_NAME, xreadgroup loop)"
  - "BATCH_READ_COUNT=5 and BLOCK_MS=10000 for code indexing (heavier than embedding, happens less frequently)"
  - "__all__ sentinel value in repo_full_name signals full workspace re-index vs single repo"
  - "Indexing status tracked in workspace_integrations.config JSONB (code_index_status, code_index_last_at)"
  - "Polling fallback checks code_index_last_at timestamp; re-indexes if >60 minutes stale"
  - "Push webhook handler uses dual approach: handle_push_event (with session) and process_push_event (standalone)"

patterns-established:
  - "Code index worker: same Redis Streams consumer group pattern as embedding_worker"
  - "Webhook-to-queue: push events enqueue async jobs instead of inline processing"
  - "Freshness polling: timestamp-based staleness check for periodic re-indexing"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-03-03
---

# Phase 12 Plan 03: Freshness Pipeline and API Surface Summary

**Redis Streams code index worker with push webhook handler, manual index API endpoints, and 60-minute polling fallback for code freshness**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-03T09:46:47Z
- **Completed:** 2026-03-03T09:53:18Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Redis Streams worker for async code indexing jobs (follows embedding_worker pattern exactly)
- Push webhook handler enqueues incremental re-indexing for monitored repos, silently skips unmonitored
- Three new API endpoints: trigger workspace/repo indexing and monitor status with per-repo chunk counts
- Code index worker registered in FastAPI lifespan for clean start/stop
- Polling fallback re-indexes workspaces whose code_index_last_at exceeds 60 minutes
- Indexing status tracked in workspace_integrations.config JSONB (consistent with sync_status pattern)

## Task Commits

Each task was committed atomically:

1. **Task 1: Code index worker + push webhook handler** - `a45fc0a` (feat)
2. **Task 2: API endpoints + lifespan registration + polling fallback** - `800cf30` (feat)

_Note: Task 1 is TDD -- RED (failing tests) -> GREEN (implementation) phases_

## Files Created/Modified
- `backend/src/services/code_index_worker.py` - Redis Streams consumer for code indexing jobs with enqueue/process/run loop
- `backend/tests/test_code_index_webhook.py` - 4 tests: xadd call, index_repo dispatch, monitored enqueue, unmonitored skip
- `backend/src/services/github_webhook.py` - Added push event dispatch, handle_push_event, process_push_event
- `backend/src/routers/github.py` - Added POST /index, POST /index/{repo}, GET /index/status endpoints
- `backend/src/main.py` - Registered code_index_worker in lifespan startup/shutdown
- `backend/src/services/sync_scheduler.py` - Added _check_code_index_freshness for 60-min polling fallback
- `backend/src/services/code_indexer.py` - Added _update_index_status for JSONB status tracking

## Decisions Made
- Redis Streams code index worker follows the exact pattern of embedding_worker.py (STREAM_KEY, GROUP_NAME, consumer group, xreadgroup loop) for consistency
- Used BATCH_READ_COUNT=5 and BLOCK_MS=10000 since code indexing is heavier and less frequent than embedding
- The `__all__` sentinel value in repo_full_name signals the worker to call index_workspace_repos() instead of index_repo()
- Indexing status (code_index_status, code_index_last_at) stored in workspace_integrations.config JSONB, same pattern as sync_status
- Polling fallback checks code_index_last_at timestamp and re-indexes if more than 60 minutes stale
- Push event handler has dual form: handle_push_event (used within existing session) and process_push_event (standalone with own session)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Code freshness pipeline complete: push webhooks, manual API triggers, and polling fallback all feed into async worker
- Embedding integration wired: code index worker enqueues embedding jobs for all indexed chunks
- Status tracking enables frontend to display indexing progress
- Phase 12 code intelligence infrastructure now complete (Plans 01-03)

## Self-Check: PASSED

All created files verified on disk. Both task commits (a45fc0a, 800cf30) verified in git log.

---
*Phase: 12-org-wide-code-intelligence-for-context*
*Completed: 2026-03-03*
