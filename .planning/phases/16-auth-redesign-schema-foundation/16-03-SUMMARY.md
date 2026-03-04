---
phase: 16-auth-redesign-schema-foundation
plan: 03
subsystem: ui
tags: [nextjs, sonner, toasts, onboarding, redirect, server-components, supabase]

# Dependency graph
requires:
  - phase: 16-auth-redesign-schema-foundation
    provides: user_onboarding_state table with completed_at column and RLS
provides:
  - Server-side onboarding gate in dashboard layout
  - /onboarding route with minimal layout (no sidebar)
  - Sonner toaster in root layout for app-wide toast notifications
  - Auth callback with onboarding status check for redirect destination
affects: [17-onboarding-wizard, dashboard-access-control]

# Tech tracking
tech-stack:
  added: []
  patterns: [onboarding-gate-pattern, null-row-backward-compat, suspense-searchparams]

key-files:
  created:
    - apps/web/src/components/ui/sonner.tsx
    - apps/web/src/app/onboarding/layout.tsx
    - apps/web/src/app/onboarding/page.tsx
  modified:
    - apps/web/src/app/layout.tsx
    - apps/web/src/app/dashboard/layout.tsx
    - apps/web/src/app/(auth)/auth/callback/route.ts

key-decisions:
  - "NULL onboarding row = legacy user, passes through dashboard gate without redirect"
  - "Middleware unchanged -- existing public/auth path logic already handles /onboarding correctly"
  - "Suspense boundary wraps useSearchParams to avoid Next.js static rendering issues"

patterns-established:
  - "Onboarding gate: query user_onboarding_state, redirect if row exists with null completed_at"
  - "Toast-on-redirect: pass ?from=dashboard query param, show toast via useEffect on mount"

requirements-completed: [ONB-09]

# Metrics
duration: 2min
completed: 2026-03-04
---

# Phase 16 Plan 03: Onboarding Gate & Route Summary

**Server-side onboarding gate in dashboard layout with /onboarding placeholder route, Sonner toaster, and auth callback redirect**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-04T11:11:22Z
- **Completed:** 2026-03-04T11:13:27Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created dark-themed Sonner Toaster component and added to root layout for app-wide toast support
- Added server-side onboarding gate to dashboard layout that queries user_onboarding_state and redirects incomplete users to /onboarding
- Created /onboarding route with minimal layout (no sidebar) and placeholder page with toast notification on redirect
- Updated auth callback to check onboarding status after code exchange, redirecting new incomplete users to /onboarding instead of /dashboard
- Preserved backward compatibility: existing users with no onboarding row (NULL) pass through without redirect

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Sonner toaster component and add to root layout** - `8a2852d` (feat)
2. **Task 2: Add onboarding gate to dashboard layout, create /onboarding route, update auth callback** - `396e87d` (feat)

## Files Created/Modified
- `apps/web/src/components/ui/sonner.tsx` - Dark-themed Toaster wrapper using sonner with bg-elevated styling
- `apps/web/src/app/layout.tsx` - Added Toaster import and component to root layout body
- `apps/web/src/app/dashboard/layout.tsx` - Added onboarding gate: queries user_onboarding_state, redirects if row exists with null completed_at
- `apps/web/src/app/onboarding/layout.tsx` - Minimal server layout with auth check, no sidebar/nav
- `apps/web/src/app/onboarding/page.tsx` - Client component with Suspense-wrapped toast handler and placeholder content
- `apps/web/src/app/(auth)/auth/callback/route.ts` - Added onboarding status check after code exchange for redirect destination

## Decisions Made
- NULL onboarding row means legacy/existing user -- treated as completed to avoid locking out pre-migration users. The gate logic is `if (onboardingState && !onboardingState.completed_at)` which only redirects when a row exists with null completed_at.
- No middleware changes needed -- the existing public/auth path logic already handles /onboarding correctly (unauthenticated users get redirected to /login, authenticated users pass through).
- Wrapped useSearchParams in a Suspense boundary via OnboardingToastHandler component to avoid Next.js static rendering bailout.

## Deviations from Plan

None - plan executed exactly as written. The plan itself noted that middleware.ts does not need modification, which was confirmed during execution.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- /onboarding route is a placeholder -- Phase 17 will replace the page content with the onboarding wizard
- Dashboard gate is active and will redirect new users with incomplete onboarding
- Sonner toaster is available app-wide for future toast notifications
- Auth callback properly routes new signups to onboarding flow

## Self-Check: PASSED

- FOUND: apps/web/src/components/ui/sonner.tsx
- FOUND: apps/web/src/app/onboarding/layout.tsx
- FOUND: apps/web/src/app/onboarding/page.tsx
- FOUND: apps/web/src/app/layout.tsx
- FOUND: apps/web/src/app/dashboard/layout.tsx
- FOUND: apps/web/src/app/(auth)/auth/callback/route.ts
- FOUND: 16-03-SUMMARY.md
- FOUND: commit 8a2852d
- FOUND: commit 396e87d
- BUILD: pnpm build passes

---
*Phase: 16-auth-redesign-schema-foundation*
*Completed: 2026-03-04*
