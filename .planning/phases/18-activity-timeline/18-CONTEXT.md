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
- Compact single-line rows, 40px height, 8px vertical gap between rows
- Layout left-to-right: [icon] [description] · [metadata chip] [timestamp]
- Middle dot separator between description and metadata chip
- Lucide icons at 16px, one per event type:
  - `sync_started` → RefreshCw
  - `sync_completed` → CheckCircle2
  - `context_generated` → Sparkles
  - `integration_connected` → Plug
  - `integration_disconnected` → Unplug
  - `user_signed_up` → UserPlus
- All icons render in `text-muted-foreground` — teal reserved for actionable elements only (DS-02)
- Impersonal descriptions — no actor names:
  - `sync_started` → "{integration} sync started"
  - `sync_completed` → "{integration} sync completed"
  - `context_generated` → "Context generated from {source_count} sources"
  - `integration_connected` → "{integration} connected"
  - `integration_disconnected` → "{integration} disconnected"
  - `user_signed_up` → "Workspace created"
- Description text: Inter, `text-sm`, `text-foreground`
- Max 1 metadata chip per row — `text-xs`, `bg-muted`, rounded, JetBrains Mono (data identifiers):
  - `sync_completed` → items count ("42 items") or duration ("1.2s"), prioritize items count
  - `context_generated` → token count ("3.2k tokens") if present
  - Other types: no chip

### Day grouping & time display
- Sticky date headers (`position: sticky; top: 0; z-10; bg-background`)
- Add 1px `border-b border-border` only while stuck (IntersectionObserver toggle)
- Day headers use `section-label` class (monospace, uppercase, tracking)
- No horizontal rule — whitespace creates separation (24px top margin, 12px bottom margin)
- Smart label convention:
  - Today → "TODAY"
  - Yesterday → "YESTERDAY"
  - Within last 7 days → weekday name ("MONDAY", "TUESDAY")
  - Older → "FEB 24, 2026" (short month, no leading zero, full year)
- Timestamps:
  - Under 1 minute: "just now"
  - 1-59 minutes: "{n}m ago"
  - 1-23 hours: "{n}h ago"
  - 24+ hours: absolute time "3:42 PM" (day header provides date context)
  - Hover tooltip always shows full: "Feb 28, 2026 at 3:42 PM" (native `title` attribute)
- Timestamps in JetBrains Mono, `text-xs`, `text-muted-foreground`, right-aligned
- Single `setInterval` every 60s at timeline container level for relative time updates — no per-row timers

### Empty & loading states
- Loading: reuse existing shimmer skeleton from Phase 15 placeholder (1 day header + 4 rows, 1 day header + 2 rows)
- Empty state (zero events):
  - Center-aligned, Clock icon (32px, `text-muted-foreground`)
  - Heading: "Activity" in `text-lg font-medium text-foreground`
  - Subtext: "Events will appear here as you connect integrations and sync your data." — `text-sm text-muted-foreground`, max-width 320px
  - CTA: text link "Connect an integration" with `text-muted-foreground` + underline on hover, links to `/dashboard/integrations` — not teal, just a navigational nudge
- End-of-list terminator: centered "— Showing last 30 days —" in `text-xs text-muted-foreground` after oldest event

### Real-time behavior
- Subscribe to all INSERTs on `activity_events` filtered by workspace_id via Supabase Realtime
- All 6 event types stream live
- Conditional insertion based on scroll position:
  - User at scroll top (position = 0): new events insert directly at top of "Today" group with entry animation
  - User scrolled down (position > 0): sticky pill banner "↑ N new events" at top of timeline area, clicking smooth-scrolls to top and inserts buffered events
- Banner style: `bg-muted/80 backdrop-blur-sm text-sm text-foreground rounded-full px-3 py-1.5`, enters with `translateY(-8px)` → `translateY(0)`, 200ms ease-out
- Entry animation for new events: `translateY(-8px)` + `opacity: 0` → `translateY(0)` + `opacity: 1`, 350ms with project spring curve `cubic-bezier(0.34, 1.56, 0.64, 1)`
- No stagger for multiple simultaneous events — all animate together
- Never auto-scroll — respect user's scroll position
- Mandatory `removeChannel` cleanup on unmount (React Strict Mode double-invoke)

### Pagination
- Cursor-based infinite scroll, 30 events per page
- Cursor: `created_at` of oldest loaded event
- IntersectionObserver on sentinel element 200px from bottom triggers next page
- Loading indicator during pagination: 2 shimmer skeleton rows at bottom
- Keep all loaded events in client state — no discarding (max ~900 events over 30 days is trivial in memory)

### Claude's Discretion
- Exact row hover state styling
- Whether sentinel uses a ref or a dedicated empty div
- How to extract integration name from metadata jsonb for description templates
- Error state if Realtime subscription fails
- Whether to debounce the scroll-position check for banner logic

</decisions>

<specifics>
## Specific Ideas

- Timeline should "prove the system is working" — seeing live events appear is the signal that integrations are active
- Conditional real-time insertion (direct vs banner) prevents content-shift disruption when reading
- Middle-dot separator between description and chip is the Linear/Vercel pattern — reads clean without visual weight
- Single setInterval for all timestamps avoids timer proliferation
- Sticky day headers with IntersectionObserver-toggled border is a premium detail

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `activity/page.tsx`: Existing skeleton placeholder — reuse as loading state, replace with dynamic component
- `Skeleton` component (`components/ui/skeleton.tsx`): Shimmer-sweep animation for loading states
- `createClient()` (`lib/supabase/client.ts`): Browser Supabase client for Realtime subscriptions
- `createClient()` (`lib/supabase/server.ts`): Server Supabase client for initial SSR data fetch
- CSS spring curve `cubic-bezier(0.34, 1.56, 0.64, 1)` from Phase 15
- `section-label` CSS class from Phase 15 for day group headers
- `font-mono` class (JetBrains Mono) for timestamps and metadata chips
- Lucide icons already used in sidebar (LogOut, Settings) and auth layout

### Established Patterns
- DarkModeApplier applies `.dark` to html — timeline inherits dark tokens automatically
- Dashboard pages are server components; client components handle interactivity
- Existing stagger-children animation pattern for list item appearance
- shadcn components (Button, Card) inherit dark tokens

### Integration Points
- `activity_events` table (migration 00012): 6 event types, workspace_id scoped, jsonb metadata, RLS via workspace_members
- `/dashboard/activity/page.tsx`: Replace placeholder with real timeline component
- Sidebar nav already links to `/dashboard/activity` with "Activity" label and teal underline active state
- Supabase Realtime: subscribe to `public:activity_events` channel filtered by workspace_id

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-activity-timeline*
*Context gathered: 2026-03-04*
