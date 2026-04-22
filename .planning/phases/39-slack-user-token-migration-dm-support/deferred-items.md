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

### ~~Pre-existing typecheck errors in step-sources.tsx~~ — RESOLVED 2026-04-22 (commit `2671848`)

- File: `apps/web/src/components/onboarding/step-sources.tsx`
- Errors referenced `NotionSyncStatus.synced` and `NotionSyncStatus.total` which are not defined on that interface (it has `sync_progress` / `sync_total` / `pages_count`).
- Verified pre-existing at HEAD commit 521827c — NOT caused by Plan 39-03 changes.
- **Resolution:** Surfaced as a CI blocker during Phase 39 deploy (Docker frontend build failed typecheck). Fixed by mapping in-flight progress to `sync_progress` and final count to `pages_count` (fallback `sync_total`).

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

## Phase 39.1 Gap Closure (inline)

**Date:** 2026-04-22
**Shipped during:** Plan 39-04 human-verify checkpoint (E2E verification surfaced missing channel events)

### What shipped

Inline gap-closure (no formal PLAN.md) to extend the user-token poller to
cover channels, not just DMs. Four atomic commits:

1. `test(39.1)` + `feat(39.1)`: expand `SLACK_USER_SCOPES` to include
   `channels:read`, `channels:history`, `groups:read`, `groups:history`.
2. `test(39.1)` + `feat(39.1)`: rename `DM_CONVERSATION_TYPES` ->
   `USER_CONVERSATION_TYPES = "im,mpim,public_channel,private_channel"`.
   Added Test K guarding that `_upsert_messages` is channel-agnostic.
3. `feat(39.1)`: re-auth banner copy now mentions "channel + DM ingestion".
4. `docs(39.1)`: this entry + `39.1-GAP-SUMMARY.md`.

### Why (scope rationale)

The Phase 39-04 human-verify checkpoint surfaced that the Slack bot
doesn't receive channel events because the `conversations.join`
auto-join code (commit d96b944 on branch `fix/slack-channel-selection`)
was never merged to main. Getting bot-invite permissions from the CTO
is blocked, so we pivoted to using the existing user-token poller
(Plan 39-02) to cover channels too -- the user token doesn't need
channel invitations.

### Trade-offs accepted

- **Duplicate ingestion path** (bot webhook + user poll): safe because
  `SlackMessage` upsert is idempotent on `(workspace_id, channel_id, ts)`
  via `uq_slack_msg`, and Plan 39-02 already enforces SET-clause parity
  at runtime via the `inspect.getsource()` assertion in Test F.
- **Rate limits**: `conversations.history` caps at 1 rpm for
  non-Marketplace apps on the user token. Acceptable for small
  workspaces; RESEARCH.md's concerns about scale still apply. 429
  handling already in place via `_slack_get` retry-once-with-Retry-After.
- **Coverage scope**: user token only sees channels the installer is
  already a member of. If the installer is not in a channel, neither
  path ingests it. The deferred auto-join fix on
  `fix/slack-channel-selection` should still eventually land once CTO
  permissions clear, for full channel coverage via the bot path.
- **Config key name retained**: `include_dms` now semantically controls
  all user-token polling (DMs + channels). A rename would require a
  data migration and breaks roundtrip with Plan 39-01's existing
  integration.config shape. Documented in module docstring and STATE.

