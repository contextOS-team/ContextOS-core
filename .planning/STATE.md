---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: active
last_updated: "2026-03-02T06:32:44Z"
progress:
  total_phases: 12
  completed_phases: 11
  total_plans: 30
  completed_plans: 30
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** Phase 09 - Notion Integration UI Polish (complete)

## Current Position

Phase: 09 (Notion Integration UI Polish)
Plan: 1 of 1 in current phase (all plans complete)
Status: Phase 09 complete
Last activity: 2026-03-02 -- Simplified Notion card: removed page list, added summary stats line, clean workspace header

Progress: [==========] 100% (09: 1/1 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 16
- Average duration: 5.8min
- Total execution time: 1.45 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3 | 12min | 4min |
| 2. Linear Integration | 3 | 26min | 8.7min |
| 3. Slack/Meeting Ingestion | 3 | 24min | 8min |
| 7. GitHub Integration | 3 | 19min | 6.3min |
| 7.1 Tech Debt Cleanup | 2 | 10min | 5min |

**Recent Trend:**
- Last 5 plans: 07-02 (6min), 07-03 (5min), 07.1-01 (7min), 07.1-02 (3min)
- Trend: Consistent execution times (5-7min)

*Updated after each plan completion*
| Phase 07.2 P01 | 3min | 2 tasks | 4 files |
| Phase 07.2 P02 | 3min | 2 tasks | 4 files |
| Phase 07.2 P03 | 3min | 2 tasks | 7 files |
| Phase 08.1 P01 | 3min | 3 tasks | 5 files |
| Phase 08.1 P02 | 6min | 3 tasks | 4 files |
| Phase 08.1.1 P01 | 5min | 3 tasks | 5 files |
| Phase 08.1.1 P02 | 4min | 2 tasks | 6 files |
| Phase 08.1.1 P03 | 3min | 2 tasks | 5 files |
| Phase 10 P01 | 6min | 3 tasks | 9 files |
| Phase 10 P02 | 5min | 2 tasks | 6 files |
| Phase 10 P03 | 7min | 4 tasks | 12 files |
| Phase 09 P01 | 2min | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 6 phases derived from 39 requirements across 3 team members
- [Roadmap]: DASH-01 (auth pages) pulled into Phase 1 so Bekbol works in parallel with Daulet from day one
- [Roadmap]: DASH-04 (integration setup) pulled into Phase 3 so Bekbol delivers UI alongside Slack/Fathom backend
- [Roadmap]: Phases 2+3 can overlap; Phase 4 starts after Phase 2 (Linear data needed for synthesis)
- [01-01]: Used moddatetime extension for updated_at triggers instead of custom function
- [01-01]: Switched build system from setuptools to hatchling for modern Python packaging
- [01-01]: Health endpoint checks DB connectivity via SELECT 1 query
- [01-01]: Codegen target deferred to Phase 2 as Makefile placeholder
- [01-01]: match_embeddings function filters out soft-deleted embeddings
- [01-02]: Added audience="authenticated" to JWT decode for Supabase aud claim
- [01-02]: Test settings patching must override get_settings in both src.config and src.auth
- [01-02]: Repository layer deferred to Phase 2+; services query DB directly for now
- [01-03]: Dashboard uses /dashboard path instead of (dashboard) route group for cleaner URLs
- [01-03]: SignOutButton extracted as client component to keep dashboard layout as server component
- [01-03]: Magic link emailRedirectTo falls back to window.location.origin when env var is unset
- [02-01]: Vault secrets API (vault.create_secret/decrypted_secrets) used over raw pgsodium for simpler token storage
- [02-01]: State parameter uses HMAC-SHA256 signing with LINEAR_CLIENT_SECRET for CSRF protection
- [02-01]: Token values stored in Vault; DB columns store Vault secret name references, not actual tokens
- [02-01]: Advisory lock key uses hashtext of workspace_id string for deterministic locking
- [02-02]: Raw httpx GraphQL client with bare token auth (not Bearer) per Linear API spec
- [02-02]: Exponential backoff on 429: 1s initial, 2x multiplier, max 3 retries
- [02-02]: Sync runs as FastAPI BackgroundTasks, progress stored in workspace_integrations.config JSONB
- [02-02]: Embedding generation decoupled as stub with correct signatures for Phase 4
- [02-03]: Module-level config import (import src.config) instead of from-import for reliable test patching across test ordering
- [02-03]: Background task delegation for webhook event processing to ensure fast 200 response to Linear
- [02-03]: Webhook service creates its own session via async_session() for background processing isolation
- [02-03]: Comment embedding queued for the comment source_type, not re-embedding the parent ticket
- [03-01]: Slack bot tokens do not expire and have no refresh tokens -- simpler than Linear OAuth
- [03-01]: Module-level config import (import src.config) for slack router matches webhook pattern
- [03-01]: Background task delegation for Slack event processing ensures fast 200 response
- [03-01]: Channel monitoring defaults to all channels if no selected_channels configured
- [03-01]: Aliased sqlalchemy.text as sa_text to avoid SQLModel/Field namespace collision
- [03-02]: Slack conversations.list uses cursor pagination with limit=1000 per page
- [03-02]: Channel list cached in workspace_integrations.config JSONB under available_channels
- [03-02]: GET /channels reads from cache; POST /channels/refresh hits Slack API fresh
- [03-02]: Fathom API key stored in Vault, key format: fathom_{workspace_id}_api_key
- [03-02]: Fathom API base URL configurable via FATHOM_API_BASE_URL (api.fathom.video does not resolve)
- [03-02]: Fathom dedup uses fathom_id in raw_data JSONB (no dedicated DB column)
- [03-02]: Processing transcripts skipped and retried on next poll cycle
- [03-02]: Poll endpoint runs in BackgroundTasks, returns 202 immediately
- [03-03]: OAuth upsert must query WITHOUT deleted_at filter to reuse soft-deleted rows on reconnect
- [03-03]: All DB timestamp columns use naive UTC -- originally datetime.utcnow(), updated to datetime.now(timezone.utc).replace(tzinfo=None) in 07.1-01
- [03-03]: Fathom API base URL is api.fathom.ai/external/v1, auth header is X-Api-Key, endpoint is /meetings
- [07-01]: PyJWT with RS256 for GitHub App JWT signing (already a project dependency, no new library needed)
- [07-01]: Installation access tokens stored in Vault with 1-hour expiry; refreshed on demand via App JWT
- [07-01]: GitHub App installation flow (not standard OAuth2) per CONTEXT.md decision
- [07-01]: HMAC-SHA256 signed state uses GITHUB_CLIENT_SECRET (same pattern as Linear/Slack)
- [07-01]: installation_id stored in OAuthToken.metadata_ JSONB for token refresh
- [07-01]: 'github' added to provider check constraints via migration ALTER
- [07-02]: Sequential repo sync per user decision to avoid rate limit exhaustion
- [07-02]: New repos NOT auto-monitored (explicit selection required, unlike Slack channels)
- [07-02]: Branch-name-only linking with case-insensitive regex for team key matching
- [07-03]: GitHub webhook signature uses X-Hub-Signature-256 with sha256= prefix format
- [07-03]: Workspace resolved from installation.id by scanning OAuthToken metadata_ JSONB
- [07-03]: Review comments stored as GithubReview records with file_path and line_range
- [07-03]: Bot filtering via exact login match against known set (dependabot, renovate, github-actions)
- [07.1-01]: datetime.now(timezone.utc).replace(tzinfo=None) replaces datetime.utcnow() across all backend code
- [07.1-01]: mock_session.add = MagicMock() pattern for AsyncMock sessions to prevent unawaited coroutine warnings
- [07.1-02]: REQUIREMENTS.md traceability table updated with correct statuses and GH-01..05 entries
- [07.2-02]: fetchStatuses() placed outside try-catch so statuses always refresh after disconnect attempt
- [Phase 07.2]: [07.2-01]: Linear API requires 'Bearer ' prefix on Authorization header (corrects prior decision [02-02])
- [Phase 07.2]: [07.2-01]: Fathom API field mapping: calendar_invitees, default_summary, scheduled_start_time, transcript array, duration from recording timestamps
- [Phase 07.2]: [07.2-03]: OAuth state signing extracted to oauth_common.py shared module; provider wrappers preserve error types
- [08.1-01]: Light/transparent top nav with backdrop-blur matches warm off-white page feel better than dark bar
- [08.1-01]: Kept export name as Sidebar to minimize import changes across layout
- [08.1-01]: Active nav indicator uses bottom border accent line extending below nav item
- [08.1-02]: Compact status rows (Linear-inspired) for home page over card grid -- higher density, faster scanning
- [08.1-02]: Status indicators use solid 1.5px dots (emerald/red/hollow ring) -- no animation, no pills
- [08.1-02]: Marketing-copy descriptions removed entirely, not replaced with placeholders
- [08.1-02]: draw-ring animation removed alongside pulse-dot since setup progress ring eliminated
- [Phase 08.1.1]: [08.1.1-01]: Notion token exchange uses HTTP Basic Auth (base64 client_id:client_secret) per Notion API spec
- [Phase 08.1.1]: [08.1.1-01]: Notion tokens are long-lived with no fixed expiry; get_valid_access_token reads from Vault without refresh check
- [Phase 08.1.1]: [08.1.1-01]: blocks_to_markdown handles 15+ block types including tables, code, callouts, images
- [Phase 08.1.1]: [08.1.1-01]: Background sync creates own session via async_session() for task isolation (same as webhook pattern)
- [Phase 08.1.1]: [08.1.1-02]: NOTION_WEBHOOK_SECRET as single env var for HMAC verification (same pattern as LINEAR_WEBHOOK_SECRET)
- [Phase 08.1.1]: [08.1.1-02]: Delivery ID derived from SHA256 hash of event_type+entity_id+timestamp (Notion has no delivery header)
- [Phase 08.1.1]: [08.1.1-02]: Webhook verification flow returns {status: verified} for initial setup handshake
- [Phase 08.1.1]: [08.1.1-02]: sync_page_by_id creates own session for background task isolation
- [Phase 08.1.1]: NotionLogo uses currentColor for outer shape and white for inner page -- matches official Notion brand
- [Phase 08.1.1]: OAuth callback params for GitHub and Notion handled in single DRY useEffect loop
- [Phase 08.1.1]: Notion pages_synced displayed inline with workspace name in integration card
- [Phase 08.1.1]: Notion uses same brandColor/brandBorder as GitHub (bg-foreground) since Notion is a black logo
- [10-02]: BATCH_SIZE=25 chosen as safe middle ground within 20-50 range from CONTEXT.md
- [10-02]: Redis Streams consumer group pattern with BUSYGROUP-tolerant group creation
- [10-02]: Whitespace normalization via re.sub(r'\s+', ' ', text).strip() before SHA-256 hashing
- [10-02]: enqueue_embedding_job creates and closes Redis connection per call for simplicity
- [10-01]: Dual-write pattern: sync_cursors AND existing JSONB config updated together for backward compat
- [10-01]: SyncAdapter uses runtime_checkable Protocol (structural typing, no base class inheritance)
- [10-01]: Module-level assert isinstance() for fail-fast protocol conformance verification
- [10-01]: SyncRunLogger uses contextvars for sync_run_id correlation across async operations
- [10-01]: Reconcile methods stubbed with not_implemented status for Plan 10-03
- [10-03]: Semaphore wraps individual HTTP calls for fine-grained concurrency control (Notion=3, GitHub=10, Linear=5)
- [10-03]: Jitter formula 0.5 + random.random() for 50-150% of base delay per CONTEXT.md spec
- [10-03]: Incremental sync compares last_edited_time before content refetch to skip unchanged Notion pages
- [10-03]: Polling fallback fetches first 100 pages per workspace (single search API call)
- [10-03]: Background workers use asyncio.create_task in FastAPI lifespan with CancelledError for graceful shutdown
- [09-01]: NotionPages component removed from UI; card shows summary stats line instead of paginated page list
- [09-01]: Re-sync button inline with stats line (no separate settings section); "Manage access" link removed
- [09-01]: Middle dot separator for stats: "{count} pages synced . {time ago}"
- [09-01]: notionDisplayName shows workspace name only (page count suffix removed from header)

### Pending Todos

None yet.

### Roadmap Evolution

- Phase 7 added: GitHub Integration
- Phase 07.1 inserted after Phase 7: tech debt cleanup (URGENT)
- Phase 07.2 inserted after Phase 07.1: Integration bug fixes & hardening from brutal codebase audit (URGENT)
- Phase 08.1.1 inserted after Phase 08.1: Notion Integration (URGENT)
- Phase 9 added: Notion Integration UI Polish
- Phase 10 added: Sync engine improvements

### Blockers/Concerns

- Linear OAuth app registration required before Phase 2
- Slack app registration required before Phase 3
- Fathom API access required before Phase 3
- Gemini API key required before Phase 4
- GitHub OAuth app registration required before Phase 7

## Session Continuity

Last session: 2026-03-02
Stopped at: Completed 09-01-PLAN.md (Phase 09 complete)
Resume file: .planning/phases/09-notion-integration-ui-polish/09-01-SUMMARY.md
