# 45-03 Summary: Missed-decision Review Actions

Date: 2026-05-25
Status: complete

## What Changed

- Added `backend/src/services/missed_decision_actions.py` for workspace-scoped candidate loading, legal lifecycle transitions, suggestion resolution/snoozing, evidence attachment, and Decision promotion.
- Added `backend/src/routers/missed_decisions.py` with authenticated `/api/missed-decisions` review and action endpoints.
- Registered the missed-decision router in `backend/src/main.py`.
- Added lifecycle, endpoint, promotion, and evidence-attachment coverage.

## Verification

- `uv run --directory backend pytest tests/test_missed_decision_actions.py tests/test_missed_decision_promotion.py tests/test_missed_decision_candidates.py tests/test_missed_decision_scanner.py tests/test_suggestions.py -q` passed: 44 tests.
- `uv run --directory backend ruff check src/services/missed_decision_actions.py src/routers/missed_decisions.py src/main.py tests/test_missed_decision_actions.py tests/test_missed_decision_promotion.py` passed.
- Plan grep gates for lifecycle actions, graph promotion, and router registration passed.
- `git diff --check` passed.

## Notes

- Confirm promotes the candidate to a graph `Decision` before resolving related suggestion state.
- Reject, defer, add-evidence, and ignore-duplicate actions record actor/timestamp metadata in candidate evidence.
- Action hints remain inert metadata and are not executed by Phase 45.

## Next

Proceed to 45-04: dashboard Needs review UI, typed action helpers, and component coverage.
