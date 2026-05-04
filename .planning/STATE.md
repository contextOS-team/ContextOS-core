---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Live Intelligence
current_plan: 3
status: completed
stopped_at: Completed 40-02-PLAN.md
last_updated: "2026-05-04T10:04:33.723Z"
last_activity: 2026-05-04
progress:
  total_phases: 9
  completed_phases: 2
  total_plans: 12
  completed_plans: 11
  percent: 92
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.
**Current focus:** Phase 40 in progress -- Telegram Shared-Bot Migration. Plan 01 (backend data plane + dispatcher + pairing-code endpoint) complete; Plans 02 (frontend pairing UI) and 03 (cutover/cleanup) pending.

## Current Position

Milestone: v1.3 Live Intelligence
Phase: 40 of 9 (Telegram Shared-Bot Migration) -- IN PROGRESS
Current Plan: 3
Total Plans in Phase: 3
Status: Plans 40-01 (backend) + 40-02 (frontend pairing UI) complete; Plan 40-03 (cutover/cleanup) pending
Last activity: 2026-05-04 -- Plan 40-02 complete (live UX verified: bot @contextOSdev_bot claimed chat -1003644773967, UI flipped to connected via Realtime)

Progress: [█████████ ] 92%

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
- [40-01] Pairing-code redemption uses peek-then-burn: SELECT ownership first, then DELETE...RETURNING only on fresh claim, so cross-workspace and same-workspace re-claim never burn the code (CONTEXT idempotency rule)
- [40-01] secrets.token_urlsafe(12) -> exact 16-char base64url (~96 bits); plaintext storage with TTL+single-use is the security boundary
- [40-01] _send_reply_safe swallows TelegramError so a muted/banned bot never rolls back a successful claim (Pitfall 6); Realtime UI flip is the user-visible ack
- [40-01] Dispatcher branch order: my_chat_member -> private-drop -> /start in group/supergroup -> claim_chat -> resolve_workspace -> process_telegram_update (claim path BEFORE ingestion -- Pitfall 2)
- [40-01] handle_my_chat_member resolves workspace BEFORE soft-deleting so integration_disconnected activity has correct workspace_id
- [40-01] Bot reply text inlines hardcoded https://contextos.app/dashboard/settings link (no settings-derived frontend URL field exists yet); Plan 02 may parameterize
- [40-01] Legacy /webhook/{workspace_id}, /connect, /disconnect, /sync routes left intact in this plan to keep it independently mergeable; Plan 03 deletes them
- [40-01] Migration 00039 uses CREATE TABLE IF NOT EXISTS + DROP POLICY IF EXISTS for idempotency; legacy oauth_tokens + workspace_integrations purge runs at the bottom (Vault key cleanup is a Plan 03 deploy script)
- [Phase 40]: [40-02] Bot username driven by env (NEXT_PUBLIC_TELEGRAM_BOT_USERNAME frontend, TELEGRAM_BOT_USERNAME backend, fail-loud) -- operator's real bot is @contextOSdev_bot, not the placeholder the plan assumed
- [Phase 40]: [40-02] /api/integrations/status overrides Provider.TELEGRAM from telegram_chat_workspace (Phase-40 source of truth) after the standard workspace_integrations loop -- per-provider override pattern keeps the aggregator endpoint stable
- [Phase 40]: [40-02] Local migration apply via psql -f against LOCAL_SUPABASE_URL (supabase db push only targets remote) -- standardize in a runbook later; tracked as future work

### Roadmap Evolution

v1.3 roadmap created with 7 phases (32-38) covering 19 requirements across activity events, graph visualization, onboarding, chrome extension, landing page, privacy research, and RAG.
- Phase 39 added: Slack User Token Migration & DM Support
- Phase 40 added: Telegram Shared-Bot Migration -- replace bring-your-own-bot with single shared @ContextOSBot via deep-link pairing

### Pending Todos

- Activity tab receives no events from integrations -- activity_events table is never written to by any sync service (Phase 32 fixes this)
- v1.2 tech debt: traverse_graph() missing source_type/source_id columns, decision node snippet wrong property keys

### Blockers/Concerns

None.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files | Completed   |
|-------|------|----------|-------|-------|-------------|
| 40    | 01   | 12min    | 3     | 8     | 2026-05-03  |
| 40    | 02   | 30min active (~19h incl. operator setup) | 3 | 7 | 2026-05-04 |

## Session Continuity

Last session: 2026-05-04T10:04:33.720Z
Stopped at: Completed 40-02-PLAN.md
Resume file: None
