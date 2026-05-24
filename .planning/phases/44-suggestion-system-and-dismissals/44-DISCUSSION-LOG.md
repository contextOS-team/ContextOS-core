# Phase 44: Suggestion System and Dismissals - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 44-suggestion-system-and-dismissals
**Areas discussed:** Suggestion contract, Lifecycle semantics, Dashboard surface, Missing source coverage

---

## Suggestion Contract

### Model Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Generic reusable contract | One suggestions model supports missed decisions, missing source coverage, and future action prompts via type, entity_type/entity_id, evidence, priority, status, and provenance. | yes |
| Narrow dashboard recommendations | Keep it focused on source-coverage suggestions now, then let Phase 45/47 extend it later. | |
| Separate models per suggestion family | Different tables/contracts for coverage gaps, missed decisions, and action prompts. | |

**User's choice:** Generic reusable contract.
**Notes:** This makes Phase 44 the shared foundation for Phase 45 and Phase 47.

### Source Linkage

| Option | Description | Selected |
|--------|-------------|----------|
| Entity pointer plus evidence bundle | Store entity_type/entity_id for the originating object when one exists, plus normalized evidence refs/snippets/provenance on the suggestion. | yes |
| Evidence-only | Store source links/snippets and metadata directly on the suggestion, without requiring an entity pointer. | |
| Entity-only | Suggestion points to a source object, and planners fetch evidence from that object when needed. | |

**User's choice:** Entity pointer plus evidence bundle.
**Notes:** The suggestion should remain explainable without reverse-engineering the originating object.

### Type Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Small typed enum plus flexible payload | Start with a few known types like missing_source_coverage, missed_decision, and action_prompt, with type-specific JSON details. | yes |
| Freeform string types | Faster to extend, but easier for future phases to drift. | |
| Fully normalized per-type fields | Stronger schema guarantees, but more migration churn before the suggestion families are proven. | |

**User's choice:** Small typed enum plus flexible payload.
**Notes:** The stable contract is the type boundary and lifecycle, not every type-specific field.

### Priority Meaning

| Option | Description | Selected |
|--------|-------------|----------|
| User-facing urgency | Priority controls ordering and copy: high means review soon, medium means useful, low means background hygiene. | yes |
| Detector confidence | Priority mostly reflects how certain ContextOS is that the suggestion is correct. | |
| Action impact | Priority reflects the likely business/engineering impact if ignored. | |

**User's choice:** User-facing urgency.
**Notes:** Confidence and impact can exist separately, but should not define priority.

---

## Lifecycle Semantics

### Dismiss

| Option | Description | Selected |
|--------|-------------|----------|
| Hide this suggestion instance forever | The exact suggestion stays dismissed across refreshes and syncs. A materially new suggestion may appear if the evidence or target changes. | yes |
| Hide this topic forever | Future syncs should suppress similar suggestions in the same workspace/topic. | |
| Temporary hide | Dismiss behaves more like not now, and the system may bring it back after enough time or evidence. | |

**User's choice:** Hide this suggestion instance forever.
**Notes:** Dismiss is not a temporary hide.

### Snooze

| Option | Description | Selected |
|--------|-------------|----------|
| Hide until a timestamp | Store snoozed_until; suggestion reappears after that time if still open and relevant. | yes |
| Hide until new evidence | Reappear only when the same suggestion gets materially new evidence. | |
| Hide until next sync | Reappear after the next source sync completes, even if nothing changed. | |

**User's choice:** Hide until a timestamp.
**Notes:** Reappearance still requires the suggestion to remain open and relevant.

### Resolve

| Option | Description | Selected |
|--------|-------------|----------|
| User says the recommendation is handled | Mark resolved when the user took the suggested follow-up or confirmed no more attention is needed. Keep audit/provenance. | yes |
| System says underlying issue disappeared | Resolve automatically when the detector no longer finds the gap. | |
| Resolved only by downstream artifact | Resolve only when a linked decision receipt, task, doc, or action record exists. | |

**User's choice:** User says the recommendation is handled.
**Notes:** Resolution should not require a downstream artifact.

### Reopen

| Option | Description | Selected |
|--------|-------------|----------|
| Manual reopen plus material-change reopen | User can reopen dismissed/resolved suggestions, and the system may create/reopen a new instance only when evidence or target materially changes. | yes |
| Manual only | Once dismissed/resolved, only the user can bring it back. | |
| System can freely reopen | Future detectors can reopen dismissed/resolved suggestions when they still score as relevant. | |

**User's choice:** Manual reopen plus material-change reopen.
**Notes:** Detectors should not freely resurrect dismissed/resolved items.

---

## Dashboard Surface

### Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Below Recent decisions, above/right of Active context | Keeps confirmed decisions as the lead hierarchy, while suggestions are visible after sync. | |
| Below Active context | Quieter, but useful suggestions may be missed. | |
| Inside Recent decisions | Maximum visibility, but mixes unconfirmed recommendations with confirmed decision memory. | |
| Top of right rail | Needs review appears at the top of the right rail when open suggestions exist. Recent decisions remains the main left-column lead. | yes |

**User's choice:** Top of right rail.
**Notes:** After an interface-craft critique and review of the actual dashboard screenshot, the locked placement is top of the right rail, capped at 2-3 rows. Active context moves below Needs review. The section label should be `Needs review`, not `Suggestions`.

---

## Missing Source Coverage

### Qualification

| Option | Description | Selected |
|--------|-------------|----------|
| Decision evidence gap | Suggest a missing source only when ContextOS sees a decision/workstream with weak or absent evidence from an expected source. | yes |
| Disconnected integration | Suggest any valuable disconnected source whenever the workspace lacks it. | |
| General hygiene | Suggest broad improvements such as connect more sources or sync more often. | |

**User's choice:** Decision evidence gap.
**Notes:** Missing-source suggestions should not be generic integration prompts.

### Specificity

| Option | Description | Selected |
|--------|-------------|----------|
| Specific decision/workstream plus missing evidence type | Name the specific decision, workstream, or repeated pattern and the missing evidence type. | yes |
| Source-level summary | Say a source is missing from the workspace. | |
| General recommendation | Recommend connecting a source to improve coverage. | |

**User's choice:** Specific decision/workstream/pattern plus named missing evidence type.
**Notes:** User provided accepted copy examples: `Decision X has Slack and PR evidence, but no design review or Figma evidence.` and `We found 6 product/design decisions in onboarding, but none include Figma evidence.` Avoid generic `Figma evidence is missing from this workspace` or `Connect Figma to improve decision coverage`.

### Action

| Option | Description | Selected |
|--------|-------------|----------|
| Review gap plus connect/select source | Primary action opens the relevant setup/selection flow only after showing the decision-memory gap. | yes |
| Dismiss/snooze only | The suggestion explains the gap but does not route to setup in Phase 44. | |
| Immediate connect CTA | Primary action goes straight to Figma/meeting-source connection. | |

**User's choice:** Review gap plus connect/select source.
**Notes:** The suggestion should explain the gap before routing to setup/selection.

### Repeated Patterns

| Option | Description | Selected |
|--------|-------------|----------|
| Aggregate when the pattern is clear | Show one bounded suggestion for repeated evidence gaps, like `6 onboarding decisions lack Figma evidence`, rather than six separate rows. | yes |
| One suggestion per decision | More precise, but risks noise. | |
| Hide repeated patterns for now | Only show single-decision evidence gaps in Phase 44. | |

**User's choice:** Aggregate when the pattern is clear.
**Notes:** Aggregation preserves quietness while still surfacing meaningful repeated gaps.

---

## Agent Discretion

- Exact table names, endpoint paths, enum literal names, and JSON payload field shapes.
- Exact right-rail row controls and full-queue route.
- Exact material-change fingerprinting and detector thresholds.

## Deferred Ideas

- Missed-decision extraction and confirmation flows are Phase 45.
- Bot actions, task/doc/PR writes, and confirmed external actions are Phase 47.
- Broad integration-health dashboards and autonomous action execution are outside this phase.
