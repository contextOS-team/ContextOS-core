---
phase: 39-slack-user-token-migration-dm-support
plan: 01
subsystem: api
tags: [slack, oauth, vault, fastapi, dm, user-token, integration]

# Dependency graph
requires:
  - phase: 03-slack-integration
    provides: "Slack bot token OAuth flow, Vault storage convention, Events API webhook, channel picker"
provides:
  - "SLACK_USER_SCOPES constant (DM-only: im/mpim/users) wired into build_auth_url"
  - "Dual-token exchange_code: persists bot + user tokens in Vault on OAuth callback"
  - "get_user_token(session, workspace_id) helper mirroring get_bot_token (no legacy fallback)"
  - "integration.config.slack_user_id populated from authed_user.id"
  - "GET /api/slack/status now returns needs_reauth + include_dms"
  - "POST /api/slack/dms/toggle endpoint with 409-on-needs-reauth semantics"
  - "integration.config.include_dms and dms_first_enabled_at keys for DM opt-in tracking"
  - "_should_filter no longer filters messages with text length < 10 chars"
affects: [39-02-dm-polling, 39-03-settings-ui, 39-04-polling-wire-up, slack-daily-digest]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-token OAuth: bot_access + user_access under the same Provider.SLACK workspace keying"
    - "Integration.config as JSONB bag for DM opt-in state (include_dms, dms_first_enabled_at, slack_user_id)"
    - "needs_reauth flag computed from (status=connected AND user_access missing in Vault)"

key-files:
  created: []
  modified:
    - "backend/src/services/slack_oauth.py"
    - "backend/src/services/slack_events.py"
    - "backend/src/routers/slack.py"
    - "backend/tests/test_slack.py"

key-decisions:
  - "SLACK_USER_SCOPES locked to DM-only (im/mpim/users) -- no channels:* or groups:* per CONTEXT.md"
  - "User tokens stored under oauth_slack_{ws}_user_access (parallel to bot_access); no legacy name fallback"
  - "slack_user_id merged into integration.config post-upsert to preserve existing keys (external_name, selected_channels)"
  - "dms_first_enabled_at is set on first enable so Plan 02's DM poller knows to run a 7-day backfill"
  - "_should_filter drops the <10-char length check for ALL paths (webhook and DM poller); bot and system-subtype filters stay"
  - "exchange_code tolerates missing authed_user (legacy Slack responses) -- warns and continues with bot-only token"

patterns-established:
  - "Dual-token Vault key naming: token_name(Provider.SLACK, ws, 'user_access') alongside 'bot_access'"
  - "needs_reauth endpoint pattern: status=connected AND user-scope token missing -> prompt re-OAuth"
  - "Integration config merge after upsert: re-query integration row, spread dict, patch new keys, commit once"

requirements-completed: [SLACK-USR-01, SLACK-USR-05, SLACK-USR-07]

# Metrics
duration: 17min
completed: 2026-04-22
---

# Phase 39 Plan 01: Slack User Token OAuth Foundation Summary

**Dual-token Slack OAuth (bot + user) with DM-only user scopes, Vault storage under `user_access`, needs_reauth signal, DM toggle endpoint, and short-message filter removal across all ingestion paths.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-04-22T15:04:51Z
- **Completed:** 2026-04-22T15:22:08Z
- **Tasks:** 2 (both TDD-driven: RED -> GREEN per task)
- **Files modified:** 4

## Accomplishments

- `SLACK_USER_SCOPES = "im:read,im:history,mpim:read,mpim:history,users:read,users:read.email"` shipped; DM-only per CONTEXT.md, no channels/groups scopes.
- `build_auth_url` now requests `user_scope=SLACK_USER_SCOPES`, so Slack's callback returns `authed_user.access_token` alongside the bot token.
- `exchange_code` persists the user token in Vault at `oauth_slack_{ws}_user_access`, and writes `integration.config.slack_user_id = "U..."` without clobbering existing keys (`external_name`, `selected_channels`, etc.).
- `get_user_token(session, workspace_id)` added, mirroring `get_bot_token` but without a legacy-name fallback (user tokens are new in Phase 39).
- `disconnect()` now deletes both bot and user Vault entries.
- `GET /api/slack/status` returns `needs_reauth` and `include_dms`. `needs_reauth=true` for any pre-Phase-39 workspace that's `connected` but has no `user_access` token in Vault.
- `POST /api/slack/dms/toggle` persists `include_dms` in integration.config, returns 409 `{"detail": "needs_reauth"}` when the user token is missing, 400 when Slack is not connected, and 401/403 without a JWT. First-time enable records `dms_first_enabled_at` so Plan 02's DM poller knows to run a 7-day backfill.
- `_should_filter` no longer drops messages under 10 characters. Short signals like "done", "no", "approved" now ingest on BOTH the existing webhook path and (future) the DM polling path, since both call the same helper.

## Task Commits

1. **Task 1 RED:** `32d1f41` (test: add failing tests for dual-token OAuth and user token helpers)
2. **Task 1 GREEN:** `82cdf18` (feat: dual-token OAuth capture with Vault storage and user token helper)
3. **Task 2 RED:** `fbae41d` (test: add failing tests for status, DM toggle, short-message retention)
4. **Task 2 GREEN:** `e3022bd` (feat: status needs_reauth+include_dms, DM toggle endpoint, short-message retention)
5. **Deferred items:** `7dd3585` (chore: log deferred test_get_channels_returns_cached regression)

## Files Modified

- `backend/src/services/slack_oauth.py` — Added `SLACK_USER_SCOPES`, `_extract_tokens`, user token persistence in `exchange_code`, `get_user_token` helper; updated `disconnect` to clean both Vault entries; imported `WorkspaceIntegration` + `select` for config patch.
- `backend/src/services/slack_events.py` — Removed <10-char filter from `_should_filter`; updated module docstring; retained bot + system-subtype filters.
- `backend/src/routers/slack.py` — Extended `get_status` with `needs_reauth` and `include_dms` fields; added `POST /dms/toggle` endpoint; imported `read_token`, `token_name`.
- `backend/tests/test_slack.py` — Added `TestUserTokenOAuth` (5 tests), `TestDmToggleAndStatus` (9 tests); inverted `test_filters_short_messages` to `test_short_messages_no_longer_filtered`; adjusted existing `test_disconnect_soft_deletes_token` execute-call counting for dual-token delete.

## Decisions Made

- **Vault key suffix `user_access`**: parallels existing `bot_access`; downstream plans (02 channel-unchanged, 02 DM poller) use `token_name(Provider.SLACK, ws, "user_access")` verbatim.
- **No legacy-name fallback in `get_user_token`**: user tokens are new in Phase 39, so the `get_bot_token` migration logic doesn't apply.
- **Config patch post-upsert**: rather than change the shared `upsert_workspace_integration` helper signature, we re-query the integration row and patch `slack_user_id` into `config` before commit. Preserves `external_name` and any `selected_channels`/`available_channels` from an earlier connect.
- **`dms_first_enabled_at` is workspace-scoped, set once**: only on the first `enabled=true` toggle. Plan 02's poller deletes or checks against it after the backfill completes.
- **409 for needs_reauth in toggle**: distinct from 400 (not connected) so the frontend can differentiate "reconnect to get DM scopes" vs "Slack integration missing entirely".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adjusted existing test_disconnect_soft_deletes_token execute-call counting**
- **Found during:** Task 1 GREEN verification
- **Issue:** The existing test mocks `session.execute` via a call-counting `side_effect` that expected the `WorkspaceIntegration` query to be the 3rd execute call. After adding `user_access` to `vault_token_names`, `disconnect_provider` now calls `delete_token` twice (each issuing one SQL execute), shifting the integration query to the 4th call.
- **Fix:** Updated the counting logic in `test_disconnect_soft_deletes_token` to expect the integration query at `call_count == 4` instead of `3`, with a comment explaining the Phase 39 flow.
- **Files modified:** `backend/tests/test_slack.py`
- **Verification:** Full `TestSlackOAuthService` class passes (4/4).
- **Committed in:** `82cdf18` (Task 1 GREEN commit).

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary adjustment to keep the existing disconnect regression test accurate for dual-token cleanup. No scope creep.

## Issues Encountered

- **Mock-session wiring for authenticated endpoints**: `get_current_user` itself issues a `session.execute` to look up workspace membership, so simple `mock_session.execute.return_value = mock_result` returns the integration row when pydantic expects a UUID. Resolved by introducing a local `_wire_session(...)` test helper that returns `UUID(TEST_WORKSPACE_ID)` on the first execute (auth) and the caller-supplied integration rows thereafter.
- **Pre-existing ruff line-length discrepancy**: ruff default is 88, but project `pyproject.toml` declares `line-length = 100`. Verified via `ruff check --line-length=100` that none of the new code introduces line-length violations (all flagged lines are pre-existing).
- **Pre-existing test_get_channels_returns_cached failure**: Verified via `git stash` that this failure exists without my changes. Logged to `deferred-items.md` for future cleanup. Out of scope: Plan 39-01 doesn't touch `get_channels`.

## Deferred Items

See `deferred-items.md` in this phase directory:
- `tests/test_slack_channels.py::TestGetChannelsEndpoint::test_get_channels_returns_cached` — pre-existing failure in `side_effect` sequencing after the route was refactored to call both `get_cached_channels` and `get_selected_channels` (3 execute calls vs the test's 2 mocks).

## User Setup Required

None - no external service configuration required for this plan. Users who already connected Slack before Phase 39 will see `needs_reauth=true` on `/api/slack/status` and must click "Reconnect Slack" (UI wired in Plan 03) to grant the DM user scopes.

## Next Phase Readiness

**Ready for Plan 39-02 (DM polling service):**
- `get_user_token(session, workspace_id)` available for the poller to authenticate `users.conversations` + `conversations.history` calls.
- `integration.config.include_dms` and `integration.config.dms_first_enabled_at` drive poller gating and backfill window.
- `_should_filter` is path-agnostic — the DM poller can reuse it directly.

**Ready for Plan 39-03 (Settings UI):**
- `GET /api/slack/status` exposes `needs_reauth` and `include_dms` for the banner + toggle.
- `POST /api/slack/dms/toggle` accepts `{enabled}` and persists; UI should handle 409 by prompting re-OAuth.

**No blockers for downstream plans.**

## Self-Check: PASSED

Verified:
- `backend/src/services/slack_oauth.py` — FOUND (modified)
- `backend/src/services/slack_events.py` — FOUND (modified)
- `backend/src/routers/slack.py` — FOUND (modified)
- `backend/tests/test_slack.py` — FOUND (modified)
- `.planning/phases/39-slack-user-token-migration-dm-support/deferred-items.md` — FOUND (created)
- Commit `32d1f41` (Task 1 RED) — FOUND in git log
- Commit `82cdf18` (Task 1 GREEN) — FOUND in git log
- Commit `fbae41d` (Task 2 RED) — FOUND in git log
- Commit `e3022bd` (Task 2 GREEN) — FOUND in git log
- Commit `7dd3585` (deferred items) — FOUND in git log
- All 40 tests in `tests/test_slack.py` pass.
- Spot-check: `build_auth_url` produces URL with `user_scope=im%3Aread,...` and no channels/groups scopes.

---
*Phase: 39-slack-user-token-migration-dm-support*
*Completed: 2026-04-22*
