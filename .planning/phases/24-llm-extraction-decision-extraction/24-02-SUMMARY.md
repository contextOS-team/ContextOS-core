---
phase: 24-llm-extraction-decision-extraction
plan: 02
subsystem: api
tags: [gemini, llm-extraction, structured-output, decision-graph, graph-persistence, pydantic]

# Dependency graph
requires:
  - phase: 24-llm-extraction-decision-extraction
    plan: 01
    provides: Pydantic extraction schemas, content pre-filter, source validation, content hash
  - phase: 22-graph-schema-rule-extraction
    provides: graph_ops upsert_node/upsert_edge, entity_type CHECK constraint includes Decision/Blocker
provides:
  - extract_entities() Gemini Flash extraction with structured output and temperature=0
  - EXTRACTION_SYSTEM_PROMPT targeting decision language patterns
  - get_gemini_client() using Settings.GEMINI_API_KEY
  - persist_decision() creating Decision nodes with discussed_in, authored_by, references edges
  - persist_blocker() creating Blocker nodes with blocks edges
affects: [24-03, 25-graph-synthesis]

# Tech tracking
tech-stack:
  added: []
  patterns: [gemini-structured-output, lazy-graph-ops-import, source-quote-hash-external-id]

key-files:
  created: []
  modified:
    - backend/src/services/llm_extractor.py
    - backend/tests/test_llm_extractor.py

key-decisions:
  - "Module-level attribute access for graph_ops (graph_ops.upsert_node) instead of from-import for mockability with lazy imports"
  - "sys.modules pre-population for mock graph_ops in tests avoids sqlmodel dependency chain"
  - "Decision external_id uses source_quote hash for deterministic dedup -- same quote always same node"

patterns-established:
  - "Lazy graph_ops import: use `from src.services import graph_ops` inside function body, access via graph_ops.upsert_node() for testability"
  - "Mock module injection: pre-populate sys.modules with mock graph_ops to avoid heavy ORM import chain in unit tests"
  - "Decision persistence: Decision -> discussed_in -> Source, Decision -> authored_by -> Person, Decision -> references -> Ticket"

requirements-completed: [EXTR-03, EXTR-04, DECIDE-01, DECIDE-02]

# Metrics
duration: 8min
completed: 2026-03-07
---

# Phase 24 Plan 02: Gemini Extraction Service and Decision Persistence Summary

**Gemini Flash structured extraction with temperature=0, decision language system prompt, and Decision/Blocker graph node persistence with discussed_in/authored_by/references/blocks edges**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-07T17:45:08Z
- **Completed:** 2026-03-07T17:53:32Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Gemini Flash extraction service (extract_entities) with structured output, temperature=0, and Pydantic response_schema
- EXTRACTION_SYSTEM_PROMPT targeting decision language: agreed, decided, going with, let's do, approved
- Decision node persistence with all DECIDE-02 properties: description, rationale, source_quote, confidence, status, extraction_model
- Decision edge creation: discussed_in (to source), authored_by (to person), references (to tickets)
- Blocker node persistence with blocks edge to source content
- External IDs use source_quote hash for deterministic fingerprint dedup
- 16 new tests across 4 test classes (TestLLMExtraction, TestDecisionExtraction, TestDecisionNodeSchema, TestDecisionEdges)

## Task Commits

Each task was committed atomically:

1. **Task 1: Gemini extraction service with structured output** - `6d33a0e` (feat)
2. **Task 2: Decision and blocker persistence to graph nodes and edges** - `b5b2ab3` (feat)

_Note: TDD tasks -- RED phase tests committed separately (e8b9eb4, c3df9c7), GREEN phase includes both implementation and test fixes_

## Files Created/Modified
- `backend/src/services/llm_extractor.py` - Added EXTRACTION_SYSTEM_PROMPT, get_gemini_client, extract_entities, persist_decision, persist_blocker
- `backend/tests/test_llm_extractor.py` - 16 new tests across 4 classes for extraction service and graph persistence

## Decisions Made
- Module-level attribute access pattern (`graph_ops.upsert_node()`) instead of `from ... import` for lazy imports -- enables `patch("src.services.graph_ops.upsert_node")` to work correctly in tests
- sys.modules pre-population with mock graph_ops module to avoid sqlmodel/SQLAlchemy import chain in unit tests
- Decision external_id uses `compute_content_hash(source_quote)` for deterministic dedup -- same quote from any source always produces the same Decision node fingerprint

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Changed from lazy `from ... import` to module attribute access for graph_ops**
- **Found during:** Task 2 (Decision persistence)
- **Issue:** Plan specified `from src.services.graph_ops import upsert_node, upsert_edge` inside function body. This lazy import pattern creates local variable bindings that cannot be intercepted by `unittest.mock.patch` -- the mock replaces the module attribute but the local binding already points to the original function. Additionally, importing graph_ops at module level triggers sqlmodel dependency chain which is not available in the unit test environment.
- **Fix:** Changed to `from src.services import graph_ops` and access functions as `graph_ops.upsert_node(...)`. This allows patch to replace the attribute on the module object, which is looked up dynamically at call time. Added sys.modules mock setup in test file to provide a lightweight graph_ops module.
- **Files modified:** backend/src/services/llm_extractor.py, backend/tests/test_llm_extractor.py
- **Verification:** All 39 tests pass including 8 new persistence tests
- **Committed in:** b5b2ab3 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed test assertions to use call_args_list filtering instead of call_args for multi-call mocks**
- **Found during:** Task 2 (Decision persistence tests)
- **Issue:** Tests used `mock_upsert_node.call_args.kwargs` which returns the LAST call. When ticket_refs is non-empty, the last upsert_node call is for the Ticket node, not the Decision node. This caused KeyError on "properties" since Ticket nodes have no explicit properties.
- **Fix:** Added `_find_decision_node_call()` helper that filters call_args_list by entity_type="Decision" to get the correct call regardless of call ordering.
- **Files modified:** backend/tests/test_llm_extractor.py
- **Verification:** All TestDecisionNodeSchema tests pass
- **Committed in:** b5b2ab3 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for test correctness with lazy import pattern. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required. Gemini API key already configured in Settings from Phase 22.

## Next Phase Readiness
- Gemini extraction service fully tested with mocked client -- ready for Plan 24-03 batch processing integration
- Decision and Blocker persistence functions ready for use by batch extraction pipeline
- All 9 exports available: ExtractedDecision, ExtractedBlocker, ExtractionResult, should_skip_for_llm, validate_extraction, compute_content_hash, extract_entities, persist_decision, persist_blocker

## Self-Check: PASSED

All files and commits verified.

---
*Phase: 24-llm-extraction-decision-extraction*
*Completed: 2026-03-07*
