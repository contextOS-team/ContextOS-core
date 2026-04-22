# Phase 39: Slack User Token Migration & DM Support - Context

**Gathered:** 2026-04-22
**Revised:** 2026-04-22 (post-research — scope narrowed due to Slack rate limit constraint)
**Status:** Ready for planning

<domain>
## Phase Boundary

Add DM and group DM ingestion to the Slack integration via user-token polling, while keeping the existing bot-token webhook path for channel messages. Phase scope is **DMs + OAuth dual-token capture**, not channel migration.

**Why not migrate channels too:** Slack's May 29, 2025 rate limit change caps `conversations.history` at 1 req/min for non-Marketplace apps. User-token polling is not viable for channels at scale — bot Events API webhooks remain the only workable path for channels.

</domain>

<decisions>
## Implementation Decisions

### Scope (Option A — post-research decision)
- **DMs + group DMs:** user-token polling (new path)
- **Channels (public + private):** stay on existing bot Events API webhooks (unchanged)
- Bot invites to channels still required — this phase does not eliminate that friction
- "Full user-token migration" is NOT in scope and likely never viable given Slack policy

### Polling Strategy (DMs only)
- Poll every 15 minutes, matching existing huddle/Notion polling cadence
- Incremental polling using `oldest` parameter with `last_poll_at` timestamp in integration config
- Poll all monitored DM conversations in a single sweep per cycle (no staggering) — low N keeps it within rate budget
- 7-day backfill on first DM opt-in — fetch last 7 days of DM history when user enables DMs
- Reuse existing `SlackMessage` table and upsert-on-conflict logic — polled DM messages use same schema as webhook-ingested channel messages
- Same embedding queue and graph extraction pipeline for polled DM messages
- Use `users.conversations` with `types=im,mpim` to enumerate only the user's own DMs (not `conversations.list` which sees everything)

### DM Privacy & Selection
- Ask during onboarding/settings: explicit consent step — "Do you want to include DMs?"
- Simple checkbox/toggle — NOT a per-conversation picker
- When enabled, ALL DMs (1:1 and group DMs) are included, no exclusion list
- Brief inline privacy note near the toggle: "DM messages will be indexed for context generation. Only you can see this data."
- DMs and group DMs displayed in the same list, labeled by participant names
- UI/UX for the toggle should get a proper design critique (use Interface Craft) during implementation

### OAuth & Token Storage
- Update `build_auth_url` to include `user_scope` parameter (currently hardcoded empty)
- Update `exchange_code` to capture `authed_user.access_token` from Slack's response
- Store user token alongside bot token in Vault (different key names)
- Force re-auth for existing users: if no user token exists, show integration as "needs update" and require re-authorization
- User scopes needed: `im:read`, `im:history`, `mpim:read`, `mpim:history`, `users:read`, `users:read.email` (only DM-related scopes — not channels/groups since bot still handles those)

### Channel Handling (unchanged)
- Keep existing channel picker UI — bot still needs invites, user still needs to pick channels
- Existing bot webhook handler continues to ingest channel messages as-is
- No change to channel message filtering rules
- Remove the <10 character message filter across ALL paths (channel webhooks + DM polling) — short messages like "no", "done", "approved" are meaningful signal
- Keep other filters: no bot messages, no system messages (join/leave/topic)

### Claude's Discretion
- Polling worker implementation details (add to existing `run_polling_fallback` or separate worker)
- User token vault key naming convention
- Exact re-auth UX copy and flow
- How to handle Slack API rate limits during DM polling (429 + Retry-After)
- Frontend component structure for the DM toggle

</decisions>

<specifics>
## Specific Ideas

- Reuse `poll_huddle_transcripts()` pattern from `slack_huddles.py` as the template for the DM polling service — same incremental timestamp tracking, same config storage pattern, same 429/Retry-After handling
- Use `users.conversations` with `types=im,mpim` + user token — returns only DMs the user is actually in (avoids seeing every conversation in the workspace)
- `conversations.history` works uniformly for DM and group DM IDs — same call shape as channels
- Existing `SlackMessage` table already has `channel_id` which works for DM conversation IDs too
- `uq_slack_msg` unique constraint + `on_conflict_do_update` handles dual-path ingest idempotency automatically

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `slack_huddles.py:poll_huddle_transcripts()` — closest polling pattern, uses `last_huddle_poll_at` in config
- `slack_events.py:_handle_message()` — upsert logic with embedding + graph extraction, reuse directly for DM messages
- `slack_oauth.py:exchange_code()` — needs update to capture `authed_user.access_token` from response
- `slack_oauth.py:build_auth_url()` — needs `user_scope` parameter added (currently hardcoded empty)
- `vault.py:store_token/read_token` — reuse for user token storage (new key name)
- `sync_scheduler.py:run_polling_fallback()` — add DM polling to existing loop

### Established Patterns
- Integration config JSONB for polling state (`workspace_integrations.config`)
- Background task pattern with `_supervised()` crash recovery in `main.py`
- Upsert-on-conflict for idempotent message ingestion (works cross-path)

### Integration Points
- `run_polling_fallback()` in sync_scheduler.py — add DM polling call
- `slack_oauth.py:exchange_code()` — store user token from `authed_user.access_token`
- `slack_oauth.py:build_auth_url()` — add user scopes to OAuth URL
- Frontend: Slack integration settings — add DM toggle (keep existing channel picker)
- Onboarding wizard step-sources.tsx — add DM consent question

### Explicitly Out of Scope
- No changes to channel ingestion path (`slack_events.py` webhook handler)
- No removal of channel picker UI
- No bot scope changes
- No migration of existing channel messages

</code_context>

<deferred>
## Deferred Ideas

- Full user-token migration for channels — blocked by Slack rate limit policy; likely never viable
- Removing the channel picker UI — keep for now; channels still need bot invites
- Per-conversation exclusion list for DMs — if users want to exclude specific DMs
- Configurable polling frequency per workspace
- Deeper backfill option (30d/90d) as user-triggered action
- Smart hybrid mode (user token for channels bot isn't in) — complexity not justified for v1

</deferred>

---

*Phase: 39-slack-user-token-migration-dm-support*
*Context gathered: 2026-04-22*
*Revised: 2026-04-22 — scope narrowed to DM-only polling after research surfaced Slack's May 2025 rate limit policy change*
