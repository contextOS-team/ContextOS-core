# Codebase Concerns

**Analysis Date:** 2026-02-24

## Tech Debt

**Incomplete Backend Implementation:**
- Issue: 13 placeholder directories exist with only `.gitkeep` files. Most business logic is missing (agents, API routes, embeddings, ingestion, synthesis, workers).
- Files: `backend/src/agents/`, `backend/src/api/routes/`, `backend/src/embeddings/`, `backend/src/ingestion/`, `backend/src/synthesis/`, `backend/src/workers/`
- Impact: Backend cannot serve any API requests, process background jobs, or generate context pages. Current state is skeleton-only.
- Fix approach: Implement core handlers in these directories: agents (LangGraph workflows), routes (FastAPI endpoints for context generation), embeddings (vector operations), ingestion (data collection), synthesis (Claude calls), workers (Celery tasks).

**Frontend Application Structure Removed:**
- Issue: All React page components were stripped in recent commit. Only directory structure remains (`app/.gitkeep`, `components/.gitkeep`, `lib/.gitkeep`).
- Files: `apps/web/src/app/`, `apps/web/src/components/`, `apps/web/src/lib/`
- Impact: Next.js app cannot render any pages. No authentication UI, dashboard, or settings UI exists.
- Fix approach: Rebuild page templates in `apps/web/src/app/` (layout, authentication pages, dashboard), add Supabase client utilities in `lib/`, build UI components in `components/`.

**Database Schema Without Application Usage:**
- Issue: Full Supabase schema exists (`supabase/migrations/00001_initial_schema.sql`) with 10 tables, RLS policies, pgvector integration, and complex functions. However, no backend code references these tables.
- Files: `supabase/migrations/00001_initial_schema.sql`
- Impact: Database layer is disconnected from application. ORM models, queries, and migrations are missing. Risk of schema drift when implementation begins.
- Fix approach: Add Supabase ORM/client layer in backend (SQLAlchemy or direct async client), verify schema matches API contracts before adding data access code.

**MCP Server Without Implementation:**
- Issue: MCP server scaffold exists with only `.gitkeep` files in resources and tools directories.
- Files: `packages/mcp-server/src/resources/`, `packages/mcp-server/src/tools/`
- Impact: MCP server cannot serve Claude Code or other AI assistants with any tools or resources.
- Fix approach: Implement MCP resources (workspace context) and tools (ticket search, context generation).

## Known Configuration Issues

**Dependency Version Mismatches:**
- Issue: Recently fixed PyPI package name (`laminai` → `lmnr`), but no error handling if older wheels cached in Docker.
- Files: `backend/pyproject.toml`
- Impact: Docker builds may fail silently if old cached wheels are used.
- Workaround: Docker image rebuilds with `--no-cache` or `docker system prune`.

**Environment Variable Inconsistency:**
- Issue: Backend config (`backend/src/config.py`) defines 9 env vars but `.env.example` documents 12+. Some frontend-only vars (NEXT_PUBLIC_POSTHOG_KEY) may cause confusion about where they're used.
- Files: `backend/src/config.py`, `.env.example`
- Impact: New developers may not know which vars are required vs optional, leading to setup failures.
- Fix approach: Add comments in config.py to document which vars are required (SUPABASE_URL, ANTHROPIC_API_KEY) vs optional (observability tools).

**Dockerfile Complexity with Missing Source:**
- Issue: Builder stage creates stub `src/__init__.py` to resolve dependencies, but build assumes `src/` structure. If module structure changes, Docker build breaks.
- Files: `backend/Dockerfile`
- Impact: Docker builds are fragile to refactoring. Developer must rebuild image if structure changes.
- Fix approach: Use direct dependency installation without creating stub structure, or document the constraint.

## Security Considerations

**SQL Injection Risk in RLS Policies:**
- Issue: All RLS policies use subqueries checking `auth.uid()` against `workspace_members`. If auth system is compromised, workspace isolation is lost.
- Files: `supabase/migrations/00001_initial_schema.sql` (lines 214-267)
- Current mitigation: Supabase's built-in `auth.uid()` function is secure. Policies are correctly scoped.
- Recommendations: Add audit logging for workspace membership changes. Test RLS policies in integration tests before deployment.

**Exposed Secrets in Environment Configuration:**
- Issue: `.env.example` includes placeholders for all secrets (LINEAR_API_KEY, SLACK_BOT_TOKEN, NOTION_TOKEN, ANTHROPIC_API_KEY). Developers may accidentally commit `.env` with real values.
- Files: `.env.example`, `.gitignore`
- Current mitigation: `.gitignore` includes `.env*` and `secrets/` patterns.
- Recommendations: Add pre-commit hook to check for .env commits, use Supabase vault or backend secrets manager instead of .env in production.

**OAuth Token Storage Without Encryption:**
- Issue: Database schema stores `access_token` and `refresh_token` as plaintext in `oauth_tokens` table.
- Files: `supabase/migrations/00001_initial_schema.sql` (line 46-47)
- Impact: If database is compromised, all integration credentials are exposed. Critical for Linear, Slack, Notion integrations.
- Fix approach: Implement encryption at rest (pgcrypto) or use Supabase vault. Add field-level encryption for sensitive tokens.

**Sentry DSN Exposed to Frontend:**
- Issue: `.env.example` includes NEXT_PUBLIC_SENTRY_DSN, which means error tracking can be poisoned from browser.
- Files: `.env.example` (line 41)
- Impact: Low risk for this specific app, but best practice is to use separate backend-only Sentry project.
- Recommendations: Use separate Sentry DSN for frontend (restricted) and backend (full access).

## Performance Bottlenecks

**Vector Search Without Connection Pooling:**
- Issue: Backend will use Supabase Python client without connection pooling configuration. With many concurrent requests for embeddings, database connections may exhaust.
- Files: `backend/src/config.py`, `supabase/migrations/00001_initial_schema.sql` (match_embeddings function)
- Impact: Under load, 429/503 errors from database connection exhaustion.
- Improvement path: Configure Supabase connection pooling, implement client-side caching with Redis for frequent queries.

**HNSW Index Without Maintenance:**
- Issue: pgvector HNSW index created without maintenance schedule. As embeddings table grows, index performance degrades without VACUUM ANALYZE.
- Files: `supabase/migrations/00001_initial_schema.sql` (line 179)
- Impact: Vector searches slow down over months without explicit reindexing.
- Improvement path: Add monthly VACUUM ANALYZE task via pg_cron, monitor vector search latency.

**Missing API Rate Limiting:**
- Issue: FastAPI backend structure exists but no rate limiting middleware defined. Celery background jobs also have no rate limits.
- Files: `backend/src/api/`
- Impact: Backend can be DOS'ed by rapid requests or Celery can be overwhelmed by malicious task queuing.
- Improvement path: Add `slowapi` rate limiter to FastAPI, implement Celery task rate limits per user.

**Embedding Generation Without Batching:**
- Issue: No evidence of batch embedding operations. If context synthesis calls Claude 100+ times per page, latency is high.
- Files: `backend/src/synthesis/`
- Impact: Context page generation slow for complex tickets with many sources.
- Improvement path: Batch Claude API calls, implement request queuing.

## Fragile Areas

**Row-Level Security Policy Complexity:**
- Files: `supabase/migrations/00001_initial_schema.sql` (lines 199-267)
- Why fragile: 9 tables have RLS policies with recursive subqueries. If workspace_members table is modified, all policies could silently break.
- Safe modification: Always test RLS policies in Supabase local dev after schema changes. Add integration tests verifying users cannot see other workspace data.
- Test coverage: No test data or RLS-specific tests exist.

**Monolithic Migration File:**
- Files: `supabase/migrations/00001_initial_schema.sql` (321 lines)
- Why fragile: All schema is in one migration. If deployment fails mid-way, rollback loses everything. No intermediate migrations exist for incremental changes.
- Safe modification: Split into multiple migrations (one per table type: users, integrations, data, search).
- Test coverage: Seed data exists but no migration rollback tests.

**Docker Build Dependent on Source Structure:**
- Files: `backend/Dockerfile`
- Why fragile: Dockerfile assumes `src/` directory exists before pip install. Refactoring module structure breaks builds.
- Safe modification: Document the src/ requirement or make it configurable via BUILD_ARG.
- Test coverage: No Docker build tests in CI.

**Supabase Config Hardcoded for Local Development:**
- Files: `supabase/config.toml`
- Why fragile: `site_url = "http://localhost:3000"` hardcoded. Production deploys require manual config changes.
- Safe modification: Use env substitution in config.toml (e.g., `site_url = "env(SUPABASE_SITE_URL)"`).

## Missing Critical Features

**No Main Application Entry Point:**
- Problem: Backend has no `src/main.py` file. Makefile references `uvicorn src.main:app` but file does not exist.
- Blocks: Any backend development, local testing, deployment.
- Priority: Critical — must exist before any backend code can run.

**No Celery Worker Configuration:**
- Problem: `docker-compose.yml` references `src.workers.celery_app` but no worker file exists.
- Blocks: Background job processing (ingestion, embedding generation).
- Priority: Critical for async processing to work.

**No Database Connection Handling:**
- Problem: No ORM configuration (SQLAlchemy, Tortoise, Piccolo). Supabase client initialization missing.
- Blocks: Any database operation.
- Priority: Critical for entire application.

**No API Route Handlers:**
- Problem: `backend/src/api/routes/` exists but empty. No endpoints for context generation, ticket search, workspace management.
- Blocks: Frontend cannot communicate with backend.
- Priority: Critical for MVP.

**No Authentication Middleware:**
- Problem: No JWT verification or Supabase Auth integration in backend. All endpoints are unauthenticated.
- Blocks: Multi-tenant isolation, user-specific operations.
- Priority: High — critical for security.

## Test Coverage Gaps

**No Backend Tests:**
- What's not tested: Database models, API endpoints, Celery tasks, agent workflows, embedding operations.
- Files: `backend/` (no test directory)
- Risk: Regressions in core logic go undetected. Schema changes break queries silently.
- Priority: High — critical before production.

**No Frontend Tests:**
- What's not tested: Component rendering, form validation, API client interactions, auth flow.
- Files: `apps/web/src/` (no test files)
- Risk: UI bugs in critical paths (login, workspace creation) reach production.
- Priority: Medium — less critical for API-first product.

**No MCP Integration Tests:**
- What's not tested: MCP resource/tool schemas, Claude Code integration, error handling.
- Files: `packages/mcp-server/` (no tests)
- Risk: AI assistants cannot use tools/resources correctly.
- Priority: Medium.

**No RLS Policy Tests:**
- What's not tested: Row-level security enforcement, workspace isolation, membership checks.
- Files: `supabase/migrations/` (no test data)
- Risk: Users can access data from other workspaces.
- Priority: Critical.

**No Docker Build Tests:**
- What's not tested: Docker image builds, Dockerfile logic, dependency installation.
- Files: `backend/Dockerfile`
- Risk: Silent build failures in CI/CD.
- Priority: Medium.

---

*Concerns audit: 2026-02-24*
