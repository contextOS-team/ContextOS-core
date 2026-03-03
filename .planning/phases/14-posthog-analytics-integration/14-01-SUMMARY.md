---
phase: 14-posthog-analytics-integration
plan: 01
subsystem: analytics
tags: [posthog, analytics, waitlist, next.js, react]

# Dependency graph
requires:
  - phase: 13-adopt-orchids-landing-page-into-apps-web
    provides: Landing page components (CTASection, Hero) and (landing) layout
provides:
  - PostHog SDK initialized on landing pages only
  - PostHogProvider and PostHogPageView components in src/lib/posthog.tsx
  - waitlist_signup event capture on form submit with email property
  - CTA click tracking on Hero links (cta_hero_click, cta_how_it_works_click)
affects: [14-posthog-analytics-integration, landing-page, waitlist]

# Tech tracking
tech-stack:
  added: [posthog-js]
  patterns: [module-level PostHog init with window guard, SPA-aware pageview tracking via PostHogPageView, silent-fail analytics with try/catch + optional chaining]

key-files:
  created:
    - apps/web/src/lib/posthog.tsx
  modified:
    - apps/web/src/app/(landing)/layout.tsx
    - apps/web/src/components/landing/CTASection.tsx
    - apps/web/src/components/landing/Hero.tsx
    - apps/web/package.json

key-decisions:
  - "PostHog scoped to landing layout only -- dashboard pages never load the SDK"
  - "capture_pageview: false with manual PostHogPageView for correct SPA navigation tracking"
  - "autocapture: false -- explicit event tracking only per CONTEXT.md"
  - "All PostHog calls wrapped in try/catch with optional chaining for silent failure"

patterns-established:
  - "Silent analytics: try/catch + optional chaining ensures PostHog never blocks UX"
  - "Landing-scoped provider: PostHogProvider in (landing)/layout.tsx keeps SDK off dashboard"
  - "SPA pageview: PostHogPageView reacts to pathname/searchParams changes via useEffect"

requirements-completed: [ANLYT-01-partial]

# Metrics
duration: 2min
completed: 2026-03-04
---

# Phase 14 Plan 01: PostHog Analytics + Waitlist Summary

**PostHog SDK installed on landing pages with waitlist_signup event capture and Hero CTA click tracking**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-03T23:28:26Z
- **Completed:** 2026-03-03T23:31:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- PostHog JS SDK installed and initialized with env-var guard (NEXT_PUBLIC_POSTHOG_KEY)
- PostHogProvider wraps landing layout only -- dashboard pages never load PostHog
- Waitlist form captures `waitlist_signup` event with email property on submit
- Hero CTA links track `cta_hero_click` and `cta_how_it_works_click` events

## Task Commits

Each task was committed atomically:

1. **Task 1: Install PostHog SDK and create landing-scoped provider** - `1092ae3` (feat)
2. **Task 2: Wire waitlist form and Hero CTA to PostHog events** - `a9d1c09` (feat)

## Files Created/Modified
- `apps/web/src/lib/posthog.tsx` - PostHog initialization, PostHogProvider, and PostHogPageView components
- `apps/web/src/app/(landing)/layout.tsx` - Landing layout wrapped with PostHogProvider and Suspense-bounded PostHogPageView
- `apps/web/src/components/landing/CTASection.tsx` - Waitlist form fires waitlist_signup event with email on submit
- `apps/web/src/components/landing/Hero.tsx` - CTA links fire cta_hero_click and cta_how_it_works_click events
- `apps/web/package.json` - Added posthog-js dependency

## Decisions Made
- PostHog scoped to landing layout only -- dashboard pages never load the SDK
- `capture_pageview: false` with manual `PostHogPageView` component for correct Next.js App Router SPA navigation tracking
- `autocapture: false` -- explicit event tracking only per CONTEXT.md guidance
- All PostHog calls wrapped in `try/catch` with optional chaining (`posthog?.capture`) for silent failure
- `person_profiles: 'identified_only'` to avoid creating anonymous person profiles

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

PostHog requires environment variables to be set for the SDK to initialize:
- `NEXT_PUBLIC_POSTHOG_KEY` - PostHog project API key (required)
- `NEXT_PUBLIC_POSTHOG_HOST` - PostHog API host (optional, defaults to `https://us.i.posthog.com`)

Without these env vars, PostHog silently does not initialize (the `typeof window` + env var guard prevents any errors).

## Next Phase Readiness
- PostHog analytics foundation complete for landing pages
- Ready for additional event tracking on other landing sections if needed
- PostHog dashboard configuration (funnels, cohorts) can be done in PostHog UI

---
*Phase: 14-posthog-analytics-integration*
*Completed: 2026-03-04*
