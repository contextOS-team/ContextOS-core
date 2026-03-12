# Phase 27: Dashboard Homepage Intelligence Widgets

## Origin

Design critique of current dashboard homepage (2026-03-09) using Interface Craft methodology. The homepage is passive and underutilizes ContextOS's cross-source data.

## Current State Problems

1. **Empty and passive** — Page shows recent contexts + integrations list, then vast empty space. Reads like a settings panel, not a homepage.
2. **Integrations dominate** — Take ~50% of visible content but deliver zero daily value after setup.
3. **No time awareness** — No concept of "what happened today" vs "this week." No signal about what changed since last visit.
4. **No cross-source intelligence** — ContextOS connects 5 tools but the homepage shows none of that aggregation value.
5. **Uniform visual treatment** — Context rows and integration rows look identical. Status dots are all teal (marks nothing when it marks everything).
6. **No focusing mechanism** — Every row has equal weight. Page doesn't answer "what do I need to know?"

## Proposed Sections (Priority Order)

### 1. "Needs Attention" Section (Structural)
Surface items requiring human action:
- Stale context pages
- Tickets with no linked context
- PRs awaiting review
- Unresolved Slack threads that were flagged

### 2. "Resurfaced" / Forgotten Context Widget (Structural — Killer Feature)
Ideas and decisions mentioned in Slack/meetings that never became tickets or action items.
Example: "@alex in #engineering (Tue): 'We should migrate to Redis' — no ticket created [Create]"

### 3. "This Week" Timeline Feed (Behavioral)
Decisions, PRs, contexts grouped by day:
- "Today: 2 contexts updated"
- "Yesterday: 1 decision captured, 3 PRs merged"
- "Monday: Sprint 14 started"

### 4. Sprint/Deadline Awareness (Behavioral)
Pull Linear cycle data: "Sprint 14 ends in 3 days — 4/12 issues complete"
Combined with Fathom meeting context for richer signals.

### 5. Demote Integrations (Visual)
Replace full integration list with minimal status dots footer row:
`● Linear  ● Slack  ● Fathom  ● GitHub  ○ Notion`
Detail belongs in Settings, not homepage.

## Proposed Layout

```
┌─────────────────────────────────────────────────┐
│  Good evening, Daulet              Sprint 14 ◉  │
│                                   3 days left   │
├─────────────────────────────────────────────────┤
│                                                 │
│  NEEDS ATTENTION (2)                            │
│  ┌─────────────────────────────────────────┐    │
│  │ CON-57 "Landing page" has 0 sources     │    │
│  │ PR #142 waiting for review (3 days)     │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  RESURFACED                                     │
│  ┌─────────────────────────────────────────┐    │
│  │ @alex in #engineering (Tue): "We should │    │
│  │ migrate caching to Redis" — no ticket   │    │
│  │ created                          [Create]│   │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  THIS WEEK                                      │
│  ┌─────────────────────────────────────────┐    │
│  │ Today     2 contexts updated            │    │
│  │ Yesterday 1 decision captured, 3 PRs    │    │
│  │ Monday    Sprint 14 started             │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  RECENT CONTEXT                     View all    │
│  ┌─────────────────────────────────────────┐    │
│  │ (existing context list, condensed)      │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ● Linear  ● Slack  ● Fathom  ● GitHub  ○ Notion│
└─────────────────────────────────────────────────┘
```

## Data Sources Available

All proposed widgets leverage existing data models:
- `activity_events` — sync events, context generation, connections
- `context_pages` — status, sources count, staleness
- `linear_tickets` — sprint/cycle data, assignees, due dates
- `slack_messages` — threads, decisions, unresolved items
- `github_pull_requests` — review status, merge state, age
- `fathom_recordings` — meeting notes, action items
- `embeddings` — semantic search for cross-source correlation

## Backend Requirements

Will need new API endpoints:
- `GET /api/dashboard/attention` — items needing action
- `GET /api/dashboard/resurfaced` — forgotten context candidates (AI-powered)
- `GET /api/dashboard/weekly-summary` — grouped activity by day
- `GET /api/dashboard/sprint` — current Linear cycle status

## Industry Benchmarks

Linear: shows assigned issues + team activity on home.
Notion: shows recent pages + suggested content.
Vercel: shows active deployments + project health.
ContextOS should exceed these by showing cross-source intelligence — the unique value prop.
