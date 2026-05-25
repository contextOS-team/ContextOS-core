# 45-02 Summary: Candidate Extraction and Suggestion Publishing

Date: 2026-05-25
Status: complete

## What Changed

- Added strict source-backed missed-decision extraction in `backend/src/services/missed_decision_extractor.py`.
- Added layered dedupe and match classification in `backend/src/services/missed_decision_dedupe.py`.
- Added a Phase 44 suggestion adapter in `backend/src/services/missed_decision_suggestions.py`.
- Replaced the scanner processing placeholder with candidate extraction, persistence, dedupe classification, suppression/linking, and eligible suggestion publishing.
- Added candidate contract coverage in `backend/tests/test_missed_decision_candidates.py`.

## Verification

- `uv run --directory backend pytest tests/test_missed_decision_candidates.py tests/test_missed_decision_scanner.py tests/test_sync_scheduler_slack.py tests/test_suggestions.py tests/test_digest.py -q` passed: 53 tests.
- `uv run --directory backend ruff check src/services/missed_decision_extractor.py src/services/missed_decision_dedupe.py src/services/missed_decision_suggestions.py src/services/missed_decision_scanner.py tests/test_missed_decision_candidates.py` passed.
- Plan grep gates for source evidence, confidence tiers, dedupe classification, and suggestion publishing passed.

## Notes

- `needs_review` candidates persist internally but do not publish Phase 44 suggestions.
- Strong duplicate candidates are suppressed; strong existing matches are linked; weak and no-match high-confidence candidates can surface as `missed_decision` suggestions.
- Raw `messages_digest` Decision nodes cannot bypass candidate persistence and publish suggestions directly.

## Next

Proceed to 45-03: review actions, candidate lifecycle transitions, evidence attachment, and Decision Receipt promotion.
