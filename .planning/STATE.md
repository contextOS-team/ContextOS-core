---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Live Intelligence
status: in_progress
stopped_at: Completed 39-02-PLAN.md
last_updated: "2026-04-22T15:43:00.000Z"
last_activity: 2026-04-22 -- Completed 39-02 Slack DM polling service
progress:
  total_phases: 8
  completed_phases: 1
  total_plans: 9
  completed_plans: 8
  percent: 97
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** Phase 39 - Slack User Token Migration & DM Support (Plans 01, 02, 03 complete; 04 remaining)

## Current Position

Milestone: v1.3 Live Intelligence
Phase: 39 of 39 (Slack User Token Migration & DM Support)
Plan: 4 of 4 in current phase
Status: Plans 39-01, 39-02, 39-03 complete; 39-04 remaining
Last activity: 2026-04-22 -- Completed 39-02 Slack DM polling service

Progress: [██████████] 97%

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

### Roadmap Evolution

v1.3 roadmap created with 7 phases (32-38) covering 19 requirements across activity events, graph visualization, onboarding, chrome extension, landing page, privacy research, and RAG.
- Phase 39 added: Slack User Token Migration & DM Support

### Pending Todos

- Activity tab receives no events from integrations -- activity_events table is never written to by any sync service (Phase 32 fixes this)
- v1.2 tech debt: traverse_graph() missing source_type/source_id columns, decision node snippet wrong property keys

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-04-22T15:41:23Z
Stopped at: Completed 39-02-PLAN.md
Resume file: .planning/phases/39-slack-user-token-migration-dm-support/39-04-PLAN.md
