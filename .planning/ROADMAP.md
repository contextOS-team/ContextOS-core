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
- [x] **Phase 17: Onboarding Wizard** - 4-step guided wizard with OAuth state preservation and animated transitions (completed 2026-03-04)
- [x] **Phase 18: Activity Timeline** - Chronological event feed with real-time updates and day-group dividers (completed 2026-03-04)
- [x] **Phase 19: Context Feed + Dashboard Home** - Browsable context feed with filtering, search, detail view, and dashboard summary (completed 2026-03-04)
- [x] **Phase 20: Settings Page** - API key management, workspace editing, team member view (completed 2026-03-06)

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
**Plans**: 2 plans

Plans:
- [ ] 17-01-PLAN.md — Wizard shell with dot stepper, steps 1-3 (workspace naming, Linear connection, optional sources grid), success checkmark, CSS crossfade
- [ ] 17-02-PLAN.md — Step 4 context page generation with mock fallback, completion flow, end-to-end visual verification

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
**Plans**: 3 plans

Plans:
- [ ] 19-01-PLAN.md — DB migration (error status + Realtime publication), npm deps (react-markdown, remark-gfm, typography), shared types/hooks
- [ ] 19-02-PLAN.md — Context feed list page with status filters, debounced search, Realtime updates, empty state with inline generate
- [ ] 19-03-PLAN.md — Context detail view with markdown rendering, copy-prompt, regenerate; Dashboard home Recent Context section

### Phase 20: Settings Page
**Goal**: Users can manage API keys, workspace settings, and view team members from a dedicated settings page
**Depends on**: Phase 15
**Requirements**: SET-01, SET-02, SET-03, SET-04
**Success Criteria** (what must be TRUE):
  1. User can create API keys (full key shown once on creation, then prefix-only) and revoke existing keys
  2. User can edit their workspace name from settings
  3. User can view connected team members
  4. Settings page is accessible from the dashboard navigation
**Plans**: 2 plans

Plans:
- [ ] 20-01-PLAN.md — Database migration (api_keys table + RLS), API key model/service, backend endpoints (CRUD api-keys, PATCH workspace, GET members)
- [ ] 20-02-PLAN.md — AlertDialog component, API client functions, settings page with General/API Keys/Team/Integrations sections

### Phase 21: Auth Redesign and Social OAuth

**Goal:** Add Google and GitHub social OAuth login, remove magic link authentication, polish auth form styling, add password reset flow, and refresh the brand panel -- making auth pages feel premium and offering fast social login
**Requirements**: OAUTH-01, OAUTH-02, AUTH-POLISH-01, AUTH-POLISH-02, AUTH-POLISH-03
**Depends on:** Phase 20
**Success Criteria** (what must be TRUE):
  1. Google and GitHub social login buttons appear on both login and signup pages above the email/password form
  2. Magic link authentication is completely removed
  3. Social OAuth integrates with existing onboarding flow (new social users go through wizard)
  4. Password reset flow works via "Forgot password?" link
  5. Auth brand panel feels alive with animated elements and product-focused content
  6. Input fields have teal-accented focus rings
**Plans**: 2 plans

Plans:
- [ ] 21-01-PLAN.md — Social OAuth buttons component, provider SVG icons, rewrite login/signup pages (remove magic link, add social buttons, focus rings, fix footer)
- [ ] 21-02-PLAN.md — Database migration for multi-provider name extraction, password reset page, brand panel refresh, visual verification

### Phase 22: Real-time Context Generation Progress UI

**Goal:** Replace the silent toast-based generation flow with a beautiful, animated, real-time progress experience that shows the LLM searching each integrated source (Slack, GitHub, Fathom, Notion, Linear) with live feedback. Progress is real (driven by backend events), source-aware (only shows connected integrations), and transitions smoothly into the completed context page.
**Requirements**: GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, GEN-06
**Depends on:** Phase 19
**Success Criteria** (what must be TRUE):
  1. SSE endpoint streams per-source progress events during context generation
  2. Progress UI shows vertical step list with only connected integrations
  3. Steps animate through waiting/active/complete states with CSS transitions
  4. On completion, progress collapses into card row then auto-navigates to detail page
  5. Error state shows failed step with retry/dismiss buttons inline
  6. Existing POST /generate endpoint preserved for programmatic consumers
**Plans**: 3 plans

Plans:
- [ ] 22-01-PLAN.md — Backend: install sse-starlette, decompose per-source content finding, streaming generation function, SSE endpoint
- [ ] 22-02-PLAN.md — Frontend: apiFetchSSE client with auth headers, GenerationProgress component, CSS animations (pulse, collapse, stagger)
- [ ] 22-03-PLAN.md — Wire progress into context feed page, replace toast triggers, collapse-to-card transition, auto-navigate, human verification

### Phase 23: Remotion Animated Hero

**Goal:** Replace the static demo.mp4 hero video with a Remotion-powered 3-scene animated product walkthrough (ticket card -> source search -> context page) rendered in real-time via @remotion/player, matching the Linear/Vercel minimal aesthetic with spring animations and brand colors
**Requirements**: HERO-ANIM-01, HERO-ANIM-02, HERO-ANIM-03, HERO-ANIM-04
**Depends on:** Phase 22
**Success Criteria** (what must be TRUE):
  1. Landing page hero shows an animated 3-scene walkthrough instead of static video
  2. Animation auto-plays, loops continuously with ~1s gap, and uses spring physics for all motion
  3. Scroll-driven perspective effect (rotateX + scale) works on the Player container
  4. Player is lazy-loaded with no layout shift (placeholder with matching aspect ratio)
  5. Headline, subheadline, badge, and CTAs remain as regular HTML
**Plans**: 2 plans

Plans:
- [ ] 23-01-PLAN.md — Install Remotion, create constants/shared components, build 3 scene compositions and root HeroComposition
- [ ] 23-02-PLAN.md — Create RemotionPlayer wrapper, integrate into Hero.tsx replacing video, visual verification checkpoint

### Phase 24: GitLab Integration

**Goal:** Add GitLab as an alternative code hosting integration alongside GitHub -- GitLab OAuth, MR/review ingestion, MR-to-Linear linking, webhook sync, and GitLab source in onboarding wizard sources grid
**Requirements**: GL-01, GL-02, GL-03, GL-04, GL-05, GL-06, GL-07, GL-08
**Depends on:** Phase 23
**Success Criteria** (what must be TRUE):
  1. GitLab OAuth connect/disconnect flow works with standard OAuth2 authorization code + refresh tokens
  2. GitLab merge requests and reviews sync from selected projects into gitlab_merge_requests/gitlab_reviews tables
  3. MRs are linked to Linear tickets via source branch name parsing
  4. GitLab webhooks process MR and note events with X-Gitlab-Token verification
  5. GitLab appears as a source in onboarding wizard step 3 and settings integrations
  6. Users can select which GitLab projects to monitor
**Plans**: 3 plans

Plans:
- [ ] 24-01-PLAN.md — Database migration (gitlab_merge_requests/gitlab_reviews tables, constraint updates), SQLModel classes, Provider enum, Settings config
- [ ] 24-02-PLAN.md — Backend services (OAuth2, MR sync, webhook handler, project selection, Linear linking) and router with /api/gitlab/* endpoints
- [ ] 24-03-PLAN.md — Frontend: GitLabLogo icon, API functions, onboarding source card, settings integration card

### Phase 25: Jira Integration

**Goal:** Add Jira as an alternative task tracker alongside Linear -- Jira OAuth 2.0 (3LO), issue sync via JQL with token-based pagination, Jira-to-context linking, webhook updates with 30-day refresh, and Jira source in onboarding wizard sources grid
**Requirements**: JIRA-01, JIRA-02, JIRA-03, JIRA-04, JIRA-05, JIRA-06
**Depends on:** Phase 23 (parallel with 24, 26)
**Success Criteria** (what must be TRUE):
  1. Jira OAuth connect/disconnect flow works via auth.atlassian.com with cloudId resolution
  2. Jira issues sync via /search/jql endpoint with nextPageToken pagination
  3. Jira issues can be linked to context pages via jira_issue_id FK
  4. Jira webhooks process issue/comment CRUD events with HMAC verification
  5. Jira appears as a source in onboarding wizard step 3 and settings integrations
  6. Integration status API includes Jira connection state
**Plans**: 3 plans

Plans:
- [x] 25-01-PLAN.md — Database migration (jira_issues/jira_comments tables, constraint updates, context_pages FK), SQLModel classes, Provider enum, Settings config
- [ ] 25-02-PLAN.md — Backend services (OAuth 3LO with cloudId, JQL sync, webhook handler) and router with /api/jira/* endpoints
- [ ] 25-03-PLAN.md — Frontend: JiraLogo icon, API functions, onboarding source card, settings integration card

### Phase 26: Telegram Chat Integration

**Goal:** Add Telegram as a chat source alongside Slack -- Telegram Bot API integration, group/channel message ingestion, message-to-ticket linking, and Telegram source in onboarding wizard sources grid
**Requirements**: TG-01, TG-02, TG-03, TG-04, TG-05, TG-06, TG-07
**Depends on:** Phase 23 (parallel with 24, 25)
**Success Criteria** (what must be TRUE):
  1. User can connect a Telegram bot via token entry (Fathom-style, no OAuth) from onboarding wizard and settings page
  2. Webhook endpoint receives Telegram updates with secret_token verification and stores messages
  3. Telegram messages appear in the linking engine for message-to-ticket matching
  4. Integration status endpoint includes Telegram
  5. Onboarding sources grid and settings integrations section show Telegram card
**Plans:** 3/3 plans complete

Plans:
- [ ] 26-01-PLAN.md — Database migration (telegram_messages table, CHECK constraint updates), TelegramMessage model, Provider enum, config, bot service, event processing
- [ ] 26-02-PLAN.md — Telegram router (connect/disconnect/webhook endpoints), main.py registration, integrations status update, linking engine integration
- [ ] 26-03-PLAN.md — Frontend: TelegramLogo SVG, API client functions, onboarding wizard card, settings page card with bot token form

### Phase 27: Dashboard Homepage Intelligence Widgets

**Goal:** Transform the passive dashboard homepage into an intelligence hub with 5 widget sections -- Needs Attention alerts, Resurfaced forgotten context, This Week timeline, Sprint progress, and demoted integration dots -- answering "what do I need to know?" with cross-source intelligence
**Requirements**: WIDGET-01, WIDGET-02, WIDGET-03, WIDGET-04, WIDGET-05, API-01, API-02, API-03, API-04
**Depends on:** Phase 26
**Success Criteria** (what must be TRUE):
  1. Dashboard homepage shows attention items (stale contexts, open PRs/MRs) with count badge and navigation links
  2. Resurfaced widget surfaces forgotten Slack decisions/ideas with no ticket follow-through
  3. This Week timeline groups activity, contexts, and merged PRs by day
  4. Sprint badge shows current Linear cycle progress with days remaining
  5. Integrations demoted from full list to compact status dots footer
**Plans:** 2 plans

Plans:
- [ ] 27-01-PLAN.md -- Backend: dashboard router with 4 aggregation endpoints (attention, weekly-summary, sprint, resurfaced)
- [ ] 27-02-PLAN.md -- Frontend: 5 widget components, dashboard page rewrite with intelligence layout

---

### Phase 28: GitLab Project Selection & Code Indexing

**Goal:** Add project selection UI and code indexing for GitLab, mirroring the GitHub experience — browse projects, select which to monitor, clone and index code using the existing provider-agnostic pipeline (tree-sitter parsing, embeddings).
**Requirements**: GL-09, GL-10, GL-11
**Depends on:** Phase 24
**Success Criteria** (what must be TRUE):
  1. Code indexing pipeline supports both GitHub and GitLab with provider-aware clone authentication
  2. POST /api/gitlab/index triggers indexing for selected GitLab projects via Redis Stream worker
  3. GET /api/gitlab/index/status returns indexing state and per-project chunk counts
  4. Users can browse, select, and save GitLab projects from the settings page
  5. Saving project selection auto-triggers code indexing with status polling
  6. Integrations status includes selected_repos_count for GitLab
**Plans:** 2/2 plans complete

Plans:
- [ ] 28-01-PLAN.md — Backend: abstract clone auth in code_indexer, add /index and /index/status endpoints to GitLab router, update integrations status
- [ ] 28-02-PLAN.md — Frontend: GitLab API client functions, GitlabRepos project selection component, wire into settings integration cards

### Phase 29: Codebase Hardening - Security, Bug Fixes, Architecture, and UI/UX Polish

**Goal:** Eliminate all identified security vulnerabilities, fix production bugs, refactor duplicated synthesis logic, decompose the settings monolith, and polish frontend UX -- hardening the codebase for production readiness
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, BUG-01, BUG-02, BUG-03, BUG-04, ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, UI-01, UI-02, UI-03, PERF-01, PERF-02, PERF-03, REL-01, REL-02
**Depends on:** Phase 28
**Success Criteria** (what must be TRUE):
  1. All security vulnerabilities (JQL injection, IP spoofing, OAuth state, API key hashing, rate limiter) are patched
  2. No context pages get stuck in "generating" status on LLM failure
  3. Synthesis pipeline uses shared helpers with zero duplication
  4. Settings page is decomposed into focused tab components (each under 200 lines)
  5. Frontend uses AlertDialog for confirmations and shows user-friendly error messages
**Plans:** 6/6 plans complete

Plans:
- [x] 29-01-PLAN.md — Security hardening: JQL injection, IP spoofing, OAuth state signing, API key salt, Redis rate limiter, consumer names, workspace safety
- [x] 29-02-PLAN.md — UI/UX polish: AlertDialog disconnect, friendly error messages, eslint-disable fixes, settings page decomposition
- [x] 29-03-PLAN.md — Quick fixes: Telegram background processing, migration renumber, shared datetime utility, deferred imports
- [x] 29-04-PLAN.md — Synthesis pipeline overhaul: error status propagation, shared helpers, token limit, dead code removal, linking optimization
- [ ] 29-05-PLAN.md — Gap closure: PERF-02 fix -- pass connected_sources into DB query functions, wire from synthesis stream path
- [ ] 29-06-PLAN.md — Gap closure: Decompose integrations-tab.tsx from 548 lines to under 200 via sub-component extraction

### Phase 30: Slack Huddle Transcript Ingestion

**Goal:** Ingest Slack huddle meeting transcripts and summaries (generated by Slack Pro's built-in AI) so engineers get meeting context alongside Slack messages, replacing the need for Fathom which doesn't support huddles. Read canvas/transcript data via Slack API, store as meeting records, and feed into the linking engine for ticket association.
**Requirements**: HUDDLE-01, HUDDLE-02, HUDDLE-03, HUDDLE-04, HUDDLE-05
**Depends on:** Phase 29
**Success Criteria** (what must be TRUE):
  1. Slack huddle transcripts and AI-generated summaries are ingested from Slack canvases/files attached to huddle channels
  2. Meeting records are stored with participant info, duration, and transcript text
  3. Meetings appear in the linking engine for ticket-to-meeting association (replacing/augmenting Fathom)
  4. Huddle data feeds into context page generation with meeting summaries
  5. No new OAuth scopes break existing Slack message ingestion
**Plans:** 2/2 plans complete

Plans:
- [ ] 30-01-PLAN.md — Database migration (slack_huddle source CHECK), OAuth scope update (canvases:read, files:read), poll-based huddle ingestion service
- [ ] 30-02-PLAN.md — Wire slack_huddle into linking engine and synthesis pipeline, add POST /api/slack/poll-huddles endpoint

### Phase 31: GitLab & GitHub Sync Performance Optimization

**Goal:** Dramatically reduce GitLab/GitHub MR sync and code indexing times by introducing concurrent API fetching, incremental sync with cursor-based pagination, parallel repository cloning/parsing, and async note/review batch fetching -- eliminating the per-MR API call bottleneck and sequential repo processing that caused production timeouts
**Requirements**: PERF-SYNC-01, PERF-SYNC-02, PERF-SYNC-03, PERF-SYNC-04, PERF-SYNC-05, PERF-SYNC-06
**Depends on:** Phase 30
**Success Criteria** (what must be TRUE):
  1. MR/PR sync fetches notes/reviews concurrently (asyncio.gather with concurrency limit) instead of one-by-one, reducing sync time by 5-10x
  2. Incremental sync uses `updated_after` cursor persisted per-project so re-syncs only fetch changed MRs, not the full history
  3. Code indexing clones and parses multiple repositories concurrently (configurable parallelism) instead of sequentially
  4. Sync operations have per-project timeouts with graceful partial-commit (completed projects saved even if one times out)
  5. Open vs closed MR fetch uses state filter to avoid fetching all MRs when only open ones are needed
  6. Progress events emitted during sync for frontend status visibility
**Plans:** 3/3 plans complete

Plans:
- [ ] 31-01-PLAN.md — GitLab sync: concurrent note fetching, incremental cursor, state filter, per-project timeout
- [ ] 31-02-PLAN.md — GitHub sync: concurrent review fetching, incremental cursor, state filter, per-repo timeout
- [ ] 31-03-PLAN.md — Concurrent code indexing for both providers with configurable parallelism and per-repo timeout

---
*Roadmap created: 2026-02-24*
*v1.1 milestone added: 2026-03-04*
