# Phase 41: Dashboard Pulse Redesign — Research

**Researched:** 2026-05-20
**Domain:** Next.js 15 + React 19 + Tailwind v4 + Supabase frontend; editorial typography; per-user state; rules-based copy generation
**Confidence:** HIGH

## Summary

The redesign is feasible inside the existing stack with three localized additions: (1) two new Google Fonts (Instrument Serif + Geist Sans + Geist Mono) wired through `next/font/google`, (2) a warm-dark palette branch in `globals.css` (existing palette is cool `oklch(0.13 0.015 270)`), and (3) one new `dashboard_user_state` table for `last_visited_at` (no equivalent exists today).

The data layer is in great shape. Phase 32 already emits all integration sync events into `activity_events` with `created_at`, so "items since timestamp X" is a single Supabase `.gt('created_at', lastVisitedAt)` query — no backend work needed for the headline generator. Decision nodes already carry a `source_quote` property (the literal decision-causing utterance, stored by `persist_decision()` in `llm_extractor.py`), and the existing `/api/graph/lens/my-work` response flows `properties` through verbatim. **Provenance quotes can ship in this phase** without a backend backfill. Attribution-person lookup is one hop through the `authored_by` edge already created by `persist_decision`.

Three friction points to plan around: (a) the lens API does not currently surface graph-node `created_at`, so for the "new since last visit" marker we drive off `activity_events.created_at` (canonical) rather than per-node timestamps; (b) `last_sync_at` lives on per-provider integration configs (Notion/Jira/Linear only) — the chrome cluster's "last synced 4m ago" should derive from `MAX(activity_events.created_at) WHERE event_type IN ('sync_completed', 'sync_started')` for a unified value; (c) `hanging-punctuation: last` is Safari-only as of 2026-05, but the design explicitly accepts silent degradation.

**Primary recommendation:** Single phase, three sequential plans. Plan 41-01 = data + state foundation (fonts, palette, `dashboard_user_state` table, `useLastVisitedAt` hook with 5-min-inactivity hysteresis, headline rules-engine). Plan 41-02 = layout reshape (delete six widgets, add headline + recent-decisions card + active-context list + needs-you, sentence-case section labels, new-item markers). Plan 41-03 = chrome cluster (sync indicator three states, integration drawer, avatar puck, focus-ring system, `prefers-reduced-motion` global).

<user_constraints>
## User Constraints (from CONTEXT.md)

CONTEXT.md is the output of a four-pass design critique (`redesign-existing-projects` → `interface-craft` → `minimalist-ui` → `emil-design-eng`) and is locked. The document does not use the `## Decisions` / `## Claude's Discretion` / `## Deferred Ideas` section structure — the entire 18-section document IS the locked decision set. Below is the equivalent extraction.

### Locked Decisions (must implement as specified)

**Page structure (CONTEXT §2):**
- Top-to-bottom order: Chrome → Headline → Recent decisions (lead, 2-3× weight, 2 visible above fold + "view all") → Active context (top 3, tighter rows + "view all") → Needs you (compact, hidden when empty) → (future) Direction summary slot
- Removed from home: Recent Activity (moves to `/activity`), My Work graph thumbnail (lives in `/graph`), This Week sparkline (deleted), "Good evening, Daulet" greeting (replaced by computed headline)

**Headline (CONTEXT §4):**
- Family: Instrument Serif (preferred) or Newsreader. Italic optional, regular weight (400)
- Size: 36-48px (`text-4xl` to `text-5xl`)
- Tracking: `letter-spacing: -0.02em` to `-0.03em`; line-height: 1.1
- Measure: `max-w-3xl` (~672px), left-aligned, never centered
- Color: `#ece9e3` (warm off-white)
- `font-feature-settings: "kern" 1, "liga" 1; font-variation-settings: "opsz" 32`
- Punctuation: full color, full weight, NO soft-opacity period
- `hanging-punctuation: last;` — accepts Safari-only degradation
- Subtext template: `"(N) more decision(s) and (M) new source(s) since you last looked, (T) ago."`
- Zero-new fallback: `"Quiet day."` headline + `"Nothing new since you last looked, (T) ago."` subtext
- Rules-based template engine for this phase (LLM-generated deferred)

**Typography system (CONTEXT §5):**
- Body/UI: Geist Sans with `font-feature-settings: "ss01" 1, "cv11" 1`
- Inline numbers: Geist Sans with `"tnum" 1` (NOT mono inline with words)
- Identifiers (RD-973, ##channel): Geist Mono at 0.92em, `letter-spacing: -0.01em`, `"tnum" 1, "zero" 1`
- `<kbd>`: Geist Mono with `border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04)`
- Section labels: sentence case ("Recent decisions"), NOT all-caps
- Tags/chips: lowercase, never uppercase-tracked
- Cyrillic-Latin: Geist Cyrillic is acceptable; bracketed prefixes in tertiary color `#a8a59f`

**Color palette (CONTEXT §6):**
- Page background: `#0f0e0d` (warm dark) — REPLACES current `oklch(0.13 0.015 270)` (cool)
- Card surface: `#13110f` (one step warmer-brighter)
- Primary text: `#ece9e3`; secondary: `#a8a59f`; tertiary: `#6e6b66`
- Mint (current `oklch(0.75 0.18 170)`): reserved for brand ONLY — wordmark + active nav state
- Dim amber `#c4a050`: needs-attention semantics, new-item marker, sync error
- Dim red `#b06863`: stale/blocked (rare)
- Dim green `#6d8c6d`: fresh/synced (rare)
- NO shadows anywhere. NO gradients. NO ambient blobs. NO background imagery.
- One color = one job rule

**Cards (CONTEXT §7):**
- Cards exist ONLY for individual items, never section wrappers
- No border by default; defined by `background: rgba(255,255,255,0.025)`
- Border-radius: 8-12px; padding: 24px (`p-6`)
- Hover: `background: rgba(255,255,255,0.04)`, transition `background-color 160ms ease`
- Active: `transform: scale(0.997)` 100ms ease-out
- Title underlines on hover: `text-decoration: 1px solid rgba(232,230,225,0.5); text-underline-offset: 0.2em`
- Spacing: ~96px between sections (`py-24`), ~24px between rows

**Chrome cluster (CONTEXT §8):**
- Sync indicator + last-updated + integration health + avatar = ONE unit (top-right)
- Idle state: `last synced 4m ago` in Geist Sans 12px, weight 450, `#6e6b66`, tnum. No icon, no dot. Once-per-minute 240ms opacity dip 1.0→0.6→1.0
- Syncing state: `syncing slack · 35%` text crossfade, color `#a8a59f`, 1px progress bar beneath full chrome width, real-tick width (NO CSS interpolation), source-change crossfade with `filter: blur(2px) 180ms`
- Error state: `slack sync paused · reconnect` in `#c4a050`, "reconnect" inline + underline-on-hover, click opens slide-over
- Manual "Sync now" tucked inside drawer (NOT a hero button)
- Avatar: initials puck, hover `scale(1.04) 120ms`, active `scale(0.96) 100ms`, tooltip after 600ms

**New-since-last-visit marker (CONTEXT §9):**
- 1px × 14px vertical bar in `#c4a050`, in LEFT gutter outside card border-radius, 2px gap, vertically centered to first text line
- NO glow, NO card fill, NO bold text
- Persists for entire session it was seen in (no mid-visit decay)
- Decays only between sessions when `lastVisitedAt` updates per §3 hysteresis
- NO entrance animation

**"Since last visit" concept (CONTEXT §3):**
- Per-user `lastVisitedAt` timestamp, first-class persistent concept
- Hysteresis: updates only after 5 min inactivity OR explicit dismissal. Tab-flips are not visits

**Interaction states (CONTEXT §10):**
- Full state matrix specified for decision-card, context-row, chrome-avatar, sync-indicator, nav-links, buttons
- Universal focus ring: `outline: 1px solid rgba(232,230,225,0.4); outline-offset: 2px; border-radius: 4px; transition: outline-offset 100ms ease-out;`
- Transitions: NEVER `all`, always specify properties
- Touch devices: all hover behind `@media (hover: hover) and (pointer: fine)`

**Animation discipline (CONTEXT §11):**
- Allowed: 240ms opacity dip on timestamp tick, 180ms blur-crossfade, 160ms hover background, 100ms active scale, 100ms focus offset
- Forbidden: scroll-entry fades, staggered list reveals, spring physics, spinners, anything on every page load
- `prefers-reduced-motion` removes all motion; color + opacity transitions remain

**Empty states (CONTEXT §12):**
- Needs you with zero items: section structurally absent (don't render the heading)
- Headline fallback: `"Quiet day."` — never "All caught up!" with a checkmark
- Recent decisions empty: show oldest available with `from <date>`, never cheerful empty state

**Per-decision provenance (CONTEXT §17, IN SCOPE):**
- One-line quote on each decision card: italics body color, source-linked
- Attribution: tertiary color, own line beneath, format `— Name in #channel, 18h ago`
- Selection rule: synthesized decision-causing utterance (the comment immediately before consensus, or explicit decision statement)
- If data unavailable: card renders title + people + channels only, NO backend backfill in this phase

### Claude's Discretion

CONTEXT.md §18 explicitly defers four implementation decisions to planning:
1. Tech stack for chrome cluster (single component vs composed)
2. Where `lastVisitedAt` lives (client localStorage vs server-side per-user state)
3. Headline generator implementation (rules-based templates this phase, LLM later — instinct stated)
4. Whether redesign is one phase or split into structure + polish

This research answers all four (recommendations in `## Open Questions` section below).

### Deferred Ideas (OUT OF SCOPE for Phase 41)

From CONTEXT §15:
- Direction summary GENERATION pipeline (slot designed; generation is a separate phase)
- `/activity` page redesign (Recent Activity moves there; activity page itself needs design work)
- Integration health drawer DETAIL (the cluster opens it; the drawer's content is a follow-up)
- cmd-K command palette (`<kbd>` styling specced for when it ships)

From CONTEXT §17:
- Backend backfill of decision-causing utterance source message IDs (not needed — `source_quote` already on Decision nodes)

</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs were assigned in REQUIREMENTS.md for Phase 41 (Phase 41 sits outside the locked v1.3 milestone, which ended at Phase 40). The roadmap entry shows `Requirements: TBD`. Below are six candidate requirement IDs the planner should propose and have the user accept before Wave 0:

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | Dashboard home replaces six-equal-section layout with pulse layout: serif headline (computed from since-last-visit delta) above Recent decisions (lead, 2-3× weight) → Active context (top 3) → Needs you (hidden when empty). Recent Activity, graph thumbnail, This Week sparkline, and greeting line are removed from home. | Current implementation at `apps/web/src/app/dashboard/page.tsx` (lines 170-298) uses a 2-col grid with six widgets. Each removed widget (`graph-thumbnail.tsx`, `this-week.tsx`, `activity-feed-mini.tsx`) is only imported by this file (verified via grep) — safe to delete. `RecentDecisions` widget exists and already parses `Decision` graph nodes from `LensGraphResponse.all_nodes`. |
| DASH-02 | Per-user `last_visited_at` timestamp persists to a new `dashboard_user_state` table (one row per user/workspace pair) and updates only after 5 min of page-level inactivity OR explicit dismissal — never on tab-flip. A `useLastVisitedAt` React hook reads on mount, debounces writes through Supabase, and exposes the stable timestamp to the headline generator and new-item markers. | No existing per-user state table exists (verified — `grep -rn user_settings\|user_preferences\|user_state` returns nothing in `supabase/migrations` and `backend/src`). No existing `localStorage`/`sessionStorage` usage in the web app (only `chrome.storage` in the Chrome extension's `background.ts`). Greenfield. Supabase RLS pattern is established (all tables filter by `auth.uid()` — see `00001_initial_schema.sql`). |
| DASH-03 | Rules-based headline generator selects between three template patterns based on the activity delta since `last_visited_at`: (a) single-item-dominant `"X is waiting on Y since Z."`, (b) bucket-aggregate `"N decisions and M sources of new context since you last looked."`, (c) zero-new fallback `"Quiet day."`. Subtext always names last-visit relative time. | `activity_events` table (Phase 32 complete, all 7 integrations emit) supports `.gt('created_at', last_visited_at).eq('workspace_id', ws)` via Supabase JS — verified pattern in `activity-timeline.tsx` line 148. Decision deltas pull from `LensGraphResponse.all_nodes.filter(entity_type=='Decision')` — already shipping in `recent-decisions.tsx`. Attention items pull from `getDashboardAttention()` — shipping. Single-item-dominance rule: if any one item has urgency-weight > 2× sum of rest, choose pattern (a). |
| DASH-04 | Top-nav chrome adds a right-aligned sync-indicator cluster (sync state text + 1px progress bar + integration-health click target + avatar puck) replacing the current avatar-only chrome. Three states: idle (`last synced 4m ago`, 240ms once-per-minute opacity dip, no icon/dot), syncing (real-tick progress bar from data stream — NO CSS interpolation, source crossfade with 180ms blur), error (dim amber `slack sync paused · reconnect`, click opens slide-over). | Existing top-nav at `apps/web/src/app/dashboard/sidebar.tsx` — small refactor: extract avatar dropdown to component, add `SyncIndicator` next to it. Last-synced timestamp source: `MAX(created_at) FROM activity_events WHERE event_type IN ('sync_completed','sync_started') AND workspace_id=ws` (unified across providers — `last_sync_at` on integration configs is per-provider and not all providers populate it). Real-time sync state: existing Supabase Realtime subscription on `activity_events` (pattern at `activity-timeline.tsx` lines 65-96) — listen for `sync_started`/`sync_completed`. |
| DASH-05 | Unseen items (decisions, context rows) carry a 1px × 14px dim-amber `#c4a050` vertical marker in the left gutter when their `created_at > last_visited_at`. Marker persists across the entire session it was first seen in (no mid-visit decay); decays only when `last_visited_at` advances per the §3 hysteresis. | `activity_events.created_at` is the canonical "new" signal (decisions appear via `context_generated` and `messages_digest` events; tickets via `ticket_created`). Per-item check is `event.created_at > lastVisitedAt` AND `event.id ∉ sessionSeenSet`. Session-seen set lives in a Zustand-style ref or React Context (no existing global store — recommend a small ref-based store, no library). |
| DASH-06 | Each Recent-decision card renders a one-line provenance quote in italics + tertiary-color attribution line when the Decision node's `properties.source_quote` is present; the card gracefully renders title + people + channels when absent. No backend backfill in this phase. | Already shipping. `backend/src/services/llm_extractor.py` line 39-41: `source_quote` is a required field on `ExtractedDecision`. `persist_decision()` at line 281-297 writes it to `graph_nodes.properties.source_quote` and creates an `authored_by` edge to a Person node. `/api/graph/lens/my-work` returns full `properties` dict (verified at `backend/src/routers/graph.py` line 706, line 280). Frontend `LensGraphResponse.all_nodes[].properties` is `Record<string, unknown>` (verified `apps/web/src/components/graph/types.ts` line 78). Attribution-person lookup: follow `authored_by` edge from decision node to Person node, read `Person.name`. |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `next` | ^15.2.0 (already installed) | App Router, server components, route handlers | Already the project's framework |
| `react` | ^19.0.0 (already installed) | UI runtime, hooks, useSyncExternalStore | Already the project's runtime |
| `@supabase/ssr` | ^0.6.0 (already installed) | Server-Side Auth, cookie session, RLS-aware Postgres client | Already used everywhere in the dashboard |
| `@supabase/supabase-js` | ^2.49.0 (already installed) | Realtime subscription, `.gt('created_at', X)` for since-last-visit queries | Pattern shipping in `activity-timeline.tsx` |
| `next/font/google` | bundled | Font loading for Instrument Serif + Geist Sans + Geist Mono | Three new families needed; project already uses `next/font/google` for Inter + JetBrains Mono |
| `tailwindcss` | ^4.0.0 (already installed) | Utility-first styling; `@theme` extension for warm-dark palette tokens | Already the project's styling system |
| `lucide-react` | ^0.469.0 (already installed) | Icons (sparingly — design explicitly bans most iconography) | Avatar dropdown icons only |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `radix-ui` | ^1.4.3 (already installed) | Drawer/Slide-over for integration-health detail | Chrome cluster click → drawer (CONTEXT §8) |
| `clsx` + `tailwind-merge` | already installed via `cn()` | Conditional class composition | All component class-name logic |
| `sonner` | ^1.7.0 (already installed) | Toast (already in root layout) | Only if sync-error needs surfaced toast — not in CONTEXT.md |

**No new npm dependencies required.** This is a notable result: every architectural primitive needed (Realtime, font loading, slide-over, theme extension) is already in the dependency tree.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `dashboard_user_state` Postgres table | `localStorage` with `useSyncExternalStore` | localStorage is single-device-only; user works across laptop + desktop. CONTEXT §3 frames `lastVisitedAt` as "how humans think about 'since I last looked'" — strongly implies multi-device. Server-side table costs one migration + one upsert per visit; localStorage costs cross-device incoherence. Pick table. |
| Custom font loader | `next/font/google` for all three | Geist Sans, Geist Mono, and Instrument Serif are all on Google Fonts. Geist via Google has fewer OpenType features than the npm `geist` package, but the design only uses `tnum`, `zero`, `ss01`, `cv11` — all available in the Google version. Pick `next/font/google` for consistency with existing Inter/JetBrains-Mono setup. |
| Rules-based headline generator | LLM-generated headline (Gemini) | CONTEXT §18 explicitly states "rules-based now, LLM later." Templates handle 95% of real cases ("X is waiting on Y", "N decisions and M sources", "Quiet day."). Rule engine is ~50 lines. LLM would add latency, cost, hallucination risk for marginal copy quality. |
| Global state library (Zustand, Jotai) | React useRef + Context | Only two pieces of cross-component state exist: `lastVisitedAt` (read-many, write-rare) and `sessionSeenItemIds` (read-many, write-many but never re-rendered). Both fit in a Context provider with a `useRef` payload. Don't add a library for two pieces of state. |
| `motion`/`framer-motion` | Plain CSS transitions | Design explicitly bans spring physics (CONTEXT §11). All allowed motion (240ms opacity, 180ms blur, 160ms hover, 100ms scale) is trivially expressible in CSS. No animation library needed. |

**Installation:**

No new dependencies. The migration:

```ts
// apps/web/src/app/layout.tsx — extend existing font imports
import { Inter, JetBrains_Mono, Geist, Geist_Mono, Instrument_Serif } from 'next/font/google'

const geistSans = Geist({ subsets: ['latin'], variable: '--font-geist-sans', display: 'swap' })
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono', display: 'swap' })
const instrumentSerif = Instrument_Serif({
  weight: '400',
  style: ['normal', 'italic'],
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
})

// Keep Inter + JetBrains_Mono temporarily for non-dashboard surfaces (landing, auth, onboarding)
// until those are migrated. Dashboard uses Geist via Tailwind config override.
```

```sql
-- supabase/migrations/00040_dashboard_user_state.sql
CREATE TABLE public.dashboard_user_state (
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  last_visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, workspace_id)
);

ALTER TABLE public.dashboard_user_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_dashboard_state" ON public.dashboard_user_state
  FOR ALL USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
```

## Architecture Patterns

### Recommended Project Structure

```
apps/web/src/app/dashboard/
├── page.tsx                       # Rewritten: orchestrator only, ~80 lines
├── layout.tsx                     # Unchanged
├── sidebar.tsx                    # Refactored: extract <ChromeNav>, add <SyncIndicator>
├── pulse/                         # NEW: phase-41 surface
│   ├── headline.tsx              # Computed serif headline + subtext
│   ├── headline-rules.ts         # Pure rules engine (template selection from delta)
│   ├── headline-rules.test.ts    # Unit tests for rule selection
│   ├── recent-decisions.tsx      # NEW: cards with provenance quotes (replaces old widget)
│   ├── active-context.tsx        # NEW: typographic list (top 3 + view all)
│   ├── needs-you.tsx             # Renamed/restructured needs-attention widget
│   ├── new-item-marker.tsx       # 1px×14px gutter bar
│   └── since-last-visit/
│       ├── use-last-visited-at.ts    # Hook: read on mount, debounce writes, 5-min hysteresis
│       ├── use-session-seen-items.ts # Ref-based store: seen IDs persist for session
│       └── activity-delta.ts          # Pure: query activity_events.gt(timestamp), bucket by type
├── chrome/                        # NEW: top-nav cluster
│   ├── sync-indicator.tsx        # Three states (idle/syncing/error)
│   ├── use-sync-state.ts         # Realtime subscription on activity_events
│   ├── integration-drawer.tsx    # Radix slide-over, opened from cluster click
│   └── avatar-puck.tsx           # Extracted from sidebar.tsx
└── widgets/                       # DELETED entirely (after migration):
    ├── activity-feed-mini.tsx    # → moved logic to /activity page
    ├── graph-thumbnail.tsx       # → lives in /graph already, drop dashboard copy
    ├── graph-thumbnail-logic.ts  # → drop with widget
    ├── this-week.tsx             # → deleted (sparkline removed entirely)
    ├── sprint-badge.tsx          # → consider keeping in chrome; not in CONTEXT §2 scope, recommend delete
    ├── resurfaced.tsx            # → not currently used on dashboard, keep until /activity redesign
    └── integration-dots.tsx      # → replaced by chrome sync indicator
```

### Pattern 1: Pulse Layout Composition

**What:** The dashboard page becomes a thin orchestrator that loads all data in parallel (existing pattern from `page.tsx` lines 85-93) and passes it to typographically-structured children. No grid, no widget framework — just stacked components with `py-24` between sections.

**When to use:** This phase only. The pulse surface is a one-off layout for the home view; other dashboard pages keep their existing structures.

**Example:**

```tsx
// apps/web/src/app/dashboard/page.tsx (rewritten skeleton)
import { Headline } from './pulse/headline'
import { RecentDecisions } from './pulse/recent-decisions'
import { ActiveContext } from './pulse/active-context'
import { NeedsYou } from './pulse/needs-you'
import { useLastVisitedAt } from './pulse/since-last-visit/use-last-visited-at'

export default function DashboardPage() {
  const lastVisitedAt = useLastVisitedAt()  // hook handles read + hysteresis write
  const { decisions, contextItems, needsYouItems, delta } = useDashboardData(lastVisitedAt)

  return (
    <div className="space-y-24">
      <Headline delta={delta} lastVisitedAt={lastVisitedAt} />
      <RecentDecisions items={decisions} lastVisitedAt={lastVisitedAt} />
      <ActiveContext items={contextItems} lastVisitedAt={lastVisitedAt} />
      {needsYouItems.length > 0 && <NeedsYou items={needsYouItems} lastVisitedAt={lastVisitedAt} />}
    </div>
  )
}
```

### Pattern 2: Headline Rules Engine (Pure Function)

**What:** A pure function that takes the activity delta (counts + top items) and returns `{ headline: string, subtext: string }`. No side effects, no hooks. Unit-testable.

**When to use:** Anywhere the headline copy is computed. Pure-function discipline ensures rule changes (which will happen — CONTEXT §18 expects LLM upgrade later) don't touch the render layer.

**Example:**

```ts
// apps/web/src/app/dashboard/pulse/headline-rules.ts
interface Delta {
  decisions: { count: number; topPersonWaiting?: { name: string; ticketId: string; sinceDay: string } | null }
  sources: { count: number }
  needsYou: { topUrgentItem?: { person: string; ticketId: string; sinceDay: string } | null }
}

interface HeadlineCopy {
  headline: string
  subtext: string
}

const SINGLE_ITEM_DOMINANCE_THRESHOLD = 2 // urgent item must be ≥2× total counts to dominate

export function computeHeadline(delta: Delta, lastVisitedAt: Date | null, now: Date = new Date()): HeadlineCopy {
  const since = lastVisitedAt ? formatRelativeTime(lastVisitedAt.toISOString()) : 'first visit'

  // Pattern (c): zero new
  if (delta.decisions.count === 0 && delta.sources.count === 0) {
    return {
      headline: 'Quiet day.',
      subtext: `Nothing new since you last looked, ${since}.`,
    }
  }

  // Pattern (a): single-item-dominant ("Vasiliy is waiting on RD-786 since Tuesday.")
  if (delta.needsYou.topUrgentItem) {
    const { person, ticketId, sinceDay } = delta.needsYou.topUrgentItem
    const remainder = Math.max(0, delta.decisions.count - 1)
    const remainderText = remainder > 0
      ? `${remainder} more decision${remainder === 1 ? '' : 's'} and ${delta.sources.count} new source${delta.sources.count === 1 ? '' : 's'} since you last looked, ${since}.`
      : `${delta.sources.count} new source${delta.sources.count === 1 ? '' : 's'} since you last looked, ${since}.`
    return {
      headline: `${person} is waiting on ${ticketId} since ${sinceDay}.`,
      subtext: remainderText,
    }
  }

  // Pattern (b): bucket-aggregate
  return {
    headline: `${delta.decisions.count} decision${delta.decisions.count === 1 ? '' : 's'} and ${delta.sources.count} sources of new context since you last looked.`,
    subtext: `Since you last looked, ${since}.`,
  }
}
```

### Pattern 3: `lastVisitedAt` Hysteresis Hook

**What:** A hook that (1) reads `last_visited_at` from `dashboard_user_state` on mount and stays at that value for the session, (2) tracks page-level inactivity via `pointermove`/`keydown`/`visibilitychange`, (3) upserts a new timestamp ONLY after 5 minutes of inactivity or on explicit `dismissNewMarkers()` call.

**When to use:** Once, at the top of `DashboardPage`. Propagate via Context to children that need the stable mount-time value.

**Example:**

```ts
// apps/web/src/app/dashboard/pulse/since-last-visit/use-last-visited-at.ts
import { useEffect, useRef, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

const INACTIVITY_MS = 5 * 60 * 1000

export function useLastVisitedAt(workspaceId: string | null): Date | null {
  const [mountedTimestamp, setMountedTimestamp] = useState<Date | null>(null)
  const lastActivityRef = useRef(Date.now())
  const supabase = createClient()

  // Read once on mount
  useEffect(() => {
    if (!workspaceId) return
    let cancelled = false
    supabase
      .from('dashboard_user_state')
      .select('last_visited_at')
      .eq('workspace_id', workspaceId)
      .maybeSingle()
      .then(({ data }) => {
        if (cancelled) return
        setMountedTimestamp(data?.last_visited_at ? new Date(data.last_visited_at) : null)
      })
    return () => { cancelled = true }
  }, [workspaceId, supabase])

  // Inactivity tracking + delayed write
  useEffect(() => {
    if (!workspaceId) return
    const markActive = () => { lastActivityRef.current = Date.now() }
    const events: (keyof WindowEventMap)[] = ['pointermove', 'keydown', 'scroll', 'visibilitychange']
    events.forEach((e) => window.addEventListener(e, markActive, { passive: true }))

    const interval = setInterval(async () => {
      const elapsed = Date.now() - lastActivityRef.current
      if (elapsed >= INACTIVITY_MS) {
        // Hysteresis: write new timestamp, but DO NOT update local state (mount value stays stable for session)
        const userRes = await supabase.auth.getUser()
        if (userRes.data.user) {
          await supabase.from('dashboard_user_state').upsert({
            user_id: userRes.data.user.id,
            workspace_id: workspaceId,
            last_visited_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }, { onConflict: 'user_id,workspace_id' })
        }
        lastActivityRef.current = Date.now() // reset
      }
    }, 30_000) // check every 30s

    return () => {
      events.forEach((e) => window.removeEventListener(e, markActive))
      clearInterval(interval)
    }
  }, [workspaceId, supabase])

  return mountedTimestamp
}
```

### Pattern 4: Sync Indicator Realtime Subscription

**What:** Subscribe to `activity_events` Realtime for the current workspace; track three states from incoming events: idle (most recent `sync_completed` timestamp), syncing (any unfinished `sync_started`), error (provider with `sync_failed` flag in metadata or computed from `connected_at IS NULL` and `status='error'` on integration).

**When to use:** Mounted once in the top chrome.

**Example:**

```ts
// apps/web/src/app/dashboard/chrome/use-sync-state.ts
type SyncState =
  | { kind: 'idle'; lastSyncedAt: Date }
  | { kind: 'syncing'; provider: string; progress: number | null }
  | { kind: 'error'; provider: string; message: string }
  | { kind: 'unknown' }

export function useSyncState(workspaceId: string | null): SyncState {
  const [state, setState] = useState<SyncState>({ kind: 'unknown' })

  useEffect(() => {
    if (!workspaceId) return
    const supabase = createClient()

    // Initial: fetch most recent sync_completed
    supabase
      .from('activity_events')
      .select('created_at, event_type, metadata')
      .eq('workspace_id', workspaceId)
      .in('event_type', ['sync_completed', 'sync_started'])
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()
      .then(({ data }) => {
        if (data?.event_type === 'sync_completed') {
          setState({ kind: 'idle', lastSyncedAt: new Date(data.created_at) })
        }
      })

    // Realtime
    const channel = supabase.channel(`sync-${workspaceId}`)
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'activity_events', filter: `workspace_id=eq.${workspaceId}` },
        (payload) => {
          const evt = payload.new as { event_type: string; metadata: Record<string, unknown>; created_at: string }
          if (evt.event_type === 'sync_started') {
            setState({ kind: 'syncing', provider: String(evt.metadata.integration ?? ''), progress: null })
          } else if (evt.event_type === 'sync_completed') {
            setState({ kind: 'idle', lastSyncedAt: new Date(evt.created_at) })
          }
        }
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [workspaceId])

  return state
}
```

### Anti-Patterns to Avoid

- **Hooking into the `stagger-children` CSS animation from `globals.css`.** That animation violates CONTEXT §11 ("Not allowed: scroll-entry fade-ins, staggered list reveals"). The new dashboard MUST drop the `stagger-children` class. Other dashboard pages that still use it (context feed, settings) are out of scope and untouched.
- **Reusing `widget-card` class.** CONTEXT §6 explicitly bans shadows; `widget-card` declares three layered shadows. Define a new `pulse-card` class in `globals.css` or inline the spec.
- **Treating `lastVisitedAt` as a normal React state.** It must remain STABLE for the entire session — mount-read once, never re-read until next session. Re-reading during the session would make the new-item marker disappear mid-visit (CONTEXT §9 "marker stays for the entire session it was seen in").
- **Computing the headline inside the component body.** Keep `computeHeadline` pure and call it once per delta change. This phase ships rules-based; phase 42+ swaps to LLM with no JSX changes.
- **Driving "last synced" off per-provider `last_sync_at` fields.** Only Notion/Jira/Linear populate them. Use `MAX(activity_events.created_at) WHERE event_type='sync_completed'` for a single workspace-wide value.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-tab/cross-device "last visit" sync | `localStorage` + `storage` event listeners | `dashboard_user_state` Postgres table + Supabase Realtime if needed | localStorage doesn't sync across devices; user works across laptop + desktop. Supabase RLS handles per-user isolation for free. |
| Font loading | Self-hosted `@font-face` with `font-display` and `unicode-range` tuning | `next/font/google` with `display: 'swap'`, `variable: '--font-…'` | `next/font/google` already in use for Inter + JetBrains Mono. Auto-handles subsetting, preloads, no CLS, no third-party request. Geist + Instrument Serif are all on Google Fonts. |
| "Items since timestamp X" query | Custom backend endpoint with cursor pagination | Supabase JS `.gt('created_at', lastVisitedAt).eq('workspace_id', ws)` on `activity_events` | Phase 32 already emits everything to `activity_events`. The query is one line with RLS-enforced workspace scoping. Pattern proven in `activity-timeline.tsx`. |
| Realtime sync-state push | SSE endpoint with polling fallback | Supabase Realtime subscription on `activity_events` filtered by workspace | Already used for the activity tab (`activity-timeline.tsx` lines 65-96). Adds zero infrastructure. |
| Decision provenance backfill | Re-process all messages to extract "decision-causing utterance" | Use existing `properties.source_quote` on Decision graph nodes | Verified at `llm_extractor.py` line 39: every Decision node since v1.2 carries an exact-substring `source_quote` (validated against original content at line 130-145). Render conditionally; older decisions without it just show title + people. |
| Slide-over drawer for integration health | Custom CSS + JS state machine | Radix `Dialog` with `position: right` styling | `radix-ui` ^1.4.3 is already installed. Hand-rolling slide-overs is one of the most common dashboard-code-debt sources. |
| Animation discipline guard | Manually audit every component for `transition: all` | Add `prefers-reduced-motion` media query block in `globals.css` once | One block catches everything. CONTEXT §11 mandates this. |

**Key insight:** The dashboard redesign is mostly about subtraction — removing six widgets, removing shadows, removing greeting text, removing animations. The few new pieces (headline, sync indicator, marker) each map cleanly to an existing pattern. Don't introduce anything custom for problems the stack already solves.

## Common Pitfalls

### Pitfall 1: Stale closure in `lastVisitedAt` inactivity timer

**What goes wrong:** The 30-second `setInterval` reads a stale `lastActivityRef.current` if the hook is closed over from the wrong render.
**Why it happens:** Closures in React effects capture the values they were created with.
**How to avoid:** Use `useRef` (not `useState`) for the activity timestamp. The ref's `.current` is always read fresh. Pattern shipped in `activity-timeline.tsx` lines 38-49 (`isScrolledToTopRef`).
**Warning signs:** Timer fires but doesn't see recent activity; new timestamp written despite recent interaction.

### Pitfall 2: Cyrillic glyph fallback in mixed strings

**What goes wrong:** Strings like `[ClientApp][iOS][CF] Настроить client-web-app` render with Geist's Latin glyphs falling back to a system Cyrillic font with mismatched cap-height, leaving a visual seam in the middle of the title.
**Why it happens:** Geist's Cyrillic subset is acceptable (CONTEXT §5) but requires explicit subset loading.
**How to avoid:** When loading Geist via `next/font/google`, pass `subsets: ['latin', 'cyrillic']` (and `latin-ext` if the team has German/French content). The bracketed prefix lives in tertiary color `#a8a59f` per CONTEXT §5, which softens any residual mismatch.
**Warning signs:** Inspect titles like `RD-781 [ClientApp][iOS][Classfields] Выпилить CapApp` and look for cap-height drift between bracketed-Latin and Cyrillic words.

### Pitfall 3: `font-variation-settings` is `all`-replacing, not additive

**What goes wrong:** Setting `font-variation-settings: "opsz" 32` on the headline overrides ANY existing `font-variation-settings` value inherited from the parent (e.g. `wght`). The font loses its weight.
**Why it happens:** `font-variation-settings` is a single CSS property; subsequent declarations replace, they don't merge.
**How to avoid:** Specify all axes in one declaration: `font-variation-settings: "opsz" 32, "wght" 400;`. Or use the longhand `font-optical-sizing: auto` and `font-weight: 400` together — both are well-supported. MDN confirms `font-optical-sizing` is the preferred high-level property when only `opsz` is needed.
**Warning signs:** Headline renders thin when it should render regular weight, or vice versa.

### Pitfall 4: Real-tick progress bar that pretends to interpolate

**What goes wrong:** Implementing the sync progress bar with `transition: width 200ms` makes the bar "predict" the next tick — moving smoothly when the data stream is actually choppy. CONTEXT §8 explicitly bans this ("no smooth CSS interpolation (smooth interpolation lies about real progress)").
**Why it happens:** Default React rendering doesn't interpolate, but adding a transition for visual smoothness is a reflexive habit.
**How to avoid:** Set `transition: none` on the progress bar fill width. The bar's `width` style updates instantly when `setState` is called from the Realtime callback. Each event tick advances the bar by its real percentage — no `requestAnimationFrame` smoothing.
**Warning signs:** Bar moves continuously between data ticks; bar progresses past the latest tick value.

### Pitfall 5: Marker decay during a long session

**What goes wrong:** User opens dashboard, walks away for 6 minutes, comes back. The hysteresis hook has written a new `last_visited_at`. Marker disappears mid-visit.
**Why it happens:** Naive implementation reads `last_visited_at` reactively (re-fires whenever the row changes).
**How to avoid:** Read `last_visited_at` ONCE on mount. Store the value in component state. The write side of the hysteresis (the `setInterval` updating the row) does NOT update local state. CONTEXT §9: "marker stays for the entire session it was seen in." Document this explicitly in the hook's JSDoc.
**Warning signs:** Markers vanish without user reload; "new" count drops to zero while user is mid-read.

### Pitfall 6: `hanging-punctuation: last` silently invisible in Chrome/Firefox

**What goes wrong:** Designer reviews the headline on Chrome and sees no hanging period. Files a bug. Engineer thinks something is broken.
**Why it happens:** `hanging-punctuation` is Safari-only (caniuse: Chrome 0%, Firefox 0%, Safari ✅ since 10). CONTEXT §4 accepts this — "degrades silently." But the team needs to know.
**How to avoid:** Comment the CSS declaration with the Safari-only caveat. Add a one-line note to the phase's deploy doc that the hanging period is intentional and Safari-specific.
**Warning signs:** Chrome QA reports "period is too close to the right margin." Reply: it's correct, see CONTEXT §4.

### Pitfall 7: Realtime subscription leaking across mounts in StrictMode

**What goes wrong:** React 19 StrictMode double-invokes effects in development. The sync-state subscription connects twice, fires duplicate events, and the second `removeChannel` removes the wrong channel.
**Why it happens:** Recently surfaced and fixed in Phase 40 (see STATE.md `[40-03]: StrictMode auto-mint guard via useRef(mintedRef)`).
**How to avoid:** Either (a) trust the effect's cleanup function returning the right channel reference, or (b) gate channel creation behind a `useRef` flag for `process.env.NODE_ENV === 'development'`. Pattern (a) is correct because `useEffect` cleanup closes over `channel`. The Phase 40 issue was a different category (POST request rather than subscription).
**Warning signs:** In dev, double events arrive. In prod, fine. Verify cleanup is symmetric.

### Pitfall 8: Tailwind v4 `@theme` not picking up next/font variables

**What goes wrong:** Defining `--font-serif: var(--font-serif)` in `@theme` of `globals.css` doesn't apply Instrument Serif to elements using `font-serif` class.
**Why it happens:** Tailwind v4 resolves CSS variables where they're defined. Next/font injects variables on the `<html>` element (via `inter.variable` class), but `@theme` needs to reference them.
**How to avoid:** Use `@theme inline` (not plain `@theme`) for next/font-injected variables. Pattern shown in the project's `globals.css` line 71-114. Existing setup: `@theme` declares the default mapping; `@theme inline` re-binds the variables. Repeat for `--font-serif`, `--font-geist-sans`, `--font-geist-mono`.
**Warning signs:** `font-serif` class doesn't change the font; computed style shows the fallback chain.

## Code Examples

Verified patterns from the existing codebase and authoritative sources.

### Loading Instrument Serif + Geist via next/font/google

```tsx
// apps/web/src/app/layout.tsx
// Source: https://nextjs.org/docs/app/getting-started/fonts + existing project pattern (lines 1-18)
import { Inter, JetBrains_Mono, Geist, Geist_Mono, Instrument_Serif } from 'next/font/google'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' })

const geistSans = Geist({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-geist-sans',
  display: 'swap',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
  display: 'swap',
})

const instrumentSerif = Instrument_Serif({
  weight: '400',
  style: ['normal', 'italic'],
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
})

// In <html className={`${inter.variable} ${jetbrainsMono.variable} ${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} dark`}>
```

### Tailwind v4 `@theme inline` mapping for fonts and warm-dark palette

```css
/* apps/web/src/app/globals.css */
/* Source: existing pattern at lines 71-114 + Tailwind v4 docs */

@theme {
  --font-serif: "Instrument Serif", ui-serif, Georgia, serif;
  --font-geist-sans: "Geist", ui-sans-serif, system-ui, sans-serif;
  --font-geist-mono: "Geist Mono", "JetBrains Mono", ui-monospace, monospace;
}

@theme inline {
  --font-serif: var(--font-serif);
  --font-geist-sans: var(--font-geist-sans);
  --font-geist-mono: var(--font-geist-mono);
}

/* Warm-dark palette — applied on .dark for the dashboard surface only.
   Other dashboard pages may need the existing cool palette during migration;
   recommend gating warm-dark behind a body class `.pulse-surface` to avoid
   bleeding into context detail / settings / activity until they're redesigned. */
.dark.pulse-surface {
  --background: #0f0e0d;
  --card: #13110f;
  --foreground: #ece9e3;
  --muted-foreground: #a8a59f;
  --tertiary-foreground: #6e6b66;

  /* Accents — one job each */
  --accent-attention: #c4a050;  /* dim amber */
  --accent-stale: #b06863;       /* dim red */
  --accent-fresh: #6d8c6d;       /* dim green */
  /* primary (mint) inherited from .dark — used ONLY for brand wordmark + active nav */
}

/* Global motion respect */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  /* color and opacity transitions remain implicit via CSS variables */
}

/* Universal focus ring per CONTEXT §10 */
:focus-visible {
  outline: 1px solid rgba(232, 230, 225, 0.4);
  outline-offset: 2px;
  border-radius: 4px;
  transition: outline-offset 100ms ease-out;
}
```

### Headline component with optical sizing

```tsx
// apps/web/src/app/dashboard/pulse/headline.tsx
// Pattern source: CONTEXT §4 + MDN font-optical-sizing
import { computeHeadline } from './headline-rules'

export function Headline({ delta, lastVisitedAt }: HeadlineProps) {
  const { headline, subtext } = computeHeadline(delta, lastVisitedAt)

  return (
    <section className="max-w-3xl">
      <h1
        className="font-serif text-5xl leading-[1.1] text-[#ece9e3]"
        style={{
          letterSpacing: '-0.025em',
          fontVariationSettings: '"opsz" 32, "wght" 400',
          fontFeatureSettings: '"kern" 1, "liga" 1',
          hangingPunctuation: 'last',  // Safari-only, degrades silently per CONTEXT §4
          textWrap: 'balance',          // optional: better headline wrapping in 2026 browsers
        }}
      >
        {headline}
      </h1>
      <p
        className="mt-6 font-geist-sans text-sm text-[#a8a59f]"
        style={{ fontFeatureSettings: '"tnum" 1' }}
      >
        {subtext}
      </p>
    </section>
  )
}
```

### "Since timestamp" query against activity_events

```ts
// apps/web/src/app/dashboard/pulse/since-last-visit/activity-delta.ts
// Pattern source: apps/web/src/app/dashboard/activity/activity-timeline.tsx line 148

export async function fetchActivityDelta(workspaceId: string, since: Date | null) {
  const supabase = createClient()
  const query = supabase
    .from('activity_events')
    .select('id, event_type, created_at, metadata, actor_id')
    .eq('workspace_id', workspaceId)
    .order('created_at', { ascending: false })
    .limit(200)

  const { data } = since
    ? await query.gt('created_at', since.toISOString())
    : await query

  return data ?? []
}
```

### Decision provenance render (conditional graceful degradation)

```tsx
// apps/web/src/app/dashboard/pulse/recent-decisions.tsx (excerpt)
function DecisionCard({ decision, isNewSinceLastVisit }: Props) {
  const sourceQuote = decision.properties?.source_quote as string | undefined
  const author = decision.properties?.author_name as string | undefined  // from authored_by edge in derived data
  const channel = decision.properties?.source_channel as string | undefined
  const sinceText = decision.properties?.date ? formatRelativeTime(decision.properties.date as string) : null

  return (
    <article className="relative pulse-card" data-new={isNewSinceLastVisit}>
      {isNewSinceLastVisit && <NewItemMarker />}
      <h3 className="font-geist-sans text-base text-[#ece9e3]">{decision.name}</h3>
      <p className="mt-1 font-geist-sans text-sm text-[#a8a59f]">
        {author && <>{author} </>}
        {channel && <>in <span className="font-geist-mono text-[0.92em]">{channel}</span></>}
        {sinceText && <> · <span className="font-geist-mono">{sinceText}</span></>}
      </p>
      {sourceQuote && (
        <blockquote className="mt-4 pulse-quote">
          <p className="font-geist-sans text-sm italic text-[#ece9e3]">&ldquo;{sourceQuote}&rdquo;</p>
          {author && (
            <p className="mt-1 font-geist-sans text-xs text-[#6e6b66]">
              — {author}{channel && <> in {channel}</>}{sinceText && <>, {sinceText}</>}
            </p>
          )}
        </blockquote>
      )}
    </article>
  )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inter + JetBrains Mono globally | Geist Sans + Geist Mono + Instrument Serif (this phase) | Phase 41 | Editorial differentiation from generic SaaS aesthetic; serif gives the headline a literary register that no engineering-tools competitor (Linear, Stripe, Vercel) uses |
| Six-equal-weight widgets | Pulse hierarchy: one headline + lead section + supporting + compact | Phase 41 | User answers "anything happen since I last looked?" in under 4 seconds (CONTEXT §1) |
| Cool dark palette (`oklch(0.13 0.015 270)`) | Warm dark (`#0f0e0d`) for dashboard | Phase 41 | One step away from the cool/clinical SaaS default; warmth signals "company brain" over "data tool" |
| `transition: all` and stagger animations | Strict per-property transitions; `prefers-reduced-motion` global | Phase 41 (CONTEXT §11) | Pulse dashboard opened tens of times per day; animation frequency × annoyance product is what we're optimizing |
| `last_sync_at` per integration config | Unified `MAX(activity_events.created_at) WHERE event_type='sync_completed'` | Phase 41 | Single timestamp surfaces in chrome cluster; works for all 7 providers without per-provider config plumbing |

**Deprecated/outdated:**

- `widget-card` class (declares three layered shadows; CONTEXT §6 bans shadows entirely on the new surface). Replace with `pulse-card` for dashboard home only; other surfaces using `widget-card` remain.
- `stagger-children` animation (CONTEXT §11 bans staggered list reveals).
- `section-label` class (uppercase + tracked; CONTEXT §5 mandates sentence case). Replace with `pulse-section-label` or inline the spec.
- `getGreeting()` function in `page.tsx` lines 33-38 (greeting deleted per CONTEXT §2).
- `getSummaryLine()` in `page.tsx` lines 40-51 (replaced by `computeHeadline` rules engine).

## Open Questions

1. **Should `last_visited_at` be per-workspace, or global per-user?**
   - What we know: The dashboard is workspace-scoped; users may be in multiple workspaces (Phase 1 schema supports `workspace_members` many-to-many). User decisions in CONTEXT.md don't explicitly resolve this.
   - What's unclear: If a user has two workspaces and visits one in the morning + the other in the evening, do they have two independent `last_visited_at` values?
   - Recommendation: Per-workspace (primary key `(user_id, workspace_id)`). It matches the mental model — "since I last looked at THIS workspace" — and costs nothing extra. Migration shown above reflects this.

2. **What's the urgency-weight function for the "single-item-dominant" headline rule?**
   - What we know: CONTEXT §4 shows the pattern (`Vasiliy is waiting on RD-786 since Tuesday.`) but doesn't define when a single item wins over the bucket pattern.
   - What's unclear: Is it "any needs-you item with age > 3 days wins"? "The oldest needs-you item always wins if it exists"? "Only when 1 needs-you item and 0 fresh decisions"?
   - Recommendation: Start with the simplest rule — if there is ANY `needs_you` item AND the user is the assignee, that item wins. Otherwise bucket pattern. Iterate after dogfood.

3. **What is a "session" for marker decay purposes?**
   - What we know: CONTEXT §9 says "marker stays for the entire session it was seen in. Decay: between sessions, when `lastVisitedAt` updates."
   - What's unclear: Is a session "while this tab is open"? "While the dashboard page is the visible top-level route"? "Until the inactivity hysteresis fires"?
   - Recommendation: Session = "from page mount until the inactivity hysteresis fires (i.e., until `last_visited_at` is updated server-side)." Closing the tab and reopening within 5 min = same session; reopening after 5+ min of inactivity = new session.

4. **One phase or split into structure + polish (CONTEXT §18 question 4)?**
   - What we know: CONTEXT.md is one cohesive direction; splitting risks shipping a half-polished surface as the "structure" plan.
   - Recommendation: ONE phase, THREE plans:
     - **41-01 Data foundation:** fonts loaded, palette tokens, `dashboard_user_state` table + RLS, `useLastVisitedAt` hook, `useSessionSeenItems` ref-store, headline rules engine + unit tests, activity-delta query
     - **41-02 Pulse surface:** delete six widgets, build headline + recent-decisions card (with provenance) + active-context list + needs-you + new-item markers, sentence-case section labels, focus-ring system, `prefers-reduced-motion` block
     - **41-03 Chrome cluster:** refactor sidebar into chrome-nav + extracted avatar puck, build sync-indicator three states with Realtime subscription, integration-health drawer (Radix slide-over)
   - Each plan is independently mergeable. Splitting into "structure" then "polish" tempts skipping polish.

5. **Should non-dashboard pages share the warm-dark palette and new fonts now or later?**
   - What we know: Other dashboard subpages (`/context`, `/settings`, `/activity`, `/graph`) currently use the cool palette + Inter/JetBrains Mono.
   - Recommendation: Phase 41 scopes the warm palette + Geist + serif to the home `/dashboard` route only. Apply via a `.pulse-surface` class on the layout's `<main>` element. Migration of other surfaces is a follow-up phase. This contains blast radius; the home redesign can ship without QA across 12 other pages.

## Sources

### Primary (HIGH confidence)

- Project codebase: `apps/web/src/app/dashboard/page.tsx`, `sidebar.tsx`, `widgets/*.tsx`, `layout.tsx` — current dashboard implementation
- Project codebase: `apps/web/src/app/layout.tsx`, `globals.css` — existing font + theme setup
- Project codebase: `apps/web/src/lib/api.ts` — existing API client surface
- Project codebase: `apps/web/src/components/graph/types.ts` — `LensGraphResponse` shape
- Project codebase: `apps/web/src/app/dashboard/activity/activity-timeline.tsx` — Realtime subscription + `.gt('created_at', X)` pattern
- Project codebase: `backend/src/services/llm_extractor.py` lines 30-50, 251-335 — `ExtractedDecision.source_quote` and `persist_decision()` graph writes
- Project codebase: `backend/src/routers/graph.py` lines 700-720 — lens API properties passthrough
- Project codebase: `backend/src/routers/integrations.py` — `last_sync_at` is per-provider only
- Project codebase: `supabase/migrations/00001_initial_schema.sql` — RLS policy patterns; `00031_activity_event_types.sql`; `00039_telegram_shared_bot.sql` — recent migration patterns to mirror
- Next.js fonts docs: https://nextjs.org/docs/app/getting-started/fonts — Geist + Instrument Serif via `next/font/google`
- Google Fonts: https://fonts.google.com/specimen/Geist , https://fonts.google.com/specimen/Geist+Mono , https://fonts.google.com/specimen/Instrument+Serif — confirmed available
- MDN: `font-optical-sizing` https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/font-optical-sizing — `opsz` axis usage
- MDN: `hanging-punctuation` https://developer.mozilla.org/en-US/docs/Web/CSS/hanging-punctuation — Safari-only confirmation
- Tailwind v4 theme docs: https://tailwindcss.com/docs/theme — `@theme inline` for next/font variables

### Secondary (MEDIUM confidence)

- caniuse.com `hanging-punctuation` — Chrome 0%, Firefox 0%, Safari ✅; cross-verified with MDN
- WebKit blog: text-wrap: pretty — relevant for future polish, optional in this phase
- Supabase upsert docs — confirms `onConflict` parameter pattern for `dashboard_user_state` upsert

### Tertiary (LOW confidence — not relied on for decisions)

- DEV.to articles on `useSyncExternalStore` cross-tab sync — not used; the table approach makes cross-tab sync free via Realtime if needed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and used; only the font additions are new
- Architecture: HIGH — patterns 1-4 each mirror an existing working pattern in the codebase
- Pitfalls: HIGH — pitfalls 1, 2, 7 are observed in shipped code; 3, 4, 6, 8 are documented framework/CSS behaviors; 5 is design-spec discipline
- Data layer: HIGH — verified `activity_events` schema, `properties.source_quote` flow, `LensGraphResponse` passthrough, `dashboard_user_state` greenfield
- Visual system migration: MEDIUM — the warm-dark palette and font additions are mechanical, but containing blast-radius (so the cool palette doesn't break on context/settings/activity pages) needs the `.pulse-surface` scope rule; first plan should verify

**Research date:** 2026-05-20
**Valid until:** 2026-06-20 (30 days; the stack is stable, but next/font and Tailwind v4 docs evolve)
