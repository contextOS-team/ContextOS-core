---
phase: 39-slack-user-token-migration-dm-support
plan: 02
subsystem: api
tags: [slack, polling, dm, user-token, httpx, pg-insert, upsert, embedding, graph]

# Dependency graph
requires:
  - phase: 39-01
    provides: "SLACK_USER_SCOPES constant, dual-token OAuth with Vault user_access, get_user_token(session, workspace_id) helper, integration.config keys (include_dms, dms_first_enabled_at, slack_user_id), _should_filter without the <10-char rule"
provides:
  - "poll_user_messages(session, workspace_id) async entry point for DM + group-DM ingestion"
  - "_enumerate_dms() calling users.conversations with types=im,mpim only (no public/private channel enumeration)"
  - "_fetch_history() with cursor pagination, 429 Retry-After handling, 401/invalid_auth -> _NeedsReauth"
  - "_upsert_messages() with SET-clause parity vs. slack_events._handle_message (text, user_id, thread_ts, parent_ts, is_thread_reply, raw_data) + per-message embedding queue + graph extraction"
  - "BACKFILL_DAYS=7, BACKFILL_MESSAGES_PER_CONVERSATION_CAP=100, DEFAULT_PAGE_SIZE=100 constants"
  - "_compute_oldest helper that coerces naive-UTC last_user_poll_at to UTC before deriving Slack ts (fixes TZ-offset bug vs. the literal plan spec)"
  - "config.last_user_poll_at ISO-naive-UTC bookkeeping + config.dms_backfill_done=true flag flipped on first backfill"
affects: [39-04-polling-wire-up, slack-daily-digest]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sequential DM iteration (never asyncio.gather) to stay under Slack's 1-rpm non-Marketplace limit"
    - "_slack_get() helper: single 429 retry honoring Retry-After, uniform ok=false fallback shape"
    - "Post-commit SELECT for inserted id (mirrors slack_events._handle_message) instead of INSERT ... RETURNING to keep mypy happy and match the webhook flow"
    - "SET-clause drift guard: inspect.getsource() assertion on _upsert_messages pinning the required field list (SLACK-USR-04)"
    - "Graph extraction wrapped in try/except per message -- graph failures are logged and non-fatal, never block ingestion"

key-files:
  created:
    - "backend/src/services/slack_messages.py"
    - "backend/tests/test_slack_messages.py"
  modified: []

key-decisions:
  - "[39-02] Coerce naive last_user_poll_at to UTC in _compute_oldest before .timestamp() -- the literal plan spec used naive-as-local, causing a TZ-offset bug. Naive-UTC ISO strings are the codebase convention"
  - "[39-02] _upsert_messages follows slack_events pattern: pg_insert + on_conflict_do_update + separate post-commit SELECT for the id, instead of INSERT ... RETURNING (cleaner mypy types, structural parity with the webhook flow)"
  - "[39-02] SET-clause parity with slack_events._handle_message verified TWICE: (a) side-by-side grep during implementation, (b) inspect.getsource() runtime assertion in TestUpsert.test_F guarding against future drift"
  - "[39-02] 429 Retry-After handling lives in a single _slack_get() helper shared by users.conversations AND conversations.history -- no retry-logic duplication"
  - "[39-02] Invalid_auth raised as internal _NeedsReauth sentinel; caller short-circuits remaining conversations and returns reason=needs_reauth without crashing or touching config.last_user_poll_at"
  - "[39-02] Backfill cap enforced inside _fetch_history via the `cap` parameter -- the loop truncates and stops paginating once cap messages accumulate, preventing runaway history fetches on large DMs"

patterns-established:
  - "Public poll_user_messages contract: returns {ingested, skipped, reason} with reason in {dms_disabled, needs_reauth, not_connected, None}; never raises for expected states"
  - "DM-only enumeration lock: users.conversations is called with types=im,mpim exclusively. Channels (public + private) remain on the bot Events API webhook path per CONTEXT.md"
  - "Per-message dual-path ingestion safety: uq_slack_msg upsert guarantees idempotence. Dedup between webhook and poll is automatic; overlaps count as skipped rather than ingested"

requirements-completed: [SLACK-USR-02, SLACK-USR-04]

# Metrics
duration: 15min
completed: 2026-04-22
---

# Phase 39 Plan 02: DM Polling Service Summary

**DM + group-DM polling service for Slack user tokens, with DM-only enumeration, 7-day backfill + 100-message cap on first opt-in, 429 Retry-After handling, and upsert/embedding/graph parity vs. the existing webhook path.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-22T15:26:34Z
- **Completed:** 2026-04-22T15:41:23Z
- **Tasks:** 2 (both TDD-driven: RED -> GREEN per task)
- **Files created:** 2

## Accomplishments

- `backend/src/services/slack_messages.py` shipped with the full DM polling path.
- `poll_user_messages(session, workspace_id)` entry point returns `{ingested, skipped, reason}` and honors the `include_dms` gate, `needs_reauth` signal, and `not_connected` short-circuit without raising for any expected state.
- `_enumerate_dms()` calls `users.conversations?types=im,mpim&exclude_archived=true&limit=200` with cursor pagination. Public and private channels are **never** enumerated or polled -- they stay on the bot Events API webhook path per Phase 39 CONTEXT.md.
- `_fetch_history()` paginates `conversations.history` with the computed `oldest`, honors 429 Retry-After once, raises `_NeedsReauth` on `invalid_auth`/`token_revoked`/`not_authed`, and returns `[]` for per-conversation errors (`missing_scope`, `not_in_channel`, `channel_not_found`) so one bad DM never aborts the cycle.
- `_compute_oldest()` handles three inputs: backfill (`now - 7d`), steady-state (`fromisoformat(last_user_poll_at)` coerced to UTC before `.timestamp()`), and unset (returns `None`). The UTC coercion fixes a TZ-offset bug in the literal plan spec since `last_user_poll_at` is stored as naive-UTC.
- `_upsert_messages()` mirrors `slack_events._handle_message` field-for-field:
  - Same filter (`_should_filter`): drops bot messages + system subtypes.
  - Same upsert: `pg_insert(SlackMessage).on_conflict_do_update(constraint="uq_slack_msg", set_=...)`.
  - Same SET-clause fields: `text, user_id, thread_ts, parent_ts, is_thread_reply, raw_data`.
  - Same post-upsert flow: commit, SELECT id back, `embedding.queue_embedding_generation`, `extract_and_populate_graph` with `source_type="slack_message"`.
  - Graph extraction failures are caught and logged (non-fatal), matching the webhook handler's best-effort semantics.
- Backfill mode caps each conversation at `BACKFILL_MESSAGES_PER_CONVERSATION_CAP=100` and stops paginating once reached. `dms_backfill_done=true` is written on first successful backfill cycle.
- Bookkeeping: on success, `integration.config.last_user_poll_at` is set to a naive-UTC ISO string (`datetime.now(UTC).replace(tzinfo=None).isoformat()`), preserving other config keys via a dict-spread merge.

## Return Shape

```python
{
    "ingested": int,          # newly inserted rows
    "skipped":  int,          # filter-drops + dedup-updates
    "reason":   str | None,   # "dms_disabled" | "needs_reauth" |
                              # "not_connected" | None on success
}
```

Reason codes:
- `not_connected` -- no Slack integration row, or status != "connected".
- `dms_disabled` -- integration exists but `config.include_dms` is falsy. **Zero HTTP calls.**
- `needs_reauth` -- `get_user_token` raised `SlackOAuthError`, OR Slack returned `invalid_auth`/`token_revoked`/`not_authed` during enumeration or history. `last_user_poll_at` is NOT advanced in this case.
- `None` -- success. `last_user_poll_at` advanced; `dms_backfill_done` flipped True if this was the first backfill.

## Task Commits

Each task was TDD-driven (RED -> GREEN) and committed atomically:

1. **Task 1 RED: failing tests A-D for DM poll skeleton** - `450d022` (test)
2. **Task 1 GREEN: DM poller skeleton with enumeration** - `d507fba` (feat)
3. **Task 2 RED: failing tests E-J for upsert+embedding+graph parity** - `1e9c020` (test)
4. **Task 2 GREEN: wire upsert + embedding + graph parity in `_upsert_messages`** - `8f71078` (feat)

## Files Created/Modified

- `backend/src/services/slack_messages.py` (new, ~400 lines) -- full polling service with `poll_user_messages` entry point, `_enumerate_dms`, `_fetch_history`, `_compute_oldest`, `_slack_get` (shared 429 handling), `_upsert_messages`, and `_NeedsReauth` internal sentinel.
- `backend/tests/test_slack_messages.py` (new, ~650 lines) -- 12 tests across `TestEnumerate` (A-D, plus a missing-key variant of A), `TestPolling` (E, G, H, I), and `TestUpsert` (F, J) with shared `_make_dm_list_response`/`_make_history_response`/`_make_message`/`_make_http_resp` helpers and autouse fixtures for embedding + graph patches.

## Backfill Contract

- **Trigger:** `config.dms_first_enabled_at` is set AND `config.dms_backfill_done` is falsy.
- **Window:** `oldest = now - 7 days` as a Slack ts float-string (`:.6f`).
- **Per-conversation cap:** 100 messages. `_fetch_history` truncates and stops paginating once reached, even if `has_more=true`.
- **Completion flag:** `config.dms_backfill_done = True` written atomically with `last_user_poll_at` after a clean cycle (no needs_reauth).
- **Subsequent cycles:** Revert to steady-state incremental polling with `oldest = last_user_poll_at` (UTC-coerced).

## Rate-Limit Strategy (as implemented)

- **Concurrency:** Sequential iteration of DM IDs via a plain `for` loop. No `asyncio.gather` per CONTEXT.md.
- **Page size:** `DEFAULT_PAGE_SIZE = 100`. RESEARCH.md flags 1-rpm + limit=15 as the worst-case non-Marketplace cap; 429 handling absorbs bursts when they occur.
- **429 handling:** Centralized in `_slack_get()`. Sleeps `int(Retry-After)` seconds (default 1) and retries once. Two consecutive 429s return `{"ok": false, "error": "rate_limited"}` so the caller bails gracefully without crashing.
- **Non-200 HTTP:** Returns `{"ok": false, "error": f"http_{status}"}` for uniform downstream handling.

## SET-Clause Parity Confirmation

Verified in both directions:

```
=== backend/src/services/slack_events.py (line 248-258) ===
    stmt = stmt.on_conflict_do_update(
        constraint="uq_slack_msg",
        set_={
            "text": stmt.excluded.text,
            "user_id": stmt.excluded.user_id,
            "thread_ts": stmt.excluded.thread_ts,
            "parent_ts": stmt.excluded.parent_ts,
            "is_thread_reply": stmt.excluded.is_thread_reply,
            "raw_data": stmt.excluded.raw_data,
        },
    )

=== backend/src/services/slack_messages.py (inside _upsert_messages) ===
        stmt = stmt.on_conflict_do_update(
            constraint="uq_slack_msg",
            set_={
                "text": stmt.excluded.text,
                "user_id": stmt.excluded.user_id,
                "thread_ts": stmt.excluded.thread_ts,
                "parent_ts": stmt.excluded.parent_ts,
                "is_thread_reply": stmt.excluded.is_thread_reply,
                "raw_data": stmt.excluded.raw_data,
            },
        )
```

**Field set identical.** Drift-guarded at runtime by `TestUpsert.test_F_upsert_parity_with_slack_events`, which uses `inspect.getsource(_upsert_messages)` to assert each required field string is present in the function body.

## Decisions Made

See `key-decisions` frontmatter. The two notable deviations from the literal plan spec:

1. **TZ-aware oldest computation.** The plan literally specified `datetime.fromisoformat(config["last_user_poll_at"]).timestamp()`, but since `last_user_poll_at` is written as naive-UTC (`datetime.now(UTC).replace(tzinfo=None).isoformat()`), `.timestamp()` would treat it as local time and produce a TZ-offset bug. Fixed by coercing naive -> UTC before `.timestamp()`. Documented in the function docstring.
2. **Post-commit SELECT for id instead of INSERT ... RETURNING.** The plan's draft used `.returning(SlackMessage.id)`, which triggered a mypy overload-match error. Refactored to match `slack_events._handle_message` exactly: execute upsert, commit, then `select(SlackMessage.id).where(...)`. Cleaner typing and structural parity with the webhook handler.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TZ-offset bug in `_compute_oldest` spec**
- **Found during:** Task 1 GREEN (test D writing expected value from literal plan spec).
- **Issue:** The plan's literal spec (`datetime.fromisoformat(last_user_poll_at).timestamp()`) silently treats naive-UTC strings as local time, producing a TZ-offset in `oldest` and causing DM history polls to fetch the wrong window. Symptom: test D asserting the buggy value failed against the correct implementation.
- **Fix:** Coerce naive datetimes to UTC (`dt.replace(tzinfo=UTC)`) before `.timestamp()`. Updated `test_D_incremental_uses_last_user_poll_at` to assert the correct TZ-aware expectation. Added a comment in the test explaining the rationale.
- **Files modified:** `backend/src/services/slack_messages.py`, `backend/tests/test_slack_messages.py`
- **Verification:** `pytest tests/test_slack_messages.py::TestEnumerate::test_D_incremental_uses_last_user_poll_at` passes.
- **Committed in:** `d507fba` (Task 1 GREEN).

**2. [Rule 3 - Blocking] Import structure for TDD Task 1 stub**
- **Found during:** Task 1 GREEN (ruff + mypy sweep after initial commit).
- **Issue:** Task 1's stubbed `_upsert_messages` didn't actually use `embedding`, `extract_and_populate_graph`, `_should_filter`, `_ts_to_datetime`, or `SlackMessage`, so ruff F401 flagged them as unused imports. But the test file's autouse fixtures patch `embedding.queue_embedding_generation` and `extract_and_populate_graph` on the module, so the attributes MUST exist.
- **Fix:** Kept the plan's required imports at module scope with `# noqa: F401` comments explaining Task 2 wires them. Task 2 GREEN then removes the noqa lines and uses the imports properly.
- **Files modified:** `backend/src/services/slack_messages.py`
- **Verification:** ruff passes; autouse fixtures patch successfully; TestEnumerate all green.
- **Committed in:** `d507fba` (Task 1 GREEN), finalized in `8f71078` (Task 2 GREEN).

**3. [Rule 1 - Bug] mypy overload mismatch on `.returning()`**
- **Found during:** Task 2 GREEN (mypy sweep).
- **Issue:** The plan's draft used `pg_insert(...).on_conflict_do_update(...).returning(SlackMessage.id)`. mypy couldn't match any of the `Insert.returning()` overloads with the SQLModel `UUID` attribute. Any `# type: ignore` would be brittle given the 60+ overloads.
- **Fix:** Adopted `slack_events._handle_message`'s exact pattern: execute upsert, commit, then `select(SlackMessage.id).where(workspace_id, channel_id, slack_ts)` per message. Removes the `.returning()` call entirely. Cleaner typing + structural parity with the webhook handler.
- **Files modified:** `backend/src/services/slack_messages.py`, `backend/tests/test_slack_messages.py` (test F and test J session.execute side_effect lists extended from 2 to 3 results).
- **Verification:** `mypy src/services/slack_messages.py` clean on this file; `pytest tests/test_slack_messages.py` all 12 green.
- **Committed in:** `8f71078` (Task 2 GREEN).

---

**Total deviations:** 3 auto-fixed (2 bugs in the literal plan spec + 1 blocking import structure issue).
**Impact on plan:** All three deviations were necessary for correctness. No scope creep; all fixes stay inside the plan's defined surface area (slack_messages.py + test_slack_messages.py).

## Issues Encountered

- **Pre-existing unrelated test failure.** `tests/test_slack_channels.py::TestGetChannelsEndpoint::test_get_channels_returns_cached` requires a live Postgres connection and fails in the sandbox. Verified pre-existing via `git stash`; already logged to `.planning/phases/39-slack-user-token-migration-dm-support/deferred-items.md` during Plan 39-01. Out of scope for Plan 39-02.
- **Pre-existing mypy noise in `slack_events.py` / `slack_oauth.py`** (`Missing type parameters for generic type "dict"`). Out of scope per SCOPE BOUNDARY rule -- these are 39-01-era issues in files this plan does not modify.

## User Setup Required

None -- no external service configuration. The new module does not add env vars, new scopes, or new OAuth flows (user scopes were added in 39-01). Plan 39-04 will wire `poll_user_messages` into the scheduler; 39-03 owns the settings UI for the `include_dms` toggle.

## Next Phase Readiness

Plan 39-04 (scheduler wiring) should:

1. Add a periodic job that iterates `WorkspaceIntegration` rows with `provider="slack"` AND `status="connected"` AND `config.include_dms = true`, and calls `await poll_user_messages(session, workspace_id)` for each.
2. Respect the poll cadence defined in 39-04 (sequential, not parallel across workspaces, to avoid fanning out Slack API hits).
3. Log `reason=needs_reauth` occurrences at WARN level and surface them to the UI via the existing `/api/slack/status.needs_reauth` signal from Plan 39-01.
4. Do **not** re-implement filtering, upsert, or rate-limit handling -- everything is already inside `poll_user_messages`.
5. Optional telemetry: record `ingested` + `skipped` counters per workspace for observability.

No blockers for 39-03 (settings UI) or 39-04 (scheduler).

## Self-Check: PASSED

- `backend/src/services/slack_messages.py` exists.
- `backend/tests/test_slack_messages.py` exists.
- Commit `450d022` (RED tests A-D) in git log.
- Commit `d507fba` (Task 1 GREEN) in git log.
- Commit `1e9c020` (RED tests E-J) in git log.
- Commit `8f71078` (Task 2 GREEN) in git log.
- All 12 tests in `tests/test_slack_messages.py` pass.
- `mypy src/services/slack_messages.py` clean on this file (remaining errors live in unrelated pre-existing files).
- `ruff check src/services/slack_messages.py tests/test_slack_messages.py` clean.
- SET-clause parity verified: `grep -A8 "uq_slack_msg" slack_events.py slack_messages.py` shows identical field set.

---
*Phase: 39-slack-user-token-migration-dm-support*
*Completed: 2026-04-22*
