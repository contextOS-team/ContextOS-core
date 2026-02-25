---
phase: 06-extension-and-hardening
plan: 04
subsystem: security
tags: [vault, token-encryption, lazy-migration, health-check, readiness-probe, supabase-vault]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Database schema, Vault token functions, health endpoint
  - phase: 02-linear-integration
    provides: Linear OAuth with Vault token storage pattern
  - phase: 06-extension-and-hardening
    provides: Structured logging via observability module (plan 06-02)
provides:
  - Vault lazy migration helper for transparent plaintext-to-Vault migration
  - Vault health check function for deployment readiness probes
  - Deep health endpoint (/api/health/ready) with DB, Vault, and external API checks
  - vault_migrated_at tracking column on oauth_tokens for migration verification
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [lazy-migration-on-first-read, deep-health-check-with-latency-metrics, critical-vs-informational-health-checks]

key-files:
  created:
    - supabase/migrations/00004_vault_lazy_migration.sql
  modified:
    - backend/src/services/vault.py
    - backend/src/routers/health.py

key-decisions:
  - "Migration numbered 00004 (next sequential after existing 00003_vault_token_functions.sql)"
  - "vault_migrated_at is nullable TIMESTAMPTZ -- NULL means not yet verified as Vault-only"
  - "Token columns NOT dropped -- they store Vault secret name references needed for lookups"
  - "Health check overall status requires DB + Vault ok; external API degradation is tolerated"
  - "HEAD request with GET fallback for external API checks (some APIs reject HEAD)"
  - "Structured logger imported with try/except fallback to stdlib logging for portability"

patterns-established:
  - "Lazy migration pattern: read_token_with_lazy_migrate() tries Vault first, migrates plaintext on miss"
  - "Deep health pattern: critical checks (DB, Vault) determine overall status; external APIs are informational"
  - "API reachability check: HEAD with 3s timeout, GET fallback on 405, status < 500 means reachable"

requirements-completed: [SEC-01]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 6 Plan 4: Vault Token Hardening + Deep Health Endpoint Summary

**Vault lazy migration helper with health check probe, vault_migrated_at tracking column, and deep /api/health/ready endpoint checking DB, Vault, Linear, Slack, and Fathom API reachability**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T07:05:02Z
- **Completed:** 2026-02-25T07:07:18Z
- **Tasks:** 2
- **Files modified:** 3 (+ 1 created)

## Accomplishments
- Enhanced Vault service with `read_token_with_lazy_migrate()` for transparent plaintext-to-Vault migration on first read
- Added `check_vault_health()` probe that stores, reads, and deletes a test secret to verify Vault connectivity
- Created deep health endpoint at `/api/health/ready` with individual checks for DB, Vault, Linear API, Slack API, and Fathom API
- Added `vault_migrated_at` tracking column to `oauth_tokens` via migration 00004
- Audited all three integration services (linear_oauth, slack_oauth, fathom) and confirmed all token access already goes exclusively through Vault

## Task Commits

Each task was committed atomically:

1. **Task 1: Vault lazy migration and unified token helpers** - `8cf7b74` (feat)
2. **Task 2: Deep health endpoint with DB, Vault, and API checks** - `d5d7b78` (feat)

## Files Created/Modified
- `backend/src/services/vault.py` - Added `read_token_with_lazy_migrate()` and `check_vault_health()` functions
- `backend/src/routers/health.py` - Added `/api/health/ready` deep health endpoint with 5 checks (DB, Vault, Linear, Slack, Fathom)
- `supabase/migrations/00004_vault_lazy_migration.sql` - Adds `vault_migrated_at` column and documents token columns as Vault name references

## Decisions Made
- Migration numbered 00004 (sequential after existing 00003_vault_token_functions.sql) -- plan suggested 00005 but 00004 is correct
- Token columns (access_token, refresh_token) are NOT dropped because they store Vault secret name references needed for lookups
- vault_migrated_at is nullable TIMESTAMPTZ -- NULL means the row has not yet been verified as Vault-only
- Overall health status requires both DB and Vault to be ok; external API degradation is tolerated (system still "healthy")
- HEAD request used for external API checks with GET fallback on 405 (Method Not Allowed), since some APIs don't support HEAD
- Structured logger imported with try/except fallback to stdlib logging for environments where observability module may not be available

## Deviations from Plan

None - plan executed exactly as written. All integration services (linear_oauth, slack_oauth, fathom) were already confirmed Vault-only during the audit step, requiring no changes.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Vault functions rely on existing Supabase Vault infrastructure from Phase 2.

## Next Phase Readiness
- This is the final plan (06-04) of Phase 6. All Phase 6 objectives are complete.
- Vault token hardening ensures all credentials are encrypted at rest
- Deep health endpoint ready for deployment readiness probes and monitoring integration
- All integration services confirmed as Vault-only access

## Self-Check: PASSED

- [x] backend/src/services/vault.py exists with read_token_with_lazy_migrate and check_vault_health
- [x] backend/src/routers/health.py exists with /health/ready endpoint
- [x] supabase/migrations/00004_vault_lazy_migration.sql exists with vault_migrated_at column
- [x] Commit 8cf7b74 found (Task 1)
- [x] Commit d5d7b78 found (Task 2)

---
*Phase: 06-extension-and-hardening*
*Completed: 2026-02-25*
