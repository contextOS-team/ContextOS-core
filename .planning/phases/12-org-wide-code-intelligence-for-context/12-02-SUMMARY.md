---
phase: 12-org-wide-code-intelligence-for-context
plan: 02
subsystem: api, embedding, synthesis
tags: [code-chunk, embedding, linking, synthesis, semantic-search, cross-repo]

# Dependency graph
requires:
  - phase: 12-org-wide-code-intelligence-for-context
    provides: CodeChunk model, code_chunks table, tree-sitter parsing service
provides:
  - code_chunk as first-class source type in embedding service (SOURCE_TYPE_MAP)
  - code_chunk discovery via hybrid search in linking engine (_lookup_source_summary)
  - Relevant Code section in 7-section synthesis template
  - Code block formatting for code_chunk items in _format_related_content
affects: [12-03, context-generation, embedding-worker]

# Tech tracking
tech-stack:
  added: []
  patterns: [code_chunk embedding with metadata header, code block formatting in synthesis prompt]

key-files:
  created:
    - backend/tests/test_linking_code.py
  modified:
    - backend/src/services/embedding.py
    - backend/src/services/linking.py
    - backend/src/services/synthesis.py

key-decisions:
  - "Metadata header format: '# {symbol_type} {symbol_name} in {file_path}' prepended to code content for embedding context"
  - "Code chunks discovered via semantic search only (no explicit FK links to tickets)"
  - "Relevant Code inserted as section 5 of 7 in synthesis template, between Related Work and Open Questions"
  - "Code_chunk items formatted with code blocks (triple backticks) in _format_related_content for LLM readability"

patterns-established:
  - "Code block formatting for code_chunk source_type in synthesis prompt"
  - "Symbol-type title format: '{symbol_type}: {symbol_name} ({repo}:{path})' in linking summaries"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-03-03
---

# Phase 12 Plan 02: Context Pipeline Integration Summary

**Code chunks wired into embedding, linking, and synthesis pipeline with metadata-header embeddings, hybrid search discovery, and Relevant Code section in context pages**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-03T09:46:13Z
- **Completed:** 2026-03-03T09:49:04Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- code_chunk added to SOURCE_TYPE_MAP in embedding service with metadata header text extraction (symbol_type, symbol_name, file_path + content)
- CodeChunk added to linking engine _lookup_source_summary for hybrid search result rendering
- SYNTHESIS_TEMPLATE expanded from 6 to 7 sections with "Relevant Code" at position 5
- Code_chunk items formatted with code blocks in _format_related_content for LLM readability

## Task Commits

Each task was committed atomically:

1. **Task 1: Add code_chunk to embedding service and linking engine** - `ed587be` (feat, TDD)
2. **Task 2: Update synthesis template to include Relevant Code section** - `608f794` (feat)

_Note: Task 1 was TDD -- RED (failing tests) -> GREEN (implementation passing) phases_

## Files Created/Modified
- `backend/src/services/embedding.py` - Added CodeChunk import and code_chunk entry in SOURCE_TYPE_MAP
- `backend/src/services/linking.py` - Added CodeChunk import and code_chunk entry in _lookup_source_summary model_map
- `backend/src/services/synthesis.py` - Added Relevant Code section to 7-section template, code block formatting for code_chunk items
- `backend/tests/test_linking_code.py` - 3 tests: lookup summary, hybrid matches, merged linking results

## Decisions Made
- Metadata header format `# {symbol_type} {symbol_name} in {file_path}` prepended to code for embedding -- gives embedding model context about what the code represents
- Code chunks discovered via semantic search only -- no explicit FK links to tickets needed (hybrid_search SQL function already searches all source types)
- Relevant Code inserted as section 5 between Related Work and Open Questions -- engineers see code context before open questions
- Code block triple-backtick formatting for code_chunk items in _format_related_content so LLM can read actual code

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Embedding service ready to generate embeddings for code_chunks once code_indexer triggers queue_embedding_generation
- Linking engine will automatically include code_chunks in context generation via hybrid search
- Synthesis template instructs LLM to produce Relevant Code sections in context pages
- Plan 12-03 can wire code_indexer into API endpoints and Redis Streams worker

## Self-Check: PASSED

All files verified on disk. Both task commits (ed587be, 608f794) verified in git log.

---
*Phase: 12-org-wide-code-intelligence-for-context*
*Completed: 2026-03-03*
