# Phase 6: Extension and Hardening - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Production-harden the ContextOS system: encrypt all OAuth tokens and API keys in Supabase Vault, add Sentry error tracking with performance monitoring across frontend and backend, integrate Laminar for full LLM observability, set up structured logging, deep health checks, rate limiting on public endpoints, and Telegram alerting for critical errors. Chrome extension (06-01, Bekbol) is a separate plan not covered here.

</domain>

<decisions>
## Implementation Decisions

### Error Tracking (Sentry)
- Capture everything: all unhandled exceptions + explicit captures in critical paths (OAuth, webhooks, sync)
- Both frontend (Next.js) and backend (FastAPI) get Sentry SDKs
- Performance monitoring enabled — track request durations, slow queries, bottlenecks
- Every event tagged with: workspace_id, user_id, endpoint
- Sentry transaction tracing on for both frontend and backend

### LLM Observability (Laminar)
- Full trace logging: input prompt, model response, latency, token counts, estimated cost
- Instrument at the client level so ALL LLM calls are automatically traced (not just context generation)
- Each trace tagged with workspace_id and Linear ticket context for debugging
- Use Laminar's default dashboard UI — no custom observability views in ContextOS
- Alerting stays in Sentry, not Laminar — Laminar is for observability/dashboards only

### Vault Token Storage
- Lazy migration: when a token is read and not yet in Vault, migrate it on the spot
- Drop plain-text token columns after migration period (via DB migration)
- Unified Vault pattern for all providers: key format = {provider}_{workspace_id}_{token_type}
- All secrets go to Vault: OAuth access/refresh tokens AND API keys (Fathom, etc.)
- Same read/write helpers across all integrations

### Alerting & Notifications
- Sentry webhook to Telegram bot — formatted error alerts posted to team Telegram chat
- Only critical + high severity errors trigger Telegram alerts (reduce noise)
- No Laminar alerting — LLM errors surface through Sentry

### Structured Logging
- Replace basic logging with structured JSON logs
- Each request gets a correlation ID for tracing across request lifecycle
- JSON format for machine-parseable logs in production

### Health Checks
- Deep health endpoint at /health/ready
- Checks: DB connectivity, Vault access, external API reachability
- Useful for deployment readiness probes

### Rate Limiting
- Rate limit public endpoints: OAuth callbacks, webhook receivers, API endpoints
- Prevent abuse without affecting normal usage patterns

### Claude's Discretion
- Exact Sentry sample rates for performance monitoring
- Rate limiting implementation (middleware vs decorator, exact limits)
- Correlation ID generation strategy (UUID vs snowflake)
- Telegram bot message formatting
- Exact Laminar SDK integration pattern
- Structured logging library choice (structlog vs python-json-logger)

</decisions>

<specifics>
## Specific Ideas

- Team uses Telegram for communication — no Slack channel for alerts
- Vault key naming follows existing pattern from Phase 2: fathom_{workspace_id}_api_key
- Sentry + Laminar are the only observability tools — no additional analytics service needed for now
- Linear OAuth already uses Vault (Phase 2 decision) — extend that pattern uniformly

</specifics>

<deferred>
## Deferred Ideas

- Usage analytics (context pages generated, active workspaces) — future phase
- Custom LLM observability dashboard in ContextOS — not needed with Laminar UI
- Laminar-specific alerting (cost spikes, latency) — evaluate after usage patterns emerge

</deferred>

---

*Phase: 06-extension-and-hardening*
*Context gathered: 2026-02-25*
