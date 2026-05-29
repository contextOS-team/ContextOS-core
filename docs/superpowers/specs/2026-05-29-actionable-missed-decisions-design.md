# Design: Actionable Missed Decisions

**Status:** Draft
**Author:** Codex
**Date:** 2026-05-29
**Scope:** v1 design for replacing broad HITL missed-decision review with source-backed, artifact-verified next actions.

## Motivation

The current missed-decision system is too close to a human review inbox. It can detect source-backed product or engineering decisions, but it still asks the user to decide whether many candidates are worth saving. The target product behavior is stricter:

> Only surface decisions that have a concrete unresolved next action, such as saving a Decision Receipt, creating or updating a Jira/Linear ticket, updating a doc/spec/runbook, or attaching evidence to an existing decision.

The user should not manually confirm obvious memory saves. HITL should be reserved for uncertainty, risky writes, or external artifact changes.

## Current State

The existing pipeline has useful pieces:

- `missed_decision_extractor.py` requires exact source quotes, valid source links, business category, affected objects, expected artifact metadata, and medium/high impact.
- `missed_decision_dedupe.py` classifies candidates against prior candidates, graph nodes, and suggestions as `strong_match`, `weak_match`, or `no_match`.
- `missed_decision_scanner.py` records artifact-search metadata and either auto-confirms, publishes a suggestion, or suppresses.
- `missed_decision_autosave.py` already auto-confirms the safest Decision Receipt candidates: `very_high`, no match, source-backed, attributed, non-risky.
- `missed_decision_actions.py` preserves source evidence when confirmed and keeps external action hints metadata-only.

The weak points are:

- `action_hints` are currently empty at extraction time.
- The artifact search result is not a first-class contract with freshness, query evidence, provider coverage, and a typed next action.
- `no_match` means no strong graph/suggestion match, not necessarily "Jira/Linear/Notion/GitHub/GitLab were searched freshly enough to prove the artifact is missing."
- Review actions are still centered on `confirm`, `add_evidence`, `defer`, and `reject`, not on "create/update this missing artifact."
- Production has existing candidates that need reclassification: a read-only aggregate snapshot on 2026-05-29 showed 136 live candidates, all with empty `action_hints` and null `review_context.missing_artifact_status` / `expected_artifact_type`.

## Product Contract

A missed-decision card is allowed to surface only when the system can state:

1. What was decided, backed by an exact source quote and link.
2. What durable artifact should exist or change.
3. Which artifact sources were searched and whether those sources were fresh enough.
4. Whether a matching artifact already exists.
5. The single recommended next action.
6. Whether that action is safe to perform automatically, safe to draft, or requires human approval.

If any of those are missing, the candidate should remain internal as `detected`, be suppressed, or be reprocessed later. It should not become a user-facing "Needs Review" item.

## Options Considered

### Option A: Tighten the Existing Prompt

Ask the extractor to emit stricter `expected_artifact` and `action_hints`.

This is cheap, but it trusts the model to infer artifact absence without checking local truth. It would still over-surface items when Jira/Linear/Notion/GitHub/GitLab evidence exists but was not retrieved.

### Option B: Multi-Agent Architecture Now

Split the system into extraction, artifact search, action planning, and risk agents.

This matches the conceptual problem, but it adds orchestration cost before the contracts are proven. The first risk is not lack of agents; it is lack of a deterministic actionability contract and eval coverage.

### Option C: Add an Actionability Verifier in the Existing Pipeline

Keep the current scanner pipeline, but insert a deterministic verifier between extraction/dedupe and publish/auto-confirm. The verifier combines deterministic artifact lookup, optional LLM action planning, and a strict routing policy.

This is the recommended v1. It narrows the behavior without a new orchestration framework and gives a clear seam for multi-agent decomposition later.

## Proposed Architecture

Add `ActionabilityVerifier` as a new service used by `process_missed_decision_source_window()` after `classify_missed_decision_candidate()` and before auto-save or suggestion publish.

Pipeline:

1. `Extractor`
   Produces source-backed candidate drafts with exact quote, decision, rationale, affected objects, expected artifact fields, and confidence.

2. `DedupeClassifier`
   Keeps existing candidate, graph, and suggestion matching. Strong matches suppress or link. Weak matches block automatic action.

3. `ArtifactSearchVerifier`
   Searches durable artifacts directly in workspace data:
   - Decision graph nodes and confirmed missed-decision receipts.
   - Existing missed-decision candidates and suggestions.
   - Jira issues and comments.
   - Linear tickets and comments.
   - GitHub PRs and reviews.
   - GitLab MRs and reviews.
   - Notion pages.
   - Context pages or docs already generated by ContextOS when relevant.

4. `ActionPlanner`
   Builds one typed next action only if artifact absence is proven or a match can be resolved:
   - `save_decision_receipt`
   - `draft_ticket`
   - `draft_doc_update`
   - `attach_evidence`
   - `suppress_already_backed`
   - `hold_for_reprocess`

5. `RoutingPolicy`
   Decides the lifecycle:
   - `confirmed`: auto-save internal Decision Receipt when safe.
   - `surfaced`: show only if there is a concrete action the user can take.
   - `linked` or `suppressed`: artifact already exists.
   - `detected`: artifact search is stale, inconclusive, unsupported, or waiting for provider sync.
   - `rejected`: only from explicit user feedback.

## Actionability Payload

Use existing JSON columns for v1: `candidate.evidence["actionability"]`, `candidate.evidence["review_context"]`, and `candidate.action_hints`. No migration is required for the first implementation.

Suggested payload:

```json
{
  "status": "actionable",
  "policy": "actionable_missed_decision_v1",
  "artifact_search": {
    "status": "not_found",
    "searched_sources": [
      {
        "source": "jira_issues",
        "freshness": "fresh",
        "query_terms": ["dashboard", "needs review rail"],
        "matches": []
      }
    ],
    "fresh_enough": true,
    "checked_after_source_timestamp": true
  },
  "next_action": {
    "kind": "draft_ticket",
    "target_provider": "jira",
    "title": "Document dashboard Needs Review rail boundary",
    "body": "Source-backed draft body with quote and link.",
    "write_policy": "draft_external",
    "requires_human": true
  },
  "route_reason": "No fresh Jira/Linear/Notion/GitHub/GitLab/Decision artifact matched the source-backed decision."
}
```

Allowed `status` values:

- `actionable`: exactly one safe next action exists.
- `already_backed`: a durable artifact already exists.
- `possible_match`: a weak match needs disambiguation; do not auto-save.
- `stale_search`: one or more required providers are not fresh enough.
- `unsupported_artifact`: the expected artifact type cannot be searched or drafted yet.
- `insufficient_evidence`: source quote, affected object, rationale, or artifact target is not strong enough.

Allowed `write_policy` values:

- `auto_internal`: safe to auto-save an internal Decision Receipt.
- `draft_external`: safe to draft a Jira/Linear/Notion action, not send/create automatically.
- `review_required`: high-risk or weak-match item needs explicit approval.
- `no_write`: suppress, link, or hold.

## Surface Rules

User-facing cards should be renamed conceptually from "Needs Review" to "Decision actions" or "Unresolved decisions." The UI can keep the existing component initially, but the copy and payload should stop implying generic review.

Surface only these cases:

- `actionable` + `auto_internal`: usually auto-confirm and do not show.
- `actionable` + `draft_external`: show the draft action with evidence and one primary CTA.
- `possible_match`: show only if the match target is a Decision and the next action is `attach_evidence`; otherwise keep internal until better ranking exists.
- `stale_search`: do not show; queue or wait for source sync.

Suppress or hold:

- Existing artifact found strongly.
- No supported action.
- Search coverage is missing or stale.
- Candidate is low confidence, vague, or risky without a concrete draft action.

## Auto-Save Policy

The existing conservative auto-save policy should remain, but it should consume `ActionabilityVerifier` output instead of raw dedupe state.

Auto-save requires:

- `next_action.kind == "save_decision_receipt"`.
- `write_policy == "auto_internal"`.
- Exact quote and resolvable source link.
- Attribution from people or source metadata.
- No strong or weak existing artifact match.
- Artifact search is fresh enough for Decision memory and planned-work sources.
- No high-risk external write implied.

External writes must not happen automatically in v1. Jira/Linear/Notion actions should be drafts with source quote and link attached.

## Artifact Search Freshness

The verifier must not claim "not documented" unless the relevant providers are fresh enough.

For each searched source, record:

- Provider/table searched.
- Whether the provider is connected.
- Last successful sync or webhook freshness if available.
- Whether the search happened after the source decision timestamp.
- Query terms/fingerprints used.
- Strong and weak matches considered.

If a provider is connected but stale, route to `stale_search`. If a provider is disconnected, mark it `not_available` and only claim absence across connected sources.

## Evals

Extend `backend/evals/datasets/missed_decisions/golden.jsonl` with actionability cases:

- Obvious internal memory save should auto-confirm.
- Missing Jira/Linear ticket should produce `draft_ticket`.
- Missing doc/spec/runbook should produce `draft_doc_update`.
- Existing Jira/Linear/Notion/PR artifact should suppress as `already_backed`.
- Weak existing match should route to `possible_match` without auto-save.
- Stale provider search should hold as `stale_search`.
- Risky production/security/billing decision should draft or require review, not auto-save.
- Vague suggestion or discussion-only source should remain rejected by extraction.

Add unit tests for:

- Artifact search over Jira, Linear, GitHub, GitLab, Notion, Graph nodes, suggestions, and existing candidates.
- Actionability routing from verifier output.
- Scanner behavior: auto-save, publish draft action, suppress, or hold.
- API serialization of `actionability` and action-specific labels.
- UI behavior that every surfaced card has one primary next action.

## Backfill and Reclassification

Production already has candidates without actionability metadata. The implementation needs a command or job that reprocesses existing non-terminal candidates:

- Include `detected`, `surfaced`, and `deferred`.
- Skip `confirmed`, `linked`, `suppressed`, and `rejected` unless explicitly requested.
- Recompute artifact search and actionability payload.
- Resolve or hide previously surfaced suggestions if they no longer have a concrete next action.
- Keep existing user review history in `evidence.review_actions`.

Backfill should be idempotent and run in small batches.

## Implementation Plan Boundary

Do not implement multi-agent orchestration in v1. Build the verifier and payload contract first. If the verifier grows into clearly independent components, later split these roles into agents:

- Extractor agent.
- Artifact-search agent.
- Action-planning agent.
- Risk/router agent.

The contract above should remain the interface between those agents if the split happens.

## Open Decisions

- Final UI name: "Decision actions", "Unresolved decisions", or keep "Needs Review" while changing payload semantics.
- Whether Jira/Linear/Notion drafts should be stored only in `action_hints` or also as first-class `Suggestion` details.
- Which provider freshness signal is authoritative per integration.
- Whether `draft_doc_update` should target Notion first, repo docs first, or a generic markdown draft.

## Recommended Next Step

Create an implementation plan for v1:

1. Add `ActionabilityVerifier` types and deterministic tests.
2. Add artifact search adapters for existing local tables.
3. Update scanner routing to require actionability before publish/auto-save.
4. Add backfill command for existing candidates.
5. Update API/UI payloads and labels.
6. Extend evals and run the existing missed-decision test/eval suite.
