#!/usr/bin/env bash
# Invite an early-access user to ContextOS.
#
# Steps:
#   1. INSERT the email into public.allowed_emails (so the signup trigger admits them)
#   2. Call Supabase Admin API inviteUserByEmail (sends them a magic link)
#
# Run from the prod VPS (creds live in /opt/contextos/.env), or anywhere the
# DATABASE_URL + SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY env vars are set.
#
# Usage:
#   bash scripts/invite-early-user.sh user@example.com [optional note]
#
# Example:
#   bash scripts/invite-early-user.sh founder@startup.com "first beta cohort"

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <email> [note]" >&2
  exit 1
fi

EMAIL="$1"
NOTE="${2:-}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -z "${DATABASE_URL:-}" ] && [ -f "$REPO_ROOT/.env" ]; then
  set -a; source "$REPO_ROOT/.env"; set +a
fi

: "${DATABASE_URL:?DATABASE_URL not set}"
: "${SUPABASE_URL:?SUPABASE_URL not set}"
: "${SUPABASE_SERVICE_ROLE_KEY:?SUPABASE_SERVICE_ROLE_KEY not set}"

DB_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"

# Refuse to talk to localhost (would invite into local-only DB).
if echo "$DB_URL" | grep -qE '@(localhost|127\.0\.0\.1)'; then
  echo "ERROR: DATABASE_URL points to localhost. Aborting." >&2
  exit 1
fi

# Step 1: allowlist
echo "==> Adding $EMAIL to allowed_emails"
psql "$DB_URL" -v ON_ERROR_STOP=1 -q <<SQL
INSERT INTO public.allowed_emails (email, invited_by_email, note)
VALUES (lower(trim('$EMAIL')), 'invite-script', NULLIF('$NOTE', ''))
ON CONFLICT (email) DO NOTHING;
SQL

# Step 2: Supabase Admin API invite. POST returns 200 with the user object,
# 422 if the email is already a user (we treat that as success — they can
# just sign in directly).
echo "==> Sending invite email via Supabase Auth"
HTTP_CODE=$(curl -s -o /tmp/invite-resp.json -w "%{http_code}" \
  -X POST "${SUPABASE_URL}/auth/v1/invite" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\"}")

case "$HTTP_CODE" in
  200|201)
    echo "    invited (HTTP $HTTP_CODE)"
    ;;
  422)
    if grep -q "already been registered" /tmp/invite-resp.json 2>/dev/null; then
      echo "    user already exists — they can sign in directly (HTTP $HTTP_CODE)"
    else
      echo "ERROR: HTTP $HTTP_CODE" >&2
      cat /tmp/invite-resp.json >&2
      exit 1
    fi
    ;;
  *)
    echo "ERROR: unexpected HTTP $HTTP_CODE" >&2
    cat /tmp/invite-resp.json >&2
    exit 1
    ;;
esac

rm -f /tmp/invite-resp.json
echo ""
echo "Done. $EMAIL is now on the allowlist and has received an invite email."
