# Phase 39 Deferred Items

Items discovered during execution that are out of scope for the current plan.

## Pre-existing test failures (not caused by Phase 39 changes)

### `tests/test_slack_channels.py::TestGetChannelsEndpoint::test_get_channels_returns_cached`

- **Discovered:** Plan 39-01, Task 2 verification
- **Status:** Pre-existing (verified via `git stash && pytest`)
- **Root cause:** Test provides only 2 `session.execute` side_effects, but the
  `/channels` route handler now calls `session.execute` 3 times:
    1. Auth lookup via `get_current_user` -> workspace_id
    2. `get_cached_channels(...)` -> integration row
    3. `get_selected_channels(...)` -> integration row (again)
- **Fix path:** Extend the `side_effect` list in `test_get_channels_returns_cached`
  to include a third result for the `get_selected_channels` call, or refactor
  the route to query the integration once and pass it into both helpers.
- **Out of scope because:** Plan 39-01 does not touch `get_channels`,
  `get_cached_channels`, or `get_selected_channels`. CONTEXT.md explicitly
  keeps the channel picker unchanged.
## 2026-04-22 — Discovered during 39-03 execution

### Pre-existing typecheck errors in step-sources.tsx

- File: `apps/web/src/components/onboarding/step-sources.tsx`
- Errors (6 total) reference `NotionSyncStatus.synced` and `NotionSyncStatus.total` which are not defined on that interface (it has `sync_progress` and `sync_total`).
- Lines: 668, 670, 692, 696, 698.
- Verified pre-existing at HEAD commit 521827c — NOT caused by Plan 39-03 changes.
- Out of scope for 39-03. Likely from a prior Notion refactor. Recommend fix in a separate hygiene PR or as part of Plan 39-04's onboarding work if touching step-sources.tsx.

## 2026-04-22 — Discovered during 39-04 execution

### Pre-existing mypy errors in `src/services/sync_scheduler.py`
- Line 69 (`ContextPage.deleted_at.is_(None)`): `union-attr` error on the nullable column type.
- Lines 198–199: `where()` argument typing complaints in `_expire_stale_generations`.
- Lines 205–206: `Result[Any]` has no attribute `rowcount`; `Unused "type: ignore" comment`.
- Verified pre-existing via `git stash` before Plan 39-04 edits. Out of scope — my new Slack DM polling block added no mypy errors.

### Pre-existing mypy errors in `src/services/slack_events.py`, `src/services/slack_oauth.py`
- 6 `type-arg` errors for missing generic type parameters on `dict`.
- Surfaced by mypy now that sync_scheduler imports slack_messages (which transitively imports slack_events + slack_oauth). Pre-existing in the source files themselves.

### Pre-existing ruff lints in `src/services/sync_scheduler.py`
- I001 import block unsorted (pre-existing `from datetime import timedelta` after blank line).
- E501 long comments at lines 32 and elsewhere.

### Pre-existing ESLint warning in `step-sources.tsx`
- Line 501 (was 490 before 39-04): `next.has(key) ? next.delete(key) : next.add(key)` expression-form ternary in `toggle()`. Pre-existing in `OnboardingRepoPicker`. Verified via `git stash`.

