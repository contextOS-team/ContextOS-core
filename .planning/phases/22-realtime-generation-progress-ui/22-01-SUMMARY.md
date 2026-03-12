---
phase: 22-realtime-generation-progress-ui
plan: 01
subsystem: api
tags: [sse, streaming, fastapi, sse-starlette, async-generator]

# Dependency graph
requires:
  - phase: 12-code-intel
    provides: "linking engine with find_related_content and hybrid search"
provides:
  - "SSE streaming endpoint GET /api/context/{ticket_identifier}/generate-stream"
  - "find_content_by_source async generator for per-source content grouping"
  - "generate_context_page_stream async generator with SSE event protocol"
affects: [22-02, 22-03]

# Tech tracking
tech-stack:
  added: [sse-starlette]
  patterns: [async-generator-sse, per-source-content-grouping, dedicated-session-in-sse-generator]

key-files:
  created: []
  modified:
    - backend/src/services/linking.py
    - backend/src/services/synthesis.py
    - backend/src/routers/context.py
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "Dedicated session inside SSE generator (not Depends) to avoid FastAPI closing session before stream ends"
  - "Query all sources upfront then group by source type, not per-source DB queries -- reuses existing linking engine"
  - "Connected integrations detected via oauth_tokens table, linear always assumed connected"
  - "Concurrent generation check returns error SSE event rather than HTTP error"

patterns-established:
  - "SSE generator pattern: async with async_session() inside event_generator, commit after stream, rollback on error"
  - "Source grouping via SOURCE_TYPE_MAP dict mapping provider names to source_type strings"

requirements-completed: [GEN-01, GEN-06]

# Metrics
duration: 3min
completed: 2026-03-07
---

# Phase 22 Plan 01: Backend SSE Streaming Summary

**SSE streaming endpoint with per-source progress events using sse-starlette and async generators**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-07T09:29:06Z
- **Completed:** 2026-03-07T09:32:04Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Installed sse-starlette and added find_content_by_source() async generator that groups linked items by source type
- Added generate_context_page_stream() that yields SSE event dicts (start, step_start, step_complete, complete, error)
- Added GET /{ticket_identifier}/generate-stream SSE endpoint with concurrent generation guard
- Existing POST /generate endpoint remains completely unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Install sse-starlette and add per-source content finding** - `dda7928` (feat)
2. **Task 2: Add streaming generation function and SSE endpoint** - `002c4f6` (feat)

## Files Created/Modified
- `backend/src/services/linking.py` - Added SOURCE_TYPE_MAP and find_content_by_source() async generator
- `backend/src/services/synthesis.py` - Added generate_context_page_stream() with SSE event protocol
- `backend/src/routers/context.py` - Added GET /{ticket_identifier}/generate-stream SSE endpoint
- `backend/pyproject.toml` - Added sse-starlette dependency
- `backend/uv.lock` - Updated lockfile

## Decisions Made
- Used dedicated session inside SSE generator (not FastAPI Depends) because Depends sessions close when response object returns, which for SSE is immediately before stream ends
- Reused existing _find_explicit_refs and _find_hybrid_matches queries with post-hoc grouping rather than per-source DB queries
- Linear always included as connected source (required by onboarding), other sources checked via oauth_tokens
- Concurrent generation returns SSE error event rather than HTTP 409 to keep client-side handling uniform

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SSE endpoint ready for frontend consumption in Plan 02
- Event protocol (start, step_start, step_complete, complete, error) defined and ready for client parsing
- Plan 03 (error handling and reconnection) can build on this foundation

---
*Phase: 22-realtime-generation-progress-ui*
*Completed: 2026-03-07*
