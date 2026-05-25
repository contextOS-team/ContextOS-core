# Requirements: ContextOS v1.4 Product Expansion & Action Layer

**Defined:** 2026-05-24
**Core Value:** ContextOS turns scattered work conversations into source-backed decision memory, then helps teams act on those decisions without losing provenance or workspace boundaries.

## v1.4 Requirements

Requirements for the product expansion and action-layer milestone. Each maps to roadmap phases 43-49.

### Workspaces

- [ ] **WS-01**: User can create an additional workspace from the app without replacing or corrupting their existing workspace.
- [ ] **WS-02**: User can switch active workspaces and every dashboard, settings, sync, graph, and source view respects the selected workspace.
- [ ] **WS-03**: Workspace integrations, OAuth credentials, sync state, graph data, suggestions, and action audit records remain isolated per workspace.
- [ ] **WS-04**: User can rename, archive, and recover from an empty or misconfigured workspace without breaking other workspaces.
- [ ] **WS-05**: Existing single-workspace users keep their current workspace and source connections after the migration.

### Suggestions

- [x] **SUG-01**: System can persist workspace-scoped suggestions with type, source evidence, priority, status, and provenance.
- [x] **SUG-02**: User can dismiss, snooze, mark resolved, or reopen a suggestion, and that state survives refreshes and syncs.
- [x] **SUG-03**: Dashboard surfaces a bounded suggestion area after sync completion without taking over the primary decision-memory hierarchy.
- [x] **SUG-04**: System can recommend missing integrations or source coverage, such as meeting notes or Figma, when decision evidence is incomplete.

### Missed Decisions

- [ ] **GAP-01**: After a source sync completes, ContextOS can scan recent synced content for likely decisions that were discussed but not documented or planned.
- [ ] **GAP-02**: User can review a missed-decision candidate with linked source evidence, confidence, people involved, and affected workstreams.
- [ ] **GAP-03**: User can confirm, reject, or defer a missed-decision candidate.
- [ ] **GAP-04**: Confirmed missed decisions can become a source-backed Decision Receipt or a follow-up suggestion without losing the original evidence trail.

### Graph RAG

- [ ] **GRAG-01**: Retrieval can target decision receipts, source evidence, graph neighborhoods, and related work with explicit provenance.
- [ ] **GRAG-02**: Graph RAG quality has an evaluation set covering decision recall, source-link accuracy, stale-context avoidance, and action-suggestion grounding.
- [ ] **GRAG-03**: Retrieval ranking uses graph adjacency, source freshness, workspace scope, and decision verification state to improve relevance.
- [ ] **GRAG-04**: Context pages and suggestion/action generation can explain which graph/source signals produced each answer.

### Action Layer

- [ ] **ACTL-01**: Slack and Telegram bots can send workspace-scoped suggested actions based on detected decisions, missed decisions, stale docs, or conflicting implementation signals.
- [ ] **ACTL-02**: User must explicitly confirm any write action before ContextOS creates a Jira/Linear task, posts a PR comment, asks an owner, or drafts a doc update.
- [ ] **ACTL-03**: Confirmed actions carry a decision receipt or source trail so the target tool shows why the action exists.
- [ ] **ACTL-04**: Action suggestions and outcomes are recorded in an audit trail with actor, workspace, source decision, target tool, and status.
- [ ] **ACTL-05**: User can dismiss or snooze action suggestions from the bot or dashboard.

### Figma

- [ ] **FIG-01**: User can connect Figma to a workspace with OAuth or an approved token flow.
- [ ] **FIG-02**: User can select Figma files or projects to sync as source material.
- [ ] **FIG-03**: ContextOS can ingest Figma comments, file metadata, frame references, and design-review evidence relevant to product/design decisions.
- [ ] **FIG-04**: Figma evidence can appear in Decision Receipts, graph nodes, and source chips alongside Slack, docs, tickets, and PRs.

### Developer Surface

- [ ] **DEV-01**: Team has a written recommendation for MCP, CLI, or both, including user stories, authentication model, network boundary, and security risks.
- [ ] **DEV-02**: First developer surface contract is defined for read-only decision/context operations before any write-capable tooling is planned.
- [ ] **DEV-03**: MCP/CLI research identifies how workspace selection, local config, audit logging, and token handling should work.

## Future Requirements

Deferred to future milestones. Tracked but not in the v1.4 roadmap.

### Action Layer Autonomy

- **ACTL-06**: ContextOS can execute low-risk actions automatically under workspace policy.
- **ACTL-07**: ContextOS can batch multiple related actions into an approval queue.
- **ACTL-08**: ContextOS can enforce decision review gates before high-risk PRs merge.

### Advanced Workspace Administration

- **WS-06**: Workspace admins can invite and remove teammates with role-based access control.
- **WS-07**: Organization owners can view cross-workspace analytics and billing.

### Advanced Figma

- **FIG-05**: Figma webhooks keep design evidence fresh without manual sync.
- **FIG-06**: ContextOS can compare design changes against implementation decisions.

## Out of Scope

Explicitly excluded from v1.4 to keep the milestone executable.

| Feature | Reason |
|---------|--------|
| Autonomous writes without confirmation | Too risky until suggestion quality, auditability, and workspace boundaries are proven |
| Full RBAC and billing administration | Multi-workspace foundation comes first; advanced org administration is a later layer |
| Cross-workspace graph search | Workspace isolation is the v1.4 safety boundary |
| Mobile app for suggestions/actions | Dashboard and Slack/Telegram cover the first action surfaces |
| Production-grade Figma webhooks | Initial Figma phase should prove ingestion and evidence value first |
| Write-capable MCP/CLI tools | Start with read-only developer context to avoid unsafe local-agent writes |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WS-01 | Phase 43 | Pending |
| WS-02 | Phase 43 | Pending |
| WS-03 | Phase 43 | Pending |
| WS-04 | Phase 43 | Pending |
| WS-05 | Phase 43 | Pending |
| SUG-01 | Phase 44 | Complete |
| SUG-02 | Phase 44 | Complete |
| SUG-03 | Phase 44 | Complete |
| SUG-04 | Phase 44 | Complete |
| GAP-01 | Phase 45 | Pending |
| GAP-02 | Phase 45 | Pending |
| GAP-03 | Phase 45 | Pending |
| GAP-04 | Phase 45 | Pending |
| GRAG-01 | Phase 46 | Pending |
| GRAG-02 | Phase 46 | Pending |
| GRAG-03 | Phase 46 | Pending |
| GRAG-04 | Phase 46 | Pending |
| ACTL-01 | Phase 47 | Pending |
| ACTL-02 | Phase 47 | Pending |
| ACTL-03 | Phase 47 | Pending |
| ACTL-04 | Phase 47 | Pending |
| ACTL-05 | Phase 47 | Pending |
| FIG-01 | Phase 48 | Pending |
| FIG-02 | Phase 48 | Pending |
| FIG-03 | Phase 48 | Pending |
| FIG-04 | Phase 48 | Pending |
| DEV-01 | Phase 49 | Pending |
| DEV-02 | Phase 49 | Pending |
| DEV-03 | Phase 49 | Pending |

**Coverage:**
- v1.4 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-05-24*
*Last updated: 2026-05-24 after v1.4 Product Expansion & Action Layer milestone started*
