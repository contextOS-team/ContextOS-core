# Dashboard pulse redesign — direction

**Status:** locked after four-pass critique. This document is the single source of truth for the redesign. Plans and mockups derive from it.

**Date locked:** 2026-05-20

**Critique passes that produced this direction:**
1. `redesign-existing-projects` — generic-AI pattern audit against current dashboard
2. `interface-craft` Design Critique (Josh Puckett methodology) — hierarchy, scanability, information architecture
3. `minimalist-ui` — editorial-aesthetic pressure-test (light vs dark, typography, palette)
4. `emil-design-eng` (Emil Kowalski) — polish spec, micro-states, uncommon care

---

## 1. Product role of the dashboard

ContextOS is a "company brain" that ingests Slack, Linear/Jira, GitHub, docs and synthesizes them. Positioning: "stay invisible — not yet another tool to manage."

The dashboard is a **pulse surface**, not a workstation, not a search bar, not a chat.

The user opens it for ~4 seconds at a time, expecting an answer to: *did anything I care about happen since I last looked, and is there anything blocking on me right now?* They leave with that answer or they don't.

This framing comes from the Puckett pass and is the constraint every design decision flows from. The current dashboard fails this test by giving six sections equal weight and forcing the user to assemble the answer. The redesign passes it by giving the answer in the headline.

## 2. Page structure (in order, top to bottom)

1. **Chrome (top nav strip)** — left: wordmark + section nav (Home / Context / Graph / Activity). Right: sync indicator + last-updated + integration health + avatar, as one visual cluster.
2. **Headline** — computed sentence based on "since last visit" delta. Serif, large, the focal point of the page.
3. **Recent decisions** — lead section, 2–3× visual weight of supporting sections. **Two visible** above the fold, "view all →" for the rest. Each decision shows a provenance quote (see §17).
4. **Active context** — what the team is currently working on. **Top 3 items**, tighter rows, smaller titles, "view all →" for the rest.
5. **Needs you** — items specifically blocking on the current user. Compact. Hidden entirely when empty.
6. *(future)* **Direction summary** — a weekly generated paragraph slot. Designed now; generation in a follow-up phase.

**Removed from home:**
- Recent Activity → moves to `/activity` (already in top nav).
- "My Work" graph thumbnail → exists in `/graph`.
- "This Week" sparkline → deleted entirely.
- "Good evening, Daulet · 1 item · 7 days" greeting line → replaced by the computed headline.

## 3. The "since last visit" concept

A first-class persistent concept. Without it, the headline can't be computed and the page has no focal point.

- Persist a per-user `lastVisitedAt` timestamp.
- The headline computes from delta since `lastVisitedAt`.
- New items get a subtle marker (see §6).
- Hysteresis: `lastVisitedAt` updates only after **5 minutes of inactivity** *or* on explicit dismissal. Tab-flips are not visits. This is uncommon care that matches how humans think about "since I last looked."

## 4. The headline

The single most-crafted element on the page. Always present. Falls back to acknowledging silence when nothing new.

**Type:**
- Family: **Instrument Serif** (preferred) or Newsreader. Italic optional, regular weight (400).
- Size: 36–48px (`text-4xl` to `text-5xl`).
- Tracking: tight, `letter-spacing: -0.02em` to `-0.03em`.
- Line-height: 1.1.
- Measure: `max-w-3xl` (~672px). Constrained narrow column, even on wide viewports.
- Alignment: left, never centered.
- Color: warm off-white `#ece9e3`. Never pure white.
- `font-feature-settings: "kern" 1, "liga" 1;`
- `font-variation-settings: "opsz" 32;` (Instrument Serif is optical-sizing-aware).

**Punctuation:**
- Full color, full weight. No "soft opacity" period — that was an AI-design-cliché caught in pass 4.
- `hanging-punctuation: last;` — period sits in the optical gutter. The right edge of the headline looks rectangular. Webkit-only as of writing; degrades silently.

**Content patterns:**

Headline (serif, large) names the single most important new thing since `lastVisitedAt`:
- *"Vasiliy is waiting on RD-786 since Tuesday."*
- *"3 decisions and 30 sources of new context since you last looked."* (when no single thing dominates)
- *"Quiet day."* (when nothing new — see fallback below)

Subtext line beneath (sans, secondary, smaller): summarizes the *remainder* using the template:

> **`(N) more decision(s) and (M) new source(s) since you last looked, (T) ago.`**

When zero new: subtext becomes *"nothing new since you last looked, (T) ago."*

The subtext always names the user's last visit (`(T) ago`). This is the "we know you" touch.

## 5. Typography system

- **Body / UI:** Geist Sans, with `font-feature-settings: "ss01" 1, "cv11" 1` for Geist's stylistic alternates.
- **Numbers and counts inline:** Geist Sans with `font-feature-settings: "tnum" 1` (tabular figures). Never mono — mono numbers inline with sans words look like two fonts had a child.
- **Identifiers (RD-973, ##channel):** Geist Mono at 0.92em with `letter-spacing: -0.01em`, `font-feature-settings: "tnum" 1, "zero" 1` (slashed zero disambiguates RD-073 vs RD-O73).
- **Keyboard hints:** `<kbd>` in Geist Mono with `border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04);`.
- **Section labels:** sentence case ("Recent decisions"), NOT all-caps. Geist Sans, smaller than body, slightly muted color.
- **Tags / chips:** lowercase. Never uppercase-with-tracking. That would re-introduce SaaS-template register.

**Cyrillic-Latin mixed strings** (real case: `[ClientApp][iOS][CF] Настроить client-web-app`):
- Geist's Cyrillic is acceptable. If shipping a Cyrillic subset, use `@font-face` with `size-adjust: 98%` to align cap-heights with Latin.
- Bracketed prefixes in tertiary color (`#a8a59f`); title after at body color. Visually separates metadata from title without splitting the string.

## 6. Color and palette (warm dark)

**Background:**
- Page: `#0f0e0d` (warm dark, slight brown undertone). Replaces the current slightly-cool `#0a0d0c`.
- Card surface: `#13110f` (one step warmer-brighter than page). Depth via background-tint differential, not borders.

**Foreground:**
- Primary text: `#ece9e3` (warm off-white).
- Secondary text: `#a8a59f` (warm gray).
- Tertiary text: `#6e6b66` (dimmer warm gray).

**Accent discipline:**
- **Mint** (current brand color): reserved for **brand only** — wordmark + active nav state. Nothing else. No status dots, no chart fills, no card edges, no link underlines.
- **Dim amber** `#c4a050`: "needs your attention" semantics. The new-item marker. The sync error state. Low saturation, warm.
- **Dim red** `#b06863`: stale/blocked items (rare). Low saturation.
- **Dim green** `#6d8c6d`: fresh/synced confirmations (rare). Low saturation.

Each non-brand color does **exactly one job**. If you can't name its single semantic role, don't use it.

**No shadows. Anywhere.** Depth in dark UI comes from background-tint differentials. Shadows on dark are nearly invisible and adding them is templating, not design.

**No gradients, no ambient blobs, no background imagery.** The page is defensibly flat dark. This is one place where the `minimalist-ui` skill's default (add ambient depth) was rejected — a pulse dashboard's job is to be calm and trustworthy, not visually rich.

## 7. Cards and section structure

**Cards exist only for individual items** (a single decision, a single context row). Section *groupings* (Recent decisions, Active context) are defined by typography and spacing, not by wrapper rectangles. This kills the "everything is a card" pattern that flattens hierarchy.

**Card chrome:**
- No border by default. Card defined by `background: rgba(255,255,255,0.025)` on top of page `#0f0e0d`.
- Border-radius: 8–12px.
- Internal padding: 24px (`p-6`).
- Hover: `background: rgba(255,255,255,0.04)`, transition `background-color 160ms ease`. No translateY, no shadow.
- Active: `transform: scale(0.997)` over 100ms ease-out. Tiny scale — these are large surfaces, not buttons.
- Title underlines on hover: `text-decoration: 1px solid rgba(232,230,225,0.5); text-underline-offset: 0.2em;`.

**Spacing:**
- Doubled space between sections (~96px, `py-24`).
- Single space between rows within a section (~24px).
- The current dashboard's uniform spacing is wrong; this hierarchy of gap is what creates section identity without borders.

## 8. Chrome cluster (top-right)

Sync indicator + last-updated + integration health + avatar live as **one unit**, not four floating elements.

**Sync indicator — three states:**

| State | Treatment |
|-------|-----------|
| **Idle (99% of the time)** | `last synced 4m ago` in Geist Sans 12px, weight 450, `#6e6b66`, tnum. No icon. No dot. The number ticks once per minute with a 240ms opacity dip (1.0 → 0.6 → 1.0) — invisible by design, makes the surface feel alive. Respects `prefers-reduced-motion`. |
| **Syncing** | `syncing slack · 35%` — text crossfades from idle state. Color shifts to `#a8a59f` (one step brighter). 1px-tall progress bar appears directly beneath the text, full width of the chrome cluster (~240px). Bar: background `rgba(255,255,255,0.04)`, fill `rgba(255,255,255,0.18)`. Fill width updates in real ticks from the data stream — no smooth CSS interpolation (smooth interpolation lies about real progress). When source changes mid-sync, text crossfades with `filter: blur(2px)` 180ms. |
| **Error** | `slack sync paused · reconnect` in dim amber `#c4a050`. "reconnect" inline, underlines on hover. Click → slide-over from right with integration state. |

**Manual "Sync now"** is tucked inside the cluster (click chrome → drawer opens with per-source state and a sync-all action). Not a hero button. If users reach for it often, the cause is a stale-sync bug to fix at the source, not a workaround to surface.

**Avatar:** small puck with initials. Hover `transform: scale(1.04)` 120ms. Active `scale(0.96)` 100ms. Tooltip after 600ms delay.

## 9. The "new since last visit" marker

- **Visual:** 1px × 14px vertical bar in dim amber `#c4a050`, in the left gutter outside the card's border-radius. 2px gap between bar and card edge. Vertically centered to the card's first line of text.
- **No glow, no card fill, no bold text.** Single column of pixels.
- **Persistence:** marker stays for the entire session it was seen in. Doesn't decay mid-visit (would feel deceptive).
- **Decay:** between sessions, when `lastVisitedAt` updates (per §3 hysteresis rules).
- **No entrance animation.** Marker is just *there* on load. Animating it would be theater.

## 10. Interaction states (full spec)

| Surface | Hover | Active | Focus |
|---------|-------|--------|-------|
| Decision card | `background: rgba(255,255,255,0.04)`, title underlines | `transform: scale(0.997)` 100ms | `outline: 1px solid rgba(232,230,225,0.4); offset 2px` (keyboard only) |
| Context row | `background: rgba(255,255,255,0.02)`, title underlines | none | same focus ring |
| Chrome avatar | `transform: scale(1.04)` 120ms | `scale(0.96)` 100ms | same focus ring |
| Sync indicator cluster | `background: rgba(255,255,255,0.025)`, 8px padding bleed, 6px radius | none (it opens a drawer) | same focus ring |
| Nav links | underline reveal | none | same focus ring |
| Buttons (primary) | color shift | `scale(0.97)` 100ms | same focus ring |

**Universal focus ring:**
```css
:focus-visible {
  outline: 1px solid rgba(232, 230, 225, 0.4);
  outline-offset: 2px;
  border-radius: 4px;
  transition: outline-offset 100ms ease-out;
}
```

**Transitions:** never `all`. Specify exactly which properties animate.

**Touch devices:** all hover styles gated behind `@media (hover: hover) and (pointer: fine)`.

## 11. Animation discipline

A pulse dashboard is opened tens of times per day. **Frequency × animation = annoyance.**

**Allowed animation:**
- The 240ms opacity dip on the sync timestamp tick (once per minute).
- Blur-during-crossfade on the sync source name change (180ms).
- Hover background transitions (160ms).
- Active scale transforms (100ms).
- Focus ring offset transition (100ms).

**Not allowed:**
- Scroll-entry fade-ins (rejected from `minimalist-ui` defaults).
- Staggered list reveals.
- Spring physics anywhere.
- Spinners.
- Anything that runs on every page load.

`prefers-reduced-motion` removes all motion; color and opacity transitions remain.

## 12. Empty states

- **Needs you with zero items:** section structurally absent. If layout demands a placeholder, single line *"nothing needs you"* in tertiary color, lowercase, no period.
- **Headline with nothing new:** `"Quiet day."` — see §4 fallback.
- **Recent decisions with nothing in date range:** show the oldest available decision with a subtle "from <date>" timestamp. Never show "All caught up!" or a checkmark.

## 13. What we explicitly rejected (and why)

- **Search bar / chat as page hero.** Hyper does this because their dashboard has no content. ContextOS has content. The dashboard surfaces it. (Pass 2.)
- **All-caps tracked section labels** (`RECENT CONTEXT`). Most generic-feeling element on the current page. Sentence case is more journal, less template. (Pass 1.)
- **Mint used for status, charts, edges, dots.** Mint is brand. One color, one job. (Passes 1 and 3.)
- **Cards-as-default for section wrappers.** Cards are for items, never for sections. (Pass 1.)
- **Light mode.** Discussed honestly in pass 3. Dark stays because the user audience lives in dark engineering tools. Editorial design *can* be dark — read.cv, Vercel dark, Tana — and the serif headline against warm dark is the differentiated aesthetic. (Pass 3.)
- **Ambient gradients, background imagery, scroll animations.** Pulse dashboard ≠ marketing page. The page is defensibly flat. (Pass 3.)
- **"Soft opacity" period on the headline.** Caught as AI-design-cliché. Use `hanging-punctuation: last` instead. (Pass 4.)
- **Sync icon (spinning refresh).** Most generic element in product design. Text-only sync indicator. (Pass 4.)
- **"All caught up!" empty state with checkmark.** Generic cheerful template. *"Quiet day."* acknowledges silence as worth acknowledging. (Pass 4.)

## 14. The one piece of uncommon care

The **headline-complete**: serif (Instrument Serif), warm off-white, tight tracking, hanging punctuation, computed from `lastVisitedAt` delta, with the `"Quiet day."` fallback when there's nothing new, and a subtext line that names the user's last visit.

It's the centerpiece. Everything else in the design is restraint that lets this element speak. An engineering product (dark base, Geist sans, mono IDs) speaking with a literary voice (the serif, the sentence, the acknowledged silence) — the dissonance is what makes it memorable. Hyper structurally can't do this (their headline slot is a search prompt). Linear / Stripe / Vercel won't do this (sans-only by conviction). ContextOS can.

## 15. Out of scope for this redesign

These are real features that should exist but belong to follow-up phases:
- Direction summary generation pipeline (the slot is designed; generation is a separate phase).
- The `/activity` page redesign (Recent Activity moves there; that page itself needs design work).
- Integration health drawer detail.
- cmd-K command palette (the `<kbd>` styling is specced for when it ships).

## 17. Per-decision provenance (in scope)

Each decision card carries a one-line provenance quote: the specific Slack message or PR comment that turned discussion into a decision, with attribution.

**Visual treatment:** quote in italics, body color, source-linked. Attribution in tertiary color on its own line beneath.

```
"we should ship the fix in the rc branch instead of waiting"
 — Ilya in #dev-room, 18h ago
```

**Selection rule:** the synthesized "decision-causing utterance" — the comment immediately before consensus formed, or the explicit decision statement if present. Needs a backend signal of *which* message a decision was extracted from. If the data isn't there yet, the quote slot renders empty and the card is just title + people + channels.

**Why in scope (not deferred):** this is the move that makes the synthesis legible. Without it, "the system decided this" sounds magical; with it, "the system noticed this" sounds correct. Hyper can't do this; it's the one differentiated feature this redesign earns.

## 18. Open questions to resolve during planning

- Exact tech stack for the chrome cluster (single component vs. composed?).
- Where `lastVisitedAt` lives (client-side localStorage vs. server-side per-user state).
- The "since last visit" headline generator: rules-based for the redesign phase, LLM-generated later? My instinct: rules-based now (templates over conditions: "X is waiting on Y since Z", "N decisions and M sources since you last looked"), LLM later.
- Whether the redesign is one phase or split into structure + polish.
- Where the "decision-causing utterance" comes from (existing decision extraction pipeline output? new field on the decision entity? backfill required?). Resolves whether provenance quotes can ship with the redesign or need a parallel backend phase.

---

**Next step:** GSD phase planning (`/gsd:plan-phase 41`).

---

## Appendix: ASCII mockup — normal case (new items since last visit)

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│  ContextOS    Home  Context  Graph  Activity            last synced 4m ago   ●DA  │
│  ──────────                                                                        │
└────────────────────────────────────────────────────────────────────────────────────┘



        Vasiliy is waiting on RD-786            ← Instrument Serif, ~48px,
        since Tuesday.                             -0.02em tracking, 1.1 lh,
                                                   off-white #ece9e3, max-w-3xl,
                                                   hanging period
        ╴╴╴╴╴╴╴╴╴╴
        1 more decision and 30 new sources         ← Geist Sans 14px, secondary
        since you last looked, 14 hours ago.



        Recent decisions                                                  view all →
        ─────────────────────────────────────────────────────────────────────────────


      ┃ Merge RD-973 fixes into branch rc/74.16.2
      ┃ Ilya · Daulet  in #dev-room · #client-room · 18h ago
        ╭──────────────────────────────────────────────────────────────────────────╮
        │   "we should ship the fix in the rc branch instead of waiting"           │
        │    — Ilya in #dev-room, 18h ago                                          │
        ╰──────────────────────────────────────────────────────────────────────────╯


      ┃ Exclude the status bar plugin from the Capacitor upgrade
      ┃ Daulet · Vasiliy  in #dev-room · #support-prt · 1d ago
        ╭──────────────────────────────────────────────────────────────────────────╮
        │   "status bar plugin breaks on iOS 17 — leaving it out of the bump"      │
        │    — Daulet in #dev-room, 1d ago                                         │
        ╰──────────────────────────────────────────────────────────────────────────╯



        Active context                                                    view all →
        ─────────────────────────────────────────────────────────────────────────────

      ┃ RD-973   1eTaxi. Краш при вводе комментария к адресу...   30 sources   1d
        RD-781   [ClientApp][iOS][Classfields] Выпилить CapApp...   28 sources   2d
        RD-906   [iOS] Версия билда 1eTaxi не обновляется             29 sources   3d



        Needs you
        ─────────────────────────────────────────────────────────────────────────────

        RD-786   [ClientApp][iOS][CF] Настроить client-web-app
                 Vasiliy asked Tuesday, no reply yet · 3d
```

Legend (visual aid, not part of design):
- `┃` = the dim-amber 1px × 14px "new since last visit" marker in the left gutter.
- `╭─╮` boxes = individual decision cards (background-tint, no border).
- Active context = typographic list, no cards.
- "Needs you" with zero items: section absent entirely (not rendered).

## Appendix: ASCII mockup — quiet day (fallback)

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│  ContextOS    Home  Context  Graph  Activity            last synced 2m ago   ●DA  │
│  ──────────                                                                        │
└────────────────────────────────────────────────────────────────────────────────────┘



        Quiet day.                                  ← serif, full size, full weight,
                                                       hanging period
        ╴╴╴╴╴╴╴╴╴╴
        Nothing new since you last looked,             ← sans 14px, secondary
        2 hours ago.



        Recent decisions                                                  view all →
        ─────────────────────────────────────────────────────────────────────────────

        Merge RD-973 fixes into branch rc/74.16.2
        Ilya · Daulet  in #dev-room · #client-room · 18h ago
        ╭──────────────────────────────────────────────────────────────────────────╮
        │   "we should ship the fix in the rc branch instead of waiting"           │
        │    — Ilya in #dev-room, 18h ago                                          │
        ╰──────────────────────────────────────────────────────────────────────────╯



        Active context                                                    view all →
        ─────────────────────────────────────────────────────────────────────────────

        RD-973   1eTaxi. Краш при вводе комментария к адресу...   30 sources   1d
        RD-781   [ClientApp][iOS][Classfields] Выпилить CapApp...   28 sources   2d


                          (Needs you: structurally absent when zero)
```

No markers (no new items). Headline acknowledges the silence. "Needs you" gone, not "empty."
