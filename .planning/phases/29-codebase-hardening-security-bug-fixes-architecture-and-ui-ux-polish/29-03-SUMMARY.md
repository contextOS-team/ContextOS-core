---
phase: 29-codebase-hardening-security-bug-fixes-architecture-and-ui-ux-polish
plan: 03
subsystem: backend
tags: [fastapi, background-tasks, migrations, datetime-utils, code-hygiene]

# Dependency graph
requires: []
provides:
  - "Telegram webhook background processing (non-blocking)"
  - "Unique migration numbering (00019b for Jira tables)"
  - "Shared parse_notion_datetime utility in backend/src/utils/datetime.py"
  - "Module-level imports in synthesis.py and jira.py"
affects: [29-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared utils module for cross-cutting helpers (backend/src/utils/)"
    - "00004b-style migration numbering for late insertions"

key-files:
  created:
    - backend/src/utils/datetime.py
  modified:
    - backend/src/routers/telegram.py
    - backend/src/routers/notion.py
    - backend/src/routers/jira.py
    - backend/src/services/notion_sync.py
    - backend/src/services/sync_scheduler.py
    - backend/src/services/synthesis.py
    - supabase/migrations/00019b_jira_tables.sql

key-decisions:
  - "Renamed jira migration to 00019b (not 00020) because 00020 is occupied by telegram_messages"
  - "Kept backward-compatible _parse_notion_datetime alias in notion.py router"

patterns-established:
  - "Shared datetime utilities in backend/src/utils/datetime.py"
  - "Letter-suffixed migration numbers (00019b) for resolving collisions"

requirements-completed: [BUG-02, BUG-04, ARCH-01, ARCH-03]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 29 Plan 03: Quick Bug Fixes and Architecture Cleanup Summary

**Telegram background processing restored, duplicate migration renumbered, datetime utility extracted to shared module, deferred imports moved to module level**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T20:02:43Z
- **Completed:** 2026-03-11T20:05:41Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Restored non-blocking Telegram webhook processing via background_tasks.add_task()
- Resolved duplicate 00019 migration numbering (gitlab + jira) by renaming jira to 00019b
- Extracted _parse_notion_datetime to shared backend/src/utils/datetime.py module
- Updated 3 importers (notion.py, notion_sync.py, sync_scheduler.py) to use new utils location
- Moved deferred import json to module level in synthesis.py and jira.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Restore Telegram background processing and renumber duplicate migration** - `766d5c1` (fix)
2. **Task 2: Extract shared datetime utility and fix deferred imports** - `beccee2` (refactor)

## Files Created/Modified
- `backend/src/utils/datetime.py` - New shared datetime parsing utility with parse_notion_datetime
- `backend/src/routers/telegram.py` - Restored background_tasks.add_task() for webhook processing
- `backend/src/routers/notion.py` - Replaced local _parse_notion_datetime with import from utils
- `backend/src/routers/jira.py` - Moved import json to module level
- `backend/src/services/notion_sync.py` - Updated import to use src.utils.datetime
- `backend/src/services/sync_scheduler.py` - Updated import to use src.utils.datetime
- `backend/src/services/synthesis.py` - Moved import json to module level
- `supabase/migrations/00019b_jira_tables.sql` - Renamed from 00019_jira_tables.sql

## Decisions Made
- Renamed jira migration to 00019b instead of 00020 (plan target) because 00020_telegram_messages.sql already exists. Follows existing 00004b precedent in the migration directory.
- Kept backward-compatible _parse_notion_datetime alias in notion.py router to avoid breaking any potential external references.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migration target 00020 already occupied**
- **Found during:** Task 1 (migration renumber)
- **Issue:** Plan specified renaming to 00020_jira_tables.sql, but 00020_telegram_messages.sql already exists
- **Fix:** Used 00019b suffix following existing 00004b_vault_lazy_migration.sql pattern
- **Files modified:** supabase/migrations/00019b_jira_tables.sql
- **Verification:** ls confirms single 00019 file (gitlab), 00019b (jira), 00020 (telegram)
- **Committed in:** 766d5c1 (Task 1 commit)

**2. [Rule 1 - Bug] Python version compatibility for type unions**
- **Found during:** Task 2 (datetime utility creation)
- **Issue:** `str | None` syntax requires Python 3.10+ but project uses older Python at module level
- **Fix:** Added `from __future__ import annotations` to datetime.py
- **Verification:** python3 -c import succeeds
- **Committed in:** beccee2 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 4 concerns (BUG-02, BUG-04, ARCH-01, ARCH-03) resolved
- Plan 04 (synthesis refactoring) can proceed without conflicts
- Shared utils module established for future shared helpers

---
*Phase: 29-codebase-hardening-security-bug-fixes-architecture-and-ui-ux-polish*
*Completed: 2026-03-12*
