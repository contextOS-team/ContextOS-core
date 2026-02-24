# Codebase Structure

**Analysis Date:** 2026-02-24

## Directory Layout

```
ContextOS-core/
├── apps/
│   └── web/                    # Next.js 15 frontend application
├── backend/                    # Python FastAPI backend service
├── packages/
│   └── mcp-server/             # TypeScript MCP server for AI assistants
├── supabase/                   # Database migrations and configuration
├── .env.example                # Example environment variables
├── .gitignore                  # Git ignore rules
├── docker-compose.yml          # Local development services (Redis, Celery)
├── Makefile                    # Development and build commands
└── README.md                   # Project overview and setup instructions
```

## Directory Purposes

**`apps/web/`:**
- Purpose: Next.js 15 + React 19 frontend application
- Contains: App router pages, React components, Tailwind CSS styling, utilities
- Key files: `package.json`, `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`
- Entry: `src/app/` (Next.js app router root)

**`apps/web/src/app/`:**
- Purpose: Next.js app router pages and layouts
- Contains: Route definitions, server components, authentication layouts
- Stub status: `.gitkeep` placeholder; real pages TBD

**`apps/web/src/components/`:**
- Purpose: Reusable React components
- Contains: UI components, form components, dashboard widgets
- Stub status: `.gitkeep` placeholder; shadcn/ui components to be added

**`apps/web/src/lib/`:**
- Purpose: Utility functions and client libraries
- Contains: Supabase client initialization, middleware, helpers
- Stub status: `.gitkeep` placeholder; auth utilities TBD

**`backend/`:**
- Purpose: Python FastAPI backend service
- Contains: API routes, agent logic, ingestion handlers, workers, configuration
- Key files: `pyproject.toml`, `Dockerfile`, `ruff.toml`
- Python version: 3.12+

**`backend/src/`:**
- Purpose: Main Python package root
- Contains: All backend code organized into functional modules

**`backend/src/config.py`:**
- Purpose: Centralized environment configuration
- Pattern: `Settings` class using Pydantic BaseSettings with @lru_cache singleton
- Env vars loaded from: `../.env` (relative path works in both CLI and Docker contexts)
- All values optional with sensible defaults (ENVIRONMENT=dev, REDIS_URL=localhost:6379/0)

**`backend/src/api/`:**
- Purpose: REST API endpoints and request handlers
- Contains: Router definitions, route handlers for context, search, webhooks
- Structure: `routes/` subdirectory groups related endpoints
- Stub status: `.gitkeep` and `routes/.gitkeep` placeholders

**`backend/src/api/routes/`:**
- Purpose: Individual route modules grouped by feature
- Planned routes: `context.py`, `search.py`, `tickets.py`, `webhooks.py`
- Pattern: Each route file defines endpoint handlers

**`backend/src/agents/`:**
- Purpose: LangGraph agents for context synthesis
- Contains: Agent graph definitions, tool definitions, decision logic
- Stub status: `.gitkeep` placeholder

**`backend/src/ingestion/`:**
- Purpose: External data source connectors
- Contains: Service-specific ingestion logic (Linear, Slack, Notion, transcripts)
- Stub status: `.gitkeep` placeholder

**`backend/src/embeddings/`:**
- Purpose: Vector embedding generation and storage
- Contains: Embedding generation logic, vector store interface, similarity search
- Stub status: `.gitkeep` placeholder

**`backend/src/synthesis/`:**
- Purpose: Context page generation from retrieved sources
- Contains: Markdown generation, content assembly, token counting
- Stub status: `.gitkeep` placeholder

**`backend/src/workers/`:**
- Purpose: Celery background job definitions
- Contains: Async task definitions, job scheduling
- Stub status: `.gitkeep` placeholder
- Dependency: Redis (via docker-compose.yml)

**`packages/mcp-server/`:**
- Purpose: MCP (Model Context Protocol) server for AI coding assistants
- Contains: MCP protocol handlers, resource definitions, tool implementations
- Key files: `package.json`, `tsconfig.json`
- Entry: `src/index.ts` (future)
- Output: `dist/index.js` (compiled from TypeScript)
- Stub status: `src/`, `src/resources/`, `src/tools/` all have `.gitkeep` placeholders

**`supabase/`:**
- Purpose: Database schema, migrations, and local configuration
- Contains: PostgreSQL migrations, seed data, Supabase local setup config

**`supabase/migrations/`:**
- Purpose: Version-controlled database schema changes
- Key file: `00001_initial_schema.sql` (complete initial schema)
- Schema defines:
  - Multi-tenant tables: workspaces, profiles, workspace_members
  - Integration storage: oauth_tokens, linear_tickets, slack_messages, notion_pages, meeting_transcripts
  - Core output: context_pages
  - Search infrastructure: embeddings table with pgvector
  - RLS policies: Workspace-scoped access control
  - Triggers: Auto-updated_at timestamp management
  - Functions: `match_embeddings()` for vector similarity search

**`supabase/config.toml`:**
- Purpose: Local Supabase instance configuration
- Contains: Port mappings, studio settings

**`supabase/seed.sql`:**
- Purpose: Initial data population for development
- Contains: Test workspace, test users, sample data

## Key File Locations

**Entry Points:**
- Frontend: `apps/web/src/app/` (Next.js app router)
- Backend API: `backend/src/api/` (FastAPI routes TBD)
- Workers: `backend/src/workers/` (Celery tasks TBD)
- MCP Server: `packages/mcp-server/src/index.ts` (TBD)

**Configuration:**
- Frontend config: `apps/web/next.config.ts`, `apps/web/tsconfig.json`
- Backend config: `backend/src/config.py`, `backend/pyproject.toml`
- MCP config: `packages/mcp-server/tsconfig.json`
- Database config: `supabase/config.toml`
- Project env vars: `.env.example` (copy to `.env` and fill in)
- Docker services: `docker-compose.yml`

**Core Logic:**
- API routes: `backend/src/api/routes/` (endpoint handlers)
- Agents: `backend/src/agents/` (LangGraph workflows)
- Ingestion: `backend/src/ingestion/` (data source connectors)
- Synthesis: `backend/src/synthesis/` (context generation)
- Embeddings: `backend/src/embeddings/` (vector management)
- Workers: `backend/src/workers/` (async job execution)

**Database:**
- Schema: `supabase/migrations/00001_initial_schema.sql`
- Seed: `supabase/seed.sql`

**Testing:**
- Backend tests: Run via `make test` or `pytest` from `backend/` directory
- Frontend linting: Run via `make lint` or `pnpm lint` from `apps/web/`
- Type checking: Run via `make typecheck`

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `config.py`, `celery_app.py`)
- TypeScript files: `camelCase.ts` or `PascalCase.tsx` for components
- Migration files: `YYYYMMDD_description.sql` (e.g., `00001_initial_schema.sql`)
- Config files: lowercase with dots (e.g., `tsconfig.json`, `next.config.ts`, `pyproject.toml`)

**Directories:**
- All lowercase, plural for collections (e.g., `apps/`, `packages/`, `routes/`, `workers/`)
- Functional/domain grouping: `agents/`, `api/`, `embeddings/`, `ingestion/`, `synthesis/`

**Database Tables:**
- Plural names: `workspaces`, `profiles`, `oauth_tokens`, `linear_tickets`, `slack_messages`
- Columns: `snake_case` (e.g., `workspace_id`, `user_id`, `created_at`, `updated_at`)
- Foreign keys: `{table_singular}_id` (e.g., `workspace_id` references workspaces.id)

**API Routes:**
- Plural resource names: `/api/contexts`, `/api/tickets`, `/api/search`
- Action suffix: `/api/contexts/{id}/generate`, `/api/webhooks/linear`

**Environment Variables:**
- Backend: UPPERCASE_WITH_UNDERSCORES (e.g., `SUPABASE_URL`, `ANTHROPIC_API_KEY`)
- Frontend exposed vars: `NEXT_PUBLIC_` prefix (e.g., `NEXT_PUBLIC_SUPABASE_URL`)

## Where to Add New Code

**New Feature (e.g., new context synthesis strategy):**
- Primary code: `backend/src/synthesis/`
- Tests: `backend/tests/synthesis/` (TBD)
- Entry: Expose via `backend/src/api/routes/context.py`

**New Component/Module (e.g., new UI widget):**
- Frontend implementation: `apps/web/src/components/`
- Library exports: `apps/web/src/lib/`
- Styling: Use Tailwind CSS v4 + shadcn/ui

**New Integration (e.g., GitHub ingestion):**
- Ingestion logic: `backend/src/ingestion/github.py`
- Database table: Add to `supabase/migrations/00002_add_github.sql`
- OAuth token: Update `public.oauth_tokens` check constraint for provider
- Worker tasks: Add to `backend/src/workers/tasks.py`

**Utilities:**
- Backend shared helpers: `backend/src/utils.py` or `backend/src/lib/`
- Frontend shared helpers: `apps/web/src/lib/utils.ts`, `apps/web/src/lib/supabase/`
- MCP utilities: `packages/mcp-server/src/utils.ts`

**Tests:**
- Backend unit tests: `backend/tests/` directory (mirror src/ structure)
- Run: `make test` or `cd backend && pytest`
- Frontend tests: TBD (Jest/Vitest setup available via Next.js)

## Special Directories

**`.git/`:**
- Purpose: Git repository metadata and history
- Generated: Yes
- Committed: No (git metadata, not source code)

**`.next/`:**
- Purpose: Next.js build output and cache
- Generated: Yes (on `pnpm build` or `next dev`)
- Committed: No (in `.gitignore`)

**`backend/.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes (on `python -m venv .venv`)
- Committed: No (in `.gitignore`)

**`node_modules/`:**
- Purpose: npm dependencies
- Generated: Yes (on `pnpm install`)
- Committed: No (in `.gitignore`)

**`dist/` (packages/mcp-server/):**
- Purpose: Compiled TypeScript output
- Generated: Yes (on `npm run build`)
- Committed: No (in `.gitignore`)

**`.planning/codebase/`:**
- Purpose: Generated analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes (by mapping agents)
- Committed: Yes (source for planning)

---

*Structure analysis: 2026-02-24*
