# Roadmap: ContextOS

## Milestones

- :white_check_mark: **v1.0 Dogfood** - Phases 1-14 (shipped 2026-03-03)
- :white_check_mark: **v1.1 Dashboard & Onboarding** - Phases 15-21 (shipped 2026-03-06)
- :white_check_mark: **v1.2 GraphRAG** - Phases 22-27 (shipped 2026-03-08)

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

<details>
<summary>v1.2 GraphRAG (Phases 22-27) - SHIPPED 2026-03-08</summary>

- [x] **Phase 22: Graph Foundation + Rule-Based Extraction** - Graph tables, traversal function, indexes, and deterministic regex extractors for structured references (completed 2026-03-06)
- [x] **Phase 23: Identity Resolution** - Cross-source person unification via email-based deterministic matching and fuzzy candidate flagging (completed 2026-03-07)
- [x] **Phase 24: LLM Extraction + Decision Extraction** - Semantic entity extraction via Gemini Flash batch pipeline with decision nodes as highest-value entity (completed 2026-03-07)
- [x] **Phase 25: Graph-Enhanced Retrieval** - Graph traversal as third retrieval signal with depth-decay scoring blended into existing search (completed 2026-03-08)
- [x] **Phase 26: Synthesis + Code-to-Discussion Linking** - Context pages enhanced with decision trails, relationship paths, people cross-references, and code provenance (completed 2026-03-08)
- [x] **Phase 27: Graph Explorer API** - Subgraph JSON endpoint for a ticket's graph neighborhood (completed 2026-03-08)

</details>

---
*Roadmap created: 2026-02-24*
*v1.1 milestone added: 2026-03-04*
*v1.2 GraphRAG milestone added: 2026-03-07*
*v1.2 GraphRAG shipped: 2026-03-08*
