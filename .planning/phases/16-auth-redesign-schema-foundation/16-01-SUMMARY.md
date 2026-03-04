---
phase: 16-auth-redesign-schema-foundation
plan: 01
subsystem: database
tags: [postgres, supabase, rls, pg_cron, onboarding, activity-feed, migrations]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: workspaces, profiles, workspace_members tables, moddatetime extension, handle_new_user trigger
provides:
  - user_onboarding_state table with user-scoped RLS
  - activity_events table with workspace-scoped RLS and composite index
  - Extended handle_new_user trigger (auto-creates onboarding row on signup)
  - pg_cron 30-day retention job for activity_events
affects: [17-onboarding-wizard, 18-activity-timeline, onboarding-gate]

# Tech tracking
tech-stack:
  added: [pg_cron]
  patterns: [user-scoped-rls, exception-wrapped-extension, trigger-extension-pattern]

key-files:
  created:
    - supabase/migrations/00012_onboarding_and_activity.sql
  modified: []

key-decisions:
  - "Extended existing handle_new_user function rather than creating a separate trigger"
  - "NULL onboarding row means legacy user (treated as completed) -- no backfill needed"
  - "pg_cron wrapped in exception handler for local dev compatibility"

patterns-established:
  - "Trigger extension: CREATE OR REPLACE to add logic to shared trigger functions"
  - "Extension guard: DO $$ BEGIN ... EXCEPTION WHEN OTHERS ... END $$ for optional extensions"

requirements-completed: [ACT-04, ONB-07]

# Metrics
duration: 1min
completed: 2026-03-04
---

# Phase 16 Plan 01: Schema Foundation Summary

**user_onboarding_state and activity_events tables with RLS, trigger extension, and pg_cron 30-day retention**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-04T11:06:58Z
- **Completed:** 2026-03-04T11:07:55Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created user_onboarding_state table with user_id PK, current_step (1-4), completed_at, and user-scoped RLS
- Created activity_events table with workspace-scoped RLS, event_type check constraint, and composite index on (workspace_id, created_at DESC)
- Extended handle_new_user trigger to auto-insert onboarding state row on signup
- Added pg_cron daily retention job (3:00 AM UTC) with exception handler for local dev

## Task Commits

Each task was committed atomically:

1. **Task 1: Create migration with both tables, RLS, indexes, and trigger extension** - `7210f6c` (feat)

## Files Created/Modified
- `supabase/migrations/00012_onboarding_and_activity.sql` - Single migration with user_onboarding_state, activity_events, trigger extension, and pg_cron retention job (122 lines)

## Decisions Made
- Extended existing handle_new_user function via CREATE OR REPLACE rather than creating a separate trigger -- keeps all signup logic atomic in one function
- NULL onboarding row for existing users treated as completed -- avoids backfill migration and doesn't lock out legacy users
- pg_cron wrapped in DO/EXCEPTION block so local dev without pg_cron doesn't fail the migration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- user_onboarding_state table ready for Phase 17 (onboarding wizard) and onboarding gate
- activity_events table ready for Phase 18 (activity timeline)
- handle_new_user trigger will auto-create onboarding rows for all new signups
- Existing users (NULL onboarding row) will not be affected

## Self-Check: PASSED

- FOUND: supabase/migrations/00012_onboarding_and_activity.sql
- FOUND: 16-01-SUMMARY.md
- FOUND: commit 7210f6c

---
*Phase: 16-auth-redesign-schema-foundation*
*Completed: 2026-03-04*
