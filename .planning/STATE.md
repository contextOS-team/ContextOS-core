---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Dashboard & Onboarding
status: executing
stopped_at: Completed 31-02-PLAN.md
last_updated: "2026-03-15T10:20:06.269Z"
last_activity: 2026-03-12 -- Completed 28-01 (GitLab Code Indexing Backend)
progress:
  total_phases: 23
  completed_phases: 20
  total_plans: 57
  completed_plans: 55
  percent: 97
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-04)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** Phase 16 complete -- Auth Redesign + Schema Foundation (all 3 plans done)

## Current Position

Phase: 29 of 29 (Codebase Hardening)
Plan: 5 of 6
Status: Executing
Last activity: 2026-03-12 -- Completed 28-01 (GitLab Code Indexing Backend)

Progress: [██████████] 97%

## Performance Metrics

**Velocity:**
- Total plans completed: 16 (v1.0)
- Average duration: 4.2min
- Total execution time: ~1.1 hours

**By Phase (v1.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3 | 12min | 4min |
| 2. Linear Integration | 3 | 26min | 8.7min |
| 3. Slack/Meeting | 3 | 24min | 8min |
| 7. GitHub | 3 | 19min | 6.3min |
| 7.1 Tech Debt | 2 | 10min | 5min |
| 07.2 Bug Fixes | 3 | 9min | 3min |
| 08.1 Design Polish | 2 | 9min | 4.5min |
| 08.1.1 Notion | 3 | 12min | 4min |
| 10. Sync Engine | 3 | 18min | 6min |
| 12. Code Intel | 3 | 15min | 5min |
| 13. Landing Page | 1 | 7min | 7min |
| 14. PostHog | 1 | 2min | 2min |

**Recent Trend:**
- Last 5 plans: 12-03 (6min), 13-01 (7min), 14-01 (2min)
- Trend: Stable (3-7min per plan)
| Phase 15 P02 | 2min | 2 tasks | 2 files |
| Phase 15 P01 | 3min | 2 tasks | 4 files |
| Phase 15 P03 | 3min | 3 tasks | 5 files |
| Phase 16 P01 | 1min | 1 task | 1 file |
| Phase 16 P02 | 2min | 2 tasks | 3 files |
| Phase 16 P03 | 2min | 2 tasks | 6 files |
| Phase 19 P01 | 2min | 2 tasks | 3 files |
| Phase 18 P02 | 4min | 1 task | 3 files |
| Phase 19 P02 | 2min | 1 tasks | 1 files |
| Phase 19 P03 | 2min | 2 tasks | 2 files |
| Phase 17 P01 | 6min | 2 tasks | 9 files |
| Phase 17 P02 | 5min | 2 tasks | 2 files |
| Phase 20 P01 | 2min | 2 tasks | 5 files |
| Phase 20 P02 | 3min | 2 tasks | 3 files |
| Phase 22 P01 | 3min | 2 tasks | 5 files |
| Phase 23 P01 | 3min | 2 tasks | 9 files |
| Phase 23 P02 | 10min | 2 tasks | 9 files |
| Phase 21 P01 | 3min | 2 tasks | 6 files |
| Phase 24 P01 | 2min | 2 tasks | 4 files |
| Phase 24 P02 | 5min | 2 tasks | 8 files |
| Phase 24 P03 | 2min | 2 tasks | 4 files |
| Phase 25 P01 | 3min | 2 tasks | 4 files |
| Phase 25 P02 | 5min | 2 tasks | 6 files |
| Phase 25 P03 | 3min | 2 tasks | 5 files |
| Phase 26 P01 | 3min | 2 tasks | 7 files |
| Phase 26 P02 | 4min | 2 tasks | 7 files |
| Phase 26 P03 | 4min | 2 tasks | 4 files |
| Phase 29 P01 | 5min | 2 tasks | 11 files |
| Phase 29 P03 | 3min | 2 tasks | 8 files |
| Phase 29 P02 | 8min | 2 tasks | 10 files |
| Phase 29 P04 | 5min | 2 tasks | 3 files |
| Phase 29 P06 | 3min | 2 tasks | 4 files |
| Phase 29 P05 | 4min | 2 tasks | 3 files |
| Phase 28 P02 | 2min | 2 tasks | 3 files |
| Phase 30 P01 | 4min | 2 tasks | 4 files |
| Phase 30 P02 | 4min | 2 tasks | 4 files |
| Phase 31 P03 | 2min | 1 tasks | 1 files |
| Phase 31 P01 | 2min | 1 tasks | 1 files |
| Phase 31 P02 | 2min | 1 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.1 Roadmap]: 6 phases derived from 36 requirements, phases 15-20
- [v1.1 Roadmap]: Phase 15 (tokens) must complete before any UI work -- wrong tokens mean rework on every component
- [v1.1 Roadmap]: Phase 16 splits onboarding into infra (schema + gate) and wizard (Phase 17) -- schema unblocks activity timeline too
- [v1.1 Roadmap]: Phases 17, 18, 19 can parallelize after Phase 16 schema exists
- [v1.1 Roadmap]: Phase 20 (settings) independent after Phase 15, lowest priority
- [Phase 13]: CSS scoped under .landing-theme to avoid dashboard pollution -- v1.1 must scope dashboard under .dark without collision
- [Phase 15]: Teal underline only for active nav state (no bg-muted) -- clean Vercel-style nav
- [Phase 15]: Settings and Sign out in avatar dropdown to declutter nav bar
- [Phase 15]: Used :where(.dark, .dark *) for @custom-variant dark mode -- zero specificity targeting
- [Phase 15]: CSS-only spring curve (cubic-bezier 0.34, 1.56, 0.64, 1) over Framer Motion -- zero bundle cost
- [Phase 15]: Dashboard grain at 0.008 opacity (vs landing 0.025) for daily-use eye comfort
- [Phase 15]: Skeleton component uses skeleton-shimmer CSS class (not animate-pulse) for premium shimmer-sweep
- [Phase 15]: Activity placeholder is static server component -- Phase 18 replaces with dynamic client component
- [Phase 16]: Extended handle_new_user trigger (CREATE OR REPLACE) rather than separate trigger -- keeps signup logic atomic
- [Phase 16]: NULL onboarding row = legacy user (treated as completed) -- no backfill needed
- [Phase 16]: pg_cron wrapped in exception handler for local dev compatibility
- [Phase 16]: Split auth layout: bg-background (L1) brand panel + bg-elevated (L3) form panel for visual depth
- [Phase 16]: Card wrappers removed from auth forms -- forms render directly on elevated panel surface
- [Phase 16]: NULL onboarding row in dashboard gate = legacy user, passes through without redirect
- [Phase 16]: Middleware unchanged for /onboarding -- existing path logic handles it correctly
- [Phase 16]: Suspense boundary wraps useSearchParams in onboarding page for Next.js static rendering
- [Phase 19]: Migration numbered 00014 (not 00013) -- adapted to existing migration sequence from Phase 18
- [Phase 19]: Ref-based callback pattern in useContextPagesRealtime: store callbacks in useRef, read from refs in channel callback, empty deps array
- [Phase 18]: Single supabase client ref shared for Realtime and pagination -- avoids duplicate connections
- [Phase 18]: Scroll position checked via useRef in Realtime callback to avoid stale closure
- [Phase 18]: Auto-flush buffer on manual scroll-to-top via scroll event listener on main
- [Phase 18]: CSS-only event-enter and banner-slide-in animations (no Framer Motion)
- [Phase 19]: Inline useDebounce hook in feed page rather than separate file -- single consumer keeps it self-contained
- [Phase 19]: Prose classes on wrapper div, not react-markdown (v10 has no className prop)
- [Phase 17]: Wizard reads current_step from DB on mount to handle OAuth return detection
- [Phase 17]: Fathom uses inline API key form within sources grid rather than separate dialog
- [Phase 17]: Back button positioned below step content for minimal visual interference
- [Phase 17]: Three-state StepContext (generating/ready/completing) keeps transitions explicit and user-driven
- [Phase 17]: Mock fallback uses realistic ENG-42 ticket data so users always see ContextOS value proposition
- [Phase 20]: ApiKey uses SQLModel directly (not BaseModel) -- no updated_at/deleted_at needed for keys
- [Phase 20]: RLS policies use get_user_workspace_ids() for SELECT, INSERT, UPDATE on api_keys
- [Phase 20]: Full API key shown once at creation, only prefix stored for display
- [Phase 20]: AlertDialog follows exact dropdown-menu.tsx pattern (data-slot, cn() merging, functional components)
- [Phase 20]: Settings page is single scrollable layout (not tabbed) -- 4 sections vertical
- [Phase 20]: Created API key shown inline with teal box and copy-once warning (not modal)
- [Phase 22]: fetch+ReadableStream over EventSource for SSE -- EventSource cannot send Authorization headers
- [Phase 22]: GenerationProgress is purely presentational -- state management deferred to Plan 03 parent
- [Phase 22]: Active step uses CSS step-pulse animation (not JS interval) for teal pulsing
- [Phase 22]: Dedicated session inside SSE generator (not Depends) to avoid FastAPI closing session before stream ends
- [Phase 22]: SSE concurrent generation returns error event (not HTTP 409) for uniform client handling
- [Phase 23]: Minimal SVG icons (hash, brackets, diamond) instead of full brand logos for Remotion self-containment
- [Phase 23]: All Remotion styles inline only -- iframe-like context without external stylesheets
- [Phase 23]: next/dynamic with ssr:false for Remotion Player -- avoids window-is-not-defined SSR errors
- [Phase 23]: Real brand SVG logos (Slack, GitHub, Linear) chosen over minimal placeholders after visual review
- [Phase 21]: Native button elements for social OAuth (not shadcn Button) for full style control
- [Phase 21]: Auth pages follow social -> divider -> form -> CTA layout order
- [Phase 21]: Focus ring uses oklch primary token (0.75 0.18 170) with 0.4 alpha ring + 0.15 glow
- [Phase 24]: GitLab tables mirror GitHub table pattern exactly for consistency
- [Phase 24]: GitLab MR uses project_id + project_path instead of single repo_full_name
- [Phase 24]: GitLab review states: approved/commented/note (notes, not formal reviews)
- [Phase 24]: Standard OAuth2 authorization code flow for GitLab (not App JWT like GitHub)
- [Phase 24]: X-Gitlab-Token header comparison for webhook verification (not HMAC body signature)
- [Phase 24]: Reuse github_linking extract_linear_issue_id -- branch name patterns are provider-agnostic
- [Phase 24]: Numeric project IDs for selection -- avoids URL encoding issues with paths
- [Phase 24]: GitLab uses authorization_url pattern (like Slack/Linear), not installation_url (like GitHub)
- [Phase 25]: Embeddings source_type CHECK constraint already removed in migration 00017 -- no Jira-specific update needed
- [Phase 25]: JiraComment.body nullable (unlike LinearComment) -- Jira allows empty comments with attachments
- [Phase 25]: Jira token exchange uses JSON body (not form data) -- critical Atlassian API difference
- [Phase 25]: Jira sync uses /search/jql POST with nextPageToken pagination (not deprecated startAt)
- [Phase 25]: ADF text extraction helper converts Jira API v3 document format to plain text
- [Phase 25]: get_valid_token returns (access_token, cloud_id) tuple since cloud_id needed for all Jira API calls
- [Phase 25]: Added Jira to dashboard page INTEGRATIONS array for quick-connect from homepage
- [Phase 25]: Jira positioned as 6th integration across all UI surfaces, updated counts from /5 to /6
- [Phase 26]: Followed SlackMessage pattern for TelegramMessage (no BaseModel, no updated_at)
- [Phase 26]: Webhook endpoint uses hmac.compare_digest for X-Telegram-Bot-Api-Secret-Token verification
- [Phase 26]: Background task pattern for webhook processing (same as Fathom _poll_background)
- [Phase 26]: TelegramConnect mirrors FathomConnect pattern for consistency
- [Phase 26]: Telegram brand color #26A5E4 for settings icon, no external BotFather link
- [Phase 29]: AlertDialog uses controlled state for disconnect confirmation (not AlertDialogTrigger wrapper)
- [Phase 29]: friendlyError maps known error substrings to user-friendly messages with generic fallback
- [Phase 29]: isResyncingRef pattern resolves eslint-disable in integrations tab without re-triggering effects
- [Phase 29]: Settings page decomposed from 1,030 lines to 112-line shell + 4 tab components
- [Phase 29]: Renamed jira migration to 00019b (not 00020) because 00020 is occupied by telegram_messages
- [Phase 29]: Kept backward-compatible _parse_notion_datetime alias in notion.py router
- [Phase 29]: Redis rate limiter fails open on Redis errors -- never blocks API due to Redis outage
- [Phase 29]: OAUTH_STATE_SECRET falls back to provider client_secret for backward compatibility
- [Phase 29]: Legacy API keys with NULL salt verify via unsalted hash path -- no migration needed
- [Phase 29]: TICKET_ID_PATTERN strict allowlist (^[A-Z][A-Z0-9]+-\d+$) for JQL injection prevention
- [Phase 29]: X-Forwarded-For trusted only from loopback/private IPs via ipaddress module
- [Phase 29]: _lookup_ticket returns 3-tuple (ticket, fk_id, is_linear) for mock-friendly ticket type detection
- [Phase 29]: NotionSyncSection receives isPageLoading prop to gate mount-effect sync resume
- [Phase 28]: Provider dispatch via string param (not class hierarchy) for minimal clone auth abstraction
- [Phase 28]: Token refresh before EACH GitLab repo clone -- OAuth tokens expire in 2 hours
- [Phase 28]: GitLab chunks filtered by matching repo_full_name against available_projects paths
- [Phase 28]: GitLab project selection uses numeric Set<number> for IDs, internal visibility uses dimmed Lock icon
- [Phase 29]: makeConnectHandler/makeDisconnectHandler moved into integration-cards.tsx as module-level helpers
- [Phase 29]: connected_sources guard pattern: None means query all (backward compat), hybrid search post-filters results
- [Phase 30]: Canvas content retrieved via files.info content field with url_private download fallback
- [Phase 30]: Huddles without AI notes create minimal MeetingTranscript with placeholder text, embedding skipped
- [Phase 30]: User name resolution cached within poll run to avoid redundant Slack API calls
- [Phase 30]: slack_huddle maps to same source types as fathom (meeting_transcript, meeting_segment) since both use MeetingTranscript model
- [Phase 30]: slack_huddle auto-added to connected_sources when Slack is connected (piggybacks on Slack OAuth token)
- [Phase 31]: Semaphore created inside each function (not module-level) to avoid cross-function interference
- [Phase 31]: Each concurrent task creates its own async_session for DB session isolation
- [Phase 31]: Semaphore(5) for GitLab note concurrency -- conservative for 10 req/sec rate limit
- [Phase 31]: sync_start timestamp for cursor (not max updated_at) to handle MRs updated during sync
- [Phase 31]: Reuse existing _github_semaphore(10) for review concurrency; cursor_value parsed as ISO datetime; per-page progress replaces per-PR

### Roadmap Evolution

- Phase 21 added: Auth redesign and social OAuth
- Phase 23 added: Remotion Animated Hero
- Phase 24 added: GitLab Integration
- Phase 25 added: Jira Integration
- Phase 26 added: Telegram Chat Integration
- Phase 27 added: Dashboard Homepage Intelligence Widgets
- Phase 29 added: Codebase Hardening - Security, Bug Fixes, Architecture, and UI/UX Polish
- Phase 30 added: Slack Huddle Transcript Ingestion
- Phase 31 added: GitLab & GitHub Sync Performance Optimization

### Pending Todos

None yet.

### Blockers/Concerns

- DarkModeApplier must apply .dark to html for Radix portals but NOT break landing page .landing-theme
- OAuth redirects in onboarding wizard destroy React state -- cookie-based state preservation required
- Supabase Realtime subscriptions need mandatory removeChannel cleanup (React Strict Mode double-invoke)

## Session Continuity

Last session: 2026-03-15T10:15:46.353Z
Stopped at: Completed 31-02-PLAN.md
Resume file: None
