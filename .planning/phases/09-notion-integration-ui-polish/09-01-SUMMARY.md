---
phase: 09-notion-integration-ui-polish
plan: 01
subsystem: ui
tags: [react, nextjs, notion, integration-card, ux-polish]

# Dependency graph
requires:
  - phase: 08.1.1-notion-integration
    provides: "Notion integration card with NotionPages component, OAuth flow, sync"
provides:
  - "Simplified Notion card with summary stats on face (page count + last sync time)"
  - "last_sync_at field in unified integration status endpoint"
  - "Clean Notion card header (workspace name only, no page count suffix)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Summary stats line pattern: '{count} pages synced . {relative time}' for integration cards"
    - "Inline action button alongside stats (re-sync button on card face)"

key-files:
  created: []
  modified:
    - "backend/src/routers/integrations.py"
    - "apps/web/src/lib/api.ts"
    - "apps/web/src/app/dashboard/integrations/page.tsx"

key-decisions:
  - "NotionPages component removed from UI but file retained (no dead code deletion in scope)"
  - "Re-sync button placed inline with stats line for single-click access via Settings expand"
  - "Manage access link removed -- adds visual noise without enough value"
  - "Middle dot separator for stats line: '{count} pages synced . {time ago}'"

patterns-established:
  - "Integration card summary pattern: stats line with inline action in expandable section"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 09 Plan 01: Notion Integration UI Polish Summary

**Simplified Notion card: removed page list, added summary stats line with page count + last sync time, clean workspace-only header**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-02T06:30:52Z
- **Completed:** 2026-03-02T06:32:44Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Notion card header now shows only workspace name (e.g., "Daulet's Space"), not "Daulet's Space - 360 pages"
- Card body shows "{count} pages synced . {time ago}" summary stats with inline re-sync button
- NotionPages paginated list removed from UI -- card matches visual weight of Linear/Slack/GitHub peers
- Backend unified status endpoint now returns last_sync_at alongside pages_synced for Notion

## Task Commits

Each task was committed atomically:

1. **Task 1: Add last_sync_at to unified status endpoint and TypeScript types** - `6d67d32` (feat)
2. **Task 2: Simplify Notion card -- remove page list, add summary stats on card face** - `e43cacf` (feat)

## Files Created/Modified
- `backend/src/routers/integrations.py` - Added last_sync_at to Notion provider status dict
- `apps/web/src/lib/api.ts` - Added last_sync_at optional field to ProviderStatus interface
- `apps/web/src/app/dashboard/integrations/page.tsx` - Removed NotionPages, simplified card to stats + re-sync, fixed header

## Decisions Made
- Re-sync button placed inline with stats line (always visible via Settings expand, no separate settings section needed)
- "Manage access in Notion settings" link removed to reduce visual noise
- Middle dot unicode separator between page count and relative time for clean scanability
- notionRefreshKey state removed since NotionPages is gone (was its only consumer)
- syncTotal state retained for internal polling even though not displayed in new simpler UI

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Notion integration card is visually aligned with Linear, Slack, GitHub, and Fathom cards
- notion-pages.tsx file still exists but is not imported (dead code -- can be cleaned up in future tech debt pass)
- All live sync progress functionality preserved (syncing state, polling, progress display)

## Self-Check: PASSED

- 09-01-SUMMARY.md: FOUND
- Commit 6d67d32: FOUND
- Commit e43cacf: FOUND

---
*Phase: 09-notion-integration-ui-polish*
*Completed: 2026-03-02*
