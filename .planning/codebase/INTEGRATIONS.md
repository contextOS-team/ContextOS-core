# External Integrations

**Analysis Date:** 2026-03-12

## APIs & External Services

**Ticket Providers (source-of-truth for engineering work):**
- **Linear** — Primary ticket provider; full sync of issues and comments via REST + GraphQL
  - OAuth: `LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`
  - Webhook secret: `LINEAR_WEBHOOK_SECRET`
  - Services: `backend/src/services/linear_oauth.py`, `backend/src/services/linear_sync.py`, `backend/src/services/linear_webhook.py`, `backend/src/services/linear_graphql.py`
  - Router: `backend/src/routers/linear.py`

- **Jira** — Secondary ticket provider (Atlassian Cloud OAuth2)
  - OAuth: `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET`
  - Webhook secret: `JIRA_WEBHOOK_SECRET`
  - Services: `backend/src/services/jira_oauth.py`, `backend/src/services/jira_sync.py`, `backend/src/services/jira_webhook.py`
  - Router: `backend/src/routers/jira.py`
  - DB tables: `supabase/migrations/00019_jira_tables.sql`

**Code Hosting (PR context, code indexing):**
- **GitHub** — GitHub App (not OAuth App); installation-based access for repos
  - App credentials: `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_PRIVATE_KEY`
  - Used to clone repos (via installation tokens) for `tree-sitter` code indexing
  - Services: `backend/src/services/github_oauth.py`, `backend/src/services/github_sync.py`, `backend/src/services/github_webhook.py`, `backend/src/services/github_repos.py`, `backend/src/services/github_common.py`, `backend/src/services/github_linking.py`
  - Router: `backend/src/routers/github.py`
  - DB tables: `supabase/migrations/000040_github_tables.sql`

- **GitLab** — OAuth2 integration for MR context
  - OAuth: `GITLAB_CLIENT_ID`, `GITLAB_CLIENT_SECRET`
  - Webhook secret: `GITLAB_WEBHOOK_SECRET`
  - Services: `backend/src/services/gitlab_oauth.py`, `backend/src/services/gitlab_sync.py`, `backend/src/services/gitlab_webhook.py`, `backend/src/services/gitlab_repos.py`, `backend/src/services/gitlab_common.py`, `backend/src/services/gitlab_linking.py`
  - Router: `backend/src/routers/gitlab.py`
  - DB tables: `supabase/migrations/000190_gitlab_tables.sql`

**Communication (message context):**
- **Slack** — OAuth2 with Events API; syncs channel messages for context
  - App credentials: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`
  - Bot token: `SLACK_BOT_TOKEN`
  - HTTPS redirect required: `SLACK_REDIRECT_URI` (must override in dev with ngrok URL)
  - SDK: `slack-bolt` Python package
  - Services: `backend/src/services/slack_oauth.py`, `backend/src/services/slack_channels.py`, `backend/src/services/slack_events.py`
  - Router: `backend/src/routers/slack.py`

- **Telegram** — Bot API; per-workspace bot tokens stored in Supabase Vault
  - Bot token: `TELEGRAM_BOT_TOKEN` (system alert bot)
  - Webhook: `TELEGRAM_WEBHOOK_BASE_URL`, `TELEGRAM_WEBHOOK_SECRET`
  - Per-workspace tokens stored encrypted in Vault, not as flat env vars
  - Services: `backend/src/services/telegram_bot.py`, `backend/src/services/telegram_events.py`
  - Router: `backend/src/routers/telegram.py`
  - DB tables: `supabase/migrations/00020_telegram_messages.sql`

**Documentation (page context):**
- **Notion** — OAuth2; syncs pages and webhooks for content updates
  - OAuth: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`
  - Webhook secret: `NOTION_WEBHOOK_SECRET`
  - Services: `backend/src/services/notion_oauth.py`, `backend/src/services/notion_sync.py`, `backend/src/services/notion_webhook.py`, `backend/src/services/notion_client.py`
  - Router: `backend/src/routers/notion.py`
  - DB tables: `supabase/migrations/00006_notion_pages.sql`

**Meeting Transcription:**
- **Fathom** — API-key based (users provide their own key via settings UI)
  - Base URL: `FATHOM_API_BASE_URL` (default: `https://api.fathom.ai/external/v1`)
  - Per-workspace API keys stored in Supabase Vault
  - Service: `backend/src/services/fathom.py`
  - Router: `backend/src/routers/fathom.py`

**AI / LLM Providers:**
- **OpenAI** — Used for both LLM completions and embeddings
  - Auth: `OPENAI_API_KEY`
  - Completions: GPT-4o-mini via `AsyncOpenAI` in `backend/src/services/llm_client.py`
  - Embeddings: `text-embedding-3-small` (768 dimensions) in `backend/src/services/embedding.py`

- **Google Gemini** — SDK installed (`google-genai`) with `GEMINI_API_KEY` setting; not active in production code paths as of this analysis (OpenAI is the live LLM client)

## Data Storage

**Databases:**
- **PostgreSQL via Supabase** — Primary database (hosted Supabase or local `supabase start`)
  - Connection: `DATABASE_URL` (`postgresql+asyncpg://...`)
  - ORM: SQLModel + SQLAlchemy 2.0 async
  - Driver: `asyncpg`
  - Engine config: pool size 5, max overflow 5, timeout 30s, recycle 300s (`backend/src/db.py`)
  - Extensions: `pgvector` for 768-dim embedding similarity search
  - RLS enforced via Supabase policies

- **Supabase Vault** — Encrypted secret storage for OAuth tokens
  - Functions: `public.store_vault_secret`, `public.read_vault_secret`, `public.delete_vault_secret`
  - SQL definitions: `supabase/migrations/00003_vault_token_functions.sql`
  - Python wrapper: `backend/src/services/vault.py`
  - Token naming: `oauth_{provider}_{workspace_id}_{token_type}`

**File Storage:**
- GitHub repos are cloned to ephemeral temp directories (`tempfile.mkdtemp`) for code indexing, then deleted. No persistent file storage.

**Caching / Queues:**
- **Redis** — In-memory store; Redis 7 Alpine
  - Connection: `REDIS_URL` (default: `redis://localhost:6379/0`)
  - Used for: caching (rate limiting state is in-process; Redis is available for service-level caching)
  - Run via: `docker-compose.yml`

## Authentication & Identity

**Auth Provider:** Supabase Auth
- JWT-based session tokens issued by Supabase
- Frontend: `@supabase/ssr` creates browser and server clients (`apps/web/src/lib/supabase/client.ts`, `apps/web/src/lib/supabase/server.ts`)
- Backend: Validates Supabase JWTs via `PyJWT` + JWKS endpoint (`backend/src/auth.py`)
- Middleware: `SentryContextMiddleware` extracts user from JWT for error tagging
- `SUPABASE_JWT_SECRET` required in production for token verification
- Social OAuth (GitHub, Google) handled via Supabase Auth social providers (`supabase/migrations/00018_handle_new_user_social_oauth.sql`)

**API Key Auth (MCP Server):**
- `CONTEXTOS_API_KEY` env var used as Bearer token by MCP server clients
- API key management: `backend/src/services/api_key.py`, `backend/src/models/api_key.py`
- DB tables: `supabase/migrations/00016_api_keys.sql`

**OAuth Flows (Integration Providers):**
- Common OAuth utilities: `backend/src/services/oauth_common.py`
- Each provider has dedicated `{provider}_oauth.py` service
- Callback URLs: `{BACKEND_URL}/api/{provider}/callback`
- Tokens stored encrypted in Supabase Vault (not in application database columns)

## Monitoring & Observability

**Error Tracking:**
- **Sentry** — Both backend and frontend
  - Backend: `sentry-sdk[fastapi]` with `FastApiIntegration` + `SqlalchemyIntegration`; traces sample rate 20% in prod (`backend/src/observability/sentry.py`)
  - Frontend: `@sentry/nextjs` via `withSentryConfig` wrapper in `apps/web/next.config.ts`
  - Config: `SENTRY_DSN` (required in production)

**LLM Observability:**
- **Laminar** — Traces all OpenAI calls with `@observe` decorator
  - SDK: `lmnr` Python package
  - Init: `backend/src/observability/laminar.py`
  - Metadata: workspace_id and ticket_identifier tagged on each trace span
  - Gracefully disabled when `LAMINAR_API_KEY` is absent

**Structured Logging:**
- `structlog` — Structured JSON logging in backend
- Configured per-environment in `backend/src/observability/logging.py`
- Correlation IDs added by `CorrelationIdMiddleware` (`backend/src/middleware/correlation.py`)

**Product Analytics:**
- **PostHog** — Frontend only; manual pageview and event tracking
  - Config: `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`
  - Implementation: `apps/web/src/lib/posthog.tsx`
  - Autocapture disabled; explicit `posthog.capture()` calls only

**Alerting:**
- Telegram bot used for critical error alerts (system bot, not the integration bot)
  - Config: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## CI/CD & Deployment

**Hosting:**
- Containerized via Docker (backend + frontend Dockerfiles provided)
- Nginx reverse proxy routes to `backend:8000` and `frontend:3000`
- No CI/CD pipeline configured (no `.github/workflows/` directory)

**Local Development:**
- `make dev` — starts Redis, instructs running frontend + backend in separate terminals
- `make dev-ngrok` — ngrok tunnel for OAuth callbacks requiring HTTPS
- `supabase start` — local Postgres + Auth + Vault + Realtime

## Webhooks & Callbacks

**Incoming Webhooks (real-time updates):**
- `POST /api/webhooks/linear` — Linear issue/comment events
- `POST /api/webhooks/github` — PR open/close/review events
- `POST /api/webhooks/gitlab` — MR events
- `POST /api/webhooks/notion` — Page content updates
- `POST /api/webhooks/jira` — Jira issue events
- `POST /api/webhooks/slack` — Slack Events API (message/reaction events)
- `POST /api/webhooks/telegram` — Telegram bot message events
- All handled in `backend/src/routers/webhooks.py`
- Signature verification per-provider using shared webhook secrets

**OAuth Callbacks:**
- `GET /api/linear/callback`
- `GET /api/slack/callback`
- `GET /api/github/callback`
- `GET /api/notion/callback`
- `GET /api/gitlab/callback`
- `GET /api/jira/callback`

**SSE (Server-Sent Events):**
- `GET /api/context/{ticket_identifier}/stream` — Streams context generation progress events
- Uses `sse-starlette` package

## Model Context Protocol (MCP)

**MCP Server:** `packages/mcp-server/` — Published as `@contextos/mcp-server`
- Provides AI coding assistants (Claude, Cursor, etc.) with ticket context
- Transport: stdio (`StdioServerTransport`)
- Tools exposed: `get_feature_context`, `search_context`, `get_related_work`
- Calls ContextOS backend API using `CONTEXTOS_API_URL` + `CONTEXTOS_API_KEY`
- Entry point: `packages/mcp-server/src/index.ts`

## Environment Configuration

**Required env vars (production):**
- `DATABASE_URL`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
- `OPENAI_API_KEY`
- `SENTRY_DSN`
- `BACKEND_URL` (must be HTTPS)
- `CORS_ORIGINS` (must not contain localhost)

**Optional env vars (degrade gracefully):**
- `LAMINAR_API_KEY` — LLM tracing disabled if absent
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — Alert bot disabled if absent
- Integration OAuth vars — that integration simply unavailable if absent

**Secrets location:**
- Root `.env` file (not committed; `.env.example` provided as template)
- OAuth tokens at runtime stored encrypted in Supabase Vault (not in `.env`)

---

*Integration audit: 2026-03-12*
