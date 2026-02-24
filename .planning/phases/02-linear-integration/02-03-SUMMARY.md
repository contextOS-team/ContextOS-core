---
phase: 02-linear-integration
plan: 03
subsystem: api
tags: [webhooks, hmac, linear, fastapi, idempotency, embedding]

# Dependency graph
requires:
  - phase: 02-linear-integration
    provides: "OAuth token lifecycle, GraphQL client, sync_single_ticket, embedding stub, WebhookDelivery model"
provides:
  - "POST /api/webhooks/linear endpoint with HMAC-SHA256 verification"
  - "Idempotent webhook delivery tracking via Linear-Delivery UUID"
  - "Replay protection via webhookTimestamp validation"
  - "Event-driven ticket/comment upserts for Issue and Comment events"
  - "Selective re-embedding: content changes trigger embeddings, metadata-only changes skip"
  - "is_content_change helper for title/description comparison"
affects: [04-context-synthesis, 05-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [hmac-sha256-webhook-verification, idempotent-delivery-tracking, selective-re-embedding, background-task-delegation]

key-files:
  created:
    - backend/src/routers/webhooks.py
    - backend/src/services/linear_webhook.py
    - backend/tests/test_linear_webhook.py
  modified:
    - backend/src/main.py

key-decisions:
  - "Module-level config import (import src.config) instead of from-import for reliable test patching across test ordering"
  - "Background task delegation for webhook event processing to ensure fast 200 response to Linear"
  - "Webhook service creates its own session via async_session() for background processing isolation"
  - "Comment embedding queued for the comment source_type, not re-embedding the parent ticket"

patterns-established:
  - "Webhook HMAC verification: raw bytes + hmac.compare_digest for timing-safe comparison"
  - "Idempotency via delivery UUID check before processing"
  - "Selective re-embedding: snapshot before upsert, compare after, only queue on content diff"

requirements-completed: [LIN-03, LIN-04]

# Metrics
duration: 17min
completed: 2026-02-24
---

# Phase 02 Plan 03: Linear Webhook Receiver Summary

**HMAC-SHA256 verified webhook endpoint with idempotent delivery tracking, event-driven ticket/comment sync, and selective re-embedding on content changes**

## Performance

- **Duration:** 17 min
- **Started:** 2026-02-24T16:32:13Z
- **Completed:** 2026-02-24T16:49:41Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- POST /api/webhooks/linear endpoint with HMAC-SHA256 signature verification on raw request bytes
- Idempotent delivery tracking via Linear-Delivery header UUID in webhook_deliveries table
- Replay protection via webhookTimestamp validation (60-second window)
- Event processor handling Issue create/update/remove and Comment create/update/remove
- Selective re-embedding: only content changes (title, description) trigger embedding; metadata-only changes (state, assignee, labels) are skipped
- Events for non-synced teams store raw data without generating embeddings
- 18 comprehensive tests covering HMAC, idempotency, all event types, re-embedding logic, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Webhook endpoint with HMAC verification and idempotency** - `4bf71d3` (feat)
2. **Task 2: Webhook event processor and comprehensive tests** - `07db0d8` (feat)

## Files Created/Modified
- `backend/src/routers/webhooks.py` - POST /api/webhooks/linear endpoint with HMAC-SHA256 verification, idempotency, replay protection
- `backend/src/services/linear_webhook.py` - Event processor dispatching to issue/comment handlers with selective re-embedding
- `backend/tests/test_linear_webhook.py` - 18 tests covering signature verification, idempotency, event processing, re-embedding logic
- `backend/src/main.py` - Registered webhooks router

## Decisions Made
- Used `import src.config as config_module` (module-level import) instead of `from src.config import get_settings` in webhooks.py to ensure test settings patching works reliably across test ordering (the `from` import captures the function object at import time, which becomes stale when mock_settings replaces it)
- Background task delegation: webhook endpoint returns 200 immediately and processes events in a FastAPI BackgroundTasks coroutine, matching Linear's expectation of fast responses to avoid retries
- The webhook service creates its own database session via `async_session()` context manager for background processing isolation (not shared with the request session)
- Comment embeddings are queued with source_type="linear_comment" rather than re-embedding the parent ticket, since the embeddings table supports comment-level granularity

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed test dependency injection for webhook settings**
- **Found during:** Task 2
- **Issue:** Endpoint tests failed when run after auth tests because `from src.config import get_settings` captures the function object at import time, and mock_settings replacement doesn't affect this captured reference
- **Fix:** Changed webhooks.py to use `import src.config as config_module` and call `config_module.get_settings()` which always resolves the current module-level function, making test patching reliable
- **Files modified:** backend/src/routers/webhooks.py
- **Verification:** All 30 tests pass when run together (auth + health + webhook)
- **Committed in:** 07db0d8 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed async mock for embedding service calls**
- **Found during:** Task 2
- **Issue:** `patch("src.services.linear_webhook.embedding")` creates a `MagicMock` but `queue_embedding_generation` is an async function, causing `TypeError: object MagicMock can't be used in 'await' expression`
- **Fix:** Added `mock_embedding.queue_embedding_generation = AsyncMock()` after patching the embedding module in all relevant test cases
- **Files modified:** backend/tests/test_linear_webhook.py
- **Verification:** All 18 webhook tests pass
- **Committed in:** 07db0d8 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Linear integration phase complete: OAuth flow, ticket sync, and real-time webhooks all implemented
- Ready for Phase 3 (Slack/Fathom integration) or Phase 4 (context synthesis, which needs Linear data)
- Embedding generation stubs are in place; Phase 4 will implement actual Google GenAI embedding

## Self-Check: PASSED

All created files verified present:
- backend/src/routers/webhooks.py - FOUND
- backend/src/services/linear_webhook.py - FOUND
- backend/tests/test_linear_webhook.py - FOUND
- backend/src/main.py - FOUND (modified)

All commits verified:
- 4bf71d3 (Task 1) - FOUND
- 07db0d8 (Task 2) - FOUND

---
*Phase: 02-linear-integration*
*Completed: 2026-02-24*
