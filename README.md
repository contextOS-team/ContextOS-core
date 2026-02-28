# ContextOS

AI-generated context pages for engineering tickets. When an engineer picks up a ticket, they immediately get the full story — where the feature came from, what was discussed in Slack, what decisions were made in meetings, and a ready-to-use AI implementation prompt. Integrates Linear, Slack, GitHub, and meeting transcripts (Fathom).

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4, shadcn/ui |
| Backend | Python 3.12, FastAPI, SQLModel |
| Database | Supabase (PostgreSQL + pgvector + Vault) |
| Auth | Supabase Auth (email/password, magic link) |
| AI | OpenAI GPT-4o-mini (synthesis), OpenAI text-embedding-3-small (embeddings) |
| MCP Server | TypeScript, @modelcontextprotocol/sdk |
| Integrations | Linear (OAuth + webhooks), Slack (OAuth + Events API), GitHub (App + webhooks), Notion (OAuth + webhooks), Fathom |
| Observability | Laminar (LLM tracing), Sentry (errors) |
| Hosting | Vercel (frontend), Railway (backend) |

## Project Structure

```
├── apps/web/          Next.js frontend (auth, dashboard, integrations)
├── backend/           Python FastAPI backend (API, services, models)
│   ├── src/
│   │   ├── models/    SQLModel schemas (user, workspace, ticket, integration, slack)
│   │   ├── routers/   API endpoints (auth, health, linear, slack, github, notion, webhooks, workspaces)
│   │   └── services/  Business logic (vault, linear_oauth, linear_sync, slack_oauth, github_oauth, notion_oauth, ...)
│   └── tests/         pytest test suite
├── packages/mcp-server/  MCP server for AI coding assistants
└── supabase/          Database migrations and config
```

## Integration Setup

See **[docs/INTEGRATION_SETUP.md](docs/INTEGRATION_SETUP.md)** for step-by-step instructions on connecting Linear and Slack.

## Getting Started

### Team Members (Quickest Path)

```bash
git clone git@github.com:contextOS-team/ContextOS-core.git
cd ContextOS-core
```

1. Drop the `.env` file from DM into the project root
2. Run setup:
   ```bash
   make setup
   ```
3. Start dev servers in three terminals:
   ```bash
   # Terminal 1:
   make dev-frontend   # http://localhost:3000

   # Terminal 2:
   make dev-backend    # http://localhost:8000/docs

   # Terminal 3:
   make dev-ngrok      # OAuth callbacks & webhooks
   ```

That's it. `make setup` handles everything:
- Checks prerequisites (node, pnpm, python3, uv, docker, supabase CLI) with install instructions if anything is missing
- Installs frontend (pnpm) and backend (uv) dependencies
- Starts Supabase and applies database migrations
- Generates `apps/web/.env.local` from `NEXT_PUBLIC_*` variables in your `.env`
- Starts Redis via Docker Compose

### Manual Setup (External Contributors)

<details>
<summary>Click to expand</summary>

**Prerequisites:** Node.js 22+, pnpm 9+, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker, Supabase CLI, [ngrok](https://ngrok.com/) (for OAuth callbacks)

1. Copy environment variables:
   ```bash
   cp .env.example .env
   # Fill in your Supabase, Linear, Slack, Notion, and other keys
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
| `make dev-ngrok` | Start ngrok tunnel for OAuth callbacks & webhooks |
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
                    │ │GitHub │ App + webhooks
                    │ └──────┘     │
                    │ ┌──────┐     │
                    │ │Notion │ OAuth + webhooks
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
