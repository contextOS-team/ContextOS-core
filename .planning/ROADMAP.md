# Roadmap: ContextOS

## Overview

ContextOS delivers AI-generated context pages for engineering tickets by pulling data from Linear and Slack, synthesizing it with Gemini Flash, and delivering it as Linear comments, through a web dashboard, and via MCP tools in IDEs. This roadmap covers Daulet Ashikbayev's scope: backend infrastructure, integrations, AI synthesis pipeline, and MCP server. Bekbol handles the web dashboard and Chrome extension separately. The build order follows data flow: foundation and auth first, then Linear as the primary data source, then the synthesis pipeline, then delivery channels (comment bot, MCP), then Slack as the additive data source, then hardening with security and observability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation and Auth** - Database schema, Supabase Auth, workspace tenancy, project dependencies
- [ ] **Phase 2: Linear Integration** - OAuth2 flow, ticket sync, webhook listener, token refresh
- [ ] **Phase 3: Slack Integration** - OAuth2 V2 flow, Events API ingestion, channel selection, message filtering
- [ ] **Phase 4: Context Generation and Comment Bot** - LangGraph gather pipeline, Gemini Flash synthesis, auto-post to Linear, update existing comments
- [ ] **Phase 5: MCP Server** - Three MCP tools, API key auth, stdio transport for Cursor and Claude Code
- [ ] **Phase 6: Security and Observability** - Vault token storage, Sentry error tracking, Laminar LLM tracing

## Phase Details

### Phase 1: Foundation and Auth
**Goal**: Engineers can sign up, sign in, and access a workspace-scoped backend with all core tables, RLS policies, and correct project dependencies
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07
**Success Criteria** (what must be TRUE):
  1. User can create an account with email/password and is redirected to an authenticated state
  2. User can sign in via magic link email and land in their workspace
  3. User session persists across browser refresh without re-authentication
  4. Unauthenticated API requests to any protected endpoint return 401
  5. First-time user login automatically creates a workspace with 1:1:1 tenancy model
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD
- [ ] 01-03: TBD

### Phase 2: Linear Integration
**Goal**: System continuously syncs Linear ticket data into the local database via OAuth and webhooks, with reliable token refresh
**Depends on**: Phase 1
**Requirements**: LIN-01, LIN-02, LIN-03, LIN-04, LIN-05
**Success Criteria** (what must be TRUE):
  1. User can connect their Linear workspace via OAuth2 and see a successful connection status
  2. After connecting, all active tickets for selected teams are pulled with full metadata and embeddings generated
  3. When a ticket is created, updated, or commented on in Linear, the local data updates within seconds via webhook
  4. Webhook requests with invalid HMAC signatures are rejected with 401
  5. Token refresh handles Linear's 24-hour expiry transparently without user intervention or race conditions
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD
- [ ] 02-03: TBD

### Phase 3: Slack Integration
**Goal**: System ingests real-time Slack messages from user-selected channels with proper filtering and thread context
**Depends on**: Phase 1
**Requirements**: SLCK-01, SLCK-02, SLCK-03, SLCK-04, SLCK-05, SLCK-06
**Success Criteria** (what must be TRUE):
  1. User can connect their Slack workspace via OAuth2 V2 and both bot and user tokens are stored
  2. Messages from user-selected channels appear in the system within seconds of being posted
  3. User can select and deselect which Slack channels are monitored
  4. Bot messages and messages shorter than 10 characters do not appear in ingested data
  5. Thread replies are stored with their parent thread relationship intact for full conversation reconstruction
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Context Generation and Comment Bot
**Goal**: System generates 5-section AI context pages from Linear and Slack data and delivers them as formatted comments on Linear tickets
**Depends on**: Phase 2, Phase 3
**Requirements**: DLVR-01, DLVR-02
**Success Criteria** (what must be TRUE):
  1. When a ticket is assigned, a context page with all 5 sections (origin story, business requirements, technical decisions, related work, AI prompt) is generated automatically
  2. The generated context page appears as a formatted Markdown comment on the corresponding Linear ticket
  3. When a context page is regenerated, the existing ContextOS comment is updated in place (no duplicates) with a changelog footer showing what changed and when
  4. On-demand regeneration produces a fresh context page reflecting the latest data
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD

### Phase 5: MCP Server
**Goal**: Engineers can access context pages and search for related work directly from Cursor or Claude Code via MCP tools
**Depends on**: Phase 4
**Requirements**: MCP-01, MCP-02, MCP-03
**Success Criteria** (what must be TRUE):
  1. Engineer can call get_feature_context with a ticket identifier and receive the full context page in their IDE
  2. Engineer can call search_context with a natural language query and receive relevant sources
  3. Engineer can call get_related_work with a ticket identifier and receive related tickets
  4. MCP server authenticates via user-generated API key against the cloud backend
  5. MCP server works in both Cursor and Claude Code via stdio transport without additional configuration beyond the API key
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Security and Observability
**Goal**: All sensitive tokens are encrypted at rest, errors are tracked with context, and LLM calls are traced for quality and cost monitoring
**Depends on**: Phase 2, Phase 3 (tokens must exist to secure), Phase 4 (LLM calls must exist to trace)
**Requirements**: SEC-01, SEC-02, SEC-03
**Success Criteria** (what must be TRUE):
  1. All OAuth tokens (Linear, Slack) are stored in Supabase Vault and no plain-text tokens exist in any database column
  2. Backend errors appear in Sentry with workspace_id, user_id, and endpoint context within seconds of occurrence
  3. Every LLM synthesis call is traced in Laminar with prompt content, response, latency, and cost visible
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6
Note: Phases 2 and 3 can execute in parallel (both depend only on Phase 1).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Auth | 0/3 | Not started | - |
| 2. Linear Integration | 0/3 | Not started | - |
| 3. Slack Integration | 0/3 | Not started | - |
| 4. Context Generation and Comment Bot | 0/3 | Not started | - |
| 5. MCP Server | 0/2 | Not started | - |
| 6. Security and Observability | 0/2 | Not started | - |
