---
phase: 42-landing-positioning-and-seo-launch-rewrite
plan: 01
subsystem: ui
tags: [landing, seo, metadata, cta, vitest]

requires:
  - phase: 42-landing-positioning-and-seo-launch-rewrite
    provides: approved launch positioning context and UI copy contract
provides:
  - Server-safe landing copy constants for SEO, hero, CTA, and claim guards
  - Landing metadata wired to approved SEO title and description
  - Booking CTA label aligned to the decision graph launch offer
  - Regression tests for metadata, meta keywords absence, booking anchor, and Cal embed config
affects: [landing, seo, phase-42, launch-copy]

tech-stack:
  added: []
  patterns:
    - Server-safe landing copy constants shared by metadata and client components
    - Metadata regression tests import Next layout metadata directly

key-files:
  created:
    - apps/web/src/components/landing/landing-copy.ts
    - apps/web/src/components/landing/__tests__/landing-metadata.test.ts
    - .planning/phases/42-landing-positioning-and-seo-launch-rewrite/deferred-items.md
  modified:
    - apps/web/src/app/(landing)/layout.tsx
    - apps/web/src/components/landing/booking.ts
    - apps/web/src/components/landing/__tests__/booking-cta.test.tsx

key-decisions:
  - "Centralized approved Phase 42 launch strings in a server-safe landing-copy module so metadata and later landing plans share one source of truth."
  - "Kept the primary CTA href on #booking while changing the label to See your decision graph, preserving the current booking-call behavior."

patterns-established:
  - "LANDING_SEO is the source of truth for public homepage title and description."
  - "LANDING_FORBIDDEN_PHRASES records overclaim phrases for later visible-copy guardrails without adding a meta keywords tag."

requirements-completed: [LAND-04, LAND-05, LAND-07]

duration: 4min
completed: 2026-05-22
---

# Phase 42 Plan 01: Landing Copy Contract and SEO Summary

**Source-backed decision-memory SEO and booking CTA contract for the launch landing page.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-22T16:54:02Z
- **Completed:** 2026-05-22T16:58:16Z
- **Tasks:** 3
- **Files modified:** 5 code/test files, 2 planning files

## Accomplishments

- Added `LANDING_SEO`, `LANDING_HERO`, `LANDING_CTA`, and `LANDING_FORBIDDEN_PHRASES` in a server-safe copy module with no React import and no client directive.
- Updated landing metadata to read the approved SEO title and description from `LANDING_SEO`.
- Changed the primary booking CTA label to `See your decision graph` while keeping the booking anchor and Cal.com config unchanged.
- Added regression coverage for metadata strings, absence of meta keywords, booking CTA anchors, and inline Cal.com embed attributes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create server-safe launch copy constants** - `7ea5fcd` (feat)
2. **Task 2: Update metadata and CTA constant** - `b91da11` (feat)
3. **Task 3: Add metadata and CTA regression tests** - `b540e9b` (test)

## Files Created/Modified

- `apps/web/src/components/landing/landing-copy.ts` - Approved launch SEO, hero, CTA, and forbidden-phrase constants.
- `apps/web/src/app/(landing)/layout.tsx` - Metadata now reads title and description from `LANDING_SEO`.
- `apps/web/src/components/landing/booking.ts` - Primary CTA label now says `See your decision graph`; booking anchor and Cal config stayed unchanged.
- `apps/web/src/components/landing/__tests__/landing-metadata.test.ts` - Verifies metadata uses `LANDING_SEO` and does not expose keywords.
- `apps/web/src/components/landing/__tests__/booking-cta.test.tsx` - Verifies decision graph CTA links route to `#booking` and preserves Cal embed assertions.
- `.planning/phases/42-landing-positioning-and-seo-launch-rewrite/deferred-items.md` - Tracks out-of-scope visible copy that later Phase 42 plans should rewrite.

## Decisions Made

- Centralized approved Phase 42 launch strings in `landing-copy.ts` so later landing rewrites consume the same exact copy as metadata.
- Kept the CTA destination as `#booking`; the label sells the buyer outcome while preserving the existing booking-call flow.
- Did not add a meta keywords tag; regression coverage now locks that out.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None in planned work.

## Deferred Issues

- Existing visible landing sections still contain phrases now listed in `LANDING_FORBIDDEN_PHRASES`: `AI synthesis complete`, `SOC 2 compliant architecture`, `2-6 hours`, and `2 minutes`. Those files are outside Plan 42-01's declared task files and are logged in `deferred-items.md` for the broader Plan 42-03 copy rewrite.

## Known Stubs

None.

## Verification

- `cd apps/web && npx vitest run src/components/landing/__tests__/landing-metadata.test.ts src/components/landing/__tests__/booking-cta.test.tsx` - passed, 2 files and 5 tests.
- `cd apps/web && npm run typecheck` - passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 42-02 can import `LANDING_HERO` for the hero rewrite.
- Plan 42-03 can import `LANDING_CTA` and `LANDING_FORBIDDEN_PHRASES` for booking copy and visible claim guards.
- Deferred visible-copy overclaim cleanup is explicitly tracked for Plan 42-03.

## Self-Check: PASSED

- Created files exist: `landing-copy.ts`, `landing-metadata.test.ts`, and `deferred-items.md`.
- Modified task files exist: `layout.tsx`, `booking.ts`, and `booking-cta.test.tsx`.
- Task commits exist: `7ea5fcd`, `b91da11`, and `b540e9b`.
- No tracked file deletions were introduced by task commits.

---
*Phase: 42-landing-positioning-and-seo-launch-rewrite*
*Completed: 2026-05-22*
