# ContextOS

AI-generated context pages for engineering tickets. When an engineer picks up a ticket, they immediately get the full story — where the feature came from, what was discussed in Slack, what decisions were made in meetings, and a ready-to-use AI implementation prompt. Integrates Linear, Slack, and meeting transcripts (Fathom).

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4, shadcn/ui |
| Backend | Python 3.12, FastAPI, SQLModel, LangGraph |
| Database | Supabase (PostgreSQL + pgvector + Vault) |
| Auth | Supabase Auth (email/password, magic link) |
| AI | Google Gemini (synthesis) |
| MCP Server | TypeScript, @modelcontextprotocol/sdk |
| Integrations | Linear (OAuth + webhooks), Slack (OAuth + Events API), Fathom |
| Observability | Laminar (LLM tracing), Sentry (errors) |
| Hosting | Vercel (frontend), Railway (backend) |

## Project Structure

```
├── apps/web/          Next.js frontend (auth, dashboard, integrations)
├── backend/           Python FastAPI backend (API, services, models)
│   ├── src/
│   │   ├── models/    SQLModel schemas (user, workspace, ticket, integration, slack)
│   │   ├── routers/   API endpoints (auth, health, linear, slack, webhooks, workspaces)
│   │   └── services/  Business logic (vault, linear_oauth, linear_sync, slack_oauth, ...)
│   └── tests/         pytest test suite
├── packages/mcp-server/  MCP server for AI coding assistants
└── supabase/          Database migrations and config
```

## Getting Started

### Prerequisites

- Node.js 22+ and pnpm 9+
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker (for Redis)
- Supabase CLI (`npx supabase` or `brew install supabase/tap/supabase`)

### Quick Setup

```bash
# Clone and enter the repo
git clone git@github.com:contextOS-team/ContextOS-core.git
cd ContextOS-core

# One-command setup (installs deps, copies .env, starts Docker)
make setup

# Edit .env with your keys (Supabase, Linear, Slack, etc.)
```

### Manual Setup

1. Copy environment variables:
   ```bash
   cp .env.example .env
   # Fill in your Supabase, Linear, Slack, and other keys
   ```

2. Start Supabase locally:
   ```bash
   supabase start
   supabase db reset  # applies migrations
   ```

3. Start Redis:
   ```bash
   docker compose up -d
   ```

4. Set up the frontend:
   ```bash
   cd apps/web && pnpm install
   ```

5. Set up the backend:
   ```bash
   cd backend && uv sync --all-extras
   ```

### Development

```bash
# Terminal 1 — Frontend
make dev-frontend

# Terminal 2 — Backend
make dev-backend

# Or start Redis first, then run both manually
make dev  # starts Redis, prints instructions
```

| Command | Description |
|---------|-------------|
| `make dev-frontend` | Start Next.js dev server (Turbopack) |
| `make dev-backend` | Start FastAPI with hot reload |
| `make test` | Run backend test suite |
| `make lint` | Lint frontend + backend |
| `make typecheck` | TypeScript + mypy type checks |
| `make db-reset` | Reset Supabase DB with migrations |
| `make clean` | Remove all build artifacts and containers |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Next.js     │────▶│  FastAPI      │────▶│  Supabase        │
│  Dashboard   │     │  Backend      │     │  PostgreSQL      │
│  (Auth UI)   │     │  (REST API)   │     │  pgvector + Vault│
└─────────────┘     └──────┬───────┘     └──────────────────┘
                           │
                    ┌──────┴───────┐
                    │  LangGraph    │
                    │  Agents       │
                    ├──────────────┤
                    │ Integrations  │
                    │ ┌──────┐     │
                    │ │Linear │ OAuth + webhooks
                    │ └──────┘     │
                    │ ┌──────┐     │
                    │ │Slack  │ OAuth + Events API
                    │ └──────┘     │
                    │ ┌──────┐     │
                    │ │Fathom │ API key + polling
                    │ └──────┘     │
                    └──────────────┘

┌─────────────┐
│ MCP Server   │ ← AI coding assistants (Claude Code, Cursor, etc.)
│ (stdio)      │
└─────────────┘
```
