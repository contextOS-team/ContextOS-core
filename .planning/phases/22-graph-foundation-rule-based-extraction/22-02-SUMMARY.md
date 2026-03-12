---
phase: 22-graph-foundation-rule-based-extraction
plan: 02
subsystem: services
tags: [regex, extraction, registry-pattern, pure-functions, graph, dedup]

# Dependency graph
requires:
  - phase: 22-01
    provides: graph_nodes and graph_edges tables, GraphNode/GraphEdge models, graph_ops service
provides:
  - ExtractedEntity dataclass for graph entity representation
  - Extractor protocol and registry pattern (register_extractor, run_extractors)
  - 5 deterministic regex extractors (tickets, mentions, PRs, file paths, URLs)
  - Cross-extractor deduplication by (entity_type, external_id)
affects: [22-03, 23-rule-based-extraction, 24-llm-extraction, 25-graph-search-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [registry-based extractor system, protocol-driven pluggability, cross-extractor dedup]

key-files:
  created:
    - backend/src/services/graph_extractor.py
    - backend/tests/test_graph_extractor.py
  modified: []

key-decisions:
  - "Registry pattern with auto-registration at module import for zero-config extractor loading"
  - "Ambiguous PR refs (#123) from non-GitHub sources marked with status=ambiguous in properties"
  - "URL extractor only matches known integration patterns (Linear, GitHub, Notion, Slack) to avoid noise"
  - "Cross-extractor dedup keeps first occurrence when same entity found by multiple extractors"

patterns-established:
  - "Extractor protocol: class with extract(content, source_type) -> list[ExtractedEntity]"
  - "Registry pattern: register_extractor() + run_extractors() with try/except isolation"
  - "Entity identity: (entity_type, external_id) tuple for dedup across extractors"

requirements-completed: [EXTR-01]

# Metrics
duration: 3min
completed: 2026-03-07
---

# Phase 22 Plan 02: Rule-Based Regex Extractors Summary

**Five deterministic regex extractors with registry pattern, cross-extractor dedup, and 39 passing unit tests covering tickets, mentions, PRs, file paths, and integration URLs**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-06T20:08:34Z
- **Completed:** 2026-03-06T20:12:14Z
- **Tasks:** 1 (TDD: test + feat commits)
- **Files modified:** 2

## Accomplishments
- ExtractedEntity dataclass with entity_type, external_id, name, properties, relationship_type
- Extractor Protocol and registry (register_extractor, run_extractors) with try/except error isolation
- TicketRefExtractor: [A-Z]{2,10}-\d{1,6} pattern with case-sensitive prefix, internal dedup
- MentionExtractor: Slack UIDs <@UXXXX> and @username patterns, email address exclusion
- PRRefExtractor: #\d{1,6} PR numbers with ambiguity marking for non-GitHub sources, 7+ hex commit SHAs with all-digit rejection
- FilePathExtractor: 16 common code extensions (.ts, .tsx, .js, .jsx, .py, .rs, .go, .sql, .md, .json, .yaml, .yml, .toml, .css, .html)
- URLExtractor: Linear issue, GitHub PR/commit, Notion page, Slack archive URL resolution to correct entity types
- Cross-extractor dedup by (entity_type, external_id) in run_extractors
- 39 unit tests all passing: happy paths, edge cases, dedup, error isolation, no-LLM static check

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests for regex extractors** - `1305cdf` (test)
2. **Task 1 (GREEN): Implement extractors and pass all tests** - `6daf571` (feat)

_TDD task: test-first then implementation._

## Files Created/Modified
- `backend/src/services/graph_extractor.py` - ExtractedEntity, 5 extractor classes, registry with run_extractors (446 lines)
- `backend/tests/test_graph_extractor.py` - 39 unit tests across 8 test classes (435 lines)

## Decisions Made
- Registry auto-registers all 5 extractors at module import via module-level register_extractor() calls
- PR refs (#123) from non-GitHub sources get properties.status="ambiguous" per RESEARCH.md open question #3
- URL extractor only matches 5 known integration URL patterns to avoid noise (Linear, GitHub PR, GitHub commit, Notion, Slack)
- Cross-extractor dedup keeps first occurrence when same (entity_type, external_id) extracted by multiple extractors (e.g., ticket ref + Linear URL)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test data exceeding regex prefix length**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Test used "PROJECTNAME" (11 chars) as ticket prefix, but regex allows 2-10 uppercase chars
- **Fix:** Changed test to use "PROJECTNAM" (10 chars) to match the intended regex range
- **Files modified:** backend/tests/test_graph_extractor.py
- **Verification:** All 39 tests pass
- **Committed in:** 6daf571 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test data)
**Impact on plan:** Test data fix only, no scope creep.

## Issues Encountered
None beyond the test data fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Extractor registry ready for Plan 03 to wire into webhook handlers via extract_and_populate_graph()
- ExtractedEntity.external_id feeds directly into graph_ops.compute_fingerprint for node creation
- Registry pattern extensible for Phase 24 LLM extractor registration

## Self-Check: PASSED

- FOUND: backend/src/services/graph_extractor.py
- FOUND: backend/tests/test_graph_extractor.py
- FOUND: 22-02-SUMMARY.md
- FOUND: commit 1305cdf (test RED)
- FOUND: commit 6daf571 (feat GREEN)

---
*Phase: 22-graph-foundation-rule-based-extraction*
*Completed: 2026-03-07*
