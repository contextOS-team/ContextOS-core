---
phase: 39-slack-user-token-migration-dm-support
plan: 04
subsystem: api + web
tags: [slack, scheduler, polling, onboarding, user-token, e2e-verified, integration]

# Dependency graph
requires:
  - phase: 39-slack-user-token-migration-dm-support
    provides: "Plan 39-01 dual-token OAuth + Plan 39-02 poll_user_messages service + Plan 39-03 Settings toggle/banner + Phase 39.1 user-token channel polling"
provides:
  - "Module-level import of poll_user_messages in sync_scheduler.py (patchable at src.services.sync_scheduler.poll_user_messages)"
  - "Per-workspace Slack user-token polling wired into 15-minute run_polling_fallback loop (fresh AsyncSession per workspace, exception isolation)"
  - "Onboarding Step 4 DM consent inline panel (OnboardingSlackDms) -- auto-expands once after Slack OAuth redirect, default OFF"
  - "End-to-end verification on a live Slack workspace: 177 messages ingested across 3 DMs, 1 group DM, and 4 channels"
  - "Two pre-existing Slack upsert bugs fixed (constraint name mismatch + tz-aware/naive datetime mismatch) that were silently broken on the bot webhook path"
affects: [slack-daily-digest, slack-channel-picker, onboarding-wizard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scheduler-side integration pattern: module-level import of service function, fresh async_session() per workspace, per-workspace try/except with logger.exception, reason-based log level (INFO on ingested, WARNING on needs_reauth, silent on dms_disabled)"
    - "Onboarding inline consent pattern extended: ExpandedSource union now includes 'slack'; OnboardingSlackDms mirrors OnboardingNotionSync layout"
    - "Upsert by index_elements (columns) instead of named UniqueConstraint — avoids model-vs-migration constraint name drift"

key-files:
  created:
    - "backend/tests/test_sync_scheduler_slack.py"
    - ".planning/phases/39-slack-user-token-migration-dm-support/39-04-SUMMARY.md"
  modified:
    - "backend/src/services/sync_scheduler.py"
    - "apps/web/src/components/onboarding/step-sources.tsx"
    - "backend/src/services/slack_events.py"
    - "backend/src/services/slack_messages.py"

key-decisions:
  - "poll_user_messages is imported at module top of sync_scheduler.py (not deferred inside the try block) so monkeypatch.setattr(\"src.services.sync_scheduler.poll_user_messages\", ...) works in tests"
  - "Fresh async_session() per workspace inside the poll loop mirrors the existing Notion reconcile pattern and avoids cross-workspace transaction bleed"
  - "Reason-based log level: INFO only on ingested>0, silent on dms_disabled (common case), WARNING on needs_reauth/not_connected to surface configuration drift, logger.exception on unexpected crashes"
  - "Slack DM poll block placed between code-index-freshness and daily-digest blocks so digests see freshly-polled DM data in the same cycle"
  - "Onboarding Slack card auto-expand guarded by autoExpandedRef so it only triggers once per onboarding session (same pattern as notion/github/gitlab)"
  - "Upsert switched to ON CONFLICT (columns...) instead of ON CONFLICT ON CONSTRAINT uq_slack_msg — the named constraint in the model does not match the auto-generated constraint name in the actual DB (pre-existing bug)"
  - "_ts_to_datetime returns naive UTC to match the TIMESTAMP WITHOUT TIME ZONE column type (asyncpg rejects mixing naive and aware datetimes — pre-existing bug)"

patterns-established:
  - "Scheduler wiring for new polled integrations: module-level import + per-workspace fresh session + exception isolation + reason-based log level"
  - "Onboarding inline consent panel reused across integrations (notion sync, slack DMs) — auto-expand ref pattern with source-specific component"

requirements-completed: [SLACK-USR-02, SLACK-USR-03, SLACK-USR-04]

# Metrics
duration: ~29min (code) + live E2E verification
completed: 2026-04-22
---

# Phase 39 Plan 04: Scheduler + Onboarding + E2E Verification Summary

**Slack user-token DM/channel polling wired into the 15-minute scheduler loop, onboarding DM consent panel added inline, and the entire Phase 39 story verified end-to-end on a live Slack workspace (177 messages ingested across DMs, group DMs, and channels).**

## Performance

- **Duration:** ~29 min of plan execution (Tasks 1-2), followed by live E2E verification on user's real Slack workspace
- **Started:** 2026-04-22T15:47:54Z (Task 1 RED commit `07e2218`)
- **Code complete:** 2026-04-22T15:54:16Z (Task 2 commit `35ac75d`)
- **Post-E2E fixes:** 2026-04-22T20:16:07Z (constraint + tz fixes `55b166e`, `5649097`)
- **User approval:** 2026-04-22 (after live E2E verification)
- **Tasks:** 3 (2 automated + 1 human-verify checkpoint)
- **Files modified:** 4 (2 Plan 39-04 scope, 2 fixed during E2E)

## Accomplishments

- **Scheduler wired up**: Every 15 minutes, `run_polling_fallback` now iterates all connected Slack workspaces and calls `poll_user_messages` for each — one fresh AsyncSession per workspace, exceptions isolated, reason-based log level. Scheduler test suite passes 4/4.
- **Onboarding consent panel shipped**: Slack card in Step 4 auto-expands once after OAuth redirect to show the DM toggle inline. Default OFF. Onboarding completion is independent of DM opt-in state.
- **E2E verified on a real workspace (177 messages, 8 conversations)**: User ran the 8-step verification script against their live Region Lab workspace. All checks passed — re-auth banner, reconnect flow, toggle persistence, channel picker parity, DM ingestion visible in the Context Feed, short-message retention, onboarding consent, and dual-mode sanity (no duplicate rows).
- **Two pre-existing bugs surfaced + fixed**: The user-token poller's exception handling exposed two silent bugs in the shared Slack ingestion path that had been quietly broken on the bot webhook (the webhook handler catches all exceptions). Fixed in-scope as Rule 3 blocking items since they prevented Phase 39 end-to-end verification.

## Task Commits

**Task 1: Wire poll_user_messages into run_polling_fallback (TDD)**
1. `07e2218` — test(39-04): add failing test for Slack DM polling in scheduler (RED)
2. `dba5ab6` — feat(39-04): wire poll_user_messages into 15-minute scheduler loop (GREEN)

**Task 2: Add DM consent inline panel to onboarding step-sources.tsx**
3. `35ac75d` — feat(39-04): add DM consent inline panel to onboarding step-sources

**Task 3: End-to-end human verification** — no file writes, user ran 8-step script and replied `approved`.

### Related commits (surfaced during E2E, committed outside the Plan 39-04 task chain)

4. `55b166e` — fix(slack): upsert by index_elements instead of named constraint
   - Model declares `UniqueConstraint(name="uq_slack_msg")` on `slack_messages`, but the actual DB constraint has the default auto-generated name (`slack_messages_workspace_id_channel_id_slack_ts_key`) from the original migration. `ON CONFLICT ON CONSTRAINT uq_slack_msg` therefore failed with `UndefinedObjectError` the moment the user-token poller tried to ingest.
   - Switched both upsert paths (bot webhook `_handle_message`, user-token `_upsert_messages`) to `ON CONFLICT (columns...)` which doesn't depend on constraint name.
   - **Pre-existing silent bug** on the bot webhook path — the webhook handler catches exceptions and moves on, so this never surfaced. The user-token poller exercised it cleanly.

5. `5649097` — fix(slack): strip tzinfo in _ts_to_datetime to match column type
   - `slack_messages.slack_created_at` is `TIMESTAMP WITHOUT TIME ZONE`, but `_ts_to_datetime` returned a UTC-aware datetime. asyncpg rejects mixing naive and aware datetimes, so insertions failed with `DataError`.
   - Fixed the helper to return naive UTC. Both the bot webhook path and the Phase 39 user-token poller consume this helper, so this fix unblocks both.
   - **Pre-existing silent bug** — same webhook exception-swallowing dynamic as commit 4.

## Files Created/Modified

- `backend/src/services/sync_scheduler.py` — Added module-level `from src.services.slack_messages import poll_user_messages` next to existing service imports. Added per-workspace Slack DM polling block between code-index freshness and daily-digest blocks.
- `backend/tests/test_sync_scheduler_slack.py` — New file. 4 async tests (per-workspace iteration, exception isolation, non-Slack provider no-op, reason=dms_disabled doesn't block other scheduler duties). All patch via `src.services.sync_scheduler.poll_user_messages` (locally-bound name).
- `apps/web/src/components/onboarding/step-sources.tsx` — Extended `ExpandedSource` union with `'slack'`. Added slack case to `autoExpandedRef` useEffect and `handleSourceCardClick`. Slack card onClick toggles the panel when connected. New `OnboardingSlackDms` component renders `<SlackDmToggle />` with a helper note.
- `backend/src/services/slack_events.py` (related commit) — Upsert uses `index_elements=["workspace_id","channel_id","slack_ts"]`. `_ts_to_datetime` returns naive UTC.
- `backend/src/services/slack_messages.py` (related commit) — Upsert switched to `index_elements` for consistency with the fix in slack_events.

## Live E2E Verification Results

User ran the 8-step verification script on their live Region Lab Slack workspace and replied `approved`. Observed outcomes:

1. **Re-auth banner (existing install)** — PASS. Amber "Reconnect required for channel + DM ingestion" banner appeared for the pre-Phase-39 install; DM toggle was not visible until reconnect.
2. **Reconnect clears banner, reveals toggle** — PASS. New scopes granted (channels + DMs), banner cleared, DM toggle visible (default OFF) with privacy caption, channel picker intact.
3. **Toggle persists** — PASS. ON state survived page refresh; OFF state survived refresh (SlackDmToggle re-reads include_dms on mount).
4. **Channel picker regression** — PASS. Select/deselect + save works; selection persists across refreshes.
5. **DM ingestion end-to-end** — PASS. **177 messages ingested across 3 DMs, 1 group DM, and 4 channels** via the 15-minute user-token poller. Messages visible in the Context Feed.
6. **Short-message filter removed** — PASS. Messages under 10 chars now appear in `slack_messages` on both the bot webhook path and the user-token poll path.
7. **Onboarding DM consent** — PASS. After Slack OAuth redirect during onboarding, the DM consent panel auto-expanded once below the Slack source card. Toggle ON inside onboarding worked without navigation. "Go to dashboard" proceeded regardless of DM toggle state.
8. **Dual-mode sanity** — PASS. Both ingestion paths (bot webhook for channels, user-token poll for DMs + channels) coexist cleanly. No duplicate rows because `SlackMessage` upsert is idempotent on `(workspace_id, channel_id, slack_ts)`.

## Decisions Made

- **Module-level import over deferred import**: Tests must patch the locally-bound `src.services.sync_scheduler.poll_user_messages` name for the scheduler to see the mock. A deferred `from src.services.slack_messages import poll_user_messages` inside the try block would re-resolve the name every call and bypass the patch. The plan made this explicit and Task 1 followed the guidance.
- **Fresh AsyncSession per workspace**: Mirrors the existing Notion reconcile pattern. Prevents one workspace's polling transaction from leaking into another's. Minor cost (session setup overhead) for a massive correctness win.
- **Slack DM poll placed before daily digests**: Digests in the same cycle can see freshly-polled DM messages. If polling happened after digests, DM context wouldn't show up until the next day's digest.
- **Onboarding DM toggle default OFF**: Privacy-first. User must explicitly opt in — even during onboarding — so we never silently ingest DMs. Consistent with Plan 39-01's /dms/toggle semantics.
- **Fix upstream, not around**: The constraint-name and tz bugs were in the shared Slack ingestion path, not in Phase 39 code. Rather than patching around them in `slack_messages.py`, we fixed them at the source so the bot webhook path also benefits. Both are pre-existing bugs, not Phase 39 regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed upsert constraint name mismatch in shared Slack ingestion path**
- **Found during:** Task 3 (E2E verification). User-token poller raised `UndefinedObjectError` on first attempted ingest: `constraint "uq_slack_msg" for table "slack_messages" does not exist`.
- **Issue:** Model declares `UniqueConstraint(name="uq_slack_msg")` but the actual DB constraint has the default auto-generated name from the original migration. `ON CONFLICT ON CONSTRAINT uq_slack_msg` fails at runtime.
- **Fix:** Switched both upsert paths (bot webhook `_handle_message`, user-token `_upsert_messages`) to `ON CONFLICT (index_elements=[workspace_id, channel_id, slack_ts])`. Index-element-based conflict targets are constraint-name-independent.
- **Files modified:** `backend/src/services/slack_events.py`, `backend/src/services/slack_messages.py`
- **Verification:** User-token poller now ingests successfully (177 messages in live E2E); bot webhook path also unblocked (though it was silently broken before due to exception-swallowing).
- **Committed in:** `55b166e`

**2. [Rule 3 - Blocking] Fixed tzinfo mismatch in _ts_to_datetime helper**
- **Found during:** Task 3 (E2E verification). After fixing #1, user-token poller raised `DataError: cannot mix naive and aware datetimes`.
- **Issue:** `slack_messages.slack_created_at` column is `TIMESTAMP WITHOUT TIME ZONE`, but `_ts_to_datetime` returned a UTC-aware datetime. asyncpg rejects the mismatch.
- **Fix:** Updated `_ts_to_datetime` to return naive UTC (`datetime.utcfromtimestamp` equivalent). Both ingestion paths consume this helper.
- **Files modified:** `backend/src/services/slack_events.py`
- **Verification:** All 177 messages inserted cleanly in live E2E; no DataError.
- **Committed in:** `5649097`

---

**Total deviations:** 2 auto-fixed (2 blocking). Both were pre-existing silent bugs in the shared Slack ingestion path that the user-token poller exposed because — unlike the bot webhook handler which catches and logs all exceptions — the user-token poller surfaces errors cleanly. No Phase 39 code caused these bugs; Phase 39 merely made them visible. Fixing them in-scope was necessary to complete E2E verification.

**Impact on plan:** No scope creep. Both fixes were strictly required to complete Task 3's verification script. They incidentally unblock the bot webhook path for the same failure modes.

## Trade-offs and follow-ups

- **User-token channel polling sidesteps the bot `/invite` requirement** (per Phase 39.1). The auto-join fix on branch `fix/slack-channel-selection` (commit `d96b944`) remains unmerged pending CTO bot-invite permissions. User-token polling is the default path for now; once CTO perms land, merging the auto-join branch restores full bot-webhook channel coverage and can reduce reliance on user-token polling (especially for rate-limited workspaces).
- **Rate-limit behavior at scale**: `conversations.history` is capped at 1 rpm per workspace for non-Marketplace user tokens. At ~8 conversations in live E2E, this was fine. Workspaces with dozens of channels may see poll sweeps take multiple 15-minute cycles. Consider per-cycle conversation budgets if this becomes a pain point.
- **Webhook exception-swallowing**: The bot webhook handler's blanket exception catch masked both upsert bugs for an unknown period. Not a Phase 39 regression to fix, but worth revisiting in a future hardening pass to surface these to Sentry rather than log-and-continue.

## Issues Encountered

None that weren't resolved as deviations above. The E2E verification checklist executed cleanly once the two pre-existing bugs were fixed.

## User Setup Required

None — no external service configuration required beyond what Plan 39-01 already established. Existing users reconnect Slack once to pick up the new user scopes (per the re-auth banner shipped in Plan 39-03).

## Next Phase Readiness

**Phase 39 complete**. The full story ships end-to-end:
- OAuth captures both bot and user tokens (Plan 39-01)
- DM + channel polling via user token (Plan 39-02 + Phase 39.1)
- Settings toggle + re-auth banner + channel picker coexistence (Plan 39-03)
- 15-minute scheduler wired up + onboarding DM consent + E2E verified (Plan 39-04, this plan)

Open items for a future pass (not blockers):
- Merge `fix/slack-channel-selection` branch (auto-join) once CTO bot-invite permissions land
- Surface webhook ingestion exceptions to Sentry instead of swallowing them
- Monitor `conversations.history` 429s per workspace at scale

**No blockers for phase transition.**

## Self-Check: PASSED

Verified:
- `backend/tests/test_sync_scheduler_slack.py` — FOUND (created in `07e2218`)
- `backend/src/services/sync_scheduler.py` — FOUND (modified in `dba5ab6`)
- `apps/web/src/components/onboarding/step-sources.tsx` — FOUND (modified in `35ac75d`)
- `backend/src/services/slack_events.py` — FOUND (modified in `55b166e`, `5649097`)
- `backend/src/services/slack_messages.py` — FOUND (modified in `55b166e`)
- Commit `07e2218` (Task 1 RED) — FOUND in git log
- Commit `dba5ab6` (Task 1 GREEN) — FOUND in git log
- Commit `35ac75d` (Task 2 onboarding) — FOUND in git log
- Commit `55b166e` (constraint-name fix) — FOUND in git log
- Commit `5649097` (tz fix) — FOUND in git log
- Live E2E verification: 177 messages ingested across 8 conversations, user replied `approved`.

---
*Phase: 39-slack-user-token-migration-dm-support*
*Plan: 04*
*Completed: 2026-04-22*
