# Phase 32: Activity Events Emission (REVISED) - Research

**Researched:** 2026-03-16
**Domain:** Backend event emission, DB migration, frontend activity UI
**Confidence:** HIGH

## Summary

Phase 32 wires all backend services to emit rows into the `activity_events` table so the Activity tab shows real, useful events. The codebase already has the complete infrastructure: the `activity_events` table (6 event types), Supabase Realtime subscription, `ActivityTimeline` component with formatters and icons. What is missing is that **no backend code ever inserts into the table**.

The revised scope adds four curated webhook event types (`ticket_created`, `pr_merged`, `meeting_recorded`, `page_created`) that require a DB migration to expand the CHECK constraint, plus frontend improvements (integration-colored icons, error state treatment, integration sync status display).

**Primary recommendation:** Create a centralized `emit_activity()` helper in `sync_adapter.py` that wraps a fail-silent INSERT into `activity_events`. Inject calls at 4 layers: (1) full_sync start/complete in each provider's sync function, (2) webhook handlers for high-signal events, (3) `synthesis.py` for context generation, (4) OAuth callback/disconnect endpoints. Update the CHECK constraint via migration 00031. Extend frontend types, formatters, and icons.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Centralized `emit_activity()` helper in `sync_adapter.py` -- single place to maintain, all providers call it
- Emit both `sync_started` AND `sync_completed` for every full sync
- Context generation: emit only `context_generated` on completion (no start event)
- Curated webhook events only (not every webhook):
  - Linear/Jira: ticket/issue created only (NOT status changes or comments)
  - GitHub/GitLab: PR merged only (NOT every push, comment, or review)
  - Slack: skip (too noisy)
  - Fathom: meeting transcript recorded (when poll_transcripts finds a new one)
  - Notion: page created (NOT every content edit)
  - Telegram: skip (too noisy)
- New event types in DB: `ticket_created`, `pr_merged`, `meeting_recorded`, `page_created`
- Failed syncs emit `sync_completed` with `metadata.error: true` -- no new event type
- Event emission is fail-silent with logging -- never breaks actual sync or webhook
- Full syncs: one event per `full_sync()` call -- not per-resource
- Integration-colored icons: brand colors per provider
- Error state: red/destructive icon + "failed" badge
- Integration sync status display: "Last synced: 3h ago" per connected integration

### Claude's Discretion
- Exact placement of emit calls within OAuth callback handlers and webhook handlers
- Provider-specific metadata fields beyond the required ones
- Exact brand colors per integration (use official brand guidelines)
- Layout of integration sync status display (inline at top vs separate section vs sidebar)
- Whether to add helper method to SyncAdapter protocol or keep as standalone function
- Whether page_created applies only to Notion or also to other providers

### Deferred Ideas (OUT OF SCOPE)
None -- all critique items included in scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACT-05 | All integration sync services emit events to activity_events on sync completion | `emit_activity()` helper + injection into 7 sync services' `full_sync()` calls |
| ACT-06 | Integration connect/disconnect actions emit activity events | Injection into OAuth callback endpoints (7 providers) and disconnect handlers (7 providers) |
| ACT-07 | Context page generation (start, complete, error) emits activity events | Injection into `synthesis.py` `generate_context_page()` and `generate_context_page_stream()` |
| ACT-08 | Activity tab shows events in real-time via existing Supabase Realtime subscription | Already working -- Realtime subscription exists in `ActivityTimeline`. Needs frontend updates for new event types, icons, formatters, error states, sync status display |
</phase_requirements>

## Architecture Patterns

### Recommended Approach: Centralized emit_activity() Helper

The `emit_activity()` function goes in `sync_adapter.py` (already the shared sync utility module). It performs a single INSERT into `activity_events` wrapped in try/except that logs but never raises.

```python
# In backend/src/services/sync_adapter.py

async def emit_activity(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    event_type: str,
    metadata: dict | None = None,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Insert an activity event row. Fail-silent -- never breaks callers."""
    try:
        from sqlalchemy import text
        await session.execute(
            text("""
                INSERT INTO activity_events (workspace_id, actor_id, event_type, metadata)
                VALUES (:workspace_id, :actor_id, :event_type, :metadata)
            """),
            {
                "workspace_id": workspace_id,
                "actor_id": actor_id,
                "event_type": event_type,
                "metadata": json.dumps(metadata or {}),
            },
        )
        # Do NOT commit here -- let the caller's transaction handle it
        # For webhook handlers that create their own sessions, they already commit
    except Exception:
        logger.warning("Failed to emit activity event %s", event_type, exc_info=True)
```

**Key design choice:** Use raw SQL `text()` INSERT rather than a SQLModel model to avoid import cycles and keep it lightweight. The `activity_events` table is simple enough that an ORM model is unnecessary.

**Critical:** Do NOT call `session.commit()` inside `emit_activity()`. Let the caller's existing transaction commit handle it. For webhook handlers that manage their own sessions (like `linear_webhook.py`), they already call `session.commit()` at the end of processing.

### Injection Points Map

#### 1. Full Sync Events (ACT-05) -- 7 providers

Each provider's `full_sync()` or its main sync function needs two calls:

| Provider | File | Sync Function | Injection Point |
|----------|------|---------------|-----------------|
| Linear | `linear_sync.py` | `sync_tickets_for_teams()` | Before line 160 (start), after line 194 (complete), in except block (error) |
| GitHub | `github_sync.py` | `sync_repos()` | At start of function (start), after completion (complete), in except block (error) |
| GitLab | `gitlab_sync.py` | similar pattern | Same as GitHub |
| Notion | `notion_sync.py` | `run_full_sync()` | After line 180 (start), after line 225 (complete), in except block (error) |
| Slack | `slack_channels.py` or wherever full_sync orchestrates | Same pattern | Same |
| Jira | `jira_sync.py` | `full_sync()` method | Same pattern |
| Telegram | `telegram_bot.py` or `telegram_events.py` | Wherever full sync runs | Same |

**Start event metadata:** `{"integration": "linear"}` (provider name)
**Complete event metadata:** `{"integration": "linear", "items_count": N, "duration_ms": M}`
**Error event metadata:** `{"integration": "linear", "error": true, "error_message": "..."}`

#### 2. Curated Webhook Events (NEW) -- 4 providers

| Event Type | Provider | File | Exact Injection Point |
|------------|----------|------|-----------------------|
| `ticket_created` | Linear | `linear_webhook.py` | End of `handle_issue_create()` (line ~224), after ticket is synced. Data available: `ticket.identifier`, `ticket.title` |
| `ticket_created` | Jira | `jira_webhook.py` | End of `_handle_issue_created()` (line ~127), after issue is upserted. Data available: `issue.jira_key`, `issue.summary` |
| `pr_merged` | GitHub | `github_webhook.py` | Inside `handle_pull_request_event()` (~line 242), check `action == "closed" and pr_data.get("merged", False)`. Data: `pr_record.number`, `pr_record.title`, `repo_full_name` |
| `pr_merged` | GitLab | `gitlab_webhook.py` | Inside `_handle_merge_request_event()`, check `state == "merged"`. Data: `mr_record.iid`, `mr_record.title`, `project_path` |
| `meeting_recorded` | Fathom | `fathom.py` | Inside `poll_transcripts()` (~line 403), after each new transcript is ingested. Data: `title`, `duration_minutes`, `len(participant_names)` |
| `page_created` | Notion | `notion_webhook.py` | More nuanced -- Notion webhook only fires `page.content_updated`. A true "page_created" would need to detect if the page is new (not in DB before sync). Could emit from `notion_sync.py` during full sync for new pages, or skip for webhooks since Notion doesn't distinguish create vs update. **Recommendation:** Emit `page_created` during Notion full_sync when a page is inserted (not updated), and potentially from the webhook handler when the page didn't exist before. |

#### 3. Context Generation Events (ACT-07)

| Event Type | File | Injection Point |
|------------|------|-----------------|
| `context_generated` (success) | `synthesis.py` | After line 681 (after commit in `generate_context_page()`). Data: `ticket_identifier`, `len(sources_list)`, `llm_response.total_tokens`, ticket title |
| `context_generated` (error) | `synthesis.py` | In the except block (~line 692). Data: `ticket_identifier`, `error: true`, `error_message` |
| `context_generated` (stream success) | `synthesis.py` | In `generate_context_page_stream()` at the equivalent completion point |

**Important:** The `generate_context_page()` function already commits within itself (line 681). The activity event INSERT must happen BEFORE that commit, or use a separate session. Recommended: insert before `session.commit()` on line 681.

#### 4. Connect/Disconnect Events (ACT-06)

| Event Type | Providers | File | Injection Point |
|------------|-----------|------|-----------------|
| `integration_connected` | All 7 | Each provider's router callback endpoint | After successful OAuth exchange/connection. Note: callback endpoints redirect (return RedirectResponse), so emit BEFORE the redirect. |
| `integration_disconnected` | All 7 | Each provider's router disconnect endpoint | After successful disconnect call. These return `{"status": "disconnected"}` so emit before the return. |

**Provider router patterns observed:**

- **OAuth providers** (Linear, GitHub, GitLab, Notion, Slack, Jira): `callback()` endpoint exchanges code, then redirects. Emit after `exchange_code()` / `handle_callback()` succeeds, before redirect.
- **API key providers** (Fathom): `connect()` endpoint. Emit after `connect_fathom()` succeeds.
- **Bot token providers** (Telegram): `connect()` endpoint. Same pattern.
- **All disconnect endpoints**: Simple -- emit after the disconnect service call.

**Session concern:** Callback endpoints in some providers don't have an active session after the service call commits. Need to create a new session for the activity event or pass the session through. The `session: AsyncSession = Depends(get_session)` is available in all callback/disconnect endpoints.

### DB Migration: Expand CHECK Constraint

New migration file: `supabase/migrations/00031_activity_event_types.sql`

```sql
-- Expand event_type CHECK constraint to include curated webhook event types
ALTER TABLE public.activity_events
  DROP CONSTRAINT activity_events_event_type_check;

ALTER TABLE public.activity_events
  ADD CONSTRAINT activity_events_event_type_check CHECK (event_type IN (
    'sync_started',
    'sync_completed',
    'context_generated',
    'integration_connected',
    'integration_disconnected',
    'user_signed_up',
    'ticket_created',
    'pr_merged',
    'meeting_recorded',
    'page_created'
  ));
```

**Important:** The CHECK constraint name needs to be verified. PostgreSQL auto-generates it. Use `\d activity_events` or inspect the migration to find the exact name. The standard auto-generated name for a CHECK on a column named `event_type` in table `activity_events` is `activity_events_event_type_check`.

### Frontend Changes

#### New Event Types in types.ts

```typescript
export type EventType =
  | 'sync_started'
  | 'sync_completed'
  | 'context_generated'
  | 'integration_connected'
  | 'integration_disconnected'
  | 'user_signed_up'
  | 'ticket_created'
  | 'pr_merged'
  | 'meeting_recorded'
  | 'page_created'
```

#### Integration Brand Colors

Official brand colors for icon tinting:

| Provider | Color | Hex | Source |
|----------|-------|-----|--------|
| Linear | Purple | `#5E6AD2` | Official brand |
| GitHub | Dark | `#24292f` | Official brand (use muted foreground in dark theme) |
| GitLab | Orange | `#FC6D26` | Official brand |
| Jira | Blue | `#0052CC` | Atlassian brand |
| Notion | Black/White | `#000000` / `#FFFFFF` (theme-aware) | Official brand |
| Slack | Aubergine | `#4A154B` | Official brand |
| Fathom | Purple-ish | `#7C3AED` | Brand approximation (verify) |
| Telegram | Blue | `#0088CC` | Official brand |

**Implementation approach:** Create a `INTEGRATION_COLORS` map in `types.ts` keyed by integration name from `metadata.integration`. Apply as inline `style={{ color }}` on the icon in `EventRow`, overriding the default `text-muted-foreground` class.

#### Error State Treatment

In `EventRow`, check `event.metadata.error === true`:
- Apply `text-destructive` class to icon instead of default color
- Show a "failed" badge chip (small red pill after the description)
- Show `metadata.error_message` inline in muted text

#### Formatter Updates for New Event Types

```typescript
case 'ticket_created':
  return `New ticket: ${meta.ticket_id ?? ''} ${meta.title ?? ''}`.trim()
case 'pr_merged':
  return `PR merged: ${meta.repo ?? ''}#${meta.pr_number ?? ''} ${meta.title ?? ''}`.trim()
case 'meeting_recorded':
  return `Meeting recorded: ${meta.title ?? 'Untitled'}`
case 'page_created':
  return `New page: ${meta.page_title ?? 'Untitled'}`
```

For `context_generated`, update to include ticket info:
```typescript
case 'context_generated':
  if (meta.ticket_id)
    return `Context generated for ${meta.ticket_id} \u00b7 ${meta.source_count ?? '?'} sources`
  return `Context generated from ${meta.source_count ?? '?'} sources`
```

#### Icons for New Event Types

Use Lucide icons already available in the project:
- `ticket_created`: `TicketPlus` or `CirclePlus`
- `pr_merged`: `GitMerge`
- `meeting_recorded`: `Mic` or `Video`
- `page_created`: `FileText` or `FilePlus`

#### Integration Sync Status Display

A new section at the top of the Activity tab showing per-integration last sync time. Data source: the existing `sync_cursors` table has `last_sync_at` per provider, and the existing `/api/{provider}/sync/status` endpoints expose this. Alternatively, query `sync_cursors` directly from Supabase client.

**Recommended approach:** Add a server-side query in `page.tsx` that fetches the latest `sync_completed` event per integration from `activity_events` (using `DISTINCT ON` or group by). This avoids a new API endpoint. Alternatively, read from `workspace_integrations` table which has `config.last_sync_at` for some providers.

**Simplest approach:** Query `activity_events` for the most recent `sync_completed` event per unique `metadata->>'integration'` value. This uses data that Phase 32 itself creates.

```sql
SELECT DISTINCT ON (metadata->>'integration')
  metadata->>'integration' as integration,
  created_at as last_synced_at,
  metadata
FROM activity_events
WHERE workspace_id = $1
  AND event_type = 'sync_completed'
ORDER BY metadata->>'integration', created_at DESC;
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Activity event insertion | Custom ORM model with relationships | Raw SQL `text()` INSERT | Simpler, no import cycles, table is write-only from backend perspective |
| Relative time formatting | Custom `formatRelativeTime()` | Existing `formatTimelineTimestamp()` in `formatters.ts` | Already handles "3h ago" format |
| Realtime subscription | New WebSocket setup | Existing Supabase Realtime channel in `ActivityTimeline` | Already subscribed to `activity_events` INSERTs |
| Brand color constants | Fetch from provider APIs | Static map in frontend code | Brand colors are stable, no API needed |

## Common Pitfalls

### Pitfall 1: Breaking Sync/Webhook on Emit Failure
**What goes wrong:** If `emit_activity()` raises an exception, the parent sync or webhook handler fails, losing actual data.
**Why it happens:** Forgetting the try/except wrapper or letting a session error propagate.
**How to avoid:** `emit_activity()` MUST wrap everything in try/except and log warning only. Never re-raise.
**Warning signs:** Sync failures in logs with activity_events in the traceback.

### Pitfall 2: Transaction Isolation with Separate Sessions
**What goes wrong:** Webhook handlers like `linear_webhook.py` create their own session (`async with async_session() as session`). If you create a SECOND session inside `emit_activity()`, the event gets committed independently and may be visible before the webhook data is committed.
**Why it happens:** Misunderstanding which session to use.
**How to avoid:** Always pass the existing session to `emit_activity()`. Never create a new session inside it.
**Warning signs:** Activity events appearing in the timeline for data that doesn't exist yet.

### Pitfall 3: CHECK Constraint Violation
**What goes wrong:** Inserting a new event type without first running the migration.
**Why it happens:** Migration not applied, or misspelled event_type string.
**How to avoid:** Migration must be the FIRST task. Use constants for event type strings.
**Warning signs:** PostgreSQL error: `new row for relation "activity_events" violates check constraint`.

### Pitfall 4: Duplicate Events on Full Sync Retry
**What goes wrong:** If a sync fails partway and retries, you get duplicate `sync_started` events.
**Why it happens:** `sync_started` is emitted at the beginning, and a retry emits it again.
**How to avoid:** This is acceptable -- the timeline shows both attempts, which is accurate. The user sees the retry happened. No dedup needed.

### Pitfall 5: Notion "page_created" Ambiguity
**What goes wrong:** Notion webhooks only fire `page.content_updated`, not `page.created`. Emitting `page_created` on every webhook would be wrong.
**Why it happens:** Notion API doesn't distinguish create from update in webhooks.
**How to avoid:** For Notion webhooks, check if the page already exists in the DB before the sync. If it's new (INSERT not UPDATE), emit `page_created`. During full_sync, emit `page_created` only for newly inserted pages.

### Pitfall 6: GitHub PR Merged Detection
**What goes wrong:** Emitting `pr_merged` on wrong conditions.
**Why it happens:** GitHub sends `action: "closed"` for both merged and unmerged-closed PRs.
**How to avoid:** Check BOTH `action == "closed"` AND `pr_data.get("merged") == True` (or `merged_at` is not None). The existing code already computes `state = map_pr_state(...)` which handles this -- check `state == "merged"`.

### Pitfall 7: Session Already Committed in synthesis.py
**What goes wrong:** `generate_context_page()` calls `session.commit()` on line 681. If you emit the activity event AFTER the commit, the event is in a new implicit transaction.
**How to avoid:** Insert the activity event BEFORE `session.commit()` on line 681, so it's part of the same transaction. Or accept that a separate flush/commit for the event is fine (fail-silent anyway).

## Code Examples

### emit_activity() Helper Pattern
```python
# Source: Derived from existing codebase patterns (sync_adapter.py)
import json

async def emit_activity(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    event_type: str,
    metadata: dict | None = None,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Emit an activity event. Fail-silent."""
    try:
        from sqlalchemy import text
        await session.execute(
            text(
                "INSERT INTO activity_events (workspace_id, actor_id, event_type, metadata)"
                " VALUES (:ws, :actor, :et, :meta::jsonb)"
            ),
            {
                "ws": workspace_id,
                "actor": actor_id,
                "et": event_type,
                "meta": json.dumps(metadata or {}),
            },
        )
    except Exception:
        logger.warning(
            "emit_activity failed: type=%s workspace=%s",
            event_type, workspace_id, exc_info=True,
        )
```

### Webhook Injection Example (Linear ticket_created)
```python
# In linear_webhook.py handle_issue_create(), after line ~224:
async def handle_issue_create(session, workspace_id, data):
    # ... existing code to sync ticket ...
    ticket = await sync_single_ticket(session, workspace_id, access_token, linear_id)
    if not ticket:
        return

    # ... existing graph extraction and embedding code ...

    # NEW: Emit activity event (fail-silent)
    from src.services.sync_adapter import emit_activity
    await emit_activity(
        session, workspace_id, "ticket_created",
        metadata={
            "integration": "linear",
            "ticket_id": ticket.identifier,
            "title": ticket.title,
        },
    )
```

### GitHub PR Merged Detection
```python
# In github_webhook.py handle_pull_request_event(), after upsert:
if state == "merged":
    await emit_activity(
        session, workspace_id, "pr_merged",
        metadata={
            "integration": "github",
            "pr_number": pr_record.number,
            "title": pr_record.title,
            "repo": repo_full_name,
        },
    )
```

### Connect/Disconnect Emission
```python
# In routers/linear.py callback(), after exchange_code succeeds:
await emit_activity(
    session, workspace_id, "integration_connected",
    metadata={"integration": "linear", "org_name": org_name},
    actor_id=user_id,
)

# In routers/linear.py disconnect_linear():
await emit_activity(
    session, workspace_id, "integration_disconnected",
    metadata={"integration": "linear"},
    actor_id=user.user_id,
)
```

## Metadata Available at Each Injection Point

### Linear Webhook (handle_issue_create)
- `ticket.identifier` (e.g., "CON-52")
- `ticket.title`
- `ticket.linear_id`
- `data.get("teamId")` -- team info

### Jira Webhook (_handle_issue_created)
- `issue.jira_key` (e.g., "PROJ-123")
- `issue.summary` (title equivalent)
- `issue.project_key`, `issue.project_name`

### GitHub Webhook (handle_pull_request_event)
- `pr_record.number`
- `pr_record.title`
- `repo_full_name`
- `pr_data.get("merged_at")`
- `state` (already computed by `map_pr_state()`)

### GitLab Webhook (_handle_merge_request_event)
- `mr_record.iid` (MR number within project)
- `mr_record.title`
- `project_path` (path_with_namespace)
- `state` (already computed by `map_mr_state()`)

### Fathom (poll_transcripts)
- `title` (meeting title)
- `duration_minutes`
- `len(participant_names)` (participants count)
- `fathom_id`

### Notion (webhook + full_sync)
- `page.title`
- `page.notion_id`
- No clear "created" signal from webhook (only `page.content_updated`)

### Synthesis (generate_context_page)
- `ticket_identifier`
- `len(sources_list)` (source_count)
- `llm_response.total_tokens` (token_count)
- `ticket.title` (available via the ticket lookup)

## Open Questions

1. **Notion page_created from webhooks**
   - What we know: Notion webhooks only fire `page.content_updated`, not a create event
   - What's unclear: Whether to detect "new page" by checking DB before sync
   - Recommendation: Emit `page_created` only during full_sync for newly inserted pages. For webhooks, check if the page existed before the sync call. If not, emit `page_created`.

2. **Fathom brand color**
   - What we know: Fathom's brand uses purple tones
   - What's unclear: Exact hex code from official brand guidelines
   - Recommendation: Use `#7C3AED` (violet-600) as approximation. Can be updated later.

3. **Sync status display layout**
   - What we know: User wants "Last synced: 3h ago" per integration
   - What's unclear: Whether this goes at the top of Activity tab, in a sidebar section, or as a summary row
   - Recommendation: Add a compact row of integration badges at the top of the Activity page, each showing provider icon + "3h ago". Simple horizontal layout, scrollable if needed.

4. **CHECK constraint name**
   - What we know: The constraint was created inline in the CREATE TABLE statement
   - What's unclear: Whether PostgreSQL auto-named it `activity_events_event_type_check` or something else
   - Recommendation: Use `ALTER TABLE ... DROP CONSTRAINT IF EXISTS` with the expected name, or query `pg_constraint` in the migration. Safest: drop and recreate the constraint by name.

## Sources

### Primary (HIGH confidence)
- `supabase/migrations/00012_onboarding_and_activity.sql` -- activity_events table schema, CHECK constraint definition
- `supabase/migrations/00013_realtime_activity.sql` -- Realtime publication
- `backend/src/services/sync_adapter.py` -- SyncAdapter protocol, update_cursor_status pattern
- `backend/src/services/linear_webhook.py` -- webhook handler structure, injection points
- `backend/src/services/github_webhook.py` -- PR event handling, state detection
- `backend/src/services/jira_webhook.py` -- issue event handling
- `backend/src/services/notion_webhook.py` -- page update handling
- `backend/src/services/fathom.py` -- transcript polling, metadata available
- `backend/src/services/synthesis.py` -- context generation flow, commit pattern
- `backend/src/services/linear_sync.py` -- full_sync pattern (sync_tickets_for_teams)
- `backend/src/services/notion_sync.py` -- full_sync pattern (run_full_sync)
- `apps/web/src/app/dashboard/activity/` -- all frontend activity files

### Secondary (MEDIUM confidence)
- Brand colors based on commonly known official values (Linear #5E6AD2, GitHub #24292f, etc.)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - using only existing dependencies (SQLAlchemy, Supabase Realtime, Lucide icons)
- Architecture: HIGH - all injection points identified from reading actual source code
- Pitfalls: HIGH - derived from actual code patterns (session management, CHECK constraints)
- Frontend: HIGH - existing component structure fully understood
- Brand colors: MEDIUM - some colors approximated (Fathom)

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable codebase, no external dependencies changing)
