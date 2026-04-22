---
phase: 39-slack-user-token-migration-dm-support
plan: 03
subsystem: ui

tags: [slack, dm-toggle, reauth, settings, shadcn, radix-switch, optimistic-update, sonner]

# Dependency graph
requires:
  - phase: 39-01
    provides: "GET /api/slack/status extended with needs_reauth + include_dms; POST /api/slack/dms/toggle endpoint"
provides:
  - "SlackProviderStatus / SlackStatusResponse TypeScript types in lib/api.ts"
  - "getSlackStatus() and toggleSlackDms() typed API clients"
  - "SlackReauthBanner component (amber, triggers connectSlack() OAuth)"
  - "SlackDmToggle component (optimistic update, reads include_dms on mount, sonner toast)"
  - "Wired banner + toggle + existing channel picker into Settings -> Integrations -> Slack card"
  - "Reusable shadcn Switch component at components/ui/switch.tsx"
affects: [39-04, phase-onboarding-consent, settings-ux]

# Tech tracking
tech-stack:
  added:
    - "shadcn Switch component (radix-ui Switch namespace, project pattern)"
  patterns:
    - "Fetch-separately for provider-specific extras (getSlackStatus) instead of expanding the aggregator endpoint"
    - "Optimistic UI with rollback on toggle error (pattern reused across future integration toggles)"
    - "Label wrapper with min-h-10 to guarantee >=40px hit area while Switch stays visually compact"
    - "eslint-disable-next-line with explicit justification when excluding unstable parent-prop callbacks from useEffect deps"

key-files:
  created:
    - "apps/web/src/components/ui/switch.tsx"
    - "apps/web/src/app/dashboard/integrations/slack-reauth-banner.tsx"
    - "apps/web/src/app/dashboard/integrations/slack-dm-toggle.tsx"
  modified:
    - "apps/web/src/lib/api.ts"
    - "apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx"

key-decisions:
  - "[39-03] Chose Option B for useEffect deps — omit fetchStatuses with eslint-disable because it is a parent-prop and is NOT wrapped in useCallback (would cause infinite loop)"
  - "[39-03] Added shadcn Switch component manually via radix-ui namespace import (matches existing Label pattern; avoided shadcn CLI which would pull standalone @radix-ui/react-switch)"
  - "[39-03] Fetch-separately pattern: integration-cards calls getSlackStatus() on mount instead of extending the aggregator /api/integrations/status — matches how GitHub/GitLab fetch repos separately"
  - "[39-03] SlackDmToggle re-reads include_dms on mount when initialIncludeDms is undefined — guarantees toggle state survives page reload"
  - "[39-03] Channel picker (<SlackChannels/>) preserved in all connected states per CONTEXT.md revision (channels stay on bot webhook path)"
  - "[39-03] Hit-area met via Label wrapper with min-h-10 instead of enlarging the Switch visually — keeps the shadcn h-5 w-9 switch aesthetic"

patterns-established:
  - "Provider-specific status extras: define ExtendedStatus interface in lib/api.ts that extends ProviderStatus with optional provider-only fields; fetch separately via dedicated endpoint"
  - "Optimistic toggle: setState(next) → await mutation → setState(response) on success or setState(prev) on error, with sonner toast for every transition"
  - "Hit-area via wrapper: wrap small visual controls in a Label/min-h-10 container instead of styling the control itself"

requirements-completed: [SLACK-USR-03, SLACK-USR-05]

# Metrics
duration: 4min
completed: 2026-04-22
---

# Phase 39 Plan 03: Settings DM Toggle + Re-auth Banner Summary

**Settings -> Integrations -> Slack card now exposes a DM ingestion toggle with optimistic updates and an amber re-auth banner for legacy workspaces whose OAuth install predates the user_scope change.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-22T15:27:05Z
- **Completed:** 2026-04-22T15:31:03Z
- **Tasks:** 3
- **Files modified:** 2 (api.ts, integration-cards.tsx)
- **Files created:** 3 (switch.tsx, slack-reauth-banner.tsx, slack-dm-toggle.tsx)

## Accomplishments

- `lib/api.ts` exports `SlackProviderStatus`, `SlackStatusResponse`, `getSlackStatus`, `toggleSlackDms` — all typed end-to-end
- `SlackReauthBanner` triggers the existing `connectSlack()` OAuth flow with sonner error reporting on failure
- `SlackDmToggle` performs optimistic updates with rollback on error, re-reads `include_dms` on mount for persistence, and shows a required privacy caption ("DM messages will be indexed for context generation. Only you can see this data.")
- `integration-cards.tsx` renders banner + toggle + channel picker in the correct conditional combinations without disturbing any existing integration
- Missing shadcn `Switch` component was added at `components/ui/switch.tsx` using the `radix-ui` namespace import pattern already used by `Label`

## Task Commits

1. **Task 1: Extend lib/api.ts with new types and toggleSlackDms client** — `b578315` (feat)
2. **Task 2: Create slack-reauth-banner and slack-dm-toggle components** — `50f86fe` (feat)
3. **Task 3: Wire banner + toggle into integration-cards.tsx** — `f5aacda` (feat)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `apps/web/src/lib/api.ts` — Added `SlackProviderStatus`, `SlackStatusResponse`, `getSlackStatus()`, `toggleSlackDms()`; narrowed `IntegrationStatusResponse.slack` to the new extended type.
- `apps/web/src/components/ui/switch.tsx` — New shadcn-style Switch using `radix-ui` namespace (parallel to existing `label.tsx`).
- `apps/web/src/app/dashboard/integrations/slack-reauth-banner.tsx` — Amber banner with `AlertTriangle` icon, `text-wrap: pretty` body, `connectSlack()` redirect.
- `apps/web/src/app/dashboard/integrations/slack-dm-toggle.tsx` — Toggle with optimistic update, mount-time `getSlackStatus()` refetch, privacy caption, >=40px hit area via Label wrapper.
- `apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx` — New `useEffect` keyed on `slack.status` populates `slackExtra` state; Slack card children wrap banner + toggle + existing `<SlackChannels/>` in a `space-y-3` div.

## Decisions Made

- **fetchStatuses stability verdict: Option B** (omit from deps with eslint-disable). `fetchStatuses` is a prop passed from the parent (`settings/page.tsx`) and is not wrapped in `useCallback` there — including it in an effect's dependency array would produce a new reference every parent render and cause an infinite re-render loop. The effect body does not call `fetchStatuses`; it calls `getSlackStatus()`. So the correct dependency is just `[slack.status]`.
- **Switch component added manually** rather than via `pnpm dlx shadcn@latest add switch`. The project uses the `radix-ui` monorepo package (e.g., `import { Label as LabelPrimitive } from "radix-ui"`), not the standalone `@radix-ui/react-*` packages that shadcn CLI installs by default. Keeping the pattern consistent with `label.tsx`.
- **Hit area** met via a Label wrapper using `min-h-10` (40px). The underlying Switch keeps the shadcn default aesthetic (`h-5 w-9` = 20×36px) while the visible row and click target comfortably exceed 40×40px.

## Deviations from Plan

None — plan executed exactly as written, including the Option B branch the plan recommended in its PRE-IMPLEMENTATION READ note for Task 3.

## Issues Encountered

- **Pre-existing typecheck errors in `src/components/onboarding/step-sources.tsx`** (6 errors referencing `NotionSyncStatus.synced` / `.total`) — present at HEAD before Plan 39-03 began. Verified via `git stash` + typecheck. Out of scope for this plan. Logged to `.planning/phases/39-slack-user-token-migration-dm-support/deferred-items.md`. Plan 39-04 will likely touch `step-sources.tsx` and can fix them in that pass; otherwise a hygiene PR is appropriate.

## User Setup Required

None — no new external service configuration, env vars, or dashboard steps. The endpoints this plan targets (`/api/slack/status`, `/api/slack/dms/toggle`) shipped in Plan 39-01.

## Known-unverified states for Plan 39-04 human-verify checkpoint

These need the dev-server smoke test Plan 39-04 will run:

- [ ] Reauth banner appears on a workspace whose `oauth_slack_{ws}_user_access` is absent from Vault (Plan 39-01 legacy case).
- [ ] DM toggle hidden while `needs_reauth=true`.
- [ ] Toggling DM ingestion ON → reload page → toggle still reads ON (persistence via mount refetch).
- [ ] Toggling DM ingestion with backend intentionally returning 409 → UI rolls back and sonner error toast appears.
- [ ] Channel picker remains visible and functional when `needs_reauth=true` AND when toggle is ON.
- [ ] Settings page does not enter an infinite render loop (DevTools Performance record for 5s — render count stabilizes).

## Next Phase Readiness

- Plan 39-04 (onboarding consent flow in `step-sources.tsx`) can now reuse `SlackDmToggle` or the `toggleSlackDms` client directly.
- Existing connected users have an immediate way to act on DM ingestion the moment Plan 39-01's backend deploys — no wait for onboarding polish.
- The pre-existing `step-sources.tsx` Notion typecheck errors remain on the roadmap for Plan 39-04 to address while it is in that file.

## Self-Check: PASSED

All claimed files exist on disk:
- apps/web/src/lib/api.ts (modified)
- apps/web/src/components/ui/switch.tsx (created)
- apps/web/src/app/dashboard/integrations/slack-reauth-banner.tsx (created)
- apps/web/src/app/dashboard/integrations/slack-dm-toggle.tsx (created)
- apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx (modified)
- .planning/phases/39-slack-user-token-migration-dm-support/39-03-SUMMARY.md (this file)

All claimed commits exist in git history:
- b578315 (Task 1)
- 50f86fe (Task 2)
- f5aacda (Task 3)

---

*Phase: 39-slack-user-token-migration-dm-support*
*Completed: 2026-04-22*
