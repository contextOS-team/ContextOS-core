# Phase 19: Context Feed + Dashboard Home - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can browse, filter, search, and inspect all their generated context pages from a dedicated feed view at /dashboard/context. The dashboard home at /dashboard provides a summary overview with recent context pages and integration health. This phase replaces the current ticket-lookup context page with a proper browsable feed, adds a detail route at /dashboard/context/[id], and enriches the dashboard home.

</domain>

<decisions>
## Implementation Decisions

*All decisions made via Interface Craft design critique methodology — analyzing existing code patterns, industry benchmarks (Linear, Vercel, Stripe), information density requirements, and visual language cohesion.*

### Feed layout & presentation
- **Two-line rows** inside a single `rounded-xl border bg-card` container with `divide-y` separators — same component language as the integration list on the home page
- Line 1: Title (text-sm font-medium) + status dot (right-aligned)
- Line 2: Ticket ID in mono (font-mono text-xs text-muted-foreground) + relative timestamp in mono + source count
- **Rationale:** Context pages carry more data than integrations (ticket ID, title, status, timestamp, source count). Single-line truncates titles or produces cluttered scan. Two-line gives title breathing room while keeping metadata scannable.
- Left border accent color-coded by status (emerald=ready, amber=generating, orange=stale, red=error) — mirrors integration brand border pattern
- Hover: `hover:bg-muted/40` matching integrations
- Click: navigates to `/dashboard/context/[id]`
- Sort: `updated_at DESC` default, no sort controls in v1

### Filters
- Horizontal pill toggles inline with section label: All | Ready | Generating | Stale | Error
- Active pill: `text-primary` with teal underline (2px, same as nav active state)
- Inactive: `text-muted-foreground`
- No background fills on pills — minimal, consistent with nav pattern
- Client-side filter on already-loaded list

### Search
- Persistent ghost input above the list, below section label + filters
- Search icon + placeholder "Filter by title or ticket ID..."
- Client-side text filtering with debounce — not semantic search
- No submit button; filter as you type

### Data fetching & real-time
- Read context_pages directly via Supabase client (RLS already configured) — follows project constraint "Supabase for reads, Python API for actions"
- Supabase Realtime subscription on context_pages table for live status updates (FEED-04)
- Channel must be properly cleaned up on unmount (React Strict Mode double-invoke concern from STATE.md)
- No new backend API endpoint needed for listing
- Regenerate and generate actions still go through Python backend API (existing endpoints)

### Dashboard home composition
- Keep existing greeting + integration count header
- Add "Recent Context" section (section-label pattern) showing last 5 context pages in the same two-line row format as the feed
- Row clicks navigate to `/dashboard/context/[id]` detail view
- "View all" link below navigates to `/dashboard/context`
- Keep existing integration status list below recent context
- **No stat cards** — the integration count ("3/5 connected" in mono) is sufficient; adding stat cards introduces a new component pattern for numbers that aren't actionable. The recent pages list itself communicates volume and status at a glance.
- **No activity preview** — that's Phase 18's scope
- "Recent Context" section only renders when context pages exist; otherwise home is greeting + integrations (current behavior)

### Detail view (/dashboard/context/[id])
- **Separate route, full page** — clean URL, shareable, SSR-friendly. Matches FEED-05 requirement. Slide-over panel deferred to v2 (FEED-07).
- Back link: `<- Context` (navigates to `/dashboard/context`)
- Header: Title (text-xl font-semibold), below: ticket ID in mono + status dot + "Generated [relative time]"
- Action bar: `[Copy Prompt]` (primary/teal) + `[Regenerate]` (outline) + `[Open in Linear]` (ghost, external link icon)
- Content: Rendered markdown via `react-markdown` + `remark-gfm`. The current page renders content as `whitespace-pre-wrap` plain text which loses all formatting — this fixes that.
- **AI Prompt callout:** The AI Implementation Prompt section (last section) rendered inside a `bg-elevated rounded-xl border` container with its own "Copy" button in the top-right corner. This is the hero feature — visually distinct from the rest of the content.
- **Copy Prompt** copies ONLY the AI prompt section — engineers paste this into Cursor/Claude Code. Toast confirmation via Sonner: "Prompt copied to clipboard"
- Sources section at bottom: section-label "Sources (N)" + compact rows with type badge + title + relevance percentage
- **Regenerate UX:** Click -> button disabled with spinner -> toast "Regenerating [ticket ID]..." -> status updates via Realtime -> when ready, toast "[ticket ID] ready" + content refreshes. No confirmation dialog — dogfooding team, low friction.

### Empty states
- Feed empty state: Inside the same `rounded-xl border bg-card` container. Three dimmed skeleton rows (Skeleton component at reduced opacity) showing two-line row layout shape. Below: centered "No context pages yet" (text-sm text-muted-foreground) + "Generate context for a ticket to see it here." + CTA button "Generate Context" (teal primary).
- **CTA behavior:** Click reveals inline ticket ID input + Generate button within the empty state container. Uses existing `generateContextPage` API. After generation starts, Realtime subscription picks up the new page.
- **Dashboard home:** No separate empty state. When no context pages exist, "Recent Context" section simply doesn't render. Greeting + integrations remain (current behavior).

### Claude's Discretion
- Exact spacing, padding, and typography sizing within rows
- react-markdown plugin configuration details
- Skeleton loading state layouts for feed and detail pages
- Pagination approach if list grows large
- Search debounce timing
- How to extract the AI prompt section from markdown content for the copy action

</decisions>

<specifics>
## Specific Ideas

- Two-line row design should match the integration list aesthetic: rounded-xl border, divide-y, hover:bg-muted/40 — visual language cohesion across the dashboard
- Status filter pills should feel like they belong with the teal underline nav pattern — minimal, not heavy tab components
- AI prompt section in detail view is the product's hero feature — must be visually distinct (elevated surface + dedicated copy button)
- Dashboard home stat numbers should use font-mono tabular-nums (matching "3/5 connected" pattern)
- Toast feedback via Sonner (already configured in Phase 16)
- Current context page's "Context Engine" heading (text-2xl font-bold) breaks from the subtle section-label pattern used everywhere else — the new feed should use section-label instead

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dashboard/page.tsx`: Integration list with compact rows, brand borders, status dots, hover states — the pattern template for feed rows
- `dashboard/context/page.tsx`: Current ticket-lookup page to be replaced; existing API calls (getContextPage, generateContextPage, searchContext) remain useful for detail view and generate actions
- `lib/api.ts`: ContextPageResponse type, getContextPage(), generateContextPage() — detail view and generate actions use these directly
- `components/ui/skeleton.tsx`: Skeleton component with shimmer-sweep for loading states
- `components/ui/sonner.tsx`: Toast notifications configured with dark theme
- `lib/supabase/client.ts`: Browser Supabase client for direct reads and Realtime subscriptions
- Existing shadcn components: Button, Input, Card, Label, DropdownMenu

### Established Patterns
- Dark OKLCH token system: bg-background (L1), bg-card (L2), bg-elevated (L3), bg-overlay (L4)
- Section labels: `section-label` class (monospace uppercase tracking)
- Data identifiers: `font-mono tabular-nums`
- Skeleton loading states match populated layout shape
- Spring animation: `animate-fade-in-up` class with cubic-bezier(0.34, 1.56, 0.64, 1)
- Stagger children: `stagger-children` class with 50ms delays
- Integration list: rounded-xl border + divide-y + hover:bg-muted/40 + border-l-2 brand accent

### Integration Points
- `/dashboard/context/page.tsx`: Replace current lookup page with feed list
- `/dashboard/context/[id]/page.tsx`: New route for detail view
- `/dashboard/page.tsx`: Extend with "Recent Context" section above integrations
- Supabase RLS on `context_pages`: workspace_data policy already allows reads for workspace members
- `context_pages` columns: id, workspace_id, ticket_id, ticket_identifier, title, content, status, sources (JSONB), generated_at, generation_model, generation_tokens_used, created_at, updated_at

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 19-context-feed-dashboard-home*
*Context gathered: 2026-03-04*
