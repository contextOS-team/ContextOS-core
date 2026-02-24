# Phase 2: Linear Integration - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

The system has live Linear ticket data flowing in -- OAuth connected, initial sync complete, webhooks updating tickets in real-time with reliable token refresh. This phase delivers the data pipeline only. Context generation (Phase 4) and delivery channels (Phase 5) consume this data but are not part of this phase.

</domain>

<decisions>
## Implementation Decisions

### OAuth connection flow
- User can initiate Linear connection from both onboarding (post-first-login prompt) AND a settings/integrations page
- After OAuth redirect back from Linear, show a brief "Connected!" success banner/toast, then auto-redirect to the dashboard or integrations page
- Disconnect is supported: revokes tokens but keeps existing ticket data intact. Reconnecting re-links and resumes syncing.
- OAuth tokens stored in Supabase Vault (pgsodium encryption) from day one -- no plain-text token columns, no Phase 6 migration needed

### Sync scope & behavior
- User selects which Linear teams to sync after connecting (team picker UI). Can change selection later in settings.
- Initial sync pulls all tickets except Cancelled state. Done/Completed tickets are included for historical context linking.
- Embedding generation is decoupled from ticket sync: tickets are stored first (fast), embeddings queued as background jobs. Tickets are searchable by metadata immediately; semantic search comes online gradually.

### Webhook processing
- Re-embed only on content changes (title, description, comments). State/assignee/label changes update metadata but skip embedding regeneration.
- Phase 2 keeps data fresh only -- no Phase 4 context page triggers. Phase 4 will hook into data change events when it's built.
- Webhook events for tickets outside synced teams: store the raw data (in case user adds that team later) but don't generate embeddings
- Full idempotency via webhook delivery ID tracking -- duplicate events are detected and skipped. Linear retries are safe.
- Webhook payloads verified via HMAC-SHA256 with webhook secret using raw request bytes

### Token lifecycle
- Proactive token refresh: background job refreshes tokens before the 24-hour expiry (e.g., at 22 hours). User never encounters an expired token.
- Race condition prevention: database advisory lock (or equivalent) ensures only one refresh happens when concurrent requests discover an expired token
- Failed refresh handling: mark integration as disconnected in the UI with a "Reconnect" button

### API & infrastructure
- Use Linear's GraphQL API via raw httpx (no SDK). Linear has no official Python SDK; community packages are too young/unmaintained. httpx is already a project dependency.
- Cursor-based pagination with exponential backoff on 429 rate limit responses for bulk sync
- Sync selected ticket fields: identifier, title, description, state, assignee, labels, project, comments

### Claude's Discretion
- Post-OAuth error handling UX (redirect back with error vs dedicated error page)
- Sync progress feedback approach (inline progress indicator vs background notification)
- Token refresh failure notification strategy (UI-only vs email)
- Exact backoff timing and retry parameters
- Background job mechanism for proactive token refresh (FastAPI background tasks, APScheduler, etc.)

</decisions>

<specifics>
## Specific Ideas

- Linear SDK research confirmed: official SDK is TypeScript-only. Community Python packages (linear-api v0.2.0, linear-py) are too immature. Raw httpx + GraphQL gives full control.
- The "store but don't embed" pattern for out-of-scope team events avoids re-syncing if the user later adds that team
- Decoupled embeddings means the sync completion feedback can be fast even for large workspaces

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 02-linear-integration*
*Context gathered: 2026-02-24*
