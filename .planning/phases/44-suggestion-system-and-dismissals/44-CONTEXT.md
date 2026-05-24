# Phase 44: Suggestion System and Dismissals - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

ContextOS needs a durable, workspace-scoped suggestion foundation that can show bounded, source-backed recommendations on the dashboard and preserve dismiss, snooze, resolve, and reopen state across refreshes and syncs. This phase creates the generic suggestion contract and first dashboard surface for missing source-coverage guidance.

The phase must support later missed-decision detection and confirmed action-layer work, but it should not build missed-decision extraction, bot actions, task/doc/PR writes, autonomous actions, or a full inbox/work queue. Suggestions are review nudges around decision memory, not the primary product object.

</domain>

<decisions>
## Implementation Decisions

### Suggestion Contract
- **D-01:** Build one generic, reusable `suggestions` contract rather than separate per-family models. The same foundation should support missing source coverage now, missed-decision candidates in Phase 45, and future action prompts in Phase 47.
- **D-02:** A suggestion should preserve `entity_type` and `entity_id` when there is a source object or originating record, and should also carry a normalized evidence bundle with source refs, snippets, and provenance.
- **D-03:** Use a small typed suggestion enum with flexible type-specific JSON details. Initial types should cover `missing_source_coverage`, `missed_decision`, and `action_prompt` or close equivalents.
- **D-04:** Suggestion priority means user-facing urgency for ordering and copy. It is not detector confidence and not raw business impact. Confidence/impact can exist as separate metadata if needed.

### Lifecycle Semantics
- **D-05:** Dismiss hides the exact suggestion instance forever across refreshes and future syncs. A materially different suggestion may appear later only when the evidence or target changes.
- **D-06:** Snooze stores `snoozed_until`. A snoozed suggestion may reappear after that timestamp if it is still open and relevant.
- **D-07:** Resolve means the user says the recommendation is handled or no longer needs attention. It must preserve audit/provenance and should not require a downstream artifact to exist.
- **D-08:** Reopen supports manual user reopen and material-change reopen/new-instance behavior. Detectors should not freely reopen dismissed or resolved suggestions just because they still score as relevant.

### Dashboard Surface
- **D-09:** The dashboard section label should be `Needs review`, not `Suggestions`. The label should frame items as bounded review work, not AI ideas to browse.
- **D-10:** When open suggestions exist, `Needs review` appears at the top of the dashboard right rail. It should not appear above the headline, above the main Recent decisions column, or inside Recent decisions.
- **D-11:** Recent decisions remains the main left-column lead and stays reserved for confirmed decision memory. Suggestions are unconfirmed guidance and must not mix into that hierarchy.
- **D-12:** The right-rail `Needs review` surface should be capped at 2-3 visible rows with a `View all` route or equivalent for the full queue. Active context moves below `Needs review` when suggestions exist.
- **D-13:** The surface should stay visually quiet: compact rows, sentence-case labels, restrained metadata, no large lower-page panel, no loud priority colors, and no inbox-like takeover.
- **D-14:** Each visible row should explain one concrete reason and expose a quiet primary action plus secondary snooze/dismiss handling. Planners can decide exact controls, but the row should not require the user to open a full page just to understand why it exists.

### Missing Source Coverage
- **D-15:** Missing-source suggestions require a concrete decision evidence gap. Do not create generic prompts to connect more tools.
- **D-16:** A missing-source suggestion must be specific to a decision, workstream, or repeated pattern and name the missing evidence type.
- **D-17:** Approved copy patterns:
  - `Decision X has Slack and PR evidence, but no design review or Figma evidence.`
  - `We found 6 product/design decisions in onboarding, but none include Figma evidence.`
- **D-18:** Avoid generic source-level suggestions such as `Figma evidence is missing from this workspace` or broad recommendations such as `Connect Figma to improve decision coverage`.
- **D-19:** If there is no specific decision, workstream, or repeated pattern, do not show a missing-source suggestion.
- **D-20:** The primary action should first review/explain the gap, then route to the relevant setup or source-selection flow. Do not jump straight to an integration connect CTA without the decision-memory context.
- **D-21:** Repeated clear evidence-gap patterns should aggregate into one bounded suggestion rather than one row per decision.

### Agent Discretion
- Planners may choose exact table names, endpoint boundaries, enum names, and JSON field shapes as long as the generic reusable contract, entity pointer plus evidence bundle, and lifecycle semantics are preserved.
- Planners may choose the exact `View all` destination and row controls, but the home dashboard must stay bounded and quiet.
- Planners may define material-change detection heuristics, but dismissed/resolved suggestions must not be freely resurrected without a materially changed evidence or target fingerprint.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Scope and Requirements
- `.planning/ROADMAP.md` - Phase 44 goal, dependency on Phase 43, success criteria, and v1.4 phase ordering.
- `.planning/REQUIREMENTS.md` - SUG-01 through SUG-04 and the later GAP/ACTL boundaries that depend on suggestions.
- `.planning/PROJECT.md` - v1.4 product expansion goal, stack constraints, workspace-scope expectation, and action-layer boundaries.
- `.planning/STATE.md` - Current milestone state and accumulated decisions.

### Prior Decisions
- `.planning/phases/45-post-sync-missed-decision-detection/45-CONTEXT.md` - Phase 45 expects a generic Phase 44 suggestion surface and uses `Needs review` for unconfirmed missed-decision candidates.
- `.planning/phases/42-landing-positioning-and-seo-launch-rewrite/42-CONTEXT.md` - Source-backed decision memory and Decision Receipt remain the core product framing.
- `.planning/phases/41-dashboard-pulse-redesign/41-CONTEXT.md` - Dashboard hierarchy, quiet pulse-surface constraints, Recent decisions priority, and right-rail behavior.

### Codebase Maps
- `.planning/codebase/STACK.md` - FastAPI, Supabase/Postgres, Next.js, React, shadcn, Tailwind, and testing stack.
- `.planning/codebase/ARCHITECTURE.md` - Workspace-scoped multi-tenancy, frontend/backend data flow, sync scheduler, dashboard endpoints, and background-worker patterns.
- `.planning/codebase/CONVENTIONS.md` - Model, service, route, frontend component, and test naming/style conventions.

### Existing Implementation Surfaces
- `backend/src/models/base.py` - Base SQLModel fields and soft-delete conventions for new persisted models.
- `backend/src/models/sync.py` - Existing workspace/provider state model pattern.
- `backend/src/routers/dashboard.py` - Current dashboard endpoint pattern.
- `backend/src/services/dashboard_resurfaced.py` - Existing decision-like message heuristic; useful as a warning against noisy broad recommendations.
- `backend/src/services/audit.py` and `supabase/migrations/00034_audit_log.sql` - Existing audit logging pattern for user actions.
- `backend/src/models/graph_node.py`, `backend/src/services/graph_ops.py`, and `supabase/migrations/00027_graph_tables.sql` - Workspace-scoped graph and Decision node patterns that later suggestions may point at.
- `apps/web/src/app/dashboard/page.tsx` - Current dashboard home composition and right-rail layout.
- `apps/web/src/app/dashboard/pulse/use-dashboard-data.ts` - Current dashboard data loading aggregation.
- `apps/web/src/app/dashboard/pulse/recent-decisions.tsx` - Confirmed decision-memory lead section that suggestions must not pollute.
- `apps/web/src/app/dashboard/pulse/active-context.tsx` and `apps/web/src/app/dashboard/pulse/needs-you.tsx` - Right-rail/list-row patterns for bounded secondary sections.
- `apps/web/src/app/dashboard/pulse/types.ts` - Dashboard home type boundaries.
- `apps/web/src/app/globals.css` - `.pulse-surface` and dashboard panel styling constraints.
- `apps/web/src/lib/api.ts` - Frontend authenticated API client and dashboard fetch conventions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseModel` and `TimestampMixin` provide UUID and timestamp fields for a new suggestion SQLModel.
- `SyncCursor` shows the current workspace/provider state pattern; suggestion detectors may need similar source-scoped state later, but Phase 44 should focus on suggestion state.
- `log_audit_event` provides a non-blocking audit helper for dismiss, snooze, resolve, and reopen actions.
- `dashboard.py` already groups dashboard-specific endpoints and is a natural place for suggestion read endpoints if a broader router is not created.
- Dashboard pulse components provide row, section label, marker, and right-rail patterns that the `Needs review` surface should reuse.
- `apiFetch` is the existing authenticated frontend API path for write actions such as dismiss/snooze/resolve/reopen.

### Established Patterns
- Every persisted suggestion must be workspace-scoped and queried by `workspace_id`.
- Frontend direct Supabase reads exist for some dashboard data, but business actions should go through the Python API.
- The dashboard home is a quiet pulse surface: Recent decisions leads, secondary content sits in the right rail, and empty sections can disappear.
- Source-backed claims should preserve provenance and snippets so users can verify why the suggestion exists.
- Graph and ingestion-related features should remain additive and should not poison provider syncs or core dashboard loading.

### Integration Points
- New Supabase migration for `suggestions` and supporting indexes/RLS.
- New backend model/service/router for listing open suggestions and mutating lifecycle state.
- Dashboard home data loading and right-rail composition.
- Future Phase 45 missed-decision candidates should publish into this suggestion contract instead of creating a separate user-visible queue.
- Future Phase 47 action-layer prompts should reuse the same dismiss/snooze/resolve semantics.

</code_context>

<specifics>
## Specific Ideas

- Actual dashboard screenshot reviewed during discussion: the current layout has Recent decisions in the main left column and Active context in the right rail. The locked suggestion placement is top of that right rail when open suggestions exist.
- Use `Needs review` as the dashboard label.
- Cap dashboard home at 2-3 visible suggestion rows.
- Missing-source suggestions should sound like decision-memory gaps, not integration upsells.
- Accepted copy examples:
  - `Decision X has Slack and PR evidence, but no design review or Figma evidence.`
  - `We found 6 product/design decisions in onboarding, but none include Figma evidence.`

</specifics>

<deferred>
## Deferred Ideas

- Missed-decision extraction, candidate scoring, and confirmation flows belong to Phase 45.
- Slack/Telegram bot action prompts, task/doc/PR writes, owner pings, and confirmed external actions belong to Phase 47.
- Autonomous or policy-driven action execution remains outside v1.4 Phase 44.
- Full source-coverage analytics or broad integration health dashboards are not part of this phase.

</deferred>

---

*Phase: 44-suggestion-system-and-dismissals*
*Context gathered: 2026-05-25*
