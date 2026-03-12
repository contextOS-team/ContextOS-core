# Phase 22: Real-time Context Generation Progress UI - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the silent toast-based context generation flow with a real-time, animated progress experience. When a user triggers generation, they see each integration source being searched with live feedback (step status, result counts), driven by real backend events via SSE. Only connected integrations appear. The progress UI lives inline in the context feed and transitions smoothly into the completed context card before auto-navigating to the detail page.

</domain>

<decisions>
## Implementation Decisions

### Progress Data Delivery
- Use **Server-Sent Events (SSE)** for real-time progress updates
- New `GET /api/context/{ticket}/generate-stream` endpoint that runs generation inline and streams progress events as each step completes
- If client disconnects mid-generation, server continues to completion
- **Keep the existing POST /generate endpoint** as a fallback for programmatic consumers (MCP server, API key users) — no breaking changes
- On disconnect/navigate-away, existing **Supabase Realtime** subscription picks up the final status change (generating -> ready) when user returns — no SSE reconnection needed

### Progress Animation Design
- **Vertical step list** layout: steps stack vertically, each row has icon + source label + status text
- Active step pulses/shimmers, completed steps show checkmark + result count, waiting steps show empty circle
- Progress UI appears **inline in the context feed**, expanding from the generating card row — user can still see other cards above/below
- **CSS transitions + keyframes only** — no framer-motion. Build on existing `shimmer-sweep`, `event-enter`, `fade-in-up` keyframes
- **Monochrome teal icon scheme** — muted-foreground when waiting, teal when active, foreground when complete. Source names provide identification, no brand colors

### Generation-to-Result Transition
- On completion: all steps show checkmarks, then **collapse animation** into the normal context card row (title, source count, ready dot)
- After collapse, **auto-navigate** to `/dashboard/context/{id}` detail page
- **Collapse timing: Claude's discretion** — tune based on what feels right with CSS animations
- On **error**: failed step turns red with error icon and message. Completed steps stay green. Show `[Retry]` and `[Dismiss]` buttons inline

### Source Step Granularity
- **One step per connected integration** + a final synthesis step:
  - Slack (messages)
  - GitHub (PRs + code combined)
  - Notion (pages)
  - Fathom (meetings)
  - Linear (comments & context)
  - Synthesize (AI generation)
- Total 3-6 visible steps depending on which integrations are connected
- **Disconnected integrations are completely hidden** — no "not connected" rows
- Result counts are **specific per type**: "Found 2 PRs, 5 code files" not "Found 7 items"
- Steps with **0 results show as completed** with "No messages found" — honest and transparent
- Integration status fetched via existing `getIntegrationStatus()` API call before starting generation to determine which steps to show

### Claude's Discretion
- Exact collapse-to-card animation timing before auto-navigate
- CSS keyframe details (easing curves, durations, stagger delays)
- Progress bar inclusion (shown in mockup but optional if it clutters the UI)
- Exact shimmer/pulse animation for active step
- How the SSE endpoint handles concurrent generation requests for the same ticket

</decisions>

<specifics>
## Specific Ideas

- Vertical step list mockup was selected with this exact feel:
  ```
  Generating context for CON-51

  checkmark Slack      Found 3 messages
  checkmark GitHub     Found 2 PRs, 5 files
  dot       Notion     Searching pages...
  circle    Linear     Waiting
  circle    Synthesize Waiting

  progress-bar  3/6
  ```
- The progress should feel like watching the system work — each step animating in as it starts, results counting up as they're found
- Error state preserves completed steps (green checkmarks) and only marks the failed step red with Retry/Dismiss buttons
- Reference: Perplexity's source-searching animation, Vercel's deployment log streaming — that level of real-time visibility

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useContextPagesRealtime` hook: Already subscribes to context_pages changes — handles the fallback when user returns after navigating away
- `getIntegrationStatus()` API: Returns which providers are connected per workspace — use to determine which steps to show
- `generateContextPage()` API client function: Current trigger — keep for programmatic use, add new SSE client function alongside
- CSS keyframes in globals.css: `shimmer-sweep`, `event-enter`, `fade-in-up`, `scale-in`, `step-enter` — build progress animations on these
- `apiFetch` wrapper: Handles auth tokens — will need a parallel `apiSSE` or `apiFetchStream` for EventSource connections with auth

### Established Patterns
- CSS-only animations (no framer-motion) — all transitions use @keyframes and CSS transitions
- Supabase Realtime for live updates — postgres_changes on context_pages table
- FastAPI BackgroundTasks for async generation — SSE endpoint will run inline instead but pattern is understood
- Dark theme with teal accents — monochrome icons with teal for active states

### Integration Points
- `backend/src/services/synthesis.py:generate_context_page()` — needs to be refactored to yield progress events per step instead of running silently
- `backend/src/services/linking.py:find_related_content()` — runs explicit refs + hybrid search. Needs to be split into per-source steps that can report progress individually
- `backend/src/routers/context.py` — add new SSE endpoint alongside existing POST /generate
- `apps/web/src/app/dashboard/context/page.tsx` — context feed page, needs inline progress component for generating cards
- `apps/web/src/lib/api.ts` — add SSE client function with auth header support
- `backend/src/routers/integrations.py:get_integration_status()` — already returns connected providers, frontend calls this before generation

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-realtime-generation-progress-ui*
*Context gathered: 2026-03-06*
