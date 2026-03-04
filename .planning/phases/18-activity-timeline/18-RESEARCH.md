# Phase 18: Activity Timeline - Research

**Researched:** 2026-03-04
**Domain:** Supabase Realtime subscriptions, React client components, timeline UI patterns
**Confidence:** HIGH

## Summary

Phase 18 replaces the static skeleton placeholder at `/dashboard/activity` with a dynamic activity timeline that queries the existing `activity_events` table, groups events by day, renders compact rows with type-specific icons and relative timestamps, and subscribes to Supabase Realtime for live updates. The `activity_events` table already exists (migration 00012) with RLS policies, 6 event types, workspace-scoped data, and a composite index on `(workspace_id, created_at DESC)`.

This is the project's first Supabase Realtime implementation. The critical infrastructure requirement is adding `activity_events` to the `supabase_realtime` publication -- without this, Realtime postgres_changes will silently receive no events. The frontend architecture follows the established pattern: server component page fetches initial data, passes to a `'use client'` component that handles interactivity and Realtime subscription. React Strict Mode (default in Next.js 15) double-invokes effects, requiring careful channel cleanup.

**Primary recommendation:** Create a new migration to enable Realtime publication, build the timeline as a single client component with useEffect-managed Realtime subscription, and use the existing `formatRelativeTime` from `lib/utils.ts` extended with the phase-specific timestamp rules (absolute time after 24h, smart day labels).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Compact single-line rows, 40px height, 8px vertical gap between rows
- Layout left-to-right: [icon] [description] . [metadata chip] [timestamp]
- Lucide icons at 16px: RefreshCw, CheckCircle2, Sparkles, Plug, Unplug, UserPlus
- All icons in `text-muted-foreground` -- teal reserved for actionable elements only (DS-02)
- Impersonal descriptions (no actor names) with specific templates per event type
- Description text: Inter, `text-sm`, `text-foreground`
- Max 1 metadata chip per row: `text-xs`, `bg-muted`, rounded, JetBrains Mono
- Sticky date headers with `position: sticky; top: 0; z-10; bg-background`
- 1px `border-b border-border` only while stuck (IntersectionObserver toggle)
- Day headers use `section-label` class (monospace, uppercase, tracking)
- Smart label convention: TODAY / YESTERDAY / weekday name (7 days) / "FEB 24, 2026" (older)
- Timestamp format: "just now" / "{n}m ago" / "{n}h ago" / absolute "3:42 PM" (24h+)
- Hover tooltip: full date via native `title` attribute
- Timestamps in JetBrains Mono, `text-xs`, `text-muted-foreground`, right-aligned
- Single `setInterval` every 60s at timeline container level for relative time updates
- Loading: reuse shimmer skeleton (1 day header + 4 rows, 1 day header + 2 rows)
- Empty state: centered Clock icon (32px), "Activity" heading, subtext, "Connect an integration" link to `/dashboard/integrations`
- End-of-list terminator: centered "-- Showing last 30 days --" in `text-xs text-muted-foreground`
- Supabase Realtime: subscribe to all INSERTs on `activity_events` filtered by workspace_id
- Conditional insertion: at scroll top -> direct insert with animation; scrolled down -> "N new events" pill banner
- Banner style: `bg-muted/80 backdrop-blur-sm text-sm text-foreground rounded-full px-3 py-1.5`
- Entry animation: `translateY(-8px)` + `opacity: 0` -> `translateY(0)` + `opacity: 1`, 350ms spring curve
- No stagger for multiple simultaneous events -- all animate together
- Never auto-scroll -- respect user's scroll position
- Mandatory `removeChannel` cleanup on unmount (React Strict Mode double-invoke)
- Cursor-based infinite scroll, 30 events per page
- Cursor: `created_at` of oldest loaded event
- IntersectionObserver sentinel 200px from bottom triggers next page
- Loading during pagination: 2 shimmer skeleton rows at bottom
- Keep all loaded events in client state (max ~900 events over 30 days)

### Claude's Discretion
- Exact row hover state styling
- Whether sentinel uses a ref or a dedicated empty div
- How to extract integration name from metadata jsonb for description templates
- Error state if Realtime subscription fails
- Whether to debounce the scroll-position check for banner logic

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACT-01 | User sees a chronological feed of workspace events (syncs, context generated, integrations connected) | Existing `activity_events` table with 6 event types, RLS via workspace_members, composite index on (workspace_id, created_at DESC). Server component fetches initial page, client component renders timeline with cursor-based pagination. |
| ACT-02 | Events display with type-specific icons, relative timestamps, and day-group dividers | Lucide icons already installed (v0.469.0). Existing `formatRelativeTime` in utils.ts needs extension for 24h+ absolute time. `section-label` CSS class exists for day headers. IntersectionObserver for sticky header border toggle. |
| ACT-03 | Activity timeline updates in real-time via Supabase Realtime | supabase-js v2.97.0 supports postgres_changes. Requires new migration to add table to `supabase_realtime` publication. Filter by `workspace_id=eq.{id}`. useEffect cleanup via `removeChannel`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @supabase/supabase-js | 2.97.0 | Realtime subscription + data queries | Already installed, provides channel API for postgres_changes |
| @supabase/ssr | 0.6.1 | Server-side Supabase client | Already installed, used for initial SSR data fetch |
| lucide-react | 0.469.0 | Type-specific event icons | Already installed, used throughout dashboard |
| React 19 | 19.x | Client component with hooks | Already installed, useEffect for subscription lifecycle |
| Next.js 15 | 15.2.x | App Router server/client split | Already installed, page.tsx as server component |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Tailwind CSS 4 | 4.x | All styling | Already configured with dark mode tokens |
| tw-animate-css | 1.4.0 | Animation utilities | Already installed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw useEffect for Realtime | @tanstack/react-query | Explicitly out of scope per REQUIREMENTS.md -- premature before caching problems exist |
| CSS animations | Framer Motion | Phase 15 decided CSS-only spring curves (zero bundle cost) |
| Manual scroll detection | react-intersection-observer | Extra dependency for something achievable with native IntersectionObserver |

**Installation:**
No new packages needed. All dependencies are already installed.

## Architecture Patterns

### Recommended Project Structure
```
apps/web/src/
├── app/dashboard/activity/
│   ├── page.tsx                    # Server component: fetches initial events + workspace_id
│   └── activity-timeline.tsx       # Client component: renders timeline, manages Realtime
├── lib/
│   ├── supabase/client.ts          # Browser Supabase client (existing)
│   ├── supabase/server.ts          # Server Supabase client (existing)
│   └── utils.ts                    # Extended with timeline-specific formatters
└── supabase/migrations/
    └── 00013_realtime_activity.sql  # Enable Realtime publication
```

### Pattern 1: Server-Fetch + Client-Hydrate
**What:** Server component fetches initial data via server Supabase client, passes as props to client component that handles interactivity and Realtime.
**When to use:** Every dashboard page that needs both SSR and client-side interactivity.
**Example:**
```typescript
// page.tsx (server component)
import { createClient } from '@/lib/supabase/server'
import { ActivityTimeline } from './activity-timeline'

export default async function ActivityPage() {
  const supabase = await createClient()

  // Get user's workspace_id for Realtime filter
  const { data: { user } } = await supabase.auth.getUser()
  const { data: membership } = await supabase
    .from('workspace_members')
    .select('workspace_id')
    .eq('user_id', user!.id)
    .single()

  // Fetch initial page of events
  const { data: events } = await supabase
    .from('activity_events')
    .select('*')
    .eq('workspace_id', membership!.workspace_id)
    .order('created_at', { ascending: false })
    .limit(30)

  return (
    <ActivityTimeline
      initialEvents={events ?? []}
      workspaceId={membership!.workspace_id}
    />
  )
}
```

### Pattern 2: Supabase Realtime Subscription with React Cleanup
**What:** useEffect creates a Realtime channel, subscribes to postgres_changes INSERT events, and returns a cleanup that calls removeChannel.
**When to use:** Any component that needs live database updates.
**Example:**
```typescript
// Source: Supabase official docs + React patterns
'use client'

import { useEffect, useRef } from 'react'
import { createClient } from '@/lib/supabase/client'

function useActivityRealtime(workspaceId: string, onNewEvent: (event: ActivityEvent) => void) {
  const supabase = createClient()

  useEffect(() => {
    const channel = supabase
      .channel('activity-events')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'activity_events',
          filter: `workspace_id=eq.${workspaceId}`,
        },
        (payload) => {
          onNewEvent(payload.new as ActivityEvent)
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [workspaceId]) // eslint-disable-line react-hooks/exhaustive-deps
  // onNewEvent excluded from deps -- use ref pattern if needed
}
```

### Pattern 3: IntersectionObserver for Sticky Header State Detection
**What:** Use a 1px sentinel element above each sticky header. When the sentinel scrolls out of view, the header is "stuck" and gets a border-bottom.
**When to use:** Sticky headers that need visual differentiation when stuck.
**Example:**
```typescript
// Source: Chrome DevRel blog on sticky headers
// Set sticky header top to 0, sentinel has negative top margin to trigger before header sticks.
// When sentinel intersectionRatio < 1, header is stuck.

useEffect(() => {
  const sentinels = containerRef.current?.querySelectorAll('.day-sentinel')
  if (!sentinels) return

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const header = entry.target.nextElementSibling as HTMLElement
        if (header) {
          header.classList.toggle('border-b', !entry.isIntersecting)
        }
      })
    },
    { threshold: [0] }
  )

  sentinels.forEach((el) => observer.observe(el))
  return () => observer.disconnect()
}, [events]) // Re-observe when day groups change
```

### Pattern 4: Cursor-Based Pagination with IntersectionObserver
**What:** Sentinel element near bottom of list triggers fetch of next page using `created_at` of oldest event as cursor.
**When to use:** Infinite scroll lists.
**Example:**
```typescript
// Sentinel div observed for intersection
const sentinelRef = useRef<HTMLDivElement>(null)

useEffect(() => {
  if (!sentinelRef.current || !hasMore) return

  const observer = new IntersectionObserver(
    ([entry]) => {
      if (entry.isIntersecting && !isLoadingMore) {
        loadNextPage()
      }
    },
    { rootMargin: '200px' }
  )

  observer.observe(sentinelRef.current)
  return () => observer.disconnect()
}, [hasMore, isLoadingMore])
```

### Anti-Patterns to Avoid
- **Per-row timers for relative timestamps:** Timer proliferation kills performance. Use a single `setInterval` at the container level that triggers a state update to re-render all timestamps.
- **Supabase channel without cleanup:** Leaks WebSocket connections. Always `removeChannel` in useEffect cleanup. React Strict Mode will double-invoke effects in development, so cleanup must be idempotent.
- **Auto-scrolling on new events:** Disrupts user reading. Buffer new events when user is scrolled down, show a "N new events" pill.
- **Using `supabase.channel()` inside render:** Creates a new channel every render. Create inside useEffect only.
- **Filtering Realtime DELETE events:** Supabase Realtime cannot filter DELETE events with column filters. Not relevant here (we only subscribe to INSERTs) but important to know.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relative time formatting | Custom date diff logic | Extend existing `formatRelativeTime` in `lib/utils.ts` | Already handles just now/m/h/d, just add 24h+ absolute time branch |
| Shimmer loading skeletons | Custom animation CSS | Existing `Skeleton` component + `skeleton-shimmer` class | Already established in Phase 15 with the exact shimmer sweep |
| Day group header styling | Custom CSS classes | Existing `section-label` class from Phase 15 | Monospace uppercase tracking already defined in globals.css |
| Spring entry animations | Framer Motion or JS animation | CSS `cubic-bezier(0.34, 1.56, 0.64, 1)` | Already defined and used throughout dashboard (Phase 15 decision) |
| Dark mode token inheritance | Manual color management | Existing OKLCH tokens via `.dark` class + DarkModeApplier | 4-level surface hierarchy already set up |

**Key insight:** Phase 15 and 16 established all the design tokens, animation curves, and component primitives this phase needs. The timeline is pure composition of existing patterns plus Supabase Realtime, which is new to the codebase.

## Common Pitfalls

### Pitfall 1: Missing Realtime Publication
**What goes wrong:** Subscribe to postgres_changes but receive no events. No error message -- just silence.
**Why it happens:** Supabase Realtime requires tables to be added to the `supabase_realtime` publication. Without it, changes are not captured by the logical replication stream.
**How to avoid:** Create migration 00013 with `ALTER PUBLICATION supabase_realtime ADD TABLE public.activity_events;`. For hosted Supabase, this can also be toggled in the dashboard UI.
**Warning signs:** Subscription status shows `SUBSCRIBED` but no events arrive despite database inserts.

### Pitfall 2: React Strict Mode Double-Invoke
**What goes wrong:** In development, useEffect runs twice due to React 18+ Strict Mode (default in Next.js 15). This creates two channels, and the first cleanup removes a channel that may interfere with the second.
**Why it happens:** React intentionally double-invokes effects in development to surface cleanup bugs.
**How to avoid:** Ensure `removeChannel` is called in the cleanup function. The Supabase client handles this gracefully -- removing a channel that's already been removed is a no-op. The pattern `return () => { supabase.removeChannel(channel) }` handles this correctly.
**Warning signs:** Duplicate events appearing in development, or events stopping after initial subscription.

### Pitfall 3: Stale Closure in Realtime Callback
**What goes wrong:** The Realtime callback captures stale state values (e.g., stale `events` array), leading to incorrect insertion logic or lost events.
**Why it happens:** The callback is created once when useEffect runs. If it closes over state variables, it sees the values from that render.
**How to avoid:** Use `useRef` for values the callback needs to read (like current scroll position, current events array), or use functional state updates (`setEvents(prev => [newEvent, ...prev])`).
**Warning signs:** New events overwrite existing ones, or scroll position detection is always wrong.

### Pitfall 4: Workspace ID Not Available at Render
**What goes wrong:** Client component tries to subscribe to Realtime before workspace_id is available, resulting in a filter like `workspace_id=eq.undefined`.
**Why it happens:** If workspace_id is fetched client-side asynchronously, the first render won't have it.
**How to avoid:** Fetch workspace_id in the server component (page.tsx) and pass as a prop. The server already authenticates the user in the dashboard layout, so querying `workspace_members` is straightforward.
**Warning signs:** Realtime subscription receives events from all workspaces (if RLS is misconfigured) or no events at all.

### Pitfall 5: Memory Leak from setInterval
**What goes wrong:** Timestamp update interval keeps running after component unmounts.
**Why it happens:** setInterval not cleared in useEffect cleanup.
**How to avoid:** Store interval ID and clear in cleanup: `return () => clearInterval(intervalId)`.
**Warning signs:** Console warnings about setting state on unmounted components.

### Pitfall 6: IntersectionObserver Referencing Stale DOM
**What goes wrong:** Observer targets elements that have been removed from DOM (e.g., day group sentinels after new events arrive and day groups re-render).
**Why it happens:** Observer isn't disconnected and re-created when the observed elements change.
**How to avoid:** Disconnect and re-observe whenever the events array changes (use events.length or a derived day-groups key as useEffect dependency). Or use a single container-level observer pattern.
**Warning signs:** Border-bottom on sticky headers stops toggling, or pagination sentinel stops firing.

## Code Examples

### Activity Event Type Definition
```typescript
// Matches activity_events table schema from migration 00012
interface ActivityEvent {
  id: string
  workspace_id: string
  actor_id: string | null
  event_type: 'sync_started' | 'sync_completed' | 'context_generated'
    | 'integration_connected' | 'integration_disconnected' | 'user_signed_up'
  metadata: Record<string, unknown>
  created_at: string
}
```

### Event Description Formatter
```typescript
// Extract description from event type + metadata
function formatEventDescription(event: ActivityEvent): string {
  const meta = event.metadata
  switch (event.event_type) {
    case 'sync_started':
      return `${meta.integration ?? 'Unknown'} sync started`
    case 'sync_completed':
      return `${meta.integration ?? 'Unknown'} sync completed`
    case 'context_generated':
      return `Context generated from ${meta.source_count ?? '?'} sources`
    case 'integration_connected':
      return `${meta.integration ?? 'Unknown'} connected`
    case 'integration_disconnected':
      return `${meta.integration ?? 'Unknown'} disconnected`
    case 'user_signed_up':
      return 'Workspace created'
    default:
      return 'Unknown event'
  }
}
```

### Event Metadata Chip
```typescript
// Extract chip content from event metadata
function getMetadataChip(event: ActivityEvent): string | null {
  const meta = event.metadata
  switch (event.event_type) {
    case 'sync_completed':
      if (typeof meta.items_count === 'number') return `${meta.items_count} items`
      if (typeof meta.duration_ms === 'number') return `${(meta.duration_ms / 1000).toFixed(1)}s`
      return null
    case 'context_generated':
      if (typeof meta.token_count === 'number') {
        return meta.token_count >= 1000
          ? `${(meta.token_count / 1000).toFixed(1)}k tokens`
          : `${meta.token_count} tokens`
      }
      return null
    default:
      return null
  }
}
```

### Timeline Timestamp Formatter (Extended)
```typescript
// Extended from existing formatRelativeTime in lib/utils.ts
// Adds: absolute time after 24h, full tooltip format
function formatTimelineTimestamp(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  if (diffMs < 0) return 'just now'

  const diffMin = Math.floor(diffMs / 60_000)
  const diffHours = Math.floor(diffMin / 60)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHours < 24) return `${diffHours}h ago`

  // 24h+: absolute time (day header provides date context)
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

function formatFullTimestamp(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }) + ' at ' + date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}
```

### Day Group Label Formatter
```typescript
function formatDayLabel(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86_400_000)

  if (diffDays === 0) return 'TODAY'
  if (diffDays === 1) return 'YESTERDAY'
  if (diffDays < 7) {
    return target.toLocaleDateString('en-US', { weekday: 'long' }).toUpperCase()
  }
  // Older: "FEB 24, 2026"
  return target.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).toUpperCase()
}
```

### Realtime Publication Migration
```sql
-- 00013_realtime_activity.sql
-- Enable Realtime postgres_changes for activity_events table.
-- Without this, Realtime subscriptions receive no events.
ALTER PUBLICATION supabase_realtime ADD TABLE public.activity_events;
```

### Icon Map
```typescript
import {
  RefreshCw,
  CheckCircle2,
  Sparkles,
  Plug,
  Unplug,
  UserPlus,
  type LucideIcon,
} from 'lucide-react'

const EVENT_ICONS: Record<ActivityEvent['event_type'], LucideIcon> = {
  sync_started: RefreshCw,
  sync_completed: CheckCircle2,
  context_generated: Sparkles,
  integration_connected: Plug,
  integration_disconnected: Unplug,
  user_signed_up: UserPlus,
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Supabase Realtime v1 (`.from().on()`) | v2 channel API (`.channel().on('postgres_changes', ...)`) | supabase-js v2.0 (2022) | Must use channel API, not legacy `.from()` pattern |
| `channel.unsubscribe()` | `supabase.removeChannel(channel)` | supabase-js v2.x | `removeChannel` is the recommended cleanup method |
| Manual RLS checking in Realtime callbacks | Automatic RLS enforcement on postgres_changes | Supabase Realtime update | RLS policies on `activity_events` automatically filter events per user |
| `animate-pulse` for loading | `skeleton-shimmer` CSS class | Phase 15 | Project uses custom shimmer sweep, not Tailwind's pulse |

**Deprecated/outdated:**
- `supabase.from('table').on('INSERT', callback).subscribe()` -- this is the v1 API, removed in v2
- `channel.unsubscribe()` -- use `supabase.removeChannel(channel)` instead for full cleanup

## Open Questions

1. **Metadata JSONB shape for each event type**
   - What we know: The `metadata` column is `jsonb DEFAULT '{}'`. Event descriptions reference `integration`, `source_count`, `items_count`, `duration_ms`, `token_count`.
   - What's unclear: The exact keys stored by the backend sync engine for each event type. The backend writes these events, so the frontend must handle whatever shape exists.
   - Recommendation: Use defensive access (`meta.integration ?? 'Unknown'`) with fallbacks for every metadata field. The description templates from CONTEXT.md are clear enough to implement safely.

2. **Scroll container for IntersectionObserver root**
   - What we know: The dashboard layout has `<main className="flex-1 overflow-y-auto">` as the scroll container.
   - What's unclear: Whether IntersectionObserver for sticky headers and pagination sentinel should use `main` as root or default to viewport.
   - Recommendation: Use default viewport (root: null). The `main` element's `overflow-y-auto` makes it the effective scroll container, and viewport intersection works correctly for elements inside scrollable containers that fill the viewport.

## Sources

### Primary (HIGH confidence)
- [Supabase Realtime Postgres Changes docs](https://supabase.com/docs/guides/realtime/postgres-changes) - Channel subscription API, filter syntax, publication requirement
- [Supabase Realtime Authorization docs](https://supabase.com/docs/guides/realtime/authorization) - RLS enforcement on postgres_changes, JWT authentication
- [Supabase JavaScript subscribe reference](https://supabase.com/docs/reference/javascript/subscribe) - subscribe/removeChannel API
- [Chrome DevRel: sticky headers with IntersectionObserver](https://developer.chrome.com/blog/sticky-headers/) - Sentinel-based stuck detection pattern
- Project codebase: migration 00012, activity/page.tsx, sidebar.tsx, globals.css, lib/utils.ts, lib/supabase/client.ts

### Secondary (MEDIUM confidence)
- [Supabase GitHub Discussion #8573](https://github.com/orgs/supabase/discussions/8573) - React Strict Mode double-invoke with Realtime
- [Supabase realtime-js Issue #169](https://github.com/supabase/realtime-js/issues/169) - Strict mode subscription behavior

### Tertiary (LOW confidence)
- None -- all findings verified with official docs and project source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed, versions verified from package.json and node_modules
- Architecture: HIGH - follows exact patterns established in Phase 15/16, server/client split documented in existing code
- Pitfalls: HIGH - Realtime publication requirement verified via official docs, Strict Mode behavior confirmed by project config (Next.js 15 default) and community reports
- Code examples: MEDIUM-HIGH - TypeScript patterns derived from official API docs and project conventions, metadata JSONB shape assumed from CONTEXT.md descriptions

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (30 days -- stable stack, no fast-moving dependencies)
