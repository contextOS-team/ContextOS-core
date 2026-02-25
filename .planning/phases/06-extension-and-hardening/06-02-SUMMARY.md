---
phase: 06-extension-and-hardening
plan: 02
subsystem: observability
tags: [sentry, structlog, rate-limiting, correlation-id, fastapi, nextjs, error-tracking]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: FastAPI app skeleton, config, auth middleware
provides:
  - Sentry error tracking for backend (FastAPI) and frontend (Next.js)
  - Structured JSON logging with correlation ID propagation
  - Rate limiting middleware for public endpoints
  - Global error boundary for frontend
  - Telegram alerting configuration (via Sentry webhook)
affects: [06-03-laminar, 06-04-vault]

# Tech tracking
tech-stack:
  added: [sentry-sdk, structlog, "@sentry/nextjs"]
  patterns: [structured-logging-with-contextvars, sliding-window-rate-limiting, middleware-composition-order]

key-files:
  created:
    - backend/src/observability/__init__.py
    - backend/src/observability/sentry.py
    - backend/src/observability/logging.py
    - backend/src/middleware/__init__.py
    - backend/src/middleware/correlation.py
    - backend/src/middleware/rate_limit.py
    - apps/web/src/lib/sentry.ts
    - apps/web/src/lib/sentry-init.tsx
    - apps/web/src/app/global-error.tsx
  modified:
    - backend/src/main.py
    - backend/src/config.py
    - backend/pyproject.toml
    - apps/web/src/app/layout.tsx
    - apps/web/next.config.ts
    - apps/web/package.json
    - .env.example

key-decisions:
  - "SqlalchemyIntegration imported lazily inside init_sentry() to avoid import-time failure when sqlalchemy is not installed"
  - "SentryInit client component wraps Sentry.init() call since layout.tsx is a server component"
  - "In-memory sliding window rate limiter (no Redis) suitable for single-instance MVP deployment"
  - "Middleware order: RateLimit -> Correlation -> CORS -> SentryContext (bottom = first executed)"
  - "Structlog configured with stdlib ProcessorFormatter for unified log output"
  - "Telegram alerting is Sentry webhook config (no custom code) -- documented in user_setup"

patterns-established:
  - "Observability package at backend/src/observability/ for Sentry, logging, and future Laminar"
  - "Middleware package at backend/src/middleware/ for cross-cutting concerns"
  - "ContextVar-based correlation ID propagation for structured log binding"
  - "SentryInit client component pattern for initializing client-side SDKs from server layout"

requirements-completed: [SEC-02]

# Metrics
duration: 8min
completed: 2026-02-25
---

# Phase 6 Plan 2: Sentry + Structured Logging + Rate Limiting Summary

**Sentry error tracking across backend (FastAPI) and frontend (Next.js 15), structlog JSON logging with correlation IDs, in-memory rate limiting on public endpoints, and Telegram alert configuration**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-25T06:52:23Z
- **Completed:** 2026-02-25T07:00:48Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- Sentry SDK integrated in both backend (FastAPI + SQLAlchemy integrations) and frontend (@sentry/nextjs v9) with environment-aware sample rates
- Structured JSON logging via structlog with automatic correlation ID binding from CorrelationIdMiddleware
- Rate limiting middleware protects webhooks, OAuth callbacks, and Fathom endpoints (120/min for webhooks, 60/min for others)
- Global error boundary captures unhandled frontend errors and reports to Sentry
- SentryContextMiddleware auto-tags every request with user_id, workspace_id, and endpoint

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend Sentry + structured logging + correlation ID + rate limiting** - `7d7d16b` (feat)
2. **Task 2: Frontend Sentry integration with Next.js** - `77fc4b0` (feat)

## Files Created/Modified
- `backend/src/observability/sentry.py` - Sentry SDK init, context tagging, SentryContextMiddleware
- `backend/src/observability/logging.py` - Structlog config with JSON/console renderers, correlation ID processor
- `backend/src/middleware/correlation.py` - CorrelationIdMiddleware with X-Correlation-ID header propagation
- `backend/src/middleware/rate_limit.py` - In-memory sliding window rate limiter for public endpoints
- `backend/src/main.py` - Sentry/logging init before app creation, middleware registration
- `backend/src/config.py` - Added TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID settings
- `backend/pyproject.toml` - Added structlog dependency
- `apps/web/src/lib/sentry.ts` - Client-side Sentry init function
- `apps/web/src/lib/sentry-init.tsx` - Client component for Sentry initialization in server layout
- `apps/web/src/app/global-error.tsx` - Next.js global error boundary reporting to Sentry
- `apps/web/src/app/layout.tsx` - SentryInit component added to root layout
- `apps/web/next.config.ts` - Wrapped with withSentryConfig
- `apps/web/package.json` - Added @sentry/nextjs dependency
- `.env.example` - Added TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID entries

## Decisions Made
- SqlalchemyIntegration imported lazily inside init_sentry() to avoid import-time failure when sqlalchemy is not installed (system Python vs. venv)
- Created SentryInit client component since layout.tsx is a server component and Sentry.init() needs to run on the client
- Middleware order: RateLimit (first to reject) -> Correlation (assign ID) -> CORS -> SentryContext (tag scope)
- Rate limits: 120/min for webhooks (higher for legitimate bursts), 60/min for OAuth callbacks and Fathom endpoints
- Structlog uses ProcessorFormatter to integrate with stdlib logging handlers
- Telegram alerting implemented as Sentry dashboard webhook configuration (no custom bot code needed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lazy import for SqlalchemyIntegration**
- **Found during:** Task 1 (Sentry SDK initialization)
- **Issue:** `from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration` fails at import time if sqlalchemy is not installed
- **Fix:** Moved import inside init_sentry() with try/except fallback
- **Files modified:** backend/src/observability/sentry.py
- **Verification:** Import succeeds in environments without sqlalchemy
- **Committed in:** 7d7d16b (Task 1 commit)

**2. [Rule 3 - Blocking] SentryInit client component for server layout**
- **Found during:** Task 2 (Frontend Sentry integration)
- **Issue:** layout.tsx is a server component but Sentry.init() needs to run on the client side
- **Fix:** Created SentryInit client component that calls initSentry() at module scope, included in layout
- **Files modified:** apps/web/src/lib/sentry-init.tsx, apps/web/src/app/layout.tsx
- **Verification:** TypeScript type check passes, Sentry init is client-only
- **Committed in:** 77fc4b0 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required

External services require manual configuration:

### Sentry
1. Create a Sentry project for the backend (Python/FastAPI)
2. Create a Sentry project for the frontend (Next.js) -- or use the same project
3. Copy DSN from Sentry Dashboard -> Settings -> Client Keys (DSN)
4. Set `SENTRY_DSN` (backend) and `NEXT_PUBLIC_SENTRY_DSN` (frontend) in .env

### Telegram Alerting
1. Create a Telegram bot via @BotFather, copy the token
2. Add the bot to the team chat
3. Use `https://api.telegram.org/bot<TOKEN>/getUpdates` to find the chat_id
4. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in .env
5. In Sentry Dashboard -> Settings -> Integrations -> Webhooks, create a webhook pointing to: `https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text={message}`
6. Create a Sentry Alert Rule to trigger on critical errors

## Next Phase Readiness
- Observability package (`backend/src/observability/`) ready for Laminar integration (plan 06-03)
- Middleware package (`backend/src/middleware/`) established for future cross-cutting concerns
- Structured logging infrastructure ready for all backend modules to use via `get_logger()`

---
*Phase: 06-extension-and-hardening*
*Completed: 2026-02-25*
