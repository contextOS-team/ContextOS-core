# Architecture Research

**Domain:** Next.js App Router dashboard redesign — dark theme, onboarding, activity feed, team settings
**Researched:** 2026-03-04
**Confidence:** HIGH (based on direct codebase analysis + verified official documentation)

---

> **Scope note:** This document covers the NEW milestone only — guided onboarding, dark-themed dashboard, context feed with filtering, activity timeline, team settings, and auth page redesign. It treats the existing codebase as ground truth and explicitly identifies what changes vs. what stays.

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ROUTE LAYER (App Router)                            │
│                                                                              │
│  ┌──────────────┐  ┌───────────────────────────────────────────────────┐    │
│  │ (landing)/   │  │              (dashboard)/                          │    │
│  │ layout.tsx   │  │ layout.tsx  ← NEW: adds .dark class to wrapper    │    │
│  │ .landing-    │  │                                                    │    │
│  │  theme       │  │  /dashboard       /context   /integrations         │    │
│  │  (existing)  │  │  (redesigned)    /settings   /team (NEW)           │    │
│  └──────────────┘  │                                                    │    │
│                    └───────────────────────────────────────────────────┘    │
│  ┌──────────────────┐                                                        │
│  │  (auth)/         │  ← MODIFIED: add .dark wrapper like landing            │
│  │  layout.tsx      │                                                        │
│  │  (auth pages     │                                                        │
│  │   redesigned)    │                                                        │
│  └──────────────────┘                                                        │
│  ┌──────────────────┐                                                        │
│  │  (onboarding)/   │  ← NEW route group                                     │
│  │  layout.tsx      │    Auth-gated, redirects out when complete             │
│  │  page.tsx        │    Multi-step wizard (3 steps, no nested routes)        │
│  └──────────────────┘                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                       COMPONENT LAYER                                        │
│                                                                              │
│  NEW components (src/components/dashboard/):                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ┌───────────────────┐   │
│  │ContextFeed   │ │ActivityPanel │ │ FilterBar    │ │ OnboardingWizard  │   │
│  │ (list + RT)  │ │ (realtime)   │ │ (compound)   │ │ (step machine)    │   │
│  └──────┬───────┘ └──────┬───────┘ └─────────────┘ └───────────────────┘   │
│         │                │                                                   │
├─────────┼────────────────┼─────────────────────────────────────────────────┤
│         │          DATA LAYER                                                │
│         ▼                ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                  Supabase (existing + new tables)                    │   │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │   │
│  │  │ context_pages  │  │ activity_events   │  │ user_onboarding     │  │   │
│  │  │ (existing)     │  │ (NEW -- RT feed)  │  │ _state (NEW)        │  │   │
│  │  └────────────────┘  └──────────────────┘  └──────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Status | Responsibility | Changes From Existing |
|-----------|--------|---------------|----------------------|
| `(dashboard)/layout.tsx` | MODIFY | Auth gate + dark theme wrapper | Add `.dark` class to root div |
| `(dashboard)/sidebar.tsx` | MODIFY | Top nav with extended nav items | Add Team, Settings links; update active state logic |
| `(dashboard)/page.tsx` | MODIFY | Dashboard home — activity + context feed | Replace integration-status-only view |
| `(auth)/layout.tsx` | MODIFY | Auth pages wrapper | Add dark theme treatment |
| `(auth)/login/page.tsx` | MODIFY | Login UI | Dark card, brand-aligned visuals |
| `(auth)/signup/page.tsx` | MODIFY | Signup UI | Dark card, brand-aligned visuals |
| `(onboarding)/layout.tsx` | NEW | Onboarding shell — auth-gated, progress bar | — |
| `(onboarding)/page.tsx` | NEW | Multi-step onboarding wizard | — |
| `components/dashboard/ContextFeed` | NEW | Filtered list of context pages with real-time status | — |
| `components/dashboard/FilterBar` | NEW | Source type toggles for ContextFeed | — |
| `components/dashboard/ActivityPanel` | NEW | Real-time activity timeline | — |
| `components/dashboard/OnboardingWizard` | NEW | Step machine (3 steps) | — |
| `(dashboard)/settings/page.tsx` | NEW | API key management, user preferences | — |
| `(dashboard)/team/page.tsx` | NEW | Team member list and invite flow | — |
| `lib/hooks/use-realtime-feed.ts` | NEW | Supabase Realtime subscription hook | Extracted from component |
| `app/globals.css` | MODIFY | Dashboard dark tokens in `.dark {}` block (already present — verify completeness) | Token audit + dashboard-specific extensions |

---

## Question 1: Design Token Unification

**Decision: Two-layer token strategy — shared semantic names, different values per context.**

The existing codebase already implements the right pattern but it is incomplete:

- `globals.css` defines OKLCH tokens at `:root` (light) and `.dark` (dark) — HIGH confidence these are correct
- `landing.css` overrides the same semantic token names (e.g. `--background`, `--primary`) scoped under `.landing-theme`
- The dashboard currently uses `:root` tokens (light mode) without applying `.dark`

**The fix is a single class addition**, not a redesign:

```tsx
// apps/web/src/app/dashboard/layout.tsx — BEFORE
<div className="flex flex-col min-h-screen bg-background">

// AFTER — adds dark theme to all dashboard descendants
<div className="dark flex flex-col min-h-screen bg-background">
```

This works because `globals.css` already defines a `.dark {}` block with OKLCH dark palette values. The `@custom-variant dark (&:is(.dark *))` declaration in `globals.css` means Tailwind's `dark:` utilities activate for any descendant of `.dark`.

**Design token layers:**

| Layer | File | Scope | Mood |
|-------|------|-------|------|
| Base tokens | `globals.css` `@theme` block | All Tailwind utilities globally | — |
| Light (default) | `globals.css` `:root {}` | Dashboard default until `.dark` applied | Clean, neutral |
| Dark dashboard | `globals.css` `.dark {}` | Everything inside `<div class="dark">` | Deep blue-gray OKLCH |
| Landing dark | `landing.css` `.landing-theme {}` | Inside `<div class="landing-theme">` | Deep navy + teal brand |
| Auth pages | `globals.css` `.dark {}` | Via `.dark` wrapper in auth layout | Same as dashboard dark |

**Why this keeps them distinct despite sharing token names:**

- Landing uses `--primary: #00D4AA` (teal) and `--background: #0A0A0F` (deep navy)
- Dashboard dark uses `--primary: oklch(0.60 0.18 250)` (indigo-blue) and `--background: oklch(0.12 0.015 270)` (blue-gray)
- They never overlap because `.landing-theme` is never nested inside `.dark` and vice versa

**Token additions needed for dashboard dark theme:**

The existing `.dark` block in `globals.css` is already complete. What is missing is dashboard-specific semantic extensions for the activity feed and context cards:

```css
/* Add to globals.css inside .dark {} block */
.dark {
  /* existing tokens already present ... */

  /* Dashboard-specific extensions */
  --activity-insert: oklch(0.45 0.15 160);      /* green tint for new items */
  --activity-update: oklch(0.45 0.15 250);      /* blue tint for updates */
  --activity-delete: oklch(0.50 0.18 25);       /* red tint for deletes */
  --context-status-ready: oklch(0.55 0.14 160); /* green for ready status */
  --context-status-generating: oklch(0.60 0.15 85); /* amber for in-progress */
  --context-status-stale: oklch(0.55 0.14 60);  /* orange for stale */
}
```

---

## Question 2: Onboarding Route Structure

**Decision: New `(onboarding)` route group with step state managed in component, not URL.**

### Route placement

```
src/app/
├── (landing)/          — existing, public
├── (auth)/             — existing, unauthenticated only
│   ├── layout.tsx      — MODIFY: add dark wrapper
│   ├── login/page.tsx  — MODIFY: dark-themed card
│   └── signup/page.tsx — MODIFY: dark-themed card
├── (onboarding)/       — NEW route group
│   ├── layout.tsx      — auth-gate + progress wrapper
│   └── page.tsx        — wizard (single URL, steps managed in React state)
└── dashboard/          — existing, auth-gated
```

**Why single URL (`/onboarding`) rather than `/onboarding/1`, `/onboarding/2`, `/onboarding/3`:**

- Back-button behavior on sub-steps is confusing for 3-step flows
- Step state is transient; it does not need to be bookmarkable or shareable
- Single URL means no intermediate loading states during step transitions
- The wizard manages step index in `useState`, transitions with framer-motion or CSS `animate-fade-in-up`

### Onboarding trigger: middleware vs. layout check

**Decision: Layout-level redirect, not middleware.**

The middleware currently runs on every route to refresh Supabase sessions. Adding a database check (has user completed onboarding?) to every middleware call adds latency to all requests including static asset fetches.

Instead, the dashboard layout (already does a server-side auth check) adds a second check:

```typescript
// apps/web/src/app/dashboard/layout.tsx
export default async function DashboardLayout({ children }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) redirect('/login')

  // NEW: onboarding gate
  const { data: onboardingState } = await supabase
    .from('user_onboarding_state')
    .select('completed_at')
    .eq('user_id', user.id)
    .single()

  if (!onboardingState?.completed_at) {
    redirect('/onboarding')
  }

  return (
    <div className="dark flex flex-col min-h-screen bg-background">
      <Sidebar userEmail={user.email ?? ''} userFullName={user.user_metadata?.full_name} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-6 py-10 lg:px-10">{children}</div>
      </main>
    </div>
  )
}
```

The `(onboarding)/layout.tsx` does the inverse — if onboarding IS complete, redirect to dashboard:

```typescript
// apps/web/src/app/(onboarding)/layout.tsx
export default async function OnboardingLayout({ children }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) redirect('/login')

  const { data: state } = await supabase
    .from('user_onboarding_state')
    .select('completed_at')
    .eq('user_id', user.id)
    .single()

  if (state?.completed_at) redirect('/dashboard')

  return (
    <div className="dark min-h-screen bg-background flex flex-col">
      {children}
    </div>
  )
}
```

### Onboarding wizard steps

```
Step 1: Profile setup
  - Full name (pre-filled from auth metadata if present)
  - Role / team (optional)
  - Action: save to user_metadata on Supabase Auth user

Step 2: Connect your first integration
  - Show integration cards: Linear, Slack, GitHub, Notion (status from FastAPI)
  - Must connect at least one to proceed (OR skip button for manual dismissal)
  - Re-uses existing connectLinear() / connectSlack() from lib/api.ts

Step 3: Choose what to surface
  - Which source types to show in context feed by default
  - Saved to user_onboarding_state.preferences JSONB column
  - "Finish setup" button marks completed_at
```

### Database table for onboarding state

```sql
CREATE TABLE user_onboarding_state (
  user_id     UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  step_reached INT NOT NULL DEFAULT 1,
  preferences  JSONB,
  completed_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_onboarding_state ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users own their onboarding state"
  ON user_onboarding_state
  FOR ALL USING (auth.uid() = user_id);
```

Row creation: triggered automatically on first auth sign-in using a Supabase database trigger (same pattern as workspace auto-creation in Phase 1).

---

## Question 3: Real-time Activity Feed with Supabase

**Decision: Supabase Realtime `postgres_changes` subscription on `activity_events` table, scoped by `workspace_id`.**

### Database table

```sql
CREATE TABLE activity_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id      UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  event_type   TEXT NOT NULL,       -- 'context_page.created', 'integration.connected', etc.
  source_type  TEXT,                -- 'linear', 'slack', 'github', 'notion', 'system'
  entity_id    TEXT,                -- e.g. ticket identifier CON-16
  entity_title TEXT,
  metadata     JSONB,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX activity_events_workspace_created
  ON activity_events(workspace_id, created_at DESC);

ALTER TABLE activity_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "workspace members see events"
  ON activity_events FOR SELECT
  USING (workspace_id IN (
    SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
  ));
```

Realtime must be enabled for this table in the Supabase dashboard (or via `supabase_realtime` publication).

### React hook pattern

```typescript
// apps/web/src/lib/hooks/use-realtime-feed.ts
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export interface ActivityEvent {
  id: string
  event_type: string
  source_type: string | null
  entity_id: string | null
  entity_title: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export function useRealtimeFeed(workspaceId: string, limit = 50) {
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = createClient()

    // Initial load
    supabase
      .from('activity_events')
      .select('*')
      .eq('workspace_id', workspaceId)
      .order('created_at', { ascending: false })
      .limit(limit)
      .then(({ data }) => {
        if (data) setEvents(data)
        setLoading(false)
      })

    // Realtime subscription — INSERT only (events are append-only)
    const channel = supabase
      .channel(`activity-${workspaceId}`)
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'activity_events',
        filter: `workspace_id=eq.${workspaceId}`,
      }, (payload) => {
        setEvents((prev) => [payload.new as ActivityEvent, ...prev].slice(0, limit))
      })
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [workspaceId, limit])

  return { events, loading }
}
```

**Key constraints:**

- The `filter` parameter uses PostgREST filter syntax: `workspace_id=eq.${workspaceId}` (not SQL)
- Cleanup via `supabase.removeChannel(channel)` is mandatory — React Strict Mode double-invokes effects, so without cleanup you get duplicate subscriptions
- The Supabase `postgres_changes` feature requires the table to be in the `supabase_realtime` publication (check with `SELECT * FROM pg_publication_tables WHERE pubname = 'supabase_realtime'`)
- Subscribe to INSERT only (not `*`) — events never change after creation, so UPDATE/DELETE subscriptions are wasteful

### Activity event writers

The FastAPI backend writes to `activity_events` as a side effect of existing operations. This is purely additive — no existing API routes change:

```python
# Called after context_page status changes to 'ready'
async def emit_activity(supabase, workspace_id, event_type, source_type=None, entity_id=None, entity_title=None, metadata=None):
    await supabase.table("activity_events").insert({
        "workspace_id": workspace_id,
        "event_type": event_type,
        "source_type": source_type,
        "entity_id": entity_id,
        "entity_title": entity_title,
        "metadata": metadata or {},
    }).execute()

# Example call sites:
# - context_page generated: emit_activity(ws_id, "context_page.created", "linear", ticket_id, ticket_title)
# - integration connected: emit_activity(ws_id, "integration.connected", "slack")
# - new PR ingested: emit_activity(ws_id, "pr.ingested", "github", pr_number, pr_title)
```

---

## Question 4: Context Feed Component Architecture

**Decision: Compound-component pattern with shared state via React context. FilterBar owns filter state and passes it down through context. ContextFeed reads filter state and applies it client-side.**

### Component tree

```
<ContextFeedProvider>          ← React context: filter state + setter
  <FilterBar />                ← source type toggles, reads/writes context
  <ContextFeedList />          ← subscribes to context_pages RT, reads filter context
    <ContextFeedItem />        ← pure display, no state
    <ContextFeedItem />
    ...
  <EmptyState />               ← shown when filter produces no results
</ContextFeedProvider>
```

### FilterBar design

Source type filter is a multi-select toggle group (not a dropdown — toggles are faster to scan):

```typescript
// Filter state shape
type SourceFilter = {
  linear: boolean
  slack: boolean
  github: boolean
  notion: boolean
  all: boolean    // shorthand — true when all are selected
}

// Context shape
interface ContextFeedContextValue {
  filter: SourceFilter
  setFilter: (update: Partial<SourceFilter>) => void
  activeCount: number   // for "X results" label
}
```

**FilterBar renders as:**

```
[All]  [Linear]  [Slack]  [GitHub]  [Notion]    showing 12 results
```

Each pill is a toggle button using existing `Button` component with `variant="outline"` for inactive, `variant="default"` (primary) for active. No new component primitives needed.

### Context feed data flow

```typescript
// Context pages come from Supabase direct read + realtime
// (following existing split read/write pattern from ARCHITECTURE.md)

// apps/web/src/components/dashboard/ContextFeedList.tsx
'use client'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

function useContextPages(workspaceId: string) {
  const [pages, setPages] = useState([])

  useEffect(() => {
    const supabase = createClient()

    // Initial load
    supabase
      .from('context_pages')
      .select('id, ticket_identifier, title, status, sources, updated_at')
      .eq('workspace_id', workspaceId)
      .order('updated_at', { ascending: false })
      .limit(100)
      .then(({ data }) => { if (data) setPages(data) })

    // Realtime: watch for status changes (generating -> ready, etc.)
    const channel = supabase
      .channel(`context-pages-${workspaceId}`)
      .on('postgres_changes', {
        event: '*',                    // INSERT (new pages) and UPDATE (status changes)
        schema: 'public',
        table: 'context_pages',
        filter: `workspace_id=eq.${workspaceId}`,
      }, (payload) => {
        if (payload.eventType === 'INSERT') {
          setPages((prev) => [payload.new, ...prev])
        } else if (payload.eventType === 'UPDATE') {
          setPages((prev) => prev.map((p) => p.id === payload.new.id ? payload.new : p))
        }
      })
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [workspaceId])

  return pages
}
```

### Client-side filtering

Filtering is applied client-side (not a new Supabase query per filter change). Rationale: 100 context pages is manageable in memory, filter changes should be instant without network round-trips, and the realtime subscription stays live across filter state changes.

```typescript
// Filter application — pure function, called during render
function applyFilter(pages: ContextPage[], filter: SourceFilter): ContextPage[] {
  if (filter.all) return pages

  return pages.filter((page) => {
    // page.sources is ContextPageSource[] — check if any source matches active filters
    return page.sources.some((source) => {
      const sourceType = mapSourceToFilterKey(source.type)
      return filter[sourceType] === true
    })
  })
}

function mapSourceToFilterKey(sourceType: string): keyof SourceFilter {
  if (sourceType.startsWith('linear')) return 'linear'
  if (sourceType.startsWith('slack')) return 'slack'
  if (sourceType.startsWith('github')) return 'github'
  if (sourceType.startsWith('notion') || sourceType === 'notion_page') return 'notion'
  return 'linear' // default
}
```

---

## Recommended Project Structure (Changes Only)

```
apps/web/src/
├── app/
│   ├── (auth)/
│   │   ├── layout.tsx           MODIFY: add dark wrapper + visual redesign
│   │   ├── login/page.tsx       MODIFY: dark card, logo, updated copy
│   │   └── signup/page.tsx      MODIFY: dark card, logo, updated copy
│   │
│   ├── (onboarding)/            NEW route group
│   │   ├── layout.tsx           NEW: auth gate + inverse onboarding check
│   │   └── page.tsx             NEW: multi-step wizard
│   │
│   ├── dashboard/
│   │   ├── layout.tsx           MODIFY: add .dark class + onboarding gate
│   │   ├── page.tsx             MODIFY: home with ContextFeed + ActivityPanel
│   │   ├── sidebar.tsx          MODIFY: add Team, Settings nav items
│   │   ├── context/page.tsx     KEEP: existing lookup UI unchanged
│   │   ├── integrations/page.tsx KEEP: existing integrations UI unchanged
│   │   ├── settings/            NEW directory
│   │   │   └── page.tsx         NEW: API keys, user preferences
│   │   └── team/                NEW directory
│   │       └── page.tsx         NEW: team members, invite
│   │
│   └── globals.css              MODIFY: audit .dark block, add feed tokens
│
├── components/
│   ├── dashboard/               NEW directory
│   │   ├── ContextFeedProvider.tsx  compound component context
│   │   ├── ContextFeedList.tsx      list + RT subscription
│   │   ├── ContextFeedItem.tsx      card display
│   │   ├── FilterBar.tsx            source type toggles
│   │   ├── ActivityPanel.tsx        timeline with RT
│   │   ├── ActivityEventRow.tsx     single event display
│   │   ├── OnboardingWizard.tsx     step machine shell
│   │   ├── OnboardingStep.tsx       individual step wrapper
│   │   └── EmptyFeedState.tsx       zero-state display
│   │
│   └── ui/                      KEEP existing; add if needed:
│       └── badge.tsx            NEW if not present (for status pills)
│
└── lib/
    ├── hooks/                   NEW directory
    │   ├── use-realtime-feed.ts activity event RT subscription
    │   └── use-context-pages.ts context page RT subscription
    └── api.ts                   MODIFY: add team invite, onboarding endpoints
```

### Structure rationale

- **`components/dashboard/`**: All new dashboard components land here, not in `app/`. The App Router convention is to keep components that are not layouts/pages outside the `app/` tree. This keeps `app/` as route declarations only.
- **`lib/hooks/`**: Extracted hooks instead of inline `useEffect` in components. Each hook owns one subscription lifecycle. This prevents Strict Mode double-subscription bugs and makes testing straightforward.
- **`(onboarding)/` route group**: Parentheses prevent `/onboarding` from inheriting dashboard layout (which requires onboarding to be complete). Route groups in Next.js App Router do not affect the URL — the page is accessible at `/onboarding`.
- **No new shared UI primitives**: All new components compose existing `Button`, `Card`, `Input`, `Label` from `components/ui/`. Only add `Badge` if not already in shadcn install.

---

## Architectural Patterns

### Pattern 1: Theme Scope via Class Wrapper (not `html` element)

**What:** Apply dark theme to a layout wrapper div rather than the `<html>` element. Each layout independently controls its theme.

**When to use:** When different route groups need different themes in the same app. The root `<html>` in `app/layout.tsx` stays theme-neutral.

**Trade-offs:**
- Pro: Landing, auth, and dashboard can each have independent palettes with zero JavaScript
- Pro: No theme flash — the class is server-rendered in the layout's HTML
- Con: shadcn components that portal out of the DOM (tooltips, modals, comboboxes) may need special handling because portals render at `document.body`, outside the `.dark` wrapper

**Handling portalled components:**

The `@custom-variant dark (&:is(.dark *))` in `globals.css` (line 5) uses `:is()` which is a CSS selector, not a DOM ancestor check. This means it works for elements that are descendants in the DOM — portalled elements at `document.body` will NOT inherit dark theme. Fix:

```typescript
// For shadcn components with portal prop (Dialog, Popover, DropdownMenu):
// Pass the wrapper element as the portal container

// Option A: Apply .dark to body when dashboard is active
// (simplest — mutate document.body.classList in a client component useEffect)

// Option B: Pass portal container explicitly
<DropdownMenuContent
  className="..."
  // Radix UI portal can target a specific element
/>
```

Recommendation: Add `.dark` to `document.body` from a client component in the dashboard layout. This is a one-line fix that eliminates the portal problem entirely:

```typescript
// apps/web/src/components/dashboard/DarkModeApplier.tsx
'use client'
import { useEffect } from 'react'
export function DarkModeApplier() {
  useEffect(() => {
    document.documentElement.classList.add('dark')
    return () => document.documentElement.classList.remove('dark')
  }, [])
  return null
}
```

Include this in dashboard layout. It adds `.dark` to `<html>` only when inside a dashboard route, and removes it on navigation away.

### Pattern 2: Extract Supabase RT Hooks

**What:** Each realtime subscription lives in a dedicated `lib/hooks/` file, not inline in a component. The hook encapsulates initial load + subscription setup + cleanup.

**When to use:** Any time a component needs real-time data. Never write subscription `useEffect` directly in a page or compound component.

**Trade-offs:**
- Pro: Prevents accidental duplicate subscriptions (React Strict Mode fires effects twice in dev)
- Pro: Hook is independently testable with a mock Supabase client
- Pro: Multiple components can share the same hook without re-subscribing
- Con: One more file per data entity

**Example (already shown in Question 3 above — `use-realtime-feed.ts`)**

### Pattern 3: Onboarding as Server-Side Guard

**What:** Onboarding completion is checked in server components (layout.tsx files), not client-side. The check is a simple database row existence query, not middleware.

**When to use:** Post-auth redirects where the condition is user-specific database state.

**Trade-offs:**
- Pro: No client-side redirect flash — the server renders the correct page immediately
- Pro: Middleware stays lightweight (session refresh only, no DB calls)
- Con: Every dashboard route request includes an extra Supabase query (acceptable — it is a single indexed row lookup by PK)

### Pattern 4: Compound Component for Filtered Feed

**What:** `ContextFeedProvider` wraps the feed area with a React context that holds filter state. `FilterBar` reads and writes it. `ContextFeedList` reads it for filtering. Neither child needs prop drilling.

**When to use:** When sibling components need to share state without a global store or prop chains.

**Trade-offs:**
- Pro: Clean separation — filter UI and data display are decoupled
- Pro: FilterBar can be moved to a different DOM location without prop refactoring
- Con: Context re-renders all consumers on any filter change (acceptable given component count and size)

**Example structure:**

```typescript
// components/dashboard/ContextFeedProvider.tsx
'use client'
import { createContext, useContext, useState } from 'react'

const ContextFeedContext = createContext<ContextFeedContextValue | null>(null)

export function ContextFeedProvider({ children }: { children: React.ReactNode }) {
  const [filter, setFilterState] = useState<SourceFilter>({
    all: true, linear: true, slack: true, github: true, notion: true,
  })

  function setFilter(update: Partial<SourceFilter>) {
    setFilterState((prev) => ({ ...prev, ...update }))
  }

  return (
    <ContextFeedContext.Provider value={{ filter, setFilter }}>
      {children}
    </ContextFeedContext.Provider>
  )
}

export function useContextFeed() {
  const ctx = useContext(ContextFeedContext)
  if (!ctx) throw new Error('useContextFeed must be inside ContextFeedProvider')
  return ctx
}
```

---

## Data Flow

### Onboarding Completion Flow

```
New user signs up / first login
    │
    ▼
DB trigger creates user_onboarding_state row (step_reached=1, completed_at=NULL)
    │
    ▼
Dashboard layout.tsx (server) checks completed_at → NULL → redirect('/onboarding')
    │
    ▼
User completes 3 steps in OnboardingWizard
    │
    ├─ Step 1: PATCH /api/user/profile → updates auth.users metadata via Supabase Admin
    ├─ Step 2: Connect integration (re-uses existing lib/api.ts connect functions)
    └─ Step 3: Save preferences → PATCH user_onboarding_state set preferences=..., completed_at=now()
    │
    ▼
redirect('/dashboard') → layout check passes → dashboard renders
```

### Real-time Activity Feed Flow

```
Backend event occurs (context page ready, integration connected, etc.)
    │
    ▼
FastAPI route/task calls emit_activity() → INSERT into activity_events
    │
    ▼
Supabase Postgres → Realtime publication → WebSocket broadcast to subscribed clients
    │
    ▼
useRealtimeFeed hook receives INSERT payload
    │
    ▼
setEvents((prev) => [newEvent, ...prev].slice(0, 50))
    │
    ▼
ActivityPanel re-renders with new event at top
```

### Context Feed Filter Flow

```
User clicks [Slack] toggle in FilterBar
    │
    ▼
FilterBar calls setFilter({ slack: false, all: false })
    │
    ▼
ContextFeedContext value updates
    │
    ▼
ContextFeedList re-renders → applyFilter(pages, filter) runs client-side
    │
    ▼
Filtered list renders (no network request, instant)
```

### Auth Page Dark Theme Flow

```
User navigates to /login
    │
    ▼
(auth)/layout.tsx renders with .dark wrapper div
    │
    ▼
DarkModeApplier (client component) runs useEffect → adds .dark to <html>
    │
    ▼
All shadcn tokens (Card, Input, Button) resolve to .dark values
Landing CSS (.landing-theme) is NOT imported in auth layout → no teal bleed
```

---

## Integration Points: New vs. Existing

### What stays unchanged

| Existing Component | Reason Not Changed |
|-------------------|-------------------|
| `lib/supabase/client.ts` | Same browser client, no changes |
| `lib/supabase/server.ts` | Same server client, no changes |
| `lib/supabase/middleware.ts` | Session refresh only, onboarding check is in layouts not middleware |
| `lib/api.ts` | All existing functions kept. New team/onboarding endpoints appended. |
| `dashboard/integrations/` | All integration cards unchanged |
| `dashboard/context/page.tsx` | Ticket lookup page unchanged |
| `components/landing/` | Untouched |
| `landing.css` | Untouched |
| `(landing)/layout.tsx` | Untouched |

### New backend endpoints needed

These are small additions to the FastAPI backend:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/user/onboarding` | GET | Fetch user onboarding state |
| `/api/user/onboarding` | PATCH | Update step, preferences, mark complete |
| `/api/user/profile` | PATCH | Update full name (writes to Supabase Auth metadata) |
| `/api/team/members` | GET | List workspace members |
| `/api/team/invite` | POST | Send email invite (Supabase Auth invite) |
| `/api/apikeys` | GET/POST/DELETE | API key management (if not yet built) |

The `emit_activity()` helper is called internally — not a new public API endpoint.

### New Supabase tables

| Table | Purpose | RLS |
|-------|---------|-----|
| `user_onboarding_state` | Per-user onboarding progress | `auth.uid() = user_id` |
| `activity_events` | Append-only event log for RT feed | Workspace membership check |

Both tables need to be added to the Supabase Realtime publication if they require real-time (only `activity_events` does).

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 users | Current pattern handles this comfortably. Each user gets one WebSocket for activity feed + one for context pages. Total: 200 open connections at 100 users. Supabase Pro handles this. |
| 100-1000 users | Activity feed subscriptions start to cost. Evaluate moving high-volume event types (Slack message ingested, embedding generated) to server-side batching rather than per-event rows. Dashboard should only show user-facing events. |
| 1000+ users | Consider event aggregation (e.g., "5 new context pages ready" instead of 5 individual rows) to reduce WebSocket message volume. Partition `activity_events` by workspace for query performance. |

### Scaling priorities for this milestone

1. **RT connection count:** The `useRealtimeFeed` + `useContextPages` hooks each open a channel. A single user visiting the dashboard creates 2 WebSocket multiplexed channels on 1 connection (Supabase multiplexes channels over one WS). This is fine.
2. **`activity_events` table growth:** With high-activity workspaces, this table grows quickly. Add a 30-day retention policy from the start (pg_cron job or Supabase scheduled function).
3. **Onboarding redirect query:** 1 indexed PK lookup per dashboard page load. Negligible.

---

## Anti-Patterns

### Anti-Pattern 1: Applying `.dark` to `<html>` globally in root layout

**What people do:** Add `className="dark"` to the `<html>` tag in `app/layout.tsx` to enable dark mode everywhere.

**Why it is wrong:** This forces dark mode on the landing page too, overriding the `.landing-theme` variables and destroying the marketing page palette. The two dark themes (landing teal vs. dashboard blue-gray) must never coexist at the root level.

**Do this instead:** Apply `.dark` in each route group layout independently. Use `DarkModeApplier` client component to also apply it to `<html>` for portal support, mounted/unmounted per route.

### Anti-Pattern 2: Writing RT subscriptions inline in page components

**What people do:** Put the `useEffect` with `supabase.channel().on().subscribe()` directly inside `page.tsx` or a compound component.

**Why it is wrong:** React Strict Mode fires effects twice in development, creating duplicate subscriptions. The cleanup function is easy to forget. The subscription logic cannot be tested independently.

**Do this instead:** Extract to `lib/hooks/use-realtime-feed.ts`. The hook returns data and handles all lifecycle. Components only call the hook.

### Anti-Pattern 3: Putting onboarding check in middleware

**What people do:** Add a database query in `middleware.ts` to check `user_onboarding_state` on every request.

**Why it is wrong:** Middleware runs on EVERY request including `_next/static` (CSS, JS), `_next/image`, and API routes. Adding a DB call multiplies database load unnecessarily. Middleware is also an edge function — it cannot easily use the full server-side Supabase client that handles cookie-based session refresh.

**Do this instead:** Check in `dashboard/layout.tsx` (server component). Only dashboard page navigations trigger this check. Static assets are excluded by the middleware `matcher` config (already in place).

### Anti-Pattern 4: Fetching context pages on every filter change

**What people do:** Make a new Supabase query with a `WHERE source_type = ?` clause each time the user toggles a filter.

**Why it is wrong:** Filter changes should be instant (< 16ms). Network round-trips introduce 50-200ms latency per change. For a feed of 100 items, client-side filtering is fast and avoids query complexity.

**Do this instead:** Load up to 100 context pages once (with realtime subscription keeping it current), filter client-side using the `applyFilter()` pure function. Only paginate if the workspace has > 200 context pages.

### Anti-Pattern 5: Nesting `.landing-theme` and `.dark` tokens

**What people do:** Import `landing.css` in the dashboard layout "for consistency" or accidentally import `globals.css` from a landing component.

**Why it is wrong:** `.landing-theme` overrides `--primary` to teal `#00D4AA`. If `.landing-theme` and `.dark` are both ancestors, teal primary bleeds into dashboard components. Auth pages with teal buttons look wrong.

**Do this instead:** Never import `landing.css` in non-landing layouts. The `(landing)/layout.tsx` is the only file that imports it (`import '../landing.css'`). Keep it that way.

---

## Build Order (This Milestone)

Dependencies determine the order. Dark theme tokens must come before any visual component work.

```
Step 1: Token foundation (no dependencies)
├── Audit .dark block in globals.css — verify sidebar tokens are complete
├── Add DarkModeApplier client component
└── Apply .dark to dashboard/layout.tsx wrapper + verify all shadcn components render correctly

Step 2: Auth page redesign (depends on Step 1)
├── Modify (auth)/layout.tsx — add .dark wrapper + DarkModeApplier
├── Redesign login/page.tsx — dark card treatment
└── Redesign signup/page.tsx — dark card treatment

Step 3: Onboarding infrastructure (depends on Step 1)
├── Create user_onboarding_state table + RLS + trigger
├── Add onboarding gate to dashboard/layout.tsx
├── Create (onboarding)/layout.tsx with inverse gate
└── Add /api/user/onboarding endpoints to FastAPI

Step 4: Onboarding wizard (depends on Step 3)
├── OnboardingWizard.tsx (step shell + progress bar)
├── OnboardingStep.tsx (step 1 — profile)
├── OnboardingStep.tsx (step 2 — integrations, re-uses api.ts connect functions)
└── OnboardingStep.tsx (step 3 — preferences + complete)

Step 5: Activity feed infrastructure (depends on Step 1)
├── Create activity_events table + RLS + index + realtime publication
├── Implement emit_activity() in FastAPI backend
└── Wire emit_activity() to existing context_page generation + integration connect handlers

Step 6: Activity feed UI (depends on Step 5)
├── use-realtime-feed.ts hook
├── ActivityPanel.tsx + ActivityEventRow.tsx
└── Integrate ActivityPanel into dashboard/page.tsx

Step 7: Context feed (depends on Step 1 for dark theme)
├── ContextFeedProvider.tsx (context + state)
├── FilterBar.tsx (source type toggles)
├── use-context-pages.ts hook (RT subscription)
├── ContextFeedList.tsx + ContextFeedItem.tsx
└── Integrate ContextFeed into dashboard/page.tsx

Step 8: New pages (depends on Steps 1, 7)
├── dashboard/settings/page.tsx (API keys, preferences)
├── dashboard/team/page.tsx (members, invite)
└── Update sidebar.tsx to include Team + Settings nav items
```

**Critical path:** Step 1 (tokens) → Step 2 (auth) or Step 3 (onboarding) → Step 4 (wizard) → Steps 5-8 (feed features) can partially parallelize.

Steps 6 and 7 are independent once Step 5's infrastructure exists.

---

## Sources

- Supabase Realtime Postgres Changes (official docs, HIGH confidence): https://supabase.com/docs/guides/realtime/postgres-changes
- Supabase Realtime cleanup pattern (official docs): "ensure you free up resources" via `supabase.removeChannel(channel)`
- Tailwind v4 scoped theming pattern (Wawand.co, verified against official Tailwind docs, MEDIUM confidence): https://wawand.co/blog/posts/managing-multiple-portals-with-tailwind/
- shadcn/ui Tailwind v4 dark mode (official docs, HIGH confidence): https://ui.shadcn.com/docs/tailwind-v4
- Next.js Route Groups (official docs, HIGH confidence): https://nextjs.org/docs/app/api-reference/file-conventions/route-groups
- Compound Component Pattern (patterns.dev, HIGH confidence): https://www.patterns.dev/react/compound-pattern/
- Codebase analysis: direct inspection of `globals.css`, `landing.css`, `(landing)/layout.tsx`, `(auth)/layout.tsx`, `dashboard/layout.tsx`, `lib/supabase/client.ts`, `lib/supabase/server.ts`, `lib/api.ts`, `middleware.ts` (HIGH confidence — ground truth)

---

*Architecture research for: ContextOS dashboard dark theme, onboarding, activity feed milestone*
*Researched: 2026-03-04*
