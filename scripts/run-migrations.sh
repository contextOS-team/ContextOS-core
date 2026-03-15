#!/usr/bin/env bash
# Run pending Supabase migrations against the linked production database.
#
# Uses `supabase db push` which tracks applied migrations natively.
#
# Requires:
#   - supabase CLI installed and project linked
#   - SUPABASE_DB_PASSWORD in env, or DB password extractable from DATABASE_URL
#
# Usage:
#   bash scripts/run-migrations.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Resolve DB password: explicit env var > extracted from DATABASE_URL > .env file
if [ -z "${SUPABASE_DB_PASSWORD:-}" ]; then
  # Try to extract from DATABASE_URL (format: ...://user:password@host...)
  DB_URL="${DATABASE_URL:-}"
  if [ -z "$DB_URL" ] && [ -f "$REPO_ROOT/.env" ]; then
    DB_URL=$(grep '^DATABASE_URL=' "$REPO_ROOT/.env" | cut -d'=' -f2- || true)
  fi
  if [ -n "$DB_URL" ]; then
    # Extract password between : and @ in the userinfo section
    SUPABASE_DB_PASSWORD=$(echo "$DB_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
  fi
fi

if [ -z "${SUPABASE_DB_PASSWORD:-}" ]; then
  echo "ERROR: Could not determine database password" >&2
  echo "Set SUPABASE_DB_PASSWORD or ensure DATABASE_URL contains credentials" >&2
  exit 1
fi

echo "Pushing pending migrations..."
supabase db push --password "$SUPABASE_DB_PASSWORD" --include-all
echo "Migrations complete."
