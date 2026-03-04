# Phase 17: Onboarding Wizard - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

4-step guided onboarding wizard (workspace name, connect Linear, optional sources, first context page) that new users complete before accessing the dashboard. Persists across browser refreshes and OAuth redirects. No dashboard changes, no new integrations — just the wizard flow replacing the Phase 16 placeholder at /onboarding.

</domain>

<decisions>
## Implementation Decisions

### Progress indicator
- Minimal dot stepper — 4 dots: filled for completed, teal ring for active, gray for upcoming
- No step labels in the indicator itself — step title and description shown in the content area below
- Positioned above the step content inside the centered card

### Wizard layout
- Centered card on dark background (bg-background)
- ContextOS logo/wordmark above the card
- Step content swaps inside the card with fade crossfade transition
- Card uses elevated surface level (bg-elevated) for visual depth against background

### Step transitions
- Fade crossfade between steps — current step fades out (opacity 1→0), next fades in (0→1)
- CSS-only transition (~200ms) — no Framer Motion, consistent with Phase 15 zero-bundle approach
- Back button available on steps 2-4 — users can revisit previous steps

### Integration connection UX (Steps 2 & 3)
- Full-page OAuth redirect for all integrations — same pattern as existing integrations page
- Reuse existing connect handlers from @/lib/api (connectLinear, connectSlack, etc.)
- Database-backed state preservation — wizard reads current_step from user_onboarding_state on mount, no cookies needed
- Auth callback updated to redirect to /onboarding when onboarding incomplete (already done in Phase 16)

### Success confirmation (ONB-08)
- CSS-only animated checkmark when integration connects successfully
- Teal circle with check icon scales in using Phase 15 spring curve (cubic-bezier 0.34, 1.56, 0.64, 1)
- ~400ms duration, teal (#00D4AA) color
- Auto-advance to next step after checkmark animation completes (~1s total)

### Step 3: Optional sources
- 2x2 icon grid layout with source cards (Slack, GitHub, Notion, Fathom)
- Each card shows brand logo + name, click to initiate OAuth connect
- Connected sources show teal checkmark overlay
- "Skip" and "Continue" buttons below the grid — user can skip all optional sources

### Step 4: First context page
- Attempt real context generation from user's Linear tickets
- If pipeline unavailable or no tickets: fall back to a realistic sample/mock context page
- While generating (10-30s): show skeleton preview of context page layout + rotating progress messages ("Analyzing your tickets...", "Generating context...")
- Skeleton uses Phase 15 shimmer-sweep animation

### Completion flow
- After step 4 content renders, show celebration moment: "You're all set!" with teal "Go to Dashboard" CTA button
- Clicking CTA marks onboarding complete (sets completed_at in user_onboarding_state) and redirects to /dashboard

### State persistence (ONB-06, ONB-07)
- Entirely database-backed via user_onboarding_state.current_step
- Wizard queries DB on mount to determine starting step
- Each step completion updates current_step in DB before advancing
- Browser close + return resumes at last completed step — no cookie needed
- OAuth redirect returns to /onboarding, wizard reads step from DB

### Claude's Discretion
- Exact card dimensions and padding
- Step title and description copy for each step
- Progress message rotation timing during generation
- Sample/mock context page content and structure
- Whether to show a subtle "back" text link or icon button
- Error handling for failed OAuth connections within the wizard
- Whether workspace name input has validation (min/max length)

</decisions>

<specifics>
## Specific Ideas

- Centered card should feel cohesive with the auth page form panel (same elevated surface, similar proportions)
- The celebration moment at the end should feel earned — "you set up something real, not just clicked through a tour"
- Integration grid in step 3 should use the same brand logos from @/components/icons/brand-logos
- Linear being required in step 2 means the "Continue" button should be disabled until connected

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `@/lib/api`: connectLinear, connectSlack, connectGithub, connectNotion, getIntegrationStatus — full OAuth connect/disconnect handlers
- `@/components/icons/brand-logos`: LinearLogo, SlackLogo, GitHubLogo, FathomLogo, NotionLogo — all brand icons
- `@/components/ui/skeleton`: Skeleton component with shimmer-sweep animation
- `@/components/ui/button`: Button component with teal primary variant
- `sonner`: Toast notifications already configured (Phase 16)
- `globals.css`: Spring curve cubic-bezier(0.34, 1.56, 0.64, 1), stagger-children, skeleton-shimmer

### Established Patterns
- OAuth flow: connectFn returns { authorization_url }, then window.location.href redirect
- Dark OKLCH tokens: bg-background (L1), bg-card (L2), bg-elevated (L3) surface hierarchy
- CSS-only animations preferred over JS libraries (Phase 15 decision)
- Supabase client for reads, Python API for actions

### Integration Points
- `/onboarding/page.tsx`: Replace Phase 16 placeholder with wizard component
- `/onboarding/layout.tsx`: Auth guard already in place, wraps in bg-background
- `user_onboarding_state` table: current_step (1-4), completed_at fields
- Auth callback (`/auth/callback/route.ts`): Already redirects incomplete onboarding to /onboarding
- Dashboard layout gate: Already redirects to /onboarding?from=dashboard if not completed
- FathomConnect component: Existing API key form pattern for non-OAuth integrations

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-onboarding-wizard*
*Context gathered: 2026-03-04*
