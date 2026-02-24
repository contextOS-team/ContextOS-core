# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** Phase 2 - Linear Integration

## Current Position

Phase: 2 of 6 (Linear Integration)
Plan: 2 of 3 in current phase
Status: Plan 02-02 complete, continuing to 02-03
Last activity: 2026-02-24 -- Completed 02-02: Linear ticket sync with GraphQL and pagination

Progress: [=====.....] 33%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 4min
- Total execution time: 0.35 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3 | 12min | 4min |
| 2. Linear Integration | 2 | 9min | 4.5min |

**Recent Trend:**
- Last 5 plans: 01-02 (4min), 01-03 (4min), 02-01 (5min), 02-02 (4min)
- Trend: Consistent

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 6 phases derived from 39 requirements across 3 team members
- [Roadmap]: DASH-01 (auth pages) pulled into Phase 1 so Bekbol works in parallel with Daulet from day one
- [Roadmap]: DASH-04 (integration setup) pulled into Phase 3 so Bekbol delivers UI alongside Slack/Fathom backend
- [Roadmap]: Phases 2+3 can overlap; Phase 4 starts after Phase 2 (Linear data needed for synthesis)
- [01-01]: Used moddatetime extension for updated_at triggers instead of custom function
- [01-01]: Switched build system from setuptools to hatchling for modern Python packaging
- [01-01]: Health endpoint checks DB connectivity via SELECT 1 query
- [01-01]: Codegen target deferred to Phase 2 as Makefile placeholder
- [01-01]: match_embeddings function filters out soft-deleted embeddings
- [01-02]: Added audience="authenticated" to JWT decode for Supabase aud claim
- [01-02]: Test settings patching must override get_settings in both src.config and src.auth
- [01-02]: Repository layer deferred to Phase 2+; services query DB directly for now
- [01-03]: Dashboard uses /dashboard path instead of (dashboard) route group for cleaner URLs
- [01-03]: SignOutButton extracted as client component to keep dashboard layout as server component
- [01-03]: Magic link emailRedirectTo falls back to window.location.origin when env var is unset
- [02-01]: Vault secrets API (vault.create_secret/decrypted_secrets) used over raw pgsodium for simpler token storage
- [02-01]: State parameter uses HMAC-SHA256 signing with LINEAR_CLIENT_SECRET for CSRF protection
- [02-01]: Token values stored in Vault; DB columns store Vault secret name references, not actual tokens
- [02-01]: Advisory lock key uses hashtext of workspace_id string for deterministic locking
- [02-02]: Raw httpx GraphQL client with bare token auth (not Bearer) per Linear API spec
- [02-02]: Exponential backoff on 429: 1s initial, 2x multiplier, max 3 retries
- [02-02]: Sync runs as FastAPI BackgroundTasks, progress stored in workspace_integrations.config JSONB
- [02-02]: Embedding generation decoupled as stub with correct signatures for Phase 4

### Pending Todos

None yet.

### Blockers/Concerns

- Linear OAuth app registration required before Phase 2
- Slack app registration required before Phase 3
- Fathom API access required before Phase 3
- Gemini API key required before Phase 4

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 02-02-PLAN.md (Linear ticket sync with GraphQL)
Resume file: .planning/phases/02-linear-integration/02-02-SUMMARY.md
