# Architecture

**Analysis Date:** 2026-03-12

## Pattern Overview

**Overall:** Multi-tier monorepo with a Next.js frontend, FastAPI backend, Supabase (PostgreSQL) as the primary datastore, Redis for async job queues, and an MCP server package for AI assistant integrations.

**Key Characteristics:**
- Workspace-scoped multi-tenancy: every DB query is filtered by `workspace_id`
- Webhook-first sync with polling fallback (15-min reconciliation loop per provider)
- Async background workers (embedding, code indexing) consuming Redis Streams
- SSE streaming for real-time context generation progress in the UI
- JWT auth via Supabase; backend validates tokens with `decode_supabase_jwt`

## Layers

**Frontend (Next.js App Router):**
- Purpose: Server-rendered React UI with client-side data fetching
- Location: `apps/web/src/`
- Contains: Pages (App Router), React components, typed API client, Supabase client wrappers
- Depends on: Supabase for auth session + direct DB reads (context pages feed), Backend API for all business operations
- Used by: End users via browser

**Backend API (FastAPI):**
- Purpose: Business logic, OAuth flows, sync orchestration, context generation
- Location: `backend/src/`
- Contains: Routers, services, models, middleware, observability wiring
- Depends on: Supabase/PostgreSQL (via SQLAlchemy async), Redis (job queues), OpenAI (embeddings + LLM), Laminar (LLM tracing), Sentry (error tracking)
- Used by: Frontend (JWT-authenticated), MCP server (API-key authenticated), webhooks (HMAC-verified)

**Data Layer (PostgreSQL via Supabase):**
- Purpose: Persistent storage with RLS, real-time subscriptions, vector search
- Location: `supabase/migrations/`
- Contains: Schema migrations, hybrid vector+full-text search function (`hybrid_search`), RLS policies, moddatetime triggers
- Depends on: pgvector extension, pg_trgm
- Used by: Backend (SQLAlchemy async), Frontend (Supabase JS client for direct reads)

**Background Workers:**
- Purpose: Async embedding generation and code indexing, decoupled from sync hot-path
- Location: `backend/src/services/embedding_worker.py`, `backend/src/services/code_index_worker.py`
- Contains: Redis Stream consumers using `XREADGROUP`
- Depends on: Redis Stream (`embedding:jobs`, `code_index:jobs`), PostgreSQL
- Used by: Launched as supervised asyncio tasks from `backend/src/main.py` lifespan

**Sync Scheduler:**
- Purpose: Polling fallback that runs reconciliation for all providers every 15 minutes
- Location: `backend/src/services/sync_scheduler.py`
- Contains: `run_polling_fallback()` loop, per-provider reconcile functions
- Depends on: Provider sync services, `SyncAdapter` protocol
- Used by: Launched as supervised asyncio task in app lifespan

**MCP Server:**
- Purpose: Model Context Protocol server exposing ContextOS to AI coding assistants
- Location: `packages/mcp-server/src/`
- Contains: Tools (`get_feature_context`, `search_context`, `get_related_work`), resources
- Depends on: ContextOS backend API (API-key auth via `CONTEXTOS_API_KEY`)
- Used by: AI coding assistants (Cursor, Claude, etc.)

## Data Flow

**Context Page Generation (SSE streaming):**

1. Frontend calls `GET /api/context/{identifier}/generate-stream` with Supabase JWT
2. Backend decodes JWT → resolves `workspace_id` via `WorkspaceMember` lookup
3. If ticket missing locally, syncs it from Linear or Jira before proceeding
4. Creates a `ContextPage` row with `status="generating"` immediately (visible in feed)
5. Yields SSE `start` event listing connected providers as steps
6. `find_content_by_source()` iterates providers; yields `step_start`/`step_complete` events per source
7. Linking engine (`linking.py`) combines explicit FK references (weight 1.0) + hybrid vector+FTS search (weight 0.8)
8. `synthesis.py` builds a structured prompt and calls `LLMClient.generate()` (OpenAI GPT-4o-mini, Laminar-traced)
9. `ContextPage` row updated to `status="ready"` with markdown content and sources list
10. Frontend receives `complete` event with `context_page_id`; navigates to detail view

**Integration Sync Flow:**

1. OAuth callback hits `/api/{provider}/callback` → exchanges code for token → stores `OAuthToken` in DB
2. Webhook arrives at `/api/webhooks/{provider}` → HMAC verified → dispatched to background task
3. Background task calls provider-specific sync service (e.g. `github_sync.py`, `notion_sync.py`)
4. Sync service upserts records and calls `enqueue_embedding_job()` → pushes to Redis Stream `embedding:jobs`
5. `embedding_worker.py` consumes job → calls `queue_embedding_generation()` → writes to `embeddings` table
6. Polling fallback (`sync_scheduler.py`) reconciles every 15 min as safety net

**Frontend Auth + DB Direct Read:**

1. `middleware.ts` calls `updateSession()` on every request to refresh Supabase cookie
2. Dashboard layout checks `user_onboarding_state` directly via Supabase client
3. Context feed (`context-feed.ts`) reads `context_pages` table directly via Supabase JS client
4. All backend API calls go through `apiFetch()` in `apps/web/src/lib/api.ts` which attaches Supabase JWT as `Bearer` token

**State Management:**
- No global client-side state manager (no Redux/Zustand). Each page/component fetches its own data.
- Realtime feed updates use Supabase Realtime subscriptions (`use-context-pages-realtime.ts`)

## Key Abstractions

**SyncAdapter Protocol:**
- Purpose: Common interface all provider sync services must implement
- Examples: `backend/src/services/github_sync.py`, `backend/src/services/notion_sync.py`, `backend/src/services/linear_sync.py`
- Pattern: `full_sync()`, `handle_webhook()`, `reconcile()` methods; tracked via `SyncCursor` model

**LinkedItem / LinkingResult:**
- Purpose: Unified container for content items found for a ticket, with source type and relevance score
- Examples: `backend/src/services/linking.py`
- Pattern: Dataclass; populated by explicit FK lookups + hybrid search; consumed by synthesis

**TicketProxy:**
- Purpose: Duck-typed adapter so Jira issues pass through the Linear-centric linking and synthesis code
- Examples: `backend/src/services/synthesis.py`
- Pattern: Dataclass with `from_jira()` factory; maps JiraIssue fields to LinearTicket interface

**BaseModel / TimestampMixin:**
- Purpose: UUID primary key + `created_at`, `updated_at`, `deleted_at` on every model
- Examples: `backend/src/models/base.py`
- Pattern: SQLModel inheritance; soft-delete via `deleted_at IS NULL` filter everywhere

**UserContext:**
- Purpose: Injected into every authenticated route handler via `Depends(get_current_user)`
- Examples: `backend/src/dependencies.py`
- Pattern: Pydantic model with `user_id`, `email`, `workspace_id`; decoded from Supabase JWT

**apiFetch / apiFetchSSE:**
- Purpose: Typed frontend API client with Supabase JWT injection
- Examples: `apps/web/src/lib/api.ts`
- Pattern: Generic fetch wrapper; SSE variant uses fetch + ReadableStream (EventSource cannot send auth headers)

## Entry Points

**Backend Application:**
- Location: `backend/src/main.py`
- Triggers: `uvicorn src.main:app`
- Responsibilities: Registers all routers, configures middleware stack, launches supervised background workers (embedding_worker, polling_fallback, code_index_worker) via asyncio tasks in `lifespan()`

**Frontend Application:**
- Location: `apps/web/src/app/layout.tsx`
- Triggers: Next.js App Router server boot
- Responsibilities: Root HTML shell, font loading, Sentry init, dark mode applier, Toaster

**Frontend Middleware:**
- Location: `apps/web/src/middleware.ts`
- Triggers: Every incoming Next.js request
- Responsibilities: Refreshes Supabase auth cookie session

**Auth Callback:**
- Location: `apps/web/src/app/(auth)/auth/callback/route.ts`
- Triggers: OAuth PKCE code exchange redirect
- Responsibilities: Exchanges code for session, checks onboarding state, redirects to `/dashboard` or `/onboarding`

**MCP Server:**
- Location: `packages/mcp-server/src/index.ts`
- Triggers: `node index.js` (stdio transport)
- Responsibilities: Registers MCP tools, proxies calls to ContextOS backend API

## Error Handling

**Strategy:** Exceptions propagate to FastAPI exception handlers; Sentry captures all unhandled errors. Sync workers log and continue (no crash propagation to API layer).

**Patterns:**
- All routes raise `HTTPException` with explicit status codes
- Sync services catch exceptions per-item and log, not per-batch (partial success)
- SSE stream catches all exceptions and yields `{"event": "error", "message": "..."}` before closing
- Background worker tasks use `_supervised()` wrapper: logs crash, sleeps 5s, restarts

## Cross-Cutting Concerns

**Logging:** Structured logging via `configure_logging()` (`backend/src/observability/logging.py`). Correlation IDs injected by `CorrelationIdMiddleware`. `SyncRunLogger` context manager adds run-scoped log context for all sync operations.

**Validation:** Pydantic/pydantic-settings for config and request models. SQLModel for DB models. Frontend uses TypeScript interfaces matching backend response shapes.

**Authentication:** Supabase JWT on all user-facing endpoints (decoded in `backend/src/dependencies.py`). HMAC-SHA256 verification on all webhook endpoints. API-key auth (hashed with bcrypt) for MCP server access. Rate limiting via `RateLimitMiddleware`.

---

*Architecture analysis: 2026-03-12*
