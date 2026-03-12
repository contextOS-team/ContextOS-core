---
phase: 29-codebase-hardening-security-bug-fixes-architecture-and-ui-ux-polish
plan: 01
subsystem: security, api
tags: [redis, rate-limiting, jql-injection, oauth, hmac, api-keys, salt]

requires:
  - phase: 20-settings
    provides: API key model and CRUD
  - phase: 10-sync-engine
    provides: Redis stream workers

provides:
  - JQL injection prevention via regex allowlist
  - Redis-backed sliding window rate limiter with fail-open
  - Dedicated OAUTH_STATE_SECRET for OAuth state signing
  - Per-key salted API key hashing
  - Dynamic Redis consumer names for horizontal scaling
  - Deterministic workspace membership query

affects: [api-keys, rate-limiting, oauth, workers]

tech-stack:
  added: [redis.asyncio sorted sets for rate limiting]
  patterns: [fail-open on Redis errors, per-key salt hashing, regex allowlist validation]

key-files:
  created:
    - supabase/migrations/00022_api_key_salt.sql
  modified:
    - backend/src/routers/context.py
    - backend/src/middleware/rate_limit.py
    - backend/src/services/oauth_common.py
    - backend/src/config.py
    - backend/src/services/embedding_worker.py
    - backend/src/services/code_index_worker.py
    - backend/src/dependencies.py
    - backend/src/services/api_key.py
    - backend/src/models/api_key.py
    - backend/src/routers/telegram.py

key-decisions:
  - "Redis rate limiter fails open on Redis errors -- never blocks API due to Redis outage"
  - "OAUTH_STATE_SECRET falls back to provider client_secret for backward compatibility"
  - "Legacy API keys with NULL salt verify via unsalted hash path -- no migration needed for existing keys"
  - "TICKET_ID_PATTERN uses strict ^[A-Z][A-Z0-9]+-\\d+$ -- rejects all non-KEY-123 formats"
  - "X-Forwarded-For trusted only from loopback/private IPs via ipaddress module"

patterns-established:
  - "Regex allowlist for untrusted input before string interpolation"
  - "Fail-open pattern for non-critical middleware backed by external services"
  - "Per-key salt with backward-compatible verification for gradual migration"

requirements-completed: [SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, REL-01, REL-02]

duration: 5min
completed: 2026-03-12
---

# Phase 29 Plan 01: Backend Security Hardening Summary

**JQL injection prevention, Redis rate limiter with fail-open, OAUTH_STATE_SECRET signing, per-key salted API key hashing, dynamic Redis consumer names, and workspace query safety**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-11T20:02:49Z
- **Completed:** 2026-03-11T20:08:24Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Fixed JQL injection vulnerability with TICKET_ID_PATTERN regex allowlist at both interpolation sites
- Replaced in-memory rate limiter with Redis sorted sets, fail-open on Redis errors
- Added dedicated OAUTH_STATE_SECRET with backward-compatible fallback to provider secrets
- New API keys hashed with per-key random salt (os.urandom), legacy keys still verify unsalted
- Dynamic consumer names using hostname+PID enable horizontal worker scaling
- Workspace membership query now deterministic with ORDER BY + LIMIT 1
- Audited Telegram bot_token logging -- confirmed safe, added security comment

## Task Commits

Each task was committed atomically:

1. **Task 1: JQL injection fix, IP spoofing prevention, OAuth state signing, consumer names, workspace safety** - `13b650d` (feat) -- committed in prior execution session
2. **Task 2: Redis rate limiter migration and API key salt** - `405fc91` (feat)

## Files Created/Modified

- `backend/src/routers/context.py` - TICKET_ID_PATTERN regex and _validate_ticket_identifier at both JQL sites
- `backend/src/middleware/rate_limit.py` - Full rewrite: Redis sorted sets, fail-open, IP spoofing protection
- `backend/src/services/oauth_common.py` - _get_signing_secret with OAUTH_STATE_SECRET fallback
- `backend/src/config.py` - Added OAUTH_STATE_SECRET setting
- `backend/src/services/embedding_worker.py` - Dynamic CONSUMER_NAME with hostname+PID
- `backend/src/services/code_index_worker.py` - Dynamic CONSUMER_NAME with hostname+PID
- `backend/src/dependencies.py` - ORDER BY created_at ASC + LIMIT 1 on workspace query
- `backend/src/services/api_key.py` - Per-key salt generation, _hash_key helper, verify_api_key function
- `backend/src/models/api_key.py` - Added salt field
- `backend/src/routers/telegram.py` - Security comment on bot_token
- `supabase/migrations/00022_api_key_salt.sql` - ADD COLUMN salt to api_keys

## Decisions Made

- Redis rate limiter fails open on Redis errors -- prevents Redis outages from blocking all API requests
- OAUTH_STATE_SECRET falls back to provider client_secret for zero-downtime migration
- Legacy API keys with NULL salt use unsalted hash path -- no data migration needed
- TICKET_ID_PATTERN strict allowlist (^[A-Z][A-Z0-9]+-\d+$) over blacklist approach
- Used ipaddress.ip_address for proxy detection (handles both IPv4 and IPv6 loopback/private)

## Deviations from Plan

None - plan executed exactly as written. Task 1 changes were already committed from a prior execution session (13b650d).

## Issues Encountered

- Task 1 changes were already present in commit 13b650d from a prior execution session. Verified all changes exist and skipped re-committing to avoid duplicates.

## User Setup Required

**Environment variable to add:**
- `OAUTH_STATE_SECRET` - Set a random secret string for OAuth state signing. If unset, falls back to provider client secrets (backward compatible).

## Next Phase Readiness

- All 8 security/reliability concerns (SEC-01 through SEC-06, REL-01, REL-02) are addressed
- Redis rate limiter ready for production (requires REDIS_URL already in config)
- API key salt migration (00022) ready to apply

---
*Phase: 29-codebase-hardening-security-bug-fixes-architecture-and-ui-ux-polish*
*Completed: 2026-03-12*
