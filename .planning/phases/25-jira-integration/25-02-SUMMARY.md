---
phase: 25-jira-integration
plan: 02
subsystem: api
tags: [jira, oauth, atlassian, rest-api, webhook, hmac, sync]

requires:
  - phase: 25-jira-integration/01
    provides: Database schema (jira_issues, jira_comments), JiraIssue/JiraComment models, Provider.JIRA enum, config settings
provides:
  - Jira OAuth 2.0 3LO flow with cloudId resolution via accessible-resources endpoint
  - Jira issue sync via modern /search/jql endpoint with nextPageToken pagination
  - Jira webhook handler with HMAC-SHA256 verification for issue/comment CRUD
  - FastAPI router at /api/jira/* with full endpoint suite
  - Integration status endpoint includes Jira provider
affects: [25-jira-integration/03, frontend-jira-settings]

tech-stack:
  added: []
  patterns: [atlassian-oauth-3lo, jira-search-jql-pagination, adf-text-extraction]

key-files:
  created:
    - backend/src/services/jira_oauth.py
    - backend/src/services/jira_sync.py
    - backend/src/services/jira_webhook.py
    - backend/src/routers/jira.py
  modified:
    - backend/src/routers/integrations.py
    - backend/src/main.py

key-decisions:
  - "Jira token exchange uses JSON body (not form data) -- critical Atlassian API difference from Linear"
  - "Jira sync uses /search/jql POST endpoint with nextPageToken pagination (not deprecated /search with startAt)"
  - "ADF text extraction helper converts Jira REST API v3 document format to plain text for descriptions/comments"
  - "get_valid_token returns (access_token, cloud_id) tuple since cloud_id is needed for all API calls"

patterns-established:
  - "Jira OAuth pattern: build_auth_url -> exchange_code (with accessible-resources) -> get_valid_token -> disconnect"
  - "Jira webhook cloud_id extraction from issue self URL for workspace resolution"

requirements-completed: [JIRA-01, JIRA-02, JIRA-03, JIRA-04]

duration: 5min
completed: 2026-03-10
---

# Phase 25 Plan 02: Jira Backend Services & Router Summary

**Jira OAuth 2.0 3LO with cloudId resolution, /search/jql issue sync with nextPageToken, HMAC-SHA256 webhook handler, and FastAPI router at /api/jira/**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-10T00:47:57Z
- **Completed:** 2026-03-10T00:53:17Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Jira OAuth flow with Atlassian accessible-resources endpoint for cloudId discovery
- Issue sync using modern /search/jql with nextPageToken pagination and ADF text extraction
- Webhook handler verifying HMAC-SHA256 signatures and processing issue/comment CRUD events
- Full router with connect/callback/disconnect/status/sync/webhook/search endpoints

## Task Commits

Each task was committed atomically:

1. **Task 1: Jira OAuth, Sync, and Webhook services** - `beb99d9` (feat)
2. **Task 2: Jira router, integrations update, and main.py wiring** - `a6a1ced` (feat)

## Files Created/Modified
- `backend/src/services/jira_oauth.py` - OAuth 2.0 3LO flow with cloudId resolution via accessible-resources
- `backend/src/services/jira_sync.py` - Issue sync via /search/jql with nextPageToken, ADF text extraction
- `backend/src/services/jira_webhook.py` - Webhook processor with HMAC-SHA256 verification
- `backend/src/routers/jira.py` - FastAPI router with 8 endpoints at /api/jira/*
- `backend/src/routers/integrations.py` - Added Provider.JIRA to PROVIDERS list with issues_synced status
- `backend/src/main.py` - Mounted jira_router in application

## Decisions Made
- Jira token exchange uses JSON body (not form data) -- Atlassian requires JSON for OAuth token requests
- Sync uses POST /search/jql with nextPageToken pagination (modern API, not deprecated startAt)
- ADF text extraction helper walks Atlassian Document Format tree to extract plain text for embedding
- get_valid_token returns (access_token, cloud_id) tuple since cloud_id is needed for every Jira API call
- Webhook cloud_id extracted from issue self URL pattern (ex/jira/{cloud_id}/...) for workspace resolution

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Jira OAuth credentials (JIRA_CLIENT_ID, JIRA_CLIENT_SECRET) were already configured in Plan 01.

## Next Phase Readiness
- Backend Jira integration complete -- ready for frontend settings UI (Plan 03)
- All endpoints tested for syntax correctness
- SyncAdapter protocol satisfied by JiraSyncService

---
*Phase: 25-jira-integration*
*Completed: 2026-03-10*
