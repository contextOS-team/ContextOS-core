---
phase: 44-suggestion-system-and-dismissals
plan: "01"
status: complete
completed: 2026-05-25
requirements: [SUG-01, SUG-02]
---

# Phase 44 Plan 01 Summary

## Accomplishments

- Added the workspace-scoped `suggestions` persistence contract in `supabase/migrations/00041_suggestions.sql`.
- Added the `Suggestion` SQLModel and exported it through `backend/src/models/__init__.py`.
- Implemented reusable suggestion service helpers for listing, dismissing, snoozing, resolving, reopening, serialization, and missing-source generation.
- Added backend coverage for lifecycle persistence, exact-fingerprint preservation, concrete decision targeting, and serialized evidence/provenance fields.

## Files Created Or Modified

- `supabase/migrations/00041_suggestions.sql`
- `backend/src/models/suggestion.py`
- `backend/src/models/__init__.py`
- `backend/src/services/suggestions.py`
- `backend/tests/test_suggestions.py`

## Decisions

- Suggestion fingerprints are the durable preservation boundary: dismissed or resolved exact fingerprints are not reopened by detector refreshes.
- Missing-source suggestions require a concrete Decision target and specific missing evidence context.
- Snoozed suggestions remain persisted but are hidden from the bounded dashboard list until `snoozed_until` expires.

## Verification

- `uv run --directory backend pytest tests/test_suggestions.py -x` - passed.
- `uv run --directory backend ruff check src/models/suggestion.py src/services/suggestions.py src/routers/suggestions.py tests/test_suggestions.py` - passed.

## Deviations

None.
