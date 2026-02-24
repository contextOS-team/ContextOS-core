---
phase: 02-linear-integration
plan: 01
subsystem: auth
tags: [oauth2, linear, vault, pgsodium, httpx, hmac, advisory-lock]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "BaseModel, TimestampMixin, Settings, get_current_user dependency, async session"
provides:
  - "Linear OAuth connect/callback/disconnect/status endpoints"
  - "Vault service for encrypted token storage (store_token, read_token, delete_token)"
  - "OAuthToken, WorkspaceIntegration, WebhookDelivery SQLModel models"
  - "Token refresh with pg_advisory_xact_lock race prevention"
  - "HMAC-SHA256 signed state for CSRF protection"
affects: [02-02-PLAN, 02-03-PLAN, 03-slack-integration]

# Tech tracking
tech-stack:
  added: [pgsodium, supabase_vault]
  patterns: [vault-encrypted-tokens, advisory-lock-refresh, hmac-signed-state]

key-files:
  created:
    - backend/src/services/linear_oauth.py
    - backend/src/services/vault.py
    - backend/src/routers/linear.py
    - backend/src/models/integration.py
    - backend/tests/test_linear_oauth.py
    - supabase/migrations/00003_vault_token_functions.sql
  modified:
    - backend/src/config.py
    - backend/src/main.py
    - backend/src/models/__init__.py
    - .env.example

key-decisions:
  - "Vault secrets API (vault.create_secret/decrypted_secrets) used over raw pgsodium for simpler token storage"
  - "State parameter uses HMAC-SHA256 signing with LINEAR_CLIENT_SECRET for CSRF protection"
  - "Token values stored in Vault; DB columns store Vault secret name references, not actual tokens"
  - "Advisory lock key uses hashtext of workspace_id string for deterministic locking"

patterns-established:
  - "Vault token pattern: store Vault secret names in DB, actual encrypted values in vault.secrets"
  - "OAuth service pattern: separate service module for lifecycle, router for HTTP endpoints"
  - "Advisory lock pattern: pg_advisory_xact_lock(hashtext(key)) for per-resource mutex"

requirements-completed: [LIN-01, LIN-05]

# Metrics
duration: 5min
completed: 2026-02-24
---

# Phase 2 Plan 1: Linear OAuth Summary

**Linear OAuth2 flow with Vault-encrypted token storage, HMAC-signed state, and advisory lock refresh**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-24T16:14:34Z
- **Completed:** 2026-02-24T16:19:48Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Linear OAuth connect/callback/disconnect/status endpoints with full lifecycle
- Vault-encrypted token storage via Supabase Vault (pgsodium) -- tokens never stored in plain text
- Token refresh with pg_advisory_xact_lock preventing race conditions across concurrent workers
- 8 tests covering authorization URL generation, code exchange, disconnect, status, advisory lock, and error handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Vault token functions, models, and config** - `bd17cb8` (feat)
2. **Task 2: OAuth service, router, and tests** - `ecc86c6` (feat)

## Files Created/Modified
- `supabase/migrations/00003_vault_token_functions.sql` - Vault helper SQL functions and webhook_deliveries table
- `backend/src/models/integration.py` - OAuthToken, WorkspaceIntegration, WebhookDelivery models
- `backend/src/services/vault.py` - Vault CRUD wrapper (store_token, read_token, delete_token)
- `backend/src/services/linear_oauth.py` - Full OAuth2 lifecycle (auth URL, code exchange, refresh, disconnect)
- `backend/src/routers/linear.py` - HTTP endpoints: /connect, /callback, /disconnect, /status
- `backend/tests/test_linear_oauth.py` - 8 tests for all OAuth flows
- `backend/src/config.py` - Added LINEAR_CLIENT_ID, LINEAR_CLIENT_SECRET, LINEAR_WEBHOOK_SECRET, linear_redirect_uri
- `backend/src/main.py` - Registered linear router
- `backend/src/models/__init__.py` - Re-exported new integration models
- `.env.example` - Added LINEAR_REDIRECT_URI with default documentation

## Decisions Made
- Used Vault secrets API (vault.create_secret/decrypted_secrets) over raw pgsodium for simpler token storage
- State parameter uses HMAC-SHA256 signing with LINEAR_CLIENT_SECRET for CSRF protection
- Token values stored in Vault; DB columns store Vault secret name references, not actual tokens
- Advisory lock key uses hashtext of workspace_id string for deterministic locking
- Callback endpoint looks up workspace owner from workspace_members as user_id source

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed auth test assertion for HTTPBearer status code**
- **Found during:** Task 2 (test_connect_requires_auth)
- **Issue:** Plan specified 401/403 but FastAPI HTTPBearer returns 401 when no credentials header present
- **Fix:** Updated assertion to accept either 401 or 403
- **Files modified:** backend/tests/test_linear_oauth.py
- **Verification:** Test passes
- **Committed in:** ecc86c6

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test assertion fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Linear OAuth app registration is documented in .env.example but is a prerequisite for live usage, not for development/testing.

## Next Phase Readiness
- OAuth endpoints ready for Plan 02-02 (Linear data sync) to use get_valid_access_token for API calls
- WebhookDelivery model ready for Plan 02-03 (webhook processing) idempotency tracking
- Vault pattern established for reuse by Slack OAuth in Phase 3

## Self-Check: PASSED

All files verified present on disk. All commit hashes verified in git log.

---
*Phase: 02-linear-integration*
*Completed: 2026-02-24*
