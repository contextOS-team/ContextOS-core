#!/usr/bin/env bash
# Securely create the minimal ContextOS production environment on the server.
#
# Secrets are read from /dev/tty with terminal echo disabled, validated without
# printing them, and installed atomically as /opt/contextos/.env (mode 0600).

set +x
set -Eeuo pipefail
umask 077

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

repo_root=$(cd "$(dirname "$0")/.." && pwd)
final="$repo_root/.env"
project_ref=${1:-wadigvlopixxupkyxtpf}
had_final=false
[[ -f $final ]] && had_final=true

if [[ ! $project_ref =~ ^[a-z0-9]{20}$ ]]; then
  echo "Invalid Supabase project reference." >&2
  exit 1
fi

for command in curl openssl psql python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

tmp=$(mktemp "$repo_root/.env.new.XXXXXX")
database_password=
encoded_password=
supabase_key=
oauth_state_secret=

cleanup() {
  rm -f -- "${tmp:-}"
  unset database_password encoded_password supabase_key oauth_state_secret \
    database_url psql_url supabase_url auth_status
}
trap cleanup EXIT HUP INT TERM

prompt_hidden() {
  local target=$1 label=$2 value
  while true; do
    IFS= read -r -s -p "$label: " value </dev/tty
    printf '\n' >/dev/tty

    if [[ -z $value ]]; then
      echo "$label cannot be empty." >&2
      continue
    fi
    if [[ $value == *$'\n'* || $value == *$'\r'* ]]; then
      echo "$label must be one line." >&2
      continue
    fi

    printf -v "$target" '%s' "$value"
    unset value
    return 0
  done
}

put() {
  local key=$1 value=$2
  if [[ $value == *"'"* ]]; then
    echo "Generated value for $key cannot be represented safely." >&2
    exit 1
  fi
  printf "%s='%s'\n" "$key" "$value" >>"$tmp"
}

echo "Enter values from Supabase project $project_ref. Input is hidden."
prompt_hidden supabase_key "Publishable (or legacy anon) API key"
prompt_hidden database_password "Database password"

encoded_password=$(
  printf '%s' "$database_password" |
    python3 -c 'import sys; from urllib.parse import quote; print(quote(sys.stdin.read(), safe=""))'
)

supabase_url="https://${project_ref}.supabase.co"
# Supabase's direct database endpoint is IPv6-only on this project, while the
# default Docker bridge is IPv4-only. Session mode preserves prepared-statement
# support while giving the persistent backend an IPv4 endpoint.
pooler_host="aws-1-eu-central-1.pooler.supabase.com"
database_url="postgresql+asyncpg://postgres.${project_ref}:${encoded_password}@${pooler_host}:5432/postgres"
oauth_state_secret=$(openssl rand -hex 32)

put ENVIRONMENT prod
put APP_URL https://contextos.pro
put BACKEND_URL https://api.contextos.pro
put CORS_ORIGINS https://contextos.pro
put REDIS_URL redis://redis:6379/0
put DATABASE_URL "$database_url"
put SUPABASE_URL "$supabase_url"
put SUPABASE_ANON_KEY "$supabase_key"
put SUPABASE_JWT_SECRET ""
put SENTRY_DSN ""
put OAUTH_STATE_SECRET "$oauth_state_secret"
put TELEGRAM_BOT_USERNAME ContextOSBot

# Compatibility with the pre-recovery Compose file. The repaired Compose file
# derives these build arguments from the canonical variables above.
put NEXT_PUBLIC_SUPABASE_URL "$supabase_url"
put NEXT_PUBLIC_SUPABASE_ANON_KEY "$supabase_key"
put NEXT_PUBLIC_BACKEND_URL https://api.contextos.pro
put NEXT_PUBLIC_APP_URL https://contextos.pro
put NEXT_PUBLIC_SENTRY_DSN ""
put NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ContextOSBot

# Validate the key and password without exposing response bodies or errors.
auth_status=$(
  curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --max-time 15 --header "apikey: $supabase_key" \
    "$supabase_url/auth/v1/health" 2>/dev/null || true
)
if [[ $auth_status != 200 ]]; then
  echo "Supabase rejected the API key (HTTP ${auth_status:-connection error}); nothing was installed." >&2
  exit 1
fi

if ! PGPASSWORD="$database_password" PGCONNECT_TIMEOUT=10 PGSSLMODE=require \
  PGGSSENCMODE=disable psql --host "$pooler_host" --port 5432 \
  --username "postgres.${project_ref}" --dbname postgres -X -v ON_ERROR_STOP=1 \
  -Atqc 'select 1' >/dev/null 2>&1; then
  echo "Supabase rejected the database password; nothing was installed." >&2
  exit 1
fi

unset database_password encoded_password supabase_key oauth_state_secret database_url

if ! env -i PATH=/usr/bin:/bin bash --noprofile --norc -c '
  set -a
  source "$1"
  : "${DATABASE_URL:?}" "${SUPABASE_URL:?}" "${SUPABASE_ANON_KEY:?}"
  [[ $DATABASE_URL == postgresql+asyncpg://* ]]
  [[ $SUPABASE_URL == https://* ]]
' _ "$tmp" >/dev/null 2>&1; then
  echo "Generated environment failed private validation; nothing was installed." >&2
  exit 1
fi

if $had_final; then
  install -o root -g root -m 600 "$final" "${final}.previous"
fi
mv -- "$tmp" "$final"
tmp=
chown root:root "$final"
chmod 600 "$final"

if ! docker compose --env-file "$final" -f "$repo_root/docker-compose.prod.yml" \
  config --quiet >/dev/null 2>&1; then
  if $had_final && [[ -f ${final}.previous ]]; then
    mv -- "${final}.previous" "$final"
  else
    rm -f -- "$final"
  fi
  echo "Compose rejected the environment; the previous state was restored." >&2
  exit 1
fi

trap - EXIT HUP INT TERM
cleanup
echo "Production environment validated and installed as root:root mode 600."
