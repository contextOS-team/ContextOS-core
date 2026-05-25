---
phase: 44
slug: suggestion-system-and-dismissals
status: complete
created: 2026-05-25
---

# Phase 44 - Research

## Goal

Build a reusable, workspace-scoped suggestion foundation with durable lifecycle state, a bounded dashboard `Needs review` surface, and first missing-source-coverage generation.

## Relevant Existing Patterns

### Persistence

- New domain rows use SQLModel classes under `backend/src/models/` plus Supabase migrations.
- Workspace-scoped tables consistently carry `workspace_id` with RLS policies through `workspace_members`.
- `BaseModel` provides UUID primary key plus `created_at`, `updated_at`, and `deleted_at`.
- JSONB fields are already used for flexible payloads in graph, integration, and audit models.

### Backend API

- Authenticated user-facing routes depend on `get_current_user`, which supplies `UserContext.workspace_id`.
- Business actions should go through the FastAPI backend, not direct frontend Supabase writes.
- `log_audit_event` is best-effort and should record lifecycle actions without making the user action fail.
- Dashboard-specific reads currently live under `/api/dashboard`, but Phase 45 already expects a generic `backend/src/routers/suggestions.py`, so Phase 44 should create a reusable suggestion router.

### Dashboard UI

- Dashboard home is a Phase 41 pulse surface. `Recent decisions` leads, secondary content lives in the right rail, and empty secondary sections disappear.
- Existing right-rail sections use compact rows, sentence-case labels, neutral chips, and no wrapper card around the full page section.
- `useDashboardData` aggregates authenticated API calls and direct Supabase reads; suggestion reads and lifecycle mutations should use `apiFetch`.

### Missing-source Detection

- Decision nodes live in `graph_nodes` with `entity_type = 'Decision'`, workspace scope, source fields, and flexible `properties`.
- Existing digest extraction creates Decision nodes from Slack/Telegram digest evidence with source metadata.
- Phase 44 can start with a conservative heuristic: only create `missing_source_coverage` suggestions for concrete Decision nodes with messaging evidence and no design/meeting/Figma evidence markers.
- Use a material fingerprint derived from suggestion type, target entity, missing evidence type, and evidence snapshot. This preserves dismissed/resolved exact instances while allowing a materially changed target/evidence bundle to create a new suggestion.

## Recommended Implementation

1. Add `suggestions` table and SQLModel with:
   - `workspace_id`, `type`, `status`, `priority`
   - `entity_type`, `entity_id`
   - `title`, `body`, `primary_action`, `action_href`
   - JSONB `evidence`, `details`, and `provenance`
   - `fingerprint`, `snoozed_until`, and lifecycle timestamps

2. Add `SuggestionService` helpers for:
   - listing visible dashboard suggestions
   - listing all suggestions for the full queue
   - dismiss/snooze/resolve/reopen lifecycle changes
   - idempotent missing-source suggestion creation without resurrecting dismissed/resolved exact fingerprints

3. Add authenticated routes:
   - `GET /api/suggestions?limit=3`
   - `GET /api/suggestions/all`
   - `POST /api/suggestions/{id}/dismiss`
   - `POST /api/suggestions/{id}/snooze`
   - `POST /api/suggestions/{id}/resolve`
   - `POST /api/suggestions/{id}/reopen`

4. Wire missing-source generation to decision graph creation after digest extraction. This keeps suggestions tied to concrete decisions and avoids broad integration upsell copy.

5. Add dashboard UI:
   - `NeedsReview` right-rail section above `Active context`
   - typed API client functions
   - `useDashboardData` suggestion fetch
   - full queue route behind `View all`

## Risks And Constraints

- Do not create a separate review queue for Phase 45; the suggestion contract must remain generic.
- Do not expose suggestions across workspaces; every query must use server-side `UserContext.workspace_id`.
- Do not mutate dismissed/resolved exact suggestions during detector refresh.
- Do not build missed-decision extraction, confirmation, bot actions, or external writes in Phase 44.

## Verification Strategy

- Backend unit tests for lifecycle, visible filtering, fingerprint preservation, and missing-source generation.
- Frontend tests for `Needs review` rendering, empty hiding, action wiring, and dashboard ordering.
- Type checks and targeted backend/frontend test runs.
