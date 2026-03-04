---
phase: 17-onboarding-wizard
plan: 01
subsystem: ui
tags: [react, onboarding, wizard, oauth, supabase, css-animation, stepper]

# Dependency graph
requires:
  - phase: 16-auth-redesign
    provides: user_onboarding_state table, auth guards, onboarding layout
provides:
  - 4-step onboarding wizard shell at /onboarding
  - Step 1 workspace naming with DB persistence
  - Step 2 Linear connection gate (required)
  - Step 3 optional sources grid (Slack, GitHub, Notion, Fathom)
  - Success checkmark animation component
  - Pure opacity crossfade step transition CSS
affects: [17-02-context-page, 20-settings]

# Tech tracking
tech-stack:
  added: []
  patterns: [wizard-state-machine, db-backed-step-persistence, oauth-return-detection]

key-files:
  created:
    - apps/web/src/components/onboarding/onboarding-wizard.tsx
    - apps/web/src/components/onboarding/step-indicator.tsx
    - apps/web/src/components/onboarding/step-workspace.tsx
    - apps/web/src/components/onboarding/step-linear.tsx
    - apps/web/src/components/onboarding/step-sources.tsx
    - apps/web/src/components/onboarding/source-card.tsx
    - apps/web/src/components/onboarding/success-checkmark.tsx
  modified:
    - apps/web/src/app/onboarding/page.tsx
    - apps/web/src/app/globals.css

key-decisions:
  - "Wizard reads current_step from DB on mount to handle OAuth return detection"
  - "Fathom uses inline API key form within sources grid rather than separate dialog"
  - "Back button positioned below step content for minimal visual interference"

patterns-established:
  - "Wizard state machine: DB-backed step persistence with optimistic UI advancement"
  - "OAuth return detection: check integration status on mount, show success checkmark, auto-advance"
  - "animate-step-enter: pure opacity crossfade for multi-step flows"

requirements-completed: [ONB-01, ONB-02, ONB-03, ONB-04, ONB-06, ONB-08]

# Metrics
duration: 6min
completed: 2026-03-04
---

# Phase 17 Plan 01: Onboarding Wizard Shell Summary

**4-step onboarding wizard with DB-backed state machine, dot stepper, workspace naming, Linear required gate, and optional sources grid with animated checkmark confirmations**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-04T16:37:31Z
- **Completed:** 2026-03-04T16:43:30Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Replaced Phase 16 placeholder with fully interactive 4-step wizard at /onboarding
- Wizard state machine persists current_step to user_onboarding_state table via Supabase client
- OAuth return detection shows animated teal checkmark for 800ms then auto-advances
- Steps 1-3 fully functional: workspace name saves to DB, Linear triggers OAuth, sources grid shows 4 options with Fathom inline API key form
- Pure opacity crossfade (200ms spring curve) for step transitions

## Task Commits

Each task was committed atomically:

1. **Task 1: Wizard shell, step indicator, and step components for steps 1-3** - `f5de724` (feat)
2. **Task 2: CSS crossfade transition classes** - Already in codebase (pre-committed in `b8758ed`)

## Files Created/Modified
- `apps/web/src/components/onboarding/onboarding-wizard.tsx` - Main wizard state machine with DB-backed step persistence
- `apps/web/src/components/onboarding/step-indicator.tsx` - 4-dot minimal progress indicator
- `apps/web/src/components/onboarding/step-workspace.tsx` - Step 1 workspace name input with DB save
- `apps/web/src/components/onboarding/step-linear.tsx` - Step 2 Linear connection required gate
- `apps/web/src/components/onboarding/step-sources.tsx` - Step 3 optional sources 2x2 grid
- `apps/web/src/components/onboarding/source-card.tsx` - Individual source card with connected checkmark overlay
- `apps/web/src/components/onboarding/success-checkmark.tsx` - Animated teal checkmark with scale-in spring
- `apps/web/src/app/onboarding/page.tsx` - Replaced placeholder with wizard, kept toast handler
- `apps/web/src/app/globals.css` - animate-step-enter opacity crossfade class (pre-committed)

## Decisions Made
- Wizard reads current_step from DB on mount and fetches workspace name + integration status in parallel for fast load
- Fathom uses inline API key form below the sources grid (not a separate dialog) for simplicity
- Back button positioned as subtle text link below step content, not competing with primary actions
- Step 4 rendered as placeholder with shimmer skeleton (Plan 02 replaces with context page generation)
- Going back is ephemeral (no DB write) -- DB records highest completed step only

## Deviations from Plan

None - plan executed exactly as written.

Note: The CSS animation class (Task 2) was already present in the codebase from a prior commit. The pre-existing broken `@import "tailwindcss/typography"` was also already fixed in a prior commit.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Step 4 placeholder ready for Plan 02 (context page generation + completion flow)
- All wizard infrastructure (state machine, step persistence, OAuth detection) in place
- Success checkmark component reusable for step 4 completion animation

---
*Phase: 17-onboarding-wizard*
*Completed: 2026-03-04*
