# Roadmap: ContextOS

## Milestones

- :white_check_mark: **v1.0 Dogfood** - Phases 1-14 (shipped 2026-03-03)
- :white_check_mark: **v1.1 Dashboard & Onboarding** - Phases 15-31 (shipped 2026-03-15)
- :white_check_mark: **v1.2 GraphRAG** - Phases 22-27 (shipped 2026-03-08)
- :construction: **v1.3 Live Intelligence** - Phases 32-38 (in progress)

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
| 40. Telegram Shared-Bot Migration | 2/3 | In Progress|  |

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
**Plans:** 2/3 plans executed

Plans:
- [x] 40-01-PLAN.md -- Migration `00039` (telegram_chat_workspace + telegram_pairing_codes + cleanup of legacy oauth_tokens rows) + SQLModel additions + `telegram_pairing` service + global `/webhook` dispatcher + `/pairing-code` endpoint + config (TELEGRAM_BOT_TOKEN_GLOBAL, TELEGRAM_BOT_USERNAME)
- [x] 40-02-PLAN.md -- Frontend: typed `createTelegramPairingCode()` client + `TelegramPairingProgress` component (deep link + countdown + Realtime subscription on `telegram_chat_workspace`) + integration-card swap in Settings (replace `TelegramConnect` token form). Live verified: bot @contextOSdev_bot claimed chat -1003644773967, UI flipped to connected via Realtime within ~1s.
- [ ] 40-03-PLAN.md -- Phase-26 cleanup (delete `connect_telegram_bot`/`disconnect_telegram_bot`, `telegram_sync.py`, `TelegramSyncSection`, `connectTelegram`/`syncTelegramHistory`/`getTelegramSyncStatus`, MTProto config) + onboarding `step-sources.tsx` migration to new pairing component + Vault token purge script + deploy runbook (`setWebhook` with `my_chat_member`, BotFather Group Privacy OFF)

---
*Roadmap created: 2026-02-24*
*v1.1 shipped: 2026-03-15*
*v1.3 roadmap added: 2026-03-15*
*Phase 39 planned: 2026-04-22*
*Phase 40 planned: 2026-05-03*
