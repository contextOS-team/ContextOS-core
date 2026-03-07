---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: GraphRAG
status: executing
stopped_at: Completed 25-02-PLAN.md (Phase 25 complete)
last_updated: "2026-03-07T23:35:06.866Z"
last_activity: 2026-03-08 -- Phase 25 Plan 02 complete
progress:
  total_phases: 13
  completed_phases: 10
  total_plans: 25
  completed_plans: 25
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-07)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** v1.2 GraphRAG -- Phase 25 complete, ready for Phase 26

## Current Position

Phase: 25 of 27 (Graph-Enhanced Retrieval) -- COMPLETE
Plan: 2 of 2 in current phase (phase complete)
Status: Executing
Last activity: 2026-03-08 -- Phase 25 Plan 02 complete

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 40 (v1.0: 16, v1.1: 14, v1.2: 10)
- Average duration: ~4min
- Total execution time: ~2.7 hours

**Recent Trend (v1.2):**
- Last 5 plans: 24-02 (8min), 24-03 (5min), 25-01 (7min), 25-02 (6min)
- Trend: Stable (5-8min per plan)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.2 Roadmap]: AGE pivoted to plain PG tables -- graph_nodes + graph_edges with recursive CTEs, works on Supabase Cloud today
- [v1.2 Roadmap]: Rule-based + LLM two-tier extraction -- regex inline at zero cost, Gemini Flash batch for semantic entities
- [v1.2 Roadmap]: Blend graph with existing hybrid search -- additive improvement, not replacement
- [v1.2 Roadmap]: Graph explorer frontend (GAPI-02) deferred to Future -- API endpoint ships in v1.2, React visualization later
- [v1.2 Roadmap]: 6 phases derived from 26 requirements across 8 categories, phases 22-27
- [v1.2 Roadmap]: Phases 23 + 24 can parallelize after Phase 22 (independent code paths, same destination tables)
- [v1.2 Roadmap]: Phases 26 + 27 can parallelize after Phase 25
- [Phase 22-01]: SHA-256 fingerprint from entity_type:external_id for deterministic graph node dedup
- [Phase 22-01]: ON CONFLICT upsert clears deleted_at to restore soft-deleted graph records
- [Phase 22-01]: Recursive CTE with path array cycle detection for traverse_graph() SECURITY DEFINER function
- [Phase 22-02]: Registry pattern with auto-registration at module import for zero-config extractor loading
- [Phase 22-02]: Ambiguous PR refs from non-GitHub sources marked with status=ambiguous in properties
- [Phase 22-02]: URL extractor matches only 5 known integration patterns to avoid noise entities
- [Phase 22-03]: Graph extraction runs for ALL content regardless of team sync status for broad reference capture
- [Phase 22-03]: Entity nodes from extractors marked with status=unresolved for dangling reference tracking
- [Phase 22-03]: Backfill script processes 7 source types sequentially with configurable batch size
- [Phase 23-01]: Canonical Person nodes use external_id='canonical:{UUID}' for stable fingerprint decoupled from email changes
- [Phase 23-01]: resolve_by_email groups by email and assigns shared canonical_person_id to all mappings in group
- [Phase 23-01]: Inline resolution is fail-silent matching Phase 22-03 pattern -- errors logged but never raised
- [Phase 23-01]: Email-based deterministic matching anchored on email, never auto-merge on name alone
- [Phase 23-02]: Roster seeding is fail-silent -- integration sync never fails due to identity resolution errors
- [Phase 23-02]: Fuzzy name matching uses rapidfuzz token_sort_ratio with threshold 80 and confidence 0.5-0.9
- [Phase 23-02]: GitHub roster deduplicates collaborators across all repos before per-user email lookup
- [Phase 23-02]: Candidate same_as edges have status=candidate and match_type=fuzzy_name -- never auto-merged
- [Phase 24-01]: All Pydantic extraction fields required with no defaults for Gemini SDK response_schema compatibility
- [Phase 24-01]: Case-insensitive source_quote matching in validate_extraction for LLM case flexibility
- [Phase 24-01]: Case-preserving content hash (Hello != hello) because different-cased content is semantically different
- [Phase 24-01]: 50-char minimum threshold for LLM extraction cost optimization (higher than real-time filter)
- [Phase 24-02]: Module-level attribute access for graph_ops (graph_ops.upsert_node) for mockability with lazy imports
- [Phase 24-02]: Decision external_id uses source_quote hash for deterministic dedup -- same quote always same node
- [Phase 24-02]: sys.modules pre-population with mock graph_ops in tests avoids sqlmodel dependency chain
- [Phase 24]: Batch pipeline uses asyncio.gather with Semaphore for concurrent Gemini calls within each batch
- [Phase 25]: Graph signal weight 0.8 (equal to hybrid), additive score boosting for overlaps
- [Phase 25]: 2,000 token unified budget for ALL retrieval signals, signal diversity first trimming
- [Phase 25]: Separate graph section in synthesis prompt with decision node highlighting
- [Phase 25]: same_as edges followed transparently (don't count as hop), silent fallback for missing graph nodes
- [Phase 25-01]: Exponential decay WEIGHT_GRAPH * DEPTH_DECAY^depth -- depth-1=0.48, depth-2=0.288
- [Phase 25-01]: same_as nodes skipped as results, tracked for path-based depth adjustment
- [Phase 25-01]: Graph results capped at 20 to prevent same_as expansion explosion
- [Phase 25-01]: Decision nodes formatted with [DECISION] highlighting and metadata fields
- [Phase 25-02]: Token estimation heuristic (char_length + 50) // 4 -- avoids tokenizer dependency
- [Phase 25-02]: Signal diversity first trimming -- reserve top-1 from each signal group before filling by score
- [Phase 25-02]: Graph items separated in synthesis by checking for 'graph:' prefix in signals list
- [Phase 25-02]: SYNTHESIS_TEMPLATE {graph_section} placeholder renders empty string when no graph items

### Pending Todos

None yet.

### Blockers/Concerns

- LLM entity extraction hallucination risk -- must validate against source text, structured output, temperature 0
- Graph context flooding synthesis prompts -- enforce fixed token budget (~2,000 tokens), depth decay scoring
- Recursive CTE + RLS performance -- SECURITY DEFINER function validates workspace once, must benchmark on Supabase Cloud
- Identity resolution false merges -- never auto-merge on name alone, anchor on platform user IDs

## Session Continuity

Last session: 2026-03-07T23:28:17Z
Stopped at: Completed 25-02-PLAN.md (Phase 25 complete)
Resume file: Next phase (26 or 27)
