# Phase 32: Activity Events Emission - Research

**Researched:** 2026-03-16
**Domain:** Backend event emission into existing activity_events table + minor frontend formatter updates
**Confidence:** HIGH

## Summary

This phase is a pure wiring exercise: the `activity_events` table, RLS policies, Realtime publication, and the frontend `ActivityTimeline` component with all 6 event type formatters already exist from Phase 18. No schema changes are needed. The work is to add `INSERT INTO activity_events` calls at the right points in 7 sync services, OAuth callback handlers, disconnect handlers, and the synthesis service.

The codebase follows a consistent pattern across all providers: each sync service has a `SyncRunLogger` context manager that wraps the sync operation, `update_cursor_status()` calls at sync boundaries, and a summary dict return value containing item counts. The `emit_activity()` helper should be placed alongside these existing cursor status updates for natural injection. OAuth callbacks all follow the same pattern (verify state, exchange code, redirect) and disconnect handlers are one-liners calling provider-specific `disconnect()` functions.

**Primary recommendation:** Create a single `emit_activity()` async helper in `sync_adapter.py` that does a direct Supabase INSERT (using the existing async session), wrapped in try/except to ensure fail-silent behavior. Wire it into each provider's sync flow, OAuth callbacks, disconnect handlers, and the synthesis service.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Centralized `emit_activity()` helper in `sync_adapter.py` -- single place to maintain, all 7 providers call it
- Emit both `sync_started` AND `sync_completed` for every full sync -- gives real-time liveness feel
- Context generation: emit only `context_generated` on completion (no start event, no schema change needed)
- Integration connect/disconnect: wire emission into OAuth callback endpoints and settings disconnect handlers
- `sync_completed` includes: `items_count`, `duration_ms`, plus provider-specific details
- `sync_started` includes: `integration` name (required by frontend formatter)
- `context_generated` includes: `source_count`, `token_count`, `ticket_title` and/or `ticket_id` for richer display
- Frontend formatter updated: "Context generated for CON-42 . 5 sources" instead of generic message
- Failed syncs emit `sync_completed` with `metadata.error: true` and `metadata.error_message` -- no new event type
- Failed events shown with red accent icon and "failed" chip in timeline
- Failed context generation emits `context_generated` with error metadata
- Event emission is fail-silent with logging -- never breaks the actual sync or context generation
- One event per `full_sync()` call -- not per-resource, not per-item
- Webhook-triggered syncs do NOT emit activity events (too noisy)
- Telegram treated identically to other providers
- `items_count` metadata conveys sync volume

### Claude's Discretion
- Exact placement of emit calls within OAuth callback handlers
- Provider-specific metadata fields beyond items_count and duration_ms
- Visual treatment details for error states (icon choice, color shade)
- Whether to add helper method to SyncAdapter protocol or keep as standalone function

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACT-05 | All integration sync services (Linear, Slack, GitHub, GitLab, Jira, Notion, Telegram) emit events to activity_events on sync completion | Mapped all 7 providers: 5 have `full_sync()` (Linear, GitHub, GitLab, Jira, Notion), Slack is webhook/event-only (huddle poll is closest sync), Telegram is webhook-only. Each has clear injection points at sync boundaries. |
| ACT-06 | Integration connect/disconnect actions emit activity events | Found all 7 OAuth callback handlers and 8 disconnect handlers (including Fathom). Each follows identical patterns -- callbacks redirect after `exchange_code()`, disconnects call provider `disconnect()` then return. |
| ACT-07 | Context page generation (start, complete, error) emits activity events | `generate_context_page()` in `synthesis.py` has clear success path (line 673: status="ready") and error path (line 696: status="error"). Per decision: emit only on completion, not start. Error metadata included. |
| ACT-08 | Activity tab shows events in real-time via existing Supabase Realtime subscription | Already working -- `ActivityTimeline` subscribes to `postgres_changes` INSERT events on `activity_events` filtered by `workspace_id`. Realtime publication enabled in migration 00013. No work needed beyond ensuring INSERTs happen. |
</phase_requirements>

## Standard Stack

### Core (Already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (async) | existing | Database INSERT for activity_events | Already used by all sync services |
| Supabase Realtime | existing | Frontend receives INSERTs in real-time | Already configured, publication enabled |
| FastAPI | existing | OAuth callback/disconnect route handlers | Already hosts all integration endpoints |

### Supporting
No new libraries needed. This phase uses only existing project dependencies.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/services/
  sync_adapter.py          # ADD: emit_activity() helper here
  linear_sync.py           # MODIFY: add emit calls in sync_tickets_for_teams()
  github_sync.py           # MODIFY: add emit calls in sync_repos()
  gitlab_sync.py           # MODIFY: add emit calls in sync_projects()
  jira_sync.py             # MODIFY: add emit calls in sync_jira_issues()
  notion_sync.py           # MODIFY: add emit calls in run_full_sync()
  synthesis.py             # MODIFY: add emit call in generate_context_page()

backend/src/routers/
  linear.py                # MODIFY: add emit in callback() and disconnect_linear()
  github.py                # MODIFY: add emit in callback() and disconnect_github()
  gitlab.py                # MODIFY: add emit in callback() and disconnect_gitlab()
  slack.py                 # MODIFY: add emit in callback() and disconnect_slack()
  notion.py                # MODIFY: add emit in callback() and disconnect_notion()
  jira.py                  # MODIFY: add emit in callback() and disconnect_jira()
  telegram.py              # MODIFY: add emit in connect() and disconnect()

apps/web/src/app/dashboard/activity/
  formatters.ts            # MODIFY: update context_generated formatter
  activity-timeline.tsx    # MODIFY: add error state visual treatment
  types.ts                 # NO CHANGE: all 6 event types already defined
```

### Pattern 1: Centralized emit_activity() Helper

**What:** A single async function that INSERTs into `activity_events` with fail-silent behavior.
**When to use:** Every sync completion, connect, disconnect, and context generation event.
**Example:**
```python
# In sync_adapter.py
async def emit_activity(
    session: AsyncSession,
    workspace_id: UUID,
    event_type: str,
    metadata: dict | None = None,
    actor_id: UUID | None = None,
) -> None:
    """Emit an activity event. Fail-silent -- never breaks the caller."""
    try:
        from sqlalchemy import text
        await session.execute(
            text("""
                INSERT INTO activity_events (workspace_id, actor_id, event_type, metadata)
                VALUES (:workspace_id, :actor_id, :event_type, :metadata)
            """),
            {
                "workspace_id": str(workspace_id),
                "actor_id": str(actor_id) if actor_id else None,
                "event_type": event_type,
                "metadata": json.dumps(metadata or {}),
            },
        )
        await session.flush()
    except Exception:
        logger.warning(
            "Failed to emit activity event %s for workspace %s",
            event_type, workspace_id, exc_info=True,
        )
```

### Pattern 2: Sync Event Injection Points

**What:** Emit `sync_started` at sync entry, `sync_completed` at sync exit (with timing).
**When to use:** Every sync service's main orchestration function.
**Example:**
```python
# In linear_sync.py, inside sync_tickets_for_teams():
import time

start_time = time.monotonic()

# At function start, after cursor status update:
await emit_activity(session, workspace_id, "sync_started", {"integration": "Linear"})

# After successful sync, before return:
duration_ms = int((time.monotonic() - start_time) * 1000)
await emit_activity(session, workspace_id, "sync_completed", {
    "integration": "Linear",
    "items_count": total_tickets,
    "duration_ms": duration_ms,
})

# In except block, after error status update:
await emit_activity(session, workspace_id, "sync_completed", {
    "integration": "Linear",
    "error": True,
    "error_message": "sync failed",
})
```

### Pattern 3: OAuth Callback Emission

**What:** Emit `integration_connected` after successful OAuth exchange.
**When to use:** Inside each provider's callback handler, after successful `exchange_code()`.
**Example:**
```python
# In linear.py callback():
# After exchange_code succeeds, before redirect:
try:
    from src.services.sync_adapter import emit_activity
    from src.db import async_session
    # Callback handlers may not have workspace session in scope,
    # use the session dependency that's already injected
    await emit_activity(session, workspace_id, "integration_connected", {
        "integration": "Linear",
    })
except Exception:
    pass  # fail-silent
```

### Pattern 4: Disconnect Emission

**What:** Emit `integration_disconnected` in disconnect handlers.
**When to use:** Every provider's disconnect endpoint.
**Example:**
```python
# In linear.py disconnect_linear():
await disconnect(session, user.workspace_id, user.user_id)
await emit_activity(session, user.workspace_id, "integration_disconnected", {
    "integration": "Linear",
}, actor_id=user.user_id)
return {"status": "disconnected"}
```

### Pattern 5: Context Generation Emission

**What:** Emit `context_generated` after synthesis completes or fails.
**When to use:** In `generate_context_page()` after LLM response.
**Example:**
```python
# In synthesis.py generate_context_page(), after commit:
await emit_activity(session, workspace_id, "context_generated", {
    "ticket_id": ticket_identifier,
    "ticket_title": ticket.title,
    "source_count": len(sources_list),
    "token_count": llm_response.total_tokens,
})

# In error handler:
await emit_activity(session, workspace_id, "context_generated", {
    "ticket_id": ticket_identifier,
    "error": True,
    "error_message": str(e)[:200],
})
```

### Anti-Patterns to Avoid
- **Emitting inside webhook handlers:** Per decision, webhook-triggered syncs do NOT emit events. Only `full_sync()` calls emit.
- **Breaking sync on emit failure:** Emission must be wrapped in try/except. A failed INSERT must never propagate to the caller.
- **Emitting per-item:** One event per sync call, not per ticket/PR/page. `items_count` in metadata communicates volume.
- **Creating a new DB session for emission:** Use the existing session from the sync function. Only create a separate session if the caller is a background task that already committed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Activity event table | New table/schema | Existing `activity_events` from migration 00012 | Schema already has all 6 event types, RLS, indexes, 30-day retention |
| Realtime delivery | Custom WebSocket | Existing Supabase Realtime subscription in ActivityTimeline | Already subscribes to INSERT events, handles buffering and pagination |
| Event type system | New event types | Existing CHECK constraint: 6 types | Adding new types requires migration; current 6 cover all requirements |
| Formatter logic | New components | Existing `formatEventDescription()` and `getMetadataChip()` | Already handle all 6 event types, just need minor updates |

## Common Pitfalls

### Pitfall 1: Session Scope in Background Tasks
**What goes wrong:** Background tasks (FastAPI `background_tasks.add_task`) run after the request session closes. If emit_activity uses the request session, it will fail.
**Why it happens:** Linear sync, GitHub sync, etc. run as background tasks that create their own sessions via `async_session()`. The emit call must use THAT session, not the request session.
**How to avoid:** Always use the session passed to the sync function. For OAuth callbacks that run in the request scope, use the request session. For background syncs, use the background session.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError: This Session's transaction has been rolled back`

### Pitfall 2: Notion Sync Creates Its Own Session
**What goes wrong:** `run_full_sync()` in `notion_sync.py` creates its own session via `async with async_session() as session:`. The emit call must happen INSIDE that context manager, using that session.
**Why it happens:** Notion sync runs as a background task that manages its own session lifecycle.
**How to avoid:** Place emit calls inside the `try` block of `run_full_sync()`, using the local `session` variable.
**Warning signs:** Events not appearing for Notion syncs specifically.

### Pitfall 3: GitHub/GitLab Per-Repo Commits
**What goes wrong:** GitHub and GitLab sync call `await session.commit()` after each repo/project. If you emit `sync_completed` after all repos but before the final commit, the event may be lost on rollback.
**Why it happens:** These services commit per-repo for partial data preservation.
**How to avoid:** Emit `sync_started` at the very beginning (before any per-repo work). Emit `sync_completed` at the end, after the last repo. Emit error events in per-repo error handlers only for individual repo failures, not the overall sync.
**Warning signs:** Missing activity events when one repo fails but others succeed.

### Pitfall 4: Slack/Telegram Have No full_sync
**What goes wrong:** Trying to add sync events to Slack and Telegram when they have no `full_sync()` method.
**Why it happens:** Slack ingests messages via webhook events (not bulk sync). Telegram processes updates via bot webhook. Neither has a scheduled full sync.
**How to avoid:** For ACT-05, Slack's closest equivalent is huddle transcript polling (`poll_huddle_transcripts`). Telegram has no sync at all -- only connect/disconnect events (ACT-06). The 7-provider requirement for sync events may only apply to the 5 that actually have full_sync, plus huddle polls for Slack. Telegram gets connect/disconnect events only.
**Warning signs:** Looking for a function that doesn't exist.

### Pitfall 5: OAuth Callback Session Availability
**What goes wrong:** OAuth callback endpoints don't have `get_current_user` dependency -- they receive redirects from providers with `code` and `state` params. There's no `user_id` readily available from the dependency.
**Why it happens:** Callbacks are not JWT-protected. The workspace_id is extracted from the signed state token. The user_id is looked up from workspace_members.
**How to avoid:** Use the `workspace_id` extracted from state verification and the `user_id` looked up from the `WorkspaceMember` query that already exists in each callback. Emit the event using the same session, after `exchange_code` succeeds but before the redirect.
**Warning signs:** Missing `actor_id` or looking for `UserContext` in callback handlers.

### Pitfall 6: Frontend Error State Display
**What goes wrong:** Error events display the same as success events -- no visual differentiation.
**Why it happens:** The current `formatEventDescription()` and `getMetadataChip()` don't check for `metadata.error`.
**How to avoid:** Update `formatEventDescription` to append " (failed)" when `metadata.error` is true. Update `getMetadataChip` to show "failed" chip. Add conditional styling in `EventRow` for error events (red icon color).
**Warning signs:** Error events look identical to success events in the timeline.

## Code Examples

### Existing activity_events Schema (from migration 00012)
```sql
-- Source: supabase/migrations/00012_onboarding_and_activity.sql
CREATE TABLE public.activity_events (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid        NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  actor_id     uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  event_type   text        NOT NULL CHECK (event_type IN (
    'sync_started', 'sync_completed', 'context_generated',
    'integration_connected', 'integration_disconnected', 'user_signed_up'
  )),
  metadata     jsonb       DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now()
);
```

### Existing Frontend Formatter (from formatters.ts)
```typescript
// Source: apps/web/src/app/dashboard/activity/formatters.ts
export function formatEventDescription(event: ActivityEvent): string {
  const meta = event.metadata
  switch (event.event_type) {
    case 'sync_started':
      return `${meta.integration ?? 'Unknown'} sync started`
    case 'sync_completed':
      return `${meta.integration ?? 'Unknown'} sync completed`
    case 'context_generated':
      return `Context generated from ${meta.source_count ?? '?'} sources`
    // ...
  }
}
```

### Existing Realtime Subscription (from activity-timeline.tsx)
```typescript
// Source: apps/web/src/app/dashboard/activity/activity-timeline.tsx
const channel = supabase
  .channel(`activity-${workspaceId}`)
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'activity_events',
      filter: `workspace_id=eq.${workspaceId}`,
    },
    (payload) => {
      const newEvent = payload.new as ActivityEvent
      // Auto-prepends to timeline
    }
  )
  .subscribe()
```

### Sync Service Return Value Patterns
```python
# Linear: {"tickets_synced": N, "comments_synced": M, "teams": [...]}
# GitHub:  {"total_prs": N, "total_reviews": M, "repos": {...}}
# GitLab: {"total_mrs": N, "total_reviews": M, "projects": {...}}
# Jira:   {"issues_synced": N, "comments_synced": M}
# Notion: run_full_sync() is void (updates config JSONB internally)
```

## Provider-Specific Injection Map

| Provider | Sync Function | Session Source | items_count Key | Connect Handler | Disconnect Handler |
|----------|---------------|---------------|-----------------|-----------------|-------------------|
| Linear | `sync_tickets_for_teams()` | Passed in (bg task creates session in router) | `tickets_synced` from return | `routers/linear.py::callback()` | `routers/linear.py::disconnect_linear()` |
| GitHub | `sync_repos()` | Passed in (bg task creates session in router) | `total_prs` from return | `routers/github.py::callback()` | `routers/github.py::disconnect_github()` |
| GitLab | `sync_projects()` | Passed in | `total_mrs` from return | `routers/gitlab.py::callback()` | `routers/gitlab.py::disconnect_gitlab()` |
| Jira | `sync_jira_issues()` | Passed in | `issues_synced` from return | `routers/jira.py::callback()` | `routers/jira.py::disconnect_jira()` |
| Notion | `run_full_sync()` | Creates own (`async_session()`) | `synced_count` local var | `routers/notion.py::callback()` | `routers/notion.py::disconnect_notion()` |
| Slack | N/A (webhook events only) | N/A | N/A | `routers/slack.py::callback()` | `routers/slack.py::disconnect_slack()` |
| Telegram | N/A (bot webhook only) | N/A | N/A | `routers/telegram.py::connect()` | `routers/telegram.py::disconnect()` |

**Note:** Slack and Telegram have no `full_sync()`. For ACT-05, emit sync events only for the 5 providers that have full sync. Slack's huddle poll (`poll_huddle_transcripts`) could optionally emit a sync event. Telegram gets connect/disconnect events only (ACT-06).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Empty activity tab | Events emitted by this phase | Phase 32 | Activity tab becomes useful |
| No sync visibility | sync_started + sync_completed events | Phase 32 | Users see when syncs happen |

**Current state:** The `activity_events` table exists but has zero rows. No code anywhere in the backend inserts into it. The frontend is fully built and waiting for data.

## Open Questions

1. **Slack sync events for ACT-05**
   - What we know: Slack has no `full_sync()`. It ingests messages via real-time webhook events. The huddle poll is the closest to a "sync" operation.
   - What's unclear: Does ACT-05 strictly require all 7 providers to emit sync events, or just the ones that have sync operations?
   - Recommendation: Emit sync events for the 5 providers with `full_sync()`. Slack gets connect/disconnect events. Optionally emit a sync event for huddle polling if that counts as a sync. Telegram gets connect/disconnect only.

2. **Commit ordering for emit in GitHub/GitLab**
   - What we know: GitHub and GitLab commit per-repo. The overall sync_completed event should come after all repos.
   - What's unclear: Should the sync_completed event be committed in a separate transaction or with the last repo commit?
   - Recommendation: Emit sync_completed after the SyncRunLogger context exits, using a fresh session if the original session was committed. Alternatively, do a final commit after emitting.

## Sources

### Primary (HIGH confidence)
- `supabase/migrations/00012_onboarding_and_activity.sql` - activity_events schema definition
- `supabase/migrations/00013_realtime_activity.sql` - Realtime publication setup
- `backend/src/services/sync_adapter.py` - SyncAdapter protocol, update_cursor_status, SyncRunLogger
- `backend/src/services/linear_sync.py` - Linear sync flow and return values
- `backend/src/services/github_sync.py` - GitHub sync flow, per-repo commits
- `backend/src/services/gitlab_sync.py` - GitLab sync flow, per-project commits
- `backend/src/services/jira_sync.py` - Jira sync flow and return values
- `backend/src/services/notion_sync.py` - Notion sync flow, own session creation
- `backend/src/services/synthesis.py` - Context generation flow, generate_context_page()
- `backend/src/routers/linear.py` - OAuth callback and disconnect patterns
- `backend/src/routers/slack.py` - Slack callback and disconnect
- `backend/src/routers/telegram.py` - Telegram connect and disconnect (bot-based)
- `apps/web/src/app/dashboard/activity/formatters.ts` - Frontend formatters
- `apps/web/src/app/dashboard/activity/activity-timeline.tsx` - Realtime subscription
- `apps/web/src/app/dashboard/activity/types.ts` - Event type definitions

### Secondary (MEDIUM confidence)
- `backend/src/services/sync_scheduler.py` - Polling fallback patterns (for understanding reconciliation vs full sync)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all components already exist in codebase
- Architecture: HIGH - patterns directly observed in source code
- Pitfalls: HIGH - identified from actual code patterns (session scoping, commit timing)

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable -- existing codebase patterns)
