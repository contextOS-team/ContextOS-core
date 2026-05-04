# Requirements: ContextOS v1.3 Live Intelligence

**Defined:** 2026-03-15
**Core Value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.

## v1.3 Requirements

Requirements for the live intelligence milestone. Each maps to roadmap phases.

### Activity Events

- [x] **ACT-05**: All integration sync services (Linear, Slack, GitHub, GitLab, Jira, Notion, Telegram) emit events to activity_events on sync completion
- [x] **ACT-06**: Integration connect/disconnect actions emit activity events
- [x] **ACT-07**: Context page generation (start, complete, error) emits activity events
- [x] **ACT-08**: Activity tab shows events in real-time via existing Supabase Realtime subscription

### Graph Visualization

- [x] **GRAPH-01**: Interactive node/edge graph visualization for a ticket showing people, decisions, PRs, messages, code
- [ ] **GRAPH-02**: Graph visualization embedded in context page detail view (/dashboard/context/[id])
- [ ] **GRAPH-03**: Standalone /dashboard/graph route for exploring the knowledge graph
- [ ] **GRAPH-04**: Click-to-expand node detail panel showing full content (message text, PR summary, decision rationale)

### Chrome Extension

- [ ] **EXT-01**: Extension packaged and published to Chrome Web Store
- [ ] **EXT-02**: Content script detects Linear ticket pages and shows ContextOS context inline/sidebar
- [ ] **EXT-03**: Content script detects Jira issue pages and shows ContextOS context inline/sidebar
- [ ] **EXT-04**: Extension popup redesigned to match dark theme brand identity

### Landing Page

- [ ] **LAND-01**: Integrations section updated to show all 9 integrations (add GitLab, Jira, Telegram, Slack Huddles)
- [ ] **LAND-02**: General typography, spacing, and animation polish
- [ ] **LAND-03**: Privacy/trust section added highlighting data ownership

### Onboarding

- [ ] **ONB-10**: Step 4 replaced with knowledge graph preview or mock context page instead of waiting for sync to complete
- [ ] **ONB-11**: Onboarding completion doesn't depend on sync finishing

### Privacy

- [ ] **PRIV-01**: Architecture research for self-hosted/local LLM deployment options

### RAG

- [ ] **RAG-01**: RAG quality improvements (scope TBD by Dulat)

### Telegram Shared Bot

- [x] **TG-05**: Users connect Telegram in one click via a shared `@ContextOSBot` deep link — no BotFather, no token paste, no group-privacy toggle. Available from both the Settings → Integrations card and the onboarding sources step.
- [x] **TG-06**: Group/supergroup chats are bound to a workspace via a single-use, ~15-min TTL pairing code. Mapping is sticky — first claim wins; no cross-workspace re-claim. Soft-deleted on `kicked`/`left`/`banned` `my_chat_member` events; `telegram_messages` history retained.
- [x] **TG-07**: A single global webhook `/api/telegram/webhook` routes all updates by `chat_id` lookup against `telegram_chat_workspace`; messages are ingested through the existing filter + upsert + graph pipeline; `/start@bot <code>` claim path is detected and routed BEFORE the ingestion path so pairing commands never pollute `telegram_messages`.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Privacy (Implementation)

- **PRIV-02**: Local LLM option (Ollama/local model instead of Gemini)
- **PRIV-03**: Self-hosted deployment (Docker Compose or Helm chart)
- **PRIV-04**: Bring-your-own API key for OpenAI/Anthropic/Gemini

### Advanced Graph

- **GRAPH-05**: Graph diff view (how the knowledge graph changed over time)
- **GRAPH-06**: Graph-based search (find all nodes related to a person/decision)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mobile app / responsive design | Desktop-first internal tool |
| Team invites and role management | Single team dogfooding, not needed yet |
| Slack historical backfill | Real-time ingestion covers current needs |
| Full privacy implementation | Research first in v1.3, implement in v1.4 based on findings |
| Telegram DMs to the shared bot | Phase 40 scope locked to groups/supergroups; Telegram terms differ for DMs |
| Telegram channel-broadcast post ingestion | One-way broadcasts; different content surface than group ingestion |
| Per-chat enable/disable toggle for Telegram | Joining + pairing the bot equals consent in v1; finer-grained UI is a future enhancement |
| Phase-26 BYO-bot migration banner + backfill | No real Phase-26 production users to migrate; founding team re-pairs manually |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ACT-05 | Phase 32 | Complete |
| ACT-06 | Phase 32 | Complete |
| ACT-07 | Phase 32 | Complete |
| ACT-08 | Phase 32 | Complete |
| GRAPH-01 | Phase 33 | Complete |
| GRAPH-02 | Phase 33 | Pending |
| GRAPH-03 | Phase 33 | Pending |
| GRAPH-04 | Phase 33 | Pending |
| ONB-10 | Phase 34 | Pending |
| ONB-11 | Phase 34 | Pending |
| EXT-01 | Phase 35 | Pending |
| EXT-02 | Phase 35 | Pending |
| EXT-03 | Phase 35 | Pending |
| EXT-04 | Phase 35 | Pending |
| LAND-01 | Phase 36 | Pending |
| LAND-02 | Phase 36 | Pending |
| LAND-03 | Phase 36 | Pending |
| PRIV-01 | Phase 37 | Pending |
| RAG-01 | Phase 38 | Pending |
| TG-05 | Phase 40 | Complete |
| TG-06 | Phase 40 | Complete |
| TG-07 | Phase 40 | Complete |

**Coverage:**
- v1.3 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-05-03 — added TG-05, TG-06, TG-07 for Phase 40 (Telegram Shared-Bot Migration)*
