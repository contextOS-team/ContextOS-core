---
phase: 03-slack-meeting-ingestion
plan: 03
status: complete
started: 2026-02-25
completed: 2026-02-25
duration: ~10min (including HITL checkpoint)
---

# Plan 03-03 Summary: Integration Setup UI

## What Was Built

Integration management page at `/dashboard/integrations` with card-based layout for Linear, Slack, and Fathom. Users can connect/disconnect all three integrations from a single page.

## Key Files

### Created
- `backend/src/routers/integrations.py` — Unified GET /api/integrations/status endpoint
- `apps/web/src/lib/api.ts` — Typed API client with helpers for all integration endpoints
- `apps/web/src/app/dashboard/integrations/page.tsx` — Integration setup page with card grid
- `apps/web/src/app/dashboard/integrations/integration-card.tsx` — Reusable card component with status badges
- `apps/web/src/app/dashboard/integrations/slack-channels.tsx` — Slack channel picker with checkboxes/search
- `apps/web/src/app/dashboard/integrations/fathom-connect.tsx` — Fathom API key input form

### Modified
- `backend/src/services/linear_oauth.py` — Fixed reconnect upsert (removed deleted_at filter), fixed timezone
- `backend/src/services/slack_oauth.py` — Same reconnect fix, timezone fix
- `backend/src/services/fathom.py` — Fixed API URL, auth header, endpoint path, timezone
- `backend/src/services/linear_webhook.py` — Timezone fix (naive UTC)
- `backend/src/services/linear_sync.py` — Timezone fix (naive UTC)
- `backend/src/services/slack_events.py` — Timezone fix (naive UTC)
- `backend/src/config.py` — Fixed Fathom API default URL
- `backend/src/main.py` — Registered integrations router

## Commits

1. `7542849` — feat(03-03): unified integration status endpoint and typed API client
2. `eede377` — feat(03-03): integration setup page with cards, channel picker, and Fathom form
3. `1efcf15` — fix(03-03): OAuth reconnect unique constraint and timezone mismatches

## Bugs Fixed During HITL

1. **OAuth reconnect UniqueViolationError**: Soft-delete sets `deleted_at` but unique constraint on `(workspace_id, user_id, provider)` doesn't exclude soft-deleted rows. Fixed by removing `deleted_at IS NULL` filter on upsert queries.
2. **Timezone-aware datetime vs TIMESTAMP WITHOUT TIME ZONE**: `datetime.now(timezone.utc)` produces tz-aware objects that asyncpg rejects. Fixed across all 6 service files to use `datetime.utcnow()`.
3. **Fathom API misconfiguration**: Wrong base URL (`api.fathom.video` doesn't resolve), wrong auth header (`Bearer` instead of `X-Api-Key`), wrong endpoint (`/calls` instead of `/meetings`).

## Deviations

- Bugfixes for OAuth and Fathom were not in the original plan but discovered during HITL verification
- All fixes committed as a single bugfix commit after visual verification passed

## Self-Check: PASSED

- [x] All 3 tasks executed (2 auto + 1 checkpoint)
- [x] Each task committed individually
- [x] SUMMARY.md created
- [x] STATE.md updated
- [x] All 3 integrations verified connected in browser
