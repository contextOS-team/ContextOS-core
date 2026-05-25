# 45-01 Checkpoint: Supabase Schema Push Blocked

Date: 2026-05-25
Status: blocked on manual Supabase project linkage

## Completed Before Block

- Added `supabase/migrations/00042_missed_decisions.sql` with scan state, scan run, and candidate tables.
- Added missed-decision SQLModels and source-window scanner services.
- Wired non-blocking enqueue calls after Slack, Telegram digest, Notion, and Fathom sync completion paths.
- Wired supervised queued-run drain into the polling fallback loop.
- Committed implementation as `8a94a00 feat(45-01): add missed decision scan foundation`.

## Verification Completed

- `uv run --directory backend pytest tests/test_missed_decision_scanner.py tests/test_sync_scheduler_slack.py -q` passed: 13 tests.
- `uv run --directory backend pytest tests/test_fathom.py -k 'not Endpoint' -q` passed: 13 tests, 6 deselected.
- `uv run --directory backend pytest tests/test_notion_sync.py -k 'not SyncConcurrencyGuard' -q` passed: 18 tests, 8 deselected.
- `uv run --directory backend ruff check src/models/missed_decision.py src/services/missed_decision_sources.py src/services/missed_decision_scanner.py tests/test_missed_decision_scanner.py` passed.
- `git diff --check` passed.

## Blocking Gate

Plan 45-01 Task 2 requires `supabase db push` before downstream persisted-schema verification.

Command:

```bash
supabase db push
```

Result:

```text
Cannot find project ref. Have you run supabase link?
Try rerunning the command with --debug to troubleshoot the error.
```

## Manual Action Required

Link this repository to the intended Supabase project, then rerun:

```bash
supabase link --project-ref <project-ref>
supabase db push
```

If the CLI also needs noninteractive auth, provide `SUPABASE_ACCESS_TOKEN` in the operator environment and rerun `supabase db push`.

Do not continue Phase 45 downstream scanner integration verification until the migration push succeeds or the operator explicitly overrides this gate.

## Verification Caveat

The full endpoint suites that start `TestClient` lifespan workers are currently unstable because background workers share and consume ordered mock-session responses during request tests. The deterministic service and scanner tests listed above passed.
