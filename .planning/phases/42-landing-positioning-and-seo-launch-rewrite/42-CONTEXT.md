# Phase 42: Landing Positioning and SEO Launch Rewrite - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** User-provided launch-positioning discussion + live landing/code inspection + SEO/market research

<domain>
## Phase Boundary

Rewrite the public landing page positioning, visual story, and SEO metadata so ContextOS can launch now with the existing MVP. The page should sell the current product: automatic decision detection, source links, decision graph/context pages, and source-backed decision receipts. It should not wait for the future action layer.

The phase is copy/content/SEO-first, but the hero and product-proof visuals must support the new message. Do not broaden this into a generic landing redesign, action-layer build, or dashboard change.

</domain>

<decisions>
## Implementation Decisions

### Launch Strategy
- Launch with current MVP capabilities instead of waiting for the action layer.
- Treat the action layer as a roadmap teaser: tasks, doc updates, owner confirmation, and PR comments are "coming next" or "next phase" language only.
- The main conversion goal is still booking a call / early access, not self-serve signup optimization.

### Positioning Wedge
- Primary wedge: ContextOS is decision memory for engineering/product teams.
- Primary outcome: teams stop losing the "why" behind company decisions.
- Primary proof object: a Decision Receipt connected to original sources, people, affected systems, docs, tickets, and PRs.
- Avoid leading with generic "AI search," "chat with your docs," "company brain," "AI-native operating system," "self-improving company," "unlock," "supercharge," or other abstract category language.

### Visual Product Primitive
- Decision Receipt is the main visual primitive for the landing. It should feel like a proof-backed artifact, not an abstract graph or AI summary.
- A Decision Receipt should show:
  - Decision
  - Why
  - People involved
  - Original sources
  - Affected systems/workstreams
  - Status such as Verified or Needs review
- The decision graph should visually support the receipt with 4-6 understandable connected nodes/chips, not a large decorative graph.
- Source Evidence Chips should look clickable and concrete: Slack thread, meeting note, GitHub PR, Linear/Jira issue, Notion/doc, with counts or identifiers where useful.

### ICP
- Fast-moving engineering/product teams, roughly 20-300 people, with important decisions scattered across Slack, meetings, GitHub/GitLab, Jira/Linear, Notion, Telegram, and similar tools.
- Buyer/user split: CTO/founder/product/engineering leads buy the decision-memory value; engineers feel the ticket/PR context value.

### Hero Copy Direction
- Hero must make the ICP feel the pain first, then make the product obvious. "Decision memory" is good category/metadata language, but the first viewport should sell the broader outcome: the company stops losing why decisions were made. Tickets, PRs, docs, onboarding, and planning are proof surfaces, not the main promise.
- Recommended primary hero direction:
  - H1: "Know why your company works the way it does."
  - Subheadline: "ContextOS finds decisions buried across Slack, meetings, GitHub/GitLab, docs, and tickets, then maps what was decided, who was involved, why it was decided, and the original source."
  - Primary CTA label: "See your decision graph"
  - Primary CTA behavior: scroll/navigate to the booking call screen or section. The label sells the outcome; the click target handles the booking.
  - Secondary CTA: "View a sample trail"
- Alternative hero directions to test:
  - "Stop re-litigating decisions your team already made"
  - "Your team already decided this. ContextOS remembers why."
  - "Turn scattered conversations into source-backed decision memory"
- Do not use the earlier generic suggestion "Your company's decision memory, built automatically" as final copy without sharpening the audience and workflow.
- Use "Decision memory for engineering teams" as an explanatory line, metadata/OG title, or below-the-fold category statement, not necessarily the main emotional H1.

### SEO Direction
- Homepage title should include the product name, core category, and audience.
- Recommended title: "ContextOS | AI Decision Tracking for Engineering Teams"
- Recommended description: "ContextOS captures source-backed decisions from Slack, meetings, GitHub/GitLab, Jira/Linear, Notion, and Telegram so every ticket, PR, and teammate has the missing why."
- Do not add a meta keywords tag; Google does not use it.
- Use natural visible copy around these clusters:
  - decision tracking software
  - decision memory
  - source-backed decisions
  - engineering knowledge management
  - AI knowledge base for engineering teams
  - company knowledge graph
  - ticket context / PR context
  - Slack, GitHub, GitLab, Jira, Linear, Notion, meeting notes
- Use "decision intelligence" carefully. It is a real market term, but Gartner's category often means decision modeling, analytics, and automation platforms. ContextOS can say "decision intelligence layer" in body copy, but should not lead with "decision intelligence platform" unless intentionally competing in that category.

### Page Structure
- First viewport:
  - Badge: "Early access for engineering teams"
  - H1: why the company works the way it does / source-backed decision memory
  - Subheadline with source tools and decision graph
  - Primary CTA: "See your decision graph" with booking call navigation
  - Secondary CTA: "View a sample trail"
  - Product visual should tell one story: scattered work conversations -> extracted decision -> verified Decision Receipt -> decision graph. It should show actual decision nodes, source evidence, owners/participants, affected systems, and related work, not abstract AI glow.
- Problem section:
  - Reframe from "context gathering before coding" to "decision context disappears after meetings, Slack threads, and PRs."
  - Include concrete questions: "Why was this built this way?", "Who decided it?", "What alternatives were rejected?", "Is it still true?", "Where is the source?"
- Product section:
  - Headline: "Every decision comes with receipts."
  - Show a Decision Receipt with detected decision, why, people involved, original source links, affected systems/workstreams, related tickets/PRs/docs, and verification status.
- Workflow section:
  - Connect tools -> detect decisions -> link sources -> build decision graph -> surface context in planning, onboarding, docs, tickets, and PRs.
- Differentiation section:
  - "Not another company search box" can be used as a section idea, but keep it factual: ContextOS models decisions and their evidence, not just documents.
- Action-layer teaser:
  - "Next: close the loop with task creation, doc drafts, owner confirmation, and PR context comments."
  - Make clear these are future/coming-soon unless implemented before launch.
- Trust section:
  - Use permission-aware/source-backed/private-by-default language only if supported.
  - Remove or soften "SOC 2 compliant architecture" unless there is real certification or a verified security document.

### Quality Bar
- Copy should be plain, specific, and buyer-facing. Prefer concrete verbs: finds, links, shows, explains, gives, flags, puts context into.
- Lead with the moment of pain:
  - "The team decided this already. Nobody can find where."
  - "Nobody remembers why the system works this way."
  - "A PR reopens a tradeoff that was settled two months ago."
  - "A new engineer asks the same architecture question for the third time."
- The strongest demo offer is not "book a demo"; it is "we will show your decision graph from your own workspace." CTA language should make the call feel like a useful outcome, while the click still takes the user to the booking call flow.
- Avoid inflated claims: "10x," "magic," "revolutionary," "autonomous company," "self-improving OS."
- Every major claim should be backed by visible product capability, a source link, an integration, a screenshot/mockup, or a narrowly phrased example.

</decisions>

<specifics>
## Specific Ideas

- Replace current H1 "Stop gathering context. Start shipping code." because it sells productivity but hides the unique object: decisions.
- Replace the current metadata description's "auto-generates everything you need to know" because it is broad and can sound overpromised.
- Update `TrustBar` to include GitLab and Fathom if the page claims those integrations.
- The current integrations grid lists 8 integrations. If the page claims 9, decide whether "Slack Huddles" is shown as separate from Slack or keep the count implicit.
- Current feature copy already has useful seeds: "Decision tracking," "Knowledge graph," and "Context Page." These should be elevated, not buried.
- Current product visual/Remotion scenes should emphasize decision nodes, source evidence, owners, affected systems, and related work rather than generic sync or ticket-only enrichment.
- Add or refactor a reusable visual component for Decision Receipt. This should be the hero/product-proof centerpiece and can reuse existing mock data/styles.
- Use a Before/After problem visual:
  - Before: "Why do we do auth this way?", Slack search with many results, stale/outdated doc, unclear PR history.
  - After: a ContextOS answer/receipt with the decision, rationale, sources, and affected systems.
- Use cases should be broad, not ticket-only: onboarding, engineering changes, product planning, leadership visibility, docs freshness, and PR/ticket context.
- Reduce generic AI glow, fake productivity metrics, "AI synthesis complete" language, ticket-only visuals, and "ship faster" copy.
- Increase source links, timestamps, people involved, confidence/verification states, decision history, affected systems, and real-looking Slack/GitHub/GitLab/Linear/Jira/Notion references.

</specifics>

<code_context>
## Existing Code Insights

### Landing Files
- `apps/web/src/app/(landing)/layout.tsx`: current SEO title and description still use the old "Stop gathering context. Start shipping code." positioning.
- `apps/web/src/components/landing/Hero.tsx`: current H1/subheadline/CTA surface. This is the highest-priority copy edit.
- `apps/web/src/components/landing/ProblemSection.tsx`: currently frames the pain as context gathering before coding. Should be reframed toward lost decisions and lost rationale.
- `apps/web/src/components/landing/HowItWorks.tsx`: already has a usable three-step flow, but step 03 "Start coding immediately" should become source-backed decision context across planning, onboarding, docs, tickets, and PRs.
- `apps/web/src/components/landing/Features.tsx`: already has "Knowledge graph" and "Decision tracking" cards that can support the new wedge.
- `apps/web/src/components/landing/Integrations.tsx`: currently shows Linear, Slack, GitHub, Notion, Telegram, Jira, GitLab, and Fathom.
- `apps/web/src/components/landing/TrustBar.tsx`: currently shows only Linear, Slack, GitHub, Notion, Jira, and Telegram.
- `apps/web/src/components/landing/CTASection.tsx`: booking embed can stay; surrounding copy should speak to seeing detected decisions from the buyer's own workspace.
- `apps/web/src/app/landing.css`: landing styling is scoped under `.landing-theme`; copy changes should not disturb dashboard styles.

### Existing Dirty Worktree
- As of context gathering, unrelated/unowned changes exist in dashboard chrome and Remotion landing files. Do not revert them.

</code_context>

<deferred>
## Deferred Ideas

- Build the action layer: create Linear/Jira tasks from decisions, draft Notion/Confluence updates, ask owners in Slack, and comment on PRs with relevant decision context.
- Create dedicated SEO content pages for "decision debt," "AI decision tracking," or "engineering knowledge graph." Do this only after launch and only if each page has real original examples, not search-engine-first filler.
- Full security/trust page with compliance posture and data handling details.

</deferred>

---

*Phase: 42-landing-positioning-and-seo-launch-rewrite*
*Context gathered: 2026-05-22*
