---
phase: 45
slug: post-sync-missed-decision-detection
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-24
---

# Phase 45 - Validation Strategy

> Per-phase validation contract for post-sync missed-decision detection.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest `9.0.2` plus Vitest `4.0.18` |
| **Config file** | `backend/pyproject.toml`; `apps/web/vitest.config.ts` |
| **Quick run command** | `uv run --directory backend pytest backend/tests/test_missed_decision_scanner.py -x` |
| **Full suite command** | `uv run --directory backend pytest && pnpm --dir apps/web test && pnpm --dir apps/web typecheck` |
| **Estimated runtime** | ~2-5 minutes |

---

## Sampling Rate

- **After every backend task commit:** Run the narrow pytest command for the touched missed-decision behavior.
- **After every frontend task commit:** Run the narrow Vitest command for the touched dashboard suggestion behavior.
- **After every plan wave:** Run backend missed-decision tests plus any touched dashboard Vitest tests.
- **Before `$gsd-verify-work`:** `uv run --directory backend pytest && pnpm --dir apps/web test && pnpm --dir apps/web typecheck` must be green.
- **Max feedback latency:** 5 minutes for phase-scoped automated feedback.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 45-00-01 | 00 | 0 | GAP-01, GAP-02, GAP-03 | T-45-01 | Phase 44 suggestion contract is verified before Phase 45 writes candidate-to-suggestion integration code | source/static | `test -f .planning/phases/44-suggestion-system-and-dismissals/44-01-PLAN.md || test -f backend/src/models/suggestion.py` | No - W0 | pending |
| 45-01-01 | 01 | 1 | GAP-01 | T-45-02 | Scanner enqueue is non-blocking, workspace-scoped, bounded by checkpoint, and checkpoint advances only after scanner success | backend unit/integration | `uv run --directory backend pytest backend/tests/test_missed_decision_scanner.py -x` | No - W0 | pending |
| 45-02-01 | 02 | 2 | GAP-02 | T-45-03 | Candidates require exact quote/source link/confidence before user-visible surfacing and never leak across workspaces | backend unit | `uv run --directory backend pytest backend/tests/test_missed_decision_candidates.py -x` | No - W0 | pending |
| 45-02-02 | 02 | 2 | GAP-02 | T-45-04 | Dedupe suppresses strong duplicates, links useful evidence, blocks raw digest Decision nodes from directly publishing suggestions, and does not treat topical similarity alone as same-decision proof | backend unit | `uv run --directory backend pytest backend/tests/test_missed_decision_candidates.py -x` | No - W0 | pending |
| 45-03-01 | 03 | 3 | GAP-03 | T-45-05 | Confirm, reject, defer, add-evidence, and ignore-duplicate actions validate workspace ownership and legal lifecycle transitions | backend endpoint | `uv run --directory backend pytest backend/tests/test_missed_decision_actions.py -x` | No - W0 | pending |
| 45-03-02 | 03 | 3 | GAP-04 | T-45-06 | Confirmed candidates create or update source-backed Decision Receipts while preserving quote, rationale, source link, confidence, people, and affected systems | backend integration | `uv run --directory backend pytest backend/tests/test_missed_decision_promotion.py -x` | No - W0 | pending |
| 45-04-01 | 04 | 4 | GAP-02, GAP-03 | T-45-07 | Dashboard shows only bounded open missed-decision suggestions outside Recent decisions and sends authenticated action mutations | frontend component | `pnpm --dir apps/web exec vitest run src/app/dashboard/pulse/needs-review-suggestions.test.tsx` | No - W0 | pending |

*Status: pending, green, red, flaky*

---

## Wave 0 Requirements

- [ ] Verify Phase 44 has concrete suggestion schema, statuses, endpoints, and dashboard surface before integrating Phase 45 into the suggestion system.
- [ ] `backend/tests/test_missed_decision_scanner.py` - covers GAP-01 scanner trigger, source window, retry behavior, and checkpoint advancement.
- [ ] `backend/tests/test_missed_decision_candidates.py` - covers GAP-02 candidate payload fields, exact-quote guard, confidence tiers, workspace isolation, raw digest Decision guardrail, and layered dedupe.
- [ ] `backend/tests/test_missed_decision_actions.py` - covers GAP-03 confirm, reject, defer, add-evidence, ignore-duplicate, invalid transitions, and suggestion resolution.
- [ ] `backend/tests/test_missed_decision_promotion.py` - covers GAP-04 graph Decision Receipt promotion and evidence preservation.
- [ ] `apps/web/src/app/dashboard/pulse/needs-review-suggestions.test.tsx` - covers bounded top 3-5 Needs review rendering, labels, hidden empty state, and action callbacks.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Needs review section remains visually bounded and does not displace Recent decisions | GAP-02, GAP-03 | DOM tests cannot prove dashboard hierarchy, visual priority, or scan-friendly composition | Run the web app, inspect dashboard home after seeding open missed-decision suggestions, and confirm Recent decisions remains the primary confirmed-decision surface. |
| Source evidence is understandable enough for confirmation | GAP-02, GAP-04 | Human judgment is needed to verify source quote, rationale, and affected systems explain why the candidate matters | Review at least 3 seeded candidates and confirm a user can decide Save as new decision, Add as evidence, Defer, or Reject from the displayed evidence. |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 test dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 5 minutes
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-24
