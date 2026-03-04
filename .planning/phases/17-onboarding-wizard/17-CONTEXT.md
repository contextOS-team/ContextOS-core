# Phase 17: Onboarding Wizard - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning
**Design methodology:** Interface Craft (Josh Puckett) — decisions driven by systematic design critique

<domain>
## Phase Boundary

4-step guided onboarding wizard (workspace name, connect Linear, optional sources, first context page) that new users complete before accessing the dashboard. Persists across browser refreshes and OAuth redirects. No dashboard changes, no new integrations — just the wizard flow replacing the Phase 16 placeholder at /onboarding.

</domain>

<decisions>
## Implementation Decisions

### Progress indicator — Minimal dot stepper
- 4 dots: filled teal for completed, teal ring for active, muted outline for upcoming
- No labels in the indicator — step title and description shown in the content area below
- Positioned above the step content inside the centered card
- **Rationale:** A numbered step bar with connecting lines communicates "this is going to take a while" — psychologically counterproductive. Dots say "almost there." Progressive disclosure: show only what's needed for the current task.

### Wizard layout — Centered card (NOT split layout)
- Full-width centered card on bg-background (L1), card uses bg-card (L2) surface with subtle border
- ContextOS wordmark above the card, small, not competing with step content
- Max-width ~480px — tight enough to feel focused, wide enough for the source grid in step 3
- `dashboard-grain` on the background for texture continuity with dashboard
- **Rationale:** Auth pages use a split layout, but that wastes 50% of viewport for a wizard with changing content across 4 steps. Centered card focuses all attention on the current task — benchmark: Linear and Vercel onboarding flows.

### Step transitions — Crossfade, CSS-only
- Outgoing step opacity 1→0, incoming step opacity 0→1, ~200ms using spring curve `cubic-bezier(0.34, 1.56, 0.64, 1)`
- NOT horizontal slide — slide implies spatial pagination which fights the vertical dot stepper
- CSS-only with transition on opacity, no Framer Motion (Phase 15 zero-bundle decision)

### Navigation — Back button on steps 2-4
- Subtle text link ("Back") — position is Claude's discretion (top-left of card or below primary action)
- Forward: teal primary button with step-specific label ("Continue" / "Connect Linear" / "Go to Dashboard")
- Button disabled when step requirements unmet (e.g., step 2 disabled until Linear connected)

### Integration connection UX (Steps 2 & 3) — Full-page OAuth redirect
- Full-page redirect to OAuth provider, returning to /onboarding — same pattern as integrations page
- Reuse existing connect handlers from `@/lib/api` (connectLinear, connectSlack, connectGithub, connectNotion)
- NOT popup window — popups blocked by many browsers, adds postMessage complexity, backend callback routes not built for popup flows
- After OAuth return: wizard mounts, reads current_step from DB, detects newly connected integration, shows success confirmation

### Success confirmation (ONB-08) — CSS spring scale-in checkmark
- Teal circle with white checkmark icon scales in from 0→1 using existing `animate-scale-in` class
- Circle replaces the "Connect" button position — direct feedback at the point of attention
- Spring overshoot from cubic-bezier(0.34, 1.56, 0.64, 1) gives satisfying "pop"
- After ~800ms, auto-advance to next step via crossfade transition
- No Lottie, no SVG path animation — CSS-only, zero dependencies

### Step 3: Optional sources — 2x2 icon grid
- Four cards in 2x2 grid: Slack, GitHub, Notion, Fathom
- Each card: brand logo (from `@/components/icons/brand-logos`) + name
- Click triggers OAuth redirect (same flow as step 2)
- Connected sources show teal checkmark overlay on the card
- Two buttons below: "Skip" (text/ghost variant) and "Continue" (teal primary, always enabled — all sources optional)
- **Rationale:** Developers hate being forced through optional setup. Skip must be prominent and guilt-free.

### Step 4: First context page — Real generation with sample fallback
- Attempt real context generation from user's Linear tickets
- If pipeline unavailable or no assigned tickets: show a realistic sample/mock context page demonstrating ContextOS value
- The user sees what ContextOS delivers either way — this is the "aha" moment
- While generating (~10-30s): shimmer skeleton matching real context page layout + rotating progress text ("Pulling your tickets...", "Analyzing context...", "Generating prompt...")
- Skeleton uses existing `skeleton-shimmer` class; reveal feels like skeleton filling in with real content

### Completion flow — Celebration moment + CTA
- After step 4 content renders, transition to completion state: "You're all set!" heading
- Brief description ("Context pages will generate automatically as tickets are assigned.")
- Teal "Go to Dashboard" button — CTA sets `completed_at` in user_onboarding_state, redirects to /dashboard
- **NOT auto-redirect** — user should feel agency. They completed something, they choose when to proceed. Auto-redirect at the end of a flow feels like being pushed.

### State persistence (ONB-06, ONB-07) — Database-backed only
- Single source of truth: `user_onboarding_state.current_step` column
- Wizard reads current_step from DB on mount to determine starting step
- Each step completion updates current_step in DB before advancing UI
- OAuth redirect returns to /onboarding, wizard mounts and reads step from DB — seamless resume
- Browser close + return resumes at last completed step — no cookie, no localStorage
- Auth callback route already redirects to /onboarding when onboarding incomplete (Phase 16)

### Claude's Discretion
- Exact card dimensions, padding, and border radius
- Step title and description copy for each of the 4 steps
- Back button positioning (top-left text link vs bottom-left below actions)
- Progress message rotation timing during step 4 generation
- Sample/mock context page content and structure for fallback
- Error handling UX for failed OAuth connections within the wizard (toast? inline error? retry?)
- Workspace name input validation rules (min/max length, character restrictions)
- Whether step 4 shows the full 5-section context page or a condensed preview
- FathomConnect inline form handling (API key, not OAuth) — reuse existing component or simplify for wizard

</decisions>

<specifics>
## Specific Ideas

- Centered card should feel focused like Vercel's project setup or Linear's workspace creation — one thing at a time, dark and clean
- The celebration at the end should feel earned — "you set up something real, not just clicked through a tour"
- Linear being required in step 2 is the key gate — must be crystal clear that this is the one non-optional step
- The "Skip" button in step 3 must not feel shameful — optional means optional

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `@/lib/api`: connectLinear, connectSlack, connectGithub, connectNotion, getIntegrationStatus, disconnectFathom — full OAuth connect/disconnect handlers with `{authorization_url}` return pattern
- `@/components/icons/brand-logos`: LinearLogo, SlackLogo, GitHubLogo, FathomLogo, NotionLogo — all brand icons with configurable size/color
- `@/components/ui/skeleton`: Skeleton component with shimmer-sweep animation
- `@/components/ui/button`: Button with primary (teal), outline, ghost variants
- `sonner`: Toast notifications already configured (Phase 16)
- `globals.css`: Spring curve `cubic-bezier(0.34, 1.56, 0.64, 1)`, `animate-scale-in`, `animate-fade-in-up`, `stagger-children`, `skeleton-shimmer`, `dashboard-grain`, `section-label`
- `FathomConnect` component: Existing API key form for non-OAuth integrations (Fathom uses API key, not OAuth)
- `IntegrationCard` component: Card with connect/disconnect UX — may inform wizard card design but is dashboard-specific

### Established Patterns
- OAuth flow: `connectFn()` returns `{authorization_url}` → `window.location.href = url`
- Dark OKLCH token hierarchy: bg-background (L1 oklch 0.13) → bg-card (L2 oklch 0.16) → bg-elevated (L3 oklch 0.19) → bg-overlay (L4 oklch 0.22)
- CSS-only animations preferred over JS libraries (Phase 15 decision)
- Supabase client for reads, Python API for write actions
- Auth pages use split layout (left brand panel + right form) — wizard intentionally departs from this

### Integration Points
- `/onboarding/page.tsx`: Replace Phase 16 placeholder with wizard component
- `/onboarding/layout.tsx`: Auth guard already in place, wraps in `bg-background`
- `user_onboarding_state` table: `current_step` (integer 1-4, default 1), `completed_at` (timestamptz)
- Auth callback (`/auth/callback/route.ts`): Already checks onboarding status, redirects to /onboarding if incomplete
- Dashboard layout gate: Already redirects to /onboarding?from=dashboard if `completed_at` is null
- `handle_new_user` trigger: Auto-creates onboarding row with `current_step=1` on signup

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-onboarding-wizard*
*Context gathered: 2026-03-04*
