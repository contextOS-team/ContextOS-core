---
phase: 25
slug: graph-enhanced-retrieval
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && python -m pytest tests/test_linking_graph.py tests/test_synthesis_graph.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_linking_graph.py tests/test_synthesis_graph.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 0 | GRAPH-SIGNAL | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_find_graph_results_basic -x` | Wave 0 | pending |
| 25-01-02 | 01 | 0 | GRAPH-FALLBACK | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_find_graph_results_no_node -x` | Wave 0 | pending |
| 25-01-03 | 01 | 0 | GRAPH-ERROR | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_find_graph_results_error_silent -x` | Wave 0 | pending |
| 25-01-04 | 01 | 0 | DEPTH-DECAY | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_depth_decay_scoring -x` | Wave 0 | pending |
| 25-01-05 | 01 | 0 | SAME-AS | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_same_as_transparent -x` | Wave 0 | pending |
| 25-01-06 | 01 | 0 | MERGE-3WAY | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_three_signal_merge -x` | Wave 0 | pending |
| 25-01-07 | 01 | 0 | TOKEN-BUDGET | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_token_budget_basic -x` | Wave 0 | pending |
| 25-01-08 | 01 | 0 | TOKEN-DIVERSITY | unit | `cd backend && python -m pytest tests/test_linking_graph.py::test_token_budget_diversity -x` | Wave 0 | pending |
| 25-01-09 | 01 | 0 | GRAPH-SECTION | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py::test_format_graph_section -x` | Wave 0 | pending |
| 25-01-10 | 01 | 0 | DECISION-FMT | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py::test_decision_node_format -x` | Wave 0 | pending |
| 25-01-11 | 01 | 0 | E2E-MERGE | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py::test_generate_includes_graph -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_linking_graph.py` — stubs for GRAPH-SIGNAL, GRAPH-FALLBACK, GRAPH-ERROR, DEPTH-DECAY, SAME-AS, MERGE-3WAY, TOKEN-BUDGET, TOKEN-DIVERSITY
- [ ] `backend/tests/test_synthesis_graph.py` — stubs for GRAPH-SECTION, DECISION-FMT, E2E-MERGE

*Existing infrastructure covers framework needs — pytest and pytest-asyncio are already in dev dependencies.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
