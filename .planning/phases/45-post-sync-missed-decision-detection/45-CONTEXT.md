# Phase 45: Post-sync Missed-decision Detection - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

After relevant source syncs complete, ContextOS scans newly synced workspace content for high-confidence decisions that were discussed but not yet clearly documented, planned, or saved as decision memory. The phase creates missed-decision candidates with source-backed evidence, routes reviewable items through the Phase 44 suggestion surface, and lets users confirm, reject, defer, or add useful evidence to existing artifacts.

This phase depends on Phase 44's durable suggestion model and bounded dashboard suggestion surface. It should not build the confirmed action layer, external write actions, autonomous task/doc creation, or bot action flows. Confirmation means the candidate becomes trusted decision memory first; any action hints are stored for later phases.

</domain>

<decisions>
## Implementation Decisions

### Scan Trigger and Source Window
- **D-01:** Missed-decision scans should run after relevant source syncs. Conversation and document sources are prioritized first, but the trigger contract can attach to existing provider sync completion events.
- **D-02:** Use per-workspace/per-source `last_missed_decision_scan_at` checkpoints. After a successful source sync, scan newly synced content since the last successful missed-decision scan for that source.
- **D-03:** Only advance `last_missed_decision_scan_at` after the missed-decision scanner succeeds. Provider sync success must not depend on scanner success.
- **D-04:** First scan fallback: if no checkpoint exists, scan the later of source connection time or `now - 14 days`. Do not scan full workspace history by default.
- **D-05:** Slack, Telegram, Fathom, and Notion can originate missed-decision candidates. Tickets, PRs, reviews, and code primarily attach as supporting evidence unless a later phase expands origin sources.
- **D-06:** Scanning runs as a retryable/observable background job after source sync completion. Provider sync should stay fast and successful even when missed-decision scanning fails.

### Candidate Strictness and Dedupe
- **D-07:** Candidate creation should be high-confidence only. Prefer fewer, stronger missed-decision candidates over noisy recall.
- **D-08:** A high-confidence MVP candidate must include exact source passage or decision quote, inferred decision, inferred rationale, and source link.
- **D-09:** People involved, affected workstream/system, and multi-source corroboration enrich confidence and ranking but are not required to surface a candidate.
- **D-10:** Confidence tiers:
  - High: quote/source passage, inferred decision, inferred rationale, and source link.
  - Very high: high-confidence fields plus people/affected system and a supporting source or matching artifact.
  - Needs review: decision-like language with missing rationale or unclear source. Hide by default or place in a separate review bucket.
- **D-11:** Suppress or attach a candidate when the same decision is already clearly represented in an existing Decision node, unresolved/handled suggestion, Linear/Jira ticket, Notion/doc page, or PR. Topical similarity alone is not enough; the artifact must clearly encode the same decision, rationale, or planned action.
- **D-12:** Dedupe works in layers:
  1. Exact/near-exact source quote fingerprint to prevent repeats from the same content.
  2. Normalized semantic fingerprint of inferred decision text to catch paraphrases across sources.
  3. Semantic similarity against existing Decision nodes, suggestions, tickets, docs, and PRs to classify strong, weak, or no match.
  4. Graph neighborhood, including people, systems, projects, tickets, docs, and time window, as confidence booster/tie-breaker only.
- **D-13:** Strong match suppresses the candidate and attaches new source evidence. Weak match surfaces as possible existing capture. No match surfaces as a missed decision.

### Review Surface and Statuses
- **D-14:** Use both a `missed_decision_candidate` record and a generic `suggestion` record. The candidate is the source of truth for detection/provenance/scoring; the suggestion is the user-visible review/action state.
- **D-15:** Candidate owns detected decision, quote/rationale/source links, evidence, confidence, fingerprints/dedupe, scan run, match/suppression status, retry/rescoring history.
- **D-16:** Suggestion owns what the user sees, review state, dismiss/snooze/accept/resolve state, recommended action, and user feedback.
- **D-17:** A suggestion should reference the missed-decision candidate via `entity_type`/`entity_id` or a direct `candidate_id`. Keep Phase 45 detection clean while letting Phase 44 remain a generic suggestion surface for future suggestion types.
- **D-18:** Candidate lifecycle should stay compact: `detected`, `surfaced`, `suppressed`, `linked`, `confirmed`, `rejected`, `deferred`. Operational scan/run state belongs on scan jobs/runs, not the main product lifecycle.
- **D-19:** Review UI actions are Confirm, Reject, Defer, and evidence/duplicate actions. Do not introduce task/doc/PR-comment writes in this phase.
- **D-20:** User-facing labels should be `Add as evidence`, `Ignore duplicate`, and `Save as new decision`; avoid "Link existing" as user-facing language.
- **D-21:** Missed-decision suggestions appear in a bounded post-sync `Needs review` suggestions area on the dashboard, not inside Recent decisions.
- **D-22:** Recent decisions stays reserved for confirmed Decision nodes. Missed-decision suggestions are unconfirmed candidates and need a separate review surface.
- **D-23:** Show the Needs review section after sync completion when open suggestions exist. Display the top 3-5 suggestions with actions: Confirm, Add as evidence, Defer, Reject/Ignore duplicate, plus a later View all route. Hide the section when there are no open suggestions.

### Confirmed Outcome
- **D-24:** When the user confirms a missed decision, first promote/create it as a confirmed Decision node / Decision Receipt and preserve the source trail.
- **D-25:** Confirmation means "this is now trusted decision memory."
- **D-26:** Confirmed Decision Receipt should preserve decision, rationale, source quote/link, confidence, people involved, and affected systems/workstreams.
- **D-27:** After the receipt exists, Phase 45 may record optional action hints such as create task, draft doc/ADR, ask owner, set review date, or save only. These are hints only; Phase 47 turns them into confirmed actions.
- **D-28:** Strong duplicate with no new value should be suppressed automatically with reason `duplicate_no_new_evidence` and no user-visible suggestion.
- **D-29:** Same decision with useful new evidence should surface only if confirmation is needed. Accepting `Add as evidence` marks the candidate `linked`, attaches source quote/rationale/source link to the existing Decision Receipt/task/doc/PR, and resolves the suggestion.
- **D-30:** Weak/ambiguous match should show review choices: Add as evidence, Save as new decision, Ignore duplicate, Dismiss.

### Agent Discretion
- Planners may choose exact table names, job mechanism, endpoint boundaries, and field shapes as long as the locked candidate/suggestion ownership split is preserved.
- Planners may choose exact confidence thresholds and semantic matching implementation, but must preserve the high-confidence-only user-visible MVP and layered dedupe behavior.
- Planners may decide whether first implementation hides "Needs review" items completely or keeps them in an internal bucket, as long as they do not pollute the main suggestions surface.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Scope and Requirements
- `.planning/ROADMAP.md` - Phase 45 goal, dependency on Phase 44, success criteria, and execution order.
- `.planning/REQUIREMENTS.md` - GAP-01 through GAP-04, plus suggestion/action-layer boundaries.
- `.planning/PROJECT.md` - Product positioning, stack constraints, and v1.4 milestone goal.
- `.planning/STATE.md` - Current milestone state and accumulated decisions.

### Prior Decisions
- `.planning/phases/42-landing-positioning-and-seo-launch-rewrite/42-CONTEXT.md` - Decision Receipt is the product-proof primitive and source-backed decision memory is the core positioning.
- `.planning/phases/41-dashboard-pulse-redesign/41-CONTEXT.md` - Dashboard must stay quiet, bounded, and Recent decisions remains the primary confirmed-decision hierarchy.
- `.planning/phases/40-telegram-shared-bot-migration/40-CONTEXT.md` - Telegram ingestion and graph extraction patterns for shared-bot message sources.

### Codebase Maps
- `.planning/codebase/STACK.md` - FastAPI, Supabase, Redis, OpenAI/Gemini, Next.js, and testing stack.
- `.planning/codebase/ARCHITECTURE.md` - Sync scheduler, background workers, graph, activity events, and workspace-scoped architecture.
- `.planning/codebase/INTEGRATIONS.md` - Provider sync surfaces and source systems.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/services/sync_adapter.py` - `SyncRunLogger`, `emit_activity`, `SyncCursor`, and sync status helpers provide the current sync-completion and workspace/provider sync-state patterns.
- `backend/src/services/digest.py` - Existing structured message digest extracts explicit decisions from Slack/Telegram style messages, emits `messages_digest`, and creates graph Decision nodes.
- `backend/src/services/llm_extractor.py` - Existing LLM extraction schema includes decision description, rationale, exact `source_quote`, confidence, person, and ticket refs with anti-hallucination quote validation.
- `backend/src/services/dashboard_resurfaced.py` - Existing heuristic for decision-like Slack messages can inform MVP candidate heuristics but is too broad/noisy to be the final user-visible candidate source.
- `backend/src/services/graph_extractor.py` and `backend/src/services/graph_ops.py` - Rule-based graph extraction and graph upsert patterns can attach tickets, people, PRs, docs, URLs, and source relationships.
- `backend/src/models/graph_node.py` and `supabase/migrations/00027_graph_tables.sql` - Decision nodes already exist in the graph model with workspace-scoped fingerprint dedupe and JSONB properties.
- `apps/web/src/app/dashboard/pulse/recent-decisions.tsx` and `apps/web/src/app/dashboard/decisions/decision-node.ts` - Current dashboard renders confirmed graph Decision nodes and source quotes; missed-decision suggestions should stay separate from this surface.

### Established Patterns
- Workspace scope is mandatory for every data model and query.
- Activity events are fail-silent and should not poison outer transactions.
- Provider sync is already represented through `sync_started` and `sync_completed` events and provider-specific sync cursors.
- Graph features are additive and fail-silent where they touch ingestion.
- Dashboard home should remain bounded and scan-friendly; open suggestions must not take over the page.
- Phase 44 owns generic suggestion state. Phase 45 should extend it rather than creating a second user-visible queue.

### Integration Points
- Source sync completion: provider services and routers that emit `sync_completed` activity events.
- Scan checkpoints: likely adjacent to `SyncCursor` or a new source-scoped scanner state table keyed by workspace/source.
- Candidate persistence: new missed-decision candidate model/table with scan-run, evidence, confidence, fingerprint, and match/suppression state.
- Suggestion surface: Phase 44 suggestion table and dashboard section, with candidate referenced as the source entity.
- Confirmation path: graph Decision node / Decision Receipt creation and evidence attachment.
- Dashboard UI: bounded post-sync Needs review section, not Recent decisions.

</code_context>

<specifics>
## Specific Ideas

- The first scan fallback should be exactly bounded: last 14 days or since the source was connected, whichever is later.
- Useful new evidence includes better rationale, original source, people involved, rejected alternative, affected system, or confirmation.
- User-facing review language should avoid "Link existing" and use clearer action labels:
  - Add as evidence
  - Ignore duplicate
  - Save as new decision
- Action hints after confirmation may include create task, draft doc/ADR, ask owner, set review date, or save only, but no action-layer write flow ships here.

</specifics>

<deferred>
## Deferred Ideas

- Create tasks, draft docs/ADRs, ask owners, set review dates, post PR comments, or otherwise execute follow-up actions. These belong to Phase 47 confirmed action layer.
- Expand origin sources so Linear/Jira/GitHub/GitLab comments and reviews can create missed-decision candidates directly. For this phase they primarily attach as supporting evidence.
- Full review page with View all route can follow after the bounded dashboard surface exists.
- Autonomous or low-risk automatic action execution is outside v1.4 Phase 45.

</deferred>

---

*Phase: 45-post-sync-missed-decision-detection*
*Context gathered: 2026-05-24*
