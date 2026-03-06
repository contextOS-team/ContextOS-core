# Roadmap: ContextOS

## Milestones

- :white_check_mark: **v1.0 Dogfood** - Phases 1-14 (shipped 2026-03-03)
- :white_check_mark: **v1.1 Dashboard & Onboarding** - Phases 15-21 (shipped 2026-03-06)
- :construction: **v1.2 GraphRAG** - Phases 22-27 (in progress)

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

<details>
<summary>v1.1 Dashboard & Onboarding (Phases 15-21) - SHIPPED 2026-03-06</summary>

- [x] **Phase 15: Dark Theme Token Foundation** - Brand-tinted OKLCH tokens, DarkModeApplier, JetBrains Mono, navigation restructure, skeleton states (completed 2026-03-04)
- [x] **Phase 16: Auth Redesign + Schema Foundation** - Dark-themed auth pages, user_onboarding_state and activity_events tables, onboarding gate (completed 2026-03-04)
- [x] **Phase 17: Onboarding Wizard** - 4-step guided wizard with OAuth state preservation and animated transitions (completed 2026-03-04)
- [x] **Phase 18: Activity Timeline** - Chronological event feed with real-time updates and day-group dividers (completed 2026-03-04)
- [x] **Phase 19: Context Feed + Dashboard Home** - Browsable context feed with filtering, search, detail view, and dashboard summary (completed 2026-03-04)
- [x] **Phase 20: Settings Page** - API key management, workspace editing, team member view (completed 2026-03-06)
- [x] **Phase 21: Auth Redesign + Social OAuth** - Auth redesign and social OAuth (completed 2026-03-06)

</details>

### v1.2 GraphRAG (In Progress)

**Milestone Goal:** Add a knowledge graph layer (plain PostgreSQL tables with recursive CTEs) that captures entities and relationships across all data sources, improving context page quality by enabling multi-hop traversal, cross-source identity resolution, and decision trail extraction -- blended with existing hybrid search, not replacing it.

- [ ] **Phase 22: Graph Foundation + Rule-Based Extraction** - Graph tables, traversal function, indexes, and deterministic regex extractors for structured references
- [ ] **Phase 23: Identity Resolution** - Cross-source person unification via email-based deterministic matching and fuzzy candidate flagging
- [ ] **Phase 24: LLM Extraction + Decision Extraction** - Semantic entity extraction via Gemini Flash batch pipeline with decision nodes as highest-value entity
- [ ] **Phase 25: Graph-Enhanced Retrieval** - Graph traversal as third retrieval signal with depth-decay scoring blended into existing search
- [ ] **Phase 26: Synthesis + Code-to-Discussion Linking** - Context pages enhanced with decision trails, relationship paths, people cross-references, and code provenance
- [ ] **Phase 27: Graph Explorer API** - Subgraph JSON endpoint for a ticket's graph neighborhood

## Phase Details

<details>
<summary>v1.1 Phase Details (Phases 15-21)</summary>

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
**Plans**: 3 plans (complete)

### Phase 16: Auth Redesign + Schema Foundation
**Goal**: Auth pages match the dark brand identity and the database tables required for onboarding and activity tracking exist with proper RLS, indexes, and triggers
**Depends on**: Phase 15
**Requirements**: AUTH-01, AUTH-02, ACT-04, ONB-07, ONB-09
**Success Criteria** (what must be TRUE):
  1. Login and signup pages render in the dark theme with the same teal accent, typography, and surface tokens as the dashboard
  2. user_onboarding_state table exists with RLS, auto-created on first sign-in, queryable for onboarding completion status
  3. activity_events table exists with workspace-scoped RLS, (workspace_id, created_at DESC) index, and 30-day retention policy
  4. Users who have not completed onboarding are redirected away from the dashboard to the onboarding flow
**Plans**: 3 plans (complete)

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
**Plans**: 2 plans (complete)

### Phase 18: Activity Timeline
**Goal**: Users see a live chronological feed of workspace events (syncs, context generated, integrations connected) that proves the system is working
**Depends on**: Phase 16
**Requirements**: ACT-01, ACT-02, ACT-03
**Success Criteria** (what must be TRUE):
  1. User sees a chronological feed of workspace events (syncs, context generated, integrations connected) on the dashboard
  2. Events display with type-specific icons, relative timestamps, and day-group dividers
  3. New events appear in real-time without page refresh via Supabase Realtime
**Plans**: 2 plans (complete)

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
**Plans**: 3 plans (complete)

### Phase 20: Settings Page
**Goal**: Users can manage API keys, workspace settings, and view team members from a dedicated settings page
**Depends on**: Phase 15
**Requirements**: SET-01, SET-02, SET-03, SET-04
**Success Criteria** (what must be TRUE):
  1. User can create API keys (full key shown once on creation, then prefix-only) and revoke existing keys
  2. User can edit their workspace name from settings
  3. User can view connected team members
  4. Settings page is accessible from the dashboard navigation
**Plans**: 2 plans (complete)

### Phase 21: Auth Redesign + Social OAuth
**Goal**: Auth redesign and social OAuth
**Depends on**: Phase 20
**Plans**: 2 plans (complete)

</details>

### Phase 22: Graph Foundation + Rule-Based Extraction
**Goal**: The knowledge graph schema exists in Supabase Postgres with workspace-scoped RLS and performant traversal, and deterministic regex extractors immediately populate graph nodes and edges from ingested content at zero LLM cost
**Depends on**: Phase 21 (v1.1 complete)
**Requirements**: GRAPH-01, GRAPH-02, GRAPH-03, EXTR-01, EXTR-02
**Success Criteria** (what must be TRUE):
  1. graph_nodes and graph_edges tables exist with workspace-scoped RLS, fingerprint-based deduplication, and JSONB properties for flexible entity storage
  2. traverse_graph() SECURITY DEFINER function performs recursive CTE traversal with configurable depth limiting and workspace validation (no per-row RLS overhead)
  3. Composite indexes on (workspace_id, entity_type), (workspace_id, relationship_type), and fingerprint uniqueness are in place and used by query plans
  4. When a webhook delivers a Slack message or Linear ticket containing ticket references, @mentions, PR numbers, or file paths, corresponding graph nodes and edges are created automatically with no LLM calls
  5. Re-ingesting the same content does not create duplicate nodes -- fingerprint deduplication prevents it
**Plans**: 3 plans
Plans:
- [ ] 22-01-PLAN.md -- Graph SQL migrations (tables, RLS, indexes, traversal function) + SQLModels + graph_ops upsert service
- [ ] 22-02-PLAN.md -- Five regex extractors with registry pattern and comprehensive unit tests
- [ ] 22-03-PLAN.md -- Wire extraction into all webhook handlers + backfill script for existing content

### Phase 23: Identity Resolution
**Goal**: Person identities are unified across Linear, Slack, GitHub, and Fathom into single canonical graph nodes so that context pages correctly attribute who said and decided what across tools
**Depends on**: Phase 22
**Requirements**: IDENT-01, IDENT-02, IDENT-03
**Success Criteria** (what must be TRUE):
  1. A person who exists in both Linear and Slack resolves to a single Person node in the graph via email-based deterministic matching
  2. During integration setup, the identity mapping table is seeded from team roster APIs (Linear users, Slack members, GitHub collaborators) so resolution works from day one
  3. When names match across platforms but emails differ, a candidate same_as edge is created with a confidence score -- no auto-merging occurs on name alone
**Plans**: TBD

### Phase 24: LLM Extraction + Decision Extraction
**Goal**: The system extracts semantic entities (decisions, rationale, blockers) from Slack messages and meeting transcripts via Gemini Flash, with decisions as the highest-value entity linking what was decided to who decided it and which tickets it affects
**Depends on**: Phase 22
**Requirements**: EXTR-03, EXTR-04, EXTR-05, EXTR-06, DECIDE-01, DECIDE-02, DECIDE-03
**Success Criteria** (what must be TRUE):
  1. After batch LLM extraction runs on a Slack thread containing a decision, a Decision node appears in the graph with description, rationale, source reference, date, and confidence score
  2. Decision nodes link bidirectionally to the Person who made the decision, the SlackThread or Meeting where it was discussed, and the Ticket(s) it affects
  3. Bot messages, short messages (<50 chars), and emoji-only content are skipped before LLM extraction -- only substantive content burns API budget
  4. Re-running extraction on already-processed content is skipped via content hash deduplication -- no duplicate entities, no wasted Gemini calls
  5. Extracted entities can be traced back to their source text -- no hallucinated entities that cannot be found in the original message
**Plans**: TBD

### Phase 25: Graph-Enhanced Retrieval
**Goal**: The linking engine uses graph traversal as a third retrieval signal alongside explicit refs and hybrid search, finding multi-hop connections that embedding similarity alone cannot surface
**Depends on**: Phase 22, Phase 23, Phase 24
**Requirements**: RETR-01, RETR-02, RETR-03
**Success Criteria** (what must be TRUE):
  1. find_related_content() returns results from graph traversal alongside explicit ref and hybrid search results -- three distinct retrieval signals
  2. Graph results are scored with depth decay (1-hop scores highest, decaying per hop) and blended with existing signal scores so graph evidence ranks naturally alongside text similarity
  3. Graph context passed to synthesis prompts is capped at a fixed token budget -- adding graph data never causes context overflow or degrades synthesis quality
**Plans**: TBD

### Phase 26: Synthesis + Code-to-Discussion Linking
**Goal**: Context pages visibly improve with decision trails, relationship paths, cross-referenced people, and code-to-discussion provenance -- the user-facing payoff of the entire graph layer
**Depends on**: Phase 25
**Requirements**: SYNTH-01, SYNTH-02, SYNTH-03, SYNTH-04, CODE-01, CODE-02, CODE-03
**Success Criteria** (what must be TRUE):
  1. A context page for a ticket with graph data includes a decision trail showing what was decided, by whom, where it was discussed, and which tickets it affected
  2. Context pages show relationship paths explaining why content is connected (e.g., "This PR was discussed in Slack thread #deploy-v2 by @alex who also authored the spec in Notion")
  3. Context pages cross-reference people showing their involvement across sources (e.g., "@alex: authored ticket, discussed in Slack, reviewed PR")
  4. For a ticket with no graph data, the context page renders identically to pre-graph behavior -- graceful degradation with no errors or empty sections
  5. When a Slack message discusses a file path or function name that exists in code_chunks, context pages show code-to-discussion provenance in the relevant code section
**Plans**: TBD

### Phase 27: Graph Explorer API
**Goal**: An API endpoint exposes the graph neighborhood for any ticket as structured JSON, enabling future frontend visualization and external tool consumption
**Depends on**: Phase 25
**Requirements**: GAPI-01
**Success Criteria** (what must be TRUE):
  1. GET request for a ticket's graph neighborhood returns a JSON response containing nodes (with entity types, names, properties) and edges (with relationship types, weights) for the surrounding subgraph
  2. The endpoint respects workspace scoping -- users can only see graph data for their own workspace
**Plans**: TBD

## Coverage

### v1.2 Coverage

**26/26 v1.2 requirements mapped.**

| Category | Requirements | Phase |
|----------|-------------|-------|
| Graph Foundation | GRAPH-01, GRAPH-02, GRAPH-03 (3) | Phase 22 |
| Entity Extraction (Rule-based) | EXTR-01, EXTR-02 (2) | Phase 22 |
| Identity Resolution | IDENT-01, IDENT-02, IDENT-03 (3) | Phase 23 |
| Entity Extraction (LLM) | EXTR-03, EXTR-04, EXTR-05, EXTR-06 (4) | Phase 24 |
| Decision Extraction | DECIDE-01, DECIDE-02, DECIDE-03 (3) | Phase 24 |
| Graph Retrieval | RETR-01, RETR-02, RETR-03 (3) | Phase 25 |
| Synthesis | SYNTH-01, SYNTH-02, SYNTH-03, SYNTH-04 (4) | Phase 26 |
| Code-to-Discussion | CODE-01, CODE-02, CODE-03 (3) | Phase 26 |
| Graph Explorer API | GAPI-01 (1) | Phase 27 |

No orphaned requirements. No duplicate mappings.

### v1.1 Coverage

<details>
<summary>36/36 v1.1 requirements mapped (all complete)</summary>

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

</details>

## Progress

**Execution Order:**
Phase 22 (schema + regex) --> Phase 23 + Phase 24 (can parallelize after 22) --> Phase 25 (needs populated graph) --> Phase 26 + Phase 27 (can parallelize after 25)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 22. Graph Foundation + Rule-Based Extraction | 2/3 | In Progress|  | - |
| 23. Identity Resolution | v1.2 | 0/TBD | Not started | - |
| 24. LLM Extraction + Decision Extraction | v1.2 | 0/TBD | Not started | - |
| 25. Graph-Enhanced Retrieval | v1.2 | 0/TBD | Not started | - |
| 26. Synthesis + Code-to-Discussion Linking | v1.2 | 0/TBD | Not started | - |
| 27. Graph Explorer API | v1.2 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-24*
*v1.1 milestone added: 2026-03-04*
*v1.2 GraphRAG milestone added: 2026-03-07*
