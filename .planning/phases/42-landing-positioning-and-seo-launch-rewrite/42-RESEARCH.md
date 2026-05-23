# Phase 42: Landing Positioning and SEO Launch Rewrite - Research

**Researched:** 2026-05-22
**Domain:** B2B AI startup positioning, decision-memory category design, landing-page conversion copy, SEO/GEO/AEO for AI search discovery
**Confidence:** HIGH for category and homepage recommendation; MEDIUM for keyword prioritization without paid search-volume tooling

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Launch Strategy
- Launch with current MVP capabilities instead of waiting for the action layer.
- Treat the action layer as a roadmap teaser: tasks, doc updates, owner confirmation, and PR comments are "coming next" or "next phase" language only.
- The main conversion goal is still booking a call / early access, not self-serve signup optimization.

#### Positioning Wedge
- Primary wedge: ContextOS is decision memory for engineering/product teams.
- Primary outcome: teams stop losing the "why" behind company decisions.
- Primary proof object: source-backed decisions connected to tickets, PRs, docs, messages, people, and systems.
- Avoid leading with generic "AI search," "chat with your docs," "company brain," "AI-native operating system," "self-improving company," "unlock," "supercharge," or other abstract category language.

#### ICP
- Fast-moving engineering/product teams, roughly 20-300 people, with important decisions scattered across Slack, meetings, GitHub/GitLab, Jira/Linear, Notion, Telegram, and similar tools.
- Buyer/user split: CTO/founder/product/engineering leads buy the decision-memory value; engineers feel the ticket/PR context value.

#### Hero Copy Direction
- Hero must answer four questions immediately: what is this, who is it for, what does it do, why is it different.
- Recommended primary hero direction:
  - H1: "Decision memory for engineering teams"
  - Subheadline: "ContextOS captures source-backed decisions from Slack, meetings, GitHub/GitLab, Jira/Linear, Notion, and Telegram, then puts the missing why into tickets, PRs, onboarding, and docs."
- Alternative hero directions to test:
  - "Know why every decision was made"
  - "Source-backed context for every ticket and PR"
  - "Stop losing the why behind engineering decisions"
- Do not use the earlier generic suggestion "Your company's decision memory, built automatically" as final copy without sharpening the audience and workflow.

#### SEO Direction
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

#### Page Structure
- First viewport:
  - Badge: "Early access for engineering teams"
  - H1: decision memory / source-backed decisions
  - Subheadline with tools and workflows
  - Primary CTA label: "See your decision graph"
  - Primary CTA behavior: scroll/navigate to the booking call screen or section
  - Secondary CTA: "See how it works"
  - Product visual should show actual decision/source/ticket context, not abstract AI glow.
- Problem section:
  - Reframe from "context gathering before coding" to "decision context disappears after meetings, Slack threads, and PRs."
  - Include concrete questions: "Why was this built this way?", "Who decided it?", "What alternatives were rejected?", "Is it still true?", "Where is the source?"
- Product section:
  - Show detected decisions, source links, affected tickets/PRs, owners/participants, and context pages.
- Workflow section:
  - Connect tools -> detect decisions -> link sources -> surface context in tickets/PRs/onboarding.
- Differentiation section:
  - "Not another company search box" can be used as a section idea, but keep it factual: ContextOS models decisions and their evidence, not just documents.
- Action-layer teaser:
  - "Next: close the loop with task creation, doc drafts, owner confirmation, and PR context comments."
  - Make clear these are future/coming-soon unless implemented before launch.
- Trust section:
  - Use permission-aware/source-backed/private-by-default language only if supported.
  - Remove or soften "SOC 2 compliant architecture" unless there is real certification or a verified security document.

#### Quality Bar
- Copy should be plain and specific. Prefer concrete verbs: captures, links, detects, shows, explains, puts context into.
- Avoid inflated claims: "10x," "magic," "revolutionary," "autonomous company," "self-improving OS."
- Every major claim should be backed by visible product capability, a source link, an integration, a screenshot/mockup, or a narrowly phrased example.

### the agent's Discretion

None in `42-CONTEXT.md`.

### Deferred Ideas (OUT OF SCOPE)

- Build the action layer: create Linear/Jira tasks from decisions, draft Notion/Confluence updates, ask owners in Slack, and comment on PRs with relevant decision context.
- Create dedicated SEO content pages for "decision debt," "AI decision tracking," or "engineering knowledge graph." Do this only after launch and only if each page has real original examples, not search-engine-first filler.
- Full security/trust page with compliance posture and data handling details.

## Executive Recommendation

ContextOS should claim **decision memory for engineering teams** on the launch homepage, with **AI decision tracking** used in the SEO title and metadata. This is the cleanest category because it names the product object ("decisions"), the buyer/user ("engineering teams"), and the differentiated behavior ("source-backed why" inside tickets and PRs). [VERIFIED: phase context] [CITED: https://www.glean.com/product/workplace-search-ai] [CITED: https://www.atlassian.com/software/rovo/guides/admin-guide/how-rovo-helps-your-teams] [CITED: https://www.notion.com/en-gb/product/enterprise-search]

Do **not** lead with "enterprise AI search," "knowledge graph," "AI knowledge base," "context layer," or "decision intelligence platform." Enterprise AI search is owned by Glean, Microsoft, Notion, Rovo, Guru, and Slite; knowledge graph is already a proof mechanism in Glean and Atlassian messaging; Gartner's "decision intelligence platform" category means decision modeling, analytics, governance, and automation, which would mis-set buyer expectations for the current ContextOS MVP. [CITED: https://www.glean.com/product/enterprise-graph] [CITED: https://www.atlassian.com/blog/company-news/rovo-team-26] [CITED: https://www.gartner.com/reviews/market/decision-intelligence-platforms]

The launch page should make one promise: **ContextOS finds the decision trail your team already created and puts the missing why where engineers work.** The proof should be a product visual showing a detected decision, source links, related ticket/PR, participants, and affected docs. [VERIFIED: codebase grep] [VERIFIED: phase context]

**Primary recommendation:** Use `Decision memory for engineering teams` as the category spine, but do not make the launch page ticket-first. Tickets and PRs are important proof surfaces, but the product promise is broader: ContextOS makes the company legible by preserving the why behind decisions. The H1 should make the buyer think, "yes, we lose this context constantly," without implying ContextOS is mainly a ticket-enrichment tool.

### Deep Research Update: What The Modern Sources Actually Change

The useful 2026 signal is not "use better SEO copy." It is that enterprise AI products are moving from passive search to **context-bearing workflow layers**: systems that gather context across tools, preserve institutional memory, and eventually coordinate actions. That validates ContextOS strategically, but it does **not** mean the launch page should say "enterprise orchestration layer." The launch page should translate that trend into a concrete wedge: decisions, sources, tickets, and PRs. [CITED: https://a16z.com/from-system-of-record-to-system-of-intelligence/] [CITED: https://a16z.com/podcast/big-ideas-2026-the-enterprise-orchestration-layer/]

Anthropic's context-engineering guidance is the technical reason the wedge matters: agents do not become reliable by receiving every possible document; they need a small, high-signal set of relevant context at the right moment. For ContextOS, this argues against "search all your tools" and for "curated decision context where work happens." The page should make this visible with decision cards that include rationale, rejected alternatives, sources, owner/participants, and affected ticket/PR. [CITED: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents]

Glean and Atlassian show where the horizontal incumbents are going: enterprise graph, system of context, MCP access, agent actions, and governed workflow automation. ContextOS should not fight them on "all company context." It should own the narrower, more legible object those platforms still blur: the decision trail behind engineering work. [CITED: https://www.glean.com/product/system-of-context] [CITED: https://developers.glean.com/] [CITED: https://www.atlassian.com/blog/company-news/rovo-team-26]

Linear's 2026 Code Intelligence launch is proof that context belongs inside work surfaces, not in a separate knowledge portal. Linear frames code as objective product context and shows demand for asking why something works, what changed, and who has context. For ContextOS, ticket/PR context should be one place where the decision graph shows up, not the main category. [CITED: https://linear.app/now/code-intelligence-for-linear-agent]

### Conversion Copy Update: Say The Thing Buyers Already Feel

The copy should not sound like a new category being explained to analysts. It should sound like an engineering lead describing the mess they want gone:

- "The team decided this already. Nobody can find where."
- "Nobody remembers why the system works this way."
- "A PR reopens a tradeoff that was settled two months ago."
- "A new engineer asks the same architecture question for the third time."
- "The person who knew the answer left, and the source is buried in Slack."

The launch page should therefore use a **company-memory / decision-graph H1** with concrete workflow proof immediately nearby:

```text
H1:
Know why your company works the way it does.

Subheadline:
ContextOS finds decisions buried across Slack, meetings, GitHub/GitLab, docs, and tickets, then maps what was decided, who was involved, why it was decided, and the original source.

Category proof line:
Decision memory for engineering teams shipping through Slack, GitHub/GitLab, Jira/Linear, Notion, Telegram, and meetings.
```

The call-to-action should feel like a useful artifact, not a sales interruption:

```text
Primary CTA:
See your decision graph

CTA behavior:
Scroll or navigate to the booking call screen/section. The CTA label sells the outcome; the click target is still the call booking flow.

CTA support:
Connect your tools and see the decisions your team made last week, with rationale, owners, source links, and affected systems.
```

This is a stronger conversion promise than "Book a demo" because it tells the buyer what they get from the call: their own decision map. It also stays inside the current MVP because ContextOS already detects decisions, links sources, and generates context.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LAND-04 | Landing hero and first viewport reposition ContextOS around source-backed decision memory for engineering teams, not generic context gathering or AI search | Competitor scan shows broad search/answers/graph language is crowded; recommendation makes decisions the object and tickets/PRs the workflow. [CITED: https://www.glean.com/product/workplace-search-ai] |
| LAND-05 | SEO title, description, H1, and visible headings target the decision-memory wedge while naturally covering adjacent intent around AI knowledge management, enterprise search, and engineering knowledge graphs | Google AI search guidance rewards crawlable, non-commodity, well-structured content; copy architecture includes adjacent topics without keyword stuffing. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide] |
| LAND-06 | Landing copy foregrounds current MVP capabilities only: detected decisions, source links, graph/context pages, and generated ticket/PR context | Current landing components already expose decision tracking, knowledge graph, context page, integrations, and booking CTA surfaces. [VERIFIED: codebase grep] |
| LAND-07 | Action-layer copy is clearly framed as coming next unless implemented, and unsupported trust/compliance claims are removed or softened | Gartner warns many agentic AI projects are hype-driven or misapplied; claims about autonomous action must stay future-tense until implemented. [CITED: https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027] |
| LAND-08 | Landing visuals introduce Decision Receipt as the primary product primitive instead of generic AI glow, abstract graph-only UI, or ticket-only context | Decision Receipt makes the product concrete: decision, rationale, people involved, original sources, affected systems, and verification status. This supports the "not search, proof-backed decision memory" positioning. [VERIFIED: phase context] |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Homepage positioning and copy | Browser / Client | Frontend Server (SSR) | Landing components render the hero, sections, product visual, and CTA; the copy must be visible and crawlable. [VERIFIED: codebase grep] |
| SEO title and description | Frontend Server (SSR) | Browser / Client | Next metadata currently lives in `apps/web/src/app/(landing)/layout.tsx`; page metadata should align with visible H1 and hero copy. [VERIFIED: codebase grep] |
| GEO/AEO discoverability | Frontend Server (SSR) | CDN / Static | AI search still depends on crawlable/indexable pages, snippets, page structure, and source-worthy content. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide] |
| Product proof visual | Browser / Client | API / Backend | The public page can use static/mock product visuals now; later live demos would need backend data and permissions. [VERIFIED: codebase grep] |
| Trust/security claims | Frontend Server (SSR) | API / Backend | The landing page should only claim controls that are supported by product architecture or company security docs. [VERIFIED: phase context] |
| Action-layer teaser | Browser / Client | API / Backend | Task/doc/owner/PR actions are explicitly deferred; homepage copy can label them "coming next" only. [VERIFIED: phase context] |

## Market And Category Map

| Category Candidate | Market Reality | Fit For ContextOS | Recommendation |
|--------------------|----------------|-------------------|----------------|
| Enterprise AI search | Glean, Microsoft Copilot Search, Notion AI, Rovo, Guru, and Slite all claim versions of unified search, answers, connected apps, citations, permissions, and enterprise graphs. [CITED: https://www.glean.com/product/workplace-search-ai] [CITED: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-search-faq] [CITED: https://www.notion.com/en-gb/product/enterprise-search] | LOW as primary; ContextOS would sound smaller than incumbents and would hide the decision-specific wedge. | Mention only as adjacent in body copy: "not another company search box." |
| AI knowledge base / agentic knowledge base | Guru and Slite emphasize verified knowledge, trusted answers, Slack answers, and self-maintaining docs. [CITED: https://www.getguru.com/solutions/agentic-knowledge-base] [CITED: https://slite.com/ask] | MEDIUM as adjacent; ContextOS overlaps on sources and trust but does not want to be judged as a wiki replacement. | Use "engineering knowledge management" and "AI knowledge base" as secondary SEO phrases, not hero category. |
| Knowledge graph / context graph | Glean's Enterprise Graph and Atlassian's Teamwork Graph already frame graph as the context substrate for enterprise AI and agents. [CITED: https://www.glean.com/product/enterprise-graph] [CITED: https://www.atlassian.com/blog/company-news/rovo-team-26] | MEDIUM as proof; ContextOS has graph/context pages, but "knowledge graph" alone sounds technical and not outcome-specific. | Use graph as evidence: "Decisions connected to people, tickets, PRs, docs, and source links." |
| Decision intelligence | Gartner's 2026 definition includes decision modeling, execution, monitoring, governance, optimization, simulation, BI, events, and AI agents. [CITED: https://www.gartner.com/reviews/market/decision-intelligence-platforms] | LOW as primary; the term pulls buyers toward analytics/automation platforms, not engineering decision memory. | Use "decision intelligence layer" only in lower-page explanatory copy if needed. |
| Context layer | Atlassian and Glean increasingly describe context graphs/layers for agents and enterprise AI. [CITED: https://www.atlassian.com/blog/company-news/rovo-team-26] [CITED: https://www.glean.com/product/overview] | MEDIUM; strategically true but abstract for a first-viewport launch message. | Use as investor/architecture language, not launch hero. |
| Context engineering / system of context | Anthropic frames context engineering as the runtime discipline for reliable agents; Glean sells "system of context" and MCP surfaces that bring company context into external agents and IDEs. [CITED: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents] [CITED: https://www.glean.com/product/system-of-context] [CITED: https://developers.glean.com/] | MEDIUM-HIGH strategically; it validates ContextOS, but the phrase is too infrastructure-heavy for a launch hero. | Use internally and in investor/technical copy. Translate externally to "source-backed decision context for tickets and PRs." |
| Engineering knowledge management | Existing tools cover docs, search, and Q&A, but engineering-specific ticket/PR context is a credible wedge. [CITED: https://www.notion.com/en-gb/product/enterprise-search] [CITED: https://www.getguru.com/solutions/agentic-knowledge-base] | HIGH as secondary; useful for SEO and buyer framing. | Use in section headings and metadata alternatives. |
| Decision memory / AI decision tracking | Less crowded than broad search, points at the product object, and matches ContextOS current capabilities. [VERIFIED: phase context] [VERIFIED: codebase grep] | HIGH. | Primary category: "Decision memory for engineering teams"; SEO category: "AI decision tracking." |

**Category decision:** ContextOS should be a **decision-memory product**, not an enterprise-search product. "AI decision tracking for engineering teams" is the more searchable phrasing; "decision memory for engineering teams" is the stronger human-facing headline.

## Competitor Messaging Table

| Competitor | Current Category / Headline | Words They Own | Gap ContextOS Can Own |
|------------|-----------------------------|----------------|------------------------|
| Glean | "AI-powered workplace search" and "Work AI" with search, assistant, agents, connectors, and enterprise graph. [CITED: https://www.glean.com/product/workplace-search-ai] [CITED: https://www.glean.com/] | Search, answers, 100+ connectors, Work AI, Enterprise Graph, personalization, permissions. | Avoid "work AI" and "enterprise search." Say "Search finds documents. ContextOS shows the decision trail behind the work." |
| Glean Enterprise Graph | "The foundation of enterprise superintelligence" and graph relationships across people, projects, teams, and processes. [CITED: https://www.glean.com/product/enterprise-graph] | Enterprise Graph, superintelligence, context, agents, multi-hop reasoning. | Do not make "knowledge graph" the category. Make graph the proof: decisions are linked to sources, owners, tickets, and PRs. |
| Atlassian Rovo | Personalized enterprise search, chat, agents, and workflows powered by Teamwork Graph. [CITED: https://www.atlassian.com/software/rovo/guides/admin-guide/how-rovo-helps-your-teams] | Teamwork Graph, search/chat/agents, AI teamwork, Jira/Confluence workflow execution. | Do not imply ContextOS is the whole system of work. Position as cross-tool decision memory that feeds existing tickets and PRs. |
| Atlassian Team '26 | Rovo + Teamwork Graph as "connective spine" for agents that search, reason, and act across tools. [CITED: https://www.atlassian.com/blog/company-news/rovo-team-26] | AI-native teamwork, context spine, governed agents, act across stack. | Avoid "AI-native organization" and autonomous-work claims. ContextOS should be narrower: source-backed decisions before action. |
| Guru | "AI-ready knowledge layer" and "self-maintaining knowledge layer" with verified, permission-aware answers. [CITED: https://www.getguru.com/solutions/agentic-knowledge-base] | Verified knowledge, permission-aware answers, knowledge agents, source of truth, knowledge quality. | Do not say "one brain" or "single source of truth." Say "the source-backed why behind engineering work." |
| Slite Ask | "Stop searching, start asking" and instant answers from trusted company info plus connected apps. [CITED: https://slite.com/ask] | Ask, trusted answers, Slack answers, verified docs, fewer repeated questions. | Avoid "ask your company knowledge." ContextOS should be proactive and object-based: it captures decisions, not just answers questions. |
| Notion AI Enterprise Search | "Every answer, one search" across connected apps, with citations, reports, permissions, and Research Mode. [CITED: https://www.notion.com/en-gb/product/enterprise-search] | Every answer, one search, reports in minutes, AI workspace, permission-aware search. | Do not compete on all-company research/report generation. Lead with ticket/PR decision context for engineering/product teams. |
| Microsoft 365 Copilot Search | AI-powered unified search using Microsoft Graph, third-party connectors, semantics, user context, and organizational relationships. [CITED: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-search-faq] | Unified enterprise search, Microsoft Graph, work context, Copilot Chat transition. | Avoid "universal search." ContextOS should integrate into engineering workflows that Microsoft search does not specialize in. |

## Differentiated Wording

Use these phrases repeatedly:

- "Decision memory for engineering teams" [VERIFIED: phase context]
- "AI decision tracking for engineering teams" [VERIFIED: phase context]
- "Source-backed decisions" [VERIFIED: phase context]
- "The missing why behind tickets and PRs" [VERIFIED: phase context]
- "Decision trails, not another search box" [CITED: https://www.glean.com/product/workplace-search-ai]
- "Decisions connected to people, source links, docs, tickets, and PRs" [VERIFIED: codebase grep]
- "Context your engineers can verify" [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide]

Avoid these phrases because incumbents already occupy them or they sound like AI slop:

- "Work AI" [CITED: https://www.glean.com/]
- "Enterprise superintelligence" [CITED: https://www.glean.com/product/enterprise-graph]
- "Every answer, one search" [CITED: https://www.notion.com/en-gb/product/enterprise-search]
- "Stop searching, start asking" [CITED: https://slite.com/ask]
- "Company brain" [ASSUMED]
- "AI-native operating system" [ASSUMED]
- "Self-improving company" [ASSUMED]
- "Autonomous agents for every workflow" unless implemented and governed. [CITED: https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027]

## Modern SEO / GEO / AEO Strategy For 2026

### What Matters Now

1. **SEO is still the base layer for AI search.** Google's generative AI guidance says AI Overviews and AI Mode are rooted in Search ranking and quality systems, and use retrieval-augmented generation plus query fan-out from the Search index. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide]

2. **Query fan-out rewards semantic coverage, not keyword stuffing.** Google says AI Mode breaks questions into subtopics and issues multiple searches; the homepage should include clear sections for problem, sources, decision extraction, ticket/PR context, graph proof, integrations, security posture, and CTA. [CITED: https://blog.google/products-and-platforms/products/search/google-search-ai-mode-update/] [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide]

3. **Non-commodity content matters more than "what is X" filler.** Google's AI optimization guide warns against recycled commodity content and thin pages made for search variants; ContextOS should publish real decision-debt examples later, not generic beginner SEO pages. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide]

4. **AI answer visibility is about being citable, parseable, and repeated consistently.** a16z's GEO analysis argues that visibility shifts from ranking to reference rates and model-recalled brand framing; this is useful as operator commentary, but still experimental and lower confidence than Google documentation. [CITED: https://a16z.com/geo-over-seo/]

5. **ChatGPT discovery depends on crawl access if ContextOS wants to appear in ChatGPT search summaries/snippets.** OpenAI's publisher FAQ says public websites can appear in ChatGPT search and recommends not blocking `OAI-SearchBot`; it also distinguishes search crawling from training crawling via `GPTBot`. [CITED: https://help.openai.com/en/articles/12627856-publishers-and-developers-faq]

6. **Crawler policy is now a launch decision.** Cloudflare's 2025 Content Signals Policy adds machine-readable `search`, `ai-input`, and `ai-train` preferences in `robots.txt`, but Cloudflare also says these signals are preferences, not technical countermeasures. [CITED: https://blog.cloudflare.com/content-signals-policy/]

7. **Structured data is a clarity layer, not a ranking hack.** Google says structured data gives explicit clues about page meaning and must describe visible page content; ContextOS should add only visible `Organization` and `SoftwareApplication` facts. [CITED: https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data] [CITED: https://schema.org/SoftwareApplication]

### Launch SEO/GEO Checklist

| Action | Why It Matters | Recommendation |
|--------|----------------|----------------|
| Align title, H1, OG title, and first paragraph | Google uses title, prominent headings, and page content to infer result title/snippet. [CITED: https://developers.google.com/search/docs/appearance/title-link] | Use one category story: decision memory / AI decision tracking. |
| Make the first viewport self-contained | AI crawlers and users need immediate category clarity. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide] | H1 + subheadline must include audience, object, sources, and workflow. |
| Use visible FAQs only if they answer real buyer objections | Structured data must reflect visible content. [CITED: https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data] | Add a short "Questions buyers ask" section only if it fits the page. |
| Let crawlers see actual copy without interaction | Google can process JavaScript but says JS SEO is more complex. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide] | Keep core copy in server-rendered Next components; do not hide key copy only in Remotion canvas/video. |
| Decide `robots.txt` AI access | OpenAI and Cloudflare now expose crawler/control choices. [CITED: https://help.openai.com/en/articles/12627856-publishers-and-developers-faq] [CITED: https://blog.cloudflare.com/content-signals-policy/] | For launch visibility, allow search crawlers and disallow training if desired; do not accidentally block `OAI-SearchBot` if ChatGPT discovery matters. |
| Build earned-source surface area | a16z frames GEO around reference rates and source documents, but the tactic is still experimental. [CITED: https://a16z.com/geo-over-seo/] | Later: founder essay, launch post, comparison page, and technical "decision debt" essay with original examples. |

### Keyword / Topic Clusters

**Primary homepage cluster:**
- AI decision tracking software
- decision memory for engineering teams
- decision tracking for engineering teams
- source-backed decisions
- engineering decision context
- ticket context
- PR context

**Secondary body-copy cluster:**
- engineering knowledge management
- AI knowledge base for engineering teams
- company knowledge graph
- engineering knowledge graph
- enterprise AI search
- internal knowledge search
- Slack decision tracking
- GitHub PR context
- Jira / Linear ticket context
- meeting decision tracking

**GEO prompt cluster to write for naturally:**
- "What is the best way to track engineering decisions across Slack and GitHub?"
- "How do engineering teams keep the why behind tickets?"
- "What is decision debt in software teams?"
- "What is the difference between enterprise search and decision memory?"
- "How do I generate context for Jira, Linear, GitHub, or GitLab work?"

## Recommended Homepage Architecture

### Visual System Recommendation

The landing should visually move from "AI ticket helper" to **source-backed decision graph**. The central product primitive is **Decision Receipt**: a concrete artifact that proves ContextOS extracted a real decision and can show evidence for it.

```text
Decision Receipt
Decision: Keep tenant isolation at database level
Why: Enterprise customers need stricter data boundaries
People involved: Ayan, Madina, Bekbol
Sources: Slack thread, meeting note, GitHub PR, architecture doc
Affected systems: Auth, Billing, Enterprise plan
Status: Verified / Needs review
```

The hero visual should tell one clear story:

```text
scattered work conversations -> extracted decision -> verified decision graph
```

Recommended hero composition:
- Left: H1, subheadline, primary CTA.
- Right: product mockup with a central Decision Receipt card and source evidence chips around it.
- Source chips should be specific and trustworthy: `Slack thread - 14 messages`, `Meeting - 32 min`, `PR #418`, `Linear ENG-217`, `Architecture doc`.
- The graph should have 4-6 understandable nodes. Avoid a big decorative network that looks impressive but says nothing.

Core visual components:
- Decision Receipt Card: decision, why, people involved, original sources, related work, confidence/status.
- Source Evidence Chips: clickable-looking source references with service, count/identifier, and timestamp where useful.
- Decision Graph Preview: decision, owner/participant, source, system, ticket/PR/doc nodes connected around one concrete decision.
- Before/After Panel: before shows Slack search overload, stale docs, unclear PR history; after shows ContextOS producing a source-backed answer/receipt.
- Use Case Cards: onboarding, engineering changes, product planning, leadership visibility, docs freshness, PR/ticket context.

Reduce or remove:
- Generic AI glow as the main visual device.
- Fake productivity metrics such as `2-6 hours` unless backed by customer evidence.
- Ticket-only visuals that make ContextOS look like a Linear/Jira helper.
- "AI synthesis complete" UI copy.
- Vague "ship faster" framing.

Increase:
- Source links, timestamps, people involved, confidence/verification states, decision history, affected systems, and real-looking Slack/GitHub/GitLab/Linear/Jira/Notion references.

### Ship Now

| Order | Section | Recommended Headline | Purpose |
|-------|---------|----------------------|---------|
| 1 | Hero | `Know why your company works the way it does.` | Make the ICP feel the broader lost-decision pain immediately, then explain ContextOS as decision memory for engineering teams. |
| 2 | Trust / integrations strip | `Built from the tools where decisions already happen` | Show Slack, meetings/Fathom, GitHub, GitLab, Jira, Linear, Notion, Telegram without over-counting unsupported integrations. [VERIFIED: codebase grep] |
| 3 | Problem | `The decision happened. The why disappeared.` | Reframe from generic "context gathering" to lost rationale. |
| 4 | Product proof | `Every decision comes with receipts` | Show Decision Receipt: decision, rationale, people involved, source evidence, affected systems, status, and related docs/tickets/PRs. |
| 5 | Workflow | `From scattered discussion to decision graph` | Tools -> detect decisions -> link evidence -> map affected systems/work -> surface context wherever the team needs it. |
| 6 | Differentiation | `Not another company search box` | Separate decision trails from generic AI search/answers. |
| 7 | Current capabilities | `What ContextOS can do today` | Detected decisions, source links, graph/context pages, ticket/PR context. [VERIFIED: phase context] |
| 8 | Coming next | `Next: close the loop from decision to action` | Future task/doc/owner/PR actions, clearly labeled coming next. [VERIFIED: phase context] |
| 9 | CTA | `See your team's decision graph` | Early access call that promises to show decisions from the buyer's own workspace, not a generic sales demo. |

### Defer Until After Launch

| Page / Asset | Why Defer | Launch Gate Before Shipping |
|--------------|-----------|-----------------------------|
| `/decision-debt` | High-potential GEO page, but generic definitions would be commodity content. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide] | Needs original examples, screenshots, and a crisp ContextOS point of view. |
| `/compare/enterprise-search-vs-decision-memory` | Useful differentiation page, but should not distract from homepage launch. | Needs side-by-side examples of search result vs decision trail. |
| `/use-cases/ticket-context` | Strong conversion page for engineers. | Needs real or high-fidelity ticket context examples. |
| `/use-cases/pr-context` | Strong developer workflow page. | Needs product evidence for PR context generation. |
| `/security` | Required for enterprise trust eventually. | Needs verified security architecture, data handling, and compliance posture. |
| Integration landing pages | Good for long-tail queries. | Needs one page per real integration with current capability, not placeholder SEO copy. |

## Exact Landing Copy Variants

### Metadata

**Recommended title:**

```text
ContextOS | AI Decision Tracking for Engineering Teams
```

**Recommended description:**

```text
ContextOS captures source-backed decisions from Slack, meetings, GitHub/GitLab, Jira/Linear, Notion, and Telegram so every ticket, PR, and teammate has the missing why.
```

**OG title:**

```text
Decision memory for engineering teams
```

**OG description:**

```text
Turn scattered discussions, tickets, PRs, docs, and meetings into source-backed decision context your team can verify.
```

### Hero Variant A - Recommended Conversion Copy

```text
Badge:
Early access for teams shipping fast

H1:
Know why your company works the way it does.

Subheadline:
ContextOS finds decisions buried across Slack, meetings, GitHub/GitLab, docs, and tickets, then maps what was decided, who was involved, why it was decided, and the original source.

Primary CTA:
See your decision graph

Secondary CTA:
View a sample trail
```

Why: this keeps the promise broad enough for the product: not ticket enrichment, not generic search, but a source-backed map of why the company works the way it does. [VERIFIED: phase context]

### Hero Variant B - Stronger Leadership Pain

```text
Badge:
For teams shipping through Slack, tickets, PRs, and meetings

H1:
Stop re-litigating decisions your team already made.

Subheadline:
ContextOS turns scattered Slack threads, meeting notes, PRs, docs, and tickets into source-backed decision trails, so engineers know what was decided, why it was decided, and where the source lives.

Primary CTA:
Find our lost decisions

Secondary CTA:
See the decision trail
```

Why: best for founders, CTOs, and product/engineering leads who feel repeated alignment meetings and duplicated debates. [ASSUMED]

### Hero Variant C - Engineer First

```text
Badge:
Source-backed context before you change code

H1:
Know why this exists before you touch it.

Subheadline:
Before someone changes a system, joins a project, or reviews a plan, ContextOS shows the decisions, rejected alternatives, source links, and owners behind it.

Primary CTA:
See your decision graph

Secondary CTA:
See a sample trail
```

Why: best if the landing visual shows engineering workflows, but the message remains broader than tickets and PRs. [ASSUMED]

### Problem Section Copy

```text
Label:
The Problem

Headline:
The decision happened. The why disappeared.

Body:
A Slack thread changed the architecture. A meeting settled the tradeoff. A PR implemented it. Three weeks later, the ticket only says what to build, not why.

Questions:
- Why was this built this way?
- Who decided it?
- What alternatives were rejected?
- Is the decision still true?
- Where is the source?
```

### Product Proof Section Copy

```text
Headline:
Every decision comes with receipts

Body:
ContextOS detects decisions across your work tools, links them to source messages, meeting moments, docs, code, tickets, PRs, and people, then builds a decision page your team can trust.

Proof labels:
- Decision
- Source links
- Owners and participants
- Affected systems and workstreams
- Related docs, tickets, and PRs
- Graph relationships
```

### Workflow Section Copy

```text
Headline:
From scattered discussion to decision graph

Step 1:
Connect the places decisions already happen
Slack, meetings, GitHub/GitLab, Jira/Linear, Notion, and Telegram.

Step 2:
ContextOS detects the decision trail
Decisions, tradeoffs, people, source links, and affected work are connected automatically.

Step 3:
Your team can ask why and verify the source
Planning, onboarding, docs, tickets, and PRs get source-backed context instead of another search chore.
```

### Differentiation Section Copy

```text
Headline:
Not another company search box

Body:
Search helps you find documents. ContextOS models decisions and their evidence: what changed, why it changed, who was involved, where it was discussed, and which work it affects.
```

### Current Capability Section Copy

```text
Headline:
What ContextOS can do today

Cards:
- Detect decisions from team conversations
- Link every decision back to its source
- Connect decisions to tickets, PRs, docs, people, and systems
- Generate context pages for engineering work
- Show relationships in a knowledge graph
```

### Coming Next Copy

```text
Headline:
Next: close the loop from decision to action

Body:
ContextOS is moving from remembering decisions to helping teams act on them: task creation, doc update drafts, owner confirmation, and PR comments with relevant decision context.

Microcopy:
Coming next. The launch product focuses on decision memory and source-backed context.
```

### CTA Copy

```text
Headline:
See your team's decision graph

Body:
Book a call to see how ContextOS turns your scattered discussions into a source-backed map of what was decided, who was involved, why it was decided, and the original source.

Button:
See your decision graph

Click behavior:
Navigate to the booking call screen/section.
```

## Claims To Avoid

| Avoid Claim | Why It Is Risky | Safer Replacement |
|-------------|-----------------|-------------------|
| "Auto-generates everything you need to know" | Too broad; implies completeness and may overpromise. [VERIFIED: codebase grep] | "Generates source-backed context from the tools you connect." |
| "2-6 hours per ticket" | Current page uses this, but no source was verified during research. [VERIFIED: codebase grep] | "Hours" only if backed by customer evidence; otherwise say "time." |
| "SOC 2 compliant architecture" | Architecture language can imply certification; phase context says soften unless verified. [VERIFIED: phase context] | "Built for source-backed, permission-conscious workflows" only if implemented; otherwise omit. |
| "Permission-aware" | Competitors make this claim with explicit enterprise controls; only claim it if product permission enforcement is verified. [CITED: https://www.glean.com/product/workplace-search-ai] [CITED: https://www.notion.com/en-gb/product/enterprise-search] | "Source-backed" and "linked to original tools." |
| "Autonomous agents create tasks/docs/PR comments" | Action layer is deferred; Gartner warns about agent washing and misapplied agentic claims. [CITED: https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027] | "Coming next: task creation, doc drafts, owner confirmation, and PR comments." |
| "Company brain" | Generic and overused; not a precise product object. [ASSUMED] | "Decision memory." |
| "AI-native operating system" | Abstract and too large for launch MVP. [VERIFIED: phase context] | "Decision memory for engineering teams." |
| "Never lose context again" | Absolute claim. [ASSUMED] | "Stop losing the why behind engineering decisions." |
| "All decisions are captured automatically" | Overpromises detection recall. [ASSUMED] | "Captures source-backed decisions from the tools you connect." |

## Current Code Implications

| File | Current Finding | Research Implication |
|------|-----------------|----------------------|
| `apps/web/src/app/(landing)/layout.tsx` | Metadata still says "Stop gathering context. Start shipping code." and "auto-generates everything you need to know." [VERIFIED: codebase grep] | Replace with the decision-tracking title and source-backed description. |
| `apps/web/src/components/landing/Hero.tsx` | H1 leads with generic productivity; subheadline mentions tools, decisions, and work mapping. [VERIFIED: codebase grep] | Replace H1/subheadline with Variant A; keep CTA shape. |
| `apps/web/src/components/landing/ProblemSection.tsx` | Problem is "context before coding" and includes the unsourced "2-6 hours" stat. [VERIFIED: codebase grep] | Reframe around disappearing decision rationale and remove/soften the stat. |
| `apps/web/src/components/landing/Features.tsx` | Existing cards already include "Knowledge graph" and "Decision tracking"; one card says "SOC 2 compliant architecture." [VERIFIED: codebase grep] | Elevate Decision Receipt / decision graph, keep graph as proof, soften or remove SOC 2 claim. |
| `apps/web/src/components/landing/HowItWorks.tsx` | Workflow ends with "Start coding immediately." [VERIFIED: codebase grep] | Change to source-backed decision graph across onboarding, planning, docs, tickets, and PRs rather than generic speed. |
| `apps/web/src/components/landing/ProductDemo.tsx` | Demo centers a context page generated from a Linear ticket. [VERIFIED: codebase grep] | Reframe as a Decision Receipt or decision graph demo; avoid making the product look ticket-only. |
| `apps/web/src/components/landing/RemotionPlayer.tsx` | Hero animation supports the first visual impression. [VERIFIED: codebase grep] | Retarget scenes toward scattered sources -> Decision Receipt -> decision graph, replacing "Pick a ticket" as the main story. |
| `apps/web/src/components/landing/Integrations.tsx` | Grid includes Linear, Slack, GitHub, Notion, Telegram, Jira, GitLab, and Fathom. [VERIFIED: codebase grep] | Avoid saying "9 integrations" unless Slack Huddles is intentionally counted separately. |
| `apps/web/src/components/landing/TrustBar.tsx` | Trust strip omits GitLab and Fathom while integrations grid includes them. [VERIFIED: codebase grep] | Align logos or avoid a numeric claim. |

## Standard Stack

No external packages should be added for this phase. Use existing Next metadata, React components, semantic HTML, and optional in-page JSON-LD if implementation time allows. [VERIFIED: codebase grep]

| Layer | Existing Tool | Version / Evidence | Purpose |
|-------|---------------|--------------------|---------|
| Web app | Next.js | `next` `^15.2.0` in `apps/web/package.json`. [VERIFIED: codebase grep] | Metadata, SSR, app routing, landing surface. |
| UI | React | `react` `^19.0.0` in `apps/web/package.json`. [VERIFIED: codebase grep] | Landing components and interactive Remotion embed. |
| Tests | Vitest | `vitest` `^4.0.18` and `apps/web/vitest.config.ts`. [VERIFIED: codebase grep] | Metadata/copy helper tests if added by planner. |

**Installation:** none.

## Package Legitimacy Audit

No new packages are recommended. Package legitimacy gate is not applicable.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SEO metadata | Custom head mutation | Next.js metadata in `apps/web/src/app/(landing)/layout.tsx` | Existing app already uses Next metadata. [VERIFIED: codebase grep] |
| Structured data | Custom nonstandard schema | JSON-LD with `Organization` and `SoftwareApplication` only for visible claims | Google structured data guidelines require page-visible content. [CITED: https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data] |
| GEO hack pages | Thin pages for every query variant | One high-quality homepage now; original decision-debt/use-case essays later | Google warns against pages created mainly for query variants and recycled commodity content. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide] |
| Trust/compliance positioning | Invented trust badges | Only verified security claims | Unsupported compliance claims create buyer and legal risk. [VERIFIED: phase context] |

## Common Pitfalls

### Pitfall 1: Competing With Glean On Glean's Category

**What goes wrong:** The page says "AI search across all company knowledge" and sounds like a small version of Glean, Notion AI, Rovo, Guru, or Slite. [CITED: https://www.glean.com/product/workplace-search-ai] [CITED: https://www.notion.com/en-gb/product/enterprise-search]

**How to avoid:** Make the object "decisions," not "answers" or "documents." Use "source-backed decision memory" and "missing why inside tickets and PRs."

### Pitfall 2: Turning "Decision Intelligence" Into The Hero Category

**What goes wrong:** Buyers expect decision modeling, analytics, simulation, BI, and autonomous decision execution because Gartner's category is broader than ContextOS current MVP. [CITED: https://www.gartner.com/reviews/market/decision-intelligence-platforms]

**How to avoid:** Use "decision memory" and "AI decision tracking" for launch. Mention "decision intelligence layer" only as lower-page explanation if needed.

### Pitfall 3: GEO Theater

**What goes wrong:** The team creates generic "what is X" pages, stuffs keywords, adds `llms.txt`, and calls it modern AI SEO. [ASSUMED]

**How to avoid:** Follow Google basics first: crawlable pages, helpful non-commodity content, coherent headings, visible evidence, and strong page experience. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide]

### Pitfall 4: Agent Washing

**What goes wrong:** The page claims autonomous task creation, doc updates, owner follow-up, or PR commenting before the action layer exists. [VERIFIED: phase context]

**How to avoid:** Keep action-layer copy in a "Coming next" section. Gartner specifically warns many vendors rebrand assistants/RPA/chatbots as agentic without real agent capability. [CITED: https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027]

### Pitfall 5: Trust Claims Without Evidence

**What goes wrong:** The page says "permission-aware," "private by default," "SOC 2 compliant architecture," or "zero retention" because competitors do. [CITED: https://www.getguru.com/solutions/agentic-knowledge-base] [CITED: https://www.notion.com/en-gb/product/enterprise-search]

**How to avoid:** Only claim source links and current product-visible trust properties unless security docs and implementation support stronger language.

## State Of The Art

| Shift | Evidence | Impact For ContextOS |
|-------|----------|----------------------|
| Enterprise AI spend is moving from experiments into purchased applications | Menlo reports enterprise generative AI spend reached $37B in 2025, with $19B in the application layer, and 76% of AI use cases purchased rather than built. [CITED: https://menlovc.com/perspective/2025-the-state-of-generative-ai-in-the-enterprise/] | A launch page can sell a bought product if it is specific, immediate, and workflow-native. |
| Product/engineering is a high-intent AI buyer segment | Menlo reports product + engineering has high startup share and coding became a major departmental AI category. [CITED: https://menlovc.com/perspective/2025-the-state-of-generative-ai-in-the-enterprise/] | Engineering-specific decision context is more credible than horizontal company-wide AI. |
| Enterprise value is moving above systems of record into systems of intelligence | a16z argues the next valuable enterprise layer pulls from systems of record, accumulates institutional context, and becomes the place users gain context and take action. [CITED: https://a16z.com/from-system-of-record-to-system-of-intelligence/] | ContextOS should present integrations as inputs to a decision-memory layer, not as a better dashboard over the same records. |
| Orchestration is becoming the enterprise AI framing | a16z's 2026 enterprise orchestration thesis frames the shift from isolated copilots to coordinated systems that plan, analyze, and execute across tools. [CITED: https://a16z.com/podcast/big-ideas-2026-the-enterprise-orchestration-layer/] | The action layer is directionally right, but launch copy must stay with current MVP: decision context before task/doc/PR automation. |
| Context engineering is replacing prompt tricks as the reliability bottleneck | Anthropic says agent reliability depends on curating the right context, not loading every available token; context is finite and must be high-signal. [CITED: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents] | "Source-backed decision context" is a stronger proof than "connect all your tools." Product visuals should show selected evidence, not huge data clouds. |
| Horizontal context platforms are productizing "system of context" and MCP access | Glean positions its system of context as an index for everything a company knows, and its developer/MCP surfaces bring docs, decisions, people, tickets, and code into coding agents. [CITED: https://www.glean.com/product/system-of-context] [CITED: https://developers.glean.com/] | ContextOS needs a narrower category: decision context for engineering work, not all-company context for every agent. |
| Work tools are bringing context directly into tickets, issues, and agents | Linear Code Intelligence says coordination gets expensive because context is scattered across code, specs, notes, issues, and decisions; it brings code context into Linear so teams can answer how features work, why regressions happened, and who has context. [CITED: https://linear.app/now/code-intelligence-for-linear-agent] | The homepage should emphasize where ContextOS shows up: tickets, PRs, onboarding, docs, and decision pages. |
| Incumbents frame AI around search, graph, and agents | Glean, Atlassian, Microsoft, and Notion all emphasize connected enterprise data, graph/context, and AI answers/actions. [CITED: https://www.glean.com/product/enterprise-graph] [CITED: https://www.atlassian.com/blog/company-news/rovo-team-26] [CITED: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-overview] | ContextOS must be narrower and more concrete. |
| AI search rewards source-worthy content, not only classic rank | Google says AI features use core Search systems plus RAG/query fan-out; a16z argues GEO shifts measurement toward reference rates. [CITED: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide] [CITED: https://a16z.com/geo-over-seo/] | Write dense, parseable, evidence-backed copy and later publish original decision-debt/use-case pages. |
| Agent claims face buyer skepticism | Gartner predicts many agentic AI projects will be canceled due to cost, unclear value, or risk controls, and warns about "agent washing." [CITED: https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027] | Future action-layer promises should stay explicitly future-tense. |
| GenAI buyers care about risk mitigation and process adoption | McKinsey reports organizations are ramping risk mitigation around inaccuracy, cybersecurity, and IP, and value capture depends on adoption/scaling practices. [CITED: https://www.mckinsey.com/~/media/mckinsey/business%20functions/quantumblack/our%20insights/the%20state%20of%20ai/2025/the-state-of-ai-how-organizations-are-rewiring-to-capture-value_final.pdf] | Trust copy should be concrete and operational, not decorative. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Company brain," "AI-native operating system," and "self-improving company" are perceived as generic AI slop by target buyers. | Differentiated Wording / Claims To Avoid | If wrong, the page may be more conservative than needed, but still clearer. |
| A2 | Hero Variant B is emotionally stronger but less category-clear than Variant A. | Exact Landing Copy Variants | If wrong, A/B testing may reveal stronger conversion for pain-led copy. |
| A3 | Hero Variant C needs a strong ticket/PR visual to work. | Exact Landing Copy Variants | If wrong, workflow-first copy may still perform without a visual. |
| A4 | "Never lose context again" and "all decisions are captured automatically" are overpromises. | Claims To Avoid | If product recall is exceptionally high, copy may be overly cautious, but legal/credibility risk is lower. |
| A5 | GEO hack pages and `llms.txt`-style rituals are low leverage for launch compared with source-worthy homepage content. | Common Pitfalls | If AI crawlers/platforms formalize new standards quickly, planner may need a later technical SEO task. |

## Open Questions

1. **Can ContextOS safely claim "permission-aware"?**
   - What we know: Competitors explicitly claim permission-aware answers/search, and buyers expect it in enterprise AI knowledge products. [CITED: https://www.getguru.com/solutions/agentic-knowledge-base] [CITED: https://www.notion.com/en-gb/product/enterprise-search]
   - What's unclear: Whether current ContextOS source linking and workspace permissions support this claim end to end.
   - Recommendation: Do not claim it in Phase 42 unless implementation is verified.

2. **Should the homepage mention Fathom as "meetings" or as a branded integration?**
   - What we know: The integration grid includes Fathom; the trust strip does not. [VERIFIED: codebase grep]
   - What's unclear: Whether Fathom is production-ready enough for first-viewport copy.
   - Recommendation: Use "meetings" in hero copy and include Fathom only where the integration grid already supports it.

3. **Should "product teams" be in the H1?**
   - What we know: Context locks engineering/product teams as the ICP, but the strongest workflow proof is tickets and PRs. [VERIFIED: phase context]
   - What's unclear: Whether buyers respond better to "engineering teams" or "engineering and product teams."
   - Recommendation: Use "engineering teams" in H1; mention product/engineering leads in lower-page buyer copy.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Node.js | Next/Vitest verification | yes | v26.0.0 [VERIFIED: local command] | Use project CI if local version causes issues. |
| npm | Web package scripts | yes | 11.12.1 [VERIFIED: local command] | Use existing lockfile/package manager pattern if planner detects one. |
| GSD SDK | Phase context discovery | yes | `/Users/dauletashikbayev/.local/bin/gsd-sdk` [VERIFIED: local command] | Manual file reads. |
| Context7 CLI | Library docs lookup | no | not found [VERIFIED: local command] | Official web docs were used for Google/OpenAI/schema guidance. |
| slopcheck | Package legitimacy | no | not found [VERIFIED: local command] | Not needed because no new packages are recommended. |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:** Context7 CLI; official docs were available via web sources.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest `^4.0.18` [VERIFIED: codebase grep] |
| Config file | `apps/web/vitest.config.ts` [VERIFIED: codebase grep] |
| Quick run command | `cd apps/web && npm run typecheck` |
| Landing test command | `cd apps/web && npx vitest run src/components/landing/__tests__ -t landing --run` |
| Full web command | `cd apps/web && npm run typecheck && npx vitest run` |

### Phase Requirements To Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| LAND-04 | Hero includes decision-memory positioning and source-backed decision copy | Unit/snapshot or DOM text test | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-copy.test.tsx -t hero` | No - Wave 0 |
| LAND-05 | Metadata title/description match decision-tracking recommendation | Unit import test or static AST/string test | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-metadata.test.ts -t metadata` | No - Wave 0 |
| LAND-06 | Current MVP capabilities are visible and no unsupported action-layer language is presented as live | Unit DOM text test | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-copy.test.tsx -t capabilities` | No - Wave 0 |
| LAND-07 | "Coming next" language wraps future actions and unsupported trust claims are absent | Unit DOM text test | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-copy.test.tsx -t claims` | No - Wave 0 |
| LAND-08 | Decision Receipt visual content is visible and ticket-only/productivity-first labels are removed | Unit DOM text test plus desktop/mobile visual check | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-copy.test.tsx -t decision-receipt` | No - Wave 0 |

### Wave 0 Gaps

- `apps/web/src/components/landing/__tests__/landing-copy.test.tsx` - asserts hero/problem/product/current/future copy.
- `apps/web/src/components/landing/__tests__/landing-metadata.test.ts` - asserts exported landing metadata.
- Visual verification should include desktop and mobile screenshots confirming Decision Receipt, source chips, status, and affected systems are visible without overlap.
- Optional helper: centralize landing copy constants if tests become brittle.

## Security Domain

Security enforcement is enabled by default because `.planning/config.json` does not disable it. [VERIFIED: local file read]

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no for public landing copy | Do not add auth behavior in this phase. |
| V3 Session Management | no for public landing copy | Do not change session handling. |
| V4 Access Control | yes for claims | Do not claim permission-aware access unless implementation is verified. |
| V5 Input Validation | yes for booking/links only | Existing CTA/link behavior; no new user input in recommended research. |
| V6 Cryptography | yes for trust claims | Do not claim encryption/compliance unless source-backed by product/security docs. |

## Sources

### Primary / High Confidence

- Google Search Central, "Optimizing your website for generative AI features on Google Search" - AI search, RAG, query fan-out, non-commodity content, crawlability: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Google Search Central, title link guidance: https://developers.google.com/search/docs/appearance/title-link
- Google Search Central, snippet/meta description guidance: https://developers.google.com/search/docs/appearance/snippet
- Google Search Central, structured data intro: https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data
- Schema.org `SoftwareApplication`: https://schema.org/SoftwareApplication
- OpenAI publisher/developer FAQ for ChatGPT search discovery and `OAI-SearchBot`: https://help.openai.com/en/articles/12627856-publishers-and-developers-faq
- Anthropic Engineering, "Effective context engineering for AI agents" - context engineering, finite context, high-signal retrieval, agent memory: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- a16z, "From System of Record to System of Intelligence" - enterprise value moving into reasoning/context/action layers above systems of record: https://a16z.com/from-system-of-record-to-system-of-intelligence/
- a16z, "Big Ideas 2026: The Enterprise Orchestration Layer" - coordinated multi-agent workflows across teams and tools: https://a16z.com/podcast/big-ideas-2026-the-enterprise-orchestration-layer/
- Glean workplace search: https://www.glean.com/product/workplace-search-ai
- Glean Enterprise Graph: https://www.glean.com/product/enterprise-graph
- Glean System of Context: https://www.glean.com/product/system-of-context
- Glean Developer Platform / MCP: https://developers.glean.com/
- Glean MCP for Engineering: https://docs.glean.com/user-guide/mcp/engineering
- Atlassian Rovo admin guide: https://www.atlassian.com/software/rovo/guides/admin-guide/how-rovo-helps-your-teams
- Atlassian Team '26 Rovo / Teamwork Graph announcement: https://www.atlassian.com/blog/company-news/rovo-team-26
- Linear Code Intelligence for Linear Agent: https://linear.app/now/code-intelligence-for-linear-agent
- Microsoft 365 Copilot Search FAQ: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-search-faq
- Microsoft 365 Copilot overview: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-overview
- Guru agentic knowledge base: https://www.getguru.com/solutions/agentic-knowledge-base
- Notion AI Enterprise Search: https://www.notion.com/en-gb/product/enterprise-search
- Slite Ask: https://slite.com/ask
- Gartner Peer Insights decision intelligence platforms definition: https://www.gartner.com/reviews/market/decision-intelligence-platforms
- Gartner agentic AI cancellation / agent washing warning: https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027

### Secondary / Medium Confidence

- Menlo Ventures 2025 State of Generative AI in the Enterprise - market/adoption sizing and application-layer trends: https://menlovc.com/perspective/2025-the-state-of-generative-ai-in-the-enterprise/
- McKinsey 2025 State of AI - risk mitigation and value-capture practices: https://www.mckinsey.com/~/media/mckinsey/business%20functions/quantumblack/our%20insights/the%20state%20of%20ai/2025/the-state-of-ai-how-organizations-are-rewiring-to-capture-value_final.pdf
- a16z GEO essay - operator/investor commentary on AI-search visibility and reference-rate framing: https://a16z.com/geo-over-seo/
- Cloudflare Content Signals Policy - AI crawler/content-use signaling: https://blog.cloudflare.com/content-signals-policy/
- Google AI Mode product update - query fan-out and AI Mode rollout: https://blog.google/products-and-platforms/products/search/google-search-ai-mode-update/

### Local Project Sources

- `.planning/phases/42-landing-positioning-and-seo-launch-rewrite/42-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `apps/web/src/app/(landing)/layout.tsx`
- `apps/web/src/components/landing/Hero.tsx`
- `apps/web/src/components/landing/ProblemSection.tsx`
- `apps/web/src/components/landing/Features.tsx`
- `apps/web/src/components/landing/HowItWorks.tsx`
- `apps/web/src/components/landing/Integrations.tsx`
- `apps/web/src/components/landing/TrustBar.tsx`
- `apps/web/package.json`
- `apps/web/vitest.config.ts`

## Metadata

**Confidence breakdown:**
- Category recommendation: HIGH - locked phase context, local product capability, and competitor scan all point toward decision memory over enterprise search.
- Competitor differentiation: HIGH - based on current official competitor pages and docs.
- SEO/GEO strategy: HIGH for Google/OpenAI fundamentals; MEDIUM for a16z/reference-rate tactics because GEO is still experimental.
- Keyword prioritization: MEDIUM - no paid search-volume or Search Console data was available.
- Trust/security copy: MEDIUM - research identifies risks, but implementation verification is required before stronger claims.

**Research date:** 2026-05-22
**Valid until:** 2026-06-21 for competitor messaging and GEO guidance; refresh sooner if Google/OpenAI crawler or AI search guidance changes.
