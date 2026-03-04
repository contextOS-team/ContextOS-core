---
phase: 15-dark-theme-token-foundation
plan: 01
subsystem: ui
tags: [css, oklch, tailwind, dark-theme, tokens, animation]

# Dependency graph
requires: []
provides:
  - "4-level OKLCH dark surface hierarchy (background, card, elevated, overlay) with hue 270"
  - "Teal primary color tokens (oklch 0.75 0.18 170) for interactive elements"
  - "@custom-variant dark with :where() zero-specificity selector"
  - "DarkModeApplier component with FOUC prevention inline script"
  - "Spring-curve animations (cubic-bezier 0.34, 1.56, 0.64, 1)"
  - "Shimmer-sweep keyframe and skeleton-shimmer class for loading states"
  - "Dashboard grain texture at 0.008 opacity"
  - "Section-label utility class (monospace uppercase tracking)"
  - "bg-elevated and bg-overlay Tailwind utility classes"
affects: [16-onboarding-infra, 17-onboarding-wizard, 18-activity-timeline, 19-dashboard-chrome, 20-settings]

# Tech tracking
tech-stack:
  added: []
  patterns: ["OKLCH 4-level surface hierarchy", "DarkModeApplier + FOUC prevention pattern", "Spring-curve CSS animations", "var() token aliasing for surface levels"]

key-files:
  created:
    - "apps/web/src/components/dashboard/dark-mode-applier.tsx"
  modified:
    - "apps/web/src/app/globals.css"
    - "apps/web/src/app/layout.tsx"
    - "apps/web/src/app/dashboard/layout.tsx"

key-decisions:
  - "Used :where(.dark, .dark *) for @custom-variant to ensure zero-specificity dark mode targeting"
  - "Wired --popover, --secondary, --muted to var(--elevated) for consistent surface hierarchy"
  - "Sidebar tokens updated to use teal primary (hue 170) and hue 270 surfaces matching dashboard"
  - "Spring-curve cubic-bezier(0.34, 1.56, 0.64, 1) gives slight overshoot for premium feel"
  - "Dashboard grain at 0.008 opacity (vs landing 0.025) for daily-use eye comfort"

patterns-established:
  - "4-level surface hierarchy: --background (L1) > --card (L2) > --elevated (L3) > --overlay (L4)"
  - "DarkModeApplier in root layout + inline FOUC script in <head> for instant dark mode"
  - "Spring-curve animation via cubic-bezier(0.34, 1.56, 0.64, 1) on all stagger/fade animations"
  - "Token aliasing pattern: --popover: var(--elevated) reduces maintenance"

requirements-completed: [DS-01, DS-02, DS-04, DS-05, DS-06, DS-07]

# Metrics
duration: 3min
completed: 2026-03-04
---

# Phase 15 Plan 01: Dark Theme Token Foundation Summary

**OKLCH 4-level dark surface hierarchy (hue 270), teal primary tokens (hue 170), DarkModeApplier with FOUC prevention, spring-curve animations, shimmer/grain/section-label utilities**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-04T08:18:52Z
- **Completed:** 2026-03-04T08:21:57Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Expanded .dark token block with 4-level OKLCH surface hierarchy (background, card, elevated, overlay) using blue-violet hue 270
- Shifted primary color from blue-indigo (hue 250) to teal (hue 170) matching brand #00D4AA -- only on interactive tokens
- Created DarkModeApplier component with inline FOUC prevention script ensuring no flash of light theme
- Added spring-curve animations, shimmer-sweep skeleton loading, dashboard grain texture, and section-label utility

## Task Commits

Each task was committed atomically:

1. **Task 1: Expand dark token system, fix @custom-variant, add animations and utility classes** - `ab94c20` (feat)
2. **Task 2: Create DarkModeApplier and integrate into root layout with FOUC prevention** - `4f35492` (feat)

## Files Created/Modified
- `apps/web/src/app/globals.css` - Fixed @custom-variant, expanded .dark block with 4-level hierarchy, spring animations, shimmer keyframe, grain class, section-label utility
- `apps/web/src/components/dashboard/dark-mode-applier.tsx` - Client component that adds .dark to html element on mount
- `apps/web/src/app/layout.tsx` - Added DarkModeApplier import/render and FOUC prevention inline script in head
- `apps/web/src/app/dashboard/layout.tsx` - Added dashboard-grain and relative classes for subtle grain texture

## Decisions Made
- Used `:where(.dark, .dark *)` for @custom-variant (zero-specificity, targets both .dark element and descendants per Tailwind v4 docs)
- Wired --popover, --secondary, --muted to `var(--elevated)` to reduce token maintenance and enforce hierarchy consistency
- Updated sidebar tokens to teal primary and hue 270 surfaces to match dashboard aesthetic
- Chose CSS-only spring curve (`cubic-bezier(0.34, 1.56, 0.64, 1)`) over Framer Motion -- sufficient for DS-06 requirements and zero bundle cost
- Dashboard grain at 0.008 opacity (vs landing's 0.025) per user decision for daily-use eye comfort

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All dark theme tokens established and build-verified
- DarkModeApplier active in root layout -- every page renders dark by default
- Landing page confirmed unaffected (scoped under .landing-theme)
- Plans 15-02 (navigation) and 15-03 (skeleton/pages) can proceed using these tokens
- New bg-elevated and bg-overlay Tailwind utilities available for component use

## Self-Check: PASSED

All 4 source files exist, SUMMARY.md created, both task commits (ab94c20, 4f35492) verified in git log.

---
*Phase: 15-dark-theme-token-foundation*
*Completed: 2026-03-04*
