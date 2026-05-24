# Phase 45: Post-sync Missed-decision Detection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 45-post-sync-missed-decision-detection
**Areas discussed:** Scan trigger and source window, Candidate strictness and deduping, Review surface and statuses, Confirmed outcome

---

## Scan Trigger and Source Window

| Question | Options Considered | User's Choice | Notes |
|---|---|---|---|
| When should missed-decision scans run? | After relevant source syncs; Conversation-heavy only; Manual/full sync only; You decide | After relevant source syncs | Conversation/doc sources are prioritized first. |
| What time window should the scan use after a sync? | Since last successful scan per source; Recent rolling window; Sync payload only; You decide | Since last successful scan per source, with first-scan fallback | User clarified checkpoint semantics: per-workspace/per-source `last_missed_decision_scan_at`, advance only after scanner success, first scan bounded to last 14 days or source connection time. |
| Which sources should create candidates, versus only attach evidence? | Conversation/doc sources create candidates; All synced sources can create candidates; Conversation-only at first | Conversation/doc sources create candidates | Slack, Telegram, Fathom, and Notion originate candidates; tickets, PRs, reviews, and code primarily attach evidence. |
| How should the scan run after sync completion? | Background job; Inline at end of sync; Scheduled batch only; You decide | Background job | Provider sync should remain successful even if scanner fails; scanner failures should be retryable and observable separately. |

---

## Candidate Strictness and Deduping

| Question | Options Considered | User's Choice | Notes |
|---|---|---|---|
| How selective should candidate creation be? | High-confidence only; High + medium confidence; Two lanes | High-confidence only | Prefer fewer, stronger candidates over noisy recall. |
| What should count as already documented or planned? | Existing Decision node or suggestion; Decision + planning/work items; Strict source-backed duplicate only | Decision + planning/work items, with strict semantic matching | Suppress or attach only when the same decision is clearly represented in a Decision node, suggestion, ticket, doc, or PR. Topical similarity alone is insufficient. |
| What evidence minimum should a high-confidence candidate need? | Decision quote + rationale + source link; Add people and affected workstream; Multi-source corroboration | Decision quote + rationale + source link | MVP minimum is exact source passage, inferred decision, inferred rationale, and source link. People/workstream/corroboration enrich confidence but are not required. |
| How should dedupe identify the same decision? | Normalized semantic fingerprint; Source quote fingerprint first; Graph neighborhood match | Layered dedupe | First exact/near-exact source quote fingerprint, then normalized semantic decision fingerprint, then semantic matching against existing artifacts, with graph neighborhood as tie-breaker. |

---

## Review Surface and Statuses

| Question | Options Considered | User's Choice | Notes |
|---|---|---|---|
| How should missed-decision candidates be modeled with the Phase 44 suggestion system? | Suggestion type with embedded fields; Separate candidate model linked to suggestion; Both, candidate as source of truth | Both, candidate as source of truth | Candidate owns detection/provenance/scoring. Suggestion owns user-visible review/action state. |
| What statuses should candidates have underneath visible suggestion states? | Detected -> surfaced/suppressed/linked -> confirmed/rejected/deferred; Pipeline-oriented statuses; Minimal hidden statuses only | Compact lifecycle | Operational scan/run state should live separately on scan jobs/runs. |
| What actions should the review UI offer? | Confirm, reject, defer, link existing; Confirm, reject, defer only; Add create task/doc draft now | Confirm, Reject, Defer, and evidence/duplicate actions | External write actions are deferred to Phase 47. |
| Where should these suggestions appear in the product? | Bounded post-sync suggestions area; Inside Recent decisions; Dedicated review page only | Bounded post-sync Needs review area | Recent decisions remains confirmed Decision nodes only. Show top 3-5 open suggestions after sync completion, hide when empty, and add View all later. |

---

## Confirmed Outcome

| Question | Options Considered | User's Choice | Notes |
|---|---|---|---|
| When the user confirms a missed decision, what should happen first? | Create confirmed Decision node/Decision Receipt immediately; Create follow-up suggestion; Ask user each time | Create confirmed Decision node/Decision Receipt immediately | Confirmation means trusted decision memory. Optional next-step suggestions come after the receipt exists. |
| What fields must be preserved on the confirmed Decision Receipt? | Decision, rationale, source quote/link, confidence, people, affected systems/workstreams; MVP minimum only; Full audit bundle | Decision, rationale, source quote/link, confidence, people, affected systems/workstreams | The receipt should be useful and source-backed without exposing every scanner internals field. |
| How should matching existing artifacts behave? | Attach evidence; Keep both but cross-link; Ask confirm-or-attach each time | Add as evidence / Ignore duplicate / Save as new decision | Strong duplicate with no new value is suppressed. Same decision with useful new evidence can be added as evidence. Weak match offers Add as evidence, Save as new decision, Ignore duplicate, Dismiss. |
| After confirmation, what should Phase 45 do with follow-up actions? | Record action hints only; Create follow-up suggestions; Ask per confirmation | Record action hints only | Phase 45 should not create action-layer suggestions or external-write flows. Phase 47 can turn hints into confirmed actions later. |

---

## Agent Discretion

- Exact table names, job mechanism, endpoint boundaries, field shapes, confidence thresholds, and semantic matching implementation are left to planning.
- Planning must preserve the locked candidate/suggestion ownership split, high-confidence-only user-visible MVP, and layered dedupe behavior.

## Deferred Ideas

- Confirmed action-layer writes such as task creation, doc/ADR drafts, owner asks, review dates, and PR comments.
- Direct candidate origination from ticket/PR/review/code sources.
- Full suggestions review page beyond the bounded dashboard surface.
