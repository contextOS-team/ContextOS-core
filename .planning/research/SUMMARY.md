# Project Research Summary

**Project:** ContextOS Dashboard Redesign — v1.1 Milestone
**Domain:** Developer tool SaaS dashboard — onboarding, dark design system, context feed, activity timeline, team settings, auth redesign
**Researched:** 2026-03-04
**Confidence:** HIGH

## Executive Summary

ContextOS's v1.1 milestone is a dashboard redesign targeting six capability areas: guided onboarding, a dark-first design system, a browsable context feed, a real-time activity timeline, team settings, and an auth page rebrand. The research consensus is clear: these features are individually well-understood (with strong precedents from Linear, Vercel, PostHog 3000, and Supabase), but they interact through a shared dark token system that must be built correctly before any other work begins. The stack additions are minimal — five npm packages on top of the existing Next.js 15 / React 19 / Tailwind v4 / shadcn/ui / Supabase foundation — and the architecture stays aligned with what is already in the codebase.

The recommended approach is build-order discipline over feature completeness: token foundation first, then auth and onboarding infrastructure, then the feed features. The most dangerous pitfall is deploying the dark theme without solving the CSS scoping problem across the three distinct theme contexts (landing, dashboard, auth). The second most dangerous is onboarding OAuth redirects destroying wizard state. Both are preventable with a single explicit decision made early: use `.dark` class on layout wrappers, never on `<html>`, and always write onboarding resume state before initiating any OAuth redirect. The entire milestone is buildable with confidence — no unknowns require architectural pivots.

The key differentiator between a template-looking dashboard and a crafted one comes down to three decisions: applying a brand-tinted color temperature to the dark token values (not neutral gray), restricting the teal accent to actionable and status elements only, and using JetBrains Mono consistently on all data identifiers. These are design token decisions, not component work. Research confirms that once the tokens are right, the components built on top will inherit the character without additional effort.

---

## Key Findings

### Recommended Stack

The existing stack (Next.js 15, React 19, TypeScript, Tailwind v4, shadcn/ui, Radix, Supabase, PostHog, Sentry, FastAPI) requires only five new npm packages for this milestone. All five have confirmed compatibility with React 19 and Next.js 15 App Router.

**Core technologies (new additions only):**
- `react-hook-form ^7.71.2` + `@hookform/resolvers ^5.2.2` + `zod ^4.3.6`: per-step validated onboarding form state — the prescribed shadcn/ui pattern; resolvers v5 adds Zod v4 auto-detection; install via `pnpm add react-hook-form @hookform/resolvers zod --filter @contextos/web`
- `motion ^12.34.5`: animated step transitions and timeline stagger — the renamed successor to framer-motion; required only because CSS keyframes cannot do `AnimatePresence` unmount animations and `height:auto` transitions; import from `'motion/react'`
- `nuqs ^2.8.9`: URL-synced filter state for the context feed — gives shareable filtered views, browser back/forward, and RSC re-render triggering; requires `NuqsAdapter` in layout
- `date-fns ^4.1.0`: relative and absolute timestamp formatting in feed and timeline — tree-shakable, ships TypeScript types, the shadcn/ui DatePicker default; use `formatDistanceToNow`, `format`, `parseISO`
- `@stepperize/react ^6.1.0`: onboarding wizard step state machine — type-safe `defineStepper` + `useStepper`; evaluate necessity at Phase 3 (only add if 4+ steps with conditional branching; for 3 linear steps, a `useState` is sufficient)

**Design system additions (zero new npm packages):**
- Ten shadcn/ui components via CLI: `progress command select badge separator avatar tabs dialog skeleton scroll-area`
- A `dashboard-theme` CSS class extending the existing `.dark` block with brand-tinted OKLCH token overrides (background `oklch(0.10 0.012 210)`, card `oklch(0.14 0.014 220)`) to prevent the neutral gray default trap
- A `DarkModeApplier` client component that applies `.dark` to `<html>` only when inside authenticated routes, enabling Radix UI portal dark mode without breaking the landing page

**Explicitly deferred:** `@tanstack/react-query` (premature before caching problems exist), `next-themes` (overkill for a force-dark dashboard with no toggle), `@tanstack/react-virtual` (context feed at MVP scale is under 500 items), `framer-motion` (renamed to `motion` — the same package).

See `.planning/research/STACK.md` for version compatibility matrix and full installation commands.

### Expected Features

**Must have (P1 — this milestone):**
- Dark mode as default across dashboard, auth, and onboarding — removes brand contradiction with the landing page
- JetBrains Mono on all data identifiers (timestamps, ticket IDs, token counts, API keys) — single CSS audit pass, instant "developer tool" signal
- Auth page dark redesign — first impression; a white card login for a dark-brand product destroys trust
- Guided onboarding (steps 1-3: workspace name, connect integration, preferences) — users will not self-onboard from a blank dashboard
- `user_onboarding_state` and `activity_events` database tables — schema prerequisites that block multiple other features
- Context feed list view replacing the lookup-only tab — browsable list with status filtering and free-text search
- Context feed detail view (redesigned) with copy-prompt and regenerate — existing functionality in a new visual design
- Activity timeline (initial version with polling acceptable) — shows the system is alive, builds trust
- Settings page with API key management — required for MCP users, spec'd in v1.0 but not yet in dashboard

**Should have (P2 — second sprint):**
- Supabase Realtime for activity timeline — upgrade from polling to live updates once basic timeline is in use
- Onboarding step 4: first context generation as the "aha moment" — requires Phase 4 pipeline to be stable; plan a mock context page fallback if unavailable
- Context feed keyboard navigation (`j/k/Enter/Esc/r/c`) — developer delight, approximately 50-line implementation
- Animated integration connection confirmation (SVG checkmark draw) in onboarding
- Stale reason indicator on context pages (requires backend to compute `stale_reason`)
- Settings: webhook health indicator (last webhook received per source with green/yellow/red status dots)

**Defer to v2+:**
- Light/dark mode toggle (external users not yet onboarding)
- Context feed right-panel split view (route-based detail is correct for v1)
- Team member invites and role management
- Social OAuth (Google/GitHub)
- API key usage metrics per key

See `.planning/research/FEATURES.md` for full prioritization matrix and competitor analysis tables.

### Architecture Approach

The architecture stays in the existing App Router pattern with targeted, additive changes. Three structural decisions are settled by research and must not be reconsidered: (1) dark theme applied via `.dark` class on each route group's layout wrapper — never on `<html>` — with `DarkModeApplier` extending it to `<html>` only for Radix portal support; (2) onboarding completion checked in `dashboard/layout.tsx` as a server-side redirect, not in middleware, to avoid DB calls on static asset requests; (3) Supabase Realtime subscriptions always extracted to dedicated `lib/hooks/` files with mandatory `removeChannel` cleanup.

**Major components and their responsibilities:**
1. `(onboarding)/layout.tsx + page.tsx` (NEW) — auth-gated route group; 3-step wizard with `@stepperize/react` + `react-hook-form`; step state persisted to `user_onboarding_state` table after each advance
2. `components/dashboard/ContextFeedProvider + ContextFeedList + FilterBar` (NEW) — compound component pattern with shared React context for filter state; client-side filtering against up to 100 pages loaded once; Supabase Realtime for live status updates
3. `lib/hooks/use-realtime-feed.ts + use-context-pages.ts` (NEW) — extracted subscription hooks with mandatory `removeChannel` cleanup; single channel per logical feed
4. `components/dashboard/ActivityPanel + ActivityEventRow` (NEW) — real-time activity timeline consuming `activity_events` via `useRealtimeFeed` hook
5. `dashboard/layout.tsx` (MODIFY) — adds `.dark` class wrapper, `DarkModeApplier`, and onboarding completion gate
6. `(auth)/layout.tsx + login + signup` (MODIFY) — dark-card treatment matching dashboard token system
7. `globals.css` (MODIFY) — dashboard-specific semantic token extensions inside `.dark {}` block with brand-tinted OKLCH values

**New database tables (2):**
- `user_onboarding_state` (user_id PK, step_reached, preferences JSONB, completed_at) — row auto-created on first sign-in via DB trigger; RLS `auth.uid() = user_id`
- `activity_events` (workspace_id FK, event_type, source_type, entity_id, entity_title denormalized, metadata JSONB) — indexed on `(workspace_id, created_at DESC)`; RLS scoped to workspace membership; 30-day retention policy via pg_cron from day one

**New FastAPI backend additions (additive, no existing routes changed):** `emit_activity()` helper as side effect of context generation and OAuth connect; `/api/user/onboarding` GET/PATCH; `/api/user/profile` PATCH; `/api/team/members` GET; `/api/apikeys` GET/POST/DELETE.

See `.planning/research/ARCHITECTURE.md` for complete project structure diff, data flow diagrams, and build order.

### Critical Pitfalls

1. **FOUC white flash on dark dashboard and auth pages** — `bg-background` resolves to near-white before `.dark` class activates. Add `className="dark"` to layout wrapper div as the very first commit of this milestone. Also add a `DarkModeApplier` client component to apply `.dark` to `<html>` for Radix portal support. Without this, every shadcn Dialog/DropdownMenu/Sheet will render with light tokens inside a dark page.

2. **Generic "AI slop" dark theme** — shadcn/ui `.dark` defaults produce neutral gray surfaces with blue primary that look like every Next.js starter template. Fix: override OKLCH values in a `dashboard-theme` block (`oklch(0.10 0.012 210)` for background, teal-tinted card and border values) and restrict teal to actionable/status elements only. This must happen during token definition before any components are built — token decisions propagate everywhere; retrofitting requires touching every component.

3. **OAuth redirect destroying onboarding wizard state** — Every OAuth connect (Linear, Slack) inside the onboarding flow involves a full-page redirect that wipes React state. Fix: write an `onboarding_return=/onboarding?step=N` cookie (10-minute TTL, whitelisted path) before initiating any OAuth redirect; read it in `/auth/callback` to redirect back to the correct wizard step. The existing `handleQuickConnect` in `dashboard/page.tsx` has this exact vulnerability.

4. **Supabase Realtime subscription leaks** — React Strict Mode double-invokes effects in development, creating duplicate subscriptions. Without `supabase.removeChannel(channel)` in effect cleanup, production subscriptions accumulate on navigation. Fix: always extract subscriptions to `lib/hooks/` files with mandatory cleanup; write a mount/unmount test after implementing each subscription to verify channel count returns to baseline.

5. **CSS scoping collision between landing and dashboard themes** — Adding `.dark` to `<html>` globally breaks the landing page which relies on `.landing-theme` for its navy-teal palette. The two themes must never coexist as DOM ancestors. The `DarkModeApplier` pattern (mounts/unmounts `.dark` on `<html>` per route group) is the correct solution. Never import `landing.css` in non-landing layouts.

---

## Implications for Roadmap

Based on research, the following phase structure is recommended. Phases 1-2 are hard blockers for all subsequent work. Phases 3-4 can partially parallelize after Phase 2 schema exists. Phases 5-6 are independent of each other once Phase 2 is complete.

### Phase 1: Dark Theme Token Foundation
**Rationale:** Every UI component in this milestone builds on the dark token system. If tokens are inconsistent or brand-disconnected, every subsequent component will need rework. This phase has zero dependencies and blocks everything else. The research identifies this as the highest-impact foundation work.
**Delivers:** `globals.css` with brand-tinted dashboard token overrides inside a scoped `dashboard-theme` class, `DarkModeApplier` client component, `.dark` class applied to dashboard and auth layout wrappers, visual verification that all existing shadcn components (including portalled dialogs and dropdowns) render correctly in dark mode, JetBrains Mono applied consistently to all data identifier elements.
**Addresses:** Dark mode as default, teal-as-signal design principle, monospace-for-data rule
**Avoids:** FOUC white flash (Pitfall 1), generic dark theme (Pitfall 2), CSS scoping collision (Pitfall 5)
**Research flag:** Standard pattern — well-documented in shadcn/ui Tailwind v4 docs. No additional research needed.

### Phase 2: Auth Page Redesign + Schema Foundation
**Rationale:** Auth pages are the first impression and cannot lag behind the dashboard visually. The `user_onboarding_state` and `activity_events` database schema are infrastructure prerequisites with no upstream dependencies — creating them early unblocks both the onboarding and activity feed phases.
**Delivers:** Dark-themed login and signup pages matching brand palette; `user_onboarding_state` and `activity_events` Supabase migrations with RLS, indexes, and DB triggers; `emit_activity()` FastAPI helper wired into existing context generation and OAuth connect handlers; auth callback updated to route to `/onboarding` when `completed_at` is null; 30-day retention policy for `activity_events`.
**Uses:** Dark tokens from Phase 1; Supabase migration tooling (existing)
**Avoids:** Auth page FOUC (Pitfall 9), activity timeline N+1 query (Pitfall 10 — denormalize `entity_title` at write time in the schema)
**Research flag:** Standard pattern. No additional research needed.

### Phase 3: Onboarding Wizard
**Rationale:** Users cannot self-discover a developer tool dashboard. Onboarding gates dashboard access and ensures the product is experienced in the intended sequence. Depends on Phase 2 schema and Phase 1 tokens.
**Delivers:** `(onboarding)` route group with 3-step wizard (workspace name → connect integration → preferences), step persistence to `user_onboarding_state` after each advance, OAuth redirect state preservation via cookie, server-side onboarding gate in `dashboard/layout.tsx`, skip options for all non-critical integrations, animated step transitions.
**Uses:** `react-hook-form` + `@hookform/resolvers` + `zod` (form validation per step), `@stepperize/react` or `useState` (step state machine — evaluate at planning time), `motion` (step transition animations via `AnimatePresence`)
**Implements:** OnboardingWizard, OnboardingStep components, `/api/user/onboarding` FastAPI endpoints
**Avoids:** OAuth redirect state loss (Pitfall 3), step persistence loss on refresh (Pitfall 8), blocking dead-ends on optional integrations (Pitfall 6), context feed dead-end empty state for onboarding-incomplete users (Pitfall 7)
**Research flag:** `@stepperize/react` has MEDIUM confidence — evaluate step count and branching at planning time. For 3 linear steps with no conditional branching, use `useState` and skip this dependency. Also: Onboarding aha-moment step 4 (first context generation) depends on the LangGraph pipeline stability — plan a mock fallback context page.

### Phase 4: Activity Timeline
**Rationale:** An activity timeline makes the system feel alive and builds trust that the backend is working. It has a firm dependency on `activity_events` table and `emit_activity()` wiring from Phase 2. Start with polling; Realtime is a fast upgrade once the basic feed ships.
**Delivers:** `use-realtime-feed.ts` hook with mandatory cleanup, `ActivityPanel` and `ActivityEventRow` components integrated into `dashboard/page.tsx`, event type icon/color mapping (lucide-react), day-group date dividers, reverse-chronological display with relative timestamps and absolute on hover, contextual empty state with actionable CTA.
**Uses:** `date-fns` (timestamp formatting), Supabase Realtime with `INSERT`-only subscription (polling first, then upgrade), lucide-react icons (existing)
**Implements:** ActivityPanel, ActivityEventRow, useRealtimeFeed hook
**Avoids:** Realtime subscription leaks (Pitfall 4 — hook-extracted cleanup), N+1 queries (entity_title denormalized at write time in Phase 2)
**Research flag:** Standard pattern — Supabase Realtime `postgres_changes` is well-documented. No additional research needed.

### Phase 5: Context Feed
**Rationale:** The context feed replaces the existing lookup-only tab as the primary entry point to context pages — the core dashboard capability. Independent of Phase 4; both can proceed in parallel after Phase 2 schema exists. Phase 1 tokens must be applied before visual work begins.
**Delivers:** `ContextFeedProvider` + `FilterBar` + `ContextFeedList` + `ContextFeedItem` compound components, `use-context-pages.ts` Realtime hook (INSERT + UPDATE), status filter pills (All/Ready/Generating/Stale/Error), URL-synced free-text search and filter state via `nuqs`, context feed detail view with copy-prompt and regenerate, branching empty states with CTAs per user onboarding status (no integrations / integrations connected but no pages / generation in progress).
**Uses:** `nuqs` (URL filter state), Supabase Realtime (live status updates on context pages), compound component pattern with React context for filter sharing
**Implements:** ContextFeedProvider, FilterBar, ContextFeedList, ContextFeedItem, EmptyFeedState, use-context-pages hook
**Avoids:** Dead-end empty state (Pitfall 7 — three branching CTAs per onboarding status), N+1 filter queries (client-side filtering on up to 100 pages loaded once), URL filter state lost on navigation (nuqs persists to URL)
**Research flag:** Standard pattern — compound component, Supabase Realtime, and nuqs URL state are all well-documented. No additional research needed.

### Phase 6: Settings Page
**Rationale:** API key management is required for MCP server users and was spec'd in v1.0 but never surfaced in the dashboard. Settings is independent of the feed phases and can be built any time after Phase 1 tokens, but is lower priority than the feed work.
**Delivers:** `dashboard/settings/page.tsx` with API key list/create/revoke (show full key once on creation with copy button, then prefix-only — GitHub PAT pattern), workspace name editing, notification preference toggles stored in `workspaces.notification_prefs JSONB`, webhook health indicator panel (last received per source, colored status dots from `activity_events`), sidebar updated with Settings nav link.
**Uses:** `react-hook-form` (settings forms — same pattern as onboarding, same dependency already installed), shadcn `tabs` component
**Implements:** Settings page, `/api/apikeys` FastAPI endpoints
**Avoids:** No major pitfalls specific to this phase; standard CRUD patterns apply.
**Research flag:** Standard CRUD pattern. Webhook health indicator query is a simple read from `activity_events` grouped by source. No research needed.

### Phase Ordering Rationale

- **Phase 1 before everything:** Tokens cascade to every component. Wrong tokens mean rework on every component already built.
- **Phase 2 (schema) before Phases 3-5:** `user_onboarding_state` must exist before Phase 3 can persist wizard state. `activity_events` and `emit_activity()` must exist before Phase 4 can display data.
- **Phase 3 before Phases 4-5 (as a gate):** Onboarding gates dashboard access. Testing Phases 4-5 without completing onboarding infrastructure requires manual database bypasses that slow development iteration.
- **Phases 4 and 5 can parallelize** once Phase 2 schema and Phase 1 tokens are in place. They share no component dependencies.
- **Phase 6 is lowest priority** — settings CRUD is valuable but not the core experience. Can ship after the feed features are stable.

### Research Flags

**Needs evaluation or care during planning:**
- **Phase 3 (`@stepperize/react`):** MEDIUM confidence library. At Phase 3 planning: if the wizard has 3 linear steps with no conditional branching, skip the dependency and use `useState`. If 4+ steps or conditional branching, add it. The threshold is documented in STACK.md.
- **Phase 3 (Onboarding aha-moment step 4):** Cross-milestone dependency on LangGraph pipeline stability. Plan a realistic mock context page fallback for the onboarding completion screen in case the pipeline is not ready. FEATURES.md explicitly flags this as the highest-risk dependency.
- **Phase 3 (Step completion derivation):** PITFALLS.md and ARCHITECTURE.md both recommend deriving step completion from actual data state (Linear connected? → step 2 complete) rather than a stored step counter. Define this mapping explicitly during Phase 3 planning to make the wizard resilient to partial state from outside the onboarding flow.

**Standard patterns — no additional research needed:**
- **Phase 1 (Dark theme tokens):** shadcn/ui Tailwind v4 documentation is comprehensive and directly applicable.
- **Phase 2 (Auth redesign + schema):** Auth dark theme follows the same `.dark` class structural pattern. Supabase migrations are routine.
- **Phase 4 (Activity timeline):** Supabase Realtime `postgres_changes` with workspace-scoped filter is fully documented.
- **Phase 5 (Context feed):** Compound component + Supabase Realtime + nuqs — all standard patterns with official docs.
- **Phase 6 (Settings):** CRUD + API key display pattern is the GitHub PAT model, widely documented.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 5 npm packages version-verified against npm registry on 2026-03-04. React 19 + Next.js 15 compatibility confirmed for all additions. Only @stepperize/react is MEDIUM — evaluable at implementation time without commitment risk. |
| Features | MEDIUM-HIGH | Table stakes and P1 features are grounded in direct competitor analysis (Linear, Vercel, PostHog 3000, Supabase). Differentiators are well-evidenced. MVP scope is deliberately conservative. The one uncertainty is the aha-moment step 4 dependency on Phase 4 pipeline. |
| Architecture | HIGH | Architecture is grounded in direct codebase inspection of existing files, not just documentation. Build order, component responsibilities, and data flow patterns are concrete and implementation-ready. All 5 architectural patterns have code examples in ARCHITECTURE.md. |
| Pitfalls | HIGH | Critical pitfalls are verified against official shadcn/ui GitHub issues, Supabase docs, and direct codebase inspection. Prevention strategies are specific (FOUC: one-line class addition; OAuth state: cookie before redirect; subscription leaks: removeChannel in cleanup) — not generic advice. |

**Overall confidence:** HIGH

### Gaps to Address

- **@stepperize/react evaluation:** Decide at Phase 3 planning time whether the wizard needs it (4+ steps with conditional branching) or whether `useState` suffices (3 linear steps). STACK.md documents this threshold; do not install the dependency until the decision is made.
- **Onboarding step 4 dependency:** Confirm Phase 4 LangGraph pipeline stability before planning the aha-moment step. If not stable, build a realistic mock context page that shows what a generated page looks like — this is explicitly called out in FEATURES.md as a required fallback.
- **Step completion derivation mapping:** Define the explicit mapping from integration state to wizard step completion during Phase 3 planning (e.g., `Linear OAuth token exists AND integration.status = 'active'` → step 2 complete). PITFALLS.md warns that storing a step counter alone causes the wizard to regress when users connect integrations outside the onboarding flow.
- **`activity_events` retention policy:** Add a 30-day pg_cron retention policy when creating the table in Phase 2. Do not defer — the table grows continuously and retrofitting retention policies after data accumulates requires a table scan migration.

---

## Sources

### Primary (HIGH confidence)
- npm registry — react-hook-form 7.71.2, @hookform/resolvers 5.2.2, zod 4.3.6, motion 12.34.5, nuqs 2.8.9, @stepperize/react 6.1.0, date-fns 4.1.0 (versions verified 2026-03-04)
- shadcn/ui official docs — React Hook Form zodResolver pattern, Tailwind v4 dark mode (`@custom-variant dark`), component registry
- Supabase official docs — Realtime postgres_changes, Realtime limits (200 connections free, 100 channels/connection), RLS patterns, channel cleanup
- Tailwind CSS v4 official docs — `@theme`, `@custom-variant dark (&:is(.dark *))`, CSS-first token architecture
- Next.js official docs — Route Groups (parentheses syntax, no URL impact), App Router server component redirects
- Direct codebase inspection — `globals.css`, `landing.css`, `dashboard/layout.tsx`, `(auth)/layout.tsx`, `middleware.ts`, `lib/supabase/client.ts`, `lib/api.ts` (ground truth for existing patterns and gaps)
- Linear UI redesign blog (linear.app/now) — LCH color system, Inter Display, spring animation curves
- PostHog "An engineer's guide to vibe design" newsletter — surface hierarchy, contrast, font recommendations, elevation options
- Vercel dashboard redesign blog — project previews, deployment status patterns, filterable logs
- Aubergine.co activity feed design guide — chronological feed component anatomy, grouping, filtering
- shadcn/ui GitHub issue #5552 — Next.js 15 + ThemeProvider hydration issues (FOUC cause confirmed)

### Secondary (MEDIUM confidence)
- @hookform/resolvers GitHub issue #799 — Zod v4 compatibility confirmation for resolvers v5.x
- LogRocket: Linear design trend article — dark mode characteristics, color reduction philosophy
- LogRocket: Best React animation libraries 2026 — motion recommendation, bundle comparison
- Stepperize GitHub repo — composable step state, shadcn integration
- OnboardJS blog: Supabase onboarding persistence — state loss on refresh patterns
- growthdives.com: Linear onboarding analysis — one input per step, minimal animations, trust over growth tricks

### Tertiary (LOW confidence)
- fmerian.medium.com: Linear FTUX (403 blocked, summary from search results) — step structure confirmation
- PostHog LinkedIn post summary — dark mode, density, side panels as three pillars of dev-tool feel

---

*Research completed: 2026-03-04*
*Ready for roadmap: yes*
