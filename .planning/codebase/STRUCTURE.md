# Codebase Structure

**Analysis Date:** 2026-03-12

## Directory Layout

```
ContextOS-core/
├── apps/
│   └── web/                    # Next.js 14 frontend (App Router)
│       ├── public/             # Static assets, brand icons
│       └── src/
│           ├── app/            # App Router pages and route handlers
│           │   ├── (auth)/     # Auth route group (no shared layout)
│           │   ├── (landing)/  # Landing page route group
│           │   ├── dashboard/  # Authenticated dashboard pages
│           │   └── onboarding/ # Onboarding wizard page
│           ├── components/     # React components
│           │   ├── auth/       # Auth form components
│           │   ├── dashboard/  # Dashboard-specific components
│           │   ├── icons/      # Brand logo SVG components
│           │   ├── landing/    # Landing page components
│           │   ├── onboarding/ # Multi-step onboarding wizard
│           │   └── ui/         # shadcn/ui primitives
│           ├── extension/      # Browser extension integration
│           ├── hooks/          # Shared React hooks
│           ├── lib/            # Utility modules and API client
│           │   ├── supabase/   # Supabase client factories (browser/server/middleware)
│           │   └── __tests__/  # Unit tests for lib utilities
│           └── remotion/       # Animated hero video components
├── backend/
│   ├── src/
│   │   ├── main.py             # FastAPI app entrypoint, lifespan, middleware
│   │   ├── config.py           # Pydantic settings (env vars)
│   │   ├── db.py               # SQLAlchemy async engine + session factory
│   │   ├── auth.py             # Supabase JWT decode
│   │   ├── dependencies.py     # get_current_user FastAPI dependency
│   │   ├── routers/            # FastAPI route handlers (one file per provider)
│   │   ├── services/           # Business logic (sync, OAuth, synthesis, workers)
│   │   ├── models/             # SQLModel ORM models (one file per domain)
│   │   ├── middleware/         # CORS, rate limit, correlation ID, security headers
│   │   ├── observability/      # Sentry, Laminar, structured logging setup
│   │   ├── utils/              # Shared helpers
│   │   ├── agents/             # (Reserved for future AI agent code)
│   │   ├── api/                # (Reserved, currently unused)
│   │   ├── embeddings/         # (Reserved, currently unused)
│   │   ├── ingestion/          # (Reserved, currently unused)
│   │   ├── synthesis/          # (Reserved, currently unused)
│   │   └── workers/            # (Reserved, currently unused)
│   └── tests/                  # pytest test suite
├── packages/
│   └── mcp-server/             # Model Context Protocol server (Node.js/TypeScript)
│       └── src/
│           ├── index.ts        # MCP server entrypoint
│           ├── tools/          # MCP tool implementations
│           └── resources/      # MCP resource implementations
├── supabase/
│   ├── migrations/             # Numbered SQL migrations (00001_ ... 00021_)
│   └── snippets/               # Saved SQL snippets
├── docs/                       # Project documentation
├── nginx/                      # Nginx reverse proxy config
├── docker-compose.yml          # Local dev: Redis only
├── docker-compose.prod.yml     # Production: Redis + Nginx
├── package.json                # Root workspace package.json (npm workspaces)
└── Makefile                    # Dev task shortcuts
```

## Directory Purposes

**`apps/web/src/app/`:**
- Purpose: Next.js App Router pages, layouts, and API route handlers
- Contains: Server components, client components, route groups with parenthesized names
- Key files:
  - `apps/web/src/app/layout.tsx` — root HTML shell
  - `apps/web/src/app/middleware.ts` — Supabase session refresh on every request
  - `apps/web/src/app/dashboard/layout.tsx` — auth guard + onboarding gate + sidebar
  - `apps/web/src/app/dashboard/page.tsx` — home dashboard (integration status + context feed)
  - `apps/web/src/app/dashboard/context/` — context pages list and detail view
  - `apps/web/src/app/dashboard/integrations/` — integrations management page
  - `apps/web/src/app/dashboard/settings/` — workspace settings, API keys, team
  - `apps/web/src/app/dashboard/activity/` — activity timeline
  - `apps/web/src/app/(auth)/auth/callback/route.ts` — OAuth PKCE exchange route handler
  - `apps/web/src/app/onboarding/` — multi-step onboarding wizard page

**`apps/web/src/components/`:**
- Purpose: Reusable React components organized by feature area
- Contains:
  - `ui/` — shadcn/ui base primitives (Button, Card, Input, etc.)
  - `onboarding/` — `OnboardingWizard` and step sub-components (`step-workspace.tsx`, `step-ticket-provider.tsx`, etc.)
  - `dashboard/` — `dark-mode-applier.tsx`
  - `icons/` — SVG brand logos as React components
  - `auth/` — auth form components
  - `landing/` — marketing page components

**`apps/web/src/lib/`:**
- Purpose: Shared utilities, API client, Supabase client factories
- Key files:
  - `apps/web/src/lib/api.ts` — typed `apiFetch` / `apiFetchSSE`, all backend API calls
  - `apps/web/src/lib/context-feed.ts` — Supabase-direct reads for context pages feed
  - `apps/web/src/lib/supabase/client.ts` — browser Supabase client
  - `apps/web/src/lib/supabase/server.ts` — server-side Supabase client (Next.js server components)
  - `apps/web/src/lib/utils.ts` — `cn()`, `formatRelativeTime()`, `displayName()`
  - `apps/web/src/lib/sync-progress.ts` — SSE generation progress state machine
  - `apps/web/src/lib/ticket-provider.ts` — ticket provider detection helpers

**`backend/src/routers/`:**
- Purpose: FastAPI route handlers, one file per integration or domain
- Contains: Auth, context, health, integrations, plus per-provider: linear, slack, github, gitlab, notion, jira, fathom, telegram, webhooks, workspaces
- Key files:
  - `backend/src/routers/context.py` — context page CRUD, background generation, SSE stream endpoint, hybrid search
  - `backend/src/routers/webhooks.py` — unified webhook receiver with HMAC verification
  - `backend/src/routers/integrations.py` — `/api/integrations/status` aggregated status endpoint
  - `backend/src/routers/workspaces.py` — workspace info, members, API key management

**`backend/src/services/`:**
- Purpose: Business logic layer; all sync, OAuth, synthesis, and worker logic lives here
- Naming pattern: `{provider}_{concern}.py` (e.g., `github_sync.py`, `github_oauth.py`, `github_webhook.py`)
- Key files:
  - `backend/src/services/synthesis.py` — `generate_context_page()`, `generate_context_page_stream()`
  - `backend/src/services/linking.py` — `find_related_content()`, `find_content_by_source()`, `LinkedItem`
  - `backend/src/services/llm_client.py` — `LLMClient` wrapping OpenAI (gpt-4o-mini), Laminar-traced
  - `backend/src/services/embedding.py` — embedding generation and DB upsert
  - `backend/src/services/embedding_worker.py` — Redis Stream consumer for embedding jobs
  - `backend/src/services/code_index_worker.py` — Redis Stream consumer for code indexing jobs
  - `backend/src/services/sync_scheduler.py` — `run_polling_fallback()` background task
  - `backend/src/services/sync_adapter.py` — `SyncAdapter` protocol, `SyncRunLogger`, `SyncCursor` helpers
  - `backend/src/services/vault.py` — secret storage via Supabase Vault

**`backend/src/models/`:**
- Purpose: SQLModel ORM models, one file per domain entity
- Key files:
  - `backend/src/models/base.py` — `BaseModel`, `TimestampMixin` (UUID PK, soft-delete)
  - `backend/src/models/ticket.py` — `LinearTicket`, `LinearComment`
  - `backend/src/models/jira.py` — `JiraIssue`, `JiraComment`
  - `backend/src/models/context_page.py` — `ContextPage` (status: draft/generating/ready/stale/error)
  - `backend/src/models/integration.py` — `OAuthToken`, `WorkspaceIntegration`, `WebhookDelivery`, `Provider` enum
  - `backend/src/models/sync.py` — `SyncCursor` (per-provider, per-workspace sync state)
  - `backend/src/models/embedding.py` — `Embedding` (pgvector, source_type/source_id polymorphic)
  - `backend/src/models/code_chunk.py` — `CodeChunk` for indexed code

**`backend/src/middleware/`:**
- Purpose: ASGI middleware stack
- Files: `correlation.py` (X-Correlation-ID), `rate_limit.py`, `security_headers.py`

**`backend/src/observability/`:**
- Purpose: Third-party observability wiring
- Files: `logging.py` (structured JSON logs), `sentry.py` (`SentryContextMiddleware`, `init_sentry`), `laminar.py` (`init_laminar`, `@observe` decorator)

**`supabase/migrations/`:**
- Purpose: Ordered SQL migration files applied by Supabase CLI
- Naming: `00NNN_{description}.sql`
- Key migrations:
  - `00008_hybrid_search.sql` — defines `hybrid_search()` pgvector + pg_trgm function
  - `00010_code_chunks.sql` — code chunk storage
  - `00012_onboarding_and_activity.sql` — onboarding state + activity feed tables
  - `00016_api_keys.sql` — workspace API keys for MCP server

**`packages/mcp-server/`:**
- Purpose: MCP server for exposing ContextOS context to AI coding assistants
- Entry: `packages/mcp-server/src/index.ts`
- Auth: `CONTEXTOS_API_KEY` env var (Bearer token to backend)

## Key File Locations

**Entry Points:**
- `backend/src/main.py` — FastAPI app, all router registration, background worker launch
- `apps/web/src/app/layout.tsx` — Next.js root layout
- `apps/web/src/middleware.ts` — Next.js middleware (session refresh)
- `packages/mcp-server/src/index.ts` — MCP server

**Configuration:**
- `backend/src/config.py` — all backend env vars via pydantic-settings
- `apps/web/src/lib/supabase/client.ts` — browser Supabase client
- `apps/web/src/lib/supabase/server.ts` — server Supabase client
- `docker-compose.yml` — local Redis

**Core Logic:**
- `backend/src/services/synthesis.py` — context page generation (blocking + SSE variants)
- `backend/src/services/linking.py` — content linking engine
- `backend/src/services/llm_client.py` — LLM wrapper
- `apps/web/src/lib/api.ts` — all frontend → backend API calls

**Testing:**
- `backend/tests/` — pytest backend tests
- `apps/web/src/app/dashboard/activity/__tests__/` — frontend activity tests
- `apps/web/src/components/onboarding/__tests__/` — onboarding component tests
- `apps/web/src/lib/__tests__/` — lib utility tests

## Naming Conventions

**Files (backend):**
- Services: `{provider}_{concern}.py` — e.g., `github_sync.py`, `notion_oauth.py`, `jira_webhook.py`
- Routers: `{provider}.py` — e.g., `github.py`, `slack.py`
- Models: `{domain}.py` — e.g., `ticket.py`, `context_page.py`, `integration.py`

**Files (frontend):**
- Pages: `page.tsx` within the route directory
- Layouts: `layout.tsx` within the route directory
- Components: `kebab-case.tsx` — e.g., `integration-card.tsx`, `generation-progress.tsx`
- Hooks: `use-{name}.ts` — e.g., `use-context-pages-realtime.ts`

**Directories:**
- Next.js route groups: `(group-name)/` — no URL segment
- Next.js dynamic routes: `[param]/` — e.g., `context/[id]/`
- Test directories: `__tests__/` co-located with the module being tested

## Where to Add New Code

**New Integration (backend):**
- Router: `backend/src/routers/{provider}.py`
- Services: `backend/src/services/{provider}_oauth.py`, `{provider}_sync.py`, `{provider}_webhook.py`
- Model: `backend/src/models/{provider}.py` (extend `BaseModel`)
- Migration: `supabase/migrations/000{N}_{provider}_tables.sql`
- Register router in: `backend/src/main.py`
- Add to linking engine: `backend/src/services/linking.py`
- Add to synthesis stream steps: `backend/src/services/synthesis.py` `connected_sources` list

**New Integration (frontend):**
- API calls: add to `apps/web/src/lib/api.ts`
- Integration card config: `apps/web/src/app/dashboard/integrations/integration-card.tsx`
- Brand logo: `apps/web/src/components/icons/brand-logos.tsx`
- Dashboard home integration list: `apps/web/src/app/dashboard/page.tsx` `INTEGRATIONS` array

**New Dashboard Page:**
- Page: `apps/web/src/app/dashboard/{page-name}/page.tsx`
- Page-specific components: `apps/web/src/components/{feature}/`
- Shared data fetching: `apps/web/src/lib/{feature}.ts`

**New Backend Endpoint (non-integration):**
- Add to most appropriate existing router, or create `backend/src/routers/{domain}.py`
- Register in `backend/src/main.py` if new router

**Utilities:**
- Backend shared helpers: `backend/src/utils/`
- Frontend shared helpers: `apps/web/src/lib/utils.ts`
- Frontend React hooks: `apps/web/src/hooks/`

## Special Directories

**`supabase/migrations/`:**
- Purpose: Immutable SQL migration history
- Generated: No — hand-authored
- Committed: Yes — applied in order by Supabase CLI

**`backend/.venv/`:**
- Purpose: Python virtual environment managed by `uv`
- Generated: Yes
- Committed: No

**`apps/web/.next/`:**
- Purpose: Next.js build output
- Generated: Yes
- Committed: No

**`.planning/`:**
- Purpose: GSD planning artifacts (phases, codebase docs, todos)
- Generated: No — written by GSD agents and humans
- Committed: Yes

**`.claude/worktrees/`:**
- Purpose: Claude agent git worktrees for isolated parallel execution
- Generated: Yes
- Committed: No (auto-created)

---

*Structure analysis: 2026-03-12*
