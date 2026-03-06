---
phase: 20-settings-page
plan: 01
subsystem: api
tags: [fastapi, sqlmodel, api-keys, rls, postgres, sha256]

# Dependency graph
requires:
  - phase: 16-auth-redesign
    provides: "Auth schema, workspace model, RLS helper function"
provides:
  - "api_keys table with RLS and indexes"
  - "API key CRUD service (generate, create, list, revoke)"
  - "5 settings endpoints on workspaces router"
  - "Workspace name update with validation"
  - "Team member listing with profile join"
affects: [20-settings-page]

# Tech tracking
tech-stack:
  added: []
  patterns: ["SHA-256 key hashing with cos_ prefix", "prefix-only display for stored keys"]

key-files:
  created:
    - supabase/migrations/00016_api_keys.sql
    - backend/src/models/api_key.py
    - backend/src/services/api_key.py
  modified:
    - backend/src/routers/workspaces.py
    - backend/src/services/workspace.py

key-decisions:
  - "ApiKey uses SQLModel directly (not BaseModel) -- no updated_at/deleted_at needed for keys"
  - "RLS policies use get_user_workspace_ids() for SELECT, INSERT, UPDATE on api_keys"
  - "Full API key shown once at creation, only prefix stored for display"

patterns-established:
  - "API key format: cos_{64-char-hex} with cos_{8-char} prefix for display"
  - "Soft-revoke via revoked_at timestamp instead of hard delete"

requirements-completed: [SET-01, SET-02, SET-03]

# Metrics
duration: 2min
completed: 2026-03-06
---

# Phase 20 Plan 01: Settings Backend Summary

**API key CRUD with SHA-256 hashing, workspace name update, and team member listing endpoints on the existing workspaces router**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-06T06:07:02Z
- **Completed:** 2026-03-06T06:09:46Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created api_keys migration with RLS policies matching existing workspace security pattern
- Built complete API key lifecycle: generate (cos_ prefix), create, list (prefix-only), revoke (soft-delete)
- Extended workspaces router with 5 new endpoints without touching main.py registration

## Task Commits

Each task was committed atomically:

1. **Task 1: Database migration and API key model** - `91444a0` (feat)
2. **Task 2: API key service and all backend endpoints** - `6fa127c` (feat)

## Files Created/Modified
- `supabase/migrations/00016_api_keys.sql` - API keys table with RLS and two indexes
- `backend/src/models/api_key.py` - ApiKey SQLModel mapping to api_keys table
- `backend/src/services/api_key.py` - Key generation, creation, listing, revocation
- `backend/src/services/workspace.py` - Added update_workspace_name and list_workspace_members
- `backend/src/routers/workspaces.py` - 5 new endpoints: POST/GET/DELETE api-keys, PATCH workspace, GET members

## Decisions Made
- ApiKey model uses SQLModel directly instead of BaseModel -- keys don't need updated_at or deleted_at columns, revoked_at serves the soft-delete purpose
- RLS policies cover SELECT, INSERT, and UPDATE (not DELETE since revocation is via UPDATE)
- Full API key is only returned in the POST response; GET returns prefix-only for security

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 5 backend endpoints ready for frontend consumption in Plan 02
- Migration ready to apply with `supabase db reset`
- No blockers for settings page UI implementation

## Self-Check: PASSED

All 5 created/modified files verified on disk. Both task commits (91444a0, 6fa127c) verified in git log.

---
*Phase: 20-settings-page*
*Completed: 2026-03-06*
