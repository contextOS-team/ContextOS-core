---
phase: 42-landing-positioning-and-seo-launch-rewrite
plan: 03
subsystem: ui
tags: [landing, product-demo, decision-memory, seo, vitest]

requires:
  - phase: 42-landing-positioning-and-seo-launch-rewrite
    provides: approved SEO copy constants and hero Decision Receipt direction from Plans 42-01 and 42-02
provides:
  - Minimal demo-first landing page order centered on a real product-shaped decision trail
  - Compact source integration strip, simplified booking section, and reduced footer/navigation
  - Regression coverage for the quieter hero, demo proof, source strip, booking anchor, and unsupported-claim guardrails
affects: [landing, homepage, launch-copy, decision-memory]

tech-stack:
  added: []
  patterns:
    - Demo-first landing composition with hero copy leading into crawlable product-state examples
    - Source and booking sections are compact supporting proof, not separate card-heavy explainer bands

key-files:
  created:
    - apps/web/src/components/landing/__tests__/landing-sections.test.tsx
    - apps/web/src/components/landing/__tests__/landing-claims.test.tsx
  modified:
    - apps/web/src/app/(landing)/page.tsx
    - apps/web/src/app/(landing)/layout.tsx
    - apps/web/src/app/(landing)/opengraph-image.tsx
    - apps/web/src/components/landing/Hero.tsx
    - apps/web/src/components/landing/Nav.tsx
    - apps/web/src/components/landing/ProductDemo.tsx
    - apps/web/src/components/landing/Integrations.tsx
    - apps/web/src/components/landing/CTASection.tsx
    - apps/web/src/components/landing/Footer.tsx
    - apps/web/src/components/landing/landing-copy.ts
    - apps/web/src/components/landing/__tests__/landing-metadata.test.ts
    - apps/web/src/components/landing/__tests__/landing-hero.test.tsx
    - apps/web/src/components/landing/__tests__/landing-sections.test.tsx
    - apps/web/src/components/landing/__tests__/booking-cta.test.tsx

key-decisions:
  - "Landing page now prioritizes a single demo-first narrative: hero -> product demo -> sources -> booking -> footer."
  - "Problem, workflow, trust, and feature bands were removed from the rendered page order after user feedback that the landing was too noisy."
  - "The primary hero CTA now jumps to #demo, while See your decision graph remains the booking conversion path."
  - "Remotion video remains untouched; the launch proof stays crawlable React text and product UI, not a video placeholder."
  - "Landing route owns absolute title plus OpenGraph, Twitter, and route-scoped OG image copy so social previews do not inherit the old ticket-first positioning."

patterns-established:
  - "Use product-shaped sample states for landing proof: decision question, answer, evidence chips, decision receipt, ticket context, and PR context."
  - "Keep source integrations as a compact strip when the page goal is comprehension rather than exhaustive feature education."

requirements-completed: [LAND-05, LAND-06, LAND-07, LAND-08]

duration: 24min
completed: 2026-05-22
---

# Phase 42 Plan 03: Minimal Demo-First Landing Summary

**The landing now leads with a quieter hero and concrete ContextOS product demos instead of a long explainer stack.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-05-22T17:12:50Z
- **Completed:** 2026-05-22T17:45:20Z
- **Tasks:** 4 planned tasks plus 1 user-directed pivot
- **Files modified:** 12 landing code/test files, 1 planning summary

## Accomplishments

- Reframed the below-fold proof into `ProductDemo`, showing a concrete decision question, source-backed answer, evidence chips, decision receipt, ticket context, and PR context as crawlable React text.
- Simplified the rendered page order from hero plus five explainer bands into `Hero`, `ProductDemo`, `Integrations`, `CTASection`, and `Footer`.
- Tightened hero copy and CTA routing so `View product demo` jumps to the demo, while `See your decision graph` preserves the inline booking conversion flow.
- Reworked sources, booking, footer, and nav into compact supporting sections instead of separate dense marketing surfaces.
- Added and updated regression tests for the demo-first flow, booking anchors, minimal hero, and unsupported-claim guardrails.
- Fixed post-review SEO/social metadata drift by adding absolute title metadata, landing OpenGraph/Twitter values, and a landing-scoped OG image.

## Task Commits

Each task was committed atomically:

1. **Task 1: Reframe landing decision proof sections** - `7d5a499` (feat)
2. **Task 2: Align capabilities and booking copy** - `5d51736` (feat)
3. **Task 3: Guard landing section claims** - `ea046e0` (test)
4. **User-directed pivot: simplify landing around product demos** - `fbb5610` (feat)
5. **Code-review remediation: align landing social metadata** - `9d32038` (fix)

## Files Created/Modified

- `apps/web/src/app/(landing)/page.tsx` - Renders the minimal demo-first page order and removes the noisy problem/how/features/trust stack from the page.
- `apps/web/src/app/(landing)/layout.tsx` - Owns absolute landing title, description, OpenGraph, and Twitter metadata.
- `apps/web/src/app/(landing)/opengraph-image.tsx` - Landing-scoped social image with decision-memory positioning.
- `apps/web/src/components/landing/Hero.tsx` - Removes the repeated receipt visual, shortens copy, routes primary CTA to `#demo`, and leaves the demo heading visible in the first viewport.
- `apps/web/src/components/landing/ProductDemo.tsx` - Provides the main product proof with decision question, answer, sources, receipt fields, ticket context, and PR context.
- `apps/web/src/components/landing/Integrations.tsx` - Converts the integration grid into a compact source strip.
- `apps/web/src/components/landing/CTASection.tsx` - Keeps the Cal embed and `#booking` id while removing decorative card nesting and extra explanatory copy.
- `apps/web/src/components/landing/Nav.tsx` and `Footer.tsx` - Reduce navigation to Demo, Sources, and booking.
- `apps/web/src/components/landing/landing-copy.ts` - Updates hero copy and CTA labels for the demo-first direction.
- `apps/web/src/components/landing/__tests__/landing-hero.test.tsx` - Updates hero coverage for the quieter CTA layout.
- `apps/web/src/components/landing/__tests__/landing-metadata.test.ts` - Covers absolute title, OpenGraph, Twitter metadata, and landing OG image alt text.
- `apps/web/src/components/landing/__tests__/landing-sections.test.tsx` - Covers the demo-first section, compact source strip, booking section, and footer.
- `apps/web/src/components/landing/__tests__/landing-claims.test.tsx` - Guards unsupported claims and banned generic AI language.
- `apps/web/src/components/landing/__tests__/booking-cta.test.tsx` - Updates CTA expectations for `#demo` plus preserved `#booking` routing.

## Decisions Made

- The page should behave more like the HeyHyper reference: fewer sections, direct product-state demos, and less explanatory copy.
- `ProductDemo` is the primary landing proof below the hero; `DecisionReceiptVisual` remains in the codebase but is no longer duplicated in the first viewport.
- The rendered landing should avoid unsupported future-action claims entirely rather than preserving a roadmap teaser.
- The source integration surface should be scannable and compact; the page no longer needs a full card grid to prove integrations.
- Landing social metadata should be route-scoped so launch previews match the decision-memory wedge rather than old ticket-context copy.

## Deviations from Plan

### User-Directed Pivot

- **Found during:** Task 4 visual/reference review.
- **Issue:** The initial Plan 42-03 implementation technically met the written plan but still felt too noisy because it rendered problem, how-it-works, product proof, features, integrations, trust, booking, and footer.
- **Fix:** Used Arc to inspect `heyhyper.ai`, then simplified the rendered page into a demo-first flow with real product-shaped states and fewer sections.
- **Files modified:** `page.tsx`, `Hero.tsx`, `ProductDemo.tsx`, `Integrations.tsx`, `CTASection.tsx`, `Footer.tsx`, `Nav.tsx`, `landing-copy.ts`, and landing tests.
- **Verification:** Landing tests, typecheck, lint, and Arc desktop inspection.
- **Committed in:** `fbb5610`

---

**Total deviations:** 1 user-directed pivot.
**Impact on plan:** Improved the goal fit by reducing noise while preserving required SEO and crawlable decision-memory copy.

## Issues Encountered

- The in-app Browser plugin was unavailable, so local visual checks used Arc.
- Playwright browser binaries were not installed, so screenshot-based mobile verification could not run without downloading browsers.
- An AppleScript attempt to resize Arc for mobile failed because Arc did not allow setting front-window bounds. Desktop Arc inspection passed; mobile visual verification remains lower-confidence.
- `npm run lint` exits successfully but reports unrelated existing warnings in dashboard, graph, and onboarding files.
- Code review found that landing social metadata still inherited old root OpenGraph/Twitter and OG image positioning. Fixed in `9d32038`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The page is ready for user review at `http://127.0.0.1:3000`.
- Remaining risk is visual preference, especially mobile polish, because automated screenshot tooling was unavailable in this environment.
- Existing dirty `RemotionPlayer.tsx`, its untracked test, and dashboard chrome edits were preserved and not staged or committed.

## Verification

- `cd apps/web && npx vitest run src/components/landing/__tests__` - passed, 6 files and 13 tests.
- `cd apps/web && npm run typecheck` - passed.
- `cd apps/web && npm run lint` - passed with unrelated existing warnings.
- Arc desktop inspection of `http://127.0.0.1:3000` - passed for the hero, demo section, source strip, and booking section; the demo heading is visible in the first viewport.
- Arc inspection of `https://heyhyper.ai` - used as the reference for compact hero plus numbered real demo states.

## Self-Check: PASSED

- Production changes are committed in task/pivot commits.
- `42-03-SUMMARY.md` exists.
- No tracked dashboard or Remotion dirty changes were staged.
- Required landing copy remains crawlable React text: decision memory, source-backed decisions, engineering knowledge management, company knowledge graph, ticket context, and PR context.
- Unsupported phrases remain guarded by tests.

---
*Phase: 42-landing-positioning-and-seo-launch-rewrite*
*Completed: 2026-05-22*
