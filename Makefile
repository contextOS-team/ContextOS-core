.PHONY: dev dev-frontend dev-backend dev-workers setup db-reset lint typecheck test clean

dev:
	@echo "Starting Redis..."
	docker compose up -d
	@echo "Redis started. Run 'make dev-frontend' and 'make dev-backend' in separate terminals."

dev-frontend:
	cd apps/web && pnpm dev

dev-backend:
	cd backend && . .venv/bin/activate && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-workers:
	docker compose --profile workers up

setup:
	@echo "Setting up ContextOS..."
	cp -n .env.example .env || true
	cd apps/web && pnpm install
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	docker compose up -d
	@echo "Done! Edit .env with your keys, then run 'make dev'"

db-reset:
	supabase db reset

lint:
	cd apps/web && pnpm lint
	cd backend && . .venv/bin/activate && ruff check .

typecheck:
	cd apps/web && pnpm typecheck
	cd backend && . .venv/bin/activate && mypy src/

test:
	cd backend && . .venv/bin/activate && pytest

clean:
	docker compose down -v
	rm -rf backend/.venv
	rm -rf apps/web/node_modules apps/web/.next
	rm -rf packages/mcp-server/node_modules packages/mcp-server/dist
