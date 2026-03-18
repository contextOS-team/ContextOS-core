---
phase: 27-dashboard-homepage-intelligence-widgets
verified: 2026-03-15T18:10:00Z
status: human_needed
score: 9/9 must-haves verified
re_verification: false
human_verification:
  - test: "Load the dashboard homepage and confirm the greeting + SprintBadge display together in the header row"
    expected: "Top row shows greeting text on the left and sprint cycle info (name, progress fraction, days remaining) on the right when Linear is connected"
    why_human: "Sprint badge renders null when no Linear cycle; visual layout requires a live session with an active Linear cycle to confirm header composition"
  - test: "Connect a Linear workspace with an active sprint, then load dashboard"
    expected: "SprintBadge shows cycle name, completed/total fraction in teal mono font, and days-remaining text"
    why_human: "Sprint endpoint queries external Linear GraphQL API; cannot verify rendered output without a live integration"
  - test: "Confirm Needs Attention widget shows count badge in header and links navigate correctly"
    expected: "Section label reads 'Needs Attention (N)' where N matches list length; clicking a stale-context row navigates to /dashboard/context/{id}"
    why_human: "Navigation requires browser interaction; count badge correctness depends on live workspace data"
  - test: "Confirm Resurfaced widget displays user, channel, and relative timestamp attribution"
    expected: "Each item shows '@user in #channel (time ago)' line above quoted text with 'No ticket created' footer"
    why_human: "Requires Slack messages in workspace matching decision keyword heuristics"
  - test: "Confirm IntegrationDots footer shows correct dot colors and tooltip text"
    expected: "Connected integrations show emerald dot, error integrations show red dot, disconnected integrations show hollow bordered dot; hovering shows 'Name: status'"
    why_human: "Visual dot rendering and tooltip display require browser interaction"
  - test: "Navigate to dashboard with no attention items, no resurfaced items, and no weekly activity"
    expected: "NeedsAttention, Resurfaced, and ThisWeek sections are completely absent from the page (not shown as empty cards)"
    why_human: "Empty-widget null returns must be visually confirmed in a browser with a clean workspace"
---

# Phase 27: Dashboard Homepage Intelligence Widgets — Verification Report

**Phase Goal:** Transform the dashboard homepage from a passive settings-like panel into an intelligence hub with five widget sections that answer "what do I need to know?" — Needs Attention (stale contexts, open PRs/MRs), Resurfaced (forgotten Slack decisions without ticket follow-through), This Week (daily activity timeline), Sprint Badge (Linear cycle progress), and Integration Dots (compact status indicators).
**Verified:** 2026-03-15T18:10:00Z
**Status:** human_needed (all automated checks passed; 6 items need human/browser verification)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /api/dashboard/attention returns stale contexts and PRs awaiting review scoped to workspace | VERIFIED | `dashboard_attention.py` queries ContextPage (status=stale or sources=[]), GithubPullRequest (state=open, non-draft), GitlabMergeRequest (state=opened, non-draft) all filtered by workspace_id |
| 2 | GET /api/dashboard/weekly-summary returns activity/context/PR counts grouped by day for last 7 days | VERIFIED | `dashboard_summary.py` initializes 7 zero-filled days then fills from activity_events (raw SQL), ContextPage, GithubPullRequest, GitlabMergeRequest aggregations |
| 3 | GET /api/dashboard/sprint returns current Linear cycle progress with name, dates, and completion ratio | VERIFIED | `dashboard_sprint.py` checks WorkspaceIntegration for Linear, retrieves token via get_valid_access_token, queries LinearGraphQLClient with activeCycle GraphQL, returns soonest-ending team cycle |
| 4 | GET /api/dashboard/resurfaced returns Slack messages containing decision-like language with no linked ticket | VERIFIED | `dashboard_resurfaced.py` uses 15 ILIKE keyword patterns on SlackMessage.text, last 14 days, limit 5, returns type='resurfaced' items |
| 5 | Dashboard homepage shows greeting with sprint badge at top | VERIFIED | `page.tsx` lines 125-130: flex header row with greeting left, `<SprintBadge sprint={sprintData} />` right |
| 6 | Needs Attention section displays stale contexts and PRs awaiting review with count badge | VERIFIED | `needs-attention.tsx` renders "Needs Attention ({items.length})" section label; links stale_context/no_sources to `/dashboard/context/{id}`; returns null when empty |
| 7 | Resurfaced section shows forgotten Slack decisions with channel and user context | VERIFIED | `resurfaced.tsx` renders @user, #channel, relative time, quoted text, "No ticket created" footer; returns null when empty |
| 8 | This Week section groups activity by day using day label formatter | VERIFIED | `this-week.tsx` imports formatDayLabel from `../activity/formatters`, filters all-zero days, renders counts inline |
| 9 | Integrations are demoted to compact status dots at the bottom | VERIFIED | `integration-dots.tsx` renders 8 integrations as colored dot + name; page.tsx line 195 renders it conditionally below all widgets |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/routers/dashboard.py` | 4 GET endpoints with workspace auth | VERIFIED | 61 lines; 4 routes: /attention, /weekly-summary, /sprint, /resurfaced; all use Depends(get_current_user) and Depends(get_session) |
| `backend/src/services/dashboard_attention.py` | Stale contexts + open PRs/MRs aggregation | VERIFIED | 130 lines; exports get_attention_items; queries 3 tables, returns unified list with type field |
| `backend/src/services/dashboard_summary.py` | Weekly activity counts by day | VERIFIED | 123 lines; exports get_weekly_summary; raw SQL for activity_events, ORM for context/PR/MR tables |
| `backend/src/services/dashboard_sprint.py` | Linear active cycle via GraphQL | VERIFIED | 112 lines; exports get_active_sprint(session, workspace_id, user_id); uses get_valid_access_token and LinearGraphQLClient |
| `backend/src/services/dashboard_resurfaced.py` | Keyword-based forgotten context detection | VERIFIED | 90 lines; exports get_resurfaced_items; 15 DECISION_KEYWORDS, ILIKE conditions, 14-day window, limit 5 |
| `apps/web/src/app/dashboard/page.tsx` | Intelligence hub layout, min 80 lines | VERIFIED | 198 lines; Promise.allSettled for 7 sources; imports all 5 widgets; skeleton loading state; error banner with retry |
| `apps/web/src/app/dashboard/widgets/needs-attention.tsx` | Attention widget with navigation | VERIFIED | 77 lines; Link to /dashboard/context/{id} for context items; AlertCircle/GitPullRequest icons |
| `apps/web/src/app/dashboard/widgets/resurfaced.tsx` | Forgotten context with attribution | VERIFIED | 44 lines; @user in #channel formatting; formatRelativeTime; quoted text |
| `apps/web/src/app/dashboard/widgets/this-week.tsx` | Day-grouped weekly timeline | VERIFIED | 46 lines; imports formatDayLabel from activity/formatters; filters zero-count days |
| `apps/web/src/app/dashboard/widgets/sprint-badge.tsx` | Sprint progress with days remaining | VERIFIED | 32 lines; calculates daysRemaining from ends_at; teal font-mono for progress fraction |
| `apps/web/src/app/dashboard/widgets/integration-dots.tsx` | Compact integration status dots row | VERIFIED | 53 lines; 8 integrations; emerald/red/hollow dot states; title tooltip per dot |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/src/routers/dashboard.py` | `backend/src/services/dashboard_attention.py` | `from src.services.dashboard_attention import get_attention_items` | WIRED | Line 17 imports, line 33 calls |
| `backend/src/routers/dashboard.py` | `backend/src/services/dashboard_sprint.py` | `from src.services.dashboard_sprint import get_active_sprint` | WIRED | Line 19 imports, line 51 calls with user.user_id |
| `backend/src/main.py` | `backend/src/routers/dashboard.py` | `from src.routers.dashboard import router as dashboard_router` | WIRED | main.py line 31 imports, line 179 app.include_router |
| `apps/web/src/app/dashboard/page.tsx` | `apps/web/src/lib/api.ts` | apiFetch calls for all 4 dashboard endpoints | WIRED | page.tsx imports getDashboardAttention, getDashboardResurfaced, getDashboardWeeklySummary, getDashboardSprint; api.ts lines 662/666/670/674 call apiFetch with correct paths |
| `apps/web/src/app/dashboard/widgets/needs-attention.tsx` | `/dashboard/context/{id}` | Link navigation for stale_context and no_sources items | WIRED | Line 22: template literal `/dashboard/context/${item.id}` inside Next.js Link |
| `apps/web/src/app/dashboard/widgets/this-week.tsx` | `apps/web/src/app/dashboard/activity/formatters.ts` | `import { formatDayLabel } from '../activity/formatters'` | WIRED | Line 2 import; formatDayLabel used at line 35 |

---

### Requirements Coverage

The requirement IDs declared in the PLAN frontmatter (WIDGET-01 through WIDGET-05, API-01 through API-04) do NOT exist as formal entries in `.planning/REQUIREMENTS.md`. REQUIREMENTS.md uses a different ID namespace (DS-*, NAV-*, ONB-*, HOME-*, FEED-*, ACT-*, SET-*, AUTH-*). Phase 27 plan IDs are phase-local identifiers, not REQUIREMENTS.md IDs.

The closest formal requirement is **HOME-01**: "Dashboard home page shows a summary view with recent context pages, integration health, and activity preview." Phase 27 substantially exceeds HOME-01 by adding intelligence widgets (attention, resurfaced, this-week, sprint) on top of the existing context feed and integration status.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| API-01 (local) | 27-01 | GET /api/dashboard/attention endpoint | SATISFIED | dashboard_attention.py + router endpoint verified |
| API-02 (local) | 27-01 | GET /api/dashboard/weekly-summary endpoint | SATISFIED | dashboard_summary.py + router endpoint verified |
| API-03 (local) | 27-01 | GET /api/dashboard/sprint endpoint | SATISFIED | dashboard_sprint.py + router endpoint verified |
| API-04 (local) | 27-01 | GET /api/dashboard/resurfaced endpoint | SATISFIED | dashboard_resurfaced.py + router endpoint verified |
| WIDGET-01 (local) | 27-01, 27-02 | Needs Attention widget | SATISFIED | needs-attention.tsx renders attention items from API-01 |
| WIDGET-02 (local) | 27-01, 27-02 | Resurfaced widget | SATISFIED | resurfaced.tsx renders resurfaced items from API-04 |
| WIDGET-03 (local) | 27-01, 27-02 | This Week timeline widget | SATISFIED | this-week.tsx renders weekly summary from API-02 |
| WIDGET-04 (local) | 27-01, 27-02 | Sprint Badge widget | SATISFIED | sprint-badge.tsx renders sprint data from API-03 |
| WIDGET-05 (local) | 27-02 | Integration Dots widget | SATISFIED | integration-dots.tsx renders compact dots via getIntegrationStatus |
| HOME-01 (formal) | (implicit) | Dashboard shows summary with context, integration health, activity | SATISFIED | page.tsx includes Recent Context, IntegrationDots, ThisWeek sections |

**Note on orphaned requirements:** REQUIREMENTS.md does not contain any entries explicitly mapped to Phase 27 beyond the implicitly satisfied HOME-01. No ORPHANED requirements detected.

**Note on ROADMAP checkbox:** The ROADMAP.md shows `- [ ] 27-02-PLAN.md` (unchecked) despite the plan being fully implemented and committed at commit `ae83ce5` and `8587e53`. This is a documentation inconsistency — the checkbox was not updated after completion. The code is correct; only the ROADMAP checkbox needs updating.

---

### Anti-Patterns Found

| File | Pattern | Severity | Notes |
|------|---------|----------|-------|
| None detected | — | — | No TODO/FIXME/PLACEHOLDER comments, no stub return patterns, no empty handlers found across all 11 modified/created files |

The `return null` patterns in all 4 widget components (needs-attention, resurfaced, this-week, sprint-badge) are intentional design — empty widgets hide themselves rather than showing empty cards. This matches the phase plan specification.

---

### Human Verification Required

#### 1. Sprint Badge in Header Row

**Test:** Connect a Linear workspace with an active sprint cycle, then load `/dashboard`
**Expected:** Header row shows greeting on the left and cycle name + "N/M" fraction in teal monospace + days-remaining on the right
**Why human:** Sprint endpoint calls external Linear GraphQL API; badge renders `null` with no active cycle, making programmatic verification impossible without a live Linear integration

#### 2. Needs Attention Widget Navigation

**Test:** Create a stale context page, load `/dashboard`, click the item in the Needs Attention section
**Expected:** Browser navigates to `/dashboard/context/{id}` for that context page
**Why human:** Link navigation requires a browser session; count badge ("Needs Attention (3)") requires live data to confirm

#### 3. Resurfaced Widget Attribution Display

**Test:** Add Slack messages containing "we should" or "action item" to a workspace (within last 14 days), then load `/dashboard`
**Expected:** Resurfaced section appears with "@user in #channel (2 days ago)" attribution line, quoted message text, and "No ticket created" footer
**Why human:** Requires Slack messages matching keyword heuristics in a live workspace

#### 4. Integration Dots Colors and Tooltips

**Test:** On the dashboard with mixed integration states (some connected, some not), hover each dot
**Expected:** Connected = filled emerald dot; error = filled red dot; disconnected = hollow bordered dot; tooltip text matches "Name: status"
**Why human:** Visual rendering of dot states and title attribute tooltip display require browser interaction

#### 5. Empty Widget Hide Behavior

**Test:** Load dashboard with a workspace that has no stale contexts, no open PRs, no resurfaced Slack messages, and no weekly activity
**Expected:** NeedsAttention, Resurfaced, and ThisWeek sections are completely absent from the rendered page — not shown as empty cards
**Why human:** Requires a clean workspace state to verify null returns result in visual absence

#### 6. Promise.allSettled Resilience

**Test:** Temporarily break one dashboard API endpoint (e.g., set Linear integration to invalid state), then load dashboard
**Expected:** The sprint badge is absent but all other widgets still render; no full-page error; the error banner only shows if the overall catch block fires
**Why human:** Failure isolation across independent widget loads can only be fully confirmed through browser DevTools with simulated API failures

---

### Gaps Summary

No functional gaps identified. All 9 observable truths verified against the codebase. All 11 artifacts exist, are substantive (not stubs), and are wired into the application. All 6 key links verified. No blocking anti-patterns detected. All 4 backend commits verified in git history.

One administrative gap: ROADMAP.md line 273 shows `- [ ] 27-02-PLAN.md` (unchecked) despite the plan being fully implemented across commits `ae83ce5` and `8587e53`. This does not affect functionality but should be corrected to `[x]` to keep the ROADMAP accurate.

---

_Verified: 2026-03-15T18:10:00Z_
_Verifier: Claude (gsd-verifier)_
