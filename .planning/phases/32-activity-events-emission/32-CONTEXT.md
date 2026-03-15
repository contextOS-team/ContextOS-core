# Phase 32: Activity Events Emission - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning (revised after design critique)

<domain>
## Phase Boundary

Wire all backend services to emit rows into the `activity_events` table so the Activity tab shows real, useful events. Covers:
1. Full sync events (sync_started/sync_completed) for 5 providers with full_sync()
2. Curated high-signal webhook events (ticket created, PR merged, meeting recorded) -- not every webhook, only user-meaningful ones
3. Context generation events
4. Integration connect/disconnect events
5. Frontend improvements: integration-colored icons, error state treatment, integration sync status display

Schema changes: new event types needed for webhook-derived events (e.g., `ticket_created`, `pr_merged`, `meeting_recorded`). Migration required to expand the CHECK constraint on event_type.

</domain>

<decisions>
## Implementation Decisions

### Emission pattern
- Centralized `emit_activity()` helper in `sync_adapter.py` -- single place to maintain, all providers call it
- Emit both `sync_started` AND `sync_completed` for every full sync -- gives real-time liveness feel
- Context generation: emit only `context_generated` on completion (no start event)
- Integration connect/disconnect: wire into OAuth callback endpoints and settings disconnect handlers

### Curated webhook events (NEW -- from design critique)
- Webhook handlers emit high-signal events only -- not every update, only meaningful ones:
  - **Linear/Jira**: ticket/issue created (NOT every status change or comment)
  - **GitHub/GitLab**: PR merged (NOT every push, comment, or review)
  - **Slack**: skip (individual messages are too noisy, no good "high-signal" event)
  - **Fathom**: meeting transcript recorded (when poll_transcripts finds a new one)
  - **Notion**: page created (NOT every content edit)
  - **Telegram**: skip (same as Slack -- individual messages)
- New event types needed in DB CHECK constraint: `ticket_created`, `pr_merged`, `meeting_recorded`, `page_created`
- Migration to expand event_type CHECK constraint
- These events include rich metadata: ticket title, PR title+number, meeting title, page title

### Event metadata
- `sync_completed` includes: `items_count`, `duration_ms`, plus Claude's discretion on provider-specific details
- `sync_started` includes: `integration` name (required by frontend formatter)
- `context_generated` includes: `source_count`, `token_count`, `ticket_title` and/or `ticket_id` for richer display
- `ticket_created` includes: `integration`, `ticket_id`, `title`
- `pr_merged` includes: `integration`, `pr_number`, `title`, `repo`
- `meeting_recorded` includes: `title`, `duration_minutes`, `participants_count`
- `page_created` includes: `integration`, `page_title`
- Frontend formatter updated: "Context generated for CON-42 . 5 sources" instead of generic message

### Failure handling
- Failed syncs emit `sync_completed` with `metadata.error: true` and `metadata.error_message` -- no new event type needed
- Failed events shown with red/destructive accent icon and "failed" badge in timeline
- Failed context generation emits `context_generated` with error metadata
- Event emission itself is fail-silent with logging -- never breaks the actual sync or webhook processing

### Frontend improvements (NEW -- from design critique)
- **Integration-colored icons**: each provider gets its brand color (Linear purple, GitHub dark, Slack multicolor, Jira blue, GitLab orange, Notion black, Telegram blue, Fathom brand color). Applied to icon color in EventRow based on `metadata.integration`
- **Error state visual treatment**: red/destructive color on icon, "failed" badge chip, error message visible in the row (not just on hover)
- **Integration sync status row**: show "Last synced: 3h ago" per connected integration at the top of the Activity tab or as a summary section, so the user knows the system is alive even on quiet days

### Granularity
- Full syncs: one event per `full_sync()` call -- not per-resource
- Webhook events: one event per high-signal action (ticket created, PR merged, etc.) -- individual and specific
- `items_count` metadata conveys sync volume

### Claude's Discretion
- Exact placement of emit calls within OAuth callback handlers and webhook handlers
- Provider-specific metadata fields beyond the required ones
- Exact brand colors per integration (use official brand guidelines)
- Layout of integration sync status display (inline at top vs separate section vs sidebar)
- Whether to add helper method to SyncAdapter protocol or keep as standalone function
- Whether page_created applies only to Notion or also to other providers

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sync_adapter.py`: `update_cursor_status()` already runs at sync boundaries -- natural injection point for `emit_activity()`
- `SyncRunLogger`: context manager that wraps sync runs -- could be extended or paralleled
- `activity_events` table: 6 event types currently, needs migration to add 4 more
- `ActivityTimeline` component: complete with Realtime subscription, formatters, icons for all 6 types
- Webhook handlers: `linear_webhook.py`, `github_webhook.py`, `jira_webhook.py`, `notion_webhook.py` -- all have clear injection points

### Established Patterns
- Fail-silent pattern: graph extraction never breaks webhook ingestion -- activity emission should follow same pattern
- `SyncAdapter` protocol: `full_sync()` returns summary dict -- can extract items_count from return value
- Frontend formatters: `formatEventDescription()` and `getMetadataChip()` in `apps/web/src/app/dashboard/activity/formatters.ts`

### Integration Points
- 7 sync services: `linear_sync.py`, `slack_sync.py`, `github_sync.py`, `gitlab_sync.py`, `jira_sync.py`, `notion_sync.py`, `telegram_sync.py`
- 4 webhook handlers: `linear_webhook.py`, `github_webhook.py`, `jira_webhook.py`, `notion_webhook.py`
- Fathom polling: `fathom.py` poll_transcripts()
- Context generation: synthesis.py generate_context_page()
- OAuth callbacks: callback endpoints in all 7 provider routers
- Settings disconnect: disconnect handlers in all 7 provider routers

</code_context>

<specifics>
## Specific Ideas

- Integration colors should match official brand colors (e.g., Linear uses #5E6AD2, GitHub uses #24292f)
- "Last synced" status should show relative time ("3h ago") consistent with timeline timestamps
- High-signal webhook events should feel like "news" -- "New ticket: CON-52 Auth redesign" reads better than "ticket_created"

</specifics>

<deferred>
## Deferred Ideas

None -- all critique items included in scope

</deferred>

---

*Phase: 32-activity-events-emission*
*Context gathered: 2026-03-16 (revised after design critique)*
