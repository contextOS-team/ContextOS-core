# Roadmap: ContextOS

## Milestones

- :white_check_mark: **v1.0 Dogfood** - Phases 1-14 (shipped 2026-03-03)
- :white_check_mark: **v1.1 Dashboard & Onboarding** - Phases 15-31 (shipped 2026-03-15)
- :construction: **v1.2 TBD** - (planning)

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

### v1.2 (Planning)

No phases yet. Run `/gsd:new-milestone` to define requirements and roadmap.

---
*Roadmap created: 2026-02-24*
*v1.1 shipped: 2026-03-15*
