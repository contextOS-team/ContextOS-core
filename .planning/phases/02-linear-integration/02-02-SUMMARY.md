---
phase: 02-linear-integration
plan: 02
subsystem: api
tags: [graphql, linear-api, httpx, cursor-pagination, rate-limiting, background-tasks, upsert, sqlalchemy, embedding]

# Dependency graph
requires:
  - phase: 02-linear-integration
    plan: 01
    provides: "Linear OAuth flow, get_valid_access_token, Vault token storage, WorkspaceIntegration model"
  - phase: 01-foundation
    provides: "BaseModel, TimestampMixin, Settings, get_current_user, async session"
provides:
  - "LinearGraphQLClient with auth, pagination, and 429 exponential backoff"
  - "LinearTicket and LinearComment SQLModel models"
  - "Sync orchestration: fetch_teams, sync_tickets_for_teams, sync_single_ticket"
  - "Embedding generation stub with correct signatures for Phase 4"
  - "GET /api/linear/teams, POST /api/linear/sync, GET /api/linear/sync/status endpoints"
affects: [02-03-PLAN, 04-context-synthesis]

# Tech tracking
tech-stack:
  added: []
  patterns: [graphql-client-with-pagination, background-sync-task, postgresql-upsert-on-conflict, decoupled-embedding-stub]

key-files:
  created:
    - backend/src/services/linear_graphql.py
    - backend/src/services/linear_sync.py
    - backend/src/services/embedding.py
    - backend/src/models/ticket.py
    - backend/tests/test_linear_sync.py
  modified:
    - backend/src/models/__init__.py
    - backend/src/routers/linear.py

key-decisions:
  - "Raw httpx GraphQL client (no SDK) per project decision; bare token auth (not Bearer) per Linear spec"
  - "Exponential backoff on 429: 1s initial, 2x multiplier, max 3 retries; respects Retry-After header"
  - "Sync runs as FastAPI BackgroundTasks per user decision on background job mechanism"
  - "Sync progress stored inline in workspace_integrations.config JSONB (sync_status, tickets_synced, last_sync_at)"
  - "Embedding generation fully decoupled: stub logs request, actual implementation deferred to Phase 4"

patterns-established:
  - "GraphQL pagination pattern: fetch_all_pages with connection_path and cursor tracking"
  - "PostgreSQL upsert pattern: insert().on_conflict_do_update() via sqlalchemy.dialects.postgresql"
  - "Background sync pattern: endpoint returns immediately, task updates integration config for progress"
  - "Embedding stub pattern: correct function signatures established, implementation deferred"

requirements-completed: [LIN-02]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 2 Plan 2: Linear Ticket Sync Summary

**GraphQL client with cursor pagination and 429 backoff, full ticket sync with upsert, team selection, and decoupled embedding stub**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T16:25:04Z
- **Completed:** 2026-02-24T16:29:31Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- LinearGraphQLClient with auth, cursor-based pagination, and exponential backoff on 429 responses
- Full ticket sync pipeline: fetch teams, sync tickets for selected teams, upsert tickets+comments with ON CONFLICT
- 3 new API endpoints: team list, sync start (background), sync status with ticket count
- 11 tests covering GraphQL client, sync logic, pagination, backoff, and endpoint behavior
- Embedding generation decoupled as stub with correct signatures for Phase 4

## Task Commits

Each task was committed atomically:

1. **Task 1: GraphQL client, ticket/comment models, and sync service** - `f1910f5` (feat)
2. **Task 2: Sync and team selection endpoints with tests** - `e67e145` (feat)

## Files Created/Modified
- `backend/src/services/linear_graphql.py` - Reusable async GraphQL client with auth, pagination, rate limit backoff
- `backend/src/services/linear_sync.py` - Sync orchestration: fetch_teams, sync_tickets_for_teams, sync_single_ticket, upsert helpers
- `backend/src/services/embedding.py` - Embedding generation stub (queue, generate, process_pending)
- `backend/src/models/ticket.py` - LinearTicket and LinearComment SQLModel table models
- `backend/src/models/__init__.py` - Re-exported LinearTicket, LinearComment
- `backend/src/routers/linear.py` - Added /teams, /sync, /sync/status endpoints
- `backend/tests/test_linear_sync.py` - 11 tests for GraphQL client, sync service, and endpoints

## Decisions Made
- Used bare token auth (not "Bearer") per Linear API spec -- Authorization header is just the token value
- Exponential backoff on 429: 1s initial delay, 2x multiplier, max 3 retries; respects Retry-After header when present
- Sync runs as FastAPI BackgroundTasks (returns immediately to caller)
- Sync progress stored in workspace_integrations.config JSONB: sync_status, tickets_synced, last_sync_at, synced_teams
- Embedding generation fully decoupled -- stub logs requests, Phase 4 will implement actual Google GenAI calls

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failure in `test_linear_oauth.py::TestConnect::test_connect_returns_authorization_url` detected during full test suite run. This is a fixture issue from Plan 02-01 where `linear_settings` patches `get_settings` in `src.routers.linear` but the Settings `Depends(get_settings)` resolves from `src.config`. Not caused by Plan 02-02 changes -- out of scope per deviation rules.

## User Setup Required
None - no external service configuration required. All tests pass with mocked dependencies.

## Next Phase Readiness
- sync_single_ticket() ready for Plan 02-03 (webhook handler) to use for real-time ticket updates
- GraphQL client reusable for any future Linear API calls
- Embedding stub signatures established for Phase 4 implementation
- Team selection and sync status endpoints ready for frontend consumption

## Self-Check: PASSED

All files verified present on disk. All commit hashes verified in git log.

---
*Phase: 02-linear-integration*
*Completed: 2026-02-24*
