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

### Team Members (Quickest Path)

```bash
git clone git@github.com:contextOS-team/ContextOS-core.git
cd ContextOS-core
# Drop in the .env file from DM
make setup
# Terminal 1:
make dev-frontend   # http://localhost:3000
# Terminal 2:
make dev-backend    # http://localhost:8000/docs
```

`make setup` checks prerequisites, installs all dependencies, starts Supabase, applies migrations, generates the frontend env file, and starts Redis. If anything is missing it tells you exactly what to install.

### Manual Setup (External Contributors)

<details>
<summary>Click to expand</summary>

**Prerequisites:** Node.js 22+, pnpm 9+, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker, Supabase CLI

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

6. Generate frontend env:
   ```bash
   make setup-frontend-env
   ```

</details>

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
