#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if (($# < 2)); then
  echo "Usage: scripts/openlog.sh <name> <command...>" >&2
  exit 2
fi

name="$1"
shift

mkdir -p "$ROOT_DIR/.openlogs"

if command -v openlogs >/dev/null 2>&1; then
  exec openlogs --out-dir "$ROOT_DIR/.openlogs" --name "$name" -- "$@"
fi

echo "Warning: openlogs not found; running ${name} without mirrored logs." >&2
exec "$@"
