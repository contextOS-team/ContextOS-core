.PHONY: dev dev-frontend dev-backend dev-ngrok setup setup-backend check-prereqs setup-frontend-env db-reset lint typecheck test codegen clean

dev:
	@echo "Starting Redis..."
	docker compose up -d
	@echo "Redis started."
	@echo ""
	@echo "Run these in separate terminals:"
	@echo "  1. make dev-frontend    # http://localhost:3000"
	@echo "  2. make dev-backend     # http://localhost:8000/docs"
	@echo "  3. make dev-ngrok       # OAuth callbacks & webhooks"

dev-frontend:
	cd apps/web && pnpm dev

dev-backend:
	cd backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-ngrok:
	@NGROK_DOMAIN=$$(grep '^NGROK_DOMAIN=' .env 2>/dev/null | cut -d= -f2-); \
	if [ -z "$$NGROK_DOMAIN" ]; then \
		echo "Error: NGROK_DOMAIN not set in .env"; \
		echo "Get a free static domain at https://dashboard.ngrok.com/domains"; \
		exit 1; \
	fi; \
	echo "Starting ngrok tunnel to localhost:8000..."; \
	echo "Public URL: https://$$NGROK_DOMAIN"; \
	ngrok http 8000 --domain=$$NGROK_DOMAIN

check-prereqs:
	@echo "Checking prerequisites..."
	@command -v node >/dev/null 2>&1 || { echo "node not found — install from https://nodejs.org or 'brew install node'"; exit 1; }
	@command -v pnpm >/dev/null 2>&1 || { echo "pnpm not found — run 'npm install -g pnpm'"; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo "python3 not found — install from https://python.org or 'brew install python'"; exit 1; }
	@command -v uv >/dev/null 2>&1 || { echo "uv not found — run 'curl -LsSf https://astral.sh/uv/install.sh | sh'"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "docker not found — install from https://docker.com"; exit 1; }
	@command -v supabase >/dev/null 2>&1 || { echo "supabase CLI not found — run 'brew install supabase/tap/supabase'"; exit 1; }
	@command -v ngrok >/dev/null 2>&1 || { echo "ngrok not found — run 'brew install ngrok' (needed for OAuth callbacks)"; exit 1; }
	@echo "All prerequisites found."

setup-frontend-env:
	@if [ -f .env ]; then \
		echo "Generating apps/web/.env.local from root .env..."; \
		grep '^NEXT_PUBLIC_' .env > apps/web/.env.local; \
		SUPABASE_URL=$$(grep '^SUPABASE_URL=' .env | cut -d= -f2-); \
		SUPABASE_KEY=$$(grep '^SUPABASE_KEY=' .env | cut -d= -f2-); \
		BACKEND_URL=$$(grep '^BACKEND_URL=' .env | cut -d= -f2-); \
		[ -n "$$SUPABASE_URL" ] && echo "NEXT_PUBLIC_SUPABASE_URL=$$SUPABASE_URL" >> apps/web/.env.local; \
		[ -n "$$SUPABASE_KEY" ] && echo "NEXT_PUBLIC_SUPABASE_ANON_KEY=$$SUPABASE_KEY" >> apps/web/.env.local; \
		[ -n "$$BACKEND_URL" ] && echo "NEXT_PUBLIC_BACKEND_URL=$$BACKEND_URL" >> apps/web/.env.local; \
		echo "Created apps/web/.env.local"; \
	else \
		echo "Warning: .env not found — skipping apps/web/.env.local generation"; \
	fi

setup: check-prereqs setup-backend
	@echo "Setting up ContextOS..."
	cp -n .env.example .env || true
	@echo "Starting Supabase (skips if already running)..."
	supabase start || true
	@echo "Applying database migrations..."
	supabase db reset
	cd apps/web && pnpm install
	$(MAKE) setup-frontend-env
	docker compose up -d
	@echo ""
	@echo "Setup complete! Next steps:"
	@echo "  1. Edit .env with your keys (or drop in the .env from DM)"
	@echo "  2. Run 'make setup-frontend-env' after updating .env"
	@echo "  3. Terminal 1: make dev-frontend"
	@echo "  4. Terminal 2: make dev-backend"

setup-backend:
	@echo "Setting up backend..."
	cd backend && uv sync --all-extras || (cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]")
	@echo "Backend dependencies installed."

db-reset:
	supabase db reset

lint:
	cd apps/web && pnpm lint
	cd backend && uv run ruff check . || (cd backend && . .venv/bin/activate && ruff check .)

typecheck:
	cd apps/web && pnpm typecheck
	cd backend && uv run mypy src/ || (cd backend && . .venv/bin/activate && mypy src/)

test:
	cd backend && uv run pytest || (cd backend && . .venv/bin/activate && pytest)

codegen:
	@echo "OpenAPI TypeScript codegen deferred to Phase 2 (see CONTEXT.md cross-team contracts)."
	@echo "Once FastAPI endpoints exist, this will generate TypeScript types from the OpenAPI spec."

clean:
	docker compose down -v
	rm -rf backend/.venv
	rm -rf apps/web/node_modules apps/web/.next
	rm -rf packages/mcp-server/node_modules packages/mcp-server/dist
