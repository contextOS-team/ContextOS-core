.PHONY: dev dev-frontend dev-backend setup setup-backend db-reset lint typecheck test codegen clean

dev:
	@echo "Starting Redis..."
	docker compose up -d
	@echo "Redis started. Run 'make dev-frontend' and 'make dev-backend' in separate terminals."

dev-frontend:
	cd apps/web && pnpm dev

dev-backend:
	cd backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

setup: setup-backend
	@echo "Setting up ContextOS..."
	cp -n .env.example .env || true
	cd apps/web && pnpm install
	docker compose up -d
	@echo "Done! Edit .env with your keys, then run 'make dev'"

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
