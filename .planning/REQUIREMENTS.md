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
- [x] **LAND-04**: Landing hero and first viewport reposition ContextOS around source-backed decision memory for engineering teams, not generic context gathering or AI search
- [x] **LAND-05**: SEO title, description, H1, and visible headings target the decision-memory wedge while naturally covering adjacent intent around AI knowledge management, enterprise search, and engineering knowledge graphs
- [ ] **LAND-06**: Landing copy foregrounds current MVP capabilities only: detected decisions, source links, graph/context pages, and generated ticket/PR context
- [x] **LAND-07**: Action-layer copy is clearly framed as coming next unless implemented, and unsupported trust/compliance claims are removed or softened
- [x] **LAND-08**: Landing visuals introduce Decision Receipt as the primary product primitive, showing decision, rationale, people involved, original sources, affected systems, and verification status instead of generic AI glow or ticket-only context

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

### Dashboard Pulse (Phase 41 — post-v1.3)

Phase 41 sits chronologically after the v1.3 milestone closed at Phase 40. These requirements were added during planning (2026-05-20) to give the redesign explicit traceability.

- [ ] **DASH-01**: Dashboard home replaces the six-equal-section layout with a pulse layout: compact Geist Sans headline (computed from since-last-visit delta) above Recent decisions (dense lead panel, 2 visible above the fold) -> Active context (top 3 panel rows) -> Needs you (hidden when empty). Recent Activity, graph thumbnail, This Week sparkline, sprint badge, integration dots, and the greeting line are removed from home. Human checkpoint rejected the warm/serif direction; `.pulse-surface` now follows the existing global dashboard dark tokens and only scopes pulse-specific affordances.
- [x] **DASH-02**: Per-(user, workspace) `last_visited_at` timestamp persists to a new `dashboard_user_state` table and advances only after 5 min of page-level inactivity OR explicit dismissal — never on tab-flip. A `useLastVisitedAt` React hook reads on mount, debounces writes through Supabase, and exposes a stable per-session value to the headline generator and new-item markers (Pitfall 5 — mount-time read only).
- [x] **DASH-03**: Rules-based pure-function headline generator (`computeHeadline`) selects between three templates from the activity delta since `last_visited_at`: (a) single-item-dominant "X has been waiting on Y since Z." (any needs-you item assigned to current user wins), (b) bucket-aggregate "N decisions and M source updates.", (c) zero-new fallback "No new activity." LLM-generated headlines deferred. The home page does not render visible headline subtext after human checkpoint.
- [x] **DASH-04**: Top-nav adds a right-aligned chrome cluster (source activity/sync state text + 1px real-tick progress bar + restyled avatar puck) replacing the avatar-only chrome. Driven by Supabase Realtime subscription on `activity_events`. Mint color reserved for wordmark + active nav-link only. Human checkpoint deviation: the integration-health click target, Radix slide-over, `Sync all`, and reconnect CTA were removed after review; source freshness risks are tracked in `41-SOURCE-FRESHNESS-RISKS.md`.
- [ ] **DASH-05**: Unseen items carry a 1px × 14px primary-token vertical marker in the left gutter when `activity_events.created_at > last_visited_at`. Marker persists for the entire session it was seen in (no mid-visit decay) via a ref-based `useSessionSeenItems` set; decays only when `last_visited_at` advances after the 5-min inactivity hysteresis fires.
- [ ] **DASH-06**: Each Recent-decision card renders a one-line provenance quote in italics + tertiary-color attribution line (`— Name in #channel, 18h ago`) when the Decision node's `properties.source_quote` is present; the card gracefully renders title + people + channels when absent. No backend backfill in this phase — `source_quote` is already populated by `llm_extractor.py` since v1.2.

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
| LAND-04 | Phase 42 | Complete |
| LAND-05 | Phase 42 | Complete |
| LAND-06 | Phase 42 | Pending |
| LAND-07 | Phase 42 | Complete |
| LAND-08 | Phase 42 | Complete |
| PRIV-01 | Phase 37 | Pending |
| RAG-01 | Phase 38 | Pending |
| TG-05 | Phase 40 | Complete |
| TG-06 | Phase 40 | Complete |
| TG-07 | Phase 40 | Complete |

| DASH-01 | Phase 41 | Pending |
| DASH-02 | Phase 41 | Complete |
| DASH-03 | Phase 41 | Complete |
| DASH-04 | Phase 41 | Complete |
| DASH-05 | Phase 41 | Pending |
| DASH-06 | Phase 41 | Pending |

**Coverage:**
- v1.3 core requirements: 22 total
- Phase 41/42 post-v1.3 requirements: 11 total
- Total active requirements: 33
- Mapped to phases: 33
- Unmapped: 0
- Post-v1.3 launch/dashboard requirements: Phase 41 has 6 dashboard requirements, Phase 42 has 5 landing requirements -- all mapped

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-05-22 - added Phase 42 launch positioning, SEO, and Decision Receipt visual requirements*
