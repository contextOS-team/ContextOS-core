---
phase: 42-landing-positioning-and-seo-launch-rewrite
plan: 02
subsystem: ui
tags: [landing, hero, decision-receipt, seo, vitest]

requires:
  - phase: 42-landing-positioning-and-seo-launch-rewrite
    provides: approved landing SEO and launch copy constants from Plan 42-01
provides:
  - Static, crawlable Decision Receipt hero visual with source chips, people, affected systems, related work, and verification state
  - Landing hero rewritten around source-backed decision memory for engineering teams
  - Regression tests covering approved hero copy, CTA anchors, receipt fields, source evidence, and old-copy absence
affects: [landing, hero, decision-memory, launch-copy]

tech-stack:
  added: []
  patterns:
    - Static client-safe product-proof component with inline sample arrays and no data fetching
    - Hero copy rendered from LANDING_HERO while booking behavior remains controlled by BOOKING_SECTION_HREF

key-files:
  created:
    - apps/web/src/components/landing/DecisionReceiptVisual.tsx
    - apps/web/src/components/landing/__tests__/landing-hero.test.tsx
  modified:
    - apps/web/src/components/landing/Hero.tsx

key-decisions:
  - "Decision Receipt is now the hero product-proof primitive, replacing the ticket-first Remotion hero dependency without deleting RemotionPlayer.tsx."
  - "Hero copy renders the approved LANDING_HERO strings while the primary CTA keeps the existing #booking flow and the secondary CTA targets #decision-trail."
  - "Decision Receipt sample data is explicitly fictional and generic to avoid implying real customer workspace data."

patterns-established:
  - "Hero visual proof should be crawlable React text/SVG, not only video, canvas, or Remotion content."
  - "Decision graph previews should stay small and inspectable with 4-6 understandable connected nodes."

requirements-completed: [LAND-04, LAND-08]

duration: 4 min
completed: 2026-05-22
---

# Phase 42 Plan 02: Hero Decision Receipt Visual Summary

**Source-backed Decision Receipt hero with approved decision-memory positioning and regression coverage.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-22T17:01:55Z
- **Completed:** 2026-05-22T17:06:25Z
- **Tasks:** 3
- **Files modified:** 3 code/test files, 1 planning summary

## Accomplishments

- Added `DecisionReceiptVisual`, a static proof component showing the decision, rationale, people, original sources, affected systems, related work, verified status, and a five-node decision graph preview.
- Rewrote the landing hero to use `LANDING_HERO`, preserve the booking CTA analytics flow, point the secondary CTA at `#decision-trail`, and render the receipt visual in the first viewport.
- Added `landing-hero.test.tsx` coverage for approved launch copy, CTA anchors, Decision Receipt fields, source chips, affected systems, verification state, and old ticket-first hero copy absence.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build DecisionReceiptVisual** - `75d08f7` (feat)
2. **Task 2: Rewrite Hero copy and first-viewport proof** - `fa7d2b8` (feat)
3. **Task 3: Add hero and receipt render tests** - `1f339ce` (test)

## Files Created/Modified

- `apps/web/src/components/landing/DecisionReceiptVisual.tsx` - New source-backed Decision Receipt visual with fictional sample data and a five-node graph preview.
- `apps/web/src/components/landing/Hero.tsx` - Rewritten hero consuming `LANDING_HERO`, `BOOKING_SECTION_HREF`, and `DecisionReceiptVisual`; removed the Remotion hero dependency from the first viewport.
- `apps/web/src/components/landing/__tests__/landing-hero.test.tsx` - New regression test for the approved hero, CTA anchors, receipt proof fields, source chips, affected systems, and old-copy absence.

## Decisions Made

- Decision Receipt is now the landing hero's primary product-proof primitive.
- Remotion remains in the repository untouched, but Hero no longer imports it for the core launch proof.
- The receipt uses only generic fictional names and identifiers, matching the plan threat model and avoiding customer-data implications.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Deferred Issues

None.

## Known Stubs

None.

## Verification

- `cd apps/web && npx vitest run src/components/landing/__tests__/landing-hero.test.tsx` - passed, 1 file and 3 tests.
- `cd apps/web && npx vitest run src/components/landing/__tests__/booking-cta.test.tsx` - passed, 1 file and 3 tests.
- `cd apps/web && npm run typecheck` - passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 42-03 can continue the below-the-fold copy rewrite while reusing the hero's `#decision-trail` anchor and Decision Receipt vocabulary.
- Existing dirty `RemotionPlayer.tsx` and its test were preserved and not staged or committed.

## Self-Check: PASSED

- Created files exist: `DecisionReceiptVisual.tsx` and `landing-hero.test.tsx`.
- Modified task file exists: `Hero.tsx`.
- Task commits exist: `75d08f7`, `fa7d2b8`, and `1f339ce`.
- No tracked file deletions were introduced by task commits.
- Stub scan found no placeholder, TODO/FIXME, hardcoded-empty, or mock-empty data flowing to the hero UI.
- Threat surface scan found no new network endpoints, auth paths, file access, or schema changes.

---
*Phase: 42-landing-positioning-and-seo-launch-rewrite*
*Completed: 2026-05-22*
