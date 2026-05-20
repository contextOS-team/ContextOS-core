---
phase: 41-dashboard-pulse-redesign
plan: 01
subsystem: ui
tags: [nextjs, react, supabase, tailwind, dashboard, typography]

requires:
  - phase: 32-activity-events-emission
    provides: activity_events rows used for since-last-visit deltas
provides:
  - dashboard_user_state migration for per-user, per-workspace last_visited_at
  - pulse dashboard shared types, activity delta bucketing, and session-seen state
  - long-form relative time helper and pure headline rule engine
  - scoped pulse-surface typography, palette, card, marker, quote, focus, and motion utilities
affects: [dashboard-home, activity-events, pulse-redesign, chrome-cluster]

tech-stack:
  added: []
  patterns:
    - next/font variables for Geist Sans, Geist Mono, and Instrument Serif
    - .pulse-surface scoped dashboard visual tokens
    - server-backed last_visited_at with client-side session stability

key-files:
  created:
    - supabase/migrations/00040_dashboard_user_state.sql
    - apps/web/src/app/dashboard/pulse/types.ts
    - apps/web/src/app/dashboard/pulse/since-last-visit/activity-delta.ts
    - apps/web/src/app/dashboard/pulse/since-last-visit/use-last-visited-at.ts
    - apps/web/src/app/dashboard/pulse/since-last-visit/use-session-seen-items.ts
    - apps/web/src/app/dashboard/pulse/headline-rules.ts
  modified:
    - apps/web/src/app/layout.tsx
    - apps/web/src/app/globals.css
    - apps/web/src/lib/utils.ts

key-decisions:
  - "dashboard_user_state stores last_visited_at per user/workspace instead of localStorage."
  - "The warm pulse palette stays scoped to .pulse-surface and is not applied in dashboard/layout.tsx."
  - "headline-rules.ts uses the long-form formatLongRelativeTime helper, not the existing short-form formatRelativeTime helper."

patterns-established:
  - "Pulse data primitives live under apps/web/src/app/dashboard/pulse/ and are pure/tested before UI consumption."
  - "New since-last-visit markers are session-stable via a ref-backed SeenItemsProvider."
  - "Dashboard home visual redesign opts in with .pulse-surface; sibling routes keep the existing dashboard palette."

requirements-completed: [DASH-02, DASH-03]

duration: 38min
completed: 2026-05-20
---

# Phase 41 Plan 01: Pulse Foundation Summary

**Server-backed since-last-visit state, deterministic pulse headline rules, and scoped warm-dark typography tokens for the dashboard redesign**

## Performance

- **Duration:** 38 min
- **Started:** 2026-05-20T18:20:00Z
- **Completed:** 2026-05-20T18:58:14Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Added `dashboard_user_state` with composite `(user_id, workspace_id)` primary key, RLS, and delete cascades.
- Added `bucketDelta()`, `fetchActivityDelta()`, stable `useLastVisitedAt()`, and session-scoped seen-item tracking for Plan 41-02.
- Added `formatLongRelativeTime()` plus `computeHeadline()` with urgent-item, bucket, and quiet-day branches covered by unit tests.
- Loaded Geist Sans, Geist Mono, and Instrument Serif while keeping Inter and JetBrains Mono for existing surfaces.
- Added `.pulse-surface` CSS tokens and utilities without applying them to shared dashboard layout.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: activity delta tests** - `b2217c0` (test)
2. **Task 1 GREEN: visit delta foundation** - `17efcb1` (feat)
3. **Task 2 RED: headline rule tests** - `5d0a05e` (test)
4. **Task 2 GREEN: headline rules** - `0abb74e` (feat)
5. **Verification fix: clear lint warning** - `d365b74` (fix)
6. **Task 3: fonts and scoped palette** - `fb5d28e` (feat)

**Plan metadata:** committed in the docs closeout commit.

## Files Created/Modified

- `supabase/migrations/00040_dashboard_user_state.sql` - Per-user, per-workspace dashboard state table with RLS.
- `apps/web/src/app/dashboard/pulse/types.ts` - Shared `Delta`, `HeadlineCopy`, `NeedsYouItem`, and `TopUrgentItem` contracts.
- `apps/web/src/app/dashboard/pulse/since-last-visit/activity-delta.ts` - Activity event fetch and bucket helpers.
- `apps/web/src/app/dashboard/pulse/since-last-visit/use-last-visited-at.ts` - Stable session last-visited hook with five-minute inactivity writes.
- `apps/web/src/app/dashboard/pulse/since-last-visit/use-session-seen-items.ts` - Ref-backed session seen-item provider.
- `apps/web/src/app/dashboard/pulse/headline-rules.ts` - Pure headline copy engine.
- `apps/web/src/lib/utils.ts` - Added `formatLongRelativeTime()` alongside the existing short helper.
- `apps/web/src/app/layout.tsx` - Added Phase 41 font variables.
- `apps/web/src/app/globals.css` - Added scoped pulse-surface palette and utilities.

## Decisions Made

- Used server-side `dashboard_user_state` rather than browser storage so last-visit behavior remains coherent across devices.
- Kept `.pulse-surface` out of `dashboard/layout.tsx` because that layout is shared by `/context`, `/settings`, `/activity`, and `/graph`.
- Kept the headline generator rules-based and pure; LLM headline generation remains deferred.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed new lint warning from `bucketDelta()`**
- **Found during:** Task 3 verification
- **Issue:** `currentUserId` is part of the planned helper signature but the current needs-you contract already carries `assignedToCurrentUser`, so ESLint flagged it as unused.
- **Fix:** Added `void currentUserId` to preserve the public contract without warning noise.
- **Files modified:** `apps/web/src/app/dashboard/pulse/since-last-visit/activity-delta.ts`
- **Verification:** `npx eslint src/app/dashboard/pulse/ src/lib/utils.ts src/app/layout.tsx` passes.
- **Committed in:** `d365b74`

---

**Total deviations:** 1 auto-fixed (1 blocking verification cleanup).
**Impact on plan:** No behavior change. The helper contract remains compatible with the plan while keeping new code lint-clean.

## Issues Encountered

- `npm run build` initially failed while network access was blocked because `next/font` could not fetch Google Fonts. Re-running with network available passed.
- `npm run lint -- <paths>` fails under this project because `next lint` is deprecated and misinterprets path arguments. The equivalent `npx eslint src/app/dashboard/pulse/ src/lib/utils.ts src/app/layout.tsx` passed.
- The shell `LOCAL_SUPABASE_URL` variable was not exported and `.env` points at a non-running local socket. `supabase status` showed the local Supabase database was running on its Docker port, and the migration was applied and verified there.

## Verification

- `cd apps/web && npx vitest run src/app/dashboard/pulse/ src/lib/__tests__/utils.test.ts` - passed, 22 tests.
- `cd apps/web && npm run typecheck` - passed.
- `cd apps/web && npm run build` - passed. Existing unrelated lint warnings remain in pre-existing files.
- `cd apps/web && npx eslint src/app/dashboard/pulse/ src/lib/utils.ts src/app/layout.tsx` - passed.
- `psql <local Supabase DB> -f supabase/migrations/00040_dashboard_user_state.sql` - passed.
- `dashboard_user_state` local schema check returned `user_id`, `workspace_id`, `last_visited_at`, and `updated_at`.
- RLS policy check returned `own_dashboard_state`.
- `rg -n "ticket_updated|sync_failed" apps/web/src/app/dashboard/pulse` - no matches.
- `rg -n "vi.mock.*@/lib/utils|vi.mock.*formatLongRelativeTime|vi.mock.*formatRelativeTime" apps/web/src/app/dashboard/pulse/__tests__/headline-rules.test.ts` - no matches.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 41-02 can now consume the pulse primitives: `.pulse-surface`, `computeHeadline()`, `fetchActivityDelta()`, `useLastVisitedAt()`, and `SeenItemsProvider`. The home page still has no visible redesign; that is intentionally owned by Plan 41-02.

## Self-Check: PASSED

All planned code artifacts exist, tests pass, the local migration was applied to the running Supabase database, and the scoped palette is not applied to sibling dashboard routes.

---
*Phase: 41-dashboard-pulse-redesign*
*Completed: 2026-05-20*
