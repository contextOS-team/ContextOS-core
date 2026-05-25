---
phase: 44
slug: suggestion-system-and-dismissals
status: complete
created: 2026-05-25
---

# Phase 44 - Code Patterns

## Backend Patterns

| Area | Existing Pattern | Phase 44 Use |
|------|------------------|--------------|
| SQLModel | `BaseModel` plus JSONB fields in graph models | New `Suggestion` model extends `BaseModel` and uses JSONB for evidence/details/provenance |
| Workspace isolation | Routes use `UserContext.workspace_id`; services filter by `workspace_id` | Every suggestion read/write receives workspace ID from auth context |
| Audit | `log_audit_event` flushes best-effort audit rows | Lifecycle actions log `suggestion_dismissed`, `suggestion_snoozed`, `suggestion_resolved`, `suggestion_reopened` |
| Routes | Routers are thin and commit after service mutations | `suggestions.py` delegates to service helpers and commits once |
| Detection | Graph digest wiring is non-blocking around graph node creation | Missing-source suggestion generation catches/logs failures and does not fail digest creation |

## Frontend Patterns

| Area | Existing Pattern | Phase 44 Use |
|------|------------------|--------------|
| API client | `apiFetch<T>()` in `apps/web/src/lib/api.ts` | Add typed suggestion fetch and lifecycle functions |
| Dashboard data | `useDashboardData` uses `Promise.allSettled` and maps domain types | Fetch suggestions alongside dashboard attention/context/graph/delta |
| Right rail | `ActiveContext` and `NeedsYou` hide when empty | `NeedsReview` hides when no visible suggestions exist |
| Styling | `.pulse-surface`, `.pulse-list-panel`, `.pulse-row`, `.pulse-tag` | Reuse existing pulse classes and add only small suggestion-specific classes |
| Tests | Vitest component tests under `pulse/__tests__` | Extend dashboard pulse tests for section ordering and lifecycle buttons |

## Naming

- Backend model: `Suggestion`
- Backend service: `backend/src/services/suggestions.py`
- Backend router: `backend/src/routers/suggestions.py`
- Frontend component: `apps/web/src/app/dashboard/pulse/needs-review.tsx`
- Frontend queue route: `apps/web/src/app/dashboard/suggestions/page.tsx`
- Migration: `supabase/migrations/00041_suggestions.sql`

## Accepted Status And Type Values

Suggestion types:
- `missing_source_coverage`
- `missed_decision`
- `action_prompt`

Statuses:
- `open`
- `snoozed`
- `dismissed`
- `resolved`

Priorities:
- `high`
- `medium`
- `low`

## Integration Boundary

Phase 44 may publish missing-source suggestions from graph Decision nodes. Phase 45 may later publish missed-decision suggestions using the same contract. Phase 47 may publish action prompts using the same lifecycle contract. Phase 44 does not implement candidate extraction, decision confirmation, or external writes.
