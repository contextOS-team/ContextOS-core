---
phase: 26-synthesis-code-to-discussion-linking
plan: 02
subsystem: graph-extraction
tags: [graph-edges, code-chunks, provenance, synthesis, fail-silent]

# Dependency graph
requires:
  - phase: 26-synthesis-code-to-discussion-linking
    provides: Enriched SYNTHESIS_TEMPLATE with "Discussed in:" annotation instructions in section 5
  - phase: 22-graph-tables-and-extraction
    provides: graph_ops.upsert_node/upsert_edge, ExtractedEntity, extract_and_populate_graph orchestrator
  - phase: 25-graph-enhanced-retrieval
    provides: Graph-enhanced linking with graph signals, _format_graph_section, code_chunk LinkedItems
provides:
  - link_code_mentions_to_chunks() for matching FilePathExtractor CodeChunk entities to actual code_chunks records
  - link_pr_code_to_discussions() for transitive discussed_in edges from PR CodeChunks to ticket discussions
  - _get_code_provenance() for batch graph query of code-to-discussion connections
  - _format_related_content() code_provenance parameter for "Discussed in:" annotations
affects: [synthesis, context-pages, graph-extraction]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Chunk node external_id convention: 'chunk:{uuid}' distinguishes actual code_chunks from FilePathExtractor's dangling 'path:{filepath}' reference nodes"
    - "False positive guard: require at least one '/' in file path before attempting code_chunks table match"
    - "Transitive edge pattern: follow PR -> ticket FK -> ticket graph node -> discussion neighbors to create explicit discussed_in edges at ingestion time"
    - "Provenance annotation pattern: batch query graph edges, build source_id -> annotation strings dict, pass to formatter"

key-files:
  created:
    - backend/tests/test_code_discussion.py
  modified:
    - backend/src/services/graph_extractor.py
    - backend/src/services/synthesis.py

key-decisions:
  - "CodeChunk graph nodes for actual code_chunks use external_id='chunk:{uuid}' to distinguish from FilePathExtractor dangling reference nodes using 'path:{filepath}'"
  - "File path matching requires at least one '/' to avoid false positives from bare filenames like config.py"
  - "Transitive discussed_in edges created at ingestion time (not query time) so graph traversal works within depth-2 limit"
  - "_get_code_provenance() queries edges where chunk nodes are TARGET (source -mentions-> chunk) for correct provenance direction"
  - "Code provenance annotation format: 'Discussed in: #channel-name; Meeting: title' with semicolon-joined discussions"

patterns-established:
  - "Code mention linking source types: slack_message, linear_comment, meeting_transcript, meeting_segment -- where file paths in content may reference actual code"
  - "PR transitive linking: PR source_type triggers link_pr_code_to_discussions() in extract_and_populate_graph()"
  - "Provenance batch query: compute fingerprints for all code_chunk items, single query for nodes, single query for edges, single query for discussion nodes"

requirements-completed: [CODE-01, CODE-02, CODE-03]

# Metrics
duration: 16min
completed: 2026-03-08
---

# Phase 26 Plan 02: Code-to-Discussion Linking Summary

**Graph edges linking Slack-mentioned file paths and PR-changed code to code_chunks records, with "Discussed in:" provenance annotations in context page code blocks**

## Performance

- **Duration:** 16 min
- **Started:** 2026-03-08T00:46:54Z
- **Completed:** 2026-03-08T01:03:01Z
- **Tasks:** 2 (TDD: 4 commits total -- 2 RED, 2 GREEN)
- **Files modified:** 3

## Accomplishments
- link_code_mentions_to_chunks() creates 'mentions' edges from source nodes (Slack, meetings, comments) to CodeChunk graph nodes backed by actual code_chunks records, with suffix file path matching and false positive guard
- link_pr_code_to_discussions() creates transitive 'discussed_in' edges from PR's CodeChunk neighbors to ticket's discussion neighbors (SlackThread/Meeting)
- _get_code_provenance() batch-queries graph edges to find discussions connected to code_chunks and builds annotation strings
- _format_related_content() annotates code_chunk items with "Discussed in: #channel; Meeting: title" when graph provenance exists
- generate_context_page() wires provenance query into the formatting pipeline
- Full TDD cycle: 14 tests written RED then turned GREEN with implementation
- Full backend test suite (540 tests) passes with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Code-to-discussion edge creation (CODE-01 + CODE-02)** - TDD
   - `4a5bfac` (test) -- RED: 6 failing tests for link_code_mentions_to_chunks and link_pr_code_to_discussions
   - `ed5b90c` (feat) -- GREEN: implement both functions, wire into extract_and_populate_graph()

2. **Task 2: Code provenance annotations in synthesis (CODE-03)** - TDD
   - `6cbd678` (test) -- RED: 8 failing tests for _format_related_content provenance, _get_code_provenance, generate_context_page wiring
   - `f649ebf` (feat) -- GREEN: implement _get_code_provenance(), update _format_related_content(), wire into generate_context_page()

**Plan metadata:** (pending docs commit)

_Note: TDD tasks split across two commits each (test RED then feat GREEN)_

## Files Created/Modified
- `backend/tests/test_code_discussion.py` - 14 tests covering CODE-01 (file path matching, false positive guard, multiple chunks, fail-silent), CODE-02 (transitive edges, no-ticket skip), CODE-03 (provenance format, batch query, fail-silent, generate wiring)
- `backend/src/services/graph_extractor.py` - Added link_code_mentions_to_chunks() and link_pr_code_to_discussions() functions, wired into extract_and_populate_graph() for appropriate source types
- `backend/src/services/synthesis.py` - Added _get_code_provenance() async helper, updated _format_related_content() with code_provenance parameter, wired into generate_context_page()

## Decisions Made
- CodeChunk graph nodes for actual code_chunks records use external_id=f"chunk:{uuid}" to distinguish from FilePathExtractor's dangling reference nodes which use external_id=f"path:{filepath}"
- File path matching requires at least one '/' directory separator to avoid false positives from bare filenames (e.g., "config.py" matches dozens of files across repos)
- Transitive discussed_in edges are created at ingestion time rather than query time, so graph traversal at synthesis time works within the depth-2 limit
- _get_code_provenance() queries edges where chunk nodes are the TARGET (source -mentions-> chunk), since that's how link_code_mentions_to_chunks creates them
- Provenance annotations use format "Discussed in: #channel-name; Meeting: title" with semicolon-joined discussions
- Discussion entity types limited to SlackThread and Meeting (not Ticket or PR, which are engineering artifacts rather than discussions)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Initial test approach used sys.modules pre-population pattern (from Phase 24-02) which caused import chain issues when CODE-03 tests needed to import synthesis.py. Simplified to direct imports since all model modules can be imported without issues in the current environment. The sys.modules pattern was unnecessary here since graph_extractor.py uses lazy imports that work with the real modules.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 7 phase 26 requirements complete (SYNTH-01/02/03/04 from Plan 01, CODE-01/02/03 from Plan 02)
- The full code-to-discussion provenance chain is operational: Slack mentions file path -> graph edge to CodeChunk -> context page shows "Discussed in:" annotation
- Graph-enhanced synthesis is fully functional with decision trails, relationship narratives, cross-referenced people, and code provenance

## Self-Check: PASSED

All files, commits, and functions verified to exist.

---
*Phase: 26-synthesis-code-to-discussion-linking*
*Completed: 2026-03-08*
