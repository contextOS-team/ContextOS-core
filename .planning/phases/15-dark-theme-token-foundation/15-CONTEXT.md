# Phase 15: Dark Theme Token Foundation - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Every dashboard and auth surface renders in a brand-tinted dark theme with consistent tokens, navigation, and loading states. This is the visual foundation every subsequent phase (16-20) builds on. No new pages or features — just the token system, DarkModeApplier, navigation restructure, and skeleton primitives.

</domain>

<decisions>
## Implementation Decisions

### Token palette
- Keep blue-violet surface tint (hue 270) — already non-generic, professional for daily use
- Primary color shifts from blue-indigo (hue 250) to teal (~hue 170) to match the landing page brand (#00D4AA)
- Teal used ONLY on actionable/status elements (DS-02) — never as surface decoration
- 4-level surface hierarchy: background → card → elevated → overlay with subtle lightness steps (~0.03-0.05 OKLCH apart) — layers felt more than seen, depth reinforced by borders + shadows
- Must feel premium — not neutral gray shadcn defaults, not flashy

### Typography
- JetBrains Mono already loaded as --font-mono — apply to all data identifiers (ticket IDs, timestamps, counts, API keys) per DS-03
- Monospace uppercase tracking pattern (from landing page) used on section labels ONLY — sparingly applied as a signature element, not broadly

### Navigation
- Keep horizontal top bar (not vertical sidebar) — 4 content links: Home, Context, Activity, Integrations
- Settings and Sign out live in an avatar dropdown menu (not in the main nav row)
- Active state: teal underline only, no background highlight — clean and minimal like Vercel's nav
- Wordmark gets teal gradient treatment + logo matching the landing page

### Skeleton loading
- Shimmer sweep animation (gradient sweeps left-to-right) — premium feel, not pulse/fade
- One reusable `<Skeleton>` primitive component — pages compose their own skeleton layouts from it
- Every dashboard page must have a structured skeleton matching its populated layout shape (DS-09)

### Grain texture
- Dashboard grain more subtle than landing page (~0.8-1% opacity vs landing's 1.5%)
- Daily-use surface should have barely perceptible texture — just enough for depth

### Claude's Discretion
- Animation approach: CSS-only (extend existing stagger-children) vs Framer Motion — pick based on what DS-06 spring-curve requirements actually need
- Grain placement: main background only vs all surfaces — pick what creates the best premium feel
- Loading skeleton exact dimensions and spacing
- DarkModeApplier implementation strategy (must apply .dark to html for Radix portals without breaking .landing-theme scoping)
- Exact OKLCH values for the 4 surface levels
- Error state styling

</decisions>

<specifics>
## Specific Ideas

- "Make sure it feels premium" — the overriding design principle for all token and visual decisions
- Wordmark + logo should match the landing page treatment (teal gradient)
- Linear and Vercel referenced as aesthetic benchmarks (subtle depth, clean nav)
- Dashboard is for daily use — everything should be muted enough to not cause fatigue

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `globals.css`: .dark token block already exists (lines 119-151) with OKLCH values — needs primary hue shift and 4-level surface expansion
- `globals.css`: noise-bg::before pseudo-element already implements grain texture (line 196-206) — reuse with adjusted opacity
- `globals.css`: stagger-children CSS animation already defined (lines 184-192) — potential base for DS-06
- `layout.tsx`: JetBrains Mono already imported and set as --font-mono CSS variable
- 4 shadcn components exist: button, input, card, label — will inherit dark tokens automatically

### Established Patterns
- Landing page CSS scoped under .landing-theme class (landing/layout.tsx wraps in div.landing-theme)
- Landing layout forces dark background via inline `<style>` tag on html/body
- All dashboard colors use semantic tokens (bg-background, text-foreground, etc.) — will auto-switch when .dark applied
- Sidebar component is actually a horizontal top nav bar (misnamed)

### Integration Points
- Root layout (`app/layout.tsx`): .dark class needs to be applied to `<html>` element — DarkModeApplier goes here or in dashboard layout
- Dashboard layout (`app/dashboard/layout.tsx`): wraps content in bg-background — will auto-switch
- Sidebar (`app/dashboard/sidebar.tsx`): needs Activity link added, Settings removed from nav (moves to avatar dropdown), active state changed to teal underline only
- Radix UI portals render at document root — .dark on html ensures they inherit dark tokens (DS-05)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-dark-theme-token-foundation*
*Context gathered: 2026-03-04*
