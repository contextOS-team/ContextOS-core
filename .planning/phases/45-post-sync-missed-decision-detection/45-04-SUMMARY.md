---
phase: 45-post-sync-missed-decision-detection
plan: "04"
status: complete
completed: 2026-05-25
requirements: [GAP-02, GAP-03]
---

# Phase 45 Plan 04 Summary

## Accomplishments

- Added typed missed-decision review API helpers and action helpers in `apps/web/src/lib/api.ts`.
- Added dashboard data integration for `needsReviewSuggestions`, section-local load errors, and post-action row removal.
- Added `NeedsReviewSuggestions` as a bounded dashboard `Needs review` section for source-backed missed-decision candidates.
- Kept unconfirmed candidates out of `Recent decisions`; the dashboard renders the missed-decision review surface in the right rail above `Active context` / `Needs you`.
- Preserved a single visible `Needs review` dashboard queue by falling back to the Phase 44 generic suggestions section only when missed-decision suggestions are absent.
- Added Vitest coverage for API routes, local fetch failure handling, hidden empty state, top 3/default and hard cap 5 rendering, evidence fields, approved action labels, destructive confirmations, action callback behavior, action failure copy, and dashboard placement.

## Files Created Or Modified

- `apps/web/src/lib/api.ts`
- `apps/web/src/app/dashboard/pulse/types.ts`
- `apps/web/src/app/dashboard/pulse/use-dashboard-data.ts`
- `apps/web/src/app/dashboard/page.tsx`
- `apps/web/src/app/dashboard/pulse/needs-review-suggestions.tsx`
- `apps/web/src/app/dashboard/pulse/needs-review-suggestions.test.tsx`
- `apps/web/src/app/dashboard/pulse/__tests__/use-dashboard-data.test.tsx`

## Commits

- `dff6b0c` - `test(45-04): add needs review dashboard contracts`
- `648009e` - `feat(45-04): add missed decision dashboard review`
- `3ca18ce` - `test(45-04): cover dashboard review placement`

## Verification

- `pnpm --dir apps/web exec vitest run src/app/dashboard/pulse/needs-review-suggestions.test.tsx` passed: 8 tests.
- `pnpm --dir apps/web exec vitest run src/app/dashboard/pulse/needs-review-suggestions.test.tsx src/app/dashboard/pulse/__tests__/use-dashboard-data.test.tsx src/app/dashboard/pulse/__tests__/components.test.tsx` passed: 21 tests.
- `pnpm --dir apps/web exec vitest run` passed: 29 files, 188 tests.
- `pnpm --dir apps/web typecheck` passed.
- `uv run --directory backend pytest tests/test_missed_decision_actions.py tests/test_missed_decision_promotion.py tests/test_missed_decision_candidates.py tests/test_missed_decision_scanner.py tests/test_suggestions.py -q` passed: 44 tests.
- Plan grep gates for API helpers, dashboard data, component labels, and dashboard ordering passed.
- `git diff --check` passed.

## Verification Notes

- The Browser in-app automation backend was not available in this session (`agent.browsers.list()` returned no browsers), so the manual visual check could not be completed through Browser.
- A plain unauthenticated `curl -I http://localhost:3000/dashboard` reached the local Next app but redirected to `/login`, so it could not verify the authenticated dashboard view.
- Vitest emitted existing React `act(...)` warnings in dashboard/UI tests; tests still passed.

## Deviations

- Manual visual verification remains a follow-up because the browser backend was unavailable and the dashboard requires authentication.

## Next

- Run `$gsd-verify-work 45` or a human-authenticated dashboard visual check before shipping.
- Link/login Supabase and push migration `00042` to the remote project before production deploy.
