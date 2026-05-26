---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Product Expansion & Action Layer
status: executing
stopped_at: Phase 46 planned; ready to execute
last_updated: "2026-05-26T11:22:00.236Z"
last_activity: 2026-05-26 -- Phase 46 planning complete
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 16
  completed_plans: 9
  percent: 29
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-24)

**Core value:** ContextOS turns scattered work conversations into source-backed decision memory, then helps teams act on those decisions without losing provenance or workspace boundaries.
**Current focus:** Phase 46 — graph-rag-quality-improvements

## Current Position

Phase: 46 (graph-rag-quality-improvements) — PLANNED
Plan: 0 of 7
Status: Ready to execute
Last activity: 2026-05-26 -- Phase 46 planning complete

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
- [Phase 40]: [40-03] Re-pair after kick uses ON CONFLICT (chat_id) DO UPDATE WHERE removed_at IS NOT NULL with RETURNING -- distinguishes successful re-claim from cross-workspace conflict
- [Phase 40]: [40-03] /api/telegram/pairing-code returns 409 already_connected when workspace has any active mapping -- prevents multi-engineer 15-min UI hang; frontend surfaces TelegramAlreadyConnectedError as a typed phase with Close button
- [Phase 40]: [40-03] Migration 00039 patched with REPLICA IDENTITY FULL on telegram_chat_workspace -- Supabase Realtime needs the full row in WAL to apply workspace_id filter against UPDATE events (re-pair UPDATEs were silently dropped without it)
- [Phase 40]: [40-03] Realtime subscription widened from event:'INSERT' to event:'*' with !row.removed_at payload filter -- re-pair is ON CONFLICT DO UPDATE not INSERT; payload filter ignores soft-delete UPDATEs on kick
- [Phase 40]: [40-03] StrictMode auto-mint guard via useRef(mintedRef) -- StrictMode dev double-fire posted /pairing-code twice; each mint wipes the prior code so the user pasted an already-burned code
- [Phase 40]: [40-03] Settings disconnect button is intentionally a toast hint pointing at the in-Telegram remove flow; Phase 40 has no workspace-level disconnect endpoint by design (bot's my_chat_member handler soft-deletes per chat)
- [Phase 40]: [40-03] Vault purge uses SQL LIKE prefilter + strict regex re-validation + per-row exception isolation -- defense in depth so an unrelated 'oauth_telegram_'-prefixed secret can't be deleted, and one permission glitch can't abort the whole run
- [Phase 41]: Phase 41 dashboard last-visited state is server-side per user/workspace — CONTEXT.md defines since-last-visit as a first-class persistent concept; server-side state keeps multi-device behavior coherent.
- [Phase 41]: Human checkpoint rejected the warm/serif pulse direction. `.pulse-surface` remains scoped to dashboard home, but now follows the existing global dashboard dark tokens and only adds pulse-specific affordances, preventing color drift from context/settings/activity/graph.
- [Phase 41]: Chrome source freshness indicator is passive after human checkpoint — no drawer, no Sync all button, no reconnect CTA. The label is `updated ...`, not `last synced ...`, because per-provider health is not yet modeled.
- [Phase 41]: Source freshness is a launch risk for the first startup pilot. The current chrome can show ambient source activity recency, but broad "everything is up to date" claims require a provider-level health model; see 41-SOURCE-FRESHNESS-RISKS.md.
- [Phase 42]: LANDING_SEO is the source of truth for public homepage title and description — Centralizing approved launch metadata prevents drift between SEO and later landing components.
- [Phase 42]: Primary landing CTA label is See your decision graph while href remains #booking — The label sells the launch outcome while preserving the existing booking-call flow.
- [Phase 42]: Decision Receipt is now the landing product-proof primitive — Replaces ticket-first Remotion proof with a crawlable source-backed artifact while leaving Remotion files untouched.
- [Phase 42]: Hero copy reads from LANDING_HERO and leads to #demo first — Centralized copy stays aligned with Plan 42-01 while preserving the booking conversion flow through See your decision graph -> #booking.
- [Phase 42]: Decision Receipt sample data is fictional — Satisfies the plan threat model by avoiding any implication of real customer workspace data.
- [Phase 42]: Landing page now prioritizes hero -> product demo -> sources -> booking -> footer — User feedback found the plan-compliant version too noisy, so problem/how/features/trust bands were removed from the rendered page order.
- [Phase 42]: Landing route owns social metadata — Absolute title, OpenGraph, Twitter, and landing-scoped OG image copy prevent old ticket-first root metadata from leaking into launch previews.
- [Phase 44]: Suggestions use one generic workspace-scoped contract for missing-source coverage now and missed-decision/action-prompt families later.
- [Phase 44]: Exact workspace/fingerprint matches are the preservation boundary; dismissed or resolved exact suggestions are not reopened by detector refreshes.
- [Phase 44]: Missing-source coverage suggestions require concrete Decision graph targets and specific missing evidence context, not generic integration upsells.
- [Phase 44]: Digest-driven suggestion publication runs in a nested non-blocking transaction so suggestion failures do not roll back digest graph activity.
- [Phase 44]: Dashboard suggestions render as a bounded `Needs review` right-rail surface; `Recent decisions` remains the primary confirmed-memory column.
- [Phase 44]: Vitest test config now uses esbuild automatic JSX instead of `@vitejs/plugin-react` because the installed plugin imported a Vite internal export unavailable in the installed Vite version.
- [Phase 45]: Missed-decision scans are non-blocking post-sync work; sync success must not depend on scanner success, and scanner checkpoints advance only after scan processing succeeds.
- [Phase 45]: User-visible missed-decision candidates require exact source quotes, source links, confidence tiers, people, affected systems, and persisted candidate rows before publishing Phase 44 suggestions.
- [Phase 45]: Raw digest Decision nodes cannot directly publish missed-decision suggestions; dedupe classifies strong/weak/no matches and suppresses exact quote duplicates before UI surfacing.
- [Phase 45]: Confirmed candidates become source-backed graph `Decision` nodes while preserving quote, rationale, source link, confidence, people, affected systems, candidate ID, and scan-run provenance.
- [Phase 45]: Dashboard missed-decision candidates use the existing `Needs review` hierarchy, stay out of `Recent decisions`, and take priority over the generic Phase 44 right-rail surface when present.

### Roadmap Evolution

v1.3 roadmap created with 7 phases (32-38) covering 19 requirements across activity events, graph visualization, onboarding, chrome extension, landing page, privacy research, and RAG.

- Phase 39 added: Slack User Token Migration & DM Support
- Phase 40 added: Telegram Shared-Bot Migration -- replace bring-your-own-bot with single shared @ContextOSBot via deep-link pairing
- Phase 42 added: Landing Positioning and SEO Launch Rewrite -- launch-focused landing copy, SEO research, and Decision Receipt visual direction around source-backed decision memory
- Milestone v1.4 added: Product Expansion & Action Layer -- split the user's feature backlog into separate phases for multi-workspace support, suggestions/dismissals, post-sync missed-decision detection, Graph RAG quality, confirmed Slack/Telegram actions, Figma evidence, and MCP/CLI research

### Pending Todos

- Activity tab receives no events from integrations -- activity_events table is never written to by any sync service (Phase 32 fixes this)
- v1.2 tech debt: traverse_graph() missing source_type/source_id columns, decision node snippet wrong property keys

### Blockers/Concerns

- [Phase 45]: Cloud `supabase db push` for migration 00042 still needs Supabase CLI login and `supabase link --project-ref <project-ref>`. Local development schema is applied and migration history repaired, so local downstream verification can proceed.
- [Phase 45]: Authenticated manual visual verification of 45-04 remains pending because Browser automation exposed no browser backend in-session and unauthenticated `/dashboard` requests redirect to `/login`. Automated component, placement, and full Vitest coverage passed.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files | Completed   |
|-------|------|----------|-------|-------|-------------|
| 40    | 01   | 12min    | 3     | 8     | 2026-05-03  |
| 40    | 02   | 30min active (~19h incl. operator setup) | 3 | 7 | 2026-05-04 |
| 40    | 03   | ~4h (incl. human-verify gate + 5 deviation fixes) | 4 | 16 | 2026-05-04 |
| Phase 41 P01 | 38min | 3 tasks | 12 files |
| Phase 41 P03 | checkpointed 2026-05-21 | 3 tasks + human visual fixes | 15 files |
| Phase 42 P01 | 4min | 3 tasks | 5 files |
| Phase 42 P02 | 4min | 3 tasks | 3 files |
| Phase 42 P03 | 24min | 4 tasks | 12 files |
| Phase 44 P01-P04 | 2026-05-25 | 8 tasks | 24 code/planning files |

## Session Continuity

Last session: 2026-05-26T09:57:28.157Z
Stopped at: Phase 46 UI-SPEC approved
Resume file: .planning/phases/46-graph-rag-quality-improvements/46-UI-SPEC.md
