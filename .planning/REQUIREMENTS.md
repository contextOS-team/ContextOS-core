# Requirements: ContextOS v1.3 Live Intelligence

**Defined:** 2026-03-15
**Core Value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.

## v1.3 Requirements

Requirements for the live intelligence milestone. Each maps to roadmap phases.

### Activity Events

- [ ] **ACT-05**: All integration sync services (Linear, Slack, GitHub, GitLab, Jira, Notion, Telegram) emit events to activity_events on sync completion
- [ ] **ACT-06**: Integration connect/disconnect actions emit activity events
- [ ] **ACT-07**: Context page generation (start, complete, error) emits activity events
- [ ] **ACT-08**: Activity tab shows events in real-time via existing Supabase Realtime subscription

### Graph Visualization

- [ ] **GRAPH-01**: Interactive node/edge graph visualization for a ticket showing people, decisions, PRs, messages, code
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

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ACT-05 | TBD | Pending |
| ACT-06 | TBD | Pending |
| ACT-07 | TBD | Pending |
| ACT-08 | TBD | Pending |
| GRAPH-01 | TBD | Pending |
| GRAPH-02 | TBD | Pending |
| GRAPH-03 | TBD | Pending |
| GRAPH-04 | TBD | Pending |
| EXT-01 | TBD | Pending |
| EXT-02 | TBD | Pending |
| EXT-03 | TBD | Pending |
| EXT-04 | TBD | Pending |
| LAND-01 | TBD | Pending |
| LAND-02 | TBD | Pending |
| LAND-03 | TBD | Pending |
| ONB-10 | TBD | Pending |
| ONB-11 | TBD | Pending |
| PRIV-01 | TBD | Pending |
| RAG-01 | TBD | Pending |

**Coverage:**
- v1.3 requirements: 19 total
- Mapped to phases: 0
- Unmapped: 19

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-03-15 after initial definition*
