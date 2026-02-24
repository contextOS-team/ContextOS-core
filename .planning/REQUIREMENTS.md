# Requirements: ContextOS

**Defined:** 2026-02-24
**Core Value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Scope:** Shared across all team members (Daulet, Dulat, Bekbol). Owner marked per requirement.

## v1 Requirements

### Foundation (Daulet)

- [ ] **FOUND-01**: Database schema with all core tables (workspaces, users, oauth_tokens, linear_tickets, slack_messages, context_pages, meeting_transcripts, embeddings), pgvector (768 dims), RLS policies via Supabase migrations
- [ ] **FOUND-02**: User can sign up with email and password via Supabase Auth
- [ ] **FOUND-03**: User can sign in with magic link via Supabase Auth
- [ ] **FOUND-04**: User session persists across browser refresh
- [ ] **FOUND-05**: API routes are protected (unauthenticated requests return 401)
- [ ] **FOUND-06**: Workspace creation on first login with 1:1:1 tenancy model (one workspace = one Linear org + one Slack workspace)
- [ ] **FOUND-07**: Update pyproject.toml dependencies: replace anthropic with google-genai, remove llama-index packages, remove celery[redis]; add slack-bolt, keep redis for caching

### Linear Integration (Daulet)

- [ ] **LIN-01**: User can connect Linear workspace via OAuth2 flow handled by Python backend (redirect → callback → store tokens in Supabase Vault)
- [ ] **LIN-02**: On first connect, system pulls all active tickets for selected team(s) with identifier, title, description, state, assignee, labels, project, comments; generates embeddings
- [ ] **LIN-03**: Linear webhooks received at POST /api/webhooks/linear and verified via HMAC-SHA256 with webhook secret using raw request bytes
- [ ] **LIN-04**: Webhook events (issue create/update, comment create, assignment change) update local linear_tickets data and trigger context page regeneration via FastAPI background tasks
- [ ] **LIN-05**: OAuth token refresh handles Linear's mandatory 24-hour expiry automatically with race condition prevention

### Slack Integration (Daulet)

- [ ] **SLCK-01**: User can connect Slack workspace via OAuth2 V2 flow with both bot token and user token scopes, handled by Python backend
- [ ] **SLCK-02**: System ingests real-time Slack messages from user-selected channels via Events API (slack-bolt)
- [ ] **SLCK-03**: User can select which Slack channels to monitor from their connected workspace
- [ ] **SLCK-04**: Bot messages and messages shorter than 10 characters are automatically filtered out during ingestion
- [ ] **SLCK-05**: Thread replies stored with thread_ts relationship for full conversation context
- [ ] **SLCK-06**: Slack webhook/event signature verification using signing secret on raw request bytes

### Meeting Transcripts (Daulet: API, Dulat: linking)

- [ ] **MEET-01**: System ingests meeting transcripts from Fathom API with participant info, timestamps, and full text (Daulet)
- [ ] **MEET-02**: Meeting transcript-to-ticket linking algorithm identifies which meetings are relevant to which tickets (Dulat)

### Context Generation (Dulat)

- [ ] **CTXG-01**: LangGraph gather-then-synthesize pipeline collects Linear ticket data, related Slack threads, meeting transcripts, and embedding search results in parallel
- [ ] **CTXG-02**: Single Gemini Flash synthesis call produces a 5-section context page (origin story, business requirements, technical decisions, related work, AI prompt) from gathered data
- [ ] **CTXG-03**: Context page auto-generates when a ticket is assigned to an engineer
- [ ] **CTXG-04**: On-demand regeneration produces a fresh context page reflecting latest data
- [ ] **CTXG-05**: Slack-to-ticket linking logic connects messages to tickets via explicit URLs, keyword matching, and thread following
- [ ] **CTXG-06**: Source attribution with links back to original Slack messages, Linear comments, and meeting transcript segments

### Delivery: Linear Comment Bot (Daulet)

- [ ] **DLVR-01**: When a context page is generated, system auto-posts it as a formatted Markdown comment on the Linear ticket via Linear API
- [ ] **DLVR-02**: On context page regeneration, system updates the existing ContextOS comment (not duplicate) with changelog footer showing what changed and when

### Delivery: MCP Server (Daulet)

- [ ] **MCP-01**: MCP server exposes three tools: get_feature_context (ticket → context page), search_context (query → relevant sources), get_related_work (ticket → related tickets)
- [ ] **MCP-02**: MCP server authenticates to cloud backend (Railway) via user-generated API key
- [ ] **MCP-03**: MCP server works with both Cursor and Claude Code via stdio transport

### Delivery: Web Dashboard (Bekbol)

- [ ] **DASH-01**: Auth pages — login, signup, and magic link pages connecting to Supabase Auth
- [ ] **DASH-02**: Context pages feed with status indicators (generating, ready, stale) and real-time updates via Supabase Realtime
- [ ] **DASH-03**: Context page detail view with formatted 5-section display and copy AI prompt button
- [ ] **DASH-04**: Integration setup page — connect/disconnect Linear, Slack, and Fathom with status display
- [ ] **DASH-05**: Settings page with API key generation for MCP server

### Delivery: Chrome Extension (Bekbol)

- [ ] **EXT-01**: Chrome extension displays context page for current Linear ticket from browser toolbar

### Security & Observability (Daulet)

- [ ] **SEC-01**: All OAuth tokens (Linear, Slack, Fathom) stored in Supabase Vault, never in plain-text columns
- [ ] **SEC-02**: Sentry SDK integrated in FastAPI backend with error context (workspace_id, user_id, endpoint)
- [ ] **SEC-03**: Laminar SDK integrated for LLM call tracing (prompts, responses, latency, cost)

## v2 Requirements

### Notion Integration

- **NOT-01**: User can connect Notion workspace via OAuth
- **NOT-02**: System fetches and processes Notion pages shared with integration
- **NOT-03**: Ticket-to-Notion linking via explicit links and semantic similarity

### Slack Enhancement

- **SLCK-07**: Slack historical backfill (last 90 days)
- **SLCK-08**: Semantic similarity for Slack-to-ticket linking via embeddings

### Onboarding & Analytics

- **ONB-01**: First-time user onboarding wizard
- **ANLYT-01**: Usage analytics (PostHog integration)
- **ANLYT-02**: Admin metrics dashboard

### Chrome Extension Enhancement

- **EXT-02**: Quick search from extension popup
- **EXT-03**: Notifications for new context pages

## Out of Scope

| Feature | Reason |
|---------|--------|
| Celery + Redis job queue | Overkill for MVP. FastAPI background tasks sufficient. |
| Full context version history | Current + previous version only. Simpler schema. |
| Team invites and role management | Single team dogfooding, not needed yet. |
| Mobile app / responsive design | Desktop-first internal tool. |
| LlamaIndex integration | Removed per research -- direct httpx/slack-bolt is simpler with fewer deps. |
| Notion in v1 | Linear + Slack + Fathom covers 80%+ of context. Defer unless time permits. |
| Semantic Slack linking | Start with explicit links + keywords + thread following. |
| Rate limiting | Not needed during dogfooding with single team. |

## Traceability

| Requirement | Phase | Owner | Status |
|-------------|-------|-------|--------|
| FOUND-01 | TBD | Daulet | Pending |
| FOUND-02 | TBD | Daulet | Pending |
| FOUND-03 | TBD | Daulet | Pending |
| FOUND-04 | TBD | Daulet | Pending |
| FOUND-05 | TBD | Daulet | Pending |
| FOUND-06 | TBD | Daulet | Pending |
| FOUND-07 | TBD | Daulet | Pending |
| LIN-01 | TBD | Daulet | Pending |
| LIN-02 | TBD | Daulet | Pending |
| LIN-03 | TBD | Daulet | Pending |
| LIN-04 | TBD | Daulet | Pending |
| LIN-05 | TBD | Daulet | Pending |
| SLCK-01 | TBD | Daulet | Pending |
| SLCK-02 | TBD | Daulet | Pending |
| SLCK-03 | TBD | Daulet | Pending |
| SLCK-04 | TBD | Daulet | Pending |
| SLCK-05 | TBD | Daulet | Pending |
| SLCK-06 | TBD | Daulet | Pending |
| MEET-01 | TBD | Daulet | Pending |
| MEET-02 | TBD | Dulat | Pending |
| CTXG-01 | TBD | Dulat | Pending |
| CTXG-02 | TBD | Dulat | Pending |
| CTXG-03 | TBD | Dulat | Pending |
| CTXG-04 | TBD | Dulat | Pending |
| CTXG-05 | TBD | Dulat | Pending |
| CTXG-06 | TBD | Dulat | Pending |
| DLVR-01 | TBD | Daulet | Pending |
| DLVR-02 | TBD | Daulet | Pending |
| MCP-01 | TBD | Daulet | Pending |
| MCP-02 | TBD | Daulet | Pending |
| MCP-03 | TBD | Daulet | Pending |
| DASH-01 | TBD | Bekbol | Pending |
| DASH-02 | TBD | Bekbol | Pending |
| DASH-03 | TBD | Bekbol | Pending |
| DASH-04 | TBD | Bekbol | Pending |
| DASH-05 | TBD | Bekbol | Pending |
| EXT-01 | TBD | Bekbol | Pending |
| SEC-01 | TBD | Daulet | Pending |
| SEC-02 | TBD | Daulet | Pending |
| SEC-03 | TBD | Daulet | Pending |

**Coverage:**
- v1 requirements: 39 total
- Daulet: 22 requirements
- Dulat: 7 requirements
- Bekbol: 7 requirements
- Shared (Daulet+Dulat): 3 requirements (MEET-01 Daulet, MEET-02 Dulat, overlap in CTXG pipeline)
- Mapped to phases: 0 (TBD — roadmapper will fill)
- Unmapped: 39

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 — v1.0 shared team scope*
