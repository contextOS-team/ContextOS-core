---
phase: 28-gitlab-code-indexing
plan: 01
subsystem: api
tags: [gitlab, code-indexing, oauth, tree-sitter, embeddings]

# Dependency graph
requires:
  - phase: 24-gitlab-integration
    provides: GitLab OAuth, project selection, workspace_integrations config
  - phase: 12-code-intel
    provides: code_indexer, code_index_worker, code_parser, code_chunks table
provides:
  - Provider-aware clone authentication (_get_clone_credentials)
  - GitLab workspace repo indexing (index_gitlab_workspace_repos)
  - POST /api/gitlab/index endpoint for triggering indexing
  - GET /api/gitlab/index/status endpoint with GitLab-filtered chunk counts
  - GitLab selected_repos_count in integrations status
affects: [28-02, frontend-gitlab-settings]

# Tech tracking
tech-stack:
  added: []
  patterns: [provider-aware clone auth dispatch, per-repo token refresh for short-lived OAuth tokens]

key-files:
  created: []
  modified:
    - backend/src/services/code_indexer.py
    - backend/src/services/code_index_worker.py
    - backend/src/routers/gitlab.py
    - backend/src/routers/integrations.py

key-decisions:
  - "Provider dispatch via string param (not class hierarchy) for minimal abstraction"
  - "Token refresh before EACH GitLab repo clone since OAuth tokens expire in 2 hours"
  - "GitLab chunks filtered by matching repo_full_name against available_projects paths"

patterns-established:
  - "_get_clone_credentials returns (url_prefix, token) tuple for provider-agnostic cloning"
  - "enqueue_workspace_index_job accepts provider param included in Redis job payload"

requirements-completed: [GL-10, GL-11]

# Metrics
duration: 4min
completed: 2026-03-12
---

# Phase 28 Plan 01: GitLab Code Indexing Summary

**Provider-aware code indexing pipeline with GitLab OAuth clone auth, /index and /index/status endpoints, and integrations status extension**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-12T10:26:07Z
- **Completed:** 2026-03-12T10:30:07Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Abstracted clone authentication to support both GitHub (installation token) and GitLab (OAuth2 token)
- Created GitLab workspace indexing function with per-repo token refresh for 2-hour token expiry
- Added POST /api/gitlab/index and GET /api/gitlab/index/status endpoints
- Extended integrations status with GitLab selected_repos_count

## Task Commits

Each task was committed atomically:

1. **Task 1: Abstract clone auth and add provider-aware indexing functions** - `3b3058b` (feat)
2. **Task 2: Add /index and /index/status endpoints to GitLab router and update integrations status** - `49336db` (feat)

## Files Created/Modified
- `backend/src/services/code_indexer.py` - Added _get_clone_credentials helper, provider param on index_repo/_update_index_status, index_gitlab_workspace_repos function
- `backend/src/services/code_index_worker.py` - Added provider field to job payload, dispatch to GitLab indexer
- `backend/src/routers/gitlab.py` - Added POST /index and GET /index/status endpoints with GitLab-filtered chunks
- `backend/src/routers/integrations.py` - Added selected_repos_count for GitLab provider

## Decisions Made
- Provider dispatch via string param (not class hierarchy) for minimal abstraction -- matches existing codebase patterns
- Token refresh before EACH GitLab repo clone since OAuth tokens expire in 2 hours -- prevents mid-batch auth failures
- GitLab chunks filtered by matching repo_full_name against available_projects path_with_namespace values from config

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend endpoints ready for frontend to trigger and poll GitLab code indexing
- Plan 02 can add frontend UI for GitLab code indexing controls

---
*Phase: 28-gitlab-code-indexing*
*Completed: 2026-03-12*
