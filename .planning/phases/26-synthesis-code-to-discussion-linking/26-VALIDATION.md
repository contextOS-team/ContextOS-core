---
phase: 26
slug: synthesis-code-to-discussion-linking
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | backend/pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && python -m pytest tests/test_synthesis_prompt.py tests/test_synthesis_graph.py tests/test_code_discussion.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_synthesis_prompt.py tests/test_synthesis_graph.py tests/test_code_discussion.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | SYNTH-01 | unit | `cd backend && python -m pytest tests/test_synthesis_prompt.py -x -q` | Exists, needs new tests | ⬜ pending |
| 26-01-02 | 01 | 1 | SYNTH-02 | unit | `cd backend && python -m pytest tests/test_synthesis_prompt.py -x -q` | Exists, needs new tests | ⬜ pending |
| 26-01-03 | 01 | 1 | SYNTH-03 | unit | `cd backend && python -m pytest tests/test_synthesis_prompt.py -x -q` | Exists, needs new tests | ⬜ pending |
| 26-01-04 | 01 | 1 | SYNTH-04 | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py -x -q` | Exists, needs regression test | ⬜ pending |
| 26-02-01 | 02 | 2 | CODE-01 | unit | `cd backend && python -m pytest tests/test_code_discussion.py -x -q` | ❌ W0 | ⬜ pending |
| 26-02-02 | 02 | 2 | CODE-02 | unit | `cd backend && python -m pytest tests/test_code_discussion.py -x -q` | ❌ W0 | ⬜ pending |
| 26-02-03 | 02 | 2 | CODE-03 | unit | `cd backend && python -m pytest tests/test_code_discussion.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_code_discussion.py` — stubs for CODE-01, CODE-02, CODE-03 (new file)
- [ ] New test cases in `backend/tests/test_synthesis_prompt.py` for SYNTH-01/02/03 instruction verification
- [ ] New test case in `backend/tests/test_synthesis_graph.py` for SYNTH-04 regression with new prompt

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LLM produces natural decision trail prose | SYNTH-01 | LLM output quality is non-deterministic | Review generated context page for a ticket with graph decision nodes; verify narrative mentions who decided, where, and what |
| LLM produces human-readable relationship paths | SYNTH-02 | LLM output quality is non-deterministic | Review generated context page; verify relationship explanations read naturally, not as raw graph notation |
| LLM aggregates cross-source person involvement | SYNTH-03 | LLM output quality is non-deterministic | Review Key People section; verify per-person multi-source involvement listed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
