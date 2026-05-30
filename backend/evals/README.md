# ContextOS Evals

ContextOS evals are separate from tracing. Langfuse and Laminar tell us what a
run did; evals decide whether the run was good against labeled expectations.

## Current Eval

Run the deterministic missed-decision eval:

```bash
make eval-missed-decisions
```

The bundled dataset lives at:

```text
backend/evals/datasets/missed_decisions/golden.jsonl
```

This eval is CI-safe and does not call a live model. Each row contains source
text, expected candidates, and structured candidate output. The runner validates
source quotes and links through the production missed-decision validator, then
reports precision, recall, invalid candidate drops, and threshold pass/fail.

## Testing Split

Deterministic evals validate AI/output contracts: source-backed extraction,
serialized suggestion payloads, and actionability metadata such as status,
write policy, and copyable draft fields.

Mocked unit and workflow tests validate orchestration, persistence, provider
boundaries, and UI behavior around those contracts.

CI evals must stay deterministic: no live model calls, no database writes, and
no external provider writes.

## Why Traces Are Not Enough

Tracing answers operational questions:

- Which prompt/model/tool path ran?
- What did retrieval include?
- How much latency and cost did the run add?
- Which source, scan, candidate, suggestion, or action did a run touch?

Evals answer quality and regression questions:

- Did this source-backed decision get found?
- Was a weak discussion correctly ignored?
- Did the candidate preserve an exact quote and valid source link?
- Did a code change reduce precision or recall?

Use Langfuse/Laminar traces as evidence and debugging context for eval failures,
not as the quality gate itself.

## Nightly Role

PR/local evals should stay deterministic and fast. A future nightly job should
replay larger labeled datasets through live model paths, then persist reports and
link traces. Nightly matters because live-model quality, prompts, retrieval data,
and synced source distributions can drift even when deterministic unit tests and
trace collection still pass.
