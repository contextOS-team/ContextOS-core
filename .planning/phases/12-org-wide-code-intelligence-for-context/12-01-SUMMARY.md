---
phase: 12-org-wide-code-intelligence-for-context
plan: 01
subsystem: database, api
tags: [tree-sitter, code-parsing, code-indexing, pgvector, github-app]

# Dependency graph
requires:
  - phase: 07-github-integration
    provides: GitHub App installation tokens, repo selection model
provides:
  - code_chunks DB table with indexes, RLS, moddatetime trigger
  - CodeChunk SQLModel mapping to code_chunks table
  - Tree-sitter parsing service (Python, TypeScript, JavaScript, Go + generic fallback)
  - Repo clone and index orchestrator with content-hash deduplication
affects: [12-02, 12-03, context-generation, embedding-service]

# Tech tracking
tech-stack:
  added: [tree-sitter-language-pack]
  patterns: [tree-sitter AST extraction, ephemeral clone with cleanup, content-hash dedup for code chunks]

key-files:
  created:
    - supabase/migrations/00010_code_chunks.sql
    - backend/src/models/code_chunk.py
    - backend/src/services/code_parser.py
    - backend/src/services/code_indexer.py
    - backend/tests/test_models_code_chunk.py
    - backend/tests/test_code_parser.py
  modified:
    - backend/pyproject.toml

key-decisions:
  - "tree-sitter-language-pack for 165+ language support with zero GPL deps (single wheel)"
  - "Dedicated code_chunks table (not reusing embeddings) for typed columns and proper indexing"
  - "Ephemeral clone strategy: clone to tmpdir, parse, delete (no persistent storage)"
  - "Sequential repo indexing per Phase 7 decision to avoid rate limit exhaustion"
  - "Content-hash dedup using same SHA-256 normalization pattern as embedding service"
  - "Type alias declarations allowed as single-line chunks (exception to 2-line minimum)"

patterns-established:
  - "CodeChunkData dataclass as intermediate parse result before DB upsert"
  - "Language-family parser dispatch (_parse_python, _parse_typescript, _parse_go, _parse_generic)"
  - "_should_skip_path() for directory/file filtering during repo walking"

requirements-completed: []

# Metrics
duration: 7min
completed: 2026-03-03
---

# Phase 12 Plan 01: Code Indexing Foundation Summary

**Tree-sitter code parsing service with Python/TS/JS/Go extraction, code_chunks DB table, and repo clone+index orchestrator with content-hash deduplication**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-03T09:35:26Z
- **Completed:** 2026-03-03T09:42:59Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- code_chunks table with unique dedup index, workspace FK, RLS, moddatetime trigger
- Tree-sitter parsing extracts functions, classes, methods, types, interfaces from Python, TypeScript, JavaScript, Go with docstring/decorator metadata
- Repo indexing orchestrator: shallow clone via GitHub App token, walk source files, parse with tree-sitter, upsert chunks with content-hash dedup, soft-delete removed symbols, always cleanup temp directory

## Task Commits

Each task was committed atomically:

1. **Task 1: DB migration + CodeChunk model** - `9ca62c7` (feat)
2. **Task 2: Tree-sitter parsing service + repo clone/index orchestrator** - `20add52` (feat)

_Note: TDD tasks -- each has RED (failing tests) -> GREEN (implementation) phases_

## Files Created/Modified
- `supabase/migrations/00010_code_chunks.sql` - code_chunks table with indexes, RLS, trigger
- `backend/src/models/code_chunk.py` - CodeChunk SQLModel mapping with unique constraint
- `backend/src/services/code_parser.py` - Tree-sitter parsing with language-family dispatch
- `backend/src/services/code_indexer.py` - Repo clone + index orchestration with dedup
- `backend/tests/test_models_code_chunk.py` - 4 model tests (instantiation, metadata, constraint, tablename)
- `backend/tests/test_code_parser.py` - 23 parser tests (detect_language, Python, TypeScript, edge cases)
- `backend/pyproject.toml` - Added tree-sitter-language-pack dependency

## Decisions Made
- Used tree-sitter-language-pack (single wheel, 165+ languages, zero GPL deps) instead of individual language packages
- Created dedicated code_chunks table with typed columns rather than reusing embeddings table -- better indexing, clearer schema
- Ephemeral clone strategy (clone, parse, delete) rather than persistent local storage -- simpler, avoids disk management
- Sequential repo indexing per Phase 7 decision to avoid GitHub API rate limit exhaustion
- Same SHA-256 content hash normalization as embedding service for consistency
- Type alias declarations exempt from 2-line minimum (single-line `type Foo = ...` is meaningful)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- code_chunks table ready for embedding integration (Plan 12-02)
- Tree-sitter parsing service tested and ready for production use
- code_indexer.py ready to be wired into Redis Streams worker or API endpoints (Plan 12-03)
- 27 tests passing provide regression safety for future changes

## Self-Check: PASSED

All 6 created files verified on disk. Both task commits (9ca62c7, 20add52) verified in git log.

---
*Phase: 12-org-wide-code-intelligence-for-context*
*Completed: 2026-03-03*
