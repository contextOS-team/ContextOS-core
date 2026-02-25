# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** Phase 7 - GitHub Integration

## Current Position

Phase: 7 of 7 (GitHub Integration)
Plan: 1 of 3 in current phase
Status: Executing Phase 07 -- Plan 01 complete
Last activity: 2026-02-25 -- Completed 07-01: GitHub App OAuth

Progress: [=========.] 60%

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 7min
- Total execution time: 1.17 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3 | 12min | 4min |
| 2. Linear Integration | 3 | 26min | 8.7min |
| 3. Slack/Meeting Ingestion | 3 | 24min | 8min |
| 7. GitHub Integration | 1 | 8min | 8min |

**Recent Trend:**
- Last 5 plans: 02-03 (17min), 03-01 (6min), 03-02 (8min), 03-03 (10min), 07-01 (8min)
- Trend: Consistent 8min for integration OAuth plans

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
- [02-03]: Module-level config import (import src.config) instead of from-import for reliable test patching across test ordering
- [02-03]: Background task delegation for webhook event processing to ensure fast 200 response to Linear
- [02-03]: Webhook service creates its own session via async_session() for background processing isolation
- [02-03]: Comment embedding queued for the comment source_type, not re-embedding the parent ticket
- [03-01]: Slack bot tokens do not expire and have no refresh tokens -- simpler than Linear OAuth
- [03-01]: Module-level config import (import src.config) for slack router matches webhook pattern
- [03-01]: Background task delegation for Slack event processing ensures fast 200 response
- [03-01]: Channel monitoring defaults to all channels if no selected_channels configured
- [03-01]: Aliased sqlalchemy.text as sa_text to avoid SQLModel/Field namespace collision
- [03-02]: Slack conversations.list uses cursor pagination with limit=1000 per page
- [03-02]: Channel list cached in workspace_integrations.config JSONB under available_channels
- [03-02]: GET /channels reads from cache; POST /channels/refresh hits Slack API fresh
- [03-02]: Fathom API key stored in Vault, key format: fathom_{workspace_id}_api_key
- [03-02]: Fathom API base URL configurable via FATHOM_API_BASE_URL (api.fathom.video does not resolve)
- [03-02]: Fathom dedup uses fathom_id in raw_data JSONB (no dedicated DB column)
- [03-02]: Processing transcripts skipped and retried on next poll cycle
- [03-02]: Poll endpoint runs in BackgroundTasks, returns 202 immediately
- [03-03]: OAuth upsert must query WITHOUT deleted_at filter to reuse soft-deleted rows on reconnect
- [03-03]: All DB timestamp columns use datetime.utcnow() (naive UTC) -- never datetime.now(timezone.utc)
- [03-03]: Fathom API base URL is api.fathom.ai/external/v1, auth header is X-Api-Key, endpoint is /meetings
- [07-01]: PyJWT with RS256 for GitHub App JWT signing (already a project dependency, no new library needed)
- [07-01]: Installation access tokens stored in Vault with 1-hour expiry; refreshed on demand via App JWT
- [07-01]: GitHub App installation flow (not standard OAuth2) per CONTEXT.md decision
- [07-01]: HMAC-SHA256 signed state uses GITHUB_CLIENT_SECRET (same pattern as Linear/Slack)
- [07-01]: installation_id stored in OAuthToken.metadata_ JSONB for token refresh
- [07-01]: 'github' added to provider check constraints via migration ALTER

### Pending Todos

None yet.

### Roadmap Evolution

- Phase 7 added: GitHub Integration

### Blockers/Concerns

- Linear OAuth app registration required before Phase 2
- Slack app registration required before Phase 3
- Fathom API access required before Phase 3
- Gemini API key required before Phase 4
- GitHub OAuth app registration required before Phase 7

## Session Continuity

Last session: 2026-02-25
Stopped at: Completed 07-01-PLAN.md
Resume file: .planning/phases/07-github-integration/07-02-PLAN.md
