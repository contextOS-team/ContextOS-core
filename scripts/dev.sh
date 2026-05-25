#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

pids=()

cleanup() {
  local status=$?

  if ((${#pids[@]} > 0)); then
    echo ""
    echo "Stopping dev processes..."
    for pid in "${pids[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
    wait "${pids[@]}" 2>/dev/null || true
  fi

  exit "$status"
}

trap cleanup INT TERM EXIT

start_process() {
  local label="$1"
  shift

  echo "Starting ${label}..."
  "$@" &
  pids+=("$!")
}

echo "Starting Supabase..."
supabase start || true

echo "Starting Redis..."
docker compose up -d

start_process "backend on http://localhost:8000/docs" \
  "$ROOT_DIR/scripts/openlog.sh" backend \
  bash -lc 'cd backend && uv run uvicorn src.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000'

start_process "frontend on http://localhost:3000" \
  "$ROOT_DIR/scripts/openlog.sh" frontend \
  bash -lc 'cd apps/web && pnpm dev'

NGROK_DOMAIN="$(grep '^NGROK_DOMAIN=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)"
if [[ "${WITH_NGROK:-auto}" != "0" && -n "$NGROK_DOMAIN" ]]; then
  if command -v ngrok >/dev/null 2>&1; then
    start_process "ngrok tunnel https://${NGROK_DOMAIN}" \
      ngrok http 8000 "--domain=${NGROK_DOMAIN}"
  else
    echo "Skipping ngrok: ngrok command not found."
  fi
elif [[ "${WITH_NGROK:-auto}" == "1" ]]; then
  echo "WITH_NGROK=1 requested, but NGROK_DOMAIN is not set in .env."
  exit 1
fi

echo ""
echo "ContextOS local dev is running:"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000/docs"
echo "  Logs:     .openlogs/frontend.txt and .openlogs/backend.txt"
if [[ "${WITH_NGROK:-auto}" != "0" && -n "$NGROK_DOMAIN" ]]; then
  echo "  Ngrok:    https://${NGROK_DOMAIN}"
fi
echo ""
echo "Press Ctrl-C to stop frontend/backend/ngrok. Supabase and Redis stay running."

wait "${pids[@]}"
