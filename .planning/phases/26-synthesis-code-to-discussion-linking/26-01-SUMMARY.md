---
phase: 26-synthesis-code-to-discussion-linking
plan: 01
subsystem: synthesis
tags: [prompt-engineering, graph-integration, synthesis-template, conditional-instructions]

# Dependency graph
requires:
  - phase: 25-graph-enhanced-retrieval
    provides: Graph section in synthesis prompt with {graph_section} placeholder and _format_graph_section()
provides:
  - Enriched SYNTHESIS_TEMPLATE with conditional graph integration instructions in sections 2, 4, 5, 7
  - Decision trail weaving instructions for Background & Decisions section
  - Relationship path narrative instructions for Related Work section
  - Discussion provenance annotation support for Relevant Code section
  - Cross-source involvement instructions for Key People section
affects: [26-02, synthesis, context-pages]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conditional prompt instructions: 'If the Graph Connections section above contains...' guards against hallucination when graph data is empty"
    - "Section enrichment without structural changes: append instructions to existing numbered sections, never add new sections"

key-files:
  created: []
  modified:
    - backend/src/services/synthesis.py
    - backend/tests/test_synthesis_prompt.py
    - backend/tests/test_synthesis_graph.py

key-decisions:
  - "All graph-referencing instructions are conditional to prevent LLM hallucination when no graph data exists"
  - "Instructions appended to existing section descriptions, maintaining exactly 7 numbered sections"
  - "Decision trail instructions include confidence level and source citation requirements"
  - "Relationship paths described in natural language, explicitly discouraging raw path notation"

patterns-established:
  - "Conditional graph instructions: Always guard graph-referencing prompts with 'If the Graph Connections section...' to maintain graceful degradation"
  - "_extract_section_text() test helper: Splits template by numbered section markers for isolated section testing"

requirements-completed: [SYNTH-01, SYNTH-02, SYNTH-03, SYNTH-04]

# Metrics
duration: 4min
completed: 2026-03-08
---

# Phase 26 Plan 01: Synthesis Prompt Enrichment Summary

**Enriched SYNTHESIS_TEMPLATE sections 2/4/5/7 with conditional graph integration instructions for decision trails, relationship narratives, code provenance, and cross-source people involvement**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-08T00:38:33Z
- **Completed:** 2026-03-08T00:42:33Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- SYNTHESIS_TEMPLATE sections 2, 4, 5, 7 enriched with conditional instructions telling the LLM how to weave graph data into narrative output
- All instructions guard against hallucination with conditional phrasing ("If the Graph Connections section above contains...")
- Template retains exactly 7 numbered sections with no structural changes
- Full TDD cycle: 5 new tests written RED, then turned GREEN with implementation
- SYNTH-04 regression test confirms graceful degradation with empty graph data
- Full backend test suite (526 tests) passes with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add tests for enriched synthesis template instructions** - `77fbe0c` (test) -- TDD RED phase: 5 new tests + 1 regression test
2. **Task 2: Update SYNTHESIS_TEMPLATE with enriched section instructions** - `aa5e50e` (feat) -- TDD GREEN phase: all 19 tests pass

**Plan metadata:** (pending docs commit)

_Note: TDD tasks split across two commits (test RED then feat GREEN)_

## Files Created/Modified
- `backend/src/services/synthesis.py` - Updated SYNTHESIS_TEMPLATE with conditional graph enrichment instructions in sections 2, 4, 5, 7
- `backend/tests/test_synthesis_prompt.py` - Added TestEnrichedSectionInstructions class (6 tests) and _extract_section_text helper
- `backend/tests/test_synthesis_graph.py` - Added test_no_graph_data_graceful_degradation regression test

## Decisions Made
- All graph-referencing instructions use conditional phrasing ("If the Graph Connections section above contains [DECISION] items...", "If graph data shows...") to prevent LLM hallucination when graph_section is empty
- Decision trail instructions require citing confidence level AND source (Slack thread name, meeting title) so engineers can verify
- Relationship path instructions explicitly discourage raw path notation ("rather than listing raw connections")
- Code provenance instruction uses "Discussed in:" annotation pattern for consistency with Plan 02's annotation format
- Cross-source involvement instruction uses example-driven phrasing to guide LLM output format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SYNTHESIS_TEMPLATE is fully enriched for Phase 26 Plan 02 (code-to-discussion linking)
- Section 5 already references "Discussed in:" annotations that Plan 02 will generate
- Graceful degradation verified -- Plan 02 can safely add code provenance without affecting no-graph-data path

---
*Phase: 26-synthesis-code-to-discussion-linking*
*Completed: 2026-03-08*
