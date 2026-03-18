---
phase: 32-activity-events-emission
verified: 2026-03-16T00:00:00Z
status: gaps_found
score: 11/12 must-haves verified
re_verification: false
gaps:
  - truth: "Failed syncs produce a sync_completed event with metadata.error=true"
    status: partial
    reason: "GitHub and GitLab sync services use per-resource loops without a top-level except block. They always emit sync_completed after the loop with only items_count and duration_ms — no error=true even when individual repos/projects failed. Linear, Jira, and Notion correctly emit sync_completed with error=true in their except blocks."
    artifacts:
      - path: "backend/src/services/github_sync.py"
        issue: "sync_completed at line 159 never includes error=true. Per-repo errors are silently aggregated into results dict but not surfaced in the activity event."
      - path: "backend/src/services/gitlab_sync.py"
        issue: "sync_completed at line 160 never includes error=true. Same per-project loop pattern as GitHub."
    missing:
      - "Wrap the per-resource loop body in github_sync.py/sync_repos() in a top-level try/except that emits sync_completed with error=True when the entire sync fails catastrophically, or add error=True to the final emit when any per-repo error was recorded in results"
      - "Same fix for gitlab_sync.py/sync_projects()"
human_verification:
  - test: "Connect a Linear workspace and trigger a full sync, then load /dashboard/activity"
    expected: "Activity tab shows sync_started followed by sync_completed events for linear, with INTEGRATION_COLORS purple (#5E6AD2) applied to the icon and per-integration last sync time in the SyncStatus header"
    why_human: "Real-time icon color rendering and SyncStatus population require a live session with an active Linear integration"
  - test: "Create a new ticket in Linear or Jira and observe the activity tab"
    expected: "A ticket_created event appears in real-time with the TicketPlus icon and description 'New ticket: CON-52 Auth redesign' (or equivalent)"
    why_human: "Webhook delivery and real-time Supabase subscription behavior require a live integration"
  - test: "Merge a GitHub or GitLab PR and observe the activity tab"
    expected: "A pr_merged event appears with GitMerge icon and description 'PR merged: owner/repo#42 PR title'; a close-without-merge should NOT generate an event"
    why_human: "Requires a live GitHub/GitLab integration and PR to merge"
  - test: "Disconnect and reconnect an integration"
    expected: "integration_disconnected event appears, then integration_connected event; icons show brand color"
    why_human: "OAuth callback flow and session handling require browser interaction"
---

# Phase 32: Activity Events Emission — Verification Report

**Phase Goal:** Emit activity events from all integration sync services, webhook handlers, and context generation — powering the Activity tab with real-time visibility into what ContextOS is doing.
**Verified:** 2026-03-16T00:00:00Z
**Status:** gaps_found (1 partial gap in error-path emission for GitHub and GitLab syncs; 4 items need human/browser verification)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Plan 01)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After any full sync completes, a sync_started and sync_completed event exist in activity_events for that integration | VERIFIED | All 5 sync providers (Linear, GitHub, GitLab, Jira, Notion) call emit_activity with sync_started at the top of their main sync function and sync_completed at the end. Confirmed in linear_sync.py:165/206, github_sync.py:95/159, gitlab_sync.py:91/160, jira_sync.py:138/219, notion_sync.py:188/259. |
| 2 | After a context page is generated, a context_generated event exists in activity_events with ticket info and source count | VERIFIED | synthesis.py:681 emits context_generated with ticket_id, title, source_count, token_count before session.commit(). Both generate_context_page() and generate_context_page_stream() are wired (lines 681 and 907). |
| 3 | Failed syncs produce a sync_completed event with metadata.error=true | PARTIAL | Linear (line 235), Jira (line 228), and Notion (line 275) correctly emit sync_completed with error=True in their except blocks. GitHub and GitLab use per-resource loops — they emit one final sync_completed after the loop without error=True, even when individual repos/projects errored. If the overall sync function raises an uncaught exception, no error event is emitted at all for these two. |
| 4 | Failed context generation produces a context_generated event with metadata.error=true | VERIFIED | synthesis.py:701-706 except block emits context_generated with error=True and truncated error_message for both sync and stream generation. |
| 5 | Event emission never breaks the parent sync or context generation on failure | VERIFIED | emit_activity in sync_adapter.py:136-163 wraps the INSERT in try/except and calls logger.warning without re-raising. No session.commit() inside emit_activity. All callers pass existing sessions. |

### Observable Truths (Plan 02)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | When a Linear or Jira ticket is created via webhook, a ticket_created event appears in activity_events | VERIFIED | linear_webhook.py:220 emits ticket_created after issue upsert. jira_webhook.py:130 emits ticket_created in _handle_issue_created. Both use existing session and are fail-silent via emit_activity. |
| 7 | When a GitHub or GitLab PR is merged via webhook, a pr_merged event appears in activity_events | VERIFIED | github_webhook.py:244 guards with `if state == "merged"` before emitting pr_merged. gitlab_webhook.py:247 guards with `if state == "merged"`. Closed-but-not-merged PRs do not produce events. |
| 8 | When Fathom polls a new transcript, a meeting_recorded event appears in activity_events | VERIFIED | fathom.py:405 emits meeting_recorded inside poll_transcripts() after each new transcript is ingested, with title, duration_minutes, and participants_count metadata. |
| 9 | When a Notion page is created during sync, a page_created event appears in activity_events | VERIFIED | notion_sync.py:227 emits page_created per new page during full sync. Limited to 5 events per sync run (new_page_events_emitted < 5 guard at line 226). Only fires for notion_ids absent from existing_notion_ids set. |
| 10 | When a user connects an integration via OAuth callback, an integration_connected event appears | VERIFIED | All 8 provider routers emit integration_connected: linear.py:118, github.py:95, gitlab.py:92, jira.py:115, notion.py:108, slack.py:108, fathom.py:56, telegram.py:52. All include actor_id and metadata.integration. |
| 11 | When a user disconnects an integration, an integration_disconnected event appears | VERIFIED | All 8 provider routers emit integration_disconnected in disconnect endpoints: linear.py:160, github.py:134, gitlab.py:130, jira.py:157, notion.py:137, slack.py:137, fathom.py:80, telegram.py:76. |
| 12 | Event emission never breaks webhook processing or OAuth flows | VERIFIED | All webhook and router emit calls use emit_activity which is fail-silent. No router creates a new session; all pass the existing session dependency. |

### Observable Truths (Plan 03)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 13 | The Activity tab renders events for all 10 event types with appropriate icons and descriptions | VERIFIED | types.ts EventType union has all 10 types (lines 15-26). EVENT_ICONS has all 10 entries including TicketPlus, GitMerge, Mic, FilePlus for new types. formatters.ts handles all 10 in formatEventDescription(). |
| 14 | Integration-related events show the provider's brand color on the icon | VERIFIED | activity-timeline.tsx:289-302: extracts integration from metadata, looks up INTEGRATION_COLORS, applies inline style={{ color: brandColor }} when not an error event. |
| 15 | Failed events (metadata.error=true) show a red icon and 'failed' badge | VERIFIED | activity-timeline.tsx:290 sets isError = event.metadata.error === true. Line 301: `text-destructive` class applied to icon. Lines 320-326: red "failed" badge rendered after description. Error message shown at lines 327+. |
| 16 | The top of the Activity page shows per-integration last sync time | VERIFIED | sync-status.tsx exists. page.tsx:36-57 queries activity_events for sync_completed events, groups by integration, passes syncStatusList to SyncStatus component rendered above ActivityTimeline. |
| 17 | context_generated events show ticket ID and source count in the description | VERIFIED | formatters.ts line 20: returns `Context generated for ${meta.ticket_id} · ${meta.source_count ?? '?'} sources` when ticket_id is present. |

**Score:** 11/12 must-have truths verified (Truth #3 is partial for GitHub and GitLab)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/00031_activity_event_types.sql` | Expanded CHECK constraint with 4 new event types including ticket_created | VERIFIED | 30 lines. Drops old constraint via pg_constraint lookup. Adds new CHECK with all 10 event types: sync_started, sync_completed, context_generated, integration_connected, integration_disconnected, user_signed_up, ticket_created, pr_merged, meeting_recorded, page_created. |
| `backend/src/services/sync_adapter.py` | emit_activity() fail-silent helper function | VERIFIED | Lines 136-163. Async function, raw SQL INSERT with ::jsonb cast, try/except wraps the entire INSERT, logger.warning on failure, no session.commit() call inside. |
| `backend/src/services/linear_webhook.py` | ticket_created emission on issue create | VERIFIED | Line 30 imports emit_activity; line 220 emits ticket_created with integration, ticket_id, title metadata. |
| `backend/src/services/github_webhook.py` | pr_merged emission on PR merge | VERIFIED | Line 38 imports emit_activity; line 244 guards with state == "merged"; line 245 emits pr_merged with integration, pr_number, title, repo metadata. |
| `backend/src/routers/linear.py` | integration_connected and integration_disconnected events | VERIFIED | Line 30 imports emit_activity; line 118 emits integration_connected in callback; line 160 emits integration_disconnected in disconnect endpoint. |
| `apps/web/src/app/dashboard/activity/types.ts` | EventType union with 10 types, EVENT_ICONS map, INTEGRATION_COLORS map | VERIFIED | EventType has 10 union members. EVENT_ICONS record covers all 10. INTEGRATION_COLORS maps 8 providers: linear, github, gitlab, jira, notion, slack, fathom, telegram with hex values. |
| `apps/web/src/app/dashboard/activity/formatters.ts` | Formatters for all 10 event types including error variants | VERIFIED | All 10 cases handled in formatEventDescription(). context_generated shows ticket_id and source_count. sync_completed shows error variant. getMetadataChip handles new types and error_message truncation. |
| `apps/web/src/app/dashboard/activity/activity-timeline.tsx` | EventRow with brand colors and error states | VERIFIED | INTEGRATION_COLORS imported at line 9. EventRow applies brandColor via inline style, text-destructive for errors, "failed" badge, truncated error_message display. |
| `apps/web/src/app/dashboard/activity/sync-status.tsx` | Integration sync status display component with "Last synced" | VERIFIED | Created. Accepts syncStatuses prop. Returns null for empty array. Renders colored dot + capitalized integration name + "Last synced {relative time}" for each integration. Uses INTEGRATION_COLORS and formatTimelineTimestamp. |
| `apps/web/src/app/dashboard/activity/page.tsx` | SyncStatus import and sync_completed query | VERIFIED | Line 3 imports SyncStatus. Lines 36-57 query activity_events for sync_completed, reduce to latest per integration, render SyncStatus component above ActivityTimeline. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/src/services/linear_sync.py` | `backend/src/services/sync_adapter.py` | `from src.services.sync_adapter import emit_activity` | WIRED | Line 43 imports; lines 165, 206, 235 call emit_activity. |
| `backend/src/services/synthesis.py` | `backend/src/services/sync_adapter.py` | `from src.services.sync_adapter import emit_activity` | WIRED | Line 24 imports; lines 681, 703, 907, 929 call emit_activity. |
| `backend/src/services/linear_webhook.py` | `backend/src/services/sync_adapter.py` | `from src.services.sync_adapter import emit_activity` | WIRED | Line 30 imports; line 220 calls emit_activity. |
| `backend/src/routers/linear.py` | `backend/src/services/sync_adapter.py` | `from src.services.sync_adapter import emit_activity` | WIRED | Line 30 imports; lines 118 and 160 call emit_activity. |
| `apps/web/src/app/dashboard/activity/activity-timeline.tsx` | `apps/web/src/app/dashboard/activity/types.ts` | `INTEGRATION_COLORS` import and usage | WIRED | Line 9 imports INTEGRATION_COLORS; line 289 uses it to look up brand color per event. |
| `apps/web/src/app/dashboard/activity/page.tsx` | `apps/web/src/app/dashboard/activity/sync-status.tsx` | `import SyncStatus` | WIRED | Line 3 imports SyncStatus; line 57 renders SyncStatus with syncStatusList prop. |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| ACT-05 | 32-01, 32-02 | All integration sync services emit events to activity_events on sync completion | SATISFIED (partial gap) | 5 sync providers wired for sync_started/sync_completed. Slack and Telegram skipped (no batch sync functions). Error path complete for Linear, Jira, Notion; partial for GitHub and GitLab (no top-level error emit). |
| ACT-06 | 32-02 | Integration connect/disconnect actions emit activity events | SATISFIED | All 8 provider routers emit integration_connected and integration_disconnected with actor_id. |
| ACT-07 | 32-01 | Context page generation (start, complete, error) emits activity events | SATISFIED | synthesis.py emits context_generated on success (with ticket_id, source_count) and on error (with error=True). Note: plan explicitly decided not to emit a "started" event — only completion. |
| ACT-08 | 32-03 | Activity tab shows events in real-time via existing Supabase Realtime subscription | SATISFIED | Frontend expanded with 10 event types, brand colors, error states, and SyncStatus header. Realtime subscription infrastructure was pre-existing and untouched. |

**Note on orphaned requirements:** REQUIREMENTS.md maps only ACT-05 through ACT-08 to Phase 32. All four are claimed across the three plans. No orphaned requirements detected.

---

## Git Commit Verification

All 6 task commits verified present in git history:

| Commit | Plan | Description |
|--------|------|-------------|
| `f090cc4` | 32-01 Task 1 | feat: add emit_activity() helper and expand event type CHECK constraint |
| `7030c83` | 32-01 Task 2 | feat: wire emit_activity into 5 sync providers and context generation |
| `21c6d0f` | 32-02 Task 1 | feat: wire curated webhook events for 5 providers |
| `8043210` | 32-02 Task 2 | feat: wire connect/disconnect events for all 8 provider routers |
| `51d552f` | 32-03 Task 1 | feat: expand activity types, icons, formatters, and brand colors |
| `88e0068` | 32-03 Task 2 | feat: add brand-colored icons, error states, and sync status display |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/services/fathom.py` | 341, 352 | Bare `pass` in except blocks | Info | Both are inside date/duration parsing helpers — they silently continue when transcript timestamps or durations can't be parsed. This is intentional defensive parsing, not a stub. No impact on meeting_recorded emission. |

No TODO/FIXME/PLACEHOLDER comments, no stub return patterns, no empty handlers found in any phase-modified files.

---

## Human Verification Required

### 1. Brand-Colored Icons in Activity Feed

**Test:** Connect a Linear workspace, trigger a full sync, and load `/dashboard/activity`
**Expected:** Activity tab shows sync_started followed by sync_completed for Linear; icon is colored with Linear's brand purple (#5E6AD2) via inline style; SyncStatus header shows "Linear — Last synced X minutes ago"
**Why human:** Icon color rendering and SyncStatus population require live events in activity_events; cannot verify dynamic inline styles without a browser session

### 2. Ticket Created Real-Time Event

**Test:** Create a new ticket in a connected Linear or Jira workspace and observe the Activity tab
**Expected:** A ticket_created event appears in real-time with the TicketPlus icon and description "New ticket: CON-52 Auth redesign" (or matching identifier and title)
**Why human:** Webhook delivery and Supabase Realtime subscription require a live integration and active browser session

### 3. PR Merged Event (GitHub/GitLab)

**Test:** Merge a pull request in a connected GitHub or GitLab repository and observe the Activity tab; also close (without merging) a different PR
**Expected:** pr_merged event appears for the merged PR with GitMerge icon; the closed-without-merge PR does NOT produce any event
**Why human:** Requires live GitHub/GitLab webhook delivery; the state == "merged" guard can only be confirmed with real webhook payloads

### 4. Integration Connect/Disconnect Lifecycle

**Test:** Disconnect a connected integration (e.g., GitHub) and then reconnect via OAuth
**Expected:** integration_disconnected event appears with GitHub's muted gray (#8b949e) icon and metadata.integration = "github"; then integration_connected event appears after OAuth callback
**Why human:** OAuth callback flow and session handling require browser interaction; actor_id presence on events requires verification against the logged-in user's UUID

---

## Gaps Summary

**One functional gap identified:** Truth #3 (failed syncs produce sync_completed with metadata.error=true) is only partially satisfied. Linear, Jira, and Notion correctly emit sync_completed with error=True in their except blocks. GitHub (`sync_repos()`) and GitLab (`sync_projects()`) use per-resource loops that catch individual repo/project errors silently — the final sync_completed event after the loop never includes error=True. If the entire GitHub or GitLab sync fails catastrophically (e.g., API authentication failure before the loop runs), no sync_completed event is emitted at all.

**Root cause:** GitHub and GitLab sync functions were designed with partial-success semantics (each repo/project is independent), so a top-level try/except was not added. The plan's error pattern assumes a single-shot sync that either succeeds or fails wholesale, which matches Linear, Jira, and Notion but not GitHub/GitLab.

**Fix scope:** Small — add a top-level try/except around the `async with SyncRunLogger` block in `sync_repos()` and `sync_projects()`, emitting sync_completed with error=True if an exception escapes the per-resource loop. Alternatively, check the `results` dict after the loop and include `"error": True` if any repo/project has status "error" or "timeout".

All other must-haves are fully verified. The 17 observable truths beyond Truth #3 all pass at the artifact existence, substantive content, and wiring levels. All six git commits are present. No blocking anti-patterns detected.

---

_Verified: 2026-03-16T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
