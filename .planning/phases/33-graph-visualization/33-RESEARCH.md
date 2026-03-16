# Phase 33: Graph Visualization - Research

**Researched:** 2026-03-16
**Status:** Complete (user-provided)
**Source:** User research on knowledge graph UI in Next.js (2026 playbook)

## Library Selection

**React Flow v12 (`@xyflow/react`)** — 4.9M weekly npm downloads, native TypeScript, full React component model, built-in dark mode via `colorMode` prop, shadcn/ui component library. Nodes are full React components — Tailwind-styled cards, icons, images. Ships with drag-and-drop, edge drawing, lasso selection, snap-to-grid, keyboard shortcuts.

**Critical limitation:** SVG/DOM rendering. Handles hundreds of complex custom nodes smoothly. At 1,000 nodes, performance degrades. Maintainers state "not intended for 10,000+ nodes."

**Layout engine:** elkjs (Eclipse Layout Kernel compiled to JS, ~800K weekly npm downloads). Supports compound/nested graphs natively, 6+ algorithms (layered, force, stress, radial, tree), 140+ configuration options. Integration: convert React Flow nodes/edges to ELK format → `elk.layout()` async (optionally Web Worker) → map positions back.

## Rendering Strategy

| Scale | Renderer | Best library | Tradeoff |
|-------|----------|-------------|----------|
| <500 nodes | SVG/DOM | React Flow | Full interactivity, rich nodes, CSS styling |
| 500-3,000 | Canvas | Cytoscape.js, G6 | Manual hit detection, no HTML-in-node |
| 3,000-100,000 | WebGL | Sigma.js, Cosmograph | Shader programming, limited text/labels |

**MVP approach:** React Flow with aggressive progressive disclosure keeping visible nodes under 500. Sigma.js escape hatch deferred.

## UX Patterns (from Neo4j Bloom, Obsidian, Heptabase, Capacities, Kumu)

1. **Progressive disclosure** — single most important pattern. Start with one entity + immediate connections (20-50 nodes), expand outward on click
2. **Dark mode** — strongly preferred for graph visualization. Glowing nodes on dark background creates emotional resonance
3. **Semantic zoom** — swap node components based on zoom level: full cards → pills → dots
4. **Contextual sidebars** — click node → sidebar with details, not modal/navigation away
5. **Color coding by entity type** — consistent across all views
6. **Mini-map** — React Flow ships `<MiniMap />` built-in
7. **Search + highlight** — filter visible nodes and highlight matches
8. **Animated transitions** — smooth layout changes

## Layout Algorithms

- **Force-directed (organic)** — default exploration view. ForceAtlas2 / D3-force reveals natural clusters
- **ELK compound** — structured grouping by entity type (compound graph support)
- **ELK radial** — ego-centric exploration from focal node
- **Recommendation:** ELK as primary layout engine with toggle between organic/grouped/focused views. Run in Web Worker.

## Libraries to Skip

- Cytoscape.js — clunky React integration, utilitarian aesthetics
- G6 (AntV) — Chinese-first documentation, small non-China community
- Reagraph — small community, limited editing, no rich HTML nodes
- vis-network — dated aesthetics, sporadic updates
- D3-force — physics engine only, not a visualization library
- yFiles — $17K/seat, not viable for startup

## Implementation Notes

- React Flow has NO built-in layout — must pair with elkjs
- Undo/redo requires custom implementation (command pattern + Zustand)
- State management: Zustand store + React Flow hooks
- Dark mode: `colorMode="dark"` prop + custom Tailwind theming
- Glow effects: CSS box-shadow with color-mix (not filters — better perf)

---
*Phase: 33-graph-visualization*
*Research completed: 2026-03-16 (user-provided)*
