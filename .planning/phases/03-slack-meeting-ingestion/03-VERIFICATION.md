---
phase: 03-slack-meeting-ingestion
verified: 2026-02-25T00:00:00Z
status: gaps_found
score: 19/20 must-haves verified
re_verification: false
gaps:
  - truth: "All tests pass covering Fathom ingestion"
    status: partial
    reason: "test_connect_validates_api_key asserts '/calls' in the validation URL, but the service was fixed in 03-03 to use '/meetings'. The implementation is correct; the test was not updated to match."
    artifacts:
      - path: "backend/tests/test_fathom.py"
        issue: "Line 221: asserts 'calls' in api_call_made[0] but service now calls /meetings endpoint (correct endpoint per 03-03 bugfix)"
    missing:
      - "Update test_connect_validates_api_key to assert 'meetings' in api_call_made[0] instead of 'calls'"
human_verification:
  - test: "Visual verification of integration setup page"
    expected: "3 cards (Linear, Slack, Fathom) visible with correct status badges, connect/disconnect actions functional, Slack channel picker expands when Slack is connected, Fathom API key form appears before connecting"
    why_human: "03-03 PLAN has a human checkpoint (Task 3) for visual approval. SUMMARY says HITL passed but no external verification record exists in the file system."
---

# Phase 03: Slack Meeting Ingestion Verification Report

**Phase Goal:** Slack OAuth + Events API integration, Fathom transcript ingestion, channel selection UI, and integration management page
**Verified:** 2026-02-25
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can connect Slack workspace via OAuth and tokens are stored encrypted in Vault | VERIFIED | `slack_oauth.py:149` calls `store_token`; `slack_oauth.py:273-277` calls `read_token`; Vault functions imported from `src.services.vault` |
| 2 | Real-time Slack messages arrive via Events API and are stored in the database | VERIFIED | `slack_events.py` `process_event` dispatches to `_handle_message` which upserts `SlackMessage` via `pg_insert().on_conflict_do_update()` (line 246); `/api/slack/events` endpoint registered and routes confirmed |
| 3 | Bot messages and messages under 10 characters are filtered out during ingestion | VERIFIED | `_should_filter()` at line 124: checks `bot_id` (line 139) and `len(text) < 10` (line 149) |
| 4 | Thread replies are stored with parent_ts relationship intact | VERIFIED | `slack_events.py:214-241`: `thread_ts != slack_ts` sets `is_thread_reply=True, parent_ts=thread_ts`; stored in upsert values |
| 5 | Slack event signatures are verified via signing secret — tampered events are rejected | VERIFIED | `verify_signature()` in `slack_events.py:49-85`: HMAC-SHA256 `v0:` prefix, `hmac.compare_digest`, 5-minute replay protection; called in router before processing |
| 6 | Message edits overwrite stored text; message deletes soft-delete the record | VERIFIED | `_handle_message_edit` (line 278) overwrites `text`; `_handle_message_delete` (line 332) sets `deleted_at = datetime.utcnow()` |
| 7 | User can select which Slack channels to monitor from their connected workspace | VERIFIED | `slack_channels.py` implements `list_channels`, `save_channel_selection`, `get_cached_channels`; endpoints `/api/slack/channels`, `/channels/refresh`, `/channels/select` all registered |
| 8 | Only messages from selected channels are ingested (unmonitored channels are skipped) | VERIFIED | `slack_events.py:155-210`: `_is_channel_monitored` checks `integration.config["selected_channels"]`; early return at line 210 if not monitored |
| 9 | Channel list shows public channels and private channels where bot has been invited | VERIFIED | `slack_channels.py:67`: `types=public_channel,private_channel` passed to `conversations.list` |
| 10 | Manual Refresh channels button fetches latest channel list from Slack API | VERIFIED | `POST /api/slack/channels/refresh` calls `fetch_channels()` which hits Slack API; `slack-channels.tsx:46-59` calls `refreshSlackChannels()` |
| 11 | Meeting transcripts from Fathom are ingested with participant info, timestamps, and full text | VERIFIED | `fathom.py:260-395`: fetches `/meetings`, extracts `title`, `participants`, `meeting_date`, `duration_minutes`; stores `MeetingTranscript` records |
| 12 | Transcripts are stored as speaker-segmented turns (speaker name, timestamp, text per segment) | VERIFIED | `fathom.py:379-393`: iterates `segments`, creates `MeetingSegment` records with `speaker_name`, `start_time_seconds`, `end_time_seconds`, `text` |
| 13 | Fathom API key is stored in Vault (not plaintext) | VERIFIED | `fathom.py:75,112`: calls `store_token(session, f"fathom_{workspace_id}_api_key", api_key)` via Vault pattern |
| 14 | Integration setup page shows cards for Linear, Slack, and Fathom | VERIFIED | `page.tsx:140-178`: renders 3 `IntegrationCard` components for Linear, Slack, Fathom |
| 15 | Each card shows service name, status badge (connected/disconnected), and connect/disconnect button | VERIFIED | `integration-card.tsx:30-55`: `StatusBadge` with green/gray/red pills; connect/disconnect buttons at lines 153-183 |
| 16 | Connected cards show workspace name and Connected X ago timestamp | VERIFIED | `integration-card.tsx:137-146`: renders `externalName` and `formatRelativeTime(connectedAt)` when `status === 'connected'` |
| 17 | Disconnect requires confirmation dialog before proceeding | VERIFIED | `integration-card.tsx:105-108`: `window.confirm()` with message "This will stop syncing data. Existing data is kept." |
| 18 | Slack card has expandable channel selection section after connecting | VERIFIED | `page.tsx:161-163`: `<SlackChannels />` passed as `children`; `integration-card.tsx:162-170`: "Settings" toggle button shows/hides children when connected |
| 19 | Channel selection shows flat list with checkboxes and search/filter input | VERIFIED | `slack-channels.tsx:136-204`: search Input, checkbox labels with `#`/lock icons, member count, "Select all" row |
| 20 | Fathom card has API key input form for connecting | VERIFIED | `fathom-connect.tsx:42-83`: form with password Input, "Find your API key in Fathom Settings" help text, Connect button calling `connectFathom()` |

**Score:** 19/20 truths verified (1 partial — test suite has one stale test)

---

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|--------------|--------|---------|
| `backend/src/services/slack_oauth.py` | 100 | 279 | VERIFIED | Full OAuth V2 lifecycle: build_auth_url, exchange_code, disconnect, get_bot_token |
| `backend/src/services/slack_events.py` | 80 | 384 | VERIFIED | Full event processing: verify_signature, process_event, filter, thread, edit, delete |
| `backend/src/routers/slack.py` | 80 | 335 | VERIFIED | 8 routes registered; OAuth + Events + channel management |
| `backend/src/models/slack.py` | 20 | 52 | VERIFIED | SlackMessage maps to `public.slack_messages`, UniqueConstraint on (workspace_id, channel_id, slack_ts) |
| `backend/tests/test_slack.py` | 150 | 833 | VERIFIED | 26 tests; all pass |
| `backend/src/services/slack_channels.py` | 60 | 242 | VERIFIED | list_channels (paginated), save_channel_selection, get_cached_channels, is_channel_monitored |
| `backend/src/services/fathom.py` | 100 | 430 | VERIFIED | connect, disconnect, poll_transcripts, get_fathom_status; Vault key storage |
| `backend/src/models/meeting.py` | 40 | 83 | VERIFIED | MeetingTranscript and MeetingSegment SQLModel table mappings |
| `backend/tests/test_slack_channels.py` | 60 | 487 | VERIFIED | 13 tests; all pass |
| `backend/tests/test_fathom.py` | 80 | 790 | PARTIAL | 19 tests; 18 pass; 1 fails (stale test asserts `/calls` URL but service uses `/meetings`) |
| `apps/web/src/app/dashboard/integrations/page.tsx` | 40 | 182 | VERIFIED | Client component; fetches status, renders 3 IntegrationCard instances |
| `apps/web/src/app/dashboard/integrations/integration-card.tsx` | 60 | 200 | VERIFIED | Status badge, connect/disconnect, confirmation dialog, expandable section |
| `apps/web/src/app/dashboard/integrations/slack-channels.tsx` | 80 | 221 | VERIFIED | Checkboxes, search, refresh, member count, select-all, save selection |
| `apps/web/src/app/dashboard/integrations/fathom-connect.tsx` | 40 | 84 | VERIFIED | Password input form, error state, calls connectFathom on submit |
| `apps/web/src/lib/api.ts` | 30 | 146 | VERIFIED | apiFetch helper + 10 typed integration helpers |
| `backend/src/routers/integrations.py` | 30 | 83 | VERIFIED | GET /api/integrations/status returns combined status for all 3 providers |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `slack/routers/slack.py` | `services/slack_oauth.py` | `build_auth_url`, `exchange_code`, `disconnect` imported and called | WIRED | Lines 31-38: direct imports; called at lines 56, 101, 126 |
| `routers/slack.py` | `services/slack_events.py` | `process_event`, `verify_signature` imported; background task calls `process_event` | WIRED | Line 30: imports; line 329: `await process_event(...)` in `_process_event_background` |
| `services/slack_events.py` | `models/slack.py` | `SlackMessage` imported; used in upsert at line 246, queries at 264-265, 300-302, 349-351 | WIRED | Line 30 import confirmed; 4 usage sites |
| `services/slack_oauth.py` | `services/vault.py` | `store_token`, `read_token`, `delete_token`, `token_name` imported and called | WIRED | Line 25 imports; called at 148-149 (store), 274 (read), 238 (delete) |
| `routers/slack.py` | `services/slack_channels.py` | `get_cached_channels`, `list_channels as fetch_channels`, `save_channel_selection` imported | WIRED | Lines 25-29: imports; called at 171, 187, 219 |
| `services/slack_channels.py` | Slack Web API `conversations.list` | `httpx` call to `{SLACK_API_BASE}/conversations.list` | WIRED | Line 67 confirmed |
| `routers/fathom.py` | `services/fathom.py` | `connect_fathom`, `disconnect_fathom`, `poll_transcripts` imported and called | WIRED | Lines 19-22 imports; called at 51, 70, 114 |
| `services/fathom.py` | `models/meeting.py` | `MeetingTranscript`, `MeetingSegment` imported; records created at lines 365, 381 | WIRED | Line 26 import; 2 creation sites + 1 query site |
| `apps/web/integrations/page.tsx` | `backend/routers/integrations.py` | `getIntegrationStatus()` fetches `/api/integrations/status` on mount | WIRED | `api.ts:65-66` defines helper; `page.tsx:27` calls `getIntegrationStatus()` in useEffect |
| `apps/web/integrations/integration-card.tsx` | Linear connect/disconnect | Handlers from `page.tsx` passed as props; `api.ts` calls `/api/linear/connect` and `/api/linear/disconnect` | WIRED | `api.ts:73-79`; `page.tsx:44-58` passes handlers to IntegrationCard |
| `apps/web/integrations/slack-channels.tsx` | `backend/routers/slack.py` | `getSlackChannels`, `refreshSlackChannels`, `saveSlackChannelSelection` call `/api/slack/channels*` | WIRED | `api.ts:105-118`; `slack-channels.tsx:33,50,66` call helpers |
| `apps/web/integrations/fathom-connect.tsx` | `backend/routers/fathom.py` | `connectFathom(apiKey)` calls POST `/api/fathom/connect` | WIRED | `api.ts:134`; `fathom-connect.tsx:31` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SLCK-01 | 03-01 | User can connect Slack workspace via OAuth2 V2 with bot token scopes | SATISFIED | `slack_oauth.py`: full OAuth V2 flow with Vault-encrypted token storage |
| SLCK-02 | 03-01 | System ingests real-time Slack messages via Events API | SATISFIED | `slack_events.py` + `/api/slack/events` endpoint handles event_callback type with HMAC verification |
| SLCK-03 | 03-02 | User can select which Slack channels to monitor | SATISFIED | `slack_channels.py` + channel endpoints + `slack-channels.tsx` UI |
| SLCK-04 | 03-01 | Bot messages and messages shorter than 10 chars filtered out | SATISFIED | `_should_filter()` checks `bot_id` and `len(text) < 10` |
| SLCK-05 | 03-01 | Thread replies stored with thread_ts relationship | SATISFIED | `_handle_message()` sets `parent_ts`, `is_thread_reply` based on `thread_ts` |
| SLCK-06 | 03-01 | Slack event signature verification using signing secret | SATISFIED | `verify_signature()` with HMAC-SHA256 and 5-minute replay protection |
| MEET-01 | 03-02 | System ingests meeting transcripts from Fathom API | SATISFIED | `fathom.py` `poll_transcripts()` fetches `/meetings`, stores `MeetingTranscript` + `MeetingSegment` records |
| DASH-04 | 03-03 | Integration setup page — connect/disconnect Linear, Slack, Fathom with status display | SATISFIED | `/dashboard/integrations` page with 3 cards; status from `/api/integrations/status`; all 3 integrations functional |

**All 8 phase requirements are satisfied.** No orphaned requirements found.

Note: REQUIREMENTS.md Traceability section lists all Phase 3 requirements with status "Pending" — this is a documentation inconsistency (statuses not updated after completion), not a code gap.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/test_fathom.py` | 221 | Stale assertion: `assert "calls" in api_call_made[0]` — service now calls `/meetings` endpoint | WARNING | Causes 1 test failure; implementation is correct, test is wrong |
| `backend/src/services/slack_oauth.py` | 199, 234 | `datetime.utcnow()` deprecated in Python 3.12+ | INFO | DeprecationWarning in test output; not blocking, no runtime failure |
| `backend/src/services/fathom.py` | 112, 422 | `datetime.utcnow()` deprecated in Python 3.12+ | INFO | DeprecationWarning in test output; not blocking |
| `apps/web/integrations/page.tsx` | 173-175 | `onConnect={() => { /* Connect handled by FathomConnect form */ }}` comment in arrow function | INFO | No-op is intentional; Fathom connect is handled by `connectForm` prop pattern, not `onConnect` |

No blocker anti-patterns. The stale test is the only actionable gap.

---

### Human Verification Required

#### 1. Visual Verification of Integration Setup Page

**Test:** Start backend (`uvicorn`) and frontend (`pnpm dev`). Visit `http://localhost:3000/dashboard/integrations`.
**Expected:** 3 integration cards (Linear, Slack, Fathom) visible with correct service names and icons. Disconnected services show gray "Not connected" badge and a Connect button. Connected services show green "Connected" badge, workspace name, and relative connected time. Clicking Disconnect shows a browser confirm dialog with the message "This will stop syncing data. Existing data is kept." Slack card's Settings button reveals the SlackChannels picker when connected. Fathom card shows the API key form before connecting.
**Why human:** The 03-03 PLAN has an explicit `checkpoint:human-verify` blocking gate (Task 3). The SUMMARY states HITL was completed, but no in-filesystem artifact records the approval. The page requires a running backend to test the API calls. TypeScript compilation has not been run as part of this automated check.

---

### Gaps Summary

One gap identified: a single stale test in `backend/tests/test_fathom.py`.

During the 03-03 phase, a bugfix corrected the Fathom validation endpoint from `/calls` to `/meetings`. The test `test_connect_validates_api_key` (line 221) was not updated to reflect this change: it asserts `"calls" in api_call_made[0]` but the service now calls `https://api.fathom.video/v1/meetings`. The fix is a one-line change to the test assertion.

The 2 other failing tests (`test_linear_oauth.py::TestTokenRefresh`) are pre-existing Phase 02 failures unrelated to Phase 03 scope.

All functional requirements (SLCK-01 through SLCK-06, MEET-01, DASH-04) are implemented and wired. The integration page is accessible at `/dashboard/integrations` with all three services. Channel selection, Fathom transcript ingestion, and HMAC signature verification are all substantive implementations with no stub patterns detected.

---

_Verified: 2026-02-25_
_Verifier: Claude (gsd-verifier)_
