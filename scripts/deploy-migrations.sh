#!/usr/bin/env bash
# Apply pending Supabase migrations against the prod database via psql.
#
# Why not `supabase db push`? It refuses to proceed when the remote history
# table has rows with no matching local file (an artifact of older migrations
# applied via Studio). psql + a manual sync of supabase_migrations.schema_migrations
# does the same job without that blocker, and uses the same history table the
# CLI does — so once history is clean, `supabase db push` works too.
#
# Reads DATABASE_URL from /opt/contextos/.env (or the env). Strips the
# SQLAlchemy-only "+asyncpg" prefix before handing to psql.
#
# Idempotent: skips migrations whose `version` is already in the history table.
# Each migration runs in its own transaction; failure aborts the whole script.
#
# Usage (from /opt/contextos):
#   bash scripts/deploy-migrations.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Load DATABASE_URL from .env if not already set.
if [ -z "${DATABASE_URL:-}" ] && [ -f "$REPO_ROOT/.env" ]; then
  set -a; source "$REPO_ROOT/.env"; set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL not set and not found in .env" >&2
  exit 1
fi

# Strip SQLAlchemy "+asyncpg" suffix that psql doesn't understand.
DB_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"

# Sanity check — refuse to run against localhost (would clobber dev DB).
if echo "$DB_URL" | grep -qE '@(localhost|127\.0\.0\.1)'; then
  echo "ERROR: refusing to run against localhost (DATABASE_URL points to local DB)" >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql not installed. Run: apt-get install -y postgresql-client" >&2
  exit 1
fi

# Ensure the history table exists (Supabase creates it lazily on first push).
psql "$DB_URL" -v ON_ERROR_STOP=1 -q <<'SQL' >/dev/null
CREATE SCHEMA IF NOT EXISTS supabase_migrations;
CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
  version text PRIMARY KEY,
  name    text,
  statements text[]
);
SQL

# 2026-05: two early integration migrations were renamed only to improve
# lexical ordering. Some databases already have their original history versions;
# normalize those ledger rows before computing pending migrations so deploys
# don't replay schemas that already exist.
psql "$DB_URL" -v ON_ERROR_STOP=1 -q <<'SQL' >/dev/null
UPDATE supabase_migrations.schema_migrations
SET version = '000040',
    name = '000040_github_tables.sql'
WHERE version = '00004'
AND NOT EXISTS (
  SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '000040'
);

DELETE FROM supabase_migrations.schema_migrations
WHERE version = '00004'
AND EXISTS (
  SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '000040'
);

UPDATE supabase_migrations.schema_migrations
SET name = '000040_github_tables.sql'
WHERE version = '000040'
AND name IS DISTINCT FROM '000040_github_tables.sql';

UPDATE supabase_migrations.schema_migrations
SET version = '000190',
    name = '000190_gitlab_tables.sql'
WHERE version = '00019'
AND NOT EXISTS (
  SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '000190'
);

DELETE FROM supabase_migrations.schema_migrations
WHERE version = '00019'
AND EXISTS (
  SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '000190'
);

UPDATE supabase_migrations.schema_migrations
SET name = '000190_gitlab_tables.sql'
WHERE version = '000190'
AND name IS DISTINCT FROM '000190_gitlab_tables.sql';
SQL

# Pull the set of applied versions into a sorted file for fast lookup.
APPLIED=$(mktemp)
trap 'rm -f "$APPLIED"' EXIT
psql "$DB_URL" -v ON_ERROR_STOP=1 -At -c "SELECT version FROM supabase_migrations.schema_migrations" \
  | sort -u > "$APPLIED"

PENDING=()
for f in supabase/migrations/*.sql; do
  base=$(basename "$f" .sql)
  # Version = leading digits of filename (handles 00001 and 000045 alike).
  version=$(echo "$base" | grep -oE '^[0-9]+')
  if ! grep -qx "$version" "$APPLIED"; then
    PENDING+=("$f|$version|$base.sql")
  fi
done

if [ ${#PENDING[@]} -eq 0 ]; then
  echo "No pending migrations."
  exit 0
fi

echo "Pending migrations: ${#PENDING[@]}"
for entry in "${PENDING[@]}"; do
  IFS='|' read -r path version name <<< "$entry"
  echo "  - $name"
done

for entry in "${PENDING[@]}"; do
  IFS='|' read -r path version name <<< "$entry"
  echo ""
  echo "==> Applying $name"
  # Run migration + history insert in one transaction so partial failures
  # don't leave the history out of sync with the schema.
  psql "$DB_URL" -v ON_ERROR_STOP=1 --single-transaction <<SQL
\i $path
INSERT INTO supabase_migrations.schema_migrations (version, name)
VALUES ('$version', '$name')
ON CONFLICT (version) DO NOTHING;
SQL
  echo "    ok"
done

echo ""
echo "All migrations applied."
