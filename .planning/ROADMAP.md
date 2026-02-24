# Roadmap: ContextOS v1.0

## Overview

ContextOS v1.0 delivers a daily-driver product where engineers get AI-generated context on any Linear ticket -- pulling from Linear, Slack, and meeting transcripts -- delivered as Linear comments, a web dashboard, MCP tools in IDEs, and a Chrome extension. Three team members build in parallel: Daulet (backend/integrations), Dulat (AI/ML/synthesis), Bekbol (frontend/extensions). The build follows data flow: foundation first (blocks everything), then Linear integration (tickets are the unit of work), then Slack and meeting ingestion (additive data sources), then context generation (the core product), then delivery channels (dashboard, comment bot, MCP), then Chrome extension and production hardening.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Database schema, auth backend + UI, workspace tenancy, project deps (Daulet + Bekbol) (completed 2026-02-24)
- [x] **Phase 2: Linear Integration** - OAuth, ticket sync, webhooks, token refresh (Daulet) (completed 2026-02-24)
- [ ] **Phase 3: Slack and Meeting Ingestion** - Slack OAuth, events API, channel selection, Fathom API, integration setup page (Daulet + Bekbol)
- [ ] **Phase 4: Context Generation** - LangGraph pipeline, Gemini synthesis, Slack-to-ticket linking, meeting-to-ticket linking (Dulat)
- [ ] **Phase 5: Delivery Channels** - Dashboard feed/detail/settings, Linear comment bot, MCP server (Daulet + Bekbol)
- [ ] **Phase 6: Extension and Hardening** - Chrome extension, Vault token storage, Sentry, Laminar (Daulet + Bekbol)

## Parallelization Map

```
Timeline   Daulet                     Dulat                      Bekbol
--------   ------                     -----                      ------
Phase 1    DB schema, auth backend,   (research: embeddings,     Auth pages UI
           workspace, deps            prompt design, pipeline)   (DASH-01)

Phase 2    Linear OAuth, sync,        (research: LangGraph       (prep dashboard
           webhooks, token refresh    pipeline architecture)     components/layout)

Phase 3    Slack OAuth, events,       (begin pipeline impl       Integration setup
           Fathom API, filtering      with Linear-only data)     page (DASH-04)

Phase 4    (support: APIs for         Context generation         (available for
           pipeline data access)      pipeline, synthesis,       dashboard polish)
                                      all linking logic

Phase 5    Linear comment bot,        (quality tuning,           Dashboard feed,
           MCP server,               prompt iteration)           detail, settings
           API key auth                                          (DASH-02,03,05)

Phase 6    Vault storage, Sentry,     --                         Chrome extension
           Laminar                                               (EXT-01)
```

**Parallel execution notes:**
- Phase 2 and Phase 3 CAN run in parallel (both depend only on Phase 1). Daulet sequences them because he owns both, but Bekbol can work on DASH-04 during Phase 2.
- Phase 5 plans run in parallel across Daulet (comment bot + MCP) and Bekbol (dashboard views).
- Phase 6 plans run in parallel across Daulet (security/observability) and Bekbol (Chrome extension).
- Dulat's Phase 4 work starts after Phase 2 completes (needs Linear data); Slack data from Phase 3 is additive.

## Phase Details

### Phase 1: Foundation
**Goal**: Engineers can sign up, log in, and access a workspace-scoped application with a working database, auth backend, and auth UI
**Depends on**: Nothing (first phase)
**Owner**: Daulet (backend) + Bekbol (auth UI)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07, DASH-01
**Success Criteria** (what must be TRUE):
  1. User can sign up with email/password and land on a logged-in dashboard page
  2. User can sign in via magic link email and land on a logged-in dashboard page
  3. User session persists across browser refresh without re-login
  4. Unauthenticated API requests return 401; unauthenticated browser access redirects to login
  5. First login creates a workspace automatically; all subsequent data is scoped to that workspace
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md -- Database schema rewrite (soft deletes, new tables, 768-dim embeddings) + backend app skeleton (deps, config, FastAPI, SQLModel)
- [x] 01-02-PLAN.md -- JWT auth, workspace auto-creation trigger, API protection, tests
- [x] 01-03-PLAN.md -- Auth pages UI (login, signup, magic link, dashboard shell)

### Phase 2: Linear Integration
**Goal**: The system has live Linear ticket data flowing in -- OAuth connected, initial sync complete, webhooks updating tickets in real-time with reliable token refresh
**Depends on**: Phase 1
**Owner**: Daulet
**Requirements**: LIN-01, LIN-02, LIN-03, LIN-04, LIN-05
**Success Criteria** (what must be TRUE):
  1. User can connect their Linear workspace via OAuth from the application and see the connection status
  2. After connecting, all active tickets (with identifier, title, description, state, assignee, labels, project, comments) appear in the database with generated embeddings
  3. When a ticket is created or updated in Linear, the local data updates within seconds via webhook
  4. OAuth tokens refresh automatically before the 24-hour expiry without user intervention
  5. Webhook payloads are verified via HMAC-SHA256 -- tampered payloads are rejected
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md -- Linear OAuth flow with Vault token storage, token refresh with advisory lock, connect/disconnect/status endpoints
- [x] 02-02-PLAN.md -- GraphQL client, initial ticket sync with cursor pagination, team selection, decoupled embedding generation
- [x] 02-03-PLAN.md -- Webhook receiver with HMAC-SHA256 verification, idempotent delivery tracking, event-driven ticket/comment updates with selective re-embedding

### Phase 3: Slack and Meeting Ingestion
**Goal**: The system ingests real-time Slack messages from selected channels, stores threaded conversations, filters noise, ingests meeting transcripts from Fathom, and provides an integration setup page for managing all connections
**Depends on**: Phase 1
**Owner**: Daulet (Slack + Fathom backend) + Bekbol (integration setup page)
**Requirements**: SLCK-01, SLCK-02, SLCK-03, SLCK-04, SLCK-05, SLCK-06, MEET-01, DASH-04
**Success Criteria** (what must be TRUE):
  1. User can connect their Slack workspace via OAuth and see connected status on the integration setup page
  2. User can select which Slack channels to monitor; only messages from selected channels are ingested
  3. Messages appear in the database in real-time; bot messages and messages under 10 characters are filtered out
  4. Thread replies are stored with their parent thread relationship intact
  5. Slack event signatures are verified -- tampered events are rejected
  6. Meeting transcripts from Fathom are ingested with participant info, timestamps, and full text
  7. Integration setup page shows connection status for Linear, Slack, and Fathom with connect/disconnect actions
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md -- Slack OAuth flow, Events API endpoint with signature verification, real-time message ingestion with filtering and threading
- [ ] 03-02-PLAN.md -- Slack channel selection (list, save, refresh) and Fathom API transcript ingestion with speaker-segmented storage
- [ ] 03-03-PLAN.md -- Integration setup page with cards for Linear, Slack, Fathom, channel picker, and Fathom API key form

### Phase 4: Context Generation
**Goal**: The system generates rich 5-section AI context pages from Linear tickets, Slack conversations, and meeting transcripts -- the core product value that makes ContextOS worth using
**Depends on**: Phase 2 (Linear data must exist), Phase 3 (Slack + meeting data is additive but expected)
**Owner**: Dulat
**Requirements**: CTXG-01, CTXG-02, CTXG-03, CTXG-04, CTXG-05, CTXG-06, MEET-02
**Success Criteria** (what must be TRUE):
  1. When a ticket is assigned to an engineer, a context page auto-generates within 60 seconds
  2. Each context page has 5 clearly distinct sections: origin story, business requirements, technical decisions, related work, and AI implementation prompt
  3. Context pages include relevant Slack messages linked via explicit URLs, keyword matching, or thread following
  4. Context pages include relevant meeting transcript segments linked to the ticket
  5. Every source (Slack message, Linear comment, meeting segment) has a clickable attribution link back to the original
  6. On-demand regeneration produces an updated context page reflecting the latest data
**Plans**: TBD

Plans:
- [ ] 04-01: LangGraph gather pipeline and Gemini Flash synthesis (Dulat)
- [ ] 04-02: Slack-to-ticket linking, meeting-to-ticket linking, source attribution (Dulat)
- [ ] 04-03: Auto-trigger on assignment, on-demand regeneration, job tracking (Dulat)

### Phase 5: Delivery Channels
**Goal**: Context pages reach engineers where they work -- a live web dashboard with real-time updates, auto-posted Linear comments, and MCP tools in their IDE
**Depends on**: Phase 4 (context pages must exist), Phase 1 (auth for dashboard)
**Owner**: Bekbol (dashboard) + Daulet (comment bot + MCP)
**Requirements**: DASH-02, DASH-03, DASH-05, DLVR-01, DLVR-02, MCP-01, MCP-02, MCP-03
**Success Criteria** (what must be TRUE):
  1. Dashboard shows a feed of context pages with status indicators (generating, ready, stale) that update in real-time without page refresh
  2. User can open a context page detail view and copy the AI implementation prompt with one click
  3. User can generate an API key from the dashboard settings page for MCP server authentication
  4. When a context page generates, a formatted Markdown comment auto-posts on the Linear ticket
  5. On regeneration, the existing Linear comment updates in place (no duplicates) with a changelog footer
  6. MCP server exposes get_feature_context, search_context, and get_related_work tools that return real data
  7. MCP server works in both Cursor and Claude Code via stdio transport, authenticated via API key
**Plans**: TBD

Plans:
- [ ] 05-01: Dashboard feed, detail view, and settings with API key generation (Bekbol)
- [ ] 05-02: Linear comment bot -- auto-post and update-in-place (Daulet)
- [ ] 05-03: MCP server with 3 tools, API key auth, stdio transport (Daulet)

### Phase 6: Extension and Hardening
**Goal**: Engineers get quick context from the browser toolbar, and the system is production-hardened with encrypted token storage, error tracking, and LLM observability
**Depends on**: Phase 5 (dashboard and context generation must work end-to-end)
**Owner**: Bekbol (extension) + Daulet (security/observability)
**Requirements**: EXT-01, SEC-01, SEC-02, SEC-03
**Success Criteria** (what must be TRUE):
  1. Chrome extension shows the context page for the current Linear ticket when activated from the browser toolbar
  2. All OAuth tokens (Linear, Slack, Fathom) are stored in Supabase Vault -- no plain-text token columns exist
  3. Backend errors are captured in Sentry with workspace_id, user_id, and endpoint context
  4. Every LLM synthesis call is traced in Laminar with prompt, response, latency, and cost visible
**Plans**: TBD

Plans:
- [ ] 06-01: Chrome extension for quick context access (Bekbol)
- [ ] 06-02: Vault token storage, Sentry error tracking, Laminar LLM observability (Daulet)

## Coverage

**39/39 v1 requirements mapped.**

| Category | Requirements | Phase | Owner |
|----------|-------------|-------|-------|
| Foundation | FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07 (7) | Phase 1 | Daulet |
| Dashboard Auth | DASH-01 (1) | Phase 1 | Bekbol |
| Linear Integration | LIN-01, LIN-02, LIN-03, LIN-04, LIN-05 (5) | Phase 2 | Daulet |
| Slack Integration | SLCK-01, SLCK-02, SLCK-03, SLCK-04, SLCK-05, SLCK-06 (6) | Phase 3 | Daulet |
| Meeting Transcripts API | MEET-01 (1) | Phase 3 | Daulet |
| Integration Setup Page | DASH-04 (1) | Phase 3 | Bekbol |
| Context Generation | CTXG-01, CTXG-02, CTXG-03, CTXG-04, CTXG-05, CTXG-06 (6) | Phase 4 | Dulat |
| Meeting Transcript Linking | MEET-02 (1) | Phase 4 | Dulat |
| Dashboard Views + Settings | DASH-02, DASH-03, DASH-05 (3) | Phase 5 | Bekbol |
| Linear Comment Bot | DLVR-01, DLVR-02 (2) | Phase 5 | Daulet |
| MCP Server | MCP-01, MCP-02, MCP-03 (3) | Phase 5 | Daulet |
| Chrome Extension | EXT-01 (1) | Phase 6 | Bekbol |
| Security and Observability | SEC-01, SEC-02, SEC-03 (3) | Phase 6 | Daulet |

No orphaned requirements. No duplicate mappings.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 --> 2 --> 3 --> 4 --> 5 --> 6
Phases 2 and 3 can overlap (both depend only on Phase 1; Bekbol works on DASH-04 while Daulet does Phase 2).
Phase 4 can begin once Phase 2 completes (Linear data exists); Phase 3 Slack data is additive.
Phase 5 plans run in parallel: Bekbol (dashboard) + Daulet (comment bot, MCP).
Phase 6 plans run in parallel: Bekbol (extension) + Daulet (security/observability).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete    | 2026-02-24 |
| 2. Linear Integration | 3/3 | Complete    | 2026-02-24 |
| 3. Slack and Meeting Ingestion | 0/2 | Not started | - |
| 4. Context Generation | 0/3 | Not started | - |
| 5. Delivery Channels | 0/3 | Not started | - |
| 6. Extension and Hardening | 0/2 | Not started | - |

---
*Roadmap created: 2026-02-24*
*Milestone: v1.0 Dogfood*
