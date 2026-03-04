---
phase: 18-activity-timeline
plan: 01
subsystem: database, ui
tags: [supabase, realtime, typescript, lucide-react, tdd]

requires:
  - phase: 16-auth-redesign-schema
    provides: "activity_events table schema from migration 00012"
provides:
  - "Supabase Realtime publication for activity_events"
  - "ActivityEvent TypeScript type and EventType union"
  - "EVENT_ICONS map (Lucide icons per event type)"
  - "6 formatter functions: descriptions, timestamps, day labels, metadata chips, day grouping"
affects: [18-02, 19-context-feed-dashboard-home]

tech-stack:
  added: []
  patterns: ["TDD red-green for pure formatter functions", "Co-located formatters with feature (not lib/utils)"]

key-files:
  created:
    - supabase/migrations/00013_realtime_activity.sql
    - apps/web/src/app/dashboard/activity/types.ts
    - apps/web/src/app/dashboard/activity/formatters.ts
    - apps/web/src/app/dashboard/activity/__tests__/formatters.test.ts
  modified: []

key-decisions:
  - "Co-located formatters instead of lib/utils — timeline formatters have different rules (absolute time after 24h vs 'd ago')"
  - "Defensive metadata access with ?? 'Unknown' fallback for integration name"
  - "TDD approach for formatters — tests written first then implementation"

patterns-established:
  - "Feature-scoped types: types.ts + formatters.ts co-located in feature directory"
  - "EVENT_ICONS as Record<EventType, LucideIcon> for type-safe icon lookup"
  - "Midnight-aligned date comparison for day label grouping"

requirements-completed: [ACT-01, ACT-02]

duration: 28min
completed: 2026-03-04
---

# Phase 18 Plan 01: Realtime Migration & TypeScript Contracts Summary

**Supabase Realtime publication for activity_events + full TypeScript contract layer (types, icons, formatters) with TDD**

## Performance

- **Duration:** 28 min
- **Completed:** 2026-03-04
- **Tasks:** 2
- **Files created:** 4

## Accomplishments
- Enabled Supabase Realtime for activity_events via ALTER PUBLICATION migration
- Created ActivityEvent type, EventType union, and EVENT_ICONS map matching DB schema
- Implemented 6 formatter functions with full test coverage via TDD
- formatEventDescription produces impersonal descriptions with metadata integration name
- formatTimelineTimestamp shows relative time (<24h) or absolute time (24h+)
- groupEventsByDay creates day-bucketed structure for timeline rendering

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Realtime publication migration** - `85b2096` (feat)
2. **Task 2: TDD RED - failing tests for formatters** - `ecb4122` (test)
3. **Task 2: TDD GREEN - implement formatters** - `89d1ed0` (feat)

## Files Created/Modified
- `supabase/migrations/00013_realtime_activity.sql` - ALTER PUBLICATION for Realtime
- `apps/web/src/app/dashboard/activity/types.ts` - ActivityEvent, EventType, EVENT_ICONS
- `apps/web/src/app/dashboard/activity/formatters.ts` - 6 pure formatter functions
- `apps/web/src/app/dashboard/activity/__tests__/formatters.test.ts` - TDD tests

## Decisions Made
- Co-located formatters in feature directory instead of lib/utils (different time rules)
- Defensive metadata access with nullish coalescing fallbacks

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All TypeScript contracts ready for Plan 02 to import
- Realtime publication enables live event streaming
- Plan 02 can build ActivityTimeline component consuming these contracts

---
*Phase: 18-activity-timeline*
*Completed: 2026-03-04*
