---
phase: 07-github-integration
plan: 02
subsystem: data-sync
tags: [github-repos, pr-sync, backfill, linear-linking, branch-parsing, pagination, rate-limit]

# Dependency graph
requires:
  - phase: 07-github-integration
    plan: 01
    provides: "GitHub App OAuth, installation token refresh, GithubPullRequest/GithubReview models"
  - phase: 02-linear-integration
    provides: "LinearTicket model, team key extraction from identifiers"
provides:
  - "Repo listing from GitHub API with Link header pagination"
  - "Repo caching in workspace_integrations.config JSONB"
  - "User-driven repo selection (no auto-monitoring)"
  - "PR sync with 60-day backfill window"
  - "Bot account filtering (dependabot, renovate, github-actions)"
  - "Draft PR inclusion"
  - "Per-repo sync status tracking in config JSONB"
  - "PR-to-Linear ticket linking via branch name pattern parsing"
  - "Auto-detected Linear team keys from existing tickets"
affects: [07-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns: [github-link-header-pagination, branch-name-linking, sequential-sync-with-rate-limit]

key-files:
  created:
    - backend/src/services/github_repos.py
    - backend/src/services/github_sync.py
    - backend/src/services/github_linking.py
    - backend/tests/test_github_repos.py
    - backend/tests/test_github_sync.py
  modified:
    - backend/src/routers/github.py

key-decisions:
  - "Sequential repo sync per user decision -- avoids rate limit exhaustion"
  - "New repos NOT auto-monitored (unlike Slack channels) -- explicit selection required"
  - "Branch-name-only linking to minimize false positives -- team keys auto-detected from Linear tickets"
  - "Bot accounts (dependabot[bot], renovate[bot], github-actions[bot]) filtered by login suffix check"
  - "60-day backfill window stops pagination when PR updated_at is older than cutoff"
  - "Per-repo sync progress tracked in config JSONB with status/synced/total fields"

patterns-established:
  - "GitHub Link header pagination: parse rel=next from Link header for multi-page API results"
  - "Branch name linking: regex pattern (?:^|[/\\-_])(TEAM_KEY)-(\\d+) with case-insensitive matching"
  - "Auto-detect team keys: SPLIT_PART on linear_tickets.identifier to extract unique prefixes"
  - "Sequential sync with rate limit: check X-RateLimit-Remaining, sleep until reset if < 100"

requirements-completed: [GH-02, GH-03]

# Metrics
duration: 6min
completed: 2026-02-25
---

# Phase 7 Plan 2: Repo Selection and PR Sync Summary

**Repo listing/selection, PR sync with 60-day backfill, bot filtering, and PR-to-Linear linking via branch name pattern parsing**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-02-25
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Repo listing from GitHub API with Link header pagination and caching in config JSONB
- User-driven repo selection with validation against cached available repos
- is_repo_monitored returns false when no repos selected (no auto-monitoring per user decision)
- PR sync with 60-day backfill window, sequential processing, and rate limit awareness
- Bot account filtering (dependabot[bot], renovate[bot], github-actions[bot]) skips bot-authored PRs
- Draft PRs included in sync (per user decision)
- Per-repo sync status tracked in config JSONB (syncing/synced/error with progress count)
- PR-to-Linear linking via branch name regex with auto-detected team keys from Linear tickets
- Unlinked PRs stored with null linear_ticket_id (not discarded)
- 29 tests total: 13 for repos + 16 for sync/linking, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Repo listing, selection, and caching service with endpoints** - `98dcbbe` (feat)
2. **Task 2: PR sync with 60-day backfill, per-repo progress, and PR-to-Linear linking** - `bb44daf` (feat)

## Files Created/Modified
- `backend/src/services/github_repos.py` - Repo listing with Link header pagination, caching, selection, is_repo_monitored
- `backend/src/services/github_sync.py` - PR sync with 60-day backfill, bot filtering, rate limiting, per-repo progress
- `backend/src/services/github_linking.py` - Branch name parsing, auto-detected team keys, PR-to-Linear linking
- `backend/src/routers/github.py` - Added /repos, /repos/refresh, /repos/select, /sync, /sync/status endpoints
- `backend/tests/test_github_repos.py` - 13 tests for repo listing, pagination, caching, selection, monitoring
- `backend/tests/test_github_sync.py` - 16 tests for linking, sync, bot filtering, drafts, 60-day window, progress

## Decisions Made
- Sequential repo sync per user decision to avoid rate limit exhaustion
- New repos NOT auto-monitored (explicit selection required, unlike Slack channels)
- Branch-name-only linking with case-insensitive regex for team key matching
- Bot filtering via login suffix check (dependabot[bot], renovate[bot], github-actions[bot])
- 60-day backfill window implemented as cutoff check on PR updated_at during pagination

## Deviations from Plan

None

## Issues Encountered
- Minor deprecation warnings for datetime.utcnow() in tests (non-blocking, Python 3.13+ deprecation)

## Next Phase Readiness
- github_repos.is_repo_monitored ready for webhook service to check if events should be processed
- github_linking.link_pr_to_ticket ready for webhook service to link new PRs
- Sync endpoints ready for frontend to trigger initial sync after repo selection
- Per-repo sync status ready for frontend progress display

## Self-Check: PASSED

All files verified present on disk. All commit hashes verified in git log.

---
*Phase: 07-github-integration*
*Completed: 2026-02-25*
