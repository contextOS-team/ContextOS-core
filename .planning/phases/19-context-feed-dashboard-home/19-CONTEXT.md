# Phase 19: Context Feed + Dashboard Home - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can browse, filter, search, and inspect all their generated context pages from a dedicated feed view at /dashboard/context. The dashboard home at /dashboard provides a summary overview with recent context pages and integration health. This phase replaces the current ticket-lookup context page with a proper browsable feed, adds a detail route at /dashboard/context/[id], and enriches the dashboard home.

</domain>

<decisions>
## Implementation Decisions

### Feed layout & presentation
- Compact single-line rows in a bordered list (like the existing integration list on home page): ticket ID (mono), title, status dot, relative timestamp
- Dense and scannable, matching the existing Linear-inspired aesthetic
- Rows are clickable -- navigate to /dashboard/context/[id] detail view
- Status filter as horizontal pill/chip toggles next to section label: All | Ready | Generating | Stale | Error
- Active filter pill gets teal text/underline matching nav active state pattern
- Search bar persistently visible above the feed list, below filters -- searches by title and ticket ID
- Search is client-side text filtering (not semantic search -- that's the existing separate feature)

### Data fetching & real-time
- Read context_pages directly via Supabase client (RLS already configured) -- follows project constraint "Supabase for reads, Python API for actions"
- Supabase Realtime subscription on context_pages table for live status updates (FEED-04) -- channel must be properly cleaned up on unmount (React Strict Mode double-invoke concern from STATE.md)
- No new backend API endpoint needed for listing
- Regenerate and generate actions still go through Python backend API (existing endpoints)

### Dashboard home composition
- Keep existing greeting + integration count header
- Add summary stat cards below greeting: total pages, ready count, generating count (simple inline stats, not heavy cards)
- Add "Recent Context" section showing last 5 context pages in the same compact row format as the feed
- Row clicks navigate to /dashboard/context/[id] detail view
- "View all context" link at bottom navigates to /dashboard/context feed
- Keep existing integration status list below recent context
- Activity preview section NOT included now -- that's Phase 18's scope
- Integrations section always visible; "Recent Context" section only appears when context pages exist

### Detail view (/dashboard/context/[id])
- Separate route (full page), not slide-over panel -- clean URL, shareable, matches FEED-05 requirement
- Back link to context feed at top
- Header: title, ticket identifier (mono), status dot, relative generation timestamp
- Action buttons: Copy Prompt, Regenerate, link to Linear ticket
- Content rendered as parsed markdown with proper headings, code blocks, formatting (5 sections: origin story, business requirements, technical decisions, related work, AI prompt)
- AI Implementation Prompt section highlighted with a dedicated copy button -- this is the hero feature
- "Copy Prompt" copies ONLY the AI prompt section (not full content) -- engineers paste this into Cursor/Claude Code
- Sources section at bottom showing source type badge, title, relevance percentage
- Regenerate triggers immediately (no confirmation dialog) -- button shows spinner, toast confirms, status updates via Realtime

### Empty states
- Feed empty state: dimmed/ghost mock rows showing the layout shape, centered text "No context pages yet", CTA button "Generate First Page"
- CTA navigates to an inline ticket ID input where user types a ticket identifier and clicks Generate (uses existing generateContextPage API)
- Dashboard home: integrations section always shows; "Recent Context" section conditionally appears only when pages exist; no separate empty state on home page

### Claude's Discretion
- Exact spacing, padding, and typography sizing within the compact rows
- Whether to use react-markdown or a lighter markdown renderer for the detail view
- Skeleton loading state layouts for feed and detail pages
- Pagination approach if context pages list grows large (cursor vs offset vs infinite scroll)
- Status dot color mapping (current page uses green/yellow/orange/gray)
- Search debounce timing
- Sort order (likely updated_at DESC but Claude can adjust)

</decisions>

<specifics>
## Specific Ideas

- The compact row design should match the integration list aesthetic on the current home page (rounded-xl border, divide-y, hover:bg-muted/40)
- Status filter pills should feel like they belong with the teal underline nav pattern -- minimal, not heavy tab components
- The AI prompt section in the detail view is the product's hero feature -- it should be visually distinct (perhaps a code-block-like container with its own copy button)
- "Copy Prompt" feedback should be a toast notification via Sonner (already set up in Phase 16)
- Dashboard home stat numbers should use font-mono tabular-nums (matching the "3/5 connected" pattern)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/web/src/app/dashboard/page.tsx`: Current home page with integration list -- pattern to follow for compact rows and section structure
- `apps/web/src/app/dashboard/context/page.tsx`: Current ticket-lookup page -- will be replaced with the feed; existing API calls (getContextPage, generateContextPage, searchContext) remain useful
- `apps/web/src/lib/api.ts`: Has ContextPageResponse type, getContextPage(), generateContextPage(), searchContext() -- detail view and generate actions use these directly
- `apps/web/src/components/ui/skeleton.tsx`: Skeleton component with shimmer-sweep animation for loading states
- `apps/web/src/components/ui/sonner.tsx`: Toast notifications already configured with dark theme
- `apps/web/src/lib/supabase/client.ts`: Browser Supabase client for direct reads and Realtime subscriptions
- Existing shadcn components: Button, Input, Card, Label, DropdownMenu

### Established Patterns
- Dark OKLCH token system from Phase 15 -- all surfaces use semantic tokens (bg-background, bg-card, bg-elevated)
- Section labels use `section-label` class (monospace uppercase tracking)
- Data identifiers use `font-mono tabular-nums` (ticket IDs, timestamps, counts)
- Skeleton loading states match populated layout shape
- Stagger animation via `animate-fade-in-up` class
- Integration list uses rounded-xl border with divide-y for row separation

### Integration Points
- `/dashboard/context/page.tsx`: Replace current lookup page with feed list component
- `/dashboard/context/[id]/page.tsx`: New route for context page detail view
- `/dashboard/page.tsx`: Extend with recent context section and summary stats
- Supabase RLS on `context_pages` table: workspace_data policy already allows reads for workspace members
- `context_pages` table columns: id, workspace_id, ticket_id, ticket_identifier, title, content, status, sources (JSONB), generated_at, generation_model, generation_tokens_used, created_at, updated_at

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 19-context-feed-dashboard-home*
*Context gathered: 2026-03-04*
