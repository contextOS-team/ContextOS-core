---
phase: 23-remotion-animated-hero
plan: 01
subsystem: ui
tags: [remotion, animation, react, hero, landing-page]

requires:
  - phase: 13-landing-page
    provides: Hero component with demo video placeholder
  - phase: 15-design-tokens
    provides: Brand colors, spring curves, design tokens
provides:
  - Remotion composition with 3 animated scenes (ticket, sources, context)
  - Shared animation components (MockCard, ProgressBar, SourceIcon)
  - Centralized constants (FPS, dimensions, spring configs, colors)
affects: [23-02-player-integration]

tech-stack:
  added: [remotion, "@remotion/player"]
  patterns: [frame-based-animation, spring-interpolate, inline-styles-only]

key-files:
  created:
    - apps/web/src/remotion/constants.ts
    - apps/web/src/remotion/HeroComposition.tsx
    - apps/web/src/remotion/scenes/TicketScene.tsx
    - apps/web/src/remotion/scenes/SourcesScene.tsx
    - apps/web/src/remotion/scenes/ContextScene.tsx
    - apps/web/src/remotion/components/MockCard.tsx
    - apps/web/src/remotion/components/ProgressBar.tsx
    - apps/web/src/remotion/components/SourceIcon.tsx
  modified:
    - apps/web/package.json

key-decisions:
  - "Minimal SVG icons (hash, brackets, diamond) instead of full brand logos for Remotion self-containment"
  - "All styles inline -- no CSS classes or Tailwind in remotion/ folder per Remotion iframe rendering constraint"

patterns-established:
  - "Frame-based animation: all motion via useCurrentFrame + spring + interpolate, zero CSS transitions"
  - "Scene composition: Series.Sequence for sequential scene playback with gap"
  - "Shared Remotion components: MockCard/ProgressBar/SourceIcon with inline styles only"

requirements-completed: [HERO-ANIM-01, HERO-ANIM-02]

duration: 3min
completed: 2026-03-07
---

# Phase 23 Plan 01: Remotion Composition & Scenes Summary

**Remotion 3-scene hero animation with ticket slide-in, source search progress, and context page materialization**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-07T22:07:44Z
- **Completed:** 2026-03-07T22:10:15Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Installed remotion and @remotion/player in apps/web
- Created 3 animation scenes: TicketScene (ENG-42 card), SourcesScene (Slack/GitHub/Linear progress), ContextScene (context page with AI prompt glow)
- Built HeroComposition root that sequences all scenes via Series (360 total frames at 30fps = 12s loop)
- Centralized all spring configs, colors, and durations in constants.ts

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Remotion and create constants + shared components** - `aae71bb` (feat)
2. **Task 2: Create three scene compositions and root HeroComposition** - `fbfa79c` (feat)

## Files Created/Modified
- `apps/web/src/remotion/constants.ts` - FPS, dimensions, spring configs, brand colors, scene durations
- `apps/web/src/remotion/HeroComposition.tsx` - Root composition using Series for 3 scenes
- `apps/web/src/remotion/scenes/TicketScene.tsx` - Scene 1: ENG-42 ticket card slide-in with staggered details
- `apps/web/src/remotion/scenes/SourcesScene.tsx` - Scene 2: Source icons with progress bars
- `apps/web/src/remotion/scenes/ContextScene.tsx` - Scene 3: Context page materialization with AI prompt glow
- `apps/web/src/remotion/components/MockCard.tsx` - Reusable glass card container
- `apps/web/src/remotion/components/ProgressBar.tsx` - Animated horizontal progress bar
- `apps/web/src/remotion/components/SourceIcon.tsx` - Source brand icon with active glow state
- `apps/web/package.json` - Added remotion and @remotion/player dependencies

## Decisions Made
- Minimal SVG icons (hash, brackets, diamond) instead of full brand logos -- keeps Remotion composition self-contained
- All styles inline only -- Remotion compositions render in iframe-like context without external stylesheets
- SPRING_ENTER config (damping 13, stiffness 100, mass 0.8) matches Phase 15 cubic-bezier spring curve

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- HeroComposition ready for Player embedding in Plan 02
- All scenes export named components compatible with lazyComponent loading
- Constants centralized for reuse in Player wrapper

## Self-Check: PASSED

All 8 created files verified present. Both task commits (aae71bb, fbfa79c) verified in git log.

---
*Phase: 23-remotion-animated-hero*
*Completed: 2026-03-07*
