---
phase: 46
slug: graph-rag-quality-improvements
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 46 - Validation Strategy

> Per-phase validation contract for Graph RAG quality improvements.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest `9.0.2`; Vitest `4.0.18` only if frontend rendering is touched |
| **Config file** | `backend/pyproject.toml`; `apps/web/vitest.config.ts` |
| **Quick run command** | `uv run --directory backend pytest tests/test_linking_graph.py tests/test_synthesis_graph.py tests/test_missed_decision_evals.py tests/test_suggestions.py -q` |
| **Full suite command** | `uv run --directory backend pytest tests/test_linking_graph.py tests/test_synthesis_graph.py tests/test_synthesis_stream.py tests/test_missed_decision_candidates.py tests/test_missed_decision_actions.py tests/test_missed_decision_evals.py tests/test_suggestions.py -q` |
| **Estimated runtime** | ~2-5 minutes |

---

## Sampling Rate

- **After every backend task commit:** Run the narrow pytest command for the touched Graph RAG behavior.
- **After every eval task commit:** Run `uv run --directory backend python -m src.evals.graph_rag --dataset evals/datasets/graph_rag/golden.jsonl --json` once the runner exists.
- **After every plan wave:** Run the Graph RAG eval runner plus phase-scoped linking/synthesis tests.
- **Before `$gsd-verify-work`:** Full phase backend suite must be green; run frontend Vitest only if a plan modifies source/explanation rendering.
- **Max feedback latency:** 5 minutes for phase-scoped automated feedback.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 46-00-01 | 00 | 0 | GRAG-02 | T-46-01 | Eval fixtures are workspace-scoped and measure expected retrieval behavior without live model calls | deterministic eval | `uv run --directory backend pytest tests/test_graph_rag_evals.py -q` | No - W0 | pending |
| 46-00-02 | 00 | 0 | GRAG-02 | T-46-02 | Golden cases cover decision recall, source-link accuracy, stale-context avoidance, action grounding, stream parity, and synthesized-context downranking | deterministic eval | `uv run --directory backend python -m src.evals.graph_rag --dataset evals/datasets/graph_rag/golden.jsonl --json` | No - W0 | pending |
| 46-00-03 | 00 | 0 | GRAG-02, GRAG-04 | T-46-09 | Golden cases cover Phase 45 missed-decision extraction quality and Phase 44 suggestion generator quality, including the current design-review relevance prompt, without relying on live model calls | deterministic eval/unit | `uv run --directory backend pytest tests/test_missed_decision_evals.py tests/test_suggestions.py -q` | Existing - extend | pending |
| 46-01-01 | 01 | 1 | GRAG-01 | T-46-03 | Retrieval targets are explicit and cannot cross workspace boundaries | backend unit/integration | `uv run --directory backend pytest tests/test_linking_graph.py -q` | Existing - extend | pending |
| 46-01-02 | 01 | 1 | GRAG-01, GRAG-04 | T-46-04 | Streaming and non-streaming context generation expose the same graph evidence or an explicit omission reason | backend unit/integration | `uv run --directory backend pytest tests/test_synthesis_stream.py tests/test_synthesis_graph.py -q` | Existing - extend | pending |
| 46-02-01 | 02 | 2 | GRAG-03 | T-46-05 | Ranking keeps workspace scope as a hard filter and exposes graph adjacency, freshness, verification state, and source originality features | backend unit/eval | `uv run --directory backend pytest tests/test_linking_graph.py tests/test_graph_rag_evals.py -q` | Partly W0 | pending |
| 46-02-02 | 02 | 2 | GRAG-03 | T-46-06 | Confirmed source-backed Decisions outrank stale, raw digest, or synthesized context evidence for factual grounding | deterministic eval | `uv run --directory backend python -m src.evals.graph_rag --dataset evals/datasets/graph_rag/golden.jsonl --json` | No - W0 | pending |
| 46-03-01 | 03 | 3 | GRAG-04 | T-46-07 | Context page source metadata includes retrieval target, signals, graph path, freshness, verification state, and explanation fields without treating source text as instructions | backend unit/integration | `uv run --directory backend pytest tests/test_synthesis_graph.py tests/test_synthesis_stream.py -q` | Existing - extend | pending |
| 46-03-02 | 03 | 3 | GRAG-04 | T-46-08 | Future action hints can be explained only from a confirmed Decision or source-backed candidate evidence; Phase 46 does not execute external writes | backend integration | `uv run --directory backend pytest tests/test_missed_decision_actions.py tests/test_missed_decision_evals.py -q` | Existing - extend if needed | pending |
| 46-03-03 | 03 | 3 | GRAG-04 | T-46-10 | Suggestion payloads across implemented families preserve target entity, evidence, provenance, calibrated priority, duplicate/match status where relevant, source quote/link where relevant, and explanation fields; missing-source quality is not hardcoded to design-review only | backend unit/integration | `uv run --directory backend pytest tests/test_missed_decision_candidates.py tests/test_missed_decision_actions.py tests/test_suggestions.py -q` | Existing - extend | pending |
| 46-03-04 | 03 | 3 | GRAG-04 | T-46-11 | Downloaded-report quality mechanisms are reflected in implementation: quote/evidence anchors, selected/dropped evidence traces, verifier-style validators, freshness/supersession fields, and prompt-injection negative cases | backend unit/eval | `uv run --directory backend pytest tests/test_graph_rag_evals.py tests/test_missed_decision_evals.py tests/test_suggestions.py -q` | Partly W0 | pending |
| 46-03-05 | 03 | 3 | GRAG-04 | T-46-12 | LLM-assisted suggestion generators share a common suggestion-family prompt/contract with family-specific policy blocks and structured suppress/show reasons | backend unit/eval | `uv run --directory backend pytest tests/test_suggestions.py tests/test_missed_decision_candidates.py -q` | Existing - extend | pending |
| 46-03-06 | 03 | 3 | GRAG-04 | T-46-13 | LLM-assisted retrieval explanations, extraction, and suggestions return Pydantic/BaseModel structured outputs, but persistence is gated by deterministic source/provenance validators rather than schema conformance alone | backend unit/eval | `uv run --directory backend pytest tests/test_graph_rag_evals.py tests/test_missed_decision_evals.py tests/test_suggestions.py -q` | Existing - extend | pending |

*Status: pending, green, red, flaky*

---

## Wave 0 Requirements

- [ ] `backend/src/evals/graph_rag.py` - deterministic Graph RAG eval runner following the missed-decision eval runner pattern.
- [ ] `backend/evals/datasets/graph_rag/golden.jsonl` - golden cases for GRAG-01 through GRAG-04.
- [ ] `backend/tests/test_graph_rag_evals.py` - runner contract tests and threshold checks.
- [ ] `backend/evals/datasets/missed_decisions/golden.jsonl` - extend cases for false positives, false negatives, duplicate suppression, source-link accuracy, and candidate-to-suggestion quality.
- [ ] `backend/tests/test_suggestions.py` - add Phase 44 suggestion generator quality cases, including design-review relevance cases beyond prompt-text assertions, generic payload/lifecycle provenance checks, and a family-level contract that future missing-source subtypes can reuse.
- [ ] Common suggestion-family prompt/contract - define shared structured assessment fields and family-specific policy blocks for `missing_source_coverage`, `missed_decision`, and future `action_prompt` grounding.
- [ ] Structured anti-hallucination contract - require Pydantic/BaseModel JSON outputs for LLM-assisted extraction, retrieval explanations, and suggestion-family assessment; treat schemas as format gates and deterministic validators as truth gates.
- [ ] Quality trace/explanation schema - define selected/dropped evidence, score breakdown, freshness, verification state, and why-selected/why-suppressed fields for retrieval, candidates, and suggestions.
- [ ] Verifier-style deterministic validators - exact evidence anchor, source-link validity, duplicate/match classification, suggestion payload quality, action grounding, and source-text prompt-injection rejection.
- [ ] `backend/tests/test_synthesis_stream.py` - stream parity fixture that proves graph evidence is present or explicitly omitted.
- [ ] Provider freshness matrix - document source timestamp semantics before ranking changes use freshness.
- [ ] Phase 45 schema checkpoint - verify local missed-decision candidate and suggestion tables exist before integration tests touch Phase 45 evidence/action surfaces.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Retrieval explanations are legible enough for humans and future agents | GRAG-04 | Automated tests can assert fields exist, but not whether the explanation text is useful for debugging or trust | Generate or inspect at least 3 context pages with graph-backed evidence and confirm the source/signal explanation makes clear why each item was selected. |
| Ranking changes improve context quality on real workspace data | GRAG-01, GRAG-03 | Fixture tests cannot prove subjective usefulness across real Slack, docs, tickets, PRs, and Decision nodes | Run the same representative tickets before/after implementation and compare retrieved Decisions, source links, stale-source behavior, and related-work ranking. |
| Phase 44/45 suggestion and AI output quality is visibly better | GRAG-02, GRAG-04 | Golden tests catch regressions, but final usefulness still depends on realistic source text and suggestion copy quality | Inspect at least 5 source-backed missed-decision candidates and 5 suggestions across implemented families before/after changes; confirm lower false positives, valid quote/link provenance where relevant, clear duplicate handling, and no ungrounded action hints. |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 test dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 5 minutes
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-25
