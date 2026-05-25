# 45-01 Summary: Missed-decision Scan Foundation

Date: 2026-05-25
Status: complete for local execution

## What Changed

- Added missed-decision persistence in `supabase/migrations/00042_missed_decisions.sql`.
- Added SQLModels for scan state, scan runs, and candidates in `backend/src/models/missed_decision.py`.
- Added workspace-scoped source-window loaders for Slack, Telegram, Notion, and Fathom in `backend/src/services/missed_decision_sources.py`.
- Added non-blocking enqueue, scan-window checkpointing, queued-run claiming, success/failure status handling, and checkpoint advancement in `backend/src/services/missed_decision_scanner.py`.
- Wired enqueue calls after successful Slack/Telegram digest, Slack polling, Notion sync, and Fathom transcript import paths.
- Wired queued-run drain into the supervised polling fallback loop.

## Verification

- `psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -v ON_ERROR_STOP=1 -f supabase/migrations/00042_missed_decisions.sql` passed.
- `supabase migration repair --status applied 00042 --local` passed.
- Local Postgres contains the missed-decision tables and unique scan-state indexes.
- `uv run --directory backend pytest tests/test_missed_decision_scanner.py tests/test_sync_scheduler_slack.py -q` passed: 13 tests.
- `uv run --directory backend pytest tests/test_fathom.py -k 'not Endpoint' -q` passed: 13 tests, 6 deselected.
- `uv run --directory backend pytest tests/test_notion_sync.py -k 'not SyncConcurrencyGuard' -q` passed: 18 tests, 8 deselected.
- `uv run --directory backend ruff check src/models/missed_decision.py src/services/missed_decision_sources.py src/services/missed_decision_scanner.py tests/test_missed_decision_scanner.py` passed.
- `git diff --check` passed.

## Deviations

- `supabase db push` could not run because the CLI is not logged in and the repo is not linked to a Supabase Cloud project ref.
- The local schema was applied with `psql` and marked applied with `supabase migration repair --local`, matching the established local migration fallback in this repo.
- Full endpoint suites that start `TestClient` lifespan workers are unstable because background workers share ordered mock-session responses during request tests. Deterministic service-level tests for this slice passed.

## Next

Proceed to 45-02: source-backed candidate extraction, confidence tiers, dedupe, and suggestion publishing.
