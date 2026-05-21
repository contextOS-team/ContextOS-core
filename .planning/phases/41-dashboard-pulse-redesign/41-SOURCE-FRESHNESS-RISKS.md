# Source freshness risks for first startup onboarding

**Date:** 2026-05-21

**Context:** This note captures concerns raised while reviewing the Phase 41 dashboard chrome freshness indicator. The issue is not only visual. A first external startup team will judge whether ContextOS can be trusted to stay current across their tools.

## Verdict

Current behavior is acceptable for a controlled, white-glove first-team pilot, but not for a hands-off "everything stays up to date" launch claim.

The dashboard chrome may show ambient recency such as `sources updated 10h ago`, but it must not imply that every connected provider is fully synced or healthy until we have a per-provider source-health model.

## Current behavior by provider

| Provider | Current update path | Current frequency | Risk |
| --- | --- | --- | --- |
| Slack channels | Slack Events API webhook for message events. | Near realtime when webhook is configured and selected channel is monitored. | Good for monitored channels, but webhook delivery/config must be verified during onboarding. |
| Slack user-token polling | `poll_user_messages()` covers DMs, group DMs, public channels, and private channels, despite the legacy `include_dms` flag name. | Every 15 minutes only when `include_dms` is enabled. | If `include_dms` is off, this polling path returns `dms_disabled`; DMs and user-token channel fallback are not ingested. |
| Slack digest | Daily digest generation over stored messages. | Scheduler checks every 15 minutes, Redis/DB dedup makes it effectively daily. | Digest freshness is not raw source freshness; do not use it as proof Slack ingestion is current. |
| Telegram | Shared bot webhook for mapped group/supergroup updates. | Near realtime. | No polling fallback or history/backfill expectation. Private chats are intentionally ignored. |
| Telegram digest | Daily digest generation over stored messages. | Scheduler checks every 15 minutes, Redis/DB dedup makes it effectively daily. | Same as Slack digest: useful summary, not freshness proof. |
| Notion | Webhook for page updates plus reconciliation via Notion search. | Reconciliation every 15 minutes. | Reasonable for pilot; verify webhook and fallback both work. |
| GitHub PR/review/comment/push | GitHub webhooks. Push enqueues code indexing. | Near realtime for webhooks. Code index fallback every 60 minutes. | PR data has no periodic lightweight reconciliation; rely on webhook/manual sync. |
| GitHub code index | Push-triggered indexing plus scheduled freshness check. | Scheduled fallback every 60 minutes. | Reasonable baseline. |
| GitLab MR/note | GitLab webhooks plus manual/queued MR sync. | Near realtime for webhooks; full MR sync only when queued. | No periodic MR reconciliation. |
| GitLab code index | Manual/triggered indexing exists. | No confirmed scheduler fallback equivalent to GitHub. | Needs parity with GitHub before external reliability claim. |
| Jira | Manual full sync plus webhook endpoint. | Manual sync; webhook near realtime if configured. | No periodic incremental fallback; webhook registration/refresh needs verification. |
| Linear | Initial auto-sync after connect, manual sync, Linear webhook endpoint. | Manual/initial sync; webhook near realtime if configured. | Scheduler only has a stub for Linear reconciliation. |
| Fathom | Manual transcript poll endpoint. | Manual only. | Not reliable for first-team freshness until scheduled polling exists. |

## First-team pilot rules

1. Treat the first startup team as a controlled pilot, not a self-serve launch.
2. Scope the supported sources explicitly: Slack channels, one ticket system, one code host, and Notion are acceptable. Fathom freshness should not be promised yet.
3. During onboarding, run initial full syncs manually for every connected provider that supports them.
4. Verify each webhook with a deliberate test event:
   - Slack: send a message in a monitored channel.
   - Telegram: send a group message in the paired chat.
   - Notion: update a synced page.
   - GitHub/GitLab: open or update a PR/MR in a monitored repo/project.
   - Jira/Linear: create or update a tracked ticket.
5. Enable Slack user-token polling if DMs, group DMs, private channels, or user-token channel fallback matter to the team.
6. Monitor backend/OpenLogs during the first week and check provider freshness at least daily.

## Recommended target policy

| Provider | Recommended policy before broad launch |
| --- | --- |
| Slack | Realtime Events API for channels; 15-minute user-token polling when the workspace opts into DMs/private/user-token coverage; explicit `needs_reauth` surfacing. |
| Telegram | Realtime webhook for mapped groups; document no DM/history backfill. |
| Notion | Keep webhook plus 15-minute reconciliation. |
| Jira | Add 15-minute incremental fallback using updated-since JQL; verify and refresh Jira webhook registrations. |
| Linear | Add 15-minute incremental fallback using `updatedAt` filters. |
| GitHub | Keep webhooks and 60-minute code index fallback; add lightweight hourly PR reconciliation for monitored repos. |
| GitLab | Add hourly MR reconciliation and GitLab code-index fallback parity with GitHub. |
| Fathom | Add scheduled polling every 30-60 minutes, or every 15 minutes during work hours if meeting freshness is core to the pilot. |

## Product/UI implications

- The Phase 41 chrome should remain ambient: `sources updated ...`, not `all synced`.
- `last synced ...` is misleading unless it is backed by provider-level sync-success state.
- A future source-health model should compute, persist, and display per-provider:
  - `last_event_at`
  - `last_success_at`
  - `last_error`
  - `needs_reauth`
  - `stale_reason`
  - `next_expected_check_at`
- The chrome can then truthfully show:
  - `sources updated 10m ago`
  - `syncing jira`
  - `slack needs reauth`
  - `gitlab stale`

## Follow-up work candidates

1. Build a source-health table/API and dashboard chrome reader.
2. Add Jira and Linear 15-minute incremental fallback reconciliation.
3. Add GitLab hourly MR reconciliation and GitLab code-index fallback.
4. Add scheduled Fathom polling.
5. Rename or migrate Slack `include_dms` to a clearer user-token polling setting, or keep the key but surface clearer UI copy.
6. Create a first-team onboarding runbook with sync verification steps and webhook test events.

