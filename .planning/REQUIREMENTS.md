# Requirements: ContextOS

**Defined:** 2026-02-24
**Core Value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Scope:** Daulet Ashikbayev's tasks only. Dulat (AI/ML, linking, synthesis) and Bekbol (dashboard, Chrome extension) have separate scopes.

## v1 Requirements

### Foundation

- [ ] **FOUND-01**: Database schema with all core tables (workspaces, users, oauth_tokens, linear_tickets, slack_messages, context_pages, embeddings), pgvector (768 dims), RLS policies via Supabase migrations
- [ ] **FOUND-02**: User can sign up with email and password via Supabase Auth
- [ ] **FOUND-03**: User can sign in with magic link via Supabase Auth
- [ ] **FOUND-04**: User session persists across browser refresh
- [ ] **FOUND-05**: API routes are protected (unauthenticated requests return 401)
- [ ] **FOUND-06**: Workspace creation on first login with 1:1:1 tenancy model (one workspace = one Linear org + one Slack workspace)
- [ ] **FOUND-07**: Update pyproject.toml dependencies: replace anthropic with google-genai, remove llama-index packages, remove celery[redis]; add slack-bolt, keep redis for caching

### Linear Integration

- [ ] **LIN-01**: User can connect Linear workspace via OAuth2 flow handled by Python backend (redirect → callback → store tokens in Supabase Vault)
- [ ] **LIN-02**: On first connect, system pulls all active tickets for selected team(s) with identifier, title, description, state, assignee, labels, project, comments; generates embeddings
- [ ] **LIN-03**: Linear webhooks received at POST /api/webhooks/linear and verified via HMAC-SHA256 with webhook secret using raw request bytes
- [ ] **LIN-04**: Webhook events (issue create/update, comment create, assignment change) update local linear_tickets data and trigger context page regeneration via FastAPI background tasks
- [ ] **LIN-05**: OAuth token refresh handles Linear's mandatory 24-hour expiry automatically with race condition prevention

### Slack Integration

- [ ] **SLCK-01**: User can connect Slack workspace via OAuth2 V2 flow with both bot token and user token scopes, handled by Python backend
- [ ] **SLCK-02**: System ingests real-time Slack messages from user-selected channels via Events API (slack-bolt)
- [ ] **SLCK-03**: User can select which Slack channels to monitor from their connected workspace
- [ ] **SLCK-04**: Bot messages and messages shorter than 10 characters are automatically filtered out during ingestion
- [ ] **SLCK-05**: Thread replies stored with thread_ts relationship for full conversation context
- [ ] **SLCK-06**: Slack webhook/event signature verification using signing secret on raw request bytes

### Delivery: Linear Comment Bot

- [ ] **DLVR-01**: When a context page is generated, system auto-posts it as a formatted Markdown comment on the Linear ticket via Linear API
- [ ] **DLVR-02**: On context page regeneration, system updates the existing ContextOS comment (not duplicate) with changelog footer showing what changed and when

### Delivery: MCP Server

- [ ] **MCP-01**: MCP server exposes three tools: get_feature_context (ticket → context page), search_context (query → relevant sources), get_related_work (ticket → related tickets)
- [ ] **MCP-02**: MCP server authenticates to cloud backend (Railway) via user-generated API key
- [ ] **MCP-03**: MCP server works with both Cursor and Claude Code via stdio transport

### Security & Observability

- [ ] **SEC-01**: All OAuth tokens (Linear, Slack) stored in Supabase Vault, never in plain-text columns
- [ ] **SEC-02**: Sentry SDK integrated in FastAPI backend with error context (workspace_id, user_id, endpoint)
- [ ] **SEC-03**: Laminar SDK integrated for LLM call tracing (prompts, responses, latency, cost)

## v2 Requirements

### Notion Integration

- **NOT-01**: User can connect Notion workspace via OAuth
- **NOT-02**: System fetches and processes Notion pages shared with integration
- **NOT-03**: Ticket-to-Notion linking via explicit links and semantic similarity

### Dashboard (Bekbol's scope, listed for reference)

- **DASH-01**: Context pages feed with status indicators
- **DASH-02**: Context page detail view with copy AI prompt
- **DASH-03**: Integration setup page
- **DASH-04**: Settings and API key management

### Chrome Extension (Bekbol's scope)

- **EXT-01**: Chrome extension for quick context access

### Onboarding & Analytics

- **ONB-01**: First-time user onboarding wizard
- **ANLYT-01**: Usage analytics (PostHog integration)
- **ANLYT-02**: Admin metrics dashboard

### Slack Enhancement

- **SLCK-07**: Slack historical backfill (last 90 days)
- **SLCK-08**: Semantic similarity for Slack-to-ticket linking

### Meeting Transcripts

- **MEET-01**: Fathom API integration for full transcript ingestion
- **MEET-02**: Meeting-to-ticket linking algorithm

## Out of Scope

| Feature | Reason |
|---------|--------|
| Celery + Redis job queue | Overkill for MVP. FastAPI background tasks sufficient. |
| Full context version history | Current + previous version only. Simpler schema. |
| Team invites and role management | Single team dogfooding, not needed yet. |
| Mobile app / responsive design | Desktop-first internal tool. |
| LlamaIndex integration | Removed per research -- direct httpx/slack-bolt is simpler with fewer deps. |
| Notion in v1 | Linear + Slack covers 80% of context. Defer unless time permits. |
| Semantic Slack linking | Start with explicit links + keywords + thread following. |
| Rate limiting | Not needed during dogfooding with single team. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| FOUND-05 | Phase 1 | Pending |
| FOUND-06 | Phase 1 | Pending |
| FOUND-07 | Phase 1 | Pending |
| LIN-01 | Phase 2 | Pending |
| LIN-02 | Phase 2 | Pending |
| LIN-03 | Phase 2 | Pending |
| LIN-04 | Phase 2 | Pending |
| LIN-05 | Phase 2 | Pending |
| SLCK-01 | Phase 3 | Pending |
| SLCK-02 | Phase 3 | Pending |
| SLCK-03 | Phase 3 | Pending |
| SLCK-04 | Phase 3 | Pending |
| SLCK-05 | Phase 3 | Pending |
| SLCK-06 | Phase 3 | Pending |
| DLVR-01 | Phase 4 | Pending |
| DLVR-02 | Phase 4 | Pending |
| MCP-01 | Phase 5 | Pending |
| MCP-02 | Phase 5 | Pending |
| MCP-03 | Phase 5 | Pending |
| SEC-01 | Phase 6 | Pending |
| SEC-02 | Phase 6 | Pending |
| SEC-03 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after initial definition*
