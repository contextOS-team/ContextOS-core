# ContextOS

## What This Is

ContextOS auto-generates rich context pages for engineering tickets by pulling data from Linear (tickets), Slack (conversations), GitHub (PRs/reviews), Notion (docs), and a knowledge graph (entities, decisions, relationships), then synthesizing everything with AI so engineers get full context before they start coding. The hero feature is an AI-generated implementation prompt that engineers can paste directly into Cursor or Claude Code.

First users are the founding team (dogfooding). The product is in daily use with three shipped milestones.

## Team

| Person | Role | Scope |
|--------|------|-------|
| **Daulet Ashikbayev** | Backend & Integrations | FastAPI backend, OAuth flows, Linear/Slack integrations, webhooks, database schema, MCP server, security/observability |
| **Dulat** | AI/ML & Synthesis | Embedding model selection, context generation pipeline (LangGraph + Gemini Flash), synthesis prompt engineering, Slack-to-ticket linking logic, quality evaluation |
| **Bekbol** | Frontend & Extensions | Next.js web dashboard (feed, detail, settings, integration setup), Chrome extension, frontend auth flows, UI/UX |

## Current State

**Shipped:** v1.0 Dogfood (2026-03-03), v1.1 Dashboard & Onboarding (2026-03-15), v1.2 GraphRAG (2026-03-08)
**Tech stack:** Next.js 15, FastAPI, Supabase (Postgres + Auth + Realtime), Redis, pgvector, knowledge graph (plain PG tables + recursive CTEs)
**Integrations:** Linear, Slack, GitHub, GitLab, Jira, Notion, Fathom, Telegram, Slack Huddles
**Next milestone:** v1.3 Live Intelligence

## Current Milestone: v1.3 Live Intelligence

**Goal:** Make ContextOS alive -- activity feed that actually shows events, interactive graph visualization, Chrome extension published to Web Store with Linear/Jira integration, privacy-first architecture for enterprise trust, and landing page refresh.

**Target features:**
- Activity events emission from all integrations (fix dead Activity tab)
- Context graph visualization UI (interactive node/edge explorer)
- Chrome extension: publish to Chrome Web Store, design Linear/Jira page integration
- Privacy/self-hosted architecture (data stays on customer infrastructure)
- Landing page update (9 integrations + polish)
- RAG improvements (TBD, Dulat's scope)

## Core Value

When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, what decisions were made and by whom, who's involved across tools, and a ready-to-paste AI prompt for their coding assistant. No more hunting through Slack threads and Notion pages.

## Requirements

### Validated

- ✓ Project repository initialized with Next.js 15, FastAPI, Supabase, MCP server scaffold -- v1.0
- ✓ Docker Compose configured for Redis -- v1.0
- ✓ Supabase local dev configured (config.toml, seed.sql) -- v1.0
- ✓ Makefile with dev workflow commands -- v1.0
- ✓ CI-ready linting (ESLint, ruff) and type checking (tsc, mypy) -- v1.0
- ✓ Database schema with pgvector embeddings, RLS multi-tenancy, and all core tables -- v1.0
- ✓ Supabase Auth (email/password + magic links) with session management -- v1.0
- ✓ Linear OAuth2, ticket sync, webhooks, token refresh -- v1.0
- ✓ Slack OAuth2, real-time event ingestion, channel selection -- v1.0
- ✓ GitHub OAuth, PR/review ingestion, PR-to-Linear linking -- v1.0
- ✓ Notion OAuth, page ingestion, webhook updates -- v1.0
- ✓ Context page generation using Gemini Flash (5 sections) -- v1.0
- ✓ MCP server with get_feature_context, search_context tools -- v1.0
- ✓ Chrome extension for quick context access -- v1.0
- ✓ Webhook signature verification (Linear, Slack) -- v1.0
- ✓ OAuth token storage in Supabase Vault -- v1.0
- ✓ Sentry error tracking, Laminar LLM observability -- v1.0
- ✓ Dark theme with brand-tinted OKLCH tokens, JetBrains Mono typography -- v1.1
- ✓ 4-step onboarding wizard with OAuth state preservation -- v1.1
- ✓ Activity timeline with real-time updates -- v1.1
- ✓ Context feed with filtering, search, detail view -- v1.1
- ✓ Settings page with API key management -- v1.1
- ✓ Knowledge graph schema with workspace-scoped RLS, fingerprint deduplication, recursive CTE traversal -- v1.2
- ✓ Rule-based extraction (ticket refs, PRs, @mentions, file paths, URLs) inline at zero LLM cost -- v1.2
- ✓ Cross-source identity resolution via email-based matching with roster seeding -- v1.2
- ✓ LLM entity extraction via Gemini Flash with decision/blocker persistence and source validation -- v1.2
- ✓ Graph-enhanced retrieval as 3rd signal with depth-decay scoring and token budget -- v1.2
- ✓ Context pages with decision trails, relationship paths, people cross-references, code provenance -- v1.2
- ✓ Graph Explorer API endpoint for subgraph JSON -- v1.2

- ✓ Dark theme with OKLCH tokens, onboarding wizard, activity timeline, context feed, settings page -- v1.1
- ✓ Social OAuth (Google/GitHub), password reset, auth brand panel -- v1.1
- ✓ Real-time SSE context generation progress UI -- v1.1
- ✓ Remotion animated hero on landing page -- v1.1
- ✓ GitLab integration (OAuth, MR sync, webhooks, code indexing) -- v1.1
- ✓ Jira integration (OAuth 3LO, JQL sync, webhooks) -- v1.1
- ✓ Telegram chat integration (Bot API, message ingestion) -- v1.1
- ✓ Dashboard intelligence widgets (attention, resurfaced, weekly, sprint) -- v1.1
- ✓ Security hardening (JQL injection, OAuth state signing, rate limiting) -- v1.1
- ✓ Concurrent sync optimization for GitLab/GitHub -- v1.1
- ✓ Slack huddle transcript ingestion -- v1.1

### Active

- [ ] Activity events emitted by all integration sync services
- [ ] Interactive graph visualization for ticket context
- [ ] Chrome extension published to Chrome Web Store
- [ ] Chrome extension surfaces context on Linear/Jira ticket pages
- [ ] Privacy-first deployment option (customer data stays local)
- [ ] Landing page updated with all 9 integrations
- [ ] RAG quality improvements (TBD)

### Out of Scope

- Full onboarding wizard (CON-27) -- Team can use integration setup page directly
- Slack historical backfill (CON-13) -- Start with real-time ingestion, backfill is v2 optimization
- Full context page version history -- Keep current + previous version only
- Team invites and role management -- Single team dogfooding, not needed yet
- Mobile app / responsive design polish -- Desktop-first internal tool
- Apache AGE extension -- Not available on Supabase Cloud, plain PG tables work better
- Neo4j or separate graph DB -- Doubles operational complexity, graph stays in Supabase Postgres
- Microsoft GraphRAG Leiden clustering -- Corpus-scale overkill, ContextOS has structured data
- Real-time LLM extraction on every webhook -- Burns API budget, two-tier (regex inline, LLM batch) is better
- Person-centric aggregation UI -- Emerges from graph data in context pages, dedicated UI deferred
- ~~Graph explorer frontend (GAPI-02)~~ -- Moved to v1.3 Active scope

## Context

**Team:** Three-person founding team dogfooding the product. Daulet owns backend and integrations, Dulat owns AI/ML, Bekbol owns frontend.

**Codebase:** 35,442 LOC Python backend, Next.js 15 frontend with dark theme. 27 phases shipped across 3 milestones. 547 backend tests passing.

**Architecture:** FastAPI + Supabase (Postgres, Auth, Realtime, Vault) + Redis. Knowledge graph uses plain Postgres tables (graph_nodes, graph_edges) with recursive CTEs and SECURITY DEFINER traversal function. Gemini Flash for synthesis and semantic entity extraction. pgvector for embeddings.

**Known tech debt (from v1.2 audit):**
- traverse_graph() missing source_type/source_id columns -- graph results have empty snippets in synthesis
- Decision node snippet reads wrong property keys -- shows "Unknown" for author/source/affects
- Duplicated _compute_fingerprint() in llm_extractor.py
- Nyquist validation incomplete across all v1.2 phases

## Constraints

- **AI Model**: Gemini Flash for synthesis (cheap, fast, smart)
- **Auth**: Supabase Auth only (no Clerk, no NextAuth)
- **Multi-tenancy**: 1:1:1 mapping (one workspace = one Linear org + one Slack workspace + optional Notion workspace)
- **Token Storage**: Supabase Vault
- **Job Queue**: FastAPI background tasks (no Celery)
- **Graph**: Plain Postgres tables with recursive CTEs (no AGE, no Neo4j)
- **Frontend-Backend**: Supabase for reads, Python API for actions
- **MCP Network**: Calls cloud backend (Railway), not localhost
- **Hosting**: Vercel (frontend), Railway (backend), Supabase Cloud (database)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Supabase Auth over Clerk/NextAuth | Already in stack, no extra dependency, built-in magic links | ✓ Good |
| Python handles OAuth flows | Backend makes API calls, avoids cross-service token passing | ✓ Good |
| Supabase Vault for tokens | Managed encryption, less custom code than AES-256 | ✓ Good |
| Gemini Flash for synthesis | Cost-effective at scale, fast response, adequate quality | ✓ Good |
| FastAPI background tasks over Celery | MVP simplicity, Celery is overkill for current scale | ✓ Good |
| 1:1:1 workspace tenancy | Matches real usage, simplest model | ✓ Good |
| Linear comment bot: update existing | One clean comment per ticket, changelog footer | ✓ Good |
| Supabase for reads, API for actions | Instant reads via Supabase client, real-time subscriptions | ✓ Good |
| Plain PG tables over Apache AGE | AGE not available on Supabase Cloud; recursive CTEs work well | ✓ Good |
| Two-tier extraction (regex + LLM batch) | Regex inline at zero cost for structured refs, Gemini Flash batch for semantic entities | ✓ Good |
| Graph blends with existing hybrid search | Additive improvement, not replacement -- existing retrieval is fallback | ✓ Good |
| Email-based identity resolution, never auto-merge on name | Deterministic matching prevents false merges across platforms | ✓ Good |
| SHA-256 fingerprint deduplication for graph nodes | Deterministic, prevents duplicates on re-ingestion | ✓ Good |
| SECURITY DEFINER for traverse_graph() | Validates workspace once, avoids per-row RLS overhead in recursive CTE | ✓ Good |
| Fail-silent graph extraction pattern | Graph features never break core webhook ingestion | ✓ Good |
| Graph explorer frontend deferred | API ships now, React visualization later when there's real graph data to explore | ✓ Good |
| 2,000 token unified budget for retrieval | Signal diversity first trimming prevents graph context flooding | ✓ Good |

---
*Last updated: 2026-03-15 after v1.3 Live Intelligence milestone started*
