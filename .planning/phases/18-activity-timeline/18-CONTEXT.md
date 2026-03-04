# Phase 18: Activity Timeline - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Users see a live chronological feed of workspace events (syncs, context generated, integrations connected) on the dashboard Activity page. The `activity_events` table already exists (Phase 16). This phase replaces the static skeleton placeholder at `/dashboard/activity` with a dynamic client component that queries events, groups them by day, renders compact rows with icons and timestamps, and subscribes to Supabase Realtime for live updates.

</domain>

<decisions>
## Implementation Decisions

### Event card design
- Compact single-line rows: icon + description text + relative timestamp
- Lucide icons mapped per event type (e.g., RefreshCw for sync, Sparkles for context, Plug for integration, UserPlus for signup)
- Icons use text-muted-foreground color -- teal reserved for actionable elements only (DS-02)
- Descriptions are impersonal: "Linear sync completed", "Context generated for CON-42" -- no actor names
- Actor info stored in DB but not displayed (available for future team features)

### Day grouping & time display
- Sticky date headers above each day group
- Day headers use section-label class (monospace, uppercase, tracking) -- "TODAY", "YESTERDAY", "MON, MAR 3"
- Smart label convention: "Today" / "Yesterday" for last 2 days, then "Weekday, Mon DD" for older
- Timestamps show relative ("2m ago", "1h ago") with absolute on hover tooltip ("3:42 PM, Mar 4")
- Timestamps in JetBrains Mono (DS-03)

### Empty & loading states
- Loading state: reuse existing skeleton layout from Phase 15 placeholder (day groups + event rows)
- No 30-day retention end marker -- timeline simply stops at oldest event

### Real-time behavior
- Subscribe to all INSERTs on activity_events for the user's workspace via Supabase Realtime
- All 6 event types stream in real-time (sync_started, sync_completed, context_generated, integration_connected, integration_disconnected, user_signed_up)
- New events prepend at top of current day group with CSS-only spring animation (Phase 15 curve)
- No auto-scroll -- if user is scrolled down, they stay in place
- Mandatory removeChannel cleanup on unmount (React Strict Mode double-invoke concern from STATE.md)

### Pagination
- Initial fetch: last 50 events
- "Show older events" button at bottom if more exist
- No infinite scroll

### Claude's Discretion
- Empty state design (follow FEED-06 pattern: "show what a populated feed looks like with one clear CTA")
- Event description copy for each of the 6 event types
- Exact Lucide icon mapping per event type
- Spring animation timing for new event insertion
- Whether "show more" loads 50 more or a different batch size
- Row hover state styling
- How metadata jsonb content is surfaced in descriptions (e.g., ticket count for sync_completed)

</decisions>

<specifics>
## Specific Ideas

- Timeline should "prove the system is working" -- seeing live events appear is the signal that integrations are active
- Compact rows keep it scannable like GitHub's activity feed
- Section-label uppercase day headers give it the dashboard's signature monospace treatment
- Hover-to-see-absolute-time is the best of both worlds -- at-a-glance relative + precise on demand

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `activity/page.tsx`: Existing skeleton placeholder -- reuse as loading state, replace with dynamic component
- `Skeleton` component (`components/ui/skeleton.tsx`): Shimmer-sweep animation ready for loading state
- `createClient()` (`lib/supabase/client.ts`): Browser Supabase client for real-time subscriptions
- `createClient()` (`lib/supabase/server.ts`): Server Supabase client for initial data fetch (SSR)
- CSS spring curve (`cubic-bezier(0.34, 1.56, 0.64, 1)`) from Phase 15 for new event animation
- `section-label` CSS class from Phase 15 for day group headers
- `font-mono` class (JetBrains Mono) for timestamps

### Established Patterns
- DarkModeApplier applies `.dark` to html -- timeline inherits dark tokens automatically
- Dashboard pages are server components that can fetch initial data; client components handle interactivity
- Existing stagger-children animation pattern for list item appearance
- Lucide icons already used in sidebar (LogOut, Settings) and auth layout

### Integration Points
- `activity_events` table (migration 00012): 6 event types, workspace_id scoped, jsonb metadata, RLS via workspace_members
- `/dashboard/activity/page.tsx`: Replace placeholder with real timeline component
- Sidebar nav already links to `/dashboard/activity` with "Activity" label and teal underline active state
- Supabase Realtime: subscribe to `public:activity_events` channel filtered by workspace_id

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 18-activity-timeline*
*Context gathered: 2026-03-04*
