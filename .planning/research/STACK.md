# Stack Research

**Domain:** AI-powered developer context synthesis platform
**Researched:** 2026-02-24
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Next.js | ^15.2.0 | Web dashboard (SSR + RSC) | Already in scaffold. Server Components for Supabase reads, Turbopack for fast dev. Vercel-native deployment. |
| FastAPI | >=0.133.0 | Backend API, webhooks, OAuth flows | Already in scaffold. Async-native, auto OpenAPI docs, excellent for webhook receivers and background task coordination. |
| Supabase (PostgreSQL + pgvector) | Cloud | Database, auth, vector search, real-time | Already chosen. Combines auth, DB, RLS multi-tenancy, vector embeddings, and real-time subscriptions in one platform. Eliminates 4+ separate services. |
| Gemini Flash | gemini-2.5-flash | LLM synthesis engine | Team decision (Dulat). Cheapest fast model for structured context synthesis. ~$0.15/1M input tokens makes it 10x cheaper than alternatives at comparable quality for summarization tasks. |
| MCP TypeScript SDK | ^1.27.0 | AI coding assistant integration | Official SDK. Delivers context to Claude Code, Cursor, Windsurf. stdio transport for local MCP server calling cloud backend. |

**Confidence:** HIGH -- all core technologies are already selected and scaffolded. Research validates the choices.

### Backend -- Python Dependencies

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| google-genai | >=1.64.0 | Gemini API client | **REPLACE `anthropic` in pyproject.toml.** New unified Google Gen AI SDK (GA). Pydantic-native types. Supports both AI Studio and Vertex AI. The old `google-generativeai` package is sunset. |
| langgraph | >=1.0.9 | Data gathering orchestration | Stateful graph for multi-step data collection (Linear -> Slack -> Notion). Handles parallel API calls, conditional routing, error recovery. Overkill for single LLM call but perfect for gather-then-synthesize pipeline. |
| httpx | >=0.28.1 | Async HTTP client | Linear GraphQL API calls, Slack API fallbacks, general HTTP. Already in scaffold. async/await native. |
| slack-bolt | >=1.27.0 | Slack event handling + API | **ADD to pyproject.toml.** Official Slack framework. Handles event verification, rate limiting, token rotation automatically. Better than raw slack-sdk for webhook/event handling. |
| slack-sdk | >=3.33.0 | Slack Web API client | Installed as dependency of slack-bolt. Use directly for conversations.history, users.info, etc. |
| supabase | >=2.28.0 | Python Supabase client | Already in scaffold. RPC calls for Vault operations, auth admin, direct DB queries from backend. |
| pydantic | >=2.10 | Data validation, settings | Already in scaffold. Schema validation for webhook payloads, API request/response models, config. |
| pydantic-settings | >=2.13.0 | Environment configuration | Already in scaffold. Type-safe env var loading with .env support. |
| sentry-sdk[fastapi] | >=2.53.0 | Error tracking | Already in scaffold. Auto-instruments FastAPI routes, captures unhandled exceptions. |
| lmnr | >=0.7.42 | LLM observability | Already in scaffold. Install with `lmnr[all]` or specific extras. OpenTelemetry-native tracing for Gemini calls, LangGraph steps. |
| uvicorn[standard] | >=0.28.0 | ASGI server | Already in scaffold. Production server for FastAPI. |

**Confidence:** HIGH for all except LangGraph (MEDIUM -- see Alternatives section).

### Frontend -- TypeScript Dependencies

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| next | ^15.2.0 | Framework | Already installed. App Router, Server Components, Server Actions. |
| react / react-dom | ^19.0.0 | UI runtime | Already installed. Server Components support. |
| @supabase/supabase-js | ^2.49.0 | Browser Supabase client | Already installed. Real-time subscriptions for context page updates, direct reads via RLS. |
| @supabase/ssr | ^0.6.0 | Server-side auth | Already installed. Cookie-based auth for SSR. Creates server/browser clients correctly. |
| shadcn/ui components | (CLI-added) | UI components | Already chosen (implied by cva, clsx, tailwind-merge). Add components on-demand via `npx shadcn@latest add`. |
| tailwindcss | ^4.0.0 | Styling | Already installed. v4 uses CSS-first config, no tailwind.config.js needed. |
| zod | ^3.24.0 | Schema validation | Already in MCP server. Add to web app for form validation and API response parsing. |
| sonner | ^1.7.0 | Toast notifications | Already installed. For async operation feedback (regenerate context, connect integration). |
| lucide-react | ^0.469.0 | Icons | Already installed. |

**Confidence:** HIGH -- frontend stack is solid and already scaffolded.

### MCP Server -- TypeScript Dependencies

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| @modelcontextprotocol/sdk | ^1.27.0 | MCP server framework | Already installed. Latest supports Streamable HTTP, structured tool outputs, OAuth auth. |
| zod | ^3.24.0 | Tool input schemas | Already installed. Required peer dependency of MCP SDK. |
| tsx | ^4.19.0 | Dev runtime | Already installed. TypeScript execution without build step. |

**Confidence:** HIGH -- MCP server scaffold is correct.

### Database & Infrastructure

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PostgreSQL (Supabase) | 15+ | Primary database | Supabase-managed. Includes pgvector, pg_trgm, RLS, Vault extensions. |
| pgvector | Built-in | Vector similarity search | Supabase includes it. Use with Gemini embeddings (768 or 1536 dimensions). No separate vector DB needed at this scale. |
| Supabase Vault | Built-in | OAuth token encryption | Encrypts tokens at rest via Transparent Column Encryption. Access via SQL functions + RPC. Server-side only (service_role key). |
| Supabase Auth | Built-in | User authentication | Email/password + magic links. Cookie-based SSR via @supabase/ssr. No Clerk/NextAuth. |
| Supabase Realtime | Built-in | Live updates | Push context page status changes to dashboard without polling. |
| Redis | 7-alpine | Cache + future queue | Already in Docker Compose. For v1: rate limit tracking, API response caching. For v2: Celery broker if needed. |

**Confidence:** HIGH

### Embedding Model

| Technology | Model ID | Dimensions | Purpose | Why Recommended |
|------------|----------|------------|---------|-----------------|
| Gemini Embedding | gemini-embedding-001 | 768 (recommended) | Ticket/message embeddings | **FREE via Google AI Studio.** Supports 768/1536/3072 dims via MRL (truncate without quality loss). Use 768 dims for v1 -- faster pgvector queries, lower storage, comparable quality. Same SDK (google-genai) as synthesis model. Zero additional cost. |

**Confidence:** MEDIUM -- Dulat owns embedding model decision. Gemini embedding is the strongest default given Gemini Flash for synthesis (one SDK, one API key, free embeddings). OpenAI text-embedding-3-small ($0.02/1M tokens, 1536 dims) is the fallback if Gemini quality is insufficient.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Python linting + formatting | Already configured. Fast Rust-based linter replacing flake8+black+isort. |
| mypy | Python type checking | Already configured. Strict mode recommended for Pydantic models. |
| ESLint 9 + eslint-config-next | TS/JS linting | Already configured. Flat config format. |
| TypeScript 5.7+ | Type checking | Already configured. `tsc --noEmit` for CI. |
| pytest + pytest-asyncio | Python testing | Already configured. Use `asyncio_mode = "auto"` in pytest config. |
| Supabase CLI | Local DB + Auth | Already configured. `supabase db reset` for migrations, `supabase start` for local dev. |
| Docker Compose | Local services | Already configured. Redis service. Keep Celery worker profile for v2. |

**Confidence:** HIGH

## Installation

```bash
# Backend -- UPDATED pyproject.toml dependencies
# Remove: anthropic, celery[redis], llama-index, llama-index-readers-slack, llama-index-readers-notion
# Add: google-genai, slack-bolt
pip install "fastapi[standard]" "uvicorn[standard]" \
    google-genai langgraph \
    httpx slack-bolt \
    supabase "pydantic>=2.0" pydantic-settings \
    "sentry-sdk[fastapi]" "lmnr[all]" \
    python-dotenv redis

# Backend dev dependencies (unchanged)
pip install -D pytest pytest-asyncio ruff mypy

# Frontend (already installed, verify)
cd apps/web && pnpm install

# MCP server (already installed, verify)
cd packages/mcp-server && pnpm install
```

## Critical pyproject.toml Changes

The current `pyproject.toml` has several packages that should be removed or replaced:

```diff
dependencies = [
    "fastapi[standard]",
    "uvicorn[standard]",
-   "anthropic",
+   "google-genai",
    "langgraph",
-   "llama-index",
-   "llama-index-readers-slack",
-   "llama-index-readers-notion",
+   "slack-bolt",
    "supabase",
-   "celery[redis]",
    "redis",
    "pydantic>=2.0",
    "pydantic-settings",
    "httpx",
-   "lmnr",
+   "lmnr[all]",
    "sentry-sdk[fastapi]",
    "python-dotenv",
]
```

**Rationale for each removal:**

| Removed | Why |
|---------|-----|
| `anthropic` | Team chose Gemini Flash, not Claude. Replace with `google-genai`. |
| `llama-index` + readers | Unnecessary abstraction layer. Linear has a simple GraphQL API (httpx POST). Slack has slack-bolt/slack-sdk. Direct API calls are simpler, more debuggable, fewer dependencies. LlamaIndex adds ~50+ transitive deps for what is essentially `httpx.post()` with pagination. |
| `celery[redis]` | Team decided FastAPI BackgroundTasks for v1. Keep `redis` for caching. Celery is v2 when job persistence matters. |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| google-genai (Gemini Flash) | anthropic (Claude) | If synthesis quality is insufficient. Claude 3.5 Sonnet is better at nuanced reasoning but 5-10x more expensive. |
| LangGraph for gather pipeline | Plain async Python (asyncio.gather) | If the data gathering flow stays simple (3 parallel API calls, merge, synthesize). LangGraph adds value when you need retries, conditional branching, or stateful multi-step flows. Start with LangGraph but evaluate if overhead justifies the abstraction. |
| Direct httpx + slack-bolt | LlamaIndex readers | If you need RAG-style document indexing with automatic chunking. For v1 (simple API pulls), direct calls are better. Reconsider LlamaIndex for v2 Notion integration if document processing gets complex. |
| Gemini embedding-001 (free) | OpenAI text-embedding-3-small ($0.02/1M) | If Gemini embedding quality is measurably worse on your ticket/message data. OpenAI has more battle-tested embeddings. Run A/B test in v1 before committing. |
| FastAPI BackgroundTasks | Celery + Redis | When tasks must survive server restarts, need retries with backoff, or take >30 seconds. Context generation is the critical path -- if Gemini calls timeout or fail silently, add Celery in v2. |
| slack-bolt | Raw slack-sdk | If you need full control over every Slack API call and don't want Bolt's opinion on event handling. For webhook/event-driven patterns, Bolt's built-in verification and rate limiting saves significant boilerplate. |
| pnpm | npm / yarn | Never for this project. Already using pnpm workspace, lockfile is pnpm-lock.yaml. |
| Supabase Vault | Custom AES-256 encryption | Never for this project. Team decision. Vault handles key rotation, encryption at rest, and access control via SQL functions. |
| shadcn/ui | Radix + custom styles, Chakra, MUI | If you need a full component library out of the box. shadcn gives you ownership of component code (copy-paste, not npm install), perfect for an internal tool where you'll customize heavily. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `anthropic` Python SDK | Team chose Gemini Flash. Don't maintain two LLM SDKs. | `google-genai` |
| `llama-index` + readers | Massive dependency tree (~50+ packages) for simple HTTP API calls. Adds abstraction over Slack/Linear APIs that makes debugging harder. The "readers" just paginate API calls you can write in 20 lines. | `httpx` for Linear GraphQL, `slack-bolt`/`slack-sdk` for Slack |
| `celery[redis]` (v1) | Overkill for MVP. Adds broker config, worker process, monitoring. Team explicitly deferred. | `FastAPI.BackgroundTasks` |
| `google-generativeai` (old SDK) | Deprecated/sunset. Google is consolidating to `google-genai`. | `google-genai` |
| `python-slack-events-api` | Deprecated. Slack recommends Bolt for Python for all new apps. | `slack-bolt` |
| NextAuth / Clerk | Team chose Supabase Auth. Adding another auth system creates token confusion and session sync issues. | `@supabase/ssr` + Supabase Auth |
| Pinecone / Weaviate / Qdrant | Separate vector DB is unnecessary. pgvector in Supabase handles the scale (thousands of tickets, not millions). Adding a vector DB adds infrastructure, cost, and sync complexity. | pgvector (Supabase built-in) |
| Prisma / SQLAlchemy / Drizzle ORM | Supabase client handles reads. Backend uses RPC + raw SQL for migrations. ORM adds a layer that fights with Supabase's RLS model. | Supabase Python client + SQL migrations |
| LangChain (full framework) | Heavy, opinionated, frequent breaking changes. LangGraph (the orchestration piece) is useful standalone. Don't pull in the full LangChain framework. | `langgraph` (standalone, works without LangChain) |

## Stack Patterns by Variant

**If context generation takes >30 seconds consistently:**
- Add `celery[redis]` with a dedicated worker process
- Use Redis (already in Docker Compose) as broker
- Keep BackgroundTasks for quick tasks (webhook acknowledgment, cache invalidation)

**If embedding quality from Gemini is insufficient:**
- Switch to OpenAI text-embedding-3-small ($0.02/1M tokens)
- Add `openai` Python SDK
- Update pgvector dimension from 768 to 1536
- This is a config change, not an architecture change

**If Slack event volume becomes high (>1000 events/min):**
- Add `arq` (lightweight Redis-based task queue) as a middle ground before Celery
- Or upgrade to Celery with dedicated workers
- FastAPI BackgroundTasks will become a bottleneck at high volume

**If MCP server needs to work offline (no cloud backend):**
- Add SQLite/local cache to MCP server package
- Current architecture assumes MCP -> Railway cloud is always available
- This would be a v3 enhancement

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI >=0.133.0 | Pydantic >=2.0 | FastAPI fully supports Pydantic v2. Do not use Pydantic v1 compatibility mode. |
| langgraph >=1.0.9 | Python >=3.10 | LangGraph 1.x requires Python 3.10+. Our project uses 3.12, which is fine. |
| google-genai >=1.64.0 | Python >=3.10 | GA SDK. Uses Pydantic internally for types. |
| @supabase/ssr ^0.6.0 | @supabase/supabase-js ^2.49.0 | Must use together. SSR package creates cookies-aware client wrapper. |
| @modelcontextprotocol/sdk ^1.27.0 | zod ^3.24.0 | MCP SDK requires zod as peer dependency. Uses zod for tool input validation. |
| Next.js ^15.2.0 | React ^19.0.0 | Next 15 requires React 19. Server Components are stable. |
| tailwindcss ^4.0.0 | PostCSS ^8.5.0 | Tailwind v4 uses CSS-first config (@import "tailwindcss"). No tailwind.config.js. |
| slack-bolt >=1.27.0 | slack-sdk >=3.33.0 | Bolt installs slack-sdk as dependency. Don't pin slack-sdk separately. |
| sentry-sdk[fastapi] >=2.53.0 | FastAPI >=0.79.0 | Auto-detects FastAPI in dependencies. No manual integration init needed. |

## Environment Variables to Add

Based on stack changes, update `.env.example`:

```bash
# Replace ANTHROPIC_API_KEY with:
GOOGLE_API_KEY=                     # Gemini API key (AI Studio)
# OR for Vertex AI:
# GOOGLE_CLOUD_PROJECT=
# GOOGLE_CLOUD_LOCATION=

# Add for Slack (if using Bolt):
SLACK_BOT_TOKEN=                    # xoxb-... Bot User OAuth Token
SLACK_SIGNING_SECRET=               # For webhook verification
SLACK_CLIENT_ID=                    # For OAuth flow
SLACK_CLIENT_SECRET=                # For OAuth flow

# Add for Linear:
LINEAR_CLIENT_ID=                   # OAuth app client ID
LINEAR_CLIENT_SECRET=               # OAuth app client secret
LINEAR_WEBHOOK_SECRET=              # HMAC-SHA256 webhook signing

# Keep existing:
SUPABASE_URL=
SUPABASE_KEY=                       # anon key for standard operations
SUPABASE_SERVICE_ROLE_KEY=          # for Vault operations, auth admin
REDIS_URL=redis://localhost:6379/0
LAMINAR_API_KEY=
SENTRY_DSN=
```

## Sources

- [Google Gemini API Models](https://ai.google.dev/gemini-api/docs/models) -- Model naming, pricing, capabilities (HIGH confidence)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/) -- SDK docs, GA status (HIGH confidence)
- [PyPI: google-genai 1.64.0](https://pypi.org/project/google-genai/) -- Version verified (HIGH confidence)
- [PyPI: langgraph 1.0.9](https://pypi.org/project/langgraph/) -- Version verified (HIGH confidence)
- [PyPI: supabase 2.28.0](https://pypi.org/project/supabase/) -- Version verified (HIGH confidence)
- [PyPI: slack-bolt 1.27.0](https://pypi.org/project/slack-bolt/) -- Version verified (HIGH confidence)
- [PyPI: sentry-sdk 2.53.0](https://pypi.org/project/sentry-sdk/) -- Version verified (HIGH confidence)
- [PyPI: lmnr 0.7.42](https://pypi.org/project/lmnr/) -- Version verified (HIGH confidence)
- [PyPI: httpx 0.28.1](https://pypi.org/project/httpx/) -- Version verified (HIGH confidence)
- [PyPI: FastAPI 0.133.0](https://pypi.org/project/fastapi/) -- Version verified (HIGH confidence)
- [npm: @modelcontextprotocol/sdk 1.27.0](https://www.npmjs.com/package/@modelcontextprotocol/sdk) -- Version from search (HIGH confidence)
- [Gemini Embedding Docs](https://ai.google.dev/gemini-api/docs/embeddings) -- gemini-embedding-001, MRL, dimensions (HIGH confidence)
- [Supabase SSR Auth for Next.js](https://supabase.com/docs/guides/auth/server-side/nextjs) -- Cookie-based auth pattern (HIGH confidence)
- [Supabase Vault](https://supabase.com/docs/guides/database/extensions/pgvector) -- Token encryption at rest (MEDIUM confidence, verify Vault SQL function patterns)
- [Linear OAuth 2.0](https://linear.app/developers/oauth-2-0-authentication) -- Refresh tokens, PKCE flow (HIGH confidence)
- [Linear Webhooks](https://linear.app/developers/webhooks) -- HMAC-SHA256 verification, retry policy (HIGH confidence)
- [Slack Bolt for Python](https://tools.slack.dev/bolt-python/) -- Event handling, rate limiting (HIGH confidence)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) -- Limitations for production (HIGH confidence)
- [FastAPI + LLM best practices](https://agentsarcade.com/blog/building-llm-apps-with-fastapi-best-practices) -- BackgroundTasks caveats (MEDIUM confidence)

---
*Stack research for: AI-powered developer context synthesis platform*
*Researched: 2026-02-24*
