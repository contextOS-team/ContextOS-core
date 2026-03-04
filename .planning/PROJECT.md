# ContextOS

## What This Is

ContextOS auto-generates rich context pages for engineering tickets by pulling data from Linear (tickets), Slack (conversations), and Notion (docs), then synthesizing everything with AI so engineers get full context before they start coding. The hero feature is an AI-generated implementation prompt that engineers can paste directly into Cursor or Claude Code.

First users are the founding team (dogfooding). The product must be reliable enough for daily use within 2-3 weeks.

## Team

| Person | Role | Scope |
|--------|------|-------|
| **Daulet Ashikbayev** | Backend & Integrations | FastAPI backend, OAuth flows, Linear/Slack integrations, webhooks, database schema, MCP server, security/observability |
| **Dulat** | AI/ML & Synthesis | Embedding model selection, context generation pipeline (LangGraph + Gemini Flash), synthesis prompt engineering, Slack-to-ticket linking logic, quality evaluation |
| **Bekbol** | Frontend & Extensions | Next.js web dashboard (feed, detail, settings, integration setup), Chrome extension, frontend auth flows, UI/UX |

## Current Milestone: v1.1 Dashboard & Onboarding

**Goal:** Transform the generic dashboard into a polished, brand-consistent product experience with guided onboarding, full context feed, activity timeline, and team settings — dark theme that mirrors the landing page's teal identity but stays muted for daily use.

**Target features:**
- Guided onboarding: step-by-step integration setup + workspace config + first context generation (user sees the product work before hitting the dashboard)
- Dashboard redesign: dark theme with teal accents (muted/professional, not flashy like landing), consistent typography and spacing
- Context feed: browsable feed of all generated context pages with filtering, search, and rich detail views
- Activity timeline: real-time feed of syncs, new context generated, integration activity
- Team & settings: workspace settings, API key management, notification preferences, team management
- Auth page redesign: login/signup styled to match the dark brand identity
- Design system: unified tokens, components, and patterns shared between landing and dashboard

## Core Value

When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, what the business requirements are, and a ready-to-paste AI prompt for their coding assistant. No more hunting through Slack threads and Notion pages.

## Requirements

### Validated

- [x] Project repository initialized with Next.js 15, FastAPI, Supabase, MCP server scaffold
- [x] Docker Compose configured for Redis
- [x] Supabase local dev configured (config.toml, seed.sql)
- [x] Makefile with dev workflow commands
- [x] CI-ready linting (ESLint, ruff) and type checking (tsc, mypy)

### Active

- [ ] Database schema with pgvector embeddings, RLS multi-tenancy, and all core tables
- [ ] Supabase Auth (email/password + magic links) with session management
- [ ] Linear OAuth2 flow handled by Python backend
- [ ] Linear initial data sync (pull active tickets, generate embeddings)
- [ ] Linear webhook listener (issue create/update, comment create)
- [ ] Slack OAuth2 V2 flow (bot + user tokens) handled by Python backend
- [ ] Slack real-time event ingestion (message.channels, message.groups)
- [ ] Slack-to-ticket linking (explicit links + keyword match + thread following)
- [ ] Context page generation using Gemini Flash (5 sections: origin story, business requirements, technical decisions, related work, AI prompt)
- [ ] Context page auto-regeneration on ticket assignment + on-demand
- [ ] Auto-post context as Linear comment (update existing + changelog footer)
- [ ] MCP server with get_feature_context, search_context, get_related_work tools
- [ ] MCP authentication via user API keys calling cloud backend
- [ ] Web dashboard: context pages feed with status indicators
- [ ] Web dashboard: context page detail view with copy AI prompt button
- [ ] Web dashboard: integration setup page (connect/disconnect Linear, Slack, Notion)
- [ ] Web dashboard: settings page with API key generation
- [ ] Web dashboard: auth pages (login, signup, magic link) connecting to Supabase Auth
- [ ] Chrome extension for quick context access from browser
- [ ] Fathom API integration for meeting transcript ingestion (Daulet: API, Dulat: linking)
- [ ] Meeting transcript-to-ticket linking algorithm
- [ ] Webhook signature verification (Linear HMAC-SHA256, Slack signing secret)
- [ ] OAuth token storage in Supabase Vault
- [ ] Sentry error tracking integration
- [ ] Laminar LLM observability integration

### Out of Scope

- Notion integration (v1) -- Nice-to-have, defer unless time permits. Linear + Slack covers 80% of context.
- Celery + Redis job queue -- Overkill for MVP. Use FastAPI background tasks instead.
- Full onboarding wizard (CON-27) -- Team can use integration setup page directly.
- Usage analytics / PostHog (CON-29) -- Ship first, measure later.
- Slack historical backfill (CON-13) -- Start with real-time ingestion. Backfill is a v2 optimization.
- Semantic similarity for Slack linking -- Start with explicit links + keyword match + thread following. Add embeddings-based search in v2.
- Full context page version history -- Keep current + previous version only.
- Team invites and role management -- Single team dogfooding, not needed yet.
- Mobile app / responsive design polish -- Desktop-first internal tool.

## Context

**Team:** Three-person founding team dogfooding the product. Daulet owns backend and integrations, Dulat owns AI/ML (embedding model, synthesis optimization, linking logic), Bekbol owns the web dashboard and Chrome extension.

**Existing codebase:** Scaffold with config files and .gitkeep placeholders. No implementation code. All backend directories (api, agents, ingestion, synthesis, embeddings, workers) are empty. Frontend has Next.js config but no pages or components. MCP server has package.json but no source.

**Linear tasks:** 24 tasks across 11 epics (CON-5 through CON-32). CON-5 (repo init) is In Review. Everything else is Backlog. Tasks have detailed acceptance criteria and implementation notes.

**External dependencies:**
- Linear OAuth app registration required
- Slack app registration required (api.slack.com/apps)
- Supabase Cloud project required
- Railway project for backend deployment
- Vercel project for frontend deployment
- Gemini API key for synthesis (Dulat's choice over Claude for cost/speed)
- Fathom API access for meeting transcript ingestion

## Constraints

- **Timeline**: 2-3 weeks to daily-driver quality
- **AI Model**: Gemini Flash for synthesis (cheap, fast, smart -- Dulat's decision)
- **Embedding Model**: TBD (Dulat decides)
- **Auth**: Supabase Auth only (no Clerk, no NextAuth)
- **Multi-tenancy**: 1:1:1 mapping (one workspace = one Linear org + one Slack workspace + optional Notion workspace)
- **Token Storage**: Supabase Vault (no custom AES-256 encryption)
- **Job Queue**: FastAPI background tasks for v1 (no Celery)
- **Generation Architecture**: Hybrid -- LangGraph for data gathering, single LLM call for synthesis
- **Context Versioning**: Current + previous version only (not full history)
- **OAuth Flows**: Python backend handles all OAuth (not Next.js)
- **Frontend-Backend**: Supabase for reads, Python API for actions
- **MCP Network**: Calls cloud backend (Railway), not localhost
- **Hosting**: Vercel (frontend), Railway (backend), Supabase Cloud (database)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Supabase Auth over Clerk/NextAuth | Already in stack, no extra dependency, built-in magic links | -- Pending |
| Python handles OAuth flows | Backend makes API calls, avoids cross-service token passing | -- Pending |
| Supabase Vault for tokens | Managed encryption, less custom code than AES-256 | -- Pending |
| Gemini Flash for synthesis | Cost-effective at scale, fast response, adequate quality | -- Pending |
| FastAPI background tasks over Celery | MVP simplicity, Celery is overkill for current scale | -- Pending |
| 1:1:1 workspace tenancy | Matches real usage (one team = one Linear + one Slack), simplest model | -- Pending |
| Start Slack linking simple | Explicit links + keywords + thread following. Defer semantic search to v2. | -- Pending |
| Linear comment bot: update existing | One clean comment per ticket, changelog footer for freshness visibility | -- Pending |
| Trigger on assignment + on-demand | Auto-generate when ticket assigned, manual regenerate available. Not all new tickets. | -- Pending |
| Current + previous version only | Simpler schema, "what changed" visibility without full history complexity | -- Pending |
| Supabase for reads, API for actions | Instant reads via Supabase client, real-time subscriptions, backend for heavy lifting | -- Pending |
| API key auth for MCP | Standard developer pattern, easy setup (generate key, paste in config) | -- Pending |
| Defer Notion to v2 | Linear + Slack covers 80% of context. Notion adds complexity for diminishing returns in v1. | -- Pending |
| Meeting transcripts in v1 | Fathom API ingestion adds meeting context to tickets. Daulet: API, Dulat: linking. | -- Pending |
| Shared roadmap for all 3 members | Previously Daulet-scoped; expanded to cover Dulat (AI/ML) and Bekbol (frontend) | -- Pending |
| Bekbol builds auth UI | Login/signup/magic-link pages in Next.js, connecting to Supabase Auth backend | -- Pending |

---
*Last updated: 2026-03-04 -- v1.1 milestone started, dashboard & onboarding focus*
