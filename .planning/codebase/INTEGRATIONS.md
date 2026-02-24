# External Integrations

**Analysis Date:** 2026-02-24

## APIs & External Services

**Issue Tracking:**
- Linear - Development ticket management
  - SDK/Client: Python `supabase` client (stores Linear tokens, uses REST API via integration)
  - Auth: `LINEAR_API_KEY` (API key)
  - Optional OAuth: `LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`, `LINEAR_WEBHOOK_SECRET`
  - Database table: `public.linear_tickets` (denormalized ticket data)
  - OAuth token storage: `public.oauth_tokens` (provider='linear')

**Communication & Chat:**
- Slack - Team communication, channel messages, threads
  - SDK/Client: Python `llama-index-readers-slack` (data source for context indexing)
  - Auth: `SLACK_BOT_TOKEN` (bot token for API calls)
  - OAuth: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`
  - Database table: `public.slack_messages` (messages, threads, reactions)
  - OAuth token storage: `public.oauth_tokens` (provider='slack')

**Knowledge Base:**
- Notion - Team documentation and knowledge management
  - SDK/Client: Python `llama-index-readers-notion` (data source for context indexing)
  - Auth: `NOTION_TOKEN` (API token for OAuth)
  - Optional OAuth: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`
  - Database table: `public.notion_pages` (pages, database entries, wiki content)
  - OAuth token storage: `public.oauth_tokens` (provider='notion')

**LLM & AI:**
- Anthropic Claude - Text generation and reasoning
  - SDK/Client: Python `anthropic` (Claude API client)
  - Auth: `ANTHROPIC_API_KEY` (API key from console.anthropic.com)
  - Used by: `langgraph` agents, synthesis engine
  - Tracked fields: `generation_model`, `generation_tokens_used` in `context_pages` table

**Meeting Transcripts:**
- Google Meet, Zoom, Teams - Video conference transcripts
  - Storage: `public.meeting_transcripts` table (source: 'google_meet', 'zoom', 'teams', 'manual')
  - Processing: Integrated via LlamaIndex (data source for context synthesis)

**Google (OAuth):**
- OAuth provider support in system
  - Supported provider: 'google' in `public.oauth_tokens`
  - No explicit library dependency detected (likely handled via OAuth redirect flow)

## Data Storage

**Primary Database:**
- Supabase (Managed PostgreSQL)
  - URL: `NEXT_PUBLIC_SUPABASE_URL` (frontend), `SUPABASE_URL` (backend)
  - Service Role Key: `SUPABASE_KEY` (backend)
  - Anon Key: `NEXT_PUBLIC_SUPABASE_ANON_KEY` (frontend)
  - Client: `@supabase/supabase-js` (frontend), `supabase` Python package (backend)
  - Features:
    - PostgreSQL 15+ with pgvector extension (1536-dimensional embeddings)
    - Vector similarity search via `match_embeddings()` function
    - Row-level security (RLS) policies per workspace
    - Full-text search via pg_trgm
    - Auto-updated timestamps via triggers

**Caching & Job Queue:**
- Redis 7-alpine
  - Connection: `REDIS_URL=redis://localhost:6379/0`
  - Purpose: Celery broker for background task queue
  - Docker service: `redis:7-alpine`
  - Data persistence: Named volume `redis_data:/data`

**File Storage:**
- Local filesystem only (no S3, cloud storage detected)
- Generated context pages stored in `context_pages` table as markdown content

## Authentication & Identity

**Auth Provider:**
- Supabase Auth (managed by Supabase)
  - Handles: User registration, login, JWT tokens, session management
  - Client: `@supabase/supabase-js` (frontend)
  - Frontend SSR helpers: `@supabase/ssr` (server-side session handling)

**OAuth Integrations:**
- Multi-provider OAuth token storage in `public.oauth_tokens`
  - Providers: linear, slack, notion, google
  - Scopes stored: `scopes` text array in table
  - Refresh tokens: `refresh_token` field (optional per provider)
  - Expiration: `token_expires_at` timestamp
  - Workspace-scoped: Each OAuth token belongs to workspace + user combination

**User Model:**
- `public.profiles` - Extended user data (references `auth.users.id`)
  - Fields: email, full_name, avatar_url, created_at, updated_at
- `public.workspace_members` - Team membership with roles
  - Roles: owner, admin, member (enforced via CHECK constraint)

## Monitoring & Observability

**Error Tracking:**
- Sentry - Error and exception monitoring
  - Backend: `sentry-sdk[fastapi]` integration
  - Frontend: Implied from `NEXT_PUBLIC_SENTRY_DSN`
  - DSN: `SENTRY_DSN` (backend), `NEXT_PUBLIC_SENTRY_DSN` (frontend)

**LLM Observability:**
- Laminar (https://laminar.sh) - LLM trace logging and observability
  - SDK/Client: Python `lmnr` package
  - Auth: `LAMINAR_API_KEY`
  - Purpose: Monitor Claude API calls, token usage, latency, cost

**Product Analytics:**
- PostHog - User event tracking and feature analytics
  - Auth: `NEXT_PUBLIC_POSTHOG_KEY`
  - Host: `NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com`
  - Scope: Frontend events (JavaScript SDK)

**Logs:**
- Structured logging via Sentry (error/exception logs)
- Application logs: Uvicorn access logs (FastAPI), Celery worker logs
- No external log aggregation detected (self-hosted or stdout to Docker logs)

## CI/CD & Deployment

**Frontend Hosting:**
- Vercel - Next.js SaaS platform
  - Auto-deploys from git on push to main
  - Builds with `next build`, starts with `next start`
  - Environment variables prefixed with `NEXT_PUBLIC_` available in browser

**Backend Hosting:**
- Railway - Python app platform
  - Deploys Docker container
  - Exposes port 8000 via uvicorn
  - Auto-scales based on load

**Local CI/CD (Makefile):**
```bash
make lint       # ESLint + Ruff
make typecheck  # TypeScript + mypy
make test       # pytest
```

**No explicit GitHub Actions or external CI detected** (configuration in .github/ not found)

## Background Jobs & Task Queue

**Job Framework:**
- Celery - Distributed task queue
  - Broker: Redis (`REDIS_URL`)
  - Worker: `celery -A src.workers.celery_app worker` (Docker profile)
  - Scheduling: Celery Beat (optional, not visible in current config)

**Worker Implementation:**
- Location: `backend/src/workers/` (directory exists)
- Trigger: Via `docker compose --profile workers up`
- Startup: Reads config from `.env` file

## Webhooks & Callbacks

**Incoming Webhooks:**
- Linear webhook support detected
  - Secret: `LINEAR_WEBHOOK_SECRET`
  - Purpose: Real-time sync of Linear ticket updates
  - Route: Not yet implemented (`api/routes/` is mostly empty with .gitkeep)

- Slack webhook support for incoming events
  - Secret: `SLACK_SIGNING_SECRET`
  - Purpose: Event subscriptions (channel messages, mentions, etc.)

**Outgoing Callbacks:**
- Context synthesis workflow (POST back to Slack/Linear)
  - MCP server stdio channel (for AI assistants)
  - Not yet wired in current scaffold

## Workspace Multi-Tenancy

**Workspace Isolation:**
- `public.workspaces` table (root entity)
  - Fields: id, name, slug (unique), created_at, updated_at
- `public.workspace_members` (RBAC)
  - Links users to workspaces with role-based access
- All data tables scoped to `workspace_id`
  - RLS policies: Users can only access their workspaces
  - Foreign keys cascade on workspace deletion

**Key Tables with Workspace Scope:**
- `oauth_tokens` - Per-workspace OAuth provider configs
- `linear_tickets` - Workspace-specific ticket index
- `slack_messages` - Workspace-specific message archive
- `notion_pages` - Workspace-specific docs index
- `context_pages` - Generated pages per ticket per workspace
- `embeddings` - Vector index scoped to workspace

## Data Flow Summary

```
Integrations (Linear, Slack, Notion)
    ↓
llama-index readers (extract, tokenize)
    ↓
Embeddings generated (OpenAI or Anthropic)
    ↓
pgvector store (Supabase)
    ↓
LangGraph agent (Claude synthesis)
    ↓
context_pages table (markdown output)
    ↓
Frontend display + MCP export
```

---

*Integration audit: 2026-02-24*
