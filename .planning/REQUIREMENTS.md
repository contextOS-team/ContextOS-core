# Requirements: ContextOS

**Defined:** 2026-03-04
**Core Value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.

## v1.2 Requirements

Requirements for the GraphRAG knowledge graph layer. Each maps to roadmap phases.

### Graph Foundation

- [x] **GRAPH-01**: Database has graph_nodes and graph_edges tables with workspace-scoped RLS, fingerprint deduplication, and JSONB properties
- [x] **GRAPH-02**: traverse_graph() SECURITY DEFINER function performs recursive CTE traversal with depth limiting and workspace validation
- [x] **GRAPH-03**: Graph tables have composite indexes on (workspace_id, entity_type), (workspace_id, relationship_type), and fingerprint uniqueness

### Entity Extraction

- [x] **EXTR-01**: Rule-based extractors create graph nodes and edges for ticket references, PR numbers, @mentions, and file paths from ingested content
- [x] **EXTR-02**: Rule-based extraction runs inline during webhook/sync ingestion with zero LLM cost
- [x] **EXTR-03**: LLM extraction identifies decisions, rationale, blockers, and semantic entities from Slack messages and meeting transcripts
- [x] **EXTR-04**: LLM extraction runs as batch background task via Gemini Flash with content hash deduplication
- [x] **EXTR-05**: LLM extraction output is validated against source text to prevent hallucinated entities
- [x] **EXTR-06**: Content filtering skips bot messages, short messages, and emoji-only content before LLM extraction

### Identity Resolution

- [x] **IDENT-01**: Person identities are unified across Linear, Slack, GitHub, and Fathom via email-based deterministic matching
- [x] **IDENT-02**: Identity mapping table is seeded from team roster APIs during integration setup
- [x] **IDENT-03**: Fuzzy name matches create candidate same_as edges with confidence scores without auto-merging

### Graph Retrieval

- [x] **RETR-01**: find_related_content() includes graph traversal as a third retrieval signal alongside explicit refs and hybrid search
- [x] **RETR-02**: Graph results are scored with depth-decay (1-hop highest, decaying per hop) and blended with existing signals
- [x] **RETR-03**: Graph context in synthesis prompts is capped at a fixed token budget to prevent context overflow

### Synthesis

- [ ] **SYNTH-01**: Context pages include decision trails showing what was decided, by whom, where discussed, and which tickets affected
- [ ] **SYNTH-02**: Context pages include relationship paths explaining why things are connected
- [ ] **SYNTH-03**: Context pages include cross-referenced people showing involvement across sources
- [x] **SYNTH-04**: Synthesis gracefully degrades when no graph data exists for a ticket

### Decision Extraction

- [x] **DECIDE-01**: LLM extraction targets decision language in Slack messages and meeting transcripts
- [x] **DECIDE-02**: Decision nodes store description, rationale, source reference, date, confidence score, and status
- [x] **DECIDE-03**: Decisions link bidirectionally to Person, SlackThread/Meeting, and Ticket nodes

### Code-to-Discussion Linking

- [ ] **CODE-01**: Slack messages mentioning file paths or function names create edges to matching code_chunks
- [ ] **CODE-02**: PRs implementing tickets create transitive links between changed code and related discussions
- [ ] **CODE-03**: Context pages show code-to-discussion provenance in the relevant code section

### Graph Explorer API

- [ ] **GAPI-01**: GET endpoint returns subgraph JSON (nodes + edges) for a ticket's graph neighborhood

## v1.1 Requirements (Complete)

<details>
<summary>36 requirements -- all complete</summary>

### Design System

- [x] **DS-01**: Dashboard renders in dark mode by default with brand-tinted OKLCH tokens
- [x] **DS-02**: Teal used only on actionable/status elements
- [x] **DS-03**: JetBrains Mono applied to all data identifiers
- [x] **DS-04**: 4-level surface hierarchy with consistent token usage
- [x] **DS-05**: Radix UI portals render correctly in dark mode
- [x] **DS-06**: Spring-curve microinteractions on list items and status changes
- [x] **DS-07**: Subtle grain texture on dashboard surfaces
- [x] **DS-08**: Section labels use monospace uppercase tracking
- [x] **DS-09**: All dashboard pages render structured skeleton loading states

### Navigation

- [x] **NAV-01**: Dashboard navigation holds all sections with clear active state indicators

### Onboarding

- [x] **ONB-01**: 4-step onboarding wizard after first signup
- [x] **ONB-02**: Step 1: workspace naming
- [x] **ONB-03**: Step 2: connect Linear (required)
- [x] **ONB-04**: Step 3: optional additional sources
- [x] **ONB-05**: Step 4: first context page with mock fallback
- [x] **ONB-06**: OAuth redirect preserves wizard state
- [x] **ONB-07**: Onboarding progress persists across refreshes
- [x] **ONB-08**: Animated checkmark on integration connect
- [x] **ONB-09**: Server-side onboarding gate

### Dashboard Home

- [x] **HOME-01**: Summary view with recent pages, integration health, activity preview

### Context Feed

- [x] **FEED-01**: Browsable context page list
- [x] **FEED-02**: Status filtering
- [x] **FEED-03**: Free text search
- [x] **FEED-04**: Real-time status updates
- [x] **FEED-05**: Route-based detail view with copy-prompt and regenerate
- [x] **FEED-06**: Empty states with CTA

### Activity Timeline

- [x] **ACT-01**: Chronological workspace event feed
- [x] **ACT-02**: Type-specific icons, relative timestamps, day-group dividers
- [x] **ACT-03**: Real-time updates via Supabase Realtime
- [x] **ACT-04**: Activity events table with 30-day retention

### Settings & Team

- [x] **SET-01**: API key create/revoke with one-time full key display
- [x] **SET-02**: Edit workspace name
- [x] **SET-03**: View connected team members
- [x] **SET-04**: Settings accessible from navigation

### Auth Redesign

- [x] **AUTH-01**: Dark theme login/signup pages
- [x] **AUTH-02**: Same teal accent and tokens as dashboard

</details>

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Graph Explorer Frontend

- **GAPI-02**: react-force-graph-2d visualization component for graph neighborhood exploration

### Theme & Customization

- **THEME-01**: Light/dark mode toggle for user preference
- **THEME-02**: Custom brand color configuration per workspace

### Advanced Feed

- **FEED-07**: Right-panel split view for inline detail
- **FEED-08**: Keyboard navigation (j/k/Enter/Esc/r/c)
- **FEED-09**: Stale reason indicator

### Team Management

- **TEAM-01**: Team member invites via email
- **TEAM-02**: Role-based access control
- **TEAM-03**: API key usage metrics

### Auth

- **AUTH-03**: Social OAuth login (Google, GitHub)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Apache AGE extension | Not available on Supabase Cloud (C extension, not TLE). Core team dismissed Oct 2024. Use plain PG tables instead. |
| Neo4j or separate graph DB | Doubles operational complexity, requires bidirectional sync. Graph stays in Supabase Postgres. |
| Microsoft GraphRAG Leiden clustering | Corpus-scale summarization overkill. ContextOS has structured data from known sources. |
| Real-time LLM extraction on every webhook | Burns API budget, adds latency. Use two-tier: regex inline, LLM batch. |
| SpaCy / full NLP pipeline | Heavy dependency (300MB+) for generic NER when domain entities are regex-extractable or need full LLM reasoning. |
| Graph versioning / temporal graph | Timestamp edges with created_at is sufficient. Full bitemporal queries are a research project. |
| Person-centric aggregation UI | Emerges from graph data in context pages. Dedicated UI deferred. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GRAPH-01 | Phase 22 | Complete |
| GRAPH-02 | Phase 22 | Complete |
| GRAPH-03 | Phase 22 | Complete |
| EXTR-01 | Phase 22 | Complete |
| EXTR-02 | Phase 22 | Complete |
| EXTR-03 | Phase 24 | Complete |
| EXTR-04 | Phase 24 | Complete |
| EXTR-05 | Phase 24 | Complete |
| EXTR-06 | Phase 24 | Complete |
| IDENT-01 | Phase 23 | Complete |
| IDENT-02 | Phase 23 | Complete |
| IDENT-03 | Phase 23 | Complete |
| RETR-01 | Phase 25 | Complete |
| RETR-02 | Phase 25 | Complete |
| RETR-03 | Phase 25 | Complete |
| SYNTH-01 | Phase 26 | Pending |
| SYNTH-02 | Phase 26 | Pending |
| SYNTH-03 | Phase 26 | Pending |
| SYNTH-04 | Phase 26 | Complete |
| DECIDE-01 | Phase 24 | Complete |
| DECIDE-02 | Phase 24 | Complete |
| DECIDE-03 | Phase 24 | Complete |
| CODE-01 | Phase 26 | Pending |
| CODE-02 | Phase 26 | Pending |
| CODE-03 | Phase 26 | Pending |
| GAPI-01 | Phase 27 | Pending |

**Coverage:**
- v1.2 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-03-07*
*Last updated: 2026-03-07 -- All 26 requirements mapped to phases 22-27*
