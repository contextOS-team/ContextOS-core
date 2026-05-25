---
phase: 44-suggestion-system-and-dismissals
plan: "02"
status: complete
completed: 2026-05-25
requirements: [SUG-01, SUG-02, SUG-04]
---

# Phase 44 Plan 02 Summary

## Accomplishments

- Added authenticated `/api/suggestions` list and lifecycle routes.
- Registered the suggestion router in the FastAPI application.
- Wired digest-created Decision nodes to non-blocking missing-source suggestion publication.
- Kept suggestion publication isolated in a nested transaction so a suggestion-table issue cannot roll back digest activity.

## Files Created Or Modified

- `backend/src/routers/suggestions.py`
- `backend/src/main.py`
- `backend/src/services/digest.py`
- `backend/tests/test_suggestions.py`

## Decisions

- Routes trust `UserContext.workspace_id`; no client-supplied workspace ID is accepted.
- Lifecycle actions commit through authenticated backend endpoints and preserve audit/provenance state.
- Missing-source publication is best-effort and logs failures without breaking digest completion.

## Verification

- `uv run --directory backend pytest tests/test_digest.py tests/test_suggestions.py -x` - passed.
- `uv run --directory backend ruff check src/models/suggestion.py src/services/suggestions.py src/routers/suggestions.py tests/test_suggestions.py` - passed.

## Deviations

- The digest hook uses `session.begin_nested()` after validation showed older test schemas without `suggestions` would otherwise poison the outer digest transaction even when the publication exception was caught.
