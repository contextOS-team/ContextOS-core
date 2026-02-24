# Phase 1: Foundation - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Database schema, authentication backend + UI, workspace tenancy, and project dependency setup. This is the base layer everything else builds on. Two owners work in parallel: Daulet (backend: FOUND-01 through FOUND-07) and Bekbol (auth UI: DASH-01).

</domain>

<decisions>
## Implementation Decisions

### Database Schema

- Full RLS policies on every table from day one -- workspace_id + RLS on all tables, not just sensitive ones
- Soft deletes everywhere -- every table gets a `deleted_at` timestamp column, records never physically removed
- Supabase CLI migrations -- `supabase migration new` for timestamped SQL files, `supabase db push` for local, `supabase db reset` for clean slate
- UUIDs as primary keys via `gen_random_uuid()` -- matches Supabase Auth user IDs
- All tables created in Phase 1 migration (full schema upfront) -- linear_tickets, slack_messages, context_pages, meeting_transcripts, embeddings all defined now even though populated in later phases
- Separate `linear_comments` table (normalized, FK to ticket) -- enables per-comment embedding and source attribution
- Single `slack_messages` table with self-referencing `thread_ts`/`parent_ts` -- matches Slack's own data model
- Separate `meeting_segments` table (speaker turns with FK to `meeting_transcripts`) -- enables per-segment embedding and fine-grained linking
- Auto-update timestamps via Supabase `moddatetime` extension trigger on every table
- Scalable `workspace_integrations` table instead of columns on workspaces -- (workspace_id, provider, external_id, status) pattern, extends cleanly to Notion v2+

### Embedding Model

- **Deferred to Dulat** -- he will decide the embedding model and dimensions. Schema should use 768 dims as default but be ready to adjust via migration if Dulat picks a different model.

### Authentication Flow

- 7-day session TTL before requiring re-authentication
- JWT verification in FastAPI -- decode and validate Supabase JWT using JWT secret, no round-trip to Supabase per request
- `FastAPI Depends(get_current_user)` dependency injection -- reusable dependency that decodes JWT, looks up user + workspace, injects into route handlers
- Frontend talks to Supabase Auth directly (Next.js + @supabase/ssr) -- backend only receives and validates JWTs, does not proxy auth
- Magic link auto-creates account if no user exists -- frictionless, Supabase supports natively
- Plain 401 JSON for unauthenticated requests -- `{"detail": "Not authenticated"}`, frontend handles redirect to login

### Data Access Layer

- SQLModel + async SQLAlchemy for all data access -- portable away from Supabase if needed in the future. Supabase used for Auth + Realtime only, not CRUD queries
- Application-level workspace filtering -- every query includes `WHERE workspace_id = :current_workspace` via base query helper. RLS policies exist as a safety net but aren't the primary enforcement mechanism
- Cursor-based pagination on all list endpoints from day one -- `{"items": [...], "next_cursor": "...", "has_more": true}` response shape

### Workspace Tenancy

- One user = one workspace in v1 -- no workspace switching, `workspace_id` is a direct FK on users table
- Supabase DB trigger on `auth.users` INSERT creates workspace + user profile atomically -- everything in one transaction
- Everyone equal in v1 -- no admin/owner roles, all workspace members have same permissions
- No workspace deletion in v1 -- workspaces can only be created

### Architecture and Infrastructure

- Router-per-domain structure -- `routers/auth.py`, `routers/workspaces.py`, etc. with FastAPI APIRouter
- Layered architecture -- routers (HTTP) -> services (business logic) -> repositories (DB queries)
- Pydantic BaseSettings + .env for configuration -- reads env vars first (Railway), falls back to .env for local dev. Type-safe, validates on startup
- Health check endpoint -- `GET /api/health` returns `{"status": "ok", "db": "connected"}`
- FastAPI default error responses -- use built-in HTTPException, no custom error schema
- No API versioning in v1 -- routes are `/api/health`, `/api/workspaces`, etc.
- CORS configured from Phase 1 -- FastAPI CORSMiddleware, allowed origins from environment variable (Vercel domain in prod, localhost in dev)
- OpenAPI/Swagger docs enabled in dev, disabled in prod

### Local Development

- Supabase local via `supabase start` -- each developer runs their own local Supabase instance (Postgres + Auth + Realtime)
- Makefile as primary developer interface -- `make dev`, `make migrate`, `make test`, `make seed`
- Separate package managers -- backend uses uv (Python), frontend uses pnpm or npm (Node)
- Seed data for local development -- test workspace + test user for consistent dev state across team

### Deployment

- Railway-ready backend from Phase 1 -- Dockerfile, railway.toml/Procfile, environment variable docs
- Vercel-ready frontend from Phase 1 -- Bekbol's auth pages deploy immediately

### Testing

- Pytest tests for critical paths -- JWT validation, workspace creation trigger, RLS filtering, health check. Sets up testing infrastructure (conftest, fixtures) for all future phases

### Cross-Team Contracts

- OpenAPI spec + auto-generated TypeScript types -- Bekbol imports generated types from FastAPI's OpenAPI spec via codegen tool. Single source of truth
- Separate .env.example per service -- `backend/.env.example` and `frontend/.env.example`
- Dulat's pipeline lives in same FastAPI app as a separate module -- `backend/src/pipeline/`. Called by background tasks, shares DB connection and models. Single deployment in v1
- Trunk-based development -- everyone commits directly to main. Small, frequent commits. No PR review gate

### Claude's Discretion

- Embedding storage strategy (separate table vs column per source table)
- Context page section storage (JSONB vs separate columns)
- Token storage approach in Phase 1 (plain encrypted columns vs Vault early -- SEC-01 is Phase 6)
- Indexing strategy for known query patterns
- Docker-compose restructuring for new stack
- Redis inclusion in Phase 1 deps vs deferring
- Workspace auto-join by domain logic (best UX for dogfooding team)
- Workspace naming on auto-create (best UX pattern)

</decisions>

<specifics>
## Specific Ideas

- "In future we can migrate from Supabase" -- this drove the SQLModel + async decision. Data access layer should not be locked to supabase-py
- Embedding dimensions (768) are a default -- Dulat will decide the actual model and may need a different dimension. Schema should be adjustable
- Auth UI decisions (layout, login/signup page structure, redirect targets) are Bekbol's domain -- backend provides the auth infrastructure, Bekbol decides the presentation
- Scalability matters -- workspace_integrations table chosen over columns specifically for future extensibility (Notion v2+)

</specifics>

<deferred>
## Deferred Ideas

- CI/CD pipeline (GitHub Actions for lint/test/deploy) -- discussed but not deep-dived. Can be set up alongside Phase 1 execution or as a separate effort
- Logging and debugging strategy -- structured logging, request tracing. Basics should come with Phase 1 but detailed strategy deferred

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-24*
