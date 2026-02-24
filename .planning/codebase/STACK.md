# Technology Stack

**Analysis Date:** 2026-02-24

## Languages

**Primary:**
- TypeScript ^5.7.0 - Frontend (Next.js) and MCP server
- Python >=3.12 - Backend API and workers
- SQL - Database migrations and functions (PostgreSQL)

**Secondary:**
- JavaScript - Build configuration, package scripts
- Shell - Development Makefile commands

## Runtime

**Environment:**
- Node.js 22+ (frontend requirement per README)
- Python 3.12 (backend runtime, Docker image: `python:3.12-slim`)
- Deno support for workers (Redis-based Celery)

**Package Managers:**
- `pnpm` 9+ (frontend monorepo)
- `pip` (Python package management)
- `setuptools` (Python build backend)

**Lockfiles:**
- `pnpm-lock.yaml` (TypeScript dependencies, implied)
- `pyproject.toml` with `poetry`-compatible format (Python dependencies)

## Frameworks

**Web Framework:**
- Next.js ^15.2.0 - Full-stack React framework with server components
  - Includes Turbopack for faster dev builds
  - Runs on Vercel (production target per README)

**API Framework:**
- FastAPI - Python async HTTP framework with automatic OpenAPI docs
  - Uvicorn ^0.28.0+ - ASGI server (Docker CMD runs uvicorn on 0.0.0.0:8000)

**Agentic Framework:**
- LangGraph - Agent orchestration for LLM workflows
- LlamaIndex - Data indexing and retrieval for context synthesis

**MCP (Model Context Protocol):**
- @modelcontextprotocol/sdk ^1.7.0 - Server for AI coding assistants (Claude Code, Cursor, etc.)
  - Exports as executable: `contextos-mcp` CLI command

**UI Framework:**
- React ^19.0.0 - Server and client components
- React DOM ^19.0.0

**UI Component Library:**
- shadcn/ui (implied from dependencies, based on README)
- class-variance-authority ^0.7.1 - Utility for variant-based component styling
- clsx ^2.1.1 - Conditional CSS class composition
- tailwind-merge ^2.6.0 - Merge Tailwind CSS classes without conflicts

**Icon Library:**
- lucide-react ^0.469.0 - Icon components

**Toast/Notification:**
- sonner ^1.7.0 - Toast notifications

## Styling & Build

**CSS Framework:**
- Tailwind CSS v4.0.0 - Utility-first CSS
- @tailwindcss/postcss ^4.0.0 - PostCSS plugin
- PostCSS ^8.5.0 - CSS preprocessing

**Linting & Code Quality:**
- ESLint ^9.0.0 - JavaScript/TypeScript linting
- eslint-config-next ^15.2.0 - Next.js ESLint config
- @eslint/eslintrc ^3.3.0 - ESLint config utilities
- ruff - Python linter and formatter (dev dependency in backend)
- mypy - Python static type checker (dev dependency in backend)

**Type Checking:**
- TypeScript compiler (tsc --noEmit) for frontend
- mypy for backend

## Testing

**Frontend:**
- Not explicitly configured in package.json
- Likely Jest/Vitest (no visible test runner in dependencies)

**Backend:**
- pytest - Python test runner (dev dependency)
- pytest-asyncio - AsyncIO support for pytest (dev dependency)

**Commands:**
```bash
# Frontend type checking
pnpm typecheck  # tsc --noEmit

# Backend tests
cd backend && python -m pytest

# Linting
pnpm lint
cd backend && ruff check .

# Backend type checking
cd backend && mypy src/
```

## Key Dependencies

**Critical — AI & Language Models:**
- anthropic - Anthropic Claude API client (backend)
- langgraph - Agent orchestration library
- llama-index - Data indexing and retrieval
- llama-index-readers-slack - Slack integration for LlamaIndex
- llama-index-readers-notion - Notion integration for LlamaIndex

**Critical — Database & ORM:**
- @supabase/supabase-js ^2.49.0 - JavaScript client (frontend)
- @supabase/ssr ^0.6.0 - Server-side rendering helpers (frontend)
- supabase - Python client (backend)

**Critical — Background Jobs:**
- celery[redis] - Task queue with Redis broker
- redis - Redis Python client

**Critical — Configuration:**
- pydantic >=2.0 - Data validation
- pydantic-settings - Environment variable loading
- python-dotenv - .env file loading

**HTTP Clients:**
- httpx - Async HTTP client (backend integrations)

**Observability:**
- lmnr - Laminar (LLM observability)
- sentry-sdk[fastapi] - Error tracking
- PostHog (frontend observability, implied from env vars)

**Data Validation:**
- zod ^3.24.0 - TypeScript schema validation (MCP server)

**Development Tools:**
- tsx ^4.19.0 - TypeScript execution for Node.js (MCP server)
- @types/node ^22.0.0 - Node.js type definitions
- @types/react ^19.0.0 - React type definitions
- @types/react-dom ^19.0.0 - React DOM type definitions

## Configuration

**Environment Variables:**
- Frontend (exposed to browser): `NEXT_PUBLIC_*` prefix required
  - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - `NEXT_PUBLIC_APP_URL`
  - `NEXT_PUBLIC_SENTRY_DSN`
  - `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`

- Backend (server-only):
  - Database: `SUPABASE_URL`, `SUPABASE_KEY`
  - LLM: `ANTHROPIC_API_KEY`
  - Integrations: `LINEAR_API_KEY`, `SLACK_BOT_TOKEN`, `NOTION_TOKEN`
  - Cache: `REDIS_URL`
  - Observability: `LAMINAR_API_KEY`, `SENTRY_DSN`
  - App: `ENVIRONMENT` (dev/staging/prod), `BACKEND_URL`

**Configuration Files:**
- `.env.example` - Template for required environment variables
- `tsconfig.json` (Next.js, MCP server) - TypeScript compiler options
- `next.config.ts` - Next.js configuration
- `postcss.config.mjs` - PostCSS configuration
- `eslint.config.mjs` - ESLint rules
- `pyproject.toml` - Python project metadata and dependencies

**Python Configuration:**
- `src/config.py` - Pydantic Settings class for environment loading (see INTEGRATIONS.md for detail)

## Database

**Primary Database:**
- PostgreSQL (via Supabase)
- Vector extension: pgvector (1536-dimensional embeddings)
- Text search: pg_trgm extension

**In-Memory Cache:**
- Redis 7-alpine (via Docker Compose)
- Default connection: `redis://localhost:6379/0`
- Purpose: Celery task queue broker

## Containerization

**Docker:**
- Multi-stage build pattern (`backend/Dockerfile`)
- Stage 1: Dependencies layer (install pip packages)
- Stage 2: Production image (copy only necessary files)
- Base image: `python:3.12-slim`
- Runs as non-root: UID 1000 (appuser)
- Exposed port: 8000

**Docker Compose:**
- Redis service (Compose file version not specified, likely v3.8+)
- Celery worker profile: `--profile workers`
- Health checks configured for Redis

## Deployment Targets

**Production Hosting:**
- Frontend: Vercel (Next.js native platform)
- Backend: Railway (Python FastAPI service)

**Local Development:**
- Docker Compose for Redis and Celery workers
- Supabase CLI for local PostgreSQL + Auth
- Node dev server (Next.js)
- Python dev server (uvicorn with --reload)

## Development Commands (Makefile)

```bash
make setup          # Install all dependencies, Docker setup
make dev           # Start Redis (docker), prompt for frontend/backend
make dev-frontend  # cd apps/web && pnpm dev
make dev-backend   # cd backend && uvicorn src.main:app --reload
make dev-workers   # docker compose --profile workers up
make lint          # ESLint + Ruff
make typecheck     # tsc + mypy
make test          # pytest
make clean         # docker down, remove venvs
make db-reset      # supabase db reset
```

---

*Stack analysis: 2026-02-24*
