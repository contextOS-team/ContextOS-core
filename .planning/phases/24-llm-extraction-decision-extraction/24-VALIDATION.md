---
phase: 24
slug: llm-extraction-decision-extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python -m pytest tests/test_llm_extractor.py -x` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_llm_extractor.py -x`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 0 | EXTR-03 | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestLLMExtraction -x` | ❌ W0 | ⬜ pending |
| 24-01-02 | 01 | 0 | EXTR-04 | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestContentHashDedup -x` | ❌ W0 | ⬜ pending |
| 24-01-03 | 01 | 0 | EXTR-05 | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestSourceValidation -x` | ❌ W0 | ⬜ pending |
| 24-01-04 | 01 | 0 | EXTR-06 | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestContentFilter -x` | ❌ W0 | ⬜ pending |
| 24-01-05 | 01 | 0 | DECIDE-01 | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestDecisionExtraction -x` | ❌ W0 | ⬜ pending |
| 24-01-06 | 01 | 0 | DECIDE-02 | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestDecisionNodeSchema -x` | ❌ W0 | ⬜ pending |
| 24-01-07 | 01 | 0 | DECIDE-03 | unit | `cd backend && python -m pytest tests/test_llm_extractor.py::TestDecisionEdges -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_llm_extractor.py` — covers EXTR-03, EXTR-04, EXTR-05, EXTR-06, DECIDE-01, DECIDE-02, DECIDE-03
- [ ] No new fixtures needed beyond existing conftest.py (mock_session, mock_settings already available)
- [ ] Gemini responses will be mocked — no API key needed for tests

*Existing infrastructure covers fixtures and test config.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
