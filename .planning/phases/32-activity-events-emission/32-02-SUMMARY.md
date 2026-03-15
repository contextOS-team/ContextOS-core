---
phase: 32-activity-events-emission
plan: 02
subsystem: api
tags: [activity-events, webhooks, oauth, fail-silent, event-emission]

# Dependency graph
requires:
  - phase: 32-activity-events-emission
    plan: 01
    provides: emit_activity() fail-silent helper and DB migration with new event types
provides:
  - ticket_created events from Linear and Jira webhook handlers
  - pr_merged events from GitHub and GitLab webhook handlers
  - meeting_recorded events from Fathom transcript polling
  - page_created events from Notion full sync
  - integration_connected events from all 8 provider routers
  - integration_disconnected events from all 8 provider routers
affects: [32-03, activity-tab-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns: [webhook event emission at handler level, connect/disconnect lifecycle events]

key-files:
  created: []
  modified:
    - backend/src/services/linear_webhook.py
    - backend/src/services/github_webhook.py
    - backend/src/services/gitlab_webhook.py
    - backend/src/services/jira_webhook.py
    - backend/src/services/fathom.py
    - backend/src/services/notion_sync.py
    - backend/src/routers/linear.py
    - backend/src/routers/github.py
    - backend/src/routers/gitlab.py
    - backend/src/routers/jira.py
    - backend/src/routers/notion.py
    - backend/src/routers/slack.py
    - backend/src/routers/fathom.py
    - backend/src/routers/telegram.py

key-decisions:
  - "GitHub/GitLab pr_merged guarded by state == merged check to avoid emitting for closed-but-not-merged PRs"
  - "Notion page_created limited to 5 events per full sync to avoid flooding activity tab"
  - "GitHub/GitLab callback routers extract workspace_id from state parameter for emit_activity since handle_callback encapsulates it"

patterns-established:
  - "Webhook event pattern: emit after successful data processing, before session commit"
  - "Connect/disconnect pattern: emit after service call succeeds, before response returned"

requirements-completed: [ACT-05, ACT-06]

# Metrics
duration: 5min
completed: 2026-03-15
---

# Phase 32 Plan 02: Webhook and Connect/Disconnect Event Emission Summary

**Curated webhook events (ticket_created, pr_merged, meeting_recorded, page_created) from 5 providers plus integration_connected/disconnected lifecycle events from all 8 provider routers**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-15T21:08:44Z
- **Completed:** 2026-03-15T21:14:43Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Wired ticket_created events from Linear and Jira webhook handlers on new issue creation
- Wired pr_merged events from GitHub and GitLab webhook handlers with merged-state guard
- Wired meeting_recorded events from Fathom poll_transcripts on new transcript ingestion
- Wired page_created events from Notion full sync for new pages (capped at 5 per sync)
- Added integration_connected events to all 8 provider OAuth callbacks and connect endpoints
- Added integration_disconnected events to all 8 provider disconnect endpoints
- All emissions use existing sessions and are fail-silent via emit_activity

## Task Commits

Each task was committed atomically:

1. **Task 1: Curated webhook events for 5 providers** - `21c6d0f` (feat)
2. **Task 2: Connect/disconnect events for all 8 provider routers** - `8043210` (feat)

## Files Created/Modified
- `backend/src/services/linear_webhook.py` - ticket_created emission on new issue create
- `backend/src/services/github_webhook.py` - pr_merged emission only when state is "merged"
- `backend/src/services/gitlab_webhook.py` - pr_merged emission only when state is "merged"
- `backend/src/services/jira_webhook.py` - ticket_created emission on issue_created webhook
- `backend/src/services/fathom.py` - meeting_recorded emission on new transcript ingestion
- `backend/src/services/notion_sync.py` - page_created emission for new pages during full sync
- `backend/src/routers/linear.py` - integration_connected/disconnected with actor_id
- `backend/src/routers/github.py` - integration_connected/disconnected with actor_id
- `backend/src/routers/gitlab.py` - integration_connected/disconnected with actor_id
- `backend/src/routers/jira.py` - integration_connected/disconnected with actor_id
- `backend/src/routers/notion.py` - integration_connected/disconnected with actor_id
- `backend/src/routers/slack.py` - integration_connected/disconnected with actor_id
- `backend/src/routers/fathom.py` - integration_connected/disconnected with actor_id
- `backend/src/routers/telegram.py` - integration_connected/disconnected with actor_id

## Decisions Made
- GitHub and GitLab pr_merged events are guarded by `state == "merged"` check to prevent emitting for closed-but-not-merged PRs
- Notion page_created events are limited to 5 per full sync to avoid flooding the activity tab during initial large syncs
- GitHub and GitLab OAuth callback routers extract workspace_id from the state parameter for emit_activity, since handle_callback encapsulates workspace resolution internally
- Provider names are consistent lowercase strings across all files: "linear", "github", "gitlab", "jira", "notion", "slack", "fathom", "telegram"

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All webhook and lifecycle events are now wired, completing the event emission layer
- Plan 03 (frontend enhancements) can now display these events with rich metadata
- The activity tab will show ticket_created, pr_merged, meeting_recorded, page_created events as real-time news items
- Connect/disconnect events provide integration lifecycle visibility

---
*Phase: 32-activity-events-emission*
*Completed: 2026-03-15*
