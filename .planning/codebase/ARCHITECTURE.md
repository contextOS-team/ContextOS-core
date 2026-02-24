# Architecture

**Analysis Date:** 2026-02-24

## Pattern Overview

**Overall:** Distributed multi-tenant service with integrated AI synthesis and background job processing.

**Key Characteristics:**
- Multi-tenant architecture with workspace isolation enforced at database level (Row Level Security)
- API-first design with async job processing (Celery)
- AI-driven context generation using LangGraph and Claude
- Real-time integration with Linear, Slack, and Notion
- Vector similarity search for semantic retrieval via pgvector

## Layers

**Frontend (Next.js 15 & React 19):**
- Purpose: Dashboard, settings, onboarding, and context page display
- Location: `apps/web/`
- Contains: React components, Next.js app router pages, Tailwind CSS, shadcn/ui
- Depends on: Supabase Auth (via `@supabase/ssr`), Backend API, Supabase client SDK
- Used by: End users accessing web interface

**Backend API (FastAPI):**
- Purpose: REST API for context operations, webhook handlers, ticket management
- Location: `backend/src/api/`
- Contains: Route definitions, request/response models, business logic
- Depends on: Configuration, database clients, external service integrations
- Used by: Frontend, webhooks from Linear/Slack/Notion, MCP server

**Agent Layer (LangGraph):**
- Purpose: Multi-step agentic workflows for context synthesis
- Location: `backend/src/agents/`
- Contains: LangGraph graph definitions, tool definitions, decision logic
- Depends on: Anthropic Claude API, embedding store, ingestion layers
- Used by: API endpoints, background workers

**Ingestion Layer:**
- Purpose: Ingest and normalize data from external sources (Linear, Slack, Notion, meeting transcripts)
- Location: `backend/src/ingestion/`
- Contains: Service-specific ingestion logic, OAuth token management, data normalization
- Depends on: External service SDKs/APIs, database
- Used by: Background workers (Celery tasks), webhook handlers

**Embeddings Layer:**
- Purpose: Generate and manage vector embeddings for semantic search
- Location: `backend/src/embeddings/`
- Contains: Embedding generation (Claude API), storage in pgvector, similarity search
- Depends on: Anthropic Embeddings API, Supabase database
- Used by: Synthesis agent (for retrieval), search endpoints

**Synthesis Layer:**
- Purpose: Generate markdown context pages by combining retrieved sources
- Location: `backend/src/synthesis/`
- Contains: Context page generation, markdown formatting, token tracking
- Depends on: Anthropic Claude API, embeddings layer, agent orchestration
- Used by: Agents, API endpoints

**Worker Layer (Celery + Redis):**
- Purpose: Execute async background jobs for ingestion and synthesis
- Location: `backend/src/workers/`
- Contains: Celery task definitions, job scheduling
- Depends on: Redis, all other backend layers
- Used by: API (for async operations), webhooks (for async processing)

**MCP Server (Model Context Protocol):**
- Purpose: Provide context tools to AI coding assistants (Claude Code, Cursor, etc.)
- Location: `packages/mcp-server/`
- Contains: MCP protocol implementation, resource definitions, tool handlers
- Depends on: @modelcontextprotocol/sdk, Zod for validation
- Used by: AI coding assistants via stdio

**Database (Supabase PostgreSQL + pgvector):**
- Purpose: Multi-tenant data storage with RLS, vector similarity search
- Location: `supabase/migrations/00001_initial_schema.sql`
- Contains: All tables (workspaces, profiles, oauth_tokens, tickets, embeddings, context_pages)
- Depends on: PostgreSQL extensions (pgvector, pg_trgm)
- Used by: All backend layers

## Data Flow

**Context Generation Flow:**

1. User triggers context generation for a Linear ticket via frontend
2. Frontend calls `POST /api/context/{ticket_id}/generate`
3. Backend API queues async Celery task for synthesis
4. Celery worker invokes agent with ticket context
5. Agent queries embeddings store for related Slack messages, Notion pages, meeting transcripts
6. Agent calls Claude API to synthesize context page
7. Generated content + metadata written to `context_pages` table
8. Frontend polls or subscribes for status updates
9. User views generated context page

**Ingestion Flow:**

1. External service webhook arrives (e.g., Linear ticket update, Slack message)
2. Backend webhook handler normalizes data and stores in appropriate table (linear_tickets, slack_messages, etc.)
3. Async task queued to generate/update embeddings for new content
4. Celery worker calls Claude Embeddings API
5. Vector stored in `embeddings` table with source reference

**Search/Retrieval Flow:**

1. Query text from agent or search endpoint
2. Generate embedding for query text
3. Call PostgreSQL `match_embeddings()` function for vector similarity search
4. Returns top-K most similar source documents (by cosine distance threshold 0.7)
5. Retrieved sources enriched with full content from source tables
6. Sent to synthesis layer for context generation

**State Management:**
- Multi-tenant isolation: `workspace_id` present in all queries via RLS policies
- User identity: `auth.uid()` from Supabase Auth in RLS predicates
- Context page status: `status` field tracks (draft → generating → ready → stale)
- OAuth tokens: Stored per workspace + user + provider for renewal on expiry

## Key Abstractions

**Workspace:**
- Purpose: Multi-tenant boundary; isolates teams and their data
- Examples: `public.workspaces` table, workspace_id foreign keys throughout schema
- Pattern: All data queries filtered by workspace membership via RLS

**Context Page:**
- Purpose: Generated knowledge artifact for a Linear ticket
- Examples: `public.context_pages` table with markdown content and source tracking
- Pattern: Immutable output; new versions create new rows; old pages marked stale

**OAuth Token:**
- Purpose: Store and manage third-party integration credentials per user per workspace
- Examples: `public.oauth_tokens` table with provider, access_token, refresh_token
- Pattern: Encrypted at rest by Supabase; refresh logic handles expiration

**Embedding:**
- Purpose: Vector representation of source content for semantic search
- Examples: `public.embeddings` table with vector(1536) and source_type discriminator
- Pattern: 1 embedding per source item; updated on content change (via content_hash)

**Source:**
- Purpose: Any ingestible content (ticket, message, page, transcript, generated context)
- Examples: linear_ticket, slack_message, notion_page, meeting_transcript, context_page
- Pattern: Discriminated union (source_type field in embeddings); enables polymorphic search

## Entry Points

**Frontend Entry Point:**
- Location: `apps/web/src/app/`
- Triggers: Browser navigation to Next.js app
- Responsibilities: Render dashboard, handle auth redirects, display context pages

**API Entry Point:**
- Location: `backend/src/api/` (future implementation)
- Triggers: HTTP requests from frontend, webhooks from external services
- Responsibilities: Route requests, validate payloads, orchestrate backend layers

**Worker Entry Point:**
- Location: `backend/src/workers/` (future implementation)
- Triggers: Celery task queue messages from Redis
- Responsibilities: Execute background jobs (ingestion, embeddings, synthesis)

**Webhook Entry Point:**
- Location: `backend/src/api/routes/` (future implementation)
- Triggers: Linear webhook, Slack event subscriptions, etc.
- Responsibilities: Validate signatures, normalize payloads, queue background tasks

**MCP Entry Point:**
- Location: `packages/mcp-server/src/index.ts`
- Triggers: AI coding assistant (Claude Code, Cursor) starts MCP server
- Responsibilities: Expose context tools/resources, serve requests over stdio

## Error Handling

**Strategy:** Graceful degradation with observability.

**Patterns:**
- API errors wrapped in structured exception format (future implementation)
- Unhandled errors captured by Sentry for monitoring
- LLM call failures queue for retry via Celery
- Invalid OAuth tokens trigger re-auth flow
- Database constraint violations surface as semantic errors (e.g., "ticket not found")
- RLS violations return 403 Forbidden at PostgreSQL level

## Cross-Cutting Concerns

**Logging:** Print to stdout (captured by Docker/Railway logs); structured logs via Sentry on error

**Validation:** Pydantic models for request payloads (backend); Zod for MCP payloads; database constraints as final validation layer

**Authentication:** Supabase Auth with JWT; verified via `auth.uid()` in RLS policies; frontend uses `@supabase/ssr` for middleware auth

**Authorization:** Row Level Security at PostgreSQL level ensures workspace isolation; no app-level permission checks needed (RLS is authoritative)

**Rate Limiting:** Not yet implemented; candidates: FastAPI SlowAPI, Redis-backed token bucket

**Observability:** Laminar for LLM tracing, Sentry for errors, PostHog for frontend analytics (env vars present in `.env.example`)

---

*Architecture analysis: 2026-02-24*
