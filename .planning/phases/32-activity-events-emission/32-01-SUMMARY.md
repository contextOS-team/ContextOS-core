---
phase: 32-activity-events-emission
plan: 01
subsystem: api
tags: [activity-events, sync, postgresql, sqlalchemy, fail-silent]

# Dependency graph
requires:
  - phase: 12-onboarding-and-activity
    provides: activity_events table and CHECK constraint
provides:
  - emit_activity() fail-silent helper in sync_adapter.py
  - sync_started/sync_completed events from 5 sync providers
  - context_generated events from synthesis.py
  - DB migration 00031 with 4 new event types
affects: [32-02, 32-03, activity-tab-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns: [fail-silent event emission, raw SQL INSERT with jsonb cast]

key-files:
  created:
    - supabase/migrations/00031_activity_event_types.sql
  modified:
    - backend/src/services/sync_adapter.py
    - backend/src/services/linear_sync.py
    - backend/src/services/github_sync.py
    - backend/src/services/gitlab_sync.py
    - backend/src/services/jira_sync.py
    - backend/src/services/notion_sync.py
    - backend/src/services/synthesis.py

key-decisions:
  - "Slack and Telegram skipped -- no full_sync functions exist (event-driven only, no batch sync)"
  - "emit_activity placed before session.commit() in synthesis.py for transactional consistency"
  - "GitHub/GitLab emit sync_completed at end of sync_repos/sync_projects (covers partial success)"

patterns-established:
  - "emit_activity() pattern: pass existing session, never commit inside, wrap in try/except"
  - "Sync timing pattern: capture time.monotonic() at start, compute duration_ms at end"

requirements-completed: [ACT-05, ACT-07]

# Metrics
duration: 5min
completed: 2026-03-15
---

# Phase 32 Plan 01: Activity Events Emission Summary

**emit_activity() fail-silent helper with sync_started/sync_completed events from 5 providers and context_generated from synthesis.py**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-15T21:00:32Z
- **Completed:** 2026-03-15T21:05:44Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Created emit_activity() fail-silent helper using raw SQL INSERT with jsonb cast in sync_adapter.py
- Expanded activity_events CHECK constraint to 10 event types via migration 00031
- Wired sync_started and sync_completed events into Linear, GitHub, GitLab, Jira, and Notion sync services
- Wired context_generated events into both generate_context_page() and generate_context_page_stream() in synthesis.py
- All error paths emit sync_completed with error=true and truncated error_message

## Task Commits

Each task was committed atomically:

1. **Task 1: DB migration + emit_activity() helper** - `f090cc4` (feat)
2. **Task 2: Wire sync events for 5 providers + context generation** - `7030c83` (feat)

## Files Created/Modified
- `supabase/migrations/00031_activity_event_types.sql` - Expands CHECK constraint to 10 event types
- `backend/src/services/sync_adapter.py` - Added emit_activity() fail-silent helper function
- `backend/src/services/linear_sync.py` - sync_started/sync_completed in sync_tickets_for_teams()
- `backend/src/services/github_sync.py` - sync_started/sync_completed in sync_repos()
- `backend/src/services/gitlab_sync.py` - sync_started/sync_completed in sync_projects()
- `backend/src/services/jira_sync.py` - sync_started/sync_completed in sync_jira_issues()
- `backend/src/services/notion_sync.py` - sync_started/sync_completed in run_full_sync()
- `backend/src/services/synthesis.py` - context_generated in both generation functions

## Decisions Made
- Slack and Telegram have no full_sync() functions -- they are event-driven (webhooks/real-time messages) with no batch sync orchestration, so emit_activity was not wired for these two providers
- emit_activity() placed BEFORE session.commit() in synthesis.py so the activity event is part of the same transaction
- GitHub and GitLab sync_repos/sync_projects handle errors per-repo/per-project internally, so sync_completed is emitted once at the end (covers both success and partial-success)

## Deviations from Plan

### Scope Adjustment

**1. Slack and Telegram providers not wired (5 of 7 providers wired)**
- **Reason:** The plan specified "all 7 sync services" but slack_channels.py is a channel listing utility (no sync orchestration) and telegram_bot.py handles bot connection/disconnection (no data sync). Neither has a full_sync() or equivalent function.
- **Impact:** No functional loss -- these providers don't perform batch data syncing. When/if Slack message backfill or Telegram message sync is added, emit_activity can be wired at that time.
- **All 5 providers that have full_sync are wired: Linear, GitHub, GitLab, Jira, Notion.**

---

**Total deviations:** 1 scope adjustment (2 providers skipped due to missing sync functions)
**Impact on plan:** Minor -- all providers that actually perform batch syncs are wired. No sync functionality lost.

## Issues Encountered
- ruff linter not available in the execution environment -- used Python AST syntax checking as fallback verification

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- emit_activity() helper is ready for Plan 02 (webhook event emission) and Plan 03 (connect/disconnect events)
- Migration 00031 must be applied before events can be written to the database
- All 4 new event types (ticket_created, pr_merged, meeting_recorded, page_created) are in the CHECK constraint, ready for webhook handlers

---
*Phase: 32-activity-events-emission*
*Completed: 2026-03-15*
