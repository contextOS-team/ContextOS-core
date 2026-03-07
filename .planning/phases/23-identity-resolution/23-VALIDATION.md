---
phase: 23
slug: identity-resolution
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python -m pytest tests/test_identity_resolution.py -x` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_identity_resolution.py -x`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | IDENT-01 | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestEmailResolution -x` | ❌ W0 | ⬜ pending |
| 23-01-02 | 01 | 1 | IDENT-01 | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestInlineResolution -x` | ❌ W0 | ⬜ pending |
| 23-02-01 | 02 | 1 | IDENT-02 | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestSlackRoster -x` | ❌ W0 | ⬜ pending |
| 23-02-02 | 02 | 1 | IDENT-02 | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestLinearRoster -x` | ❌ W0 | ⬜ pending |
| 23-02-03 | 02 | 1 | IDENT-02 | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestGitHubRoster -x` | ❌ W0 | ⬜ pending |
| 23-03-01 | 03 | 2 | IDENT-03 | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestFuzzyMatching -x` | ❌ W0 | ⬜ pending |
| 23-03-02 | 03 | 2 | IDENT-03 | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestFuzzyMatching::test_below_threshold -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_identity_resolution.py` — stubs for IDENT-01, IDENT-02, IDENT-03
- [ ] `rapidfuzz>=3.0` in pyproject.toml dependencies — required for IDENT-03 fuzzy matching

*Existing pytest + pytest-asyncio infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Slack re-authorization after scope change | IDENT-02 | OAuth flow requires browser interaction | 1. Disconnect Slack integration 2. Re-authorize with updated scopes 3. Verify users:read.email granted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
