---
phase: 39-slack-user-token-migration-dm-support
verified: 2026-04-22T22:00:00Z
status: passed
score: 6/6 success criteria verified
re_verification: no
requirements_note: |
  SLACK-USR-01..SLACK-USR-05, SLACK-USR-07 are declared in the four plan
  frontmatters but are NOT present in .planning/REQUIREMENTS.md (which only
  tracks v1.3 requirements: ACT-*, GRAPH-*, EXT-*, LAND-*, ONB-*, PRIV-*,
  RAG-*). Phase 39 was added mid-milestone per 39-CONTEXT.md and carries its
  own ad-hoc requirement IDs used only inside the phase directory. This is
  informational — not a gap.
---

# Phase 39: Slack User Token Migration & DM Support — Verification Report

**Phase Goal (ROADMAP.md):** Add DM and group-DM ingestion to the Slack integration via user-token polling, while keeping the existing bot Events API webhook path for channel messages (Slack's May 2025 rate-limit cap makes user-token polling unviable for channels at scale).

**Effective Goal after Phase 39.1 gap closure:** Ship DM + group DM *and* channel polling via user token (because bot-invite permissions were blocked for channel webhook rollout). Channels run via BOTH the bot webhook path (when available) and the user-token poller; SlackMessage upsert idempotency prevents duplicates.

**Verified:** 2026-04-22
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

Verified against the six Success Criteria enumerated in ROADMAP.md (the authoritative contract for this phase) plus the Phase 39.1 scope extension documented in 39.1-GAP-SUMMARY.md.

### Observable Truths

| # | Truth (Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | Slack OAuth captures & stores a user token alongside the bot token under Vault key `oauth_slack_{ws}_user_access` | VERIFIED | `slack_oauth.py:50` declares `SLACK_USER_SCOPES`; `build_auth_url` passes `user_scope=SLACK_USER_SCOPES` (line 76); `exchange_code` parses `authed_user.access_token` via `_extract_tokens` (lines 83-100) and stores under `token_name(Provider.SLACK, ws, "user_access")` (line 165); `get_user_token` helper at line 290 mirrors `get_bot_token` |
| 2 | 15-minute polling service fetches new DM / group-DM messages via user token; channels stay on bot Events API path (unchanged) | VERIFIED (extended by 39.1) | `slack_messages.py:95` defines `poll_user_messages`; wired into `sync_scheduler.run_polling_fallback` at line 271-292 with per-workspace `async_session()` and exception isolation. 39.1 extended enumeration to `types=im,mpim,public_channel,private_channel` (`USER_CONVERSATION_TYPES` line 74). Bot Events API path in `slack_events.py` remains in place for channels. |
| 3 | Users can opt in to DM ingestion via a Settings toggle (and during onboarding); default OFF with inline privacy note | VERIFIED | `POST /api/slack/dms/toggle` endpoint at `routers/slack.py:264-314`. `SlackDmToggle` component writes via `toggleSlackDms` (`slack-dm-toggle.tsx` line 58). Privacy caption: "DM messages will be indexed for context generation. Only you can see this data." present at `slack-dm-toggle.tsx:107`. Onboarding inline panel `OnboardingSlackDms` at `step-sources.tsx:760` renders inside expanded Slack source card (line 300-301). First-time enable marker `dms_first_enabled_at` written in toggle handler lines 307-311. |
| 4 | Existing-install users without a user token see a re-auth banner prompting reconnect | VERIFIED | `GET /api/slack/status` returns `needs_reauth=true` when `user_access` is missing in Vault (`routers/slack.py:191`). `SlackReauthBanner` renders conditionally in `integration-cards.tsx:259` (`slackExtra?.needs_reauth`). Banner button runs existing `connectSlack()` OAuth flow (`slack-reauth-banner.tsx:30`). 39.1 updated banner copy to cover both channel + DM scopes. |
| 5 | Channel picker UI remains functional (channels still require bot invites) | VERIFIED | `<SlackChannels onSaved={fetchStatuses} />` always renders for connected workspaces in `integration-cards.tsx:265`, regardless of `needs_reauth` or `include_dms` state. Existing channel picker endpoints (`/channels`, `/channels/refresh`, `/channels/select`) untouched. |
| 6 | Short messages (<10 chars) are no longer filtered on either path | VERIFIED | `_should_filter` in `slack_events.py:126-153` retains only bot + system-subtype filters; the length check is gone. Docstring explicitly calls out Phase 39 removal. Poller reuses the same helper (`slack_messages.py` imports `_should_filter` and applies it in `_upsert_messages`). |

**Score:** 6/6 truths verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `backend/src/services/slack_oauth.py` | SLACK_USER_SCOPES + dual-token `exchange_code` + `get_user_token` | VERIFIED | 11,274 bytes; contains `SLACK_USER_SCOPES` (DM+channels per 39.1), `_extract_tokens`, `exchange_code`, `get_user_token`, user vault cleanup in `disconnect` |
| `backend/src/services/slack_events.py` | `_should_filter` without 10-char rule; `_ts_to_datetime` returning naive UTC | VERIFIED | 12,512 bytes; filter at lines 126-153 has no length check. `_ts_to_datetime` at line 385 returns naive UTC (fixed in commit `5649097` during E2E). Upsert path uses `index_elements=["workspace_id","channel_id","slack_ts"]` (line 249, fixed in `55b166e`). |
| `backend/src/routers/slack.py` | `get_status` with needs_reauth + include_dms; `POST /dms/toggle` | VERIFIED | 16,374 bytes; `get_status` returns 5 fields including `needs_reauth` and `include_dms`. `toggle_dms` endpoint handles 400 (not connected), 409 (needs_reauth), 200 success. |
| `backend/src/services/slack_messages.py` | `poll_user_messages` + `_enumerate_dms` + `_fetch_history` + `_upsert_messages` | VERIFIED | 19,079 bytes (≥150 lines required, actual ~560 lines). Declares `BACKFILL_DAYS=7`, `BACKFILL_MESSAGES_PER_CONVERSATION_CAP=100`, `USER_CONVERSATION_TYPES`. Upsert uses same `index_elements` + SET clause as `slack_events._handle_message`. Embedding + graph extraction parity enforced. |
| `backend/src/services/sync_scheduler.py` | Module-level import of `poll_user_messages`; per-cycle loop | VERIFIED | 13,118 bytes; `from src.services.slack_messages import poll_user_messages` at line 25 (module-level). Loop at lines 271-292 iterates connected Slack workspaces with fresh `async_session()` per workspace and try/except `logger.exception`. |
| `backend/tests/test_slack.py` | OAuth + status + toggle + filter tests | VERIFIED | 48,719 bytes; 40 tests. Includes `TestUserTokenOAuth`, `TestDmToggleAndStatus`, `TestMessageFiltering` with `test_short_messages_no_longer_filtered`. |
| `backend/tests/test_slack_messages.py` | Poller behavior tests A–K | VERIFIED | 30,416 bytes; 13 tests across `TestEnumerate`, `TestPolling`, `TestUpsert`. Test K regression guard (channel-agnostic `_upsert_messages`) added in 39.1. |
| `backend/tests/test_sync_scheduler_slack.py` | Scheduler wiring tests patching `sync_scheduler.poll_user_messages` | VERIFIED | 9,452 bytes; 4 tests. All 4 patch `src.services.sync_scheduler.poll_user_messages` (not the origin in `slack_messages`) — confirms the module-level import contract. |
| `apps/web/src/lib/api.ts` | `SlackProviderStatus`, `getSlackStatus`, `toggleSlackDms` | VERIFIED | 24,508 bytes; exports all three symbols. `IntegrationStatusResponse.slack` narrowed to `SlackProviderStatus`. |
| `apps/web/src/app/dashboard/integrations/slack-dm-toggle.tsx` | Toggle component with optimistic update + privacy note | VERIFIED | 3,225 bytes; imports `getSlackStatus`, `toggleSlackDms`; re-reads `include_dms` on mount via useEffect (line 40); privacy caption at line 107. |
| `apps/web/src/app/dashboard/integrations/slack-reauth-banner.tsx` | Amber banner with `connectSlack()` trigger | VERIFIED | 2,125 bytes; imports `AlertTriangle`, calls `connectSlack()` → `window.location.href = authorization_url` (lines 30-33). Copy updated by 39.1 to "Reconnect required for channel + DM ingestion". |
| `apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx` | Conditional render of banner + toggle + channel picker | VERIFIED | 12,086 bytes; imports and renders all three components (lines 36-38, 259-265). Effect at line 139 fetches `getSlackStatus()` keyed on `slack.status`; `fetchStatuses` intentionally omitted from deps per eslint-disable comment (Option B, documented at line 153). |
| `apps/web/src/components/onboarding/step-sources.tsx` | DM consent inline panel `OnboardingSlackDms` | VERIFIED | 26,619 bytes; `ExpandedSource` union includes `'slack'` (line 45); auto-expand branch at lines 92-94; `OnboardingSlackDms` component at line 760 wraps `<SlackDmToggle />`. |
| `apps/web/src/components/ui/switch.tsx` | shadcn Switch primitive | VERIFIED | 1,164 bytes; created via radix-ui namespace pattern (parallel to existing `label.tsx`). |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `slack_oauth.build_auth_url` | Slack authorize URL `user_scope` param | urlencode with `SLACK_USER_SCOPES` | WIRED | Line 76: `"user_scope": SLACK_USER_SCOPES`. Constant contains `im:read,im:history,mpim:read,mpim:history,channels:read,channels:history,groups:read,groups:history,users:read,users:read.email` (lines 50-54). |
| `slack_oauth.exchange_code` | Vault user token + `integration.config.slack_user_id` | `store_token(session, token_name(SLACK, ws, 'user_access'), ...)` + config patch | WIRED | Line 165 stores user token; lines 187-199 merge `slack_user_id` into config without clobbering existing keys. |
| `routers/slack.get_status` | `read_token(session, token_name(SLACK, ws, 'user_access'))` | `needs_reauth = status=='connected' AND user_token is None` | WIRED | Line 191. |
| `slack_messages.poll_user_messages` | `get_user_token` from `slack_oauth` | direct import; Vault `user_access` lookup | WIRED | Line 105: `try: user_token = await get_user_token(...); except SlackOAuthError: return {..., "reason": "needs_reauth"}`. |
| `slack_messages._enumerate_dms` | `users.conversations?types=im,mpim,public_channel,private_channel` | httpx GET with `Authorization: Bearer {user_token}` | WIRED | Line 266. 39.1 expanded scope of enumerated types. |
| `slack_messages._upsert_messages` | `SlackMessage` + embedding queue + graph extractor | `pg_insert.on_conflict_do_update(index_elements=...)` + `queue_embedding_generation` + `extract_and_populate_graph` | WIRED | Lines 480-524. SET clause field list identical to `slack_events._handle_message` (text, user_id, thread_ts, parent_ts, is_thread_reply, raw_data). Drift-guarded at runtime by `inspect.getsource()` assertion in Test F. |
| `slack_messages._upsert_messages` SET clause | `slack_events._handle_message` SET clause | exact field-list match on both sides | WIRED | Both files grep to the identical 6-field set (see 39-02-SUMMARY.md for side-by-side dump). |
| `sync_scheduler.run_polling_fallback` | `slack_messages.poll_user_messages` | one await per connected Slack workspace per cycle; module-level import | WIRED | Line 25 imports at module top; lines 271-292 loop with fresh session and exception isolation. All 4 scheduler tests patch the locally-bound name. |
| `integration-cards.tsx` | `SlackDmToggle` + `SlackReauthBanner` | conditional render based on `slackExtra.needs_reauth` and `slack.status` | WIRED | Lines 259-265: banner iff `slackExtra?.needs_reauth`; toggle iff connected and not needs_reauth; channel picker always when connected. |
| `slack-dm-toggle.tsx` | `POST /api/slack/dms/toggle` | `toggleSlackDms()` in `lib/api.ts` | WIRED | Line 58. Optimistic update with rollback-on-error at lines 55-66. |
| `slack-reauth-banner.tsx` | `connectSlack()` OAuth redirect | button onClick → `window.location.href = authorization_url` | WIRED | Lines 28-33. |
| `integration-cards.tsx` useEffect | `getSlackStatus()` | effect keyed on `slack.status` only; `fetchStatuses` omitted with documented eslint-disable (Option B) | WIRED | Lines 128-154. `fetchStatuses` is a parent prop not wrapped in useCallback — correctly excluded per plan 39-03 PRE-IMPLEMENTATION READ guidance. |
| `step-sources.tsx` Slack card | `SlackDmToggle` | inline `OnboardingSlackDms` wrapper rendered when `expandedSource === 'slack' && slackConnected` | WIRED | Lines 300-301 + 760. |

### Requirements Coverage

| Requirement (phase-local) | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| SLACK-USR-01 | 39-01 | OAuth dual-token capture (bot + user) with DM-only user scopes (later expanded in 39.1 to include channels) | SATISFIED | `SLACK_USER_SCOPES` shipped; `exchange_code` stores both tokens; `get_user_token` helper exists. TestUserTokenOAuth passes. |
| SLACK-USR-02 | 39-02, 39-04 | `poll_user_messages` DM (+ channel per 39.1) polling service wired into 15-minute scheduler | SATISFIED | `poll_user_messages` implemented; scheduler calls it per-workspace; test_sync_scheduler_slack.py passes 4/4. |
| SLACK-USR-03 | 39-03, 39-04 | Settings DM toggle + re-auth banner + onboarding inline consent | SATISFIED | `SlackDmToggle`, `SlackReauthBanner`, `OnboardingSlackDms` all shipped and wired. |
| SLACK-USR-04 | 39-02, 39-04 | SET-clause parity between `slack_events._handle_message` and `slack_messages._upsert_messages` so dual-path ingestion is safe | SATISFIED | Exact 6-field match verified side-by-side; runtime drift-guard via `inspect.getsource` in Test F. |
| SLACK-USR-05 | 39-01, 39-03 | `needs_reauth` signal surfaced through `/api/slack/status` and reflected in UI | SATISFIED | Status endpoint computes the flag; banner renders on truthy value; `connectSlack()` re-auth round-trip observed in live E2E. |
| SLACK-USR-07 | 39-01 | Remove <10 character message filter on all ingestion paths | SATISFIED | `_should_filter` retains only bot + system-subtype filters; filter helper is shared by both webhook and poller paths. Inverted test `test_short_messages_no_longer_filtered` passes. |

**IMPORTANT (informational, not a gap):** SLACK-USR-* requirement IDs are declared only inside phase 39 plan frontmatters and do not appear in `.planning/REQUIREMENTS.md`, which scopes itself to v1.3 requirements (ACT, GRAPH, EXT, LAND, ONB, PRIV, RAG). Per 39-CONTEXT.md, Phase 39 was planned and executed mid-milestone with its own ad-hoc requirement namespace. The verifier was explicitly told to note but not fail on this.

### Anti-Patterns Found

No blocker anti-patterns found in phase-scoped files. Scanned:
- `backend/src/services/slack_messages.py`
- `backend/src/services/slack_oauth.py`
- `backend/src/services/sync_scheduler.py`
- `apps/web/src/app/dashboard/integrations/slack-dm-toggle.tsx`
- `apps/web/src/app/dashboard/integrations/slack-reauth-banner.tsx`

No `TODO`, `FIXME`, `XXX`, `HACK`, `PLACEHOLDER`, empty returns, or console-log-only implementations. `noqa: BLE001` in `slack_messages.py:523` is intentional (graph extraction wrapped in try/except by design, matching `_handle_message`'s best-effort semantics).

Commit `55b166e` and `5649097` (landed during live E2E) fixed two *pre-existing* bot-webhook bugs that the user-token poller surfaced:
- `55b166e` — switched upsert from `ON CONFLICT ON CONSTRAINT uq_slack_msg` (constraint name never existed in the DB) to `ON CONFLICT (index_elements=[...])`. Both `slack_events.py` and `slack_messages.py` now use the stable index-element form. Verified in place.
- `5649097` — made `_ts_to_datetime` return naive UTC to match the `TIMESTAMP WITHOUT TIME ZONE` column type. Verified in place.

Both fixes are incorporated correctly, resolve latent correctness bugs, and are properly scoped (touch only shared Slack ingestion helpers).

### Human Verification Results

Phase 39 already executed its human-verify checkpoint (Plan 39-04 Task 3) against a live Slack workspace:

- **8 of 8 verification steps passed** (re-auth banner, reconnect + scopes, toggle persistence, channel picker regression, end-to-end DM ingestion, short-message retention, onboarding DM consent, dual-mode sanity).
- **177 messages ingested** across 3 DMs, 1 group DM, and 4 channels on the real Region Lab workspace.
- User replied `approved`.

No open human-verification items remain.

### Gaps Summary

None. The phase goal is fully achieved:
- OAuth dual-token capture shipped and stored in Vault under documented key names.
- User-token polling service shipped, wired into the 15-minute scheduler, and exercised against a live workspace (177 messages ingested).
- Settings UI ships the toggle, re-auth banner, and preserves the channel picker.
- Onboarding inline DM consent panel ships with auto-expand-after-OAuth UX.
- Short-message filter removed uniformly across webhook + poller paths.
- Phase 39.1 inline gap closure correctly extended coverage from DM-only to DM + channels when bot-invite permissions became a blocker; treated as scope-additive, not a scope violation.
- Two pre-existing bot-webhook bugs (`55b166e`, `5649097`) were fixed in-scope during E2E because they prevented end-to-end verification; both are proper correctness fixes and are committed.

### Narrative

Phase 39 went beyond its original DM-only scope (via the 39.1 inline gap closure) to deliver full user-token polling coverage for both DMs and channels, which turned out to be the correct long-term architecture given that CTO-level bot-invite permissions were blocked for rollout. The phase also surfaced and fixed two long-standing silent bugs on the shared bot-webhook ingestion path (constraint-name mismatch and tz-aware/naive datetime mismatch), both of which had been swallowed by the webhook's blanket `except Exception` handler for an unknown period.

The SET-clause parity invariant between `slack_events._handle_message` and `slack_messages._upsert_messages` is protected both at code-review time (side-by-side verification documented in 39-02-SUMMARY.md) and at runtime (Test F uses `inspect.getsource()` to assert the required field list is present verbatim), which is the right defense for a dual-path ingestion system where silent SET-clause drift would cause hard-to-detect data corruption.

Test patching for the scheduler wiring correctly targets `src.services.sync_scheduler.poll_user_messages` (the locally-bound module attribute) rather than the origin in `src.services.slack_messages`, matching the contract that Plan 39-04 intentionally documents — this is a subtle mistake the plan preemptively called out.

Phase 39 is complete and ready for merge. The one follow-up worth tracking (not a gap): the `fix/slack-channel-selection` branch (auto-join commit `d96b944`) remains unmerged pending CTO bot-invite permissions; when those land, merging it restores full bot-webhook channel coverage and reduces reliance on user-token polling for rate-limited workspaces.

---

*Verified: 2026-04-22*
*Verifier: Claude (gsd-verifier)*
