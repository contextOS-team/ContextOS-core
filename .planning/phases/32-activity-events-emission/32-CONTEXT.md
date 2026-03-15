# Phase 32: Activity Events Emission - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire all backend services to emit rows into the `activity_events` table so the Activity tab shows real events. Covers: integration sync events (7 providers), context generation events, and integration connect/disconnect events. No schema changes, no new frontend components -- just backend emission + minor formatter updates.

</domain>

<decisions>
## Implementation Decisions

### Emission pattern
- Centralized `emit_activity()` helper in `sync_adapter.py` -- single place to maintain, all 7 providers call it
- Emit both `sync_started` AND `sync_completed` for every full sync -- gives real-time liveness feel
- Context generation: emit only `context_generated` on completion (no start event, no schema change needed)
- Integration connect/disconnect: Claude finds OAuth callback endpoints and settings disconnect handlers, wires emission there

### Event metadata
- `sync_completed` includes: `items_count`, `duration_ms`, plus Claude's discretion on provider-specific details
- `sync_started` includes: `integration` name (required by frontend formatter)
- `context_generated` includes: `source_count`, `token_count`, `ticket_title` and/or `ticket_id` for richer display
- Frontend formatter updated: "Context generated for CON-42 · 5 sources" instead of generic "Context generated from 5 sources"

### Failure handling
- Failed syncs emit `sync_completed` with `metadata.error: true` and `metadata.error_message` -- no new event type needed
- Failed events shown with red accent icon and "failed" chip in timeline
- Failed context generation emits `context_generated` with error metadata (satisfies ACT-07 requirement for error events)
- Event emission itself is fail-silent with logging -- never breaks the actual sync or context generation (follows existing fail-silent graph extraction pattern)

### Granularity
- One event per `full_sync()` call -- not per-resource, not per-item
- Webhook-triggered syncs do NOT emit activity events (too noisy -- every Slack message, every ticket update)
- Telegram treated identically to other providers despite bot-based auth
- `items_count` metadata conveys sync volume

### Claude's Discretion
- Exact placement of emit calls within OAuth callback handlers
- Provider-specific metadata fields beyond items_count and duration_ms
- Visual treatment details for error states (icon choice, color shade)
- Whether to add helper method to SyncAdapter protocol or keep as standalone function

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sync_adapter.py`: `update_cursor_status()` already runs at sync boundaries -- natural injection point for `emit_activity()`
- `SyncRunLogger`: context manager that wraps sync runs -- could be extended or paralleled
- `activity_events` table: fully defined with 6 event types, RLS, indexes, 30-day retention
- `ActivityTimeline` component: complete with Realtime subscription, formatters, icons for all 6 types

### Established Patterns
- Fail-silent pattern: graph extraction never breaks webhook ingestion -- activity emission should follow same pattern
- `SyncAdapter` protocol: `full_sync()` returns summary dict -- can extract items_count from return value
- Frontend formatters: `formatEventDescription()` and `getMetadataChip()` in `apps/web/src/app/dashboard/activity/formatters.ts`

### Integration Points
- 7 sync services: `linear_sync.py`, `slack_sync.py` (find), `github_sync.py`, `gitlab_sync.py`, `jira_sync.py`, `notion_sync.py`, `telegram_sync.py` (find)
- Context generation: find the synthesis/generation service that produces context pages
- OAuth callbacks: find callback endpoints in routers for connect events
- Settings disconnect: find disconnect handlers in settings/integration routers

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 32-activity-events-emission*
*Context gathered: 2026-03-16*
