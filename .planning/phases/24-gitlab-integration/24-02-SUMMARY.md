---
phase: 24-gitlab-integration
plan: 02
subsystem: api
tags: [gitlab, oauth2, fastapi, httpx, webhooks, merge-requests]

# Dependency graph
requires:
  - phase: 24-gitlab-integration/01
    provides: "GitLab DB models (gitlab_merge_requests, gitlab_reviews), Provider.GITLAB enum, config settings"
provides:
  - "GitLab OAuth2 connect/callback/disconnect/status"
  - "GitLab project listing, selection, caching"
  - "GitLab MR + review sync with 60-day backfill"
  - "GitLab webhook processing (MR + note events)"
  - "GitLab MR-to-Linear ticket linking via branch name"
  - "FastAPI router with 10 endpoints registered in main.py"
affects: [24-gitlab-integration/03, frontend-integrations]

# Tech tracking
tech-stack:
  added: []
  patterns: ["GitLab OAuth2 standard code flow (not App JWT)", "X-Gitlab-Token constant-time comparison for webhooks", "Numeric project IDs (not paths) for selection"]

key-files:
  created:
    - backend/src/services/gitlab_common.py
    - backend/src/services/gitlab_oauth.py
    - backend/src/services/gitlab_repos.py
    - backend/src/services/gitlab_sync.py
    - backend/src/services/gitlab_webhook.py
    - backend/src/services/gitlab_linking.py
    - backend/src/routers/gitlab.py
  modified:
    - backend/src/main.py

key-decisions:
  - "Standard OAuth2 authorization code flow -- GitLab uses standard OAuth2 not App JWT like GitHub"
  - "X-Gitlab-Token header comparison for webhook verification -- not HMAC body signature like GitHub"
  - "Reuse github_linking extract_linear_issue_id -- branch name patterns are provider-agnostic"
  - "Numeric project IDs for selection -- per research pitfall 2 about URL-encoded paths"

patterns-established:
  - "GitLab OAuth2 flow: /connect -> /callback with code+state -> token exchange"
  - "Webhook lookup by project_id in selected_projects config JSONB"

requirements-completed: [GL-01, GL-02, GL-03, GL-04, GL-05, GL-06]

# Metrics
duration: 5min
completed: 2026-03-10
---

# Phase 24 Plan 02: GitLab Backend Services Summary

**Complete GitLab backend with OAuth2 connect/disconnect, MR sync with pagination, webhook processing, project selection, and Linear linking across 6 service modules + router**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-10T00:48:42Z
- **Completed:** 2026-03-10T00:54:07Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Built 6 GitLab service modules (1910 lines total) mirroring GitHub integration architecture
- Created FastAPI router with 10 endpoints: connect, callback, disconnect, status, repos, repos/refresh, repos/select, sync, sync/status, webhook
- Registered gitlab_router in main.py alongside existing integrations

## Task Commits

Each task was committed atomically:

1. **Task 1: Create GitLab common, OAuth, and repos services** - `bbf6c70` (feat)
2. **Task 2: Create GitLab sync, webhook, linking services, router, and register in main.py** - `97356bd` (feat)

## Files Created/Modified
- `backend/src/services/gitlab_common.py` - API helpers, headers, token refresh, state mapping, timestamp parsing
- `backend/src/services/gitlab_oauth.py` - OAuth2 connect/callback/disconnect/status lifecycle
- `backend/src/services/gitlab_repos.py` - Project listing, selection, caching with numeric IDs
- `backend/src/services/gitlab_sync.py` - MR + note sync with 60-day backfill and pagination
- `backend/src/services/gitlab_webhook.py` - Webhook event processor for MR and note events
- `backend/src/services/gitlab_linking.py` - MR-to-Linear ticket linking delegating to github_linking
- `backend/src/routers/gitlab.py` - FastAPI router with all GitLab endpoints
- `backend/src/main.py` - Added gitlab_router import and registration

## Decisions Made
- Used standard OAuth2 authorization code flow (not GitHub App JWT) -- GitLab uses standard OAuth2
- X-Gitlab-Token header with hmac.compare_digest for webhook verification -- constant-time comparison prevents timing attacks
- Reused extract_linear_issue_id from github_linking -- branch name patterns are provider-agnostic, no regex duplication
- Used numeric project IDs (not path_with_namespace) for project selection -- avoids URL encoding issues per research

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All backend services ready for frontend integration (Plan 03)
- Router endpoints match the interface patterns from Linear/Slack/GitHub integrations
- OAuth callback redirects to /dashboard/integrations?gitlab=connected

---
*Phase: 24-gitlab-integration*
*Completed: 2026-03-10*
