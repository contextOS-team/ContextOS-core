# Phase 9: Notion Integration UI Polish - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Polish the Notion integration card UX — replace the flat paginated page list with a collapsed summary view showing page count and last sync time, remove the page list entirely, fix the header vs body page count mismatch to use a single source of truth (integration status endpoint), and ensure visual consistency with other integration cards.

</domain>

<decisions>
## Implementation Decisions

### Summary view
- Page count and last sync time always visible on the card face without expanding
- Error states (sync failures) shown inline on the card face — a red indicator or error text
- During re-sync, the stats line shows live progress: "Syncing... 45 pages imported" replacing the static count
- After sync completes, stats settle back to "360 pages synced"

### Page list removal
- Drop the NotionPages component entirely — users don't need to browse individual pages
- The page list was "proof it works" at best; the page count summary is sufficient
- No search or filter bar needed — there's nothing to search
- The paginated pages endpoint can stay in the API (other consumers may use it) but the frontend won't render it

### Page count source of truth
- Use `pages_synced` from the integration status endpoint as the single canonical count
- Remove the redundant count from the card header display name (currently shows "Daulet's Space - 360 pages")
- Header should show just the workspace name: "Daulet's Space"
- Count lives in the card body stats line instead
- Last sync timestamp comes from the status endpoint (`last_synced_at`), not derived from UI state

### Visual cleanup
- Remove the page count suffix from `notionDisplayName` in the integrations page
- Notion card should match the visual weight of Linear, Slack, GitHub cards — no heavier than peers
- The type badges ('page', 'db entry') and per-row external link icons go away with the page list removal
- Consistent spacing, density, and action placement with other cards

### Claude's Discretion
- Whether re-sync button appears on card face always vs behind a settings expand
- Whether to keep the "Manage access in Notion settings" link (and how to style it)
- Exact layout of the stats line (typography, spacing, separator style)
- Whether the settings expand is still needed at all (given no page list)
- Re-sync button visibility pattern (always visible vs hover-only)

</decisions>

<specifics>
## Specific Ideas

- Live sync progress inline on the card: count updates every 2 seconds as batches commit, then settles to final count
- Keep the existing polling mechanism for sync progress — it works well
- The card should feel like a peer to Linear/Slack/GitHub cards, not an outlier

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `IntegrationCard` component (`integration-card.tsx`): Handles status indicator, connect/disconnect, expandable children pattern
- `formatRelativeTime` utility: Already used for connected_at timestamps, reuse for last sync time
- `getNotionSyncStatus` API function: Returns `sync_status` and `pages_count` for polling
- `getIntegrationStatus` API function: Returns `pages_synced` — the canonical count source

### Established Patterns
- GitHub repos card uses search + scrollable list with max-height — NOT needed here since we're dropping the list
- Slack channels card has a simple expandable settings area — good reference for minimal expand content
- All cards use the same `IntegrationCard` wrapper with `children` prop for expanded content

### Integration Points
- `page.tsx:176`: `notionDisplayName` concatenation — remove the pages_synced suffix
- `page.tsx:241`: `NotionPages` component usage — remove entirely
- `notion-pages.tsx`: Entire file can be removed or kept unused
- `api.ts`: `getNotionPages` function stays in API but is no longer called from the UI
- Backend status endpoint already provides `pages_synced` and `sync_status` fields

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-notion-integration-ui-polish*
*Context gathered: 2026-03-01*
