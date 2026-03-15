# Phase 27: Dashboard Homepage Intelligence Widgets - Research

**Researched:** 2026-03-15
**Domain:** Dashboard UI widgets, backend API aggregation endpoints, cross-source intelligence
**Confidence:** HIGH

## Summary

Phase 27 transforms the passive ContextOS dashboard homepage into an intelligence hub. The current homepage (`apps/web/src/app/dashboard/page.tsx`) is a 386-line client component that shows a greeting, 5 recent context pages, and a full 8-integration status list -- essentially a settings panel, not a daily driver. The CONTEXT.md prescribes 5 specific interventions: "Needs Attention" alerts, "Resurfaced" forgotten context widget, "This Week" timeline feed, Sprint/Deadline awareness, and integration demotion to minimal status dots.

The backend has all the raw data tables needed (`context_pages`, `linear_tickets`, `slack_messages`, `github_pull_requests`, `gitlab_merge_requests`, `meeting_transcripts`, `activity_events`), but no aggregation endpoints exist. Four new API endpoints are needed under `/api/dashboard/`. The "Resurfaced" widget requires AI (Gemini via the existing `LLMClient`) to identify Slack messages containing decisions/ideas that never became tickets. Sprint/cycle data is NOT currently synced from Linear -- the `linear_tickets` table has no cycle columns and the ISSUES_QUERY GraphQL does not request cycle fields. This is the largest data gap.

**Primary recommendation:** Build backend aggregation endpoints first (pure SQL queries against existing tables), then the frontend widgets. The "Resurfaced" AI widget should be Plan 3 since it is the most complex and the most differentiating feature. Sprint awareness requires a new Linear GraphQL query for active cycles, which can be a lightweight addition to the existing `linear_sync.py` service.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Five specific widget sections in priority order: (1) Needs Attention, (2) Resurfaced/Forgotten Context, (3) This Week Timeline, (4) Sprint/Deadline Awareness, (5) Demote Integrations
- Exact layout prescribed in ASCII wireframe (greeting + sprint badge at top, then sections in order, integrations demoted to status dots footer)
- Four new backend API endpoints: `GET /api/dashboard/attention`, `GET /api/dashboard/resurfaced`, `GET /api/dashboard/weekly-summary`, `GET /api/dashboard/sprint`
- Data sources: activity_events, context_pages, linear_tickets, slack_messages, github_pull_requests, fathom_recordings, embeddings
- Cross-source intelligence is the differentiating value

### Claude's Discretion
- Implementation approach for "Resurfaced" AI detection (LLM-based vs heuristic vs hybrid)
- Exact staleness thresholds for "Needs Attention"
- Caching strategy for aggregation endpoints
- Component decomposition and file structure

### Deferred Ideas (OUT OF SCOPE)
- None explicitly listed
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WIDGET-01 | "Needs Attention" section surfaces items requiring human action (stale contexts, unlinked tickets, PRs awaiting review) | SQL aggregation across context_pages, github_pull_requests, gitlab_merge_requests; staleness via updated_at comparison |
| WIDGET-02 | "Resurfaced" widget shows forgotten ideas/decisions from Slack/meetings with no ticket | AI-powered: LLM classifies slack_messages for decision-like content, cross-references with linear_tickets |
| WIDGET-03 | "This Week" timeline feed groups decisions/PRs/contexts by day | Reuses activity_events table + augments with context_pages/PR counts per day |
| WIDGET-04 | Sprint/Deadline awareness shows current Linear cycle progress | Requires new Linear GraphQL query for active cycles (not currently synced) |
| WIDGET-05 | Integrations demoted to minimal status dots footer | Refactor existing integration list to compact dot row |
| API-01 | GET /api/dashboard/attention endpoint | New FastAPI router with workspace-scoped SQL queries |
| API-02 | GET /api/dashboard/resurfaced endpoint | New endpoint using LLM or semantic search for cross-source detection |
| API-03 | GET /api/dashboard/weekly-summary endpoint | SQL GROUP BY date on activity_events + context_pages + PRs |
| API-04 | GET /api/dashboard/sprint endpoint | New Linear GraphQL query for activeCycle |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 15.2+ | Frontend framework | Already in use, App Router with Turbopack |
| FastAPI | current | Backend API | Already in use for all routers |
| Supabase JS | 2.49+ | Client-side data fetching, Realtime | Already in use for auth + direct queries |
| SQLModel + SQLAlchemy | current | Backend ORM | Already in use for all models |
| Tailwind CSS | 4.0 | Styling | Already in use with OKLCH dark mode tokens |
| Lucide React | 0.469+ | Icons | Already in use throughout dashboard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Google Gemini (genai) | current | AI classification for Resurfaced widget | Only for the Resurfaced endpoint |
| sonner | 1.7+ | Toast notifications | Error states on widget load failures |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LLM for Resurfaced | Pure embedding similarity | Cheaper but less accurate at identifying actionable decisions |
| Direct SQL queries | Supabase RPC functions | RPC is cleaner but adds migration complexity for little gain |

**Installation:**
```bash
# No new packages needed -- all dependencies already installed
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/
  routers/
    dashboard.py            # NEW: /api/dashboard/* endpoints
  services/
    dashboard_attention.py  # NEW: attention items aggregation
    dashboard_resurfaced.py # NEW: AI-powered forgotten context detection
    dashboard_summary.py    # NEW: weekly summary aggregation
    linear_graphql.py       # MODIFY: add activeCycle query

apps/web/src/app/dashboard/
  page.tsx                  # REWRITE: new intelligence layout
  widgets/
    needs-attention.tsx     # NEW: attention items widget
    resurfaced.tsx          # NEW: forgotten context widget
    this-week.tsx           # NEW: weekly timeline widget
    sprint-badge.tsx        # NEW: sprint progress indicator
    integration-dots.tsx    # NEW: compact integration status
```

### Pattern 1: Backend Aggregation Endpoints
**What:** Each widget has a dedicated API endpoint that returns pre-aggregated data. The frontend makes parallel fetches on page load.
**When to use:** Every widget that needs cross-table queries.
**Example:**
```python
# Source: Existing router pattern from backend/src/routers/integrations.py
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/attention")
async def get_attention_items(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Items requiring user attention."""
    # Query context_pages with 0 sources or stale status
    # Query github_pull_requests awaiting review
    # Return unified attention items list
    ...
```

### Pattern 2: Frontend Parallel Widget Loading
**What:** Each widget loads independently with its own loading skeleton and error boundary. Uses Promise.all on initial page load but each widget degrades gracefully.
**When to use:** Dashboard page with multiple independent data sources.
**Example:**
```typescript
// Source: Existing dashboard page.tsx pattern
const [attentionRes, weeklyRes, sprintRes] = await Promise.allSettled([
  apiFetch('/api/dashboard/attention'),
  apiFetch('/api/dashboard/weekly-summary'),
  apiFetch('/api/dashboard/sprint'),
])
```

### Pattern 3: Activity Events Reuse
**What:** The "This Week" timeline reuses the existing `activity_events` table and `groupEventsByDay` formatter from the activity page.
**When to use:** Weekly summary widget.
**Example:**
```typescript
// Reuse from apps/web/src/app/dashboard/activity/formatters.ts
import { groupEventsByDay, formatDayLabel } from '../activity/formatters'
```

### Anti-Patterns to Avoid
- **Full integration list on homepage:** Current pattern takes 50% of space. Demote to status dots.
- **Single monolithic page component:** Current page.tsx is 386 lines. Split into widget components.
- **Client-side aggregation:** Do not query raw tables and aggregate in the browser. Backend endpoints should return pre-computed data.
- **Blocking widget loads:** One slow widget should not prevent the entire page from rendering. Use independent loading states.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date grouping | Custom day-bucket logic | Existing `groupEventsByDay` from activity formatters | Already handles TODAY/YESTERDAY/weekday/date formatting |
| Relative time display | Custom time formatter | Existing `formatRelativeTime` from lib/utils | Consistent with rest of dashboard |
| Integration status fetching | Custom status checker | Existing `getIntegrationStatus()` from lib/api | Already returns all 8 providers in one call |
| Auth + workspace scoping | Custom auth logic | Existing `get_current_user` dependency | Standard FastAPI dependency injection pattern |
| Linear GraphQL with retry | Custom HTTP client | Existing `LinearGraphQLClient` with backoff | Handles rate limits and retries |

**Key insight:** Most infrastructure (auth, data models, formatters, API client) already exists. This phase is primarily about aggregation queries and UI composition.

## Common Pitfalls

### Pitfall 1: Sprint/Cycle Data Not Available
**What goes wrong:** The Linear sync does NOT currently fetch cycle/sprint data. There are no cycle columns in `linear_tickets` and no cycle-related GraphQL queries.
**Why it happens:** Original sync focused on tickets only.
**How to avoid:** Add a lightweight `activeCycle` GraphQL query to the sprint endpoint. Do NOT store cycle data in a table -- query it live from Linear API. Linear's API returns cycle data quickly.
**Warning signs:** Empty sprint widget with no error message.

### Pitfall 2: N+1 Queries in Attention Endpoint
**What goes wrong:** Checking each context page's sources count, each PR's review status, etc. individually creates many queries.
**Why it happens:** Iterating through items and checking related data one by one.
**How to avoid:** Use aggregate SQL queries with JOINs. Single query for stale contexts (WHERE sources = '[]' OR status = 'stale'), single query for PRs awaiting review.
**Warning signs:** Dashboard load time exceeding 2 seconds.

### Pitfall 3: Resurfaced Widget Overwhelming Users
**What goes wrong:** Showing too many "forgotten" items makes the widget feel noisy rather than intelligent.
**Why it happens:** Not limiting results or not filtering quality.
**How to avoid:** Limit to 3-5 items max. Use confidence threshold for AI classification. Prioritize by recency.
**Warning signs:** User scrolls past the widget every time.

### Pitfall 4: Stale Closure in Widget State
**What goes wrong:** Widget state updates from Supabase Realtime subscriptions reference stale state variables.
**Why it happens:** React closures capture state at subscription time, not at callback execution time.
**How to avoid:** Use useRef for callback storage (same pattern as activity timeline's `isScrolledToTopRef`).
**Warning signs:** Widget shows outdated data until manual refresh.

### Pitfall 5: Integration Dots Missing Dynamic Status
**What goes wrong:** Compact integration dots lose the connection status information.
**Why it happens:** Over-simplifying the UI removes useful signals.
**How to avoid:** Use three states for dots: filled green (connected), filled red (error), hollow (disconnected). Tooltip on hover shows details.
**Warning signs:** Users navigate to Settings to check integration status.

## Code Examples

### Backend: Attention Items Query
```python
# Stale context pages (no sources or stale status)
stale_contexts = await session.exec(
    select(ContextPage.id, ContextPage.title, ContextPage.ticket_identifier, ContextPage.status)
    .where(ContextPage.workspace_id == user.workspace_id)
    .where(ContextPage.deleted_at.is_(None))
    .where(
        or_(
            ContextPage.status == "stale",
            ContextPage.sources == sa_text("'[]'::jsonb"),
        )
    )
    .order_by(ContextPage.updated_at.desc())
    .limit(10)
)

# PRs awaiting review (open, not draft, not authored by current user)
open_prs = await session.exec(
    select(GithubPullRequest)
    .where(GithubPullRequest.workspace_id == user.workspace_id)
    .where(GithubPullRequest.state == "open")
    .where(GithubPullRequest.is_draft == False)
    .order_by(GithubPullRequest.github_created_at.asc())
    .limit(5)
)
```

### Backend: Linear Active Cycle Query
```python
ACTIVE_CYCLE_QUERY = """
query {
    teams {
        nodes {
            id
            name
            activeCycle {
                id
                name
                number
                startsAt
                endsAt
                completedScopeCount
                totalScopeCount
                progress
            }
        }
    }
}
"""
```

### Frontend: Widget Component Pattern
```typescript
// Each widget follows this pattern:
interface AttentionItem {
  type: 'stale_context' | 'pr_review' | 'no_sources'
  id: string
  title: string
  detail: string
  link: string
  age?: string
}

function NeedsAttentionWidget({ items }: { items: AttentionItem[] }) {
  if (items.length === 0) return null // Don't show empty sections

  return (
    <div>
      <h3 className="section-label mb-3">
        Needs Attention ({items.length})
      </h3>
      <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
        {items.map(item => (
          <Link key={item.id} href={item.link} className="...">
            ...
          </Link>
        ))}
      </div>
    </div>
  )
}
```

### Frontend: Compact Integration Dots
```typescript
function IntegrationDots({ statuses }: { statuses: IntegrationStatusResponse }) {
  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      {INTEGRATIONS.map(i => {
        const s = statuses[i.key]
        const isConnected = s.status === 'connected'
        const isError = s.status === 'error'
        return (
          <span key={i.key} className="flex items-center gap-1" title={`${i.name}: ${s.status}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${
              isConnected ? 'bg-emerald-500' : isError ? 'bg-red-500' : 'border border-muted-foreground/30'
            }`} />
            {i.name}
          </span>
        )
      })}
    </div>
  )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full integration list on homepage | Compact status dots | Phase 27 | Frees 50% of homepage space |
| Passive context list only | Active attention + AI resurfacing | Phase 27 | Homepage answers "what do I need to know?" |
| No sprint awareness | Linear cycle progress badge | Phase 27 | Engineers see sprint context without leaving dashboard |

**Key data gaps to address:**
- Linear cycle data: Not synced, needs live API query
- "Resurfaced" detection: No existing classification of Slack messages as actionable vs informational
- Weekly summary: activity_events table exists but no day-grouped aggregation endpoint

## Open Questions

1. **Resurfaced widget: LLM vs heuristic approach**
   - What we know: Slack messages are stored with text content. Linear tickets exist with titles.
   - What's unclear: Whether simple text matching (keywords like "we should", "let's", "need to") is sufficient or if LLM classification is needed.
   - Recommendation: Start with heuristic keyword matching for v1, add LLM classification as enhancement. Heuristics are deterministic, fast, and free. The endpoint can be swapped to LLM later without frontend changes.

2. **Sprint badge: Multiple teams**
   - What we know: Linear workspaces can have multiple teams, each with their own active cycle.
   - What's unclear: Which team's cycle to show when workspace has multiple teams.
   - Recommendation: Show the first team's active cycle. If multiple teams have cycles, show the one ending soonest.

3. **Weekly summary: Enrichment beyond activity_events**
   - What we know: activity_events captures syncs, context generation, integration connections. PRs merged and decisions captured are not in activity_events.
   - What's unclear: Whether to extend activity_events with new event types or query PRs/contexts directly.
   - Recommendation: Query context_pages and github_pull_requests directly with date filtering. Do not add new event types to activity_events for display-only data.

## Sources

### Primary (HIGH confidence)
- `apps/web/src/app/dashboard/page.tsx` - Current homepage implementation (386 lines)
- `backend/src/models/*.py` - All data models (context_page, ticket, github, slack, meeting, integration)
- `backend/src/services/linear_graphql.py` - Linear GraphQL client pattern
- `backend/src/services/linear_sync.py` - ISSUES_QUERY confirming no cycle data
- `apps/web/src/app/dashboard/activity/` - Activity timeline patterns (formatters, types, realtime)
- `supabase/migrations/00012_onboarding_and_activity.sql` - activity_events schema
- `.planning/phases/27-dashboard-homepage-intelligence-widgets/27-CONTEXT.md` - User decisions and wireframe

### Secondary (MEDIUM confidence)
- Linear GraphQL API documentation - activeCycle field availability (verified field name from Linear API schema)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, no new dependencies
- Architecture: HIGH - Follows existing patterns (router, service, component decomposition)
- Pitfalls: HIGH - Based on direct code analysis of existing patterns
- Sprint/Cycle API: MEDIUM - Linear activeCycle field is standard but not yet used in codebase
- Resurfaced AI: MEDIUM - Heuristic approach is straightforward, LLM approach depends on prompt engineering

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable domain, existing codebase patterns)
