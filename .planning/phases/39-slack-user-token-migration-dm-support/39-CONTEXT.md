# Phase 39: Slack User Token Migration & DM Support - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace bot-token-only Slack integration with user-token-based polling that reads channels, private channels, DMs, and group DMs. Eliminate the need for bot invites and enable DM ingestion. Keep bot webhooks running during transition (dual mode), with full bot deprecation as a later phase.

</domain>

<decisions>
## Implementation Decisions

### Polling Strategy
- Poll every 15 minutes, matching existing huddle/Notion polling cadence
- Incremental polling using `oldest` parameter with `last_poll_at` timestamp in integration config
- Poll all monitored conversations in a single sweep per cycle (no staggering)
- 7-day backfill on first connect — fetch last 7 days of message history when user token is first stored
- Reuse existing `SlackMessage` table and upsert-on-conflict logic — polled messages are indistinguishable from webhook-ingested ones
- Same embedding queue and graph extraction pipeline for polled messages

### DM Privacy & Selection
- Ask during onboarding/settings: explicit consent step — "Do you want to include DMs?"
- Simple checkbox/toggle — NOT a per-conversation picker
- When enabled, ALL DMs (1:1 and group DMs) are included, no exclusion list
- Brief inline privacy note near the toggle: "DM messages will be indexed for context generation. Only you can see this data."
- DMs and group DMs displayed in the same list, labeled by participant names
- UI/UX for the toggle should get a proper design critique (use Interface Craft) during implementation

### Migration Path
- Dual mode: keep bot webhooks running for existing channel messages while adding user-token polling
- Bot deprecation is a separate future phase — not in scope here
- Store user token alongside bot token in Vault (different key names)
- Force re-auth for existing users: if no user token exists, show integration as "needs update" and require re-authorization
- Slack app OAuth scopes already configured: user scopes for channels:read, channels:history, groups:read, groups:history, im:read, im:history, mpim:read, mpim:history, users:read, users:read.email

### Conversation Type Handling
- NO channel picker — remove the existing channel selection UI entirely
- With user tokens, all channels the user is in are monitored by default
- DMs are the only thing that requires explicit opt-in (toggle)
- Remove the <10 character message filter — short messages like "no", "done", "approved" are meaningful signal
- Keep other filters: no bot messages, no system messages (join/leave/topic)
- Same filtering rules apply across all conversation types (channels, DMs, group DMs)

### Claude's Discretion
- Polling worker implementation details (add to existing `run_polling_fallback` or separate worker)
- User token vault key naming convention
- OAuth exchange code changes to capture `authed_user.access_token`
- How to handle Slack API rate limits during polling (429 + Retry-After)
- Frontend component structure for the DM toggle

</decisions>

<specifics>
## Specific Ideas

- Reuse `poll_huddle_transcripts()` pattern from `slack_huddles.py` as the template for the polling service — same incremental timestamp tracking, same config storage pattern
- The `conversations.history` API works uniformly for channels, DMs, and group DMs — just pass the conversation ID
- `conversations.list` with `types=public_channel,private_channel,im,mpim` returns all conversation types in one call
- Existing `SlackMessage` table already has `channel_id` which works for DM conversation IDs too

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `slack_huddles.py:poll_huddle_transcripts()` — closest polling pattern, uses `last_huddle_poll_at` in config
- `slack_events.py:_handle_message()` — upsert logic with embedding + graph extraction, reuse directly
- `slack_channels.py:list_channels()` — extend to support `types=im,mpim` parameter
- `slack_oauth.py:exchange_code()` — needs update to capture `authed_user.access_token` from response
- `vault.py:store_token/read_token` — reuse for user token storage
- `sync_scheduler.py:run_polling_fallback()` — add Slack message polling to existing loop

### Established Patterns
- Integration config JSONB for polling state (`workspace_integrations.config`)
- Background task pattern with `_supervised()` crash recovery in `main.py`
- Upsert-on-conflict for idempotent message ingestion

### Integration Points
- `run_polling_fallback()` in sync_scheduler.py — add Slack message polling call
- `slack_oauth.py:exchange_code()` — store user token from `authed_user.access_token`
- `slack_oauth.py:build_auth_url()` — add user scopes to OAuth URL
- Frontend: Slack integration settings section — replace channel picker with DM toggle
- Onboarding wizard step-sources.tsx — add DM consent question

</code_context>

<deferred>
## Deferred Ideas

- Full bot token deprecation — remove Events API webhook endpoint and bot scopes entirely (future phase)
- Per-conversation exclusion list for DMs — if users want to exclude specific DMs
- Configurable polling frequency per workspace
- Deeper backfill option (30d/90d) as user-triggered action

</deferred>

---

*Phase: 39-slack-user-token-migration-dm-support*
*Context gathered: 2026-04-22*
