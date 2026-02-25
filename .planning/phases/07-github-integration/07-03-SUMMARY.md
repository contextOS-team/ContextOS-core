---
phase: 07-github-integration
plan: 03
subsystem: webhooks-ui
tags: [github-webhooks, hmac-sha256, idempotency, react, repo-picker, integration-ui]

# Dependency graph
requires:
  - phase: 07-github-integration
    plan: 01
    provides: "GitHub App OAuth, installation token refresh, GithubPullRequest/GithubReview models, GITHUB_WEBHOOK_SECRET config"
  - phase: 07-github-integration
    plan: 02
    provides: "Repo listing/selection, is_repo_monitored, link_pr_to_ticket, PR sync service"
  - phase: 02-linear-integration
    provides: "Webhook receiver pattern, idempotent delivery tracking, WebhookDelivery model"
  - phase: 03-slack-meeting-ingestion
    provides: "SlackChannels picker component pattern, integration card pattern"
provides:
  - "POST /api/webhooks/github endpoint with HMAC-SHA256 signature verification"
  - "Idempotent webhook delivery tracking via X-GitHub-Delivery header"
  - "PR event processing: opened/closed/merged/edited with bot filtering"
  - "Review event processing: approved/changes_requested/commented states"
  - "Review comment processing with file_path and line_range context"
  - "GitHub integration card on /dashboard/integrations page"
  - "Searchable repo picker component (GithubRepos)"
  - "GitHub provider in unified /api/integrations/status endpoint"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [github-webhook-hmac-sha256, installation-id-workspace-lookup, review-comment-file-context]

key-files:
  created:
    - backend/src/services/github_webhook.py
    - backend/tests/test_github_webhook.py
    - apps/web/src/app/dashboard/integrations/github-repos.tsx
  modified:
    - backend/src/routers/webhooks.py
    - backend/src/routers/integrations.py
    - apps/web/src/lib/api.ts
    - apps/web/src/app/dashboard/integrations/page.tsx

key-decisions:
  - "GitHub webhook signature uses X-Hub-Signature-256 header with sha256= prefix format (vs Linear's simple hex digest)"
  - "Workspace resolved from installation.id in payload by scanning OAuthToken metadata_ JSONB"
  - "Review comments stored as GithubReview records (same table as reviews) with file_path and line_range for code context"
  - "Bot filtering via exact login match against known set (dependabot[bot], renovate[bot], github-actions[bot])"
  - "Grid layout changed from md:grid-cols-3 to md:grid-cols-2 lg:grid-cols-4 for 4 integration cards"

patterns-established:
  - "GitHub webhook HMAC: sha256= prefix comparison with hmac.compare_digest for timing-safe validation"
  - "Installation-to-workspace lookup: scan OAuthToken records for matching installation_id in metadata_ JSONB"
  - "Review comment file context: path field for file, line+original_line for range stored as string"

requirements-completed: [GH-04, GH-05]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 7 Plan 3: Webhook Receiver and Integration UI Summary

**GitHub webhook receiver with HMAC-SHA256 verification, idempotent PR/review event processing, and integration setup UI with searchable repo picker**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-25T13:10:26Z
- **Completed:** 2026-02-25T13:15:41Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- POST /api/webhooks/github with HMAC-SHA256 signature verification, idempotent delivery tracking, and background task delegation
- PR event handler upserts GithubPullRequest records with state mapping (open/closed/merged), bot filtering, and Linear ticket linking
- Review and review comment handlers upsert GithubReview records with author, state, body, and file/line context
- GitHub integration card on /dashboard/integrations with connect/disconnect and expandable repo picker
- Searchable GithubRepos component mirroring SlackChannels UX (checkbox list, search, refresh, save)
- Unified /api/integrations/status endpoint now includes github provider with selected_repos_count
- 12 tests covering all webhook flows: signature validation, idempotency, PR events, review events, workspace lookup

## Task Commits

Each task was committed atomically:

1. **Task 1: GitHub webhook receiver with signature verification, idempotency, and event processing** - `4106870` (feat)
2. **Task 2: GitHub integration card, repo picker UI, and unified status endpoint update** - `b86d120` (feat)

## Files Created/Modified
- `backend/src/services/github_webhook.py` - Webhook event processor: PR, review, review comment handlers with bot filtering and workspace lookup
- `backend/src/routers/webhooks.py` - Added POST /api/webhooks/github endpoint with HMAC-SHA256 verification and idempotency
- `backend/tests/test_github_webhook.py` - 12 tests for signature verification, idempotency, all event types, workspace lookup
- `backend/src/routers/integrations.py` - Added "github" to PROVIDERS, selected_repos_count in status
- `apps/web/src/lib/api.ts` - Added GitHub API functions and GithubRepo type, updated IntegrationStatusResponse
- `apps/web/src/app/dashboard/integrations/github-repos.tsx` - Searchable repo picker component
- `apps/web/src/app/dashboard/integrations/page.tsx` - Added GitHub card, handlers, updated grid to 4-col

## Decisions Made
- Used X-Hub-Signature-256 header with sha256= prefix format per GitHub's webhook specification (different from Linear's simple hex digest)
- Workspace resolved from installation.id by scanning OAuthToken metadata_ JSONB (GitHub webhooks are App-level, not per-repo)
- Review comments stored as GithubReview records with file_path and line_range fields for code-level context
- Bot filtering uses exact login match against known set rather than suffix pattern matching
- Integration grid changed from 3-col to responsive 2-col/4-col layout to accommodate 4th card

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
GitHub App registration and webhook configuration required before live usage. The webhook URL should be set to `{BACKEND_URL}/api/webhooks/github` in the GitHub App settings. GITHUB_WEBHOOK_SECRET env var must match the secret configured in the GitHub App.

## Next Phase Readiness
- Phase 7 GitHub integration is now complete: OAuth (plan 01), repo selection + PR sync (plan 02), and webhooks + UI (plan 03)
- All GitHub webhook events (pull_request, pull_request_review, pull_request_review_comment) are processed in real-time
- Integration setup page now has 4 complete cards: Linear, Slack, Fathom, GitHub
- Ready for Phase 4 embedding generation when PRs and reviews need semantic search

## Self-Check: PASSED

All files verified present on disk. All commit hashes verified in git log.

---
*Phase: 07-github-integration*
*Completed: 2026-02-25*
