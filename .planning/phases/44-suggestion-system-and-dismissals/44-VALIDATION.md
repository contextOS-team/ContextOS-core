---
phase: 44
slug: suggestion-system-and-dismissals
status: ready
created: 2026-05-25
---

# Phase 44 - Validation Plan

## Automated Checks

Backend:
- `uv run --directory backend pytest backend/tests/test_suggestions.py -x`
- `uv run --directory backend pytest backend/tests/test_digest.py backend/tests/test_suggestions.py -x`

Frontend:
- `pnpm --dir apps/web exec vitest run src/app/dashboard/pulse/__tests__/components.test.tsx`
- `pnpm --dir apps/web typecheck`

Repository:
- `git diff --check`
- `gsd-sdk query check.decision-coverage-plan .planning/phases/44-suggestion-system-and-dismissals .planning/phases/44-suggestion-system-and-dismissals/44-CONTEXT.md`

## Acceptance Evidence

| Requirement | Evidence |
|-------------|----------|
| SUG-01 | Migration/model/service fields include workspace, type, source evidence, priority, status, and provenance |
| SUG-02 | Lifecycle service tests and router actions prove dismiss/snooze/resolve/reopen survive reload as persisted state |
| SUG-03 | Dashboard component tests prove `Needs review` is bounded, hidden when empty, and placed in the right rail without displacing `Recent decisions` |
| SUG-04 | Missing-source generation tests prove a specific Decision node can produce a source-backed `missing_source_coverage` suggestion |

## Manual Review

- Inspect `/dashboard` after implementation to confirm `Needs review` is above `Active context` in the right rail and absent when there are no visible suggestions.
- Inspect `/dashboard/suggestions` for lifecycle recovery and full queue visibility.
