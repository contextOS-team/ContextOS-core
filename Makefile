.PHONY: dev dev-frontend dev-backend dev-workers setup db-reset lint typecheck

# Start everything
dev:
	@echo "Starting all services..."
	docker compose up -d
	@echo "Redis started. Now run 'make dev-frontend' and 'make dev-backend' in separate terminals."

dev-frontend:
	cd apps/web && pnpm dev

dev-backend:
	cd backend && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

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
	cd backend && ruff check .

typecheck:
	cd apps/web && pnpm typecheck
	cd backend && mypy src/
