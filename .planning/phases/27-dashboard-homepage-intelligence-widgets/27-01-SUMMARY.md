---
phase: 27-dashboard-homepage-intelligence-widgets
plan: 01
subsystem: api
tags: [fastapi, dashboard, linear-graphql, sqlalchemy, slack, heuristics]

# Dependency graph
requires:
  - phase: 02-linear-integration
    provides: Linear GraphQL client and OAuth token retrieval
  - phase: 03-slack-meeting
    provides: SlackMessage model and ingestion
  - phase: 07-github
    provides: GithubPullRequest model
  - phase: 24-gitlab-integration
    provides: GitlabMergeRequest model
provides:
  - GET /api/dashboard/attention endpoint (stale contexts + open PRs/MRs)
  - GET /api/dashboard/weekly-summary endpoint (day-bucketed activity counts)
  - GET /api/dashboard/sprint endpoint (Linear active cycle progress)
  - GET /api/dashboard/resurfaced endpoint (forgotten context detection)
affects: [27-02-frontend-widgets]

# Tech tracking
tech-stack:
  added: []
  patterns: [dashboard service pattern with per-widget service modules]

key-files:
  created:
    - backend/src/routers/dashboard.py
    - backend/src/services/dashboard_attention.py
    - backend/src/services/dashboard_summary.py
    - backend/src/services/dashboard_sprint.py
    - backend/src/services/dashboard_resurfaced.py
  modified:
    - backend/src/main.py

key-decisions:
  - "Sprint endpoint uses get_valid_access_token from linear_oauth for token retrieval with user_id"
  - "Resurfaced uses heuristic keyword matching (15 patterns) for v1 -- deterministic, fast, free"
  - "Weekly summary uses raw SQL for activity_events (no SQLModel model) and SQLAlchemy for other tables"

patterns-established:
  - "Dashboard service pattern: one service module per widget, router delegates to service functions"

requirements-completed: [API-01, API-02, API-03, API-04, WIDGET-01, WIDGET-02, WIDGET-03, WIDGET-04]

# Metrics
duration: 3min
completed: 2026-03-15
---

# Phase 27 Plan 01: Dashboard Intelligence Widget APIs Summary

**4 pre-aggregated dashboard API endpoints: attention items, weekly activity summary, Linear sprint progress, and resurfaced forgotten Slack context**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-15T17:38:46Z
- **Completed:** 2026-03-15T17:41:38Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- 4 GET endpoints under /api/dashboard/ returning workspace-scoped pre-aggregated data
- Attention endpoint combines stale context pages, open GitHub PRs, and open GitLab MRs into unified list
- Weekly summary groups activity events, context updates, and merged PRs/MRs by day for last 7 days
- Sprint endpoint queries Linear GraphQL activeCycle and returns the team with soonest-ending cycle
- Resurfaced endpoint uses 15 decision-like keyword patterns to surface forgotten Slack messages

## Task Commits

Each task was committed atomically:

1. **Task 1: Create dashboard router with attention, weekly-summary, and sprint endpoints** - `9210a08` (feat)
2. **Task 2: Create resurfaced forgotten context endpoint** - `aaf3f15` (feat)

## Files Created/Modified
- `backend/src/routers/dashboard.py` - Dashboard router with 4 GET endpoints
- `backend/src/services/dashboard_attention.py` - Stale contexts + open PRs/MRs aggregation
- `backend/src/services/dashboard_summary.py` - Weekly activity counts by day
- `backend/src/services/dashboard_sprint.py` - Linear active cycle via GraphQL
- `backend/src/services/dashboard_resurfaced.py` - Keyword-based forgotten context detection
- `backend/src/main.py` - Dashboard router registration

## Decisions Made
- Sprint endpoint requires user_id for Linear OAuth token retrieval (uses get_valid_access_token from linear_oauth)
- Resurfaced v1 uses heuristic keyword matching (15 patterns) instead of LLM -- deterministic, fast, free
- Weekly summary uses raw SQL text() for activity_events table (no SQLModel model exists) and SQLAlchemy ORM for other tables
- GitLab merged MRs added to same prs_merged counter in weekly summary (combined with GitHub)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 4 dashboard API endpoints operational and registered in main.py
- Frontend can consume these endpoints for dashboard homepage widgets
- Resurfaced endpoint swappable to LLM-based detection later without frontend changes

---
*Phase: 27-dashboard-homepage-intelligence-widgets*
*Completed: 2026-03-15*
