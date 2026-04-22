---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Live Intelligence
status: in_progress
stopped_at: Phase 39 complete -- Slack user token migration + DM support shipped; E2E verified on live workspace
last_updated: "2026-04-22T20:17:47Z"
last_activity: 2026-04-22 -- Plan 39-04 complete (scheduler + onboarding + live E2E, 177 messages ingested)
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** Phase 39 complete -- Slack User Token Migration & DM Support shipped end-to-end and verified on a live workspace (177 messages ingested across DMs + channels).

## Current Position

Milestone: v1.3 Live Intelligence
Phase: 39 of 39 (Slack User Token Migration & DM Support) -- COMPLETE
Plan: 4 of 4 in current phase (+ Phase 39.1 inline gap closure) -- all complete
Status: Plans 39-01 through 39-04 complete; Phase 39.1 gap closure shipped; Plan 39-04 verified end-to-end by user and approved
Last activity: 2026-04-22 -- Plan 39-04 complete (scheduler wire-up + onboarding DM consent + live E2E verification)

Progress: [██████████] 100%

## Accumulated Context

### Decisions

- [32-01] Slack and Telegram skipped -- no full_sync functions exist (event-driven only)
- [32-01] emit_activity placed before session.commit() in synthesis.py for transactional consistency
- [32-01] GitHub/GitLab emit sync_completed at end of sync_repos/sync_projects (covers partial success)
- [32-03] Use inline style for integration brand colors (Tailwind can't accept dynamic color vars)
- [32-03] GitHub brand color #8b949e (muted) instead of #24292f for dark theme visibility
- [32-03] Notion uses neutral gray #9CA3AF for dark theme compatibility
- [32-02] GitHub/GitLab pr_merged guarded by state == merged to avoid emitting for closed-but-not-merged PRs
- [32-02] Notion page_created limited to 5 events per full sync to avoid activity tab flooding
- [32-02] GitHub/GitLab callback routers extract workspace_id from state for emit_activity
- [33-01] ReactFlow v12 uses named exports; import as `{ ReactFlow }` not default
- [33-01] ELK layout via dynamic import for tree-shaking (~200KB)
- [33-01] Generic computeElkLayout<N> preserves typed node data through layout pipeline
- [33-01] Node type switching via type field on nodes (not swapping nodeTypes registry)
- [39-01] SLACK_USER_SCOPES locked to DM-only (im/mpim/users) -- no channels/groups scopes
- [39-01] User tokens stored under oauth_slack_{ws}_user_access (parallel to bot_access); no legacy fallback
- [39-01] slack_user_id merged into integration.config post-upsert to preserve existing keys
- [39-01] needs_reauth flag computed from status=connected AND user_access missing in Vault
- [39-01] _should_filter drops <10-char rule across ALL paths (webhook + future DM poller)
- [39-01] dms_first_enabled_at set on first enable so Plan 02's DM poller knows to run 7-day backfill
- [39-03] fetchStatuses prop NOT wrapped in useCallback at parent — Settings useEffect uses [slack.status] deps with eslint-disable (Option B) to avoid infinite render loop
- [39-03] Switch component added manually via radix-ui namespace to match existing Label pattern (not shadcn CLI which pulls standalone @radix-ui/react-switch)
- [39-03] Fetch-separately pattern: getSlackStatus on mount avoids extending backend aggregator endpoint (matches GitHub/GitLab repos pattern)
- [39-03] SlackDmToggle re-reads include_dms on mount for reload-survival; Label wrapper min-h-10 provides >=40px hit area while Switch stays visually compact
- [39-02] _compute_oldest coerces naive last_user_poll_at to UTC before .timestamp() -- fixes TZ-offset bug in literal plan spec
- [39-02] _upsert_messages mirrors slack_events._handle_message exactly: pg_insert + on_conflict_do_update + post-commit SELECT for id (not .returning())
- [39-02] SET-clause parity with slack_events verified via inspect.getsource() assertion in TestUpsert.test_F (runtime drift guard, SLACK-USR-04)
- [39-02] Sequential DM iteration (no asyncio.gather) + single-retry 429 Retry-After via shared _slack_get helper
- [39-02] DM-only lock: users.conversations called with types=im,mpim exclusively; channels stay on webhook path per CONTEXT.md
- [39.1] Pivoted to user-token channel polling (CTO invite permissions blocked); accepts idempotent duplicate ingestion path vs. bot webhook
- [39.1] USER_CONVERSATION_TYPES includes im,mpim,public_channel,private_channel; include_dms gate controls all user-token polling
- [39-04] poll_user_messages imported at module top of sync_scheduler.py (not deferred) so tests can patch src.services.sync_scheduler.poll_user_messages; fresh AsyncSession per workspace mirrors Notion reconcile pattern
- [39-04] Slack DM poll block placed between code-index-freshness and daily-digest blocks so digests in the same cycle see freshly-polled DM/channel data
- [39-04] Onboarding Slack card auto-expands once per session after OAuth redirect (guarded by autoExpandedRef); DM toggle defaults OFF — onboarding completion independent of opt-in state
- [39-04] Plan 39-04 verified end-to-end on user's real Slack workspace (177 messages ingested across 3 DMs, 1 group DM, and 4 channels)
- [39-04] Discovered and fixed 2 pre-existing Slack upsert bugs during live test (constraint name drift: switched to ON CONFLICT index_elements; tz mismatch: _ts_to_datetime now returns naive UTC). Both were silent on the bot webhook path due to exception-swallowing.

### Roadmap Evolution

v1.3 roadmap created with 7 phases (32-38) covering 19 requirements across activity events, graph visualization, onboarding, chrome extension, landing page, privacy research, and RAG.
- Phase 39 added: Slack User Token Migration & DM Support

### Pending Todos

- Activity tab receives no events from integrations -- activity_events table is never written to by any sync service (Phase 32 fixes this)
- v1.2 tech debt: traverse_graph() missing source_type/source_id columns, decision node snippet wrong property keys

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-04-22T20:17:47Z
Stopped at: Phase 39 complete -- Slack user token migration + DM support shipped; E2E verified on live workspace
Resume file: None
