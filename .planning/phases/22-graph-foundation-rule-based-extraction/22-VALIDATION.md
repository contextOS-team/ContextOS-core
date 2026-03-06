---
phase: 22
slug: graph-foundation-rule-based-extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python -m pytest tests/test_graph_extractor.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_graph_extractor.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | GRAPH-01 | integration | `cd backend && python -m pytest tests/test_graph_ops.py::test_node_upsert_dedup -x` | Wave 0 | pending |
| 22-01-02 | 01 | 1 | GRAPH-01 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_fingerprint_deterministic -x` | Wave 0 | pending |
| 22-01-03 | 01 | 1 | GRAPH-02 | integration | `cd backend && python -m pytest tests/test_graph_ops.py::test_traverse_graph_depth -x` | Wave 0 | pending |
| 22-01-04 | 01 | 1 | GRAPH-02 | integration | `cd backend && python -m pytest tests/test_graph_ops.py::test_traverse_workspace_isolation -x` | Wave 0 | pending |
| 22-01-05 | 01 | 1 | GRAPH-03 | manual-only | EXPLAIN ANALYZE on graph queries | N/A | pending |
| 22-02-01 | 02 | 2 | EXTR-01 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_ticket_ref_extraction -x` | Wave 0 | pending |
| 22-02-02 | 02 | 2 | EXTR-01 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_mention_extraction -x` | Wave 0 | pending |
| 22-02-03 | 02 | 2 | EXTR-01 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_pr_ref_extraction -x` | Wave 0 | pending |
| 22-02-04 | 02 | 2 | EXTR-01 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_file_path_extraction -x` | Wave 0 | pending |
| 22-02-05 | 02 | 2 | EXTR-01 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_url_extraction -x` | Wave 0 | pending |
| 22-02-06 | 02 | 2 | EXTR-02 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_no_llm_calls -x` | Wave 0 | pending |
| 22-02-07 | 02 | 2 | EXTR-02 | unit | `cd backend && python -m pytest tests/test_graph_extractor.py::test_reingestion_dedup -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_graph_extractor.py` -- stubs for EXTR-01, EXTR-02 (unit tests for pure regex functions)
- [ ] `backend/tests/test_graph_ops.py` -- stubs for GRAPH-01, GRAPH-02 (integration tests for DB operations)
- [ ] No new framework install needed -- pytest + pytest-asyncio already in dev dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Composite indexes used by query plans | GRAPH-03 | Requires EXPLAIN ANALYZE on live Supabase instance | Run `EXPLAIN ANALYZE SELECT * FROM graph_nodes WHERE workspace_id = '...' AND entity_type = 'Ticket'` in Supabase SQL editor. Verify index scan, not seq scan. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
