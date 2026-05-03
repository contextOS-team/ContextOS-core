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
