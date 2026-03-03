---
phase: 13-adopt-orchids-landing-page-into-apps-web
plan: 01
subsystem: ui
tags: [react, tailwind, css, landing-page, marketing, components]

# Dependency graph
requires:
  - phase: 08.1.1-notion-integration
    provides: brand-logos.tsx with LinearLogo, SlackLogo, GitHubLogo, NotionLogo, FathomLogo
provides:
  - 10 landing section components in apps/web/src/components/landing/
  - Landing CSS with scoped dark theme variables and utility classes
  - useInView hook for scroll-triggered animations
  - Barrel export for all landing components
affects: [13-02 landing layout and page assembly]

# Tech tracking
tech-stack:
  added: []
  patterns: [scoped CSS variables under .landing-theme class, landing-grain class for grain overlay, barrel export for component library]

key-files:
  created:
    - apps/web/src/app/landing.css
    - apps/web/src/hooks/useInView.ts
    - apps/web/src/components/landing/Nav.tsx
    - apps/web/src/components/landing/Hero.tsx
    - apps/web/src/components/landing/TrustBar.tsx
    - apps/web/src/components/landing/ProblemSection.tsx
    - apps/web/src/components/landing/HowItWorks.tsx
    - apps/web/src/components/landing/Features.tsx
    - apps/web/src/components/landing/ProductDemo.tsx
    - apps/web/src/components/landing/Integrations.tsx
    - apps/web/src/components/landing/CTASection.tsx
    - apps/web/src/components/landing/Footer.tsx
    - apps/web/src/components/landing/index.ts
  modified: []

key-decisions:
  - "CSS variables scoped under .landing-theme class to avoid dashboard CSS pollution"
  - "Grain overlay converted from body::before to .landing-grain class for layout composability"
  - "TrustBar rewritten with real brand logo imports from brand-logos.tsx instead of inline SVGs"
  - "Integrations component uses brand logo components for live integrations, letter-icon fallback for soon items"
  - "ProblemSection emoji faces replaced with text emoticons for cross-platform consistency"
  - "Footer product links limited to Features, How It Works, Integrations (no Pricing/Docs/Changelog)"
  - "Footer company links limited to Twitter/X and GitHub (no Blog/About)"

patterns-established:
  - "Landing component pattern: each section is a self-contained default export using useInView for scroll animation"
  - "Scoped CSS theme: .landing-theme class wraps all landing-specific CSS variables"
  - "Brand logo reuse: import from @/components/icons/brand-logos for consistent integration logos"

requirements-completed: []

# Metrics
duration: 7min
completed: 2026-03-03
---

# Phase 13 Plan 01: Landing Page Components Migration Summary

**10 landing section components + scoped dark-theme CSS + useInView hook migrated from Orchids to apps/web with TrustBar rewritten to use real brand logos**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-03T19:14:10Z
- **Completed:** 2026-03-03T19:21:10Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- Created landing.css with all ContextOS brand variables, glow utilities, gradient utilities, and keyframe animations scoped under .landing-theme
- Migrated all 10 landing section components (Nav, Hero, TrustBar, ProblemSection, HowItWorks, Features, ProductDemo, Integrations, CTASection, Footer)
- Rewrote TrustBar to use real brand logo components (LinearLogo, SlackLogo, GitHubLogo, NotionLogo, FathomLogo) and "Integrates with" heading
- Updated Integrations component with 5 live integrations using brand logos + 4 "soon" integrations
- Created barrel export index.ts for clean imports

## Task Commits

Each task was committed atomically:

1. **Task 1: Create landing CSS and useInView hook** - `a35aa5b` (feat)
2. **Task 2: Migrate all 9 landing section components** - `465c63c` (feat)

## Files Created/Modified
- `apps/web/src/app/landing.css` - Scoped dark theme CSS with brand variables, glow/gradient utilities, keyframes
- `apps/web/src/hooks/useInView.ts` - IntersectionObserver hook for scroll-triggered animations
- `apps/web/src/components/landing/Nav.tsx` - Fixed nav with scroll transparency, 3 anchor links, waitlist CTA
- `apps/web/src/components/landing/Hero.tsx` - Hero with MockContextPage, scroll parallax, teal gradient
- `apps/web/src/components/landing/TrustBar.tsx` - Integration logo bar with real brand logos
- `apps/web/src/components/landing/ProblemSection.tsx` - Before/after comparison with useInView
- `apps/web/src/components/landing/HowItWorks.tsx` - 3-step grid with inline tool visuals
- `apps/web/src/components/landing/Features.tsx` - Bento grid with LargeCardMockup timeline
- `apps/web/src/components/landing/ProductDemo.tsx` - Browser mockup with video placeholder
- `apps/web/src/components/landing/Integrations.tsx` - 5 live + 4 soon integrations grid
- `apps/web/src/components/landing/CTASection.tsx` - Waitlist email form (client-side only)
- `apps/web/src/components/landing/Footer.tsx` - Brand, trimmed product/company links, 2026 copyright
- `apps/web/src/components/landing/index.ts` - Barrel export for all 10 components

## Decisions Made
- CSS variables scoped under `.landing-theme` class to avoid leaking into dashboard theme
- Grain overlay uses `.landing-grain` class instead of `body::before` for composability with landing layout
- TrustBar rewritten to use `brand-logos.tsx` components instead of inline SVGs
- Nav links trimmed to Features, How It Works, Integrations (no Pricing per plan)
- Footer links trimmed to existing pages only (no Pricing, Docs, Changelog, Blog, About)
- Emoji faces in ProblemSection replaced with text emoticons for cross-platform safety
- No new npm dependencies added -- all components are pure React + Tailwind + custom CSS

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced emoji characters with text emoticons in ProblemSection**
- **Found during:** Task 2 (ProblemSection migration)
- **Issue:** Original used emoji characters which could render inconsistently across platforms and violate project convention of no emojis in files
- **Fix:** Replaced frustrated face emoji with ":(" and rocket emoji with ":)" text
- **Files modified:** apps/web/src/components/landing/ProblemSection.tsx
- **Verification:** Component renders without emoji characters
- **Committed in:** 465c63c (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor cosmetic adjustment. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 10 landing section components ready for Plan 02 (landing layout and page assembly)
- landing.css ready to be imported in the landing layout
- useInView hook ready for use by all scroll-animated sections
- Barrel export enables clean imports: `import { Nav, Hero, ... } from '@/components/landing'`

## Self-Check: PASSED

All 13 created files verified present. Both task commits (a35aa5b, 465c63c) verified in git log.

---
*Phase: 13-adopt-orchids-landing-page-into-apps-web*
*Completed: 2026-03-03*
