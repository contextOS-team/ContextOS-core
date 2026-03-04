# Phase 19: Context Feed + Dashboard Home - Research

**Researched:** 2026-03-04
**Domain:** Next.js dashboard views, Supabase Realtime, Markdown rendering
**Confidence:** HIGH

## Summary

Phase 19 replaces the current ticket-lookup context page (`/dashboard/context`) with a browsable feed, adds a detail route (`/dashboard/context/[id]`), and enriches the dashboard home with a "Recent Context" section. The core technical challenges are: (1) reading context_pages via Supabase client with proper workspace scoping, (2) setting up Supabase Realtime subscriptions with correct cleanup for React Strict Mode, (3) rendering markdown content with `react-markdown` + `remark-gfm`, and (4) enabling the `supabase_realtime` publication on the `context_pages` table (currently not configured).

The existing codebase provides strong foundations: the dashboard layout, design tokens, Skeleton component, Sonner toast, and API client are all in place. The current context page (`dashboard/context/page.tsx`) will be fully replaced. No new backend endpoints are needed -- the feed reads directly from Supabase, and generate/regenerate actions use existing Python API endpoints.

**Primary recommendation:** Install `react-markdown` + `remark-gfm`, add `context_pages` to the `supabase_realtime` publication via migration, and build the feed as a client component with Supabase Realtime subscription following the cleanup pattern documented below.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Feed layout:** Two-line rows inside `rounded-xl border bg-card` container with `divide-y` separators
- **Row structure:** Line 1: Title (text-sm font-medium) + status dot. Line 2: Ticket ID in mono + relative timestamp + source count
- **Left border accent:** Color-coded by status (emerald=ready, amber=generating, orange=stale, red=error)
- **Filters:** Horizontal pill toggles (All | Ready | Generating | Stale | Error), active pill with teal underline, client-side filtering
- **Search:** Persistent ghost input above list, client-side text filtering with debounce, no submit button
- **Data fetching:** Supabase client for reads (RLS configured), Realtime subscription for live updates, no new backend API
- **Dashboard home:** Keep greeting + integration count. Add "Recent Context" section (last 5 pages, same row format). "View all" link. Section only renders when pages exist. No stat cards. No activity preview.
- **Detail view:** Separate route `/dashboard/context/[id]`. Back link, header with title/ticket ID/status/timestamp, action bar (Copy Prompt primary, Regenerate outline, Open in Linear ghost). Markdown rendered via `react-markdown` + `remark-gfm`. AI Prompt callout in `bg-elevated` container with dedicated Copy button. Sources section at bottom.
- **Copy Prompt:** Copies ONLY the AI prompt section. Toast via Sonner.
- **Regenerate UX:** Button disabled with spinner, toast "Regenerating...", status via Realtime, no confirmation dialog
- **Empty state:** Skeleton rows at reduced opacity + message + CTA "Generate Context" that reveals inline ticket ID input
- **Sort:** `updated_at DESC` default, no sort controls in v1

### Claude's Discretion
- Exact spacing, padding, typography sizing within rows
- react-markdown plugin configuration details
- Skeleton loading state layouts for feed and detail pages
- Pagination approach if list grows large
- Search debounce timing
- How to extract the AI prompt section from markdown content for the copy action

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FEED-01 | User can browse all generated context pages in a scrollable list view | Supabase client reads with RLS, two-line row component, `updated_at DESC` ordering |
| FEED-02 | User can filter context pages by status (All/Ready/Generating/Stale/Error) | Client-side filter on status field; note: DB schema only has draft/generating/ready/stale (no error) |
| FEED-03 | User can search context pages by free text (title, ticket ID) | Client-side text filter with debounced input, matching against title and ticket_identifier fields |
| FEED-04 | Context feed shows real-time status updates via Supabase Realtime | Requires adding context_pages to supabase_realtime publication + Realtime subscription pattern |
| FEED-05 | Context page detail is a route-based view with copy-prompt and regenerate actions | Next.js dynamic route `[id]`, react-markdown rendering, clipboard API, existing generateContextPage API |
| FEED-06 | Empty states show what a populated feed looks like with one clear CTA | Skeleton rows at reduced opacity + inline generate form using existing generateContextPage API |
| HOME-01 | Dashboard home shows summary with recent context pages, integration health, activity preview | Add "Recent Context" section (5 most recent pages) to existing dashboard home; activity preview out of scope per CONTEXT.md |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-markdown | ^10.1.0 | Render markdown content in context page detail view | Standard React markdown renderer, ESM, React 18+/19 compatible, safe by default |
| remark-gfm | ^4.0.1 | GFM support (tables, strikethrough, tasklists, autolinks) | Required for rendering context page content which includes GFM features |
| @supabase/supabase-js | 2.97.0 (existing) | Direct reads from context_pages + Realtime subscriptions | Already installed, RLS policies configured |
| sonner | ^1.7.0 (existing) | Toast notifications for copy/regenerate feedback | Already installed and configured with dark theme |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | ^0.469.0 (existing) | Icons for search, copy, external link, back arrow, loader | All UI icons throughout feed and detail views |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-markdown | @next/mdx | @next/mdx is for file-based MDX; react-markdown is for rendering dynamic content strings. react-markdown is correct here. |
| Client-side search | Backend search endpoint | Client-side is simpler and sufficient for small datasets (dogfooding team). If list grows, add server-side pagination later. |

**Installation:**
```bash
cd apps/web && pnpm add react-markdown remark-gfm
```

## Architecture Patterns

### Recommended Project Structure
```
apps/web/src/app/dashboard/
├── page.tsx                    # Dashboard home (extend with Recent Context)
├── context/
│   ├── page.tsx                # Feed list (REPLACE current lookup page)
│   └── [id]/
│       └── page.tsx            # Detail view (NEW route)
```

### Pattern 1: Supabase Direct Read with RLS
**What:** Read context_pages directly from the browser Supabase client; RLS enforces workspace scoping automatically.
**When to use:** For the feed list and detail view data fetching.
**Example:**
```typescript
// Source: Existing project pattern (lib/supabase/client.ts) + Supabase docs
import { createClient } from '@/lib/supabase/client'

async function fetchContextPages() {
  const supabase = createClient()
  const { data, error } = await supabase
    .from('context_pages')
    .select('id, title, ticket_identifier, status, sources, updated_at')
    .is('deleted_at', null)
    .order('updated_at', { ascending: false })

  if (error) throw error
  return data
}
```

### Pattern 2: Supabase Realtime Subscription with Cleanup
**What:** Subscribe to postgres_changes on context_pages for live status updates. Must clean up on unmount (React Strict Mode concern from STATE.md).
**When to use:** Feed page and detail page for live status updates.
**Example:**
```typescript
// Source: Supabase docs (https://supabase.com/docs/guides/realtime/postgres-changes)
import { useEffect } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { RealtimeChannel } from '@supabase/supabase-js'

function useContextPagesRealtime(onUpdate: (payload: any) => void) {
  useEffect(() => {
    const supabase = createClient()
    const channel: RealtimeChannel = supabase
      .channel('context-pages-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'context_pages',
        },
        (payload) => onUpdate(payload)
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [onUpdate])
}
```

### Pattern 3: Client-side Filter + Debounced Search
**What:** Filter already-loaded list client-side by status and text search.
**When to use:** Feed page filters and search.
**Example:**
```typescript
// Debounced search with useMemo for filtering
import { useState, useMemo, useCallback, useRef, useEffect } from 'react'

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debouncedValue
}

// In component:
const [searchQuery, setSearchQuery] = useState('')
const [statusFilter, setStatusFilter] = useState<string>('all')
const debouncedQuery = useDebounce(searchQuery, 200)

const filteredPages = useMemo(() => {
  let result = pages
  if (statusFilter !== 'all') {
    result = result.filter(p => p.status === statusFilter)
  }
  if (debouncedQuery) {
    const q = debouncedQuery.toLowerCase()
    result = result.filter(p =>
      p.title.toLowerCase().includes(q) ||
      p.ticket_identifier?.toLowerCase().includes(q)
    )
  }
  return result
}, [pages, statusFilter, debouncedQuery])
```

### Pattern 4: AI Prompt Extraction from Markdown
**What:** Extract the "AI Implementation Prompt" section from context page markdown for the Copy Prompt action.
**When to use:** Detail view Copy Prompt button.
**Example:**
```typescript
// Extract AI prompt section from markdown content
// The AI prompt is typically the last major section, starting with a heading like
// "## AI Implementation Prompt" or "## Implementation Prompt"
function extractAIPrompt(content: string): string {
  const promptHeadingPattern = /^##\s+(?:AI\s+)?Implementation\s+Prompt/im
  const match = content.match(promptHeadingPattern)
  if (!match || match.index === undefined) return content
  return content.slice(match.index).trim()
}
```

### Pattern 5: Markdown Rendering with Dark Theme
**What:** Render context page content as formatted markdown with GFM support.
**When to use:** Detail view content area.
**Example:**
```typescript
// Source: react-markdown docs (https://github.com/remarkjs/react-markdown)
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function ContextContent({ content }: { content: string }) {
  return (
    <div className="prose prose-sm prose-invert max-w-none">
      <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
    </div>
  )
}
```
**Note:** react-markdown v10 removed the `className` prop. Apply classes on a wrapper div.

### Anti-Patterns to Avoid
- **Creating a new Supabase client inside useEffect:** Use `createClient()` from the existing singleton pattern. Creating inside the effect causes new instances on every render.
- **Not cleaning up Realtime channels:** Always call `supabase.removeChannel(channel)` in the useEffect cleanup. Failing to do so causes "TooManyChannels" errors, especially with React Strict Mode.
- **Using `whitespace-pre-wrap` for markdown:** The current context page does this. It loses all formatting. Use react-markdown instead.
- **Polling for generation status:** The current page polls with setTimeout. Replace with Realtime subscription.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown rendering | Custom parser or dangerouslySetInnerHTML | react-markdown + remark-gfm | Markdown parsing has edge cases. react-markdown is safe by default (no XSS). |
| Debounce | Custom setTimeout logic | Simple useDebounce hook (10 lines) or lodash.debounce | Easy to get wrong with stale closures |
| Relative time formatting | New utility | Existing `formatRelativeTime` from `@/lib/utils` | Already built and used in dashboard |
| Toast notifications | Custom notification UI | Sonner (already configured) | Already styled for dark theme |
| Clipboard copy | Manual document.execCommand | `navigator.clipboard.writeText()` | Modern API, works in all target browsers |

**Key insight:** The project already has most utilities needed (formatRelativeTime, Skeleton, Sonner, Supabase client). The only new dependencies are react-markdown and remark-gfm.

## Common Pitfalls

### Pitfall 1: Supabase Realtime Publication Not Enabled
**What goes wrong:** Realtime subscription connects but never receives events.
**Why it happens:** The `context_pages` table is NOT added to the `supabase_realtime` publication. This is a REQUIRED setup step.
**How to avoid:** Create a migration: `ALTER PUBLICATION supabase_realtime ADD TABLE context_pages;`
**Warning signs:** Subscription status is "SUBSCRIBED" but no events fire when rows change.
**Confidence:** HIGH -- verified by checking all migration files; no publication setup exists.

### Pitfall 2: Status "error" Does Not Exist in Schema
**What goes wrong:** The CONTEXT.md specifies filter pills for "Error" status, but the database CHECK constraint on context_pages.status only allows `('draft', 'generating', 'ready', 'stale')`.
**Why it happens:** The filter design includes an error state that the schema doesn't support.
**How to avoid:** Either (a) add `'error'` to the CHECK constraint via migration, or (b) map "Error" filter to show pages with no status match (which would never match). Recommendation: add `'error'` to the constraint since it's a legitimate pipeline state.
**Warning signs:** Filter shows "Error" option but never has results.
**Confidence:** HIGH -- verified from `00001_initial_schema.sql`.

### Pitfall 3: React Strict Mode Double Subscription
**What goes wrong:** Two Realtime channels created in development, leading to duplicate events or "TooManyChannels" error.
**Why it happens:** React 18+ StrictMode runs useEffect twice in development.
**How to avoid:** Always return cleanup function that calls `supabase.removeChannel(channel)`. The Supabase client handles deduplication if the same channel name is reused, but explicit cleanup is required.
**Warning signs:** Console shows duplicate channel subscriptions.
**Confidence:** HIGH -- documented in STATE.md as a known concern.

### Pitfall 4: react-markdown v10 className Removal
**What goes wrong:** Passing `className` prop to `<Markdown>` component has no effect or causes TypeScript error.
**Why it happens:** react-markdown v10 removed the `className` prop.
**How to avoid:** Wrap in a `<div>` with the desired classes. Use `prose prose-sm prose-invert max-w-none` on the wrapper.
**Warning signs:** TypeScript error on className prop, or no classes applied to markdown output.
**Confidence:** HIGH -- verified from react-markdown changelog (v10.0.0 breaking change).

### Pitfall 5: Stale Closure in Realtime Callback
**What goes wrong:** Realtime callback captures stale state, causing updates to not reflect in UI.
**Why it happens:** The callback passed to `.on()` closes over the initial state value.
**How to avoid:** Use `useCallback` with proper dependencies, or use a ref to hold the latest state setter/updater function. The safest pattern is using the functional form of `setState(prev => ...)`.
**Warning signs:** Realtime events fire (visible in console) but UI doesn't update.

### Pitfall 6: Missing workspace_id Filter on Direct Reads
**What goes wrong:** Query returns all context pages across all workspaces (before RLS filters them).
**Why it happens:** While RLS enforces workspace scoping server-side, not including a workspace_id filter means Supabase scans all rows and filters via policy.
**How to avoid:** RLS handles security automatically. For performance, consider adding `.eq('workspace_id', workspaceId)` if the workspace ID is available, but for a small dogfooding team this is not critical.
**Warning signs:** Slow queries at scale (not a v1 concern).

## Code Examples

### Feed Row Component
```typescript
// Two-line row matching integration list pattern from dashboard/page.tsx
const STATUS_COLORS = {
  ready: { dot: 'bg-emerald-500', border: 'border-l-emerald-500' },
  generating: { dot: 'bg-amber-500', border: 'border-l-amber-500' },
  stale: { dot: 'bg-orange-500', border: 'border-l-orange-500' },
  error: { dot: 'bg-red-500', border: 'border-l-red-500' },
  draft: { dot: 'bg-muted-foreground/30', border: 'border-l-transparent' },
}

function ContextRow({ page, onClick }: { page: ContextPage; onClick: () => void }) {
  const colors = STATUS_COLORS[page.status] ?? STATUS_COLORS.draft
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 transition-colors duration-150 hover:bg-muted/40 border-l-2 ${colors.border}`}
    >
      {/* Line 1: Title + status dot */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-foreground truncate">{page.title}</span>
        <span className={`shrink-0 h-1.5 w-1.5 rounded-full ${colors.dot}`} />
      </div>
      {/* Line 2: Ticket ID + timestamp + source count */}
      <div className="flex items-center gap-3 mt-0.5">
        <span className="text-xs font-mono text-muted-foreground">{page.ticket_identifier}</span>
        <span className="text-xs font-mono text-muted-foreground">{formatRelativeTime(page.updated_at)}</span>
        <span className="text-xs text-muted-foreground">{page.sources?.length ?? 0} sources</span>
      </div>
    </button>
  )
}
```

### Status Filter Pills
```typescript
// Horizontal pill toggles matching nav active state pattern
const FILTER_OPTIONS = ['all', 'ready', 'generating', 'stale', 'error'] as const

function StatusFilters({
  active,
  onSelect,
}: {
  active: string
  onSelect: (filter: string) => void
}) {
  return (
    <div className="flex items-center gap-1">
      {FILTER_OPTIONS.map((filter) => (
        <button
          key={filter}
          onClick={() => onSelect(filter)}
          className={`relative px-3 py-1.5 text-xs font-medium capitalize transition-colors duration-150 ${
            active === filter
              ? 'text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {filter}
          {active === filter && (
            <span className="absolute bottom-0 left-3 right-3 h-[2px] rounded-full bg-primary" />
          )}
        </button>
      ))}
    </div>
  )
}
```

### Clipboard Copy with Toast
```typescript
// Source: Web Clipboard API + Sonner (existing)
import { toast } from 'sonner'

async function copyToClipboard(text: string, label: string = 'Copied') {
  try {
    await navigator.clipboard.writeText(text)
    toast(label)
  } catch {
    toast.error('Failed to copy to clipboard')
  }
}
```

### Supabase Read for Feed
```typescript
import { createClient } from '@/lib/supabase/client'

interface ContextPageRow {
  id: string
  title: string
  ticket_identifier: string | null
  status: string
  sources: Array<{ type: string; id: string; title: string; relevance_score: number }>
  updated_at: string
  generated_at: string | null
}

async function fetchContextPages(): Promise<ContextPageRow[]> {
  const supabase = createClient()
  const { data, error } = await supabase
    .from('context_pages')
    .select('id, title, ticket_identifier, status, sources, updated_at, generated_at')
    .is('deleted_at', null)
    .order('updated_at', { ascending: false })

  if (error) throw error
  return data ?? []
}
```

### Supabase Read for Single Page (Detail View)
```typescript
async function fetchContextPageById(id: string) {
  const supabase = createClient()
  const { data, error } = await supabase
    .from('context_pages')
    .select('*')
    .eq('id', id)
    .is('deleted_at', null)
    .single()

  if (error) throw error
  return data
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ticket lookup page with polling | Feed list + Realtime subscriptions | This phase | Replaces setTimeout polling with proper WebSocket updates |
| `whitespace-pre-wrap` for markdown | react-markdown + remark-gfm | This phase | Proper markdown rendering with tables, headings, code blocks |
| react-markdown v9 className prop | v10 wrapper div pattern | Feb 2025 | className prop removed; must use wrapper element |

**Deprecated/outdated:**
- The current `dashboard/context/page.tsx` lookup/search tab pattern is being fully replaced
- `document.execCommand('copy')` -- use `navigator.clipboard.writeText()` instead

## Open Questions

1. **Error status in database schema**
   - What we know: DB CHECK constraint allows only (draft, generating, ready, stale). CONTEXT.md specifies Error filter.
   - What's unclear: Whether the pipeline ever sets an error status, or if this needs a schema migration.
   - Recommendation: Add `'error'` to the CHECK constraint via migration. It's a valid pipeline state for failed generations.

2. **AI Prompt section delimiter**
   - What we know: The context page content is markdown with an AI Implementation Prompt section.
   - What's unclear: Exact heading text used for this section across all generated pages.
   - Recommendation: Check a few generated context pages in the database to confirm the heading pattern. Use a regex like `/^##\s+(?:AI\s+)?Implementation\s+Prompt/im` and fall back to copying all content if not found.

3. **Linear ticket URL construction**
   - What we know: Detail view has "Open in Linear" button. We have ticket_identifier (e.g., "ENG-123") but need the full Linear URL.
   - What's unclear: Whether the Linear workspace slug is stored or needs to be derived.
   - Recommendation: Check if workspace integrations store the Linear org/workspace URL. If not, the link might need to use the Linear universal URL format `https://linear.app/issue/{ticket_identifier}` or be omitted until the URL is available.

4. **Pagination strategy**
   - What we know: V1 loads all pages client-side. Dogfooding team, so dataset is small.
   - What's unclear: At what scale this becomes a problem.
   - Recommendation: For v1, load all pages (likely < 100). Add cursor-based pagination if the list exceeds ~200 items. The Supabase `.range()` method supports this easily.

## Sources

### Primary (HIGH confidence)
- Supabase Postgres Changes docs: https://supabase.com/docs/guides/realtime/postgres-changes -- subscription API, filter syntax, RLS behavior
- Supabase Realtime Authorization docs: https://supabase.com/docs/guides/realtime/authorization -- JWT auto-authentication, RLS enforcement
- react-markdown GitHub: https://github.com/remarkjs/react-markdown -- v10 breaking changes (className removal), usage with remarkPlugins
- react-markdown changelog: https://github.com/remarkjs/react-markdown/blob/main/changelog.md -- v10.0.0 released 2025-02-20, React 19 types fixed in v9.0.2
- Project source code: `supabase/migrations/00001_initial_schema.sql` -- context_pages schema, RLS policies, status CHECK constraint
- Project source code: `apps/web/src/app/dashboard/page.tsx` -- integration list pattern (template for feed rows)
- Project source code: `apps/web/src/lib/supabase/client.ts` -- browser Supabase client setup
- Project source code: `apps/web/src/lib/api.ts` -- ContextPageResponse type, generateContextPage API

### Secondary (MEDIUM confidence)
- Supabase Realtime React Strict Mode: https://github.com/supabase/realtime-js/issues/169 -- cleanup pattern with removeChannel
- remark-gfm releases: https://github.com/remarkjs/remark-gfm/releases -- v4.0.1 latest

### Tertiary (LOW confidence)
- AI prompt section extraction regex -- needs validation against actual generated content in database

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- react-markdown and remark-gfm are well-established, versions verified from official sources
- Architecture: HIGH -- follows existing project patterns (Supabase client reads, component structure)
- Pitfalls: HIGH -- Realtime publication gap and schema constraint verified from migration files
- Markdown rendering: HIGH -- react-markdown v10 API verified from changelog
- AI prompt extraction: LOW -- depends on actual content format in generated pages, needs runtime validation

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (stable libraries, low churn)
