# Phase 33: Graph Visualization - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Interactive React graph explorer for ticket context — users visually explore knowledge graph nodes (people, decisions, PRs, messages, code, documents, meetings) and edges as an interactive network. Two placements: embedded in context page detail view as a tab, and standalone /dashboard/graph route. Uses the existing Graph Explorer API (Phase 27) that returns nodes[] + edges[] JSON.

</domain>

<decisions>
## Implementation Decisions

### Library & Rendering
- Use React Flow v12 (`@xyflow/react`) — full React component model, native TypeScript, built-in dark mode, zoom/pan/drag
- Pair with elkjs for layout computation (run in Web Worker to keep UI responsive)
- Ship Organic (force-directed) layout only for MVP — Grouped and Radial deferred unless needed
- SVG/DOM rendering — handles the 50-200 node range easily
- No additional graph libraries needed for v1

### Node Visual Design
- 8 entity types, each with distinct OKLCH color tuned for equal perceptual brightness on dark backgrounds
- Entity types: Ticket (violet), Person (pink/rose), Decision (amber), PR/MR (green), Message (blue), Code (teal/primary), Notion Page (cool gray-blue), Meeting (orange)
- Use Lucide icons per entity type (NOT emoji) — matching existing SOURCE_TYPE_CONFIG patterns: CheckCircle2 for Ticket, User for Person, Lightbulb for Decision, GitPullRequest for PR, MessageSquare for Message, Code2 for Code, FileText for Notion, Video for Meeting
- Three-tier semantic zoom based on React Flow's viewport zoom level:
  - Full detail cards (zoom > 1.5): rounded card with icon, name, metadata, type badge, colored border + glow
  - Compact pills (zoom 0.6–1.5): small rounded pill with icon dot + short label (identifier or name)
  - Glow dots (zoom < 0.6): colored circles with box-shadow glow — galaxy overview
- Node backgrounds use `var(--elevated)` (not `var(--card)`) on the `var(--bg)` canvas for sufficient contrast
- Glow as semantic hierarchy: root ticket = strong glow, selected = pulse-ring, hovered = medium, resting = none/minimal

### Edge Styling
- Edges subtle by default (low opacity), prominent on hover or when connecting to selected/hovered node
- Relationship types distinguished by line pattern:
  - authored/created: solid line, directional arrow
  - mentions/references: dashed line, directional arrow
  - blocks/depends_on: thicker line, red-tinted
  - related_to (generic): thin, muted, no arrow
- Hover an edge: floating label shows relationship type at midpoint
- Connected nodes brighten on hover; unconnected nodes dim to 30% opacity

### Detail Panel (Click Interaction)
- Click node → compact floating popover near the node (minimalist: entity name, type icon, 2-3 key properties, connected count)
- Popover has "Expand →" action that opens a narrow right sidebar panel with full details + connection list
- Clicking a connection row in the sidebar pans the graph to that node, selects it, updates the panel — "walk the graph" interaction
- Esc or X closes popover/sidebar
- This hybrid approach keeps the graph uncluttered by default while providing depth on demand

### Graph Embed in Context Page (GRAPH-02)
- Tab-based approach: "Content" | "Graph" tabs in the main content area of /dashboard/context/[id]
- Sources sidebar stays visible in both tabs
- Graph tab uses the same <GraphExplorer /> component as standalone page, with fitView on mount
- Tab switch preserves scroll position in the Content tab

### Standalone Graph Page (GRAPH-03)
- Route: /dashboard/graph
- Search-first empty canvas as initial state — prominent search bar, user types ticket ID or name to start exploring
- Below search: "Recent" row showing recently viewed context page ticket IDs as quick-start chips
- After search: graph loads the ticket's subgraph at depth 2 centered on screen
- Top bar shows: page title, node/edge counts
- Entity type filter chips in topbar for quick type-based filtering

### Controls
- Floating pill bar at bottom-center of graph canvas: zoom in/out, fit view, layout mode, search (⌘K), filter toggle, minimap toggle
- React Flow's built-in <MiniMap /> component in bottom-right corner

### Empty/Loading/Error States
- Loading: pulsing skeleton dots at estimated positions, graph builds progressively as layout computes
- Empty (no graph data): message "This ticket hasn't been processed yet" + "Generate Context" CTA button
- Error: retry button with clear error message

### Claude's Discretion
- Exact zoom thresholds for semantic zoom transitions (suggested 0.6 and 1.5 but can adjust)
- Expand/collapse node interaction affordance (e.g., +N badge vs button in popover)
- Controls bar exact icon choices and ordering
- Animation spring curves and transition durations (match existing cubic-bezier(0.34, 1.56, 0.64, 1) from globals.css)
- Exact OKLCH values for entity colors (ensure 40°+ hue separation between adjacent colors at dot scale)
- Whether to use React Flow's `colorMode="dark"` or fully custom theming

</decisions>

<specifics>
## Specific Ideas

- "Neo4j Bloom meets Linear" aesthetic — glowing nodes on dark background with precise, minimal chrome
- Glow effects via CSS box-shadow with color-mix (not filters — better performance)
- Semantic zoom should feel like "zooming into a galaxy" — dots coalesce into pills, pills expand into cards
- The "walk the graph" interaction (click connection → navigate to node) is the core engagement loop
- Search in standalone page should work like ⌘K command palette — fast, keyboard-navigable
- Hover dimming (30% opacity on unconnected nodes) creates a focus effect that makes individual relationships legible in dense graphs
- UI concepts HTML mockup at `.planning/phases/33-graph-visualization/graph-ui-concepts.html` for visual reference
- Design critique identified key risks: ensure color discrimination at dot zoom level, use glow purposefully (not decoratively), and define the expand/collapse affordance clearly

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/routers/graph.py`: Graph Explorer API at `GET /api/graph/{ticket_identifier}` — returns `GraphNeighborhoodResponse` with nodes[], edges[], metadata. Supports depth (1-5) and limit (1-200) query params
- `traverse_graph()` SQL function: recursive CTE traversal with workspace scoping
- `graph_ops.compute_fingerprint()`: fingerprint-based node lookup
- Entity colors in `apps/web/src/app/dashboard/activity/types.ts`: `INTEGRATION_COLORS` map — can extend for graph entity colors
- Source type config in `apps/web/src/app/dashboard/context/[id]/page.tsx`: `SOURCE_TYPE_CONFIG` with icons and group colors
- `globals.css`: OKLCH dark theme tokens, spring-curve animations, section-label utility, noise/grain textures
- shadcn/ui components: Card, Button, Skeleton, etc.
- Lucide icons already used throughout: CheckCircle2, GitPullRequest, Code2, FileText, MessageSquare, Video, User, Lightbulb

### Established Patterns
- Dashboard pages use `animate-fade-in-up` for page transitions
- `stagger-children` for sequential element entrance animations
- `section-label` class for monospace uppercase section headers
- `Skeleton` component for loading states
- Two-column layout in context detail page: sources sidebar (220px) + main content area
- Tab pattern not yet used in the dashboard — will be a new pattern to introduce

### Integration Points
- `apps/web/src/app/dashboard/context/[id]/page.tsx`: Add "Content" | "Graph" tab bar above the main content area
- `apps/web/src/app/dashboard/graph/page.tsx`: New route for standalone graph explorer
- `apps/web/src/lib/api.ts`: Add API function to call graph endpoint
- `apps/web/src/app/dashboard/layout.tsx`: Add "Graph" nav item to sidebar navigation

</code_context>

<deferred>
## Deferred Ideas

- Grouped (compound) and Radial layout modes — add if users request after MVP ships
- Graph diff view (how the knowledge graph changed over time) — GRAPH-05 in v2 requirements
- Graph-based search (find all nodes related to a person/decision) — GRAPH-06 in v2 requirements
- Click entity mentions in markdown content to jump to Graph tab with that entity focused — nice-to-have, Phase 33.1
- Right-click context menu on nodes ("Expand connections", "Navigate to source", "Pin/Unpin") — Phase 33.1
- Sigma.js WebGL fallback for 1000+ node graphs — only if scale demands it

</deferred>

---

*Phase: 33-graph-visualization*
*Context gathered: 2026-03-16*
