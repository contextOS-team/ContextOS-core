# Phase 31: GitLab & GitHub Sync Performance Optimization - Research

**Researched:** 2026-03-15
**Domain:** Python asyncio concurrency, API rate limiting, incremental sync patterns
**Confidence:** HIGH

## Summary

The current GitLab and GitHub sync services process repositories sequentially and fetch notes/reviews one-by-one per MR/PR within each repo. This creates an O(repos * MRs * API_calls) serial bottleneck -- for a workspace with 5 repos and 100 MRs each, this means ~500 sequential API calls for reviews alone, plus another ~500 for notes. The code indexing pipeline (`index_workspace_repos` and `index_gitlab_workspace_repos`) also processes repos sequentially.

The fix is straightforward: the codebase already uses `asyncio`, `httpx.AsyncClient`, and has a semaphore pattern (`_github_semaphore = asyncio.Semaphore(10)`) in `github_common.py`. The primary changes are: (1) batch note/review fetching with `asyncio.gather` + semaphore, (2) persist `updated_after` cursor per project in the existing `sync_cursors` table (which already has `cursor_value` field), (3) wrap repo processing in `asyncio.gather` with configurable concurrency, (4) add `asyncio.timeout` per project with partial-commit on timeout, (5) add state filter parameter to avoid fetching all MRs when only open ones are needed, and (6) emit progress events via the existing `_update_project_sync_status` / `_update_repo_sync_status` pattern.

**Primary recommendation:** Refactor `sync_single_project` / `sync_single_repo` to batch-fetch notes/reviews concurrently, persist incremental cursors, and wrap the outer repo loop in bounded `asyncio.gather`. No new libraries needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERF-SYNC-01 | MR/PR sync fetches notes/reviews concurrently (asyncio.gather with concurrency limit) instead of one-by-one | Semaphore + asyncio.gather pattern applied to `_fetch_notes` / `_fetch_reviews` calls within `sync_single_project` / `sync_single_repo` |
| PERF-SYNC-02 | Incremental sync uses `updated_after` cursor persisted per-project so re-syncs only fetch changed MRs | `sync_cursors.cursor_value` field already exists; store ISO timestamp of last successful sync's max `updated_at` |
| PERF-SYNC-03 | Code indexing clones and parses multiple repositories concurrently (configurable parallelism) | `asyncio.Semaphore(N)` + `asyncio.gather` in `index_workspace_repos` / `index_gitlab_workspace_repos` |
| PERF-SYNC-04 | Sync operations have per-project timeouts with graceful partial-commit | `asyncio.timeout(seconds)` context manager (Python 3.11+) around each project sync; commit completed projects even if one times out |
| PERF-SYNC-05 | Open vs closed MR fetch uses state filter to avoid fetching all MRs when only open ones are needed | Add `state` parameter to `sync_projects` / `sync_repos`; pass `?state=opened` or `?state=open` to GitLab/GitHub API |
| PERF-SYNC-06 | Progress events emitted during sync for frontend status visibility | Extend existing `_update_project_sync_status` / `_update_repo_sync_status` with per-MR progress counts |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib | Concurrency primitives (gather, Semaphore, timeout) | Already used throughout codebase |
| httpx | existing | Async HTTP client for API calls | Already the project's HTTP client |
| sqlalchemy | existing | Async DB operations | Already the project's ORM |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.Semaphore | stdlib | Bound concurrent API calls | Wrap all concurrent API fetches |
| asyncio.timeout | stdlib (3.11+) | Per-project timeout | Wrap each project sync call |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.gather | asyncio.TaskGroup (3.11+) | TaskGroup cancels all on first error; gather with return_exceptions=True is better for partial-success pattern |
| Manual semaphore | aiometer/asyncio-throttle | Extra dependency for minimal benefit; semaphore pattern already established in codebase |

**Installation:**
No new packages needed. All primitives are stdlib or already installed.

## Architecture Patterns

### Current Architecture (Sequential)
```
sync_projects(project_ids):
    for project_id in project_ids:          # Sequential
        sync_single_project(project_id):
            for mr in fetch_mrs():          # Sequential pages
                _fetch_notes(mr.iid)        # Sequential per-MR API call  <-- BOTTLENECK
                _upsert_review(...)
```

### Target Architecture (Concurrent with Incremental)
```
sync_projects(project_ids, state_filter):
    semaphore = Semaphore(MAX_CONCURRENT_PROJECTS)   # e.g., 3

    async def _sync_one(project_id):
        async with semaphore:
            async with asyncio.timeout(PROJECT_TIMEOUT):
                cursor = get_cursor(project_id)       # Incremental
                updated_after = cursor.value or 60_day_cutoff

                for mr_page in fetch_mrs(state=state_filter, updated_after=updated_after):
                    # Batch fetch notes for all MRs in page concurrently
                    note_tasks = [_fetch_notes(mr.iid) for mr in mr_page]
                    all_notes = await asyncio.gather(*note_tasks, return_exceptions=True)

                    for mr, notes in zip(mr_page, all_notes):
                        upsert_mr(mr)
                        if not isinstance(notes, Exception):
                            for note in notes: upsert_review(note)

                    emit_progress(project_id, count)

                save_cursor(project_id, max_updated_at)

    results = await asyncio.gather(
        *[_sync_one(pid) for pid in project_ids],
        return_exceptions=True
    )
    # Partial commit: completed projects saved even if one fails/times out
```

### Pattern 1: Bounded Concurrent Note/Review Fetching
**What:** Use `asyncio.gather` with a semaphore to fetch notes/reviews for multiple MRs in a single page concurrently
**When to use:** Inside `sync_single_project` / `sync_single_repo` after fetching a page of MRs
**Example:**
```python
# Concurrency limit for note/review API calls within a sync
_NOTE_FETCH_SEMAPHORE = asyncio.Semaphore(5)  # 5 concurrent note fetches

async def _fetch_notes_bounded(client, token, project_id, mr_iid):
    async with _NOTE_FETCH_SEMAPHORE:
        return await _fetch_notes(client, token, project_id, mr_iid)

# In sync_single_project, after fetching a page of MRs:
note_tasks = [
    _fetch_notes_bounded(client, token, project_id, mr["iid"])
    for mr in mrs_page
    if not is_bot_user(mr.get("author", {}))
]
all_notes = await asyncio.gather(*note_tasks, return_exceptions=True)
```

### Pattern 2: Incremental Cursor Persistence
**What:** Store the max `updated_at` timestamp from the last successful sync as `cursor_value` in the existing `sync_cursors` table
**When to use:** At the start of `sync_single_project` / `sync_single_repo` to determine `updated_after` parameter
**Example:**
```python
# Read cursor at start
cursor = await get_or_create_cursor(session, workspace_id, "gitlab", str(project_id))
if cursor.cursor_value:
    updated_after = cursor.cursor_value  # ISO timestamp from last sync
else:
    updated_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")  # 60-day fallback

# After successful sync, save max updated_at
await update_cursor_status(
    session, workspace_id, "gitlab", str(project_id),
    sync_status="complete",
    records_synced=mr_count,
    cursor_value=max_updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
)
```

### Pattern 3: Per-Project Timeout with Graceful Partial Commit
**What:** Wrap each project sync in `asyncio.timeout()` and commit completed work before moving on
**When to use:** In the outer loop of `sync_projects` / `sync_repos`
**Example:**
```python
PROJECT_SYNC_TIMEOUT = 300  # 5 minutes per project

try:
    async with asyncio.timeout(PROJECT_SYNC_TIMEOUT):
        mr_count, review_count = await sync_single_project(...)
except TimeoutError:
    srl.warning("Project %d timed out after %ds", project_id, PROJECT_SYNC_TIMEOUT)
    results[str(project_id)] = {"status": "timeout", "partial": True}
    # Session already has partial data from flush() calls within sync_single_project
    await session.commit()  # Save what we got
```

### Pattern 4: Concurrent Repo Indexing
**What:** Clone and parse multiple repos concurrently using `asyncio.gather` with bounded concurrency
**When to use:** In `index_workspace_repos` / `index_gitlab_workspace_repos`
**Example:**
```python
MAX_CONCURRENT_CLONES = 3  # Configurable

clone_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CLONES)

async def _index_one(repo):
    async with clone_semaphore:
        return await index_repo(workspace_id, repo["full_name"], session, settings)

results = await asyncio.gather(
    *[_index_one(repo) for repo in monitored_repos],
    return_exceptions=True
)
```

### Anti-Patterns to Avoid
- **Unbounded asyncio.gather:** Never launch unlimited concurrent API calls. Always use a semaphore. GitLab rate limit is 10 req/sec for OAuth tokens; GitHub is 5000/hour but bursty.
- **Shared mutable session in concurrent tasks:** Each concurrent task that does DB writes needs careful session handling. Use `session.flush()` within tasks but commit only at the outer level, OR use separate sessions per concurrent task.
- **Ignoring return_exceptions:** Without `return_exceptions=True` in `asyncio.gather`, one failed note fetch cancels all others. Always use `return_exceptions=True` and handle Exception results.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Custom rate limiter | `asyncio.Semaphore` + existing `check_rate_limit` | Semaphore handles concurrency; `check_rate_limit` handles API-reported limits |
| Sync cursor storage | New table or file-based state | `sync_cursors.cursor_value` (already exists) | Table and helpers already exist with proper workspace scoping |
| Progress tracking | WebSocket or SSE endpoint | Existing JSONB config pattern (`_update_project_sync_status`) | Frontend already polls this for sync status |
| Timeout management | Manual timer + cancellation | `asyncio.timeout()` (stdlib 3.11+) | Clean context manager, auto-raises TimeoutError |

**Key insight:** The entire infrastructure for incremental cursors, status tracking, and concurrency primitives already exists in the codebase. This phase is purely about wiring existing patterns into the sync loops.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Session Sharing in Concurrent Tasks
**What goes wrong:** Multiple `asyncio.gather` tasks writing to the same `AsyncSession` causes "session is already flushing" errors or data corruption.
**Why it happens:** SQLAlchemy sessions are not thread-safe and not designed for concurrent access from multiple coroutines.
**How to avoid:** Two options: (a) Do all DB writes sequentially after gathering API results, or (b) use a separate session per concurrent task. Option (a) is simpler and recommended here since the bottleneck is API calls, not DB writes.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError` during concurrent operations.

### Pitfall 2: GitLab Rate Limiting (10 req/sec per token)
**What goes wrong:** Bursting 100 concurrent note fetches triggers 429 responses and temporary token ban.
**Why it happens:** GitLab enforces stricter rate limits than GitHub (10 req/sec vs 5000/hour).
**How to avoid:** Keep semaphore value at 5 for GitLab (lower than GitHub's 10). Add exponential backoff on 429 responses.
**Warning signs:** HTTP 429 responses in logs, `Retry-After` headers.

### Pitfall 3: Incremental Cursor Edge Case -- MRs Updated During Sync
**What goes wrong:** An MR updated during sync window gets a newer `updated_at` than the saved cursor, but its notes were fetched with old data.
**Why it happens:** The cursor is saved after sync completes, but MRs can be updated concurrently.
**How to avoid:** Save cursor_value as `sync_start_time` (timestamp when sync began) rather than max `updated_at` from fetched data. This ensures overlapping updates are re-fetched on next sync.
**Warning signs:** Missing notes on recently-updated MRs after incremental sync.

### Pitfall 4: Partial Commit Session State
**What goes wrong:** After a timeout, calling `session.commit()` commits unflushed dirty state from the timed-out coroutine.
**Why it happens:** `asyncio.timeout` raises `TimeoutError` which may leave the session in an inconsistent state.
**How to avoid:** Use separate DB sessions for each project sync (via `async_session()` context manager). This is already the pattern in the router layer (`_run_sync` creates its own `bg_session`).
**Warning signs:** Partial MR data without corresponding reviews in the database.

### Pitfall 5: GitHub API -- No `updated_after` Equivalent
**What goes wrong:** Attempting to use `updated_after` parameter for GitHub PRs API that doesn't exist.
**Why it happens:** GitHub's List PRs endpoint doesn't have an `updated_after` filter (GitLab does). GitHub sorts by `updated` but returns ALL PRs.
**How to avoid:** For GitHub, the incremental cursor works differently: fetch pages sorted by `updated desc` and stop when hitting a PR with `updated_at < cursor_value`. This is already the pattern (the `reached_cutoff` check), just change the cutoff to use the persisted cursor instead of the hardcoded 60-day window.
**Warning signs:** GitHub incremental sync still fetching the same number of PRs as full sync.

## Code Examples

### Concurrent Note Fetching (GitLab)
```python
# In sync_single_project, replace the sequential per-MR note fetch:

# BEFORE (sequential):
for mr_data in mrs:
    notes = await _fetch_notes(client, token, project_id, mr_data["iid"])

# AFTER (concurrent, bounded):
_note_semaphore = asyncio.Semaphore(5)

async def _fetch_notes_bounded(client, token, project_id, mr_iid):
    async with _note_semaphore:
        return mr_iid, await _fetch_notes(client, token, project_id, mr_iid)

# Collect non-bot MRs first
valid_mrs = [mr for mr in mrs if not is_bot_user(mr.get("author", {}))]

# Fetch all notes concurrently
note_results = await asyncio.gather(
    *[_fetch_notes_bounded(client, token, project_id, mr["iid"]) for mr in valid_mrs],
    return_exceptions=True,
)

# Process results sequentially (DB writes)
for mr_data, result in zip(valid_mrs, note_results):
    mr_record = await _upsert_mr(session, workspace_id, project_id, mr_data)
    if isinstance(result, Exception):
        logger.warning("Failed to fetch notes for MR !%d: %s", mr_data["iid"], result)
        continue
    _iid, notes = result
    for note in notes:
        await _upsert_review(session, workspace_id, mr_record.id, note)
```

### Incremental Cursor Read/Write
```python
# At start of sync_single_project:
cursor = await get_or_create_cursor(session, workspace_id, "gitlab", str(project_id))
sync_start = datetime.now(timezone.utc).replace(tzinfo=None)

if cursor.cursor_value:
    updated_after = cursor.cursor_value
else:
    cutoff = sync_start - timedelta(days=BACKFILL_DAYS)
    updated_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

# After successful sync:
await update_cursor_status(
    session, workspace_id, "gitlab", str(project_id),
    sync_status="complete",
    records_synced=mr_count,
    cursor_value=sync_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
)
```

### State Filter for Open-Only Sync
```python
# Add state parameter to sync functions:
async def sync_projects(
    workspace_id: UUID,
    project_ids: list[int],
    session: AsyncSession,
    settings: Settings,
    state_filter: str = "all",  # "all", "opened", "merged", "closed"
) -> dict:
    ...

# In sync_single_project, apply to URL:
state_param = state_filter if state_filter != "all" else "all"
url = (
    f"{GITLAB_API_BASE}/projects/{project_id}/merge_requests"
    f"?state={state_param}&order_by=updated_at&sort=desc&per_page=100"
    f"&updated_after={updated_after}"
)

# GitHub equivalent: state=open (not "opened")
github_state = "open" if state_filter == "opened" else state_filter
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential per-MR note fetch | Batch concurrent fetch with semaphore | This phase | 5-10x sync time reduction |
| 60-day hardcoded backfill | Incremental cursor from sync_cursors | This phase | Re-syncs fetch only changed MRs |
| Sequential repo cloning | Concurrent cloning with configurable parallelism | This phase | 2-3x indexing speedup |
| No per-project timeout | asyncio.timeout per project | This phase | Prevents one slow repo from blocking entire sync |

## Open Questions

1. **Concurrency limits for GitLab vs GitHub**
   - What we know: GitHub has 5000 req/hour with burst tolerance; GitLab has 10 req/sec per OAuth token
   - What's unclear: Optimal semaphore values for production load
   - Recommendation: Start with 5 for GitLab, 10 for GitHub (matches existing `_github_semaphore`), make configurable via env var

2. **Session isolation for concurrent repo indexing**
   - What we know: `index_workspace_repos` currently does `session.commit()` per repo; concurrent tasks sharing a session is unsafe
   - What's unclear: Whether to use one session per task or serialize DB writes
   - Recommendation: Use separate `async_session()` per concurrent task, matching the code_index_worker pattern

3. **Progress event granularity**
   - What we know: Frontend polls JSONB config for sync status; existing pattern uses `_update_project_sync_status`
   - What's unclear: Whether to emit per-MR progress or per-page progress
   - Recommendation: Per-page progress (after each page of 100 MRs) to avoid excessive DB writes

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `backend/src/services/gitlab_sync.py` -- current sequential sync implementation
- Codebase analysis: `backend/src/services/github_sync.py` -- current sequential sync with semaphore pattern
- Codebase analysis: `backend/src/services/code_indexer.py` -- current sequential repo indexing
- Codebase analysis: `backend/src/services/sync_adapter.py` -- existing SyncCursor with `cursor_value` field
- Codebase analysis: `backend/src/services/github_common.py` -- existing `_github_semaphore = asyncio.Semaphore(10)`
- Python stdlib: `asyncio.gather`, `asyncio.Semaphore`, `asyncio.timeout` (3.11+)

### Secondary (MEDIUM confidence)
- GitLab API rate limits: 10 requests per second per OAuth token (standard tier)
- GitHub API rate limits: 5000 requests per hour for installation tokens

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all stdlib/existing libraries, no new dependencies
- Architecture: HIGH - patterns already established in codebase (semaphore, cursors, gather)
- Pitfalls: HIGH - well-understood async patterns with clear failure modes

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable patterns, no moving targets)
