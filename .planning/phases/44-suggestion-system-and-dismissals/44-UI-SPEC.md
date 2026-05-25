---
phase: 44
slug: suggestion-system-and-dismissals
status: approved
shadcn_initialized: true
preset: new-york
created: 2026-05-25
reviewed_at: 2026-05-25
---

# Phase 44 - UI Design Contract

> Visual and interaction contract for the generic suggestion surface and dashboard `Needs review` section.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn |
| Preset | new-york, neutral base, Tailwind v4 CSS variables |
| Component library | Existing dashboard pulse components plus Radix/shadcn primitives only where already present |
| Icon library | lucide only for secondary utility affordances; no icon-only lifecycle actions |
| Font | Geist Sans for dashboard copy, Geist Mono for source IDs, providers, and timestamps |

Source of truth: `apps/web/components.json`, `apps/web/src/app/globals.css`, `apps/web/src/app/dashboard/pulse/*`, Phase 41 dashboard pulse context, and Phase 44 CONTEXT decisions.

---

## Phase Screen Contract

| Surface | Contract |
|---------|----------|
| Dashboard home | Existing headline and `Recent decisions` remain primary. `Needs review` appears at the top of the right rail only when visible suggestions exist. |
| Mobile order | `Needs review` appears after `Recent decisions` and before `Active context`. |
| Section visibility | Hide the section entirely when no open or expired-snooze suggestions are visible. No empty-state card on dashboard home. |
| Section label | `Needs review` |
| Section support copy | None on the dashboard surface; row copy must carry the concrete reason. |
| Visible rows | Cap at 3 rows on the dashboard. Full list lives behind `View all`. |
| Relationship to Recent decisions | Suggestions never render inside `Recent decisions`; unconfirmed guidance must not pollute confirmed decision memory. |
| Full queue route | A simple `View all` route may list open, snoozed, dismissed, and resolved suggestions for lifecycle recovery. It must stay operational, not marketing-like. |
| Out-of-scope UI | No full inbox takeover, no chat prompt, no autonomous action controls, no external write controls, no broad integration-health dashboard. |

---

## Spacing Scale

Declared values are multiples of 4:

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Inline metadata gaps, marker offsets |
| sm | 8px | Chip gaps, title-to-reason spacing |
| md | 16px | Compact row padding and action gaps |
| lg | 24px | Section rhythm and right-rail spacing |
| xl | 32px | Dashboard grid gutters only |
| 2xl | 48px | Major dashboard breaks outside the suggestion section |
| 3xl | 64px | Page-level spacing outside this surface |

Exceptions: action targets may use 40px desktop and 44px touch minimum heights for accessibility.

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Metadata | 12px | 400 | 1.35 |
| Body | 14px | 400 | 1.5 |
| Row title | 15px | 600 | 1.35 |
| Section label | 12px | 600 | 1.35 |

Rules:
- Keep `letter-spacing: 0`.
- Use sentence case: `Needs review`, `Missing design evidence`, `Review gap`.
- Use Geist Mono only for identifiers, provider labels, and timestamps.
- Do not introduce hero-scale text inside dashboard panels or rows.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `var(--background)` | Dashboard background and negative space |
| Secondary (30%) | `var(--pulse-panel)` / `rgba(255,255,255,0.035)` | Suggestion rows and list panel |
| Accent (10%) | `var(--primary)` | Focus ring, 1px new marker, and primary `Review gap` emphasis only |
| Destructive | `var(--destructive)` | Dismiss confirmation copy and destructive button state only |

Accent reserved for: focus-visible ring, new marker, active dashboard navigation inherited from Phase 41, and the quiet primary action.

Accent must not be used for priority badges, confidence scales, card borders, decorative glows, or all links. Priority is conveyed through ordering and text.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Dashboard section | Needs review |
| Primary CTA | Review gap |
| Secondary CTA | Snooze |
| Dismiss CTA | Dismiss |
| Resolve CTA | Mark resolved |
| Reopen CTA | Reopen |
| Empty state heading | No suggestions need review |
| Empty state body | Source-backed suggestions will appear here when ContextOS finds a specific decision evidence gap. |
| Error state | Could not update this suggestion. Try again. |
| Destructive confirmation | Dismiss suggestion: Hide this exact suggestion unless the evidence or target changes. |

Approved missing-source copy patterns:
- `Decision X has Slack and PR evidence, but no design review or Figma evidence.`
- `We found 6 product/design decisions in onboarding, but none include Figma evidence.`

Avoid:
- `Figma evidence is missing from this workspace`
- `Connect Figma to improve decision coverage`
- `AI found this`
- Broad, source-level upsell copy.

---

## Component Contracts

| Component | Contract |
|-----------|----------|
| `NeedsReview` | Right-rail section hidden when empty, label plus optional `View all`, existing pulse rhythm, top of right rail above `Active context`. |
| `SuggestionRow` | Dense row in a `pulse-list-panel`; title first, reason second, neutral evidence chips third, actions last. Radius 8px max. |
| Evidence chips | Neutral chips with source/evidence labels such as `Slack`, `PR evidence`, `missing Figma`, `Decision`. |
| Lifecycle controls | Text buttons. `Review gap` is primary, `Snooze` and `Dismiss` are quiet secondary actions. |
| Full queue rows | Same visual language as dashboard rows, plus status and reopen controls for dismissed/resolved rows. |
| Loading state | Skeleton rows under the label only while suggestion data loads. |
| Inline error | One short row-level error, then keep all controls available. |

---

## State And Data Contract

| State | UI Contract |
|-------|-------------|
| No visible suggestions | Dashboard section absent. Full queue may show the empty copy above. |
| Open suggestion | Visible if not soft-deleted and workspace matches the active user context. |
| Snoozed suggestion | Hidden until `snoozed_until`; reappears after the timestamp if still relevant. |
| Dismissed suggestion | Hidden on dashboard. Exact instance does not reappear across refreshes or syncs. |
| Resolved suggestion | Hidden on dashboard. Preserved in full queue for audit and optional reopen. |
| Reopened suggestion | Returns to open state and can appear on dashboard. |
| Action failure | Keep row visible and show `Could not update this suggestion. Try again.` |

---

## Motion And Interaction Contract

| Interaction | Contract |
|-------------|----------|
| Page load | No entrance animation or stagger. |
| Row hover | Background-color transition only, 160ms, hover-capable devices only. |
| Button press | Scale button to 0.96 for 100-120ms; do not scale the row. |
| Row action pending | Disable only the clicked action, keep row stable. |
| Row removal | Remove after API success; no height animation. |
| Reduced motion | Disable transform movement and keep color transitions only. |

No `transition: all`. Do not add Motion/Framer Motion for this section.

---

## Accessibility Contract

| Area | Contract |
|------|----------|
| Hit area | Actions are at least 40px desktop and 44px touch. |
| Labels | No icon-only primary actions. |
| Focus | Use global tokenized focus ring. |
| Status | Priority and lifecycle state must be readable from text, not color alone. |
| Source reason | Reason text stays real text and is not rendered as an image/canvas. |
| Destructive action | Dismiss copy must explain that only the exact suggestion instance is hidden. |

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | Skeleton/button primitives already in repo if needed | No new registry install required |
| third-party registry | none | Do not use |

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-05-25
