# AGENTS.md

## Cursor Cloud specific instructions

### Architecture overview

ContextOS is a monorepo with three services:

| Service | Path | Tech | Dev port |
|---|---|---|---|
| Frontend | `apps/web/` | Next.js 15, React 19, TypeScript | 3000 |
| Backend | `backend/` | Python 3.12, FastAPI, SQLModel | 8000 |
| MCP Server (optional) | `packages/mcp-server/` | TypeScript | stdio |

Infrastructure dependencies: **Supabase** (PostgreSQL + Auth, ports 54321-54323) and **Redis** (port 6379).

### Commands reference

See `README.md` and root `Makefile` for the canonical list. Key commands:

- `make dev-frontend` / `make dev-backend` — start dev servers
- `make lint` — ESLint (frontend) + ruff (backend)
- `make typecheck` — tsc (frontend) + mypy (backend)
- `make test` — backend pytest suite
- `make db-reset` — reset Supabase DB with migrations

### Known issues and gotchas

1. **Duplicate migration versions**: The `supabase/migrations/` directory has duplicate version prefixes (00017, 00018, 00019, 00020) and non-standard filenames (00004b, 00019b). Running `supabase start` or `supabase db reset` will fail. Workaround: temporarily move all migrations out, start Supabase with an empty migrations dir (also move `seed.sql` temporarily), then apply each SQL file via `docker exec -i supabase_db_workspace psql -U postgres -d postgres < file.sql` in the correct dependency order. Restore all files afterward.

2. **Migration dependency order**: `00017_graph_tables.sql` must be applied before `00019_identity_mappings.sql` (which references `graph_nodes`). `00018_traverse_graph_function.sql` also depends on graph tables.

3. **Docker in Cloud VM**: Requires `fuse-overlayfs` storage driver and `iptables-legacy`. The Docker daemon must be started with `sudo dockerd` and socket permissions set via `sudo chmod 666 /var/run/docker.sock`.

4. **Backend .env loading**: The backend reads from the project root `.env` file (not `backend/.env`). See `backend/src/config.py`.

5. **Frontend .env.local generation**: After updating root `.env`, always run `make setup-frontend-env` to regenerate `apps/web/.env.local`.

6. **pnpm build scripts**: Some packages (esbuild, sharp, unrs-resolver) have ignored build scripts. `pnpm approve-builds` is interactive and cannot be run non-interactively. The app runs fine in dev mode without them.

7. **Backend ruff lint**: The codebase has ~737 pre-existing ruff findings. These are not regressions.

8. **Backend tests**: 17 of 620 tests fail pre-existing. The 603 passing tests cover most functionality.

### Starting services (after update script has run)

1. Start Docker daemon if not running: `sudo dockerd &>/tmp/dockerd.log &`
2. Fix socket permissions: `sudo chmod 666 /var/run/docker.sock`
3. Start Supabase: follow the migration workaround above
4. Start Redis: `docker compose up -d`
5. Generate frontend env: `make setup-frontend-env`
6. Start backend: `make dev-backend` (port 8000)
7. Start frontend: `make dev-frontend` (port 3000)
8. Health check: `curl http://localhost:8000/api/health`
