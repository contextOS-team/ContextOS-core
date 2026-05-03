# Phase 40 — Deferred Items (out of scope of this phase's tasks)

## Pre-existing test failures (NOT caused by Phase 40 work)

### `tests/test_telegram.py::TestWebhookEndpoint::test_accepts_valid_secret`

**Status:** Pre-existing failure on the legacy `/webhook/{workspace_id}` route.
**Root cause:** Test asserts `resp.json() == {"status": "ok"}` but the legacy
webhook handler in `backend/src/routers/telegram.py:webhook` returns
`{"ok": True}`. The mismatch predates Phase 40.

**Verification:** `git stash` revert of all Phase-40 changes still shows this
test failing in isolation, confirming the failure is unrelated to this plan.

**Disposition:** Plan 03 deletes the legacy `/webhook/{workspace_id}` route
and this test will be removed/rewritten alongside it. No fix needed in Plan 01.

**Discovered during:** Plan 40-01, Task 1 verification run.

### `tests/test_telegram.py::TestProcessTelegramUpdate::test_processes_normal_message` (and 5 sibling tests)

**Status:** Pre-existing failures on Phase-26 `process_telegram_update` tests.
**Failing tests:**
- `test_processes_normal_message`
- `test_supergroup_chat_id_int64`
- `test_workspace_id_must_be_uuid`
- `test_edited_message_processed`
- `test_reply_tracking`
- `test_date_parsed_as_naive_utc`

**Root cause:** All assert `mock_session.execute.assert_called_once()` but
`process_telegram_update` now calls `extract_and_populate_graph` (graph
extraction added in a later phase) which itself executes a second statement.
The tests need to be updated to allow >1 execute call (or use `assert_called`
without count). Independent of Phase 40.

**Verification:** `git stash` revert of all Phase-40 changes still shows
these tests failing, confirming the failures predate this plan.

**Disposition:** Out of scope for Plan 40-01. Plan 03 (cleanup) may rewrite
these tests when it deletes the legacy ingestion path.

**Discovered during:** Plan 40-01, Task 1 verification run.

## Pre-existing eslint warnings in `apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx`

**Status:** Pre-existing warnings (NOT introduced by Plan 40-02).
**Findings:**
- Line 6: `'Skeleton' is defined but never used` (`@typescript-eslint/no-unused-vars`)
- Line 157: `Unused eslint-disable directive (no problems were reported from 'react-hooks/exhaustive-deps')`

**Root cause:** Both predate Phase 40 — `Skeleton` import is leftover from an
earlier loading-state version; the disable directive on line 157 was added in
Plan 39-03 to silence a then-real warning that has since been resolved by other
edits.

**Verification:** Plan 40-02 makes zero edits to `integration-cards.tsx`
(`git diff HEAD apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx`
returns empty). The Telegram card already wires `connectForm={<TelegramConnect ... />}`
which now renders the new pairing UI automatically via the rewritten
`TelegramConnect` wrapper.

**Disposition:** Out of scope for Plan 40-02. Plan 03 (cleanup) will touch this
file to remove `<TelegramSyncSection />` and the `disconnectTelegram` import,
which is the natural place to also remove the unused `Skeleton` import and the
stale eslint-disable directive.

**Discovered during:** Plan 40-02, Task 2 verification run.
