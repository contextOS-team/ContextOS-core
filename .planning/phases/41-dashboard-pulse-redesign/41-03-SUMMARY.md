---
phase: 41-dashboard-pulse-redesign
plan: 03
subsystem: ui
tags: [nextjs, react, supabase, dashboard, chrome, sync]

requires:
  - phase: 32-activity-events-emission
    provides: activity_events rows used for source activity and sync chrome state
provides:
  - shared dashboard chrome nav rendered across dashboard subroutes
  - passive source freshness/sync indicator in the top-right cluster
  - neutral avatar puck with profile/settings/sign-out menu parity
  - route coverage and sync-state tests for dashboard chrome
  - source freshness risk note for first-team launch planning
affects: [dashboard-chrome, dashboard-home, source-freshness]

key-files:
  created:
    - apps/web/src/app/dashboard/chrome/chrome-nav.tsx
    - apps/web/src/app/dashboard/chrome/sync-indicator.tsx
    - apps/web/src/app/dashboard/chrome/use-sync-state.ts
    - apps/web/src/app/dashboard/chrome/avatar-puck.tsx
    - apps/web/src/app/dashboard/chrome/__tests__/use-sync-state.test.ts
    - apps/web/src/app/dashboard/chrome/__tests__/sync-indicator.test.tsx
    - apps/web/src/app/dashboard/chrome/__tests__/chrome-nav-routes.test.tsx
    - .planning/phases/41-dashboard-pulse-redesign/41-SOURCE-FRESHNESS-RISKS.md
  modified:
    - apps/web/src/app/dashboard/sidebar.tsx
    - apps/web/src/app/dashboard/page.tsx
    - apps/web/src/app/dashboard/widgets/empty-state.tsx
    - apps/web/package.json
    - apps/web/package-lock.json
    - apps/web/tsconfig.json
  removed:
    - apps/web/src/app/dashboard/chrome/integration-drawer.tsx
    - apps/web/src/app/dashboard/widgets/integration-dots.tsx

requirements-completed: [DASH-04]
accepted-deviations:
  - "The Radix integration drawer, Sync all button, reconnect CTA, and clickable integration-health cluster were removed after the human visual checkpoint."
  - "The top-right text now says `updated ...` and derives idle recency from source activity plus sync lifecycle events, not only sync_completed rows."
  - "The legacy bottom integration dots were removed early because they duplicated the same source-status concept and conflicted with the accepted chrome direction."

completed: 2026-05-21
---

# Phase 41 Plan 03: Chrome Checkpoint Summary

**Dashboard chrome now has shared navigation, passive source freshness, and a neutral avatar puck across dashboard subroutes.**

## Accomplishments

- Extracted the shared dashboard top nav into `chrome/` and kept `sidebar.tsx` as the compatibility shim used by `dashboard/layout.tsx`.
- Added a passive sync/source indicator with `unknown`, `idle`, `syncing`, and `error` states backed by Supabase `activity_events`.
- Restyled the avatar away from mint so mint remains reserved for the wordmark and active nav underline.
- Added route coverage so the chrome renders on home, context, settings, activity, and graph routes.
- Removed the bottom integration dots from home; source freshness now belongs in the chrome, not as a stray footer row.
- Captured source freshness risks and launch policy concerns in `41-SOURCE-FRESHNESS-RISKS.md`.

## Human Checkpoint Deviations

The original plan called for a clickable chrome cluster that opened a right-side integration drawer with provider rows, reconnect copy, and a `Sync all` button. The human checkpoint rejected that direction as visually noisy and mismatched with the intended dashboard.

Accepted behavior after review:

- The chrome indicator is passive. It is not a button.
- No slide-over drawer ships in this checkpoint.
- No `Sync all` or `reconnect` affordance ships in this checkpoint.
- The label changed from `last synced ...` to `updated ...` because `last synced 3d ago` implied a global provider sync success claim that the product cannot truthfully make yet.
- Idle recency now uses both source activity events and sync lifecycle events, so the chrome answers "did source data update recently?" rather than "did every provider fully sync recently?"

This means `DASH-04` is complete against the accepted checkpoint scope, not against the rejected drawer/button draft in the original plan.

## Verification

- `cd apps/web && npx vitest run src/app/dashboard/chrome/` - passed, 18 tests.
- `cd apps/web && npm run typecheck` - passed.
- `cd apps/web && npx eslint src/app/dashboard/chrome/ src/app/dashboard/page.tsx src/app/dashboard/widgets/empty-state.tsx` - passed.
- OpenLogs was connected for backend and frontend monitoring during the visual checkpoint; the post-fix frontend tail was clean.

## Open Product Risk

Source freshness is still a product risk for the first startup pilot. The current chrome can truthfully say that sources were recently updated, but it cannot yet prove every connected provider is healthy or fully synced.

Follow-up candidates are tracked in `41-SOURCE-FRESHNESS-RISKS.md`: provider-level source health, Jira/Linear fallback reconciliation, GitLab parity, scheduled Fathom polling, clearer Slack user-token polling copy, and a first-team onboarding runbook.

## Next Plan Readiness

Plan 41-02 can now own the dashboard body without carrying the source-status footer. The top chrome is already shared by the dashboard layout and should be left visually quiet while the pulse surface is rebuilt below it.

