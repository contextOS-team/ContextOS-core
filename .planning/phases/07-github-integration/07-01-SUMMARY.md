---
phase: 07-github-integration
plan: 01
subsystem: auth
tags: [github-app, oauth, jwt, rs256, pyjwt, httpx, vault, rls, sqlmodel]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "BaseModel, TimestampMixin, Settings, get_current_user dependency, async session"
  - phase: 02-linear-integration
    provides: "Vault service (store_token, read_token, delete_token), OAuthToken/WorkspaceIntegration models, HMAC-signed state pattern"
provides:
  - "GitHub App OAuth connect/callback/disconnect/status endpoints"
  - "GitHub App JWT (RS256) for installation access token generation"
  - "Installation access token refresh (1-hour expiry) via App JWT"
  - "GithubPullRequest and GithubReview SQLModel models"
  - "github_pull_requests and github_reviews tables with RLS"
  - "Vault-encrypted installation access token storage"
affects: [07-02-PLAN, 07-03-PLAN]

# Tech tracking
tech-stack:
  added: [pyjwt-rs256]
  patterns: [github-app-jwt, installation-token-refresh, github-app-install-flow]

key-files:
  created:
    - supabase/migrations/00004_github_tables.sql
    - backend/src/models/github.py
    - backend/src/services/github_oauth.py
    - backend/src/routers/github.py
    - backend/tests/test_github_oauth.py
  modified:
    - backend/src/config.py
    - backend/src/main.py
    - backend/src/models/__init__.py
    - .env.example

key-decisions:
  - "PyJWT with RS256 for GitHub App JWT signing (already a project dependency, no new library needed)"
  - "Installation access tokens stored in Vault with 1-hour expiry tracking; refreshed on demand via App JWT"
  - "GitHub App installation flow (not standard OAuth2 code exchange) per CONTEXT.md decision"
  - "HMAC-SHA256 signed state parameter uses GITHUB_CLIENT_SECRET (same pattern as Linear/Slack)"
  - "installation_id stored in OAuthToken.metadata_ JSONB for token refresh without extra DB query"
  - "'github' added to oauth_tokens and workspace_integrations provider check constraints via migration"

patterns-established:
  - "GitHub App JWT pattern: RS256-signed JWT with iss=APP_ID, iat-60s, exp+10min for API authentication"
  - "Installation token refresh: check expiry with 5-min buffer, generate new token via POST /app/installations/{id}/access_tokens"
  - "GitHub App install flow: redirect to github.com/apps/{slug}/installations/new?state={hmac_state}"

requirements-completed: [GH-01]

# Metrics
duration: 8min
completed: 2026-02-25
---

# Phase 7 Plan 1: GitHub App OAuth Summary

**GitHub App OAuth with RS256 JWT signing, installation access token refresh, Vault-encrypted storage, and PR/review database schema**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-25T06:52:34Z
- **Completed:** 2026-02-25T07:01:06Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- GitHub App OAuth connect/callback/disconnect/status endpoints with full installation lifecycle
- RS256-signed App JWT for GitHub API authentication, installation access token generation with 1-hour expiry tracking and on-demand refresh
- github_pull_requests and github_reviews tables with RLS, indexes, moddatetime triggers, and SQLModel models
- 11 tests covering all OAuth flows, JWT generation, token refresh, error cases, and auth requirements

## Task Commits

Each task was committed atomically:

1. **Task 1: GitHub database tables and SQLModel models** - `650b56a` (feat)
2. **Task 2: GitHub App OAuth service, router, config, and tests** - `0043b36` (feat)

## Files Created/Modified
- `supabase/migrations/00004_github_tables.sql` - github_pull_requests and github_reviews tables with RLS, indexes, triggers, and provider constraint updates
- `backend/src/models/github.py` - GithubPullRequest and GithubReview SQLModel models with JSONB, ARRAY patterns
- `backend/src/models/__init__.py` - Re-exported GithubPullRequest and GithubReview
- `backend/src/config.py` - Added GITHUB_APP_ID, GITHUB_APP_SLUG, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_WEBHOOK_SECRET, GITHUB_APP_PRIVATE_KEY, GITHUB_REDIRECT_URI, github_redirect_uri property
- `backend/src/services/github_oauth.py` - Full GitHub App OAuth lifecycle: install URL, callback, disconnect, status, installation token refresh, App JWT creation
- `backend/src/routers/github.py` - HTTP endpoints: /connect, /callback, /disconnect, /status
- `backend/src/main.py` - Registered github router
- `backend/tests/test_github_oauth.py` - 11 tests for all OAuth flows
- `.env.example` - Added GitHub App environment variables with documentation

## Decisions Made
- Used PyJWT with RS256 for GitHub App JWT signing -- already a project dependency (`PyJWT[crypto]>=2.8`), no new library needed
- Installation access tokens stored in Vault with 1-hour expiry tracking; refreshed on demand via fresh App JWT
- Used GitHub App installation flow (redirect to `/apps/{slug}/installations/new`) per CONTEXT.md decision, not standard OAuth2 code exchange
- HMAC-SHA256 signed state parameter uses GITHUB_CLIENT_SECRET (consistent with Linear/Slack OAuth pattern)
- installation_id stored in OAuthToken.metadata_ JSONB for efficient token refresh without extra DB lookup
- Added 'github' to oauth_tokens and workspace_integrations provider check constraints via migration ALTER

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed invalid test RSA private key**
- **Found during:** Task 2 (test execution)
- **Issue:** Initial placeholder RSA key was not a valid PEM key; PyJWT RS256 signing rejected it with InvalidKeyError
- **Fix:** Generated a proper 2048-bit RSA private key using cryptography library for test fixtures
- **Files modified:** backend/tests/test_github_oauth.py
- **Verification:** All 11 tests pass
- **Committed in:** 0043b36

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test fixture fix. No scope creep.

## Issues Encountered
None

## User Setup Required
GitHub App registration is required before live usage. Environment variables documented in `.env.example`:
- GITHUB_APP_ID, GITHUB_APP_SLUG, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
- GITHUB_WEBHOOK_SECRET, GITHUB_APP_PRIVATE_KEY
- Callback URL: {BACKEND_URL}/api/github/callback
- Required permissions: Pull requests (Read), Contents (Read), Metadata (Read)
- Required events: pull_request, pull_request_review, pull_request_review_comment

## Next Phase Readiness
- OAuth endpoints ready for Plan 07-02 (repo selection and PR sync) to use get_installation_token for GitHub API calls
- GithubPullRequest and GithubReview models ready for Plan 07-02 PR data ingestion
- Installation token refresh mechanism ready for long-running sync operations
- Database schema ready for PR-to-Linear linking via linear_ticket_id FK

## Self-Check: PASSED

All files verified present on disk. All commit hashes verified in git log.

---
*Phase: 07-github-integration*
*Completed: 2026-02-25*
