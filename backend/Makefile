.PHONY: dev setup test lint typecheck format

dev:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

setup:
	uv sync --all-extras || (python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]")

test:
	uv run pytest --cov=src || (. .venv/bin/activate && pytest --cov=src)

lint:
	uv run ruff check . || (. .venv/bin/activate && ruff check .)

typecheck:
	uv run mypy src/ || (. .venv/bin/activate && mypy src/)

format:
	uv run ruff format . || (. .venv/bin/activate && ruff format .)
