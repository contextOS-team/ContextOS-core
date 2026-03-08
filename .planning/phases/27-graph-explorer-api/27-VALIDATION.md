---
phase: 27
slug: graph-explorer-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python -m pytest tests/test_graph_api.py -x` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_graph_api.py -x`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 27-01-01 | 01 | 1 | GAPI-01a | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_success -x` | ❌ W0 | ⬜ pending |
| 27-01-02 | 01 | 1 | GAPI-01b | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_ticket_not_found -x` | ❌ W0 | ⬜ pending |
| 27-01-03 | 01 | 1 | GAPI-01c | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_no_graph_data -x` | ❌ W0 | ⬜ pending |
| 27-01-04 | 01 | 1 | GAPI-01d | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_requires_auth -x` | ❌ W0 | ⬜ pending |
| 27-01-05 | 01 | 1 | GAPI-01e | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_truncation -x` | ❌ W0 | ⬜ pending |
| 27-01-06 | 01 | 1 | GAPI-01f | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_query_params -x` | ❌ W0 | ⬜ pending |
| 27-01-07 | 01 | 1 | GAPI-01g | unit | `cd backend && python -m pytest tests/test_graph_api.py::test_get_graph_neighborhood_deduplication -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_graph_api.py` — stubs for GAPI-01 (all sub-behaviors)
- No new test fixtures needed — existing `client`, `valid_auth_header`, `mock_session` fixtures are sufficient
- No framework install needed — pytest + pytest-asyncio already in dev dependencies

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

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
