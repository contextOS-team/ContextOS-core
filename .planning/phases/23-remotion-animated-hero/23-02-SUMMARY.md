---
phase: 23-remotion-animated-hero
plan: 02
subsystem: ui
tags: [remotion, player, lazy-loading, next-dynamic, scroll-perspective, landing-page]

requires:
  - phase: 23-remotion-animated-hero-01
    provides: HeroComposition with 3 scenes, constants, shared components
  - phase: 13-landing-page
    provides: Hero component with demo video placeholder
provides:
  - RemotionPlayer wrapper with lazy composition loading
  - Hero.tsx with dynamic Remotion Player replacing static video
  - Scroll-driven perspective effect preserved on Player container
affects: []

tech-stack:
  added: [next/dynamic]
  patterns: [ssr-false-dynamic-import, lazy-composition-loading, aspect-ratio-placeholder]

key-files:
  created:
    - apps/web/src/components/landing/RemotionPlayer.tsx
  modified:
    - apps/web/src/components/landing/Hero.tsx
    - apps/web/src/remotion/constants.ts
    - apps/web/src/remotion/components/MockCard.tsx
    - apps/web/src/remotion/components/ProgressBar.tsx
    - apps/web/src/remotion/components/SourceIcon.tsx
    - apps/web/src/remotion/scenes/TicketScene.tsx
    - apps/web/src/remotion/scenes/SourcesScene.tsx
    - apps/web/src/remotion/scenes/ContextScene.tsx

key-decisions:
  - "next/dynamic with ssr:false for Remotion Player -- avoids window-is-not-defined SSR errors"
  - "16:9 aspect-ratio placeholder in loading state prevents CLS during lazy load"
  - "Real brand SVG logos (Slack 4-color, GitHub octocat, Linear mark) after visual review polish"

patterns-established:
  - "Client-only Player wrapper: useCallback for lazyComponent to avoid re-renders on parent state changes"
  - "Scroll transform isolation: perspective/rotateX/scale on parent div, Player receives zero scroll-dependent props"

requirements-completed: [HERO-ANIM-03, HERO-ANIM-04]

duration: 10min
completed: 2026-03-07
---

# Phase 23 Plan 02: Player Integration & Hero Replacement Summary

**Remotion Player integrated into Hero.tsx via next/dynamic with SSR-safe lazy loading, replacing static demo.mp4 with animated 3-scene walkthrough**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-07T22:12:20Z
- **Completed:** 2026-03-07T22:22:45Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Created RemotionPlayer wrapper component with lazy composition loading via useCallback
- Replaced static video element in Hero.tsx with dynamically imported RemotionHeroPlayer (ssr: false)
- Preserved scroll-driven perspective effect (rotateX 12->0, scale 0.88->1.0) on parent container
- Polished all 3 animation scenes after visual review: real brand SVG logos, increased card sizes/fonts, crossfade transitions, improved glow effects

## Task Commits

Each task was committed atomically:

1. **Task 1: Create RemotionPlayer wrapper and integrate into Hero.tsx** - `d7e9025` (feat)
2. **Task 2: Polish animation scenes after visual review** - `3cb3555` (feat)

## Files Created/Modified
- `apps/web/src/components/landing/RemotionPlayer.tsx` - Client component wrapping @remotion/player Player with lazy composition loading
- `apps/web/src/components/landing/Hero.tsx` - Dynamic import of RemotionHeroPlayer replacing video element
- `apps/web/src/remotion/constants.ts` - Added CROSSFADE_FRAMES, cardGradient, slackBlue, slackRed colors
- `apps/web/src/remotion/components/MockCard.tsx` - Radial gradient top-light, teal glow shadows
- `apps/web/src/remotion/components/ProgressBar.tsx` - Increased height and track opacity
- `apps/web/src/remotion/components/SourceIcon.tsx` - Real brand SVG logos (Slack, GitHub, Linear)
- `apps/web/src/remotion/scenes/TicketScene.tsx` - Wider card, unified entrance, cross-fade out, bumped fonts
- `apps/web/src/remotion/scenes/SourcesScene.tsx` - Wider card, entrance animation, animated labels, cross-fade out
- `apps/web/src/remotion/scenes/ContextScene.tsx` - Wider card, unified entrance with scale, smooth glow, bumped fonts

## Decisions Made
- next/dynamic with ssr:false for Remotion Player -- avoids "window is not defined" SSR errors during Next.js build
- 16:9 aspect-ratio placeholder with #0A0A0F background prevents CLS during lazy load
- useCallback wrapping lazyComponent import prevents re-creation on scroll-triggered re-renders
- Real brand SVG logos chosen over minimal placeholders after visual review confirmed better product feel
- Cross-fade transitions added between scenes for smoother visual flow

## Deviations from Plan

### Post-checkpoint Polish (User-directed)

After visual checkpoint approval, design critique improvements were applied to all 7 Remotion composition files:
- Increased card widths (500-560px -> 700-740px) and font sizes ~30% for readability
- Added crossfade transitions between scenes
- Replaced placeholder SVG icons with real brand logos
- Enhanced MockCard with radial gradient and teal glow shadows
- These changes were user-directed during the visual review checkpoint.

**Total deviations:** 1 user-directed polish pass
**Impact on plan:** Improved visual quality. No scope creep -- all changes within the animation composition scope.

## Issues Encountered

- TypeScript `--noEmit` check shows esModuleInterop warnings from Remotion's own .d.ts files (node_modules). These are upstream Remotion type definition issues, not errors in our code. Next.js build handles them correctly via tsconfig settings.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 23 (Remotion Animated Hero) is fully complete -- both plans shipped
- Landing page hero now shows animated 3-scene product walkthrough
- No further phases depend on this work

## Self-Check: PASSED

All files verified present. Both task commits (d7e9025, 3cb3555) verified in git log.

---
*Phase: 23-remotion-animated-hero*
*Completed: 2026-03-07*
