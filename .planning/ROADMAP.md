# Roadmap: ContextOS

## Milestones

- :white_check_mark: **v1.0 Dogfood** - Phases 1-14 (shipped 2026-03-03)
- :white_check_mark: **v1.1 Dashboard & Onboarding** - Phases 15-31 (shipped 2026-03-15)
- :white_check_mark: **v1.2 GraphRAG** - Phases 22-27 (shipped 2026-03-08)
- :construction: **v1.3 Live Intelligence** - Phases 32-42 (in progress)
- :clipboard: **v1.4 Product Expansion & Action Layer** - Phases 43-49 (planned)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 Dogfood (Phases 1-14) - SHIPPED 2026-03-03</summary>

- [x] **Phase 1: Foundation** - Database schema, auth backend + UI, workspace tenancy, project deps (completed 2026-02-24)
- [x] **Phase 2: Linear Integration** - OAuth, ticket sync, webhooks, token refresh (completed 2026-02-24)
- [x] **Phase 3: Slack and Meeting Ingestion** - Slack OAuth, events API, channel selection, Fathom API
- [x] **Phase 4: Context Generation** - LangGraph pipeline, Gemini synthesis, Slack-to-ticket linking
- [x] **Phase 5: Delivery Channels** - Dashboard feed/detail/settings, Linear comment bot, MCP server
- [x] **Phase 6: Extension and Hardening** - Chrome extension, Vault token storage, Sentry, Laminar (completed 2026-02-25)
- [x] **Phase 7: GitHub Integration** - GitHub OAuth, PR/review ingestion, PR-to-Linear linking (completed 2026-02-25)
- [x] **Phase 07.1: Tech Debt Cleanup** - Fix 12 tech debt items from v1.0 audit (INSERTED)
- [x] **Phase 07.2: Integration Bug Fixes** - Fix critical/high/medium integration bugs (INSERTED)
- [x] **Phase 08: Dashboard UI/UX Redesign** - Polished Linear-inspired dashboard (INSERTED)
- [x] **Phase 08.1: Dashboard Design Polish** - Distinctive craft-polished product aesthetic (INSERTED)
- [x] **Phase 08.1.1: Notion Integration** - Notion OAuth, page ingestion, webhook updates (INSERTED)
- [x] **Phase 10: Sync Engine Improvements** - Sync state, Redis Streams, batch embeddings, concurrency
- [x] **Phase 12: Org-wide Code Intelligence** - Tree-sitter parsing, code embeddings, cross-repo search
- [x] **Phase 13: Adopt Orchids Landing Page** - Dark teal landing page in apps/web
- [x] **Phase 14: PostHog Analytics + Live Waitlist** - PostHog SDK, waitlist form, event tracking

</details>

<details>
<summary>v1.1 Dashboard & Onboarding (Phases 15-31) - SHIPPED 2026-03-15</summary>

**Original scope (phases 15-20):**
- [x] **Phase 15: Dark Theme Token Foundation** - Brand-tinted OKLCH tokens, DarkModeApplier, JetBrains Mono, navigation, skeletons (completed 2026-03-04)
- [x] **Phase 16: Auth Redesign + Schema Foundation** - Dark auth pages, onboarding/activity tables, onboarding gate (completed 2026-03-04)
- [x] **Phase 17: Onboarding Wizard** - 4-step wizard with OAuth state preservation (completed 2026-03-04)
- [x] **Phase 18: Activity Timeline** - Chronological event feed with real-time updates (completed 2026-03-04)
- [x] **Phase 19: Context Feed + Dashboard Home** - Browsable context feed with filtering, search, detail view (completed 2026-03-04)
- [x] **Phase 20: Settings Page** - API key management, workspace editing, team member view (completed 2026-03-06)

**Extended scope (phases 21-31):**
- [x] **Phase 21: Auth Redesign and Social OAuth** - Google/GitHub social login, password reset, brand panel
- [x] **Phase 22: Real-time Context Generation Progress UI** - SSE streaming, animated step progress
- [x] **Phase 23: Remotion Animated Hero** - 3-scene product walkthrough replacing static video
- [x] **Phase 24: GitLab Integration** - OAuth, MR/review sync, webhooks, project selection
- [x] **Phase 25: Jira Integration** - OAuth 3LO, JQL sync, webhook updates
- [x] **Phase 26: Telegram Chat Integration** - Bot API, group message ingestion, ticket linking
- [x] **Phase 27: Dashboard Homepage Intelligence Widgets** - Attention, resurfaced, weekly summary, sprint
- [x] **Phase 28: GitLab Project Selection & Code Indexing** - Provider-agnostic code indexing pipeline
- [x] **Phase 29: Codebase Hardening** - Security, bug fixes, architecture, UI/UX polish (6 plans)
- [x] **Phase 30: Slack Huddle Transcript Ingestion** - Canvas/file API huddle ingestion
- [x] **Phase 31: GitLab & GitHub Sync Performance** - Concurrent fetching, incremental cursors, timeouts

</details>

### v1.3 Live Intelligence (Phases 32-38)

- [x] **Phase 32: Activity Events Emission** - Wire all integration services to emit activity events (completed 2026-03-15)
- [ ] **Phase 33: Graph Visualization** - Interactive React graph explorer for ticket context
- [ ] **Phase 34: Onboarding Graph Preview** - Replace sync-dependent Step 4 with graph preview
- [ ] **Phase 35: Chrome Extension Publishing** - Publish to Web Store, Linear/Jira content scripts, popup redesign
- [ ] **Phase 36: Landing Page Polish** - Update integrations count, add privacy section, typography polish
- [ ] **Phase 37: Privacy Architecture Research** - Research self-hosted/local LLM deployment options
- [ ] **Phase 38: RAG Quality Improvements** - Retrieval quality improvements (Dulat's scope)

## Phase Details

### Phase 32: Activity Events Emission
**Goal**: The Activity tab shows real events from all integrations instead of being empty
**Depends on**: Nothing (uses existing activity_events table and frontend from Phase 18)
**Requirements**: ACT-05, ACT-06, ACT-07, ACT-08
**Success Criteria** (what must be TRUE):
  1. After a Linear/Slack/GitHub/GitLab/Jira/Notion/Telegram sync completes, the Activity tab shows an event for that sync within seconds
  2. When a user connects or disconnects an integration in Settings, an activity event appears in the timeline
  3. When a context page is generated (or fails), the Activity tab shows a generation event with status
  4. Events arrive in real-time without page refresh (existing Supabase Realtime subscription works)
**Plans:** 3/3 plans complete
Plans:
- [ ] 32-01-PLAN.md -- DB migration + emit_activity() helper + sync events for 7 providers + context generation events
- [ ] 32-02-PLAN.md -- Curated webhook events (ticket_created, pr_merged, meeting_recorded, page_created) + connect/disconnect events
- [ ] 32-03-PLAN.md -- Frontend: new event types, brand-colored icons, error states, sync status display

### Phase 33: Graph Visualization
**Goal**: Users can visually explore the knowledge graph around any ticket -- seeing people, decisions, PRs, and messages as an interactive network
**Depends on**: Nothing (uses existing Graph Explorer API from v1.2)
**Requirements**: GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04
**Success Criteria** (what must be TRUE):
  1. On a context page detail view, the user sees an interactive graph showing nodes (people, decisions, PRs, messages, code) and edges connecting them
  2. User can navigate to /dashboard/graph and explore the full knowledge graph for their workspace
  3. Clicking a node opens a detail panel showing the full content (message text, PR summary, decision rationale, person details)
  4. Graph renders smoothly with drag, zoom, and pan interactions
**Plans:** 1/2 plans executed
Plans:
- [ ] 33-01-PLAN.md -- React Flow + ELK setup, graph types, custom nodes (3 zoom tiers), edges, GraphExplorer component
- [ ] 33-02-PLAN.md -- Context page graph tab, standalone /dashboard/graph page, node detail popover + sidebar

### Phase 34: Onboarding Graph Preview
**Goal**: New users complete onboarding without waiting for sync to finish -- Step 4 shows a graph preview instead of blocking on context generation
**Depends on**: Phase 33 (graph visualization component)
**Requirements**: ONB-10, ONB-11
**Success Criteria** (what must be TRUE):
  1. Onboarding Step 4 shows a knowledge graph preview (or mock context page) instead of attempting to generate a full context page
  2. User can complete onboarding and reach the dashboard even if integration sync is still running in the background
**Plans**: TBD

### Phase 35: Chrome Extension Publishing
**Goal**: The Chrome extension is publicly available on the Web Store and surfaces ContextOS context directly on Linear and Jira ticket pages
**Depends on**: Nothing (builds on existing extension from v1.0 Phase 6)
**Requirements**: EXT-01, EXT-02, EXT-03, EXT-04
**Success Criteria** (what must be TRUE):
  1. Extension is installable from the Chrome Web Store (published and approved)
  2. When viewing a Linear ticket page, the extension shows ContextOS context for that ticket in a sidebar or inline panel
  3. When viewing a Jira issue page, the extension shows ContextOS context for that issue in a sidebar or inline panel
  4. Extension popup matches the dark theme brand identity used in the web dashboard
**Plans**: TBD

### Phase 36: Landing Page Polish
**Goal**: The landing page reflects the full product -- all 9 integrations displayed, privacy messaging for enterprise trust, and refined visual quality
**Depends on**: Nothing (independent)
**Requirements**: LAND-01, LAND-02, LAND-03
**Success Criteria** (what must be TRUE):
  1. The integrations section shows all 9 integrations: Linear, Slack, GitHub, GitLab, Jira, Notion, Telegram, Slack Huddles, Fathom
  2. A privacy/trust section communicates data ownership and security posture to prospective users
  3. Typography, spacing, and animations are polished with no visual rough edges
**Plans**: TBD

### Phase 37: Privacy Architecture Research
**Goal**: The team has a clear technical plan for self-hosted/local LLM deployment so enterprise customers can keep data on their infrastructure
**Depends on**: Nothing (independent research)
**Requirements**: PRIV-01
**Success Criteria** (what must be TRUE):
  1. A written research document exists covering self-hosted deployment options (Docker Compose, Helm), local LLM alternatives (Ollama, vLLM), and feasibility assessment
  2. The document identifies which components need modification for a self-hosted deployment and estimates effort for v1.4 implementation
**Plans**: TBD

### Phase 38: RAG Quality Improvements
**Goal**: Context page retrieval quality is measurably better -- more relevant context, fewer misses
**Depends on**: Nothing (independent, Dulat's scope)
**Requirements**: RAG-01
**Success Criteria** (what must be TRUE):
  1. Retrieval pipeline changes are identified, implemented, and tested against existing context pages
  2. At least one measurable improvement to context relevance (scope to be defined by Dulat)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 32 -> 33 -> 34 -> 35 -> 36 -> 37 -> 38 -> 39
Note: Phases 35, 36, 37, 38, 39 are independent and can execute in parallel after Phase 34.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 32. Activity Events Emission | 3/3 | Complete   | 2026-03-15 |
| 33. Graph Visualization | 1/2 | In Progress|  |
| 34. Onboarding Graph Preview | 0/TBD | Not started | - |
| 35. Chrome Extension Publishing | 0/TBD | Not started | - |
| 36. Landing Page Polish | 0/TBD | Not started | - |
| 37. Privacy Architecture Research | 0/TBD | Not started | - |
| 38. RAG Quality Improvements | 0/TBD | Not started | - |
| 39. Slack User Token Migration & DM Support | 4/4 | Complete    | 2026-04-22 |
| 40. Telegram Shared-Bot Migration | 3/3 | Complete   | 2026-05-04 |

### Phase 39: Slack User Token Migration & DM Support
**Goal**: Add DM and group-DM ingestion to the Slack integration via user-token polling, while keeping the existing bot Events API webhook path for channel messages (Slack's May 2025 rate-limit cap makes user-token polling unviable for channels at scale)
**Depends on**: Nothing (independent)
**Requirements**: SLACK-USR-01, SLACK-USR-02, SLACK-USR-03, SLACK-USR-04, SLACK-USR-05, SLACK-USR-07
**Success Criteria** (what must be TRUE):
  1. Slack OAuth now captures and stores a user token alongside the existing bot token (under Vault key `oauth_slack_{ws}_user_access`)
  2. A new 15-minute polling service fetches new messages from DMs and group DMs using the user token; channels continue to ingest via the bot Events API webhook path (unchanged)
  3. Users can opt in to DM ingestion via a toggle in Settings (and during onboarding); default is OFF, with an inline privacy note
  4. Existing-install users without a user token see a re-auth banner prompting them to reconnect Slack
  5. Channel picker UI remains functional (channels still require bot invites)
  6. Short messages (<10 chars) such as "ok" or "done" are no longer filtered on either path, so they appear in the feed
**Plans:** 5/4 plans complete
Plans:
- [x] 39-01-PLAN.md -- OAuth dual-token capture + /status needs_reauth flag + /dms/toggle endpoint + remove <10 char filter
- [x] 39-02-PLAN.md -- slack_messages.poll_user_messages service (DMs + group DMs, 7d backfill, embedding/graph parity)
- [x] 39-03-PLAN.md -- Settings UI: re-auth banner + DM toggle + typed api.ts clients (channel picker preserved)
- [x] 39-04-PLAN.md -- Wire poll_user_messages into run_polling_fallback + onboarding DM consent panel + E2E verified (177 messages ingested across DMs + channels on live workspace)

### Phase 40: Telegram Shared-Bot Migration

**Goal:** Replace the bring-your-own-bot Telegram flow (Phase 26) with a single shared `@ContextOSBot`. New users connect Telegram in one click via a `t.me/<bot>?startgroup=<code>` deep link — pick a group, bot joins, posts a pairing message, ingestion starts. No BotFather, no token paste, no group-privacy toggle.

**Scope:**
- New tables: `telegram_chat_workspace` (chat_id PK → workspace_id mapping) and `telegram_pairing_codes` (single-use, ~15-min TTL, base64url payload up to 64 chars)
- Global webhook `/api/telegram/webhook` routes incoming updates by `chat_id` lookup; `/start@bot <code>` handler claims chats for workspaces (`my_chat_member` logged for visibility)
- New env: `TELEGRAM_BOT_TOKEN_GLOBAL`, `TELEGRAM_BOT_USERNAME` (kept distinct from existing Sentry-alert `TELEGRAM_BOT_TOKEN`)
- New UI: dashboard "Connect via @ContextOSBot" button rendering the `?startgroup=<code>` deep link, replacing the bot-token form
- Clean cutover: legacy `/webhook/{workspace_id}`, `connect_telegram_bot()`, `disconnect_telegram_bot()`, BYO-bot UI form, `telegram_sync.py` (drain + Telethon), `TelegramSyncSection`, `connectTelegram(token)`, MTProto config (TELEGRAM_API_ID/HASH), and per-workspace Vault tokens are removed in this phase. No dual-mode, no migration banner, no backfill — founding team re-pairs the dogfood workspace manually.

**Out of scope:** DMs to the bot, channel-broadcast posts (groups + supergroups only).

**Depends on:** Phase 26 (TelegramMessage model, webhook scaffolding, graph extraction)
**Requirements**: TG-05 (one-click shared-bot deep-link connect), TG-06 (sticky chat→workspace mapping via single-use 15-min pairing code), TG-07 (single global webhook routing by chat_id with claim-before-ingest dispatcher)
**Plans:** 3/3 plans complete

Plans:
- [x] 40-01-PLAN.md -- Migration `00039` (telegram_chat_workspace + telegram_pairing_codes + cleanup of legacy oauth_tokens rows) + SQLModel additions + `telegram_pairing` service + global `/webhook` dispatcher + `/pairing-code` endpoint + config (TELEGRAM_BOT_TOKEN_GLOBAL, TELEGRAM_BOT_USERNAME)
- [x] 40-02-PLAN.md -- Frontend: typed `createTelegramPairingCode()` client + `TelegramPairingProgress` component (deep link + countdown + Realtime subscription on `telegram_chat_workspace`) + integration-card swap in Settings (replace `TelegramConnect` token form). Live verified: bot @contextOSdev_bot claimed chat -1003644773967, UI flipped to connected via Realtime within ~1s.
- [x] 40-03-PLAN.md -- Phase-26 cleanup (delete `connect_telegram_bot`/`disconnect_telegram_bot`, `telegram_sync.py`, `TelegramSyncSection`, `connectTelegram`/`syncTelegramHistory`/`getTelegramSyncStatus`, MTProto config) + onboarding `step-sources.tsx` migration to new pairing component + Vault token purge script + deploy runbook (`setWebhook` with `my_chat_member`, BotFather Group Privacy OFF). 5 inline deviations during human-verify gate: re-pair-after-kick UPDATE (d9aa4fd), 409 multi-engineer guard (d9aa4fd + 05bebcd), dashboard URL hostname/anchor (d9aa4fd), REPLICA IDENTITY FULL migration patch (d9aa4fd), StrictMode mintedRef (05bebcd).

### Phase 41: Dashboard Pulse Redesign

**Goal:** The dashboard home becomes a pulse surface — a single computed Geist headline answers "did anything I care about happen since I last looked?" in under 4 seconds, with Recent decisions (provenance-quoted) leading the page, Active context tight, and Needs-you compact-or-hidden. Six legacy widgets removed; after human checkpoint, `.pulse-surface` follows the existing global dashboard dark tokens instead of introducing warm/serif styling; per-workspace `last_visited_at` persists with 5-minute inactivity hysteresis; rules-based headline generator (LLM upgrade deferred). Chrome cluster (passive source activity/sync indicator + restyled avatar) replaces the avatar-only top-right.
**Depends on:** Phase 40 (no code dependency; sits chronologically after v1.3)
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06
**Success Criteria** (what must be TRUE):
  1. /dashboard renders exactly four stacked sections in CONTEXT §2 order (Headline → Recent decisions → Active context → Needs you) with the four-pass design critique's typography, palette, and motion discipline applied via a `.pulse-surface` class scoped to the home route.
  2. The headline copy is computed by a pure rules engine against the activity delta since `last_visited_at`; the three template patterns (single-item-dominant, bucket-aggregate, "No new activity.") cover every real case.
  3. `last_visited_at` persists per-(user, workspace) in `dashboard_user_state`, advances only after 5 minutes of inactivity, and drives the headline plus 1px × 14px new-item markers (session-stable per CONTEXT §9).
  4. Each Recent-decision card renders an italics `source_quote` + tertiary attribution line when the data is present, and degrades gracefully (title + people + channels only) when it isn't — no backend backfill required.
  5. The chrome cluster (passive source activity/sync indicator + neutral-bg avatar) replaces the existing avatar-only top-right; mint is used only on the wordmark and active nav link. The originally planned drawer/reconnect affordance was removed at the human checkpoint.
  6. Sibling dashboard subroutes (/context, /settings, /activity, /graph) remain visually unchanged.
**Plans:** 2/3 plans executed

Plans:
- [x] 41-01-PLAN.md — Data + state foundation: fonts loaded, initial palette scope added, `dashboard_user_state` table + RLS, `useLastVisitedAt` hysteresis hook, `useSessionSeenItems` ref store, pure `computeHeadline` rules engine with unit tests, `fetchActivityDelta` + `bucketDelta` helpers. Human checkpoint later superseded warm/serif styling in favor of global dashboard tokens.
- [ ] 41-02-PLAN.md — Pulse surface: rewrite `dashboard/page.tsx` as orchestrator, build `pulse/{headline,recent-decisions,active-context,needs-you,new-item-marker,use-dashboard-data}.tsx`, render provenance quotes when `source_quote` exists on Decision nodes, delete 9 legacy widget files, human-verify checkpoint (wave 2, depends on 41-01)
- [x] 41-03-PLAN.md — Chrome cluster: `chrome/{chrome-nav,sync-indicator,use-sync-state,avatar-puck}.tsx`, passive source activity/sync indicator with Realtime subscription on `activity_events`, sidebar.tsx becomes thin shim, mint discipline enforced. Human checkpoint removed the planned drawer, `Sync all`, and reconnect CTA; see `41-03-SUMMARY.md` and `41-SOURCE-FRESHNESS-RISKS.md`.

### Phase 42: Landing Positioning and SEO Launch Rewrite

**Goal:** Reposition the landing page for launch around source-backed decision memory, with SEO metadata, conversion copy, and Decision Receipt visuals that make ContextOS legible as a source-backed decision graph for engineering/product teams
**Depends on:** Nothing (launch copy can ship independently of Phase 41)
**Requirements**: LAND-04, LAND-05, LAND-06, LAND-07, LAND-08
**Success Criteria** (what must be TRUE):
  1. The hero explains what ContextOS is, who it is for, and why it is useful within the first viewport without vague "AI-native OS" language
  2. The page foregrounds current MVP capabilities only: detected decisions, source links, decision graph/context pages, and source-backed decision receipts
  3. SEO title, description, H1, section headings, and visible body copy target the decision-memory wedge while still capturing adjacent search intent around AI knowledge management, enterprise search, and engineering knowledge graphs
  4. The page includes a low-risk action-layer teaser without promising autonomous task/doc/Slack actions before they exist
  5. Unsupported trust claims are removed or softened unless verified in the codebase/company materials
  6. The hero/product-proof visuals make Decision Receipt the central product primitive, with source chips, people involved, affected systems, and verification state visible in the mock UI
**Plans:** 3/3 plans complete

Plans:
- [x] 42-01-PLAN.md -- SEO metadata, shared launch copy constants, booking CTA label, metadata/CTA regression tests
- [x] 42-02-PLAN.md -- Hero rewrite plus source-backed Decision Receipt visual with source chips, people, affected systems, related work, and verification state
- [x] 42-03-PLAN.md -- Problem/workflow/features/product-proof/booking/trust/footer copy rewrite, claim guards, and desktop/mobile visual verification

### v1.4 Product Expansion & Action Layer (Phases 43-49)

**Milestone Goal:** Expand ContextOS from source-backed decision memory into workspace-aware decision operations: multiple workspaces, post-sync decision gap detection, dismissible guidance, confirmed bot actions, Figma evidence, better Graph RAG, and a researched MCP/CLI developer surface.

**Phase Status:**
- [ ] **Phase 43: Multi-workspace Foundation** - Not started
- [x] **Phase 44: Suggestion System and Dismissals** - Durable workspace suggestions and dismissal lifecycle (completed 2026-05-25)
- [x] **Phase 45: Post-sync Missed-decision Detection** - Missed-decision scan, review, lifecycle, and Decision promotion complete (completed 2026-05-25; remote schema push follow-up pending)
- [ ] **Phase 46: Graph RAG Quality Improvements** - Not started
- [ ] **Phase 47: Confirmed Action Layer Bots** - Not started
- [ ] **Phase 48: Figma Decision Evidence Integration** - Not started
- [ ] **Phase 49: MCP and CLI Surface Research** - Not started

### Phase 43: Multi-workspace Foundation

**Goal:** Users can create, switch, and manage multiple workspaces while all source data, graph records, suggestions, integrations, and future actions stay isolated by workspace.
**Depends on:** Phase 42
**Requirements**: WS-01, WS-02, WS-03, WS-04, WS-05
**Success Criteria** (what must be TRUE):
  1. Existing single-workspace users keep their current workspace and integrations after migration.
  2. User can create another workspace, switch active workspace, and see dashboard/settings/graph data scoped to that workspace.
  3. OAuth credentials, sync cursors, source records, graph nodes, suggestions, and action audit rows are workspace-scoped with no cross-workspace leakage.
  4. Empty, archived, or misconfigured workspaces render recoverable states instead of breaking the dashboard.
**Plans:** TBD

Plans:
- [ ] TBD (run /gsd-plan-phase 43 to break down)

### Phase 44: Suggestion System and Dismissals

**Goal:** ContextOS has a durable suggestion model and dashboard surface for workspace-scoped recommendations, with dismiss/snooze/resolve semantics that future decision-gap and action-layer work can reuse.
**Depends on:** Phase 43
**Requirements**: SUG-01, SUG-02, SUG-03, SUG-04
**Success Criteria** (what must be TRUE):
  1. Suggestions persist with type, source evidence, priority, status, workspace, and provenance.
  2. User can dismiss, snooze, resolve, and reopen suggestions, and that state survives refreshes and future syncs.
  3. Dashboard shows suggestions in a bounded surface after sync completion without displacing the Recent decisions hierarchy.
  4. ContextOS can recommend missing source coverage such as meeting notes or Figma when evidence gaps are detected.
**Plans:** 4/4 plans complete

Plans:
- [x] 44-01-PLAN.md -- Suggestion schema, SQLModel, lifecycle service, missing-source generation, and backend tests
- [x] 44-02-PLAN.md -- Authenticated suggestion API routes, router registration, and digest decision publication hook
- [x] 44-03-PLAN.md -- Dashboard Needs review data fetch, right-rail surface, lifecycle actions, and component coverage
- [x] 44-04-PLAN.md -- Full suggestion queue route, verification, and closeout

### Phase 45: Post-sync Missed-decision Detection

**Goal:** After source syncs, ContextOS detects likely decisions that were discussed but not documented or planned, then lets users confirm, reject, or defer them from the suggestion system.
**Depends on:** Phase 44
**Requirements**: GAP-01, GAP-02, GAP-03, GAP-04
**Success Criteria** (what must be TRUE):
  1. Sync completion can enqueue a missed-decision scan for recent workspace sources.
  2. Candidate missed decisions include source evidence, confidence, people involved, and affected systems or workstreams.
  3. User can confirm, reject, or defer each candidate.
  4. Confirmed candidates become source-backed Decision Receipts or follow-up suggestions while preserving the source trail.
**Plans:** 5/5 plans complete

Plans:
**Wave 1**
- [x] 45-00-PLAN.md -- Phase 44 suggestion contract checkpoint before Phase 45 implementation proceeds
- [x] 45-01-PLAN.md -- Missed-decision scan schema, source windows, non-blocking enqueue, and queued-run drain
  - Note: cloud `supabase db push` still needs project linkage; local schema was applied with `psql` and repaired as migration `00042`.

**Wave 2**
- [x] 45-02-PLAN.md -- Source-backed candidate extraction, confidence tiers, layered dedupe, and suggestion publishing

**Wave 3**
- [x] 45-03-PLAN.md -- Review actions, candidate lifecycle transitions, evidence attachment, and Decision Receipt promotion

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 45-04-PLAN.md -- Bounded dashboard Needs review UI, typed action helpers, and component coverage
  - Note: authenticated visual verification remains a follow-up because Browser automation exposed no browser backend in the execution session; automated placement/component coverage passed.

### Phase 46: Graph RAG Quality Improvements

**Goal:** Retrieval over the decision graph becomes measurable and more reliable, with better recall, provenance, source freshness handling, and grounding for context pages and future action suggestions.
**Depends on:** Phase 45
**Requirements**: GRAG-01, GRAG-02, GRAG-03, GRAG-04
**Success Criteria** (what must be TRUE):
  1. Retrieval can explicitly target decision receipts, source evidence, graph neighborhoods, and related work.
  2. A repeatable evaluation set measures decision recall, source-link accuracy, stale-context avoidance, and action-suggestion grounding.
  3. Ranking uses graph adjacency, source freshness, workspace scope, and decision verification state.
  4. Context pages and suggestion/action generation can explain which graph/source signals supported an answer.
**Plans:** 5/7 plans executed

Plans:
**Wave 1**
- [x] 46-00-PLAN.md -- Wave 0 Graph RAG eval runner, golden dataset, trace contracts, and Make target
- [x] 46-01-PLAN.md -- Wave 0 suggestion-family quality contracts and missed-decision eval extensions
- [x] 46-02-PLAN.md -- Target-aware retrieval routing, stream parity, and Phase 45 Decision property support

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 46-03-PLAN.md -- Freshness, verification, source originality, selected/dropped ranking features, and ranking evals

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 46-04-PLAN.md -- Context-page source explanation persistence and synthesis prompt provenance packets
- [ ] 46-05-PLAN.md -- Suggestion/action-hint grounding explanations and no-write boundary tests

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 46-06-PLAN.md -- Bounded context-sidebar source path explanation UI

### Phase 47: Confirmed Action Layer Bots

**Goal:** Slack and Telegram bots suggest useful follow-up actions from decisions, but every write to another tool requires explicit human confirmation and keeps the decision receipt attached as evidence.
**Depends on:** Phase 46
**Requirements**: ACTL-01, ACTL-02, ACTL-03, ACTL-04, ACTL-05
**Success Criteria** (what must be TRUE):
  1. Slack and Telegram can show workspace-scoped action suggestions linked to a decision, missed-decision candidate, stale doc, or conflicting implementation signal.
  2. User must confirm before ContextOS creates Jira/Linear tasks, posts PR comments, asks owners, or drafts doc updates.
  3. Confirmed actions include the relevant decision receipt or source trail in the target surface.
  4. Every suggestion and action outcome is recorded with actor, workspace, source decision, target tool, and status.
  5. User can dismiss or snooze action suggestions from the bot or dashboard.
**Plans:** TBD

Plans:
- [ ] TBD (run /gsd-plan-phase 47 to break down)

### Phase 48: Figma Decision Evidence Integration

**Goal:** Figma becomes a first-class evidence source for product and design decisions, so design-review context can appear in decision receipts, graph nodes, and source chips.
**Depends on:** Phase 43
**Requirements**: FIG-01, FIG-02, FIG-03, FIG-04
**Success Criteria** (what must be TRUE):
  1. User can connect Figma to a workspace with OAuth or an approved token flow.
  2. User can select Figma files or projects to sync.
  3. ContextOS ingests relevant file metadata, comments, frame references, and design-review evidence.
  4. Figma evidence appears in Decision Receipts, graph nodes, and source chips alongside Slack, docs, tickets, and PRs.
**Plans:** TBD

Plans:
- [ ] TBD (run /gsd-plan-phase 48 to break down)

### Phase 49: MCP and CLI Surface Research

**Goal:** Decide whether ContextOS should expose MCP, CLI, or both for developer and agent workflows, then define the first read-only surface contract with auth, workspace selection, local config, and audit boundaries.
**Depends on:** Phase 43
**Requirements**: DEV-01, DEV-02, DEV-03
**Success Criteria** (what must be TRUE):
  1. A research document compares MCP, CLI, and combined approaches for ContextOS user stories and security constraints.
  2. The first developer surface is scoped to read-only decision/context operations before any write-capable tooling is planned.
  3. The recommendation defines authentication, workspace selection, local config, token handling, and audit logging.
  4. The output gives a concrete next build phase if MCP, CLI, or both are selected.
**Plans:** TBD

Plans:
- [ ] TBD (run /gsd-plan-phase 49 to break down)

## Product Expansion Progress

**Execution Order:**
Phases execute in numeric order: 43 -> 44 -> 45 -> 46 -> 47, with 48 and 49 independent after Phase 43.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 43. Multi-workspace Foundation | 0/TBD | Not started | - |
| 44. Suggestion System and Dismissals | 4/4 | Complete    | 2026-05-25 |
| 45. Post-sync Missed-decision Detection | 3/5 | In Progress|  |
| 46. Graph RAG Quality Improvements | 5/7 | In Progress|  |
| 47. Confirmed Action Layer Bots | 0/TBD | Not started | - |
| 48. Figma Decision Evidence Integration | 0/TBD | Not started | - |
| 49. MCP and CLI Surface Research | 0/TBD | Not started | - |
