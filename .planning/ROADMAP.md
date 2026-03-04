# Roadmap: ContextOS

## Milestones

- :white_check_mark: **v1.0 Dogfood** - Phases 1-14 (shipped 2026-03-03)
- :construction: **v1.1 Dashboard & Onboarding** - Phases 15-20 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 Dogfood (Phases 1-14) - SHIPPED 2026-03-03</summary>

- [x] **Phase 1: Foundation** - Database schema, auth backend + UI, workspace tenancy, project deps (completed 2026-02-24)
- [x] **Phase 2: Linear Integration** - OAuth, ticket sync, webhooks, token refresh (completed 2026-02-24)
- [ ] **Phase 3: Slack and Meeting Ingestion** - Slack OAuth, events API, channel selection, Fathom API, integration setup page
- [ ] **Phase 4: Context Generation** - LangGraph pipeline, Gemini synthesis, Slack-to-ticket linking, meeting-to-ticket linking
- [ ] **Phase 5: Delivery Channels** - Dashboard feed/detail/settings, Linear comment bot, MCP server
- [x] **Phase 6: Extension and Hardening** - Chrome extension, Vault token storage, Sentry, Laminar (completed 2026-02-25)
- [x] **Phase 7: GitHub Integration** - GitHub OAuth, PR/review ingestion, PR-to-Linear linking (completed 2026-02-25)
- [x] **Phase 07.1: Tech Debt Cleanup** - Fix 12 tech debt items from v1.0 audit (INSERTED, completed 2026-02-26)
- [x] **Phase 07.2: Integration Bug Fixes and Hardening** - Fix critical/high/medium integration bugs (INSERTED)
- [x] **Phase 08: Dashboard UI/UX Redesign** - Polished Linear-inspired dashboard (INSERTED)
- [x] **Phase 08.1: Dashboard Design Polish** - Distinctive craft-polished product aesthetic (INSERTED)
- [x] **Phase 08.1.1: Notion Integration** - Notion OAuth, page ingestion, webhook updates (INSERTED)
- [ ] **Phase 9: Notion Integration UI Polish** - Summary stats line, card simplification
- [x] **Phase 10: Sync Engine Improvements** - Sync state, Redis Streams, batch embeddings, concurrency
- [ ] **Phase 11: Production Infrastructure** - TBD
- [x] **Phase 12: Org-wide Code Intelligence** - Tree-sitter parsing, code embeddings, cross-repo search
- [x] **Phase 13: Adopt Orchids Landing Page** - Dark teal landing page in apps/web
- [x] **Phase 14: PostHog Analytics + Live Waitlist** - PostHog SDK, waitlist form, event tracking

</details>

### v1.1 Dashboard & Onboarding (In Progress)

**Milestone Goal:** Transform the generic dashboard into a polished, brand-consistent product experience with guided onboarding, full context feed, activity timeline, and team settings -- dark theme that mirrors the landing page's teal identity but stays muted for daily use.

- [x] **Phase 15: Dark Theme Token Foundation** - Brand-tinted OKLCH tokens, DarkModeApplier, JetBrains Mono, navigation restructure, skeleton states (completed 2026-03-04)
- [x] **Phase 16: Auth Redesign + Schema Foundation** - Dark-themed auth pages, user_onboarding_state and activity_events tables, onboarding gate (completed 2026-03-04)
- [ ] **Phase 17: Onboarding Wizard** - 4-step guided wizard with OAuth state preservation and animated transitions
- [ ] **Phase 18: Activity Timeline** - Chronological event feed with real-time updates and day-group dividers
- [ ] **Phase 19: Context Feed + Dashboard Home** - Browsable context feed with filtering, search, detail view, and dashboard summary
- [ ] **Phase 20: Settings Page** - API key management, workspace editing, team member view

## Phase Details

### Phase 15: Dark Theme Token Foundation
**Goal**: Every dashboard and auth surface renders in a brand-tinted dark theme with consistent tokens, navigation, and loading states -- the visual foundation every subsequent phase builds on
**Depends on**: Phase 14 (v1.0 complete)
**Requirements**: DS-01, DS-02, DS-03, DS-04, DS-05, DS-06, DS-07, DS-08, DS-09, NAV-01
**Success Criteria** (what must be TRUE):
  1. Dashboard renders dark by default with brand-tinted surfaces (not neutral gray shadcn defaults) and teal appears only on actionable/status elements
  2. JetBrains Mono displays on all data identifiers (ticket IDs, timestamps, counts, API keys) and section labels use monospace uppercase tracking
  3. All Radix UI portals (Dialog, Dropdown, Sheet) render correctly in dark mode without light-theme flash
  4. Dashboard navigation holds all sections (context feed, activity, integrations, settings) with clear active state indicators
  5. Every dashboard page shows a structured skeleton loading state that matches the populated layout shape
**Plans**: 3 plans

Plans:
- [ ] 15-01-PLAN.md — OKLCH token system, DarkModeApplier, FOUC prevention, spring animations, grain texture, shimmer keyframe
- [ ] 15-02-PLAN.md — Navigation restructure with Activity link, avatar dropdown, teal underline active state, wordmark gradient
- [ ] 15-03-PLAN.md — Skeleton component, structured loading states, font-mono typography, section-label utility, Activity placeholder

### Phase 16: Auth Redesign + Schema Foundation
**Goal**: Auth pages match the dark brand identity and the database tables required for onboarding and activity tracking exist with proper RLS, indexes, and triggers
**Depends on**: Phase 15
**Requirements**: AUTH-01, AUTH-02, ACT-04, ONB-07, ONB-09
**Success Criteria** (what must be TRUE):
  1. Login and signup pages render in the dark theme with the same teal accent, typography, and surface tokens as the dashboard
  2. user_onboarding_state table exists with RLS, auto-created on first sign-in, queryable for onboarding completion status
  3. activity_events table exists with workspace-scoped RLS, (workspace_id, created_at DESC) index, and 30-day retention policy
  4. Users who have not completed onboarding are redirected away from the dashboard to the onboarding flow
**Plans**: 3 plans

Plans:
- [ ] 16-01-PLAN.md — Database migration: user_onboarding_state + activity_events tables, trigger extension, pg_cron retention
- [ ] 16-02-PLAN.md — Auth UI redesign: split layout with brand panel, dark-themed login/signup pages with teal CTAs
- [ ] 16-03-PLAN.md — Onboarding gate in dashboard layout, /onboarding route placeholder, Sonner toaster, auth callback update

### Phase 17: Onboarding Wizard
**Goal**: New users experience a guided 4-step onboarding (workspace name, connect Linear, optional sources, first context page) that persists across refreshes and OAuth redirects before they ever see the dashboard
**Depends on**: Phase 16
**Requirements**: ONB-01, ONB-02, ONB-03, ONB-04, ONB-05, ONB-06, ONB-08
**Success Criteria** (what must be TRUE):
  1. After first signup, user sees a 4-step wizard (workspace name, connect Linear, optional sources, first context page) before the dashboard
  2. User cannot proceed past step 2 without connecting Linear; optional sources in step 3 can be skipped
  3. OAuth redirects (Linear, Slack, etc.) return the user to the correct wizard step without losing progress
  4. Closing the browser and returning resumes the wizard at the last completed step (database-backed persistence)
  5. Successful integration connection shows an animated checkmark confirmation
**Plans**: TBD

Plans:
- [ ] 17-01: TBD
- [ ] 17-02: TBD

### Phase 18: Activity Timeline
**Goal**: Users see a live chronological feed of workspace events (syncs, context generated, integrations connected) that proves the system is working
**Depends on**: Phase 16
**Requirements**: ACT-01, ACT-02, ACT-03
**Success Criteria** (what must be TRUE):
  1. User sees a chronological feed of workspace events (syncs, context generated, integrations connected) on the dashboard
  2. Events display with type-specific icons, relative timestamps, and day-group dividers
  3. New events appear in real-time without page refresh via Supabase Realtime
**Plans**: 2 plans

Plans:
- [ ] 18-01-PLAN.md — Realtime publication migration, ActivityEvent types, formatter functions (descriptions, timestamps, day labels, metadata chips)
- [ ] 18-02-PLAN.md — Server page with SSR data fetch, ActivityTimeline client component with Realtime subscription, day-grouped rendering, pagination, animations

### Phase 19: Context Feed + Dashboard Home
**Goal**: Users can browse, filter, search, and inspect all their generated context pages from a dedicated feed view, and the dashboard home provides a summary overview
**Depends on**: Phase 16
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, FEED-06, HOME-01
**Success Criteria** (what must be TRUE):
  1. User can browse all generated context pages in a scrollable list with status indicators
  2. User can filter context pages by status (All/Ready/Generating/Stale/Error) and search by free text (title, ticket ID)
  3. Context feed updates in real-time as page statuses change (no manual refresh needed)
  4. User can open a context page detail view at /dashboard/context/[id] with copy-prompt and regenerate actions
  5. Empty states show what a populated feed looks like with a clear CTA, and the dashboard home shows recent pages, integration health, and activity preview
**Plans**: TBD

Plans:
- [ ] 19-01: TBD
- [ ] 19-02: TBD

### Phase 20: Settings Page
**Goal**: Users can manage API keys, workspace settings, and view team members from a dedicated settings page
**Depends on**: Phase 15
**Requirements**: SET-01, SET-02, SET-03, SET-04
**Success Criteria** (what must be TRUE):
  1. User can create API keys (full key shown once on creation, then prefix-only) and revoke existing keys
  2. User can edit their workspace name from settings
  3. User can view connected team members
  4. Settings page is accessible from the dashboard navigation
**Plans**: TBD

Plans:
- [ ] 20-01: TBD

## Coverage

### v1.1 Coverage

**36/36 v1.1 requirements mapped.**

| Category | Requirements | Phase |
|----------|-------------|-------|
| Design System | DS-01, DS-02, DS-03, DS-04, DS-05, DS-06, DS-07, DS-08, DS-09 (9) | Phase 15 |
| Navigation | NAV-01 (1) | Phase 15 |
| Auth Redesign | AUTH-01, AUTH-02 (2) | Phase 16 |
| Activity Schema | ACT-04 (1) | Phase 16 |
| Onboarding Infra | ONB-07, ONB-09 (2) | Phase 16 |
| Onboarding Wizard | ONB-01, ONB-02, ONB-03, ONB-04, ONB-05, ONB-06, ONB-08 (7) | Phase 17 |
| Activity Timeline | ACT-01, ACT-02, ACT-03 (3) | Phase 18 |
| Context Feed | FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, FEED-06 (6) | Phase 19 |
| Dashboard Home | HOME-01 (1) | Phase 19 |
| Settings & Team | SET-01, SET-02, SET-03, SET-04 (4) | Phase 20 |

No orphaned requirements. No duplicate mappings.

## Progress

**Execution Order:**
Phase 15 (tokens) --> Phase 16 (auth + schema) --> Phases 17, 18, 19 (can parallelize after 16) --> Phase 20 (independent after 15)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 15. Dark Theme Token Foundation | 3/3 | Complete    | 2026-03-04 | - |
| 16. Auth Redesign + Schema Foundation | 3/3 | Complete    | 2026-03-04 | - |
| 17. Onboarding Wizard | v1.1 | 0/TBD | Not started | - |
| 18. Activity Timeline | v1.1 | 0/2 | Planned | - |
| 19. Context Feed + Dashboard Home | v1.1 | 0/TBD | Not started | - |
| 20. Settings Page | v1.1 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-24*
*v1.1 milestone added: 2026-03-04*
