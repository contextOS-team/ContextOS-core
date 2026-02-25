---
phase: 06-extension-and-hardening
verified: 2026-02-25T07:30:00Z
status: passed
score: 19/19 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Load extension in Chrome, navigate to a Linear ticket"
    expected: "Extension popup shows the detected ticket ID, loading state, and appropriate empty/error state"
    why_human: "Browser extension UI cannot be verified programmatically -- requires Chrome developer mode and actual navigation"
  - test: "Set SENTRY_DSN and trigger a Python exception in a backend route"
    expected: "Exception appears in Sentry dashboard with workspace_id, user_id, and endpoint tags"
    why_human: "Requires live Sentry project and DSN configuration to validate tag enrichment"
  - test: "Set NEXT_PUBLIC_SENTRY_DSN and throw a frontend error in the browser"
    expected: "Error appears in Sentry dashboard under the frontend project"
    why_human: "Requires live Sentry DSN and browser interaction"
  - test: "Set LAMINAR_API_KEY and call the LLMClient with a real prompt"
    expected: "Trace appears in Laminar dashboard with prompt, response, latency, token counts, workspace_id, and ticket_identifier"
    why_human: "Requires live Laminar API key and Google GenAI key for end-to-end verification"
  - test: "Make 61 requests in one minute to /api/webhooks/linear"
    expected: "Request 61 returns HTTP 429 with Retry-After header"
    why_human: "Rate limiting requires actual HTTP load testing to confirm sliding window behavior"
  - test: "Curl GET /api/health/ready with running backend"
    expected: "JSON response with status, checks.database, checks.vault, checks.linear_api, checks.slack_api, checks.fathom_api, and timestamp"
    why_human: "Requires a running backend with Supabase connection to verify the full probe chain"
---

# Phase 6: Extension and Hardening Verification Report

**Phase Goal:** Engineers get quick context from the browser toolbar, and the system is production-hardened with encrypted token storage, error tracking, and LLM observability
**Verified:** 2026-02-25T07:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Chrome extension icon appears in toolbar after loading unpacked extension | VERIFIED | `manifest.json` is Manifest V3, `action.default_icon` references icon-16/48/128.png, all icons present under `apps/web/public/icons/` |
| 2 | Popup shows context page for current Linear ticket | VERIFIED | `popup.tsx` (343 lines) renders 5 context sections (origin story, business requirements, technical decisions, related work, AI prompt) from backend response |
| 3 | Content script detects Linear ticket IDs with SPA navigation support | VERIFIED | `content.ts` uses `/linear\.app\/[^/]+\/issue\/([A-Z]+-\d+)/` regex, wraps `history.pushState`/`replaceState`, uses `MutationObserver` on document title, and listens for `popstate` |
| 4 | Extension handles missing context (404) and auth errors (401) gracefully | VERIFIED | `background.ts` maps 404 to `not_found`, 401/403 to `unauthorized`, network errors to `error`; popup renders distinct state for each |
| 5 | Unhandled backend exceptions captured in Sentry with workspace_id, user_id, endpoint tags | VERIFIED | `sentry.py` calls `sentry_sdk.set_tag("workspace_id")`, `set_tag("user_id")`, `set_user()`, `set_tag("endpoint")`; `SentryContextMiddleware` applies tags per-request |
| 6 | Frontend errors captured in Sentry with user context | VERIFIED | `global-error.tsx` calls `Sentry.captureException(error)` in `useEffect`; `sentry-init.tsx` calls `initSentry()` at module scope; `layout.tsx` renders `<SentryInit />` |
| 7 | Every HTTP request has a unique correlation ID in structured JSON logs | VERIFIED | `CorrelationIdMiddleware` generates UUID4 per request, sets `correlation_id_var` ContextVar, `_add_correlation_id` structlog processor binds it on every log line |
| 8 | Public endpoints (webhooks, OAuth callbacks) are rate-limited | VERIFIED | `RateLimitMiddleware` applies 120 req/min to `/api/webhooks/`, 60 req/min to `/api/linear/callback`, `/api/slack/callback`, `/api/fathom/`; returns 429 with `Retry-After` header |
| 9 | Every LLM synthesis call is traced in Laminar with prompt, response, latency, and token counts | VERIFIED | `LLMClient.generate()` decorated with `@observe(name="llm_generate")`; captures `prompt_token_count`, `candidates_token_count`, `total_token_count` from `usage_metadata`; records `latency_ms` via `time.monotonic()` |
| 10 | LLM traces tagged with workspace_id and ticket identifier | VERIFIED | `set_laminar_metadata()` called inside `generate()` with `workspace_id` and `ticket_identifier`; uses `Laminar.set_span_attributes()` |
| 11 | Laminar initialization is safe when API key is missing | VERIFIED | `init_laminar()` returns early with `logger.info("Laminar disabled (no API key)")` when `settings.LAMINAR_API_KEY` is falsy; init failure caught in `try/except` |
| 12 | All LLM calls go through single instrumented client | VERIFIED | `get_llm_client()` singleton factory; both `generate()` and `generate_context_page()` carry `@observe` decorators; pattern documented for Phase 4 consumption |
| 13 | All OAuth tokens (Linear, Slack) and API keys (Fathom) read from Supabase Vault | VERIFIED | `linear_oauth.py` imports `store_token`, `read_token`, `delete_token` from vault and calls them for all token operations; `slack_oauth.py` does the same; `fathom.py` uses `store_token`, `read_token`, `delete_token` for all API key operations |
| 14 | Lazy migration transparently moves plain-text tokens to Vault on first read | VERIFIED | `read_token_with_lazy_migrate()` in `vault.py` tries Vault first, calls `store_token()` if plaintext_value provided and Vault miss occurs |
| 15 | Migration adds vault_migrated_at tracking column | VERIFIED | `supabase/migrations/00004_vault_lazy_migration.sql` adds `vault_migrated_at TIMESTAMPTZ DEFAULT NULL` to `oauth_tokens` via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` |
| 16 | Deep health endpoint checks DB connectivity, Vault access, and external API reachability | VERIFIED | `GET /api/health/ready` in `health.py` calls `_check_db()`, `_check_vault()`, `_check_external_api()` for Linear, Slack, and Fathom; returns JSON with per-check `status` and `latency_ms` |
| 17 | DB or Vault failure makes /health/ready return "unhealthy" | VERIFIED | `critical_ok = db_result["status"] == "ok" and vault_result["status"] == "ok"`; external API degradation tolerated |
| 18 | Vault key naming follows unified format: {provider}_{workspace_id}_{token_type} | VERIFIED | `token_name()` generates `oauth_{provider}_{workspace_id}_{token_type}`; fathom uses `fathom_{workspace_id}_api_key` convention |
| 19 | Sentry init and Laminar init run before any request handler | VERIFIED | Both `init_sentry(settings)` and `init_laminar(settings)` called at module level in `main.py` before `app = FastAPI(...)` |

**Score:** 19/19 truths verified

---

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Notes |
|----------|-----------|--------------|--------|-------|
| `apps/web/public/manifest.json` | -- | 31 | VERIFIED | manifest_version: 3, service_worker, content_scripts, permissions all present |
| `apps/web/src/extension/popup.tsx` | 50 | 343 | VERIFIED | Full vanilla DOM popup with 5-section context display and all error states |
| `apps/web/src/extension/background.ts` | 30 | 200 | VERIFIED | Service worker with fetch to `/api/context/by-ticket/`, message handlers |
| `apps/web/src/extension/content.ts` | 20 | 77 | VERIFIED | Linear ticket regex, SPA navigation detection via pushState/popstate/MutationObserver |
| `backend/src/observability/sentry.py` | 40 | 122 | VERIFIED | init_sentry(), set_sentry_context(), SentryContextMiddleware all present |
| `backend/src/observability/logging.py` | 30 | 106 | VERIFIED | configure_logging(), get_logger(), correlation_id_var ContextVar, structlog setup |
| `backend/src/middleware/correlation.py` | 20 | 75 | VERIFIED | CorrelationIdMiddleware with X-Correlation-ID header and structured logging |
| `backend/src/middleware/rate_limit.py` | 30 | 145 | VERIFIED | Sliding window rate limiter with 4 path prefixes, 429 + Retry-After response |
| `apps/web/src/lib/sentry.ts` | 15 | 37 | VERIFIED | initSentry() with DSN guard, trace/replay sample rates, environment |
| `apps/web/src/app/global-error.tsx` | 15 | 68 | VERIFIED | "use client", Sentry.captureException(error) in useEffect, reset button |
| `backend/src/observability/laminar.py` | 30 | 68 | VERIFIED | init_laminar(), set_laminar_metadata(), observe re-export from lmnr |
| `backend/src/services/llm_client.py` | 40 | 199 | VERIFIED | LLMClient, LLMResponse dataclass, @observe decorators, get_llm_client() |
| `backend/src/services/vault.py` | 50 | 136 | VERIFIED | read_token_with_lazy_migrate(), check_vault_health() added alongside existing functions |
| `backend/src/routers/health.py` | 40 | 157 | VERIFIED | /api/health/ready with DB, Vault, Linear, Slack, Fathom checks; unauthenticated |
| `supabase/migrations/00004_vault_lazy_migration.sql` | -- | 25 | VERIFIED | vault_migrated_at column added; column comments document Vault name reference pattern |

---

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `backend/src/main.py` | `observability/sentry.py` | `init_sentry(settings)` at module level | WIRED | Line 26: `init_sentry(settings)` called before `app = FastAPI(...)` |
| `backend/src/main.py` | `middleware/correlation.py` | `app.add_middleware(CorrelationIdMiddleware)` | WIRED | Line 73: `app.add_middleware(CorrelationIdMiddleware)` |
| `backend/src/main.py` | `middleware/rate_limit.py` | `app.add_middleware(RateLimitMiddleware)` | WIRED | Line 75: `app.add_middleware(RateLimitMiddleware)` |
| `backend/src/main.py` | `observability/sentry.py` | `app.add_middleware(SentryContextMiddleware)` | WIRED | Line 63: `app.add_middleware(SentryContextMiddleware)` |
| `backend/src/main.py` | `observability/laminar.py` | `init_laminar(settings)` at module level | WIRED | Line 29: `init_laminar(settings)` called at module scope |
| `apps/web/src/app/layout.tsx` | `apps/web/src/lib/sentry-init.tsx` | `<SentryInit />` component in RootLayout | WIRED | Line 2: `import { SentryInit }`, Line 19: `<SentryInit />` rendered |
| `apps/web/src/lib/sentry-init.tsx` | `apps/web/src/lib/sentry.ts` | `initSentry()` called at module scope | WIRED | `import { initSentry }` + `initSentry()` called before export |
| `backend/src/services/llm_client.py` | `observability/laminar.py` | `@observe(name=...)` on generate() and generate_context_page() | WIRED | Lines 70, 130: `@observe(name="llm_generate")` and `@observe(name="llm_generate_with_context")` |
| `backend/src/services/linear_oauth.py` | `backend/src/services/vault.py` | `store_token`, `read_token`, `delete_token` | WIRED | Lines 141, 145, 283, 289, 323, 326, 378, 417, 418 all use vault functions |
| `backend/src/services/slack_oauth.py` | `backend/src/services/vault.py` | `store_token`, `read_token`, `delete_token` | WIRED | Lines 149, 238, 274 use vault functions |
| `backend/src/services/fathom.py` | `backend/src/services/vault.py` | `store_token`, `read_token`, `delete_token` | WIRED | Lines 92, 93, 135, 136, 168, 169 use vault functions |
| `backend/src/routers/health.py` | `backend/src/services/vault.py` | `check_vault_health()` in /api/health/ready | WIRED | Line 19: `from src.services.vault import check_vault_health`; called at line 69 |
| `apps/web/src/extension/content.ts` | `linear.app ticket page` | URL regex `/linear\.app\/[^/]+\/issue\/([A-Z]+-\d+)/` | WIRED | Line 9: `const LINEAR_TICKET_RE = /linear\.app\/[^/]+\/issue\/([A-Z]+-\d+)/` |
| `apps/web/src/extension/background.ts` | `backend API /api/context` | `fetch(url, { ... Authorization: Bearer ${token} })` | WIRED | Line 71: `fetch(url, { headers: { Authorization: \`Bearer ${token}\` } })` to `/api/context/by-ticket/${identifier}` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| EXT-01 | 06-01 | Chrome extension displays context page for current Linear ticket from browser toolbar | SATISFIED | Extension manifest, popup, content script, and background service worker all implemented and wired; owned by Bekbol |
| SEC-01 | 06-04 | All OAuth tokens (Linear, Slack, Fathom) stored in Supabase Vault, never in plain-text columns | SATISFIED | linear_oauth.py, slack_oauth.py, fathom.py all import and use vault.store_token/read_token/delete_token exclusively; lazy migration helper added for edge cases |
| SEC-02 | 06-02 | Sentry SDK integrated in FastAPI backend with error context (workspace_id, user_id, endpoint) | SATISFIED | init_sentry() in main.py, SentryContextMiddleware tags all requests, set_sentry_context() sets user + tags; frontend global-error.tsx captures client errors |
| SEC-03 | 06-03 | Laminar SDK integrated for LLM call tracing (prompts, responses, latency, cost) | SATISFIED | init_laminar() in main.py, @observe on both LLMClient methods, LLMResponse captures text/tokens/latency/model, set_laminar_metadata() tags workspace_id and ticket_identifier |

All 4 Phase 6 requirement IDs (EXT-01, SEC-01, SEC-02, SEC-03) are accounted for. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/services/llm_client.py` | 142 | "this is a working placeholder" in docstring of `generate_context_page()` | Info | The method is fully implemented (builds prompt, calls generate(), returns LLMResponse). The comment refers to Phase 4 refining the prompt template, not to a stub implementation. Not a blocker. |
| `apps/web/src/extension/popup.tsx` | 108, 120 | `placeholder:` attribute values | Info | These are HTML input placeholder attributes for settings form fields, not code stubs. Not a blocker. |

No blocker or warning anti-patterns found.

---

### Human Verification Required

The following items require runtime or browser validation that cannot be confirmed programmatically:

#### 1. Chrome Extension End-to-End

**Test:** Load the extension from `apps/web/public/` as unpacked in Chrome developer mode. Navigate to a Linear ticket URL. Click the extension icon.
**Expected:** Popup renders header with ticket ID, loading spinner, then either context sections (if context exists) or "No context page yet" empty state.
**Why human:** Chrome extension runtime behavior cannot be verified without a real browser session.

#### 2. Sentry Backend Tag Enrichment

**Test:** Configure `SENTRY_DSN` in `.env`, start backend, hit an unauthenticated route with a valid JWT to trigger an error.
**Expected:** Sentry receives the error event tagged with `workspace_id`, `user_id`, and `endpoint`.
**Why human:** Requires a live Sentry project and DSN to confirm tag delivery.

#### 3. Sentry Frontend Error Capture

**Test:** Configure `NEXT_PUBLIC_SENTRY_DSN`, run `next dev`, trigger a JavaScript error in the browser console or via a component throw.
**Expected:** Error appears in Sentry dashboard under the frontend project.
**Why human:** Requires live DSN and browser interaction.

#### 4. Laminar LLM Trace Visibility

**Test:** Set `LAMINAR_API_KEY` and `GOOGLE_GENAI_API_KEY`, call `get_llm_client().generate("test prompt")`.
**Expected:** Trace appears in Laminar dashboard with prompt text, response text, latency_ms, prompt_tokens, completion_tokens, and workspace_id/ticket_identifier metadata.
**Why human:** Requires live API keys and Laminar project.

#### 5. Rate Limiting Enforcement

**Test:** Send 61 POST requests in under 60 seconds to `/api/webhooks/linear`.
**Expected:** First 120 succeed (2/min per IP for webhooks); any request exceeding the limit returns HTTP 429 with `Retry-After` header.
**Why human:** Sliding window rate limiting requires actual HTTP load test to confirm timing behavior.

#### 6. Deep Health Endpoint Runtime

**Test:** Start backend with valid Supabase connection. `curl http://localhost:8000/api/health/ready`.
**Expected:** JSON response with `"status": "healthy"` (or `"unhealthy"` if Vault unreachable), individual check objects for `database`, `vault`, `linear_api`, `slack_api`, `fathom_api`, each with `status` and `latency_ms`.
**Why human:** Requires running backend with Supabase Vault accessible.

---

### Notation on Migration File Number

The 06-04-PLAN.md specified migration file as `00005_vault_lazy_migration.sql`, but the actual file is `supabase/migrations/00004_vault_lazy_migration.sql`. This deviation is correct and documented in the SUMMARY: 00004 is the sequential next number after `00003_vault_token_functions.sql`. The PLAN contained an incorrect estimate; the implementation is correct.

---

### Gaps Summary

No gaps. All 19 observable truths are verified. All 15 artifacts pass the three-level check (exists, substantive, wired). All 14 key links are confirmed wired in the codebase. All 4 requirement IDs (EXT-01, SEC-01, SEC-02, SEC-03) are satisfied. The 6 human verification items are runtime checks that cannot be confirmed without live credentials and a running system.

---

_Verified: 2026-02-25T07:30:00Z_
_Verifier: Claude (gsd-verifier)_
