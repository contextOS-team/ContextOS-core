# ContextOS

Auto-generated context pages for engineering tickets. Integrates Linear, Slack, Notion, and meeting transcripts to give engineers full context before they start working.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4, shadcn/ui |
| Backend | Python, FastAPI, LangGraph, LlamaIndex |
| Database | Supabase (PostgreSQL + pgvector) |
| Auth | Supabase Auth |
| AI | Anthropic Claude |
| MCP Server | TypeScript, @modelcontextprotocol/sdk |
| Background Jobs | Celery + Redis |
| Observability | Laminar (LLM), Sentry (errors) |
| Hosting | Vercel (frontend), Railway (backend) |

## Project Structure

- `apps/web/` — Next.js frontend (dashboard, settings, onboarding)
- `backend/` — Python FastAPI backend (API, agents, ingestion, synthesis)
- `packages/mcp-server/` — MCP server for AI coding assistants
- `supabase/` — Database migrations and config

## Getting Started

### Prerequisites

- Node.js 22+ and pnpm 9+
- Python 3.12+ and uv (or pip)
- Docker (for Redis)
- Supabase CLI (`npm install -g supabase`)

### Setup

1. Clone the repo:
   ```bash
   git clone git@github.com:contextOS-team/ContextOS-core.git
   cd ContextOS-core
   ```

2. Copy environment variables:
   ```bash
   cp .env.example .env
   # Fill in your keys
   ```

3. Start local services:
   ```bash
   docker compose up -d
   ```

4. Set up the frontend:
   ```bash
   cd apps/web
   pnpm install
   pnpm dev
   ```

5. Set up the backend:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   uvicorn src.main:app --reload
   ```

6. Start Supabase locally:
   ```bash
   supabase start
   supabase db reset  # applies migrations + seed
   ```

### Development

| Command | Description |
|---------|-------------|
| `cd apps/web && pnpm dev` | Start frontend dev server |
| `uvicorn src.main:app --reload` | Start backend dev server |
| `docker compose --profile workers up` | Start Celery workers |
| `supabase start` | Start local Supabase |
| `supabase db reset` | Reset DB with migrations |
| `supabase migration new <name>` | Create new migration |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Next.js     │────▶│  FastAPI      │────▶│  Supabase       │
│  Frontend    │     │  Backend      │     │  (PostgreSQL +  │
│              │     │              │     │   pgvector)      │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────┴───────┐
                    │  LangGraph    │
                    │  Agents       │
                    │              │
                    ├──────────────┤
                    │ Integrations  │
                    │ ┌────┐┌─────┐│
                    │ │Slack││Notion││
                    │ └────┘└─────┘│
                    │ ┌──────┐     │
                    │ │Linear │     │
                    │ └──────┘     │
                    └──────────────┘

┌─────────────┐
│ MCP Server   │ ← AI coding assistants (Claude Code, Cursor, etc.)
│ (stdio)      │
└─────────────┘
```
