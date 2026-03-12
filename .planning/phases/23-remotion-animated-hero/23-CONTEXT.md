# Phase 23: Remotion Animated Hero - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the current static demo.mp4 hero video with a Remotion-powered animated product walkthrough on the landing page. The animation showcases the ContextOS flow (ticket -> source search -> context page) using stylized UI mockups rendered via @remotion/player. Headline text and CTAs remain as HTML. Research modern 2026 landing page animated hero best practices to inform implementation.

</domain>

<decisions>
## Implementation Decisions

### Animation Content
- 3-scene product walkthrough showing the core ContextOS value prop:
  - Scene 1 (0-3s): Ticket card (ENG-42) slides in, details populate
  - Scene 2 (3-7s): Source icons (Slack, GitHub, Linear) activate one by one with progress bars filling
  - Scene 3 (7-11s): Context page materializes with sections fading in sequentially, AI prompt section highlights
- Stylized mockup fidelity — recognizable as ContextOS but simplified for animation (rounded corners, teal borders, brand colors, focus on motion not pixel-perfect detail)
- ~10-12 second total duration per loop

### Delivery Format
- @remotion/player embedded directly in the page (real-time React rendering, no pre-rendered video file)
- Replaces the existing demo.mp4 entirely — no video element needed
- Player container keeps the existing scroll-driven perspective effect (rotateX + scale transform that flattens on scroll)

### Visual Style
- Linear/Vercel minimal aesthetic — clean, precise motion
- Spring easing (0.34, 1.56, 0.64, 1) consistent with Phase 15 dashboard animations
- Stagger delays (100-150ms between elements)
- Subtle scale on enter (0.95 -> 1)
- Teal glow (#00D4AA) on active/progress elements
- Dark #0A0A0F background matching landing page
- Card shadows + glass borders (rgba white borders)
- No particles, no noise effects
- Source icons use their real brand colors (Slack purple/green/yellow, GitHub white, Linear purple) — teal only for progress/active states

### Playback Behavior
- Auto-play on page load, loops continuously
- ~1 second pause between loop end and restart
- No user interaction required to trigger

### Page Structure
- Headline ("Stop gathering context..."), subheadline, badge, and CTAs remain as regular HTML with existing CSS transitions
- Remotion Player renders only the product walkthrough area (replaces the current video element)
- SEO, text selection, and responsive text behavior preserved via HTML

### Claude's Discretion
- Exact Remotion composition structure and component decomposition
- Spring animation parameters and timing fine-tuning
- How to handle the loop-to-restart transition (fade, reset, or smooth)
- Responsive sizing of the Player at different breakpoints
- Whether to lazy-load the Remotion Player for performance
- Research findings on modern landing page hero best practices (2026) to inform motion design choices

</decisions>

<specifics>
## Specific Ideas

- The 3-scene flow mirrors the actual product: ticket in -> sources searched -> context out
- Source icons should use real brand colors so visitors instantly recognize their tools
- The perspective tilt effect on the Player should match the current demo.mp4 behavior exactly (rotateX 12deg at top, flattens to 0 on scroll, scale 0.88 -> 1.0)
- Animation should feel like Linear's or Vercel's hero — premium SaaS quality, not flashy
- Research modern 2026 landing page animated hero patterns for best practices before implementation

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Hero.tsx` (apps/web/src/components/landing/Hero.tsx): Current hero with scroll-driven perspective logic (rotateX, scale transforms) — reuse the scroll handler and transform math
- Landing page CSS: `.landing-theme` scope, teal gradient text (`.teal-gradient-text`), `.btn-primary`, `.btn-ghost` button styles
- `lucide-react`: Icon library already installed — may need source-specific icons or SVGs
- PostHog tracking: `posthog.capture("cta_hero_click")` pattern for CTA analytics

### Established Patterns
- CSS-only animations preferred (Phase 15) — but Remotion is justified here as it renders video-like compositions, not simple transitions
- Landing page scoped under `.landing-theme` to avoid dashboard CSS collision (Phase 13)
- Spring curve `cubic-bezier(0.34, 1.56, 0.64, 1)` used across dashboard — same spring feel in Remotion
- Dark brand identity: #0A0A0F background, #00D4AA teal, dot grid overlay

### Integration Points
- `Hero.tsx` component replacement — same file, same export, same position in landing page
- `apps/web/package.json` — needs `@remotion/core`, `@remotion/player`, and potentially `remotion` dev dependency
- Landing page `(landing)/page.tsx` — imports Hero, no changes needed if export stays the same
- `demo.mp4` in `apps/web/public/` — can be removed after Remotion replaces it

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-remotion-animated-hero*
*Context gathered: 2026-03-08*
