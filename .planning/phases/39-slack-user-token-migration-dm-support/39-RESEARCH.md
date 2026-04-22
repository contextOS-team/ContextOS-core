# Phase 39: Slack User Token Migration & DM Support - Research

**Researched:** 2026-04-22
**Domain:** Slack OAuth v2 user-token migration, polling-based message ingestion (channels/DMs/group-DMs), dual bot+user token storage
**Confidence:** HIGH

> ## ⚠ SUPERSEDED NOTICE — 2026-04-22 CONTEXT.md revision
>
> Parts of this research document were written against an earlier CONTEXT.md that
> planned to remove the channel picker UI and migrate all conversation types to
> user-token polling. CONTEXT.md was revised later on 2026-04-22 after the
> May-2025 Slack rate-limit policy (1 rpm + limit=15 for non-Marketplace apps)
> surfaced: channels now stay on the bot Events API webhook path indefinitely,
> and the channel picker UI is RETAINED. Only DMs and group DMs are moved to
> user-token polling.
>
> **Concrete supersessions (authoritative source: 39-CONTEXT.md revised 2026-04-22):**
>
> 1. **Conversation Type Handling** block in "Locked Decisions" below is OBSOLETE.
>    The bullet `NO channel picker — remove the existing channel selection UI entirely`
>    is WRONG. Correct decision: the channel picker UI is KEPT. Bot still monitors
>    selected channels via Events API. Only DMs are opt-in.
>
> 2. **SLACK-USR-06** ("Remove channel picker UI") in the Phase Requirements table
>    is DROPPED. The channel picker is no longer removed, so that requirement does
>    not exist for Phase 39. Plans 39-01 through 39-04 correctly omit it.
>
> 3. **User scopes** described anywhere below as including `channels:read, channels:history,
>    groups:read, groups:history` are WRONG for this phase. CONTEXT.md locks
>    user scopes to DM-only: `im:read, im:history, mpim:read, mpim:history, users:read,
>    users:read.email`. Plan 39-01 implements this DM-only scope set. Do NOT
>    include channels/groups user scopes even for "future-proofing".
>
> 4. **"Primary recommendation"** in the Summary (option (b) hybrid: bot for
>    channels, user-token poll for DMs) remains the chosen direction — that part
>    is NOT superseded. The dual-mode architecture is correct.
>
> The Locked Decisions / Architecture / Pitfall sections that describe channel
> enumeration, `conversations.list` with `public_channel,private_channel` types,
> and the `is_member` filter are RESEARCH REFERENCE ONLY — the production code
> path for Phase 39 enumerates ONLY `im,mpim` via `users.conversations`. See
> Plans 39-01 / 39-02 for the authoritative polling behavior.

## Summary

Phase 39 replaces the bot-only Slack integration with a user-token-based polling pipeline that reads every conversation the authenticated user can see — public channels, private channels, DMs, and group DMs — in a single sweep every 15 minutes. The user token is captured from the existing OAuth v2 flow by adding `user_scope` parameters; Slack returns the user token inside `authed_user.access_token` on the same `oauth.v2.access` response that already returns the bot token. Both tokens are stored in Supabase Vault under distinct names; the bot token stays live for existing channel Events API ingestion during the dual-mode transition.

The single biggest external risk is a Slack policy change effective **May 29, 2025**: for "non-Marketplace commercially distributed" apps (which is ContextOS today — commercial product, not on Slack Marketplace, distributed to customers), `conversations.history` and `conversations.replies` are rate-limited to **1 request per minute** with a **max limit=15 messages per call** on all new installations. Existing installs from before May 29, 2025 are grandfathered at the old Tier-3 limits. This dictates polling strategy: per-conversation calls are unacceptable if a workspace has 100+ conversations. The plan must either (a) get ContextOS on Slack Marketplace, (b) keep using Events API for channels and only poll DMs via user token (DMs are typically single-digit counts per user), or (c) design the polling cadence around the 1-rpm cap (budget: ~60 conversations/min/workspace at limit=15).

**Primary recommendation:** Go with option (b) hybrid design — keep the bot Events API webhook running for channel messages (zero rate-limit cost, real-time), and ONLY use user-token polling for DMs and group DMs (small N per user, well under the 1-rpm cap). This aligns exactly with CONTEXT.md's "dual mode" decision and turns a potential deal-breaker into a non-issue. Channel-list enumeration uses the separate `conversations.list` method (Tier 2, not affected by the non-Marketplace cap).

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Polling Strategy**
- Poll every 15 minutes, matching existing huddle/Notion polling cadence
- Incremental polling using `oldest` parameter with `last_poll_at` timestamp in integration config
- Poll all monitored conversations in a single sweep per cycle (no staggering)
- 7-day backfill on first connect — fetch last 7 days of message history when user token is first stored
- Reuse existing `SlackMessage` table and upsert-on-conflict logic — polled messages are indistinguishable from webhook-ingested ones
- Same embedding queue and graph extraction pipeline for polled messages

**DM Privacy & Selection**
- Ask during onboarding/settings: explicit consent step — "Do you want to include DMs?"
- Simple checkbox/toggle — NOT a per-conversation picker
- When enabled, ALL DMs (1:1 and group DMs) are included, no exclusion list
- Brief inline privacy note near the toggle: "DM messages will be indexed for context generation. Only you can see this data."
- DMs and group DMs displayed in the same list, labeled by participant names
- UI/UX for the toggle should get a proper design critique (use Interface Craft) during implementation

**Migration Path**
- Dual mode: keep bot webhooks running for existing channel messages while adding user-token polling
- Bot deprecation is a separate future phase — not in scope here
- Store user token alongside bot token in Vault (different key names)
- Force re-auth for existing users: if no user token exists, show integration as "needs update" and require re-authorization
- ~~Slack app OAuth scopes already configured: user scopes for `channels:read, channels:history, groups:read, groups:history, im:read, im:history, mpim:read, mpim:history, users:read, users:read.email`~~
  - **SUPERSEDED 2026-04-22:** Per revised CONTEXT.md, user scopes are DM-only:
    `im:read, im:history, mpim:read, mpim:history, users:read, users:read.email`.
    Channels/groups user scopes are NOT requested. Bot still handles channels via Events API.

**Conversation Type Handling** ⚠ ENTIRE BLOCK SUPERSEDED 2026-04-22 — see notice at top of file.

The bullets below were the ORIGINAL research interpretation. They have been OVERRIDDEN by the revised CONTEXT.md:

- ~~NO channel picker — remove the existing channel selection UI entirely~~ → **SUPERSEDED.** Channel picker UI stays.
- ~~With user tokens, all channels the user is in are monitored by default~~ → **SUPERSEDED.** Bot continues to monitor bot-invited channels via Events API; channel picker is NOT removed.
- DMs are the only thing that requires explicit opt-in (toggle) → **Still correct** (only bullet in this block that survives).
- Remove the <10 character message filter — short messages like "no", "done", "approved" are meaningful signal → **Still correct.**
- Keep other filters: no bot messages, no system messages (join/leave/topic) → **Still correct.**
- ~~Same filtering rules apply across all conversation types (channels, DMs, group DMs)~~ → **Partially correct.** Filtering rules are identical in the two paths, but the paths themselves are distinct: channels = Events API webhook (slack_events.py), DMs = user-token poll (slack_messages.py, new).

### Claude's Discretion

- Polling worker implementation details (add to existing `run_polling_fallback` or separate worker)
- User token vault key naming convention
- OAuth exchange code changes to capture `authed_user.access_token`
- How to handle Slack API rate limits during polling (429 + Retry-After)
- Frontend component structure for the DM toggle

### Deferred Ideas (OUT OF SCOPE)

- Full bot token deprecation — remove Events API webhook endpoint and bot scopes entirely (future phase)
- Per-conversation exclusion list for DMs — if users want to exclude specific DMs
- Configurable polling frequency per workspace
- Deeper backfill option (30d/90d) as user-triggered action

## Phase Requirements

Phase 39 has no explicit REQ IDs in REQUIREMENTS.md (roadmap marks "Requirements: TBD"). Derived from success criteria and CONTEXT.md:

| ID | Description | Research Support |
|----|-------------|------------------|
| SLACK-USR-01 | OAuth flow captures and stores the user token alongside the bot token | `oauth.v2.access` returns both on one response (section: OAuth Flow Changes); Vault multi-key pattern already used for `bot_access` — mirror as `user_access` |
| SLACK-USR-02 | Polling service fetches new messages from DMs and group DMs using the user token (channels stay on Events API bot webhook) | `conversations.history` with user token reads any conversation the user is in (section: Rate Limit Strategy); reuse `poll_huddle_transcripts()` pattern verbatim |
| SLACK-USR-03 | Users can select DM/group-DM opt-in (DMs off by default) | Integration config JSONB `include_dms: bool` flag; `users.conversations` filter `types=im,mpim` when enabled |
| SLACK-USR-04 | Existing channel message ingestion continues working during migration; SET-clause parity between bot webhook upsert and user-token poll upsert prevents dual-path data corruption | Dual-mode: bot Events API webhook stays live; user-token polling is additive; dedup by `uq_slack_msg` constraint handles any overlap |
| SLACK-USR-05 | Force re-auth for users without user token | Status endpoint returns `needs_reauth=true` when OAuthToken row has no `user_access_token` ref; frontend shows amber "Update required" state |
| ~~SLACK-USR-06~~ | ~~Remove channel picker UI~~ | **DROPPED 2026-04-22 per revised CONTEXT.md.** Channel picker UI stays. Plans 39-01 through 39-04 correctly omit this requirement. |
| SLACK-USR-07 | Remove the <10 character message filter across ALL ingestion paths (channel webhook + DM poll) | `slack_events._should_filter` drops the length check; `slack_messages` reuses `_should_filter` so the change applies uniformly |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | (already pinned) | Slack Web API HTTP client | Already used by every Slack service (`slack_huddles`, `slack_channels`, `slack_oauth`); keep consistency |
| SQLAlchemy async + SQLModel | (already pinned) | Database ORM for `SlackMessage`, `OAuthToken`, `WorkspaceIntegration` | Established pattern; use `pg_insert().on_conflict_do_update` for idempotent upserts |
| Supabase Vault (via `vault.store_token`/`read_token`) | — | Encrypted storage for both bot and user tokens | Already wired for bot tokens; same helper covers user tokens with a different `token_name` |
| FastAPI `BackgroundTasks` / `asyncio.create_task` | — | Polling loop scheduling | Mirrors `run_polling_fallback` + `_supervised` wrapper in `main.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| existing `embedding.queue_embedding_generation` | — | Queue Slack messages for embedding | Called after each upsert — same call as `slack_events._handle_message` |
| existing `graph_extractor.extract_and_populate_graph` | — | Entity/decision extraction from polled messages | Called after upsert for full parity with webhook-ingested messages |
| existing `identity_resolution.fetch_slack_roster` | — | Roster seeding — already called during OAuth | Continue using bot token; user token would also work but no reason to change |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx direct calls | `slack-sdk` Python (async `AsyncWebClient`) | Cleaner API, built-in rate-limit retry, but none of our 4 existing Slack services use it — introducing a new dependency just for Phase 39 adds inconsistency; defer to a cross-cutting "adopt slack-sdk" refactor |
| Single polling loop | Per-workspace `asyncio.gather` for parallel polling | Gather burns the 1-rpm budget instantly on multi-workspace tenants; sequential per workspace is safer |
| `conversations.history` with `limit=200` | `limit=15` (safe for non-Marketplace cap) | If ContextOS's Slack app is classified as non-Marketplace commercial, NEW installs get `limit=15` hard-capped. Existing install is grandfathered. See Rate Limit Strategy. |

**No new packages required** — the entire phase reuses existing dependencies.

## Architecture Patterns

### Recommended Project Structure

```
backend/src/services/
├── slack_oauth.py        # [MODIFY] build_auth_url: add user_scope (DM-only); exchange_code: capture authed_user.access_token; new get_user_token() helper
├── slack_messages.py     # [NEW] poll_user_messages() — mirrors slack_huddles.poll_huddle_transcripts()
├── slack_channels.py     # [KEEP] — conversations.list helper (unchanged — channel picker stays per CONTEXT.md revision)
├── slack_events.py       # [MINOR] remove <10-char filter from _should_filter()
└── sync_scheduler.py     # [MODIFY] add Slack DM polling call inside run_polling_fallback (module-level import of poll_user_messages)

backend/src/routers/
└── slack.py              # [MODIFY] add GET /status → include needs_reauth, include_dms; POST /dms/toggle; callback → store user token; /channels endpoints UNTOUCHED

apps/web/src/
├── app/dashboard/settings/tabs/integration-cards.tsx  # [MODIFY] KEEP <SlackChannels/>, ADD <SlackDmToggle/> + <SlackReauthBanner/>
├── app/dashboard/integrations/slack-dm-toggle.tsx     # [NEW] small toggle component
├── app/dashboard/integrations/slack-reauth-banner.tsx # [NEW] amber reconnect banner
├── components/onboarding/step-sources.tsx             # [MODIFY] post-connect Slack panel shows DM consent
└── lib/api.ts                                          # [MODIFY] add toggleSlackDms(enabled) client
```

### Pattern 1: Dual-Token Vault Storage
**What:** Store bot token under `oauth_slack_{ws}_bot_access` and user token under `oauth_slack_{ws}_user_access`.
**When to use:** Every Slack OAuth exchange after the user_scope change.
**Example:**
```python
# Source: existing slack_oauth.py + CONTEXT.md "store user token alongside bot token"
bot_token_value = data["access_token"]
user_token_value = data.get("authed_user", {}).get("access_token")
slack_user_id = data.get("authed_user", {}).get("id")

bot_name = token_name(Provider.SLACK, workspace_id, "bot_access")
await store_token(session, bot_name, bot_token_value)

if user_token_value:
    user_name = token_name(Provider.SLACK, workspace_id, "user_access")
    await store_token(session, user_name, user_token_value)

# Store slack_user_id in integration.config so polling knows whose conversations to pull
config["slack_user_id"] = slack_user_id
```

### Pattern 2: Incremental Polling with `oldest`
**What:** Store `last_user_poll_at` as a Slack timestamp (float string like `"1712345678.000000"`) in `integration.config`, pass it as `oldest` on next `conversations.history` call.
**When to use:** Every poll cycle.
**Example:**
```python
# Source: docs.slack.dev/reference/methods/conversations.history + existing slack_huddles.py pattern
params = {"channel": conv_id, "limit": 15, "inclusive": "false"}
if last_poll_ts:
    params["oldest"] = last_poll_ts
response = await client.get(f"{SLACK_API_BASE}/conversations.history",
                             params=params, headers={"Authorization": f"Bearer {user_token}"})
# After success, persist the LATEST message's ts as the new last_user_poll_at
# IMPORTANT: capture this BEFORE the next poll cycle so overlap window is minimized
```

Caveat: the Slack `oldest` parameter is an open boundary by default (messages strictly after the ts). Combined with upsert-on-conflict (`uq_slack_msg`), an inclusive check is safe either way — dedup is handled at the DB layer.

### Pattern 3: Conversation Enumeration Per Poll ⚠ SUPERSEDED 2026-04-22
**What (ORIGINAL RESEARCH):** Call `conversations.list` with `types=public_channel,private_channel` (always) and append `,im,mpim` IFF `include_dms=true`. Then iterate the returned IDs.
**Current (Phase 39 implementation):** Call `users.conversations` with `types=im,mpim` ONLY when `include_dms=true`. Public and private channels are NOT enumerated from the poll path — they are handled by the bot Events API webhook. Do NOT follow the original pattern below; Plan 39-02 is authoritative.
```python
# ⚠ Historical reference only — Phase 39 does NOT enumerate channels in the poll path.
# types = ["public_channel", "private_channel"]
# if config.get("include_dms"):
#     types += ["im", "mpim"]
# params = {"types": ",".join(types), ...}
```
**Correct Phase 39 code (see 39-02 interfaces block):**
```python
params = {"types": "im,mpim", "exclude_archived": "true", "limit": 200}
# GET https://slack.com/api/users.conversations (user token) — DMs + group DMs only.
```

### Pattern 4: Supervised Background Worker
**What:** Add Slack user-message polling to the existing `run_polling_fallback()` loop. No new task required; the loop already runs every 15 min and is wrapped by `_supervised()` in `main.py` which auto-restarts on crash.
**When to use:** For any workspace-scoped periodic job in this codebase.
**Example:**
```python
# Source: existing backend/src/services/sync_scheduler.py pattern
# IMPORTANT (Phase 39): import poll_user_messages at MODULE TOP, not inside the loop.
from src.services.slack_messages import poll_user_messages

async def run_polling_fallback() -> None:
    while True:
        try:
            # ... existing Notion, GitHub, Slack digests ...
            slack_workspaces = await _get_connected_workspaces(Provider.SLACK)
            for ws_id in slack_workspaces:
                try:
                    async with async_session() as session:
                        await poll_user_messages(session, ws_id)
                except Exception:
                    logger.exception("Slack user-message poll failed for %s", ws_id)
        except Exception:
            logger.exception("Polling fallback scheduler error")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
```

### Pattern 5: Re-Auth Required State
**What:** `/api/slack/status` endpoint returns `{connected: true, needs_reauth: true}` when the workspace integration exists but no user token is stored. Frontend renders amber "Update required — reconnect to enable DM support" card that triggers the standard `connectSlack()` flow.
**When to use:** Every Slack status fetch.
**Example:**
```python
# Source: CONTEXT.md "Force re-auth for existing users"
user_name = token_name(Provider.SLACK, workspace_id, "user_access")
user_token = await read_token(session, user_name)
return {
    "connected": integration.status == "connected",
    "team_name": integration.external_id,
    "needs_reauth": integration.status == "connected" and user_token is None,
    "include_dms": integration.config.get("include_dms", False),
}
```

### Anti-Patterns to Avoid

- **Parallel per-workspace polling with `asyncio.gather`:** Burns the 1-rpm budget on the first cycle if any workspace is non-Marketplace-capped. Iterate sequentially.
- **Polling `conversations.replies` to hydrate threads:** Phase 30's huddle poller does this for one specific thread per huddle — fine. For general message polling, do NOT walk every thread; ingest top-level messages only and rely on webhook thread events (dual-mode keeps those alive) for replies. Otherwise rate-limit cost explodes by 10-100x.
- **Storing the user token in `OAuthToken.access_token` and the bot token in... where?** The `OAuthToken` table has one `access_token` column (Vault name). Follow the pattern: the `OAuthToken.access_token` column stores the *bot* Vault name (existing behavior); store the user Vault name in a second `OAuthToken.metadata_['user_token_name']` JSONB field, OR simply look up `token_name(..., "user_access")` by convention without a DB pointer. CONTEXT.md picks Vault-key-by-convention; do that.
- **Re-resolving every user ID on every poll cycle:** `_resolve_user_names()` in `slack_huddles.py` caches within one run. For multi-run caching, rely on the already-seeded `identity_resolution` roster table. Don't re-call `users.info` in the poll hot path.
- **Polling DMs when the user hasn't opted in:** Check `config.get("include_dms", False)` before adding `im,mpim` to the `conversations.list` `types` filter. Default is False per CONTEXT.md.
- **Enumerating channels from the user-token path (NEW 2026-04-22):** Per revised CONTEXT.md, channels stay on the bot Events API webhook. The user-token poll enumerates ONLY `im,mpim`. Do not extend to public/private channels without a new phase.
- **Deferred import of `poll_user_messages` inside the scheduler try-block (NEW 2026-04-22):** Makes monkeypatching fragile. Import at module top; tests patch `src.services.sync_scheduler.poll_user_messages`.
- **Divergent SET clauses between webhook and poll upserts (NEW 2026-04-22):** `slack_events._handle_message` and `slack_messages._upsert_messages` MUST use identical `on_conflict_do_update` SET clauses (fields: `text, user_id, thread_ts, parent_ts, is_thread_reply, raw_data`). Mismatch causes silent data corruption when both paths see the same message.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parsing OAuth v2 response for dual tokens | Custom dict parser scattered across `exchange_code` | Keep extraction localized in one place; define helper `_extract_tokens(data)` returning `(bot_token, user_token, user_id, team)` | Slack's response structure is stable but has optional paths (`authed_user` may be absent if user_scope is empty); one place to handle `.get()` defensively |
| Vault key naming | Ad-hoc f-strings | `vault.token_name(Provider.SLACK, ws, "user_access")` | Already includes the legacy-format migration trick in `get_bot_token`; reuse the convention or you'll re-create that bug |
| Rate-limit 429 handling | New retry decorator | Existing pattern in `slack_huddles._find_huddle_messages` (response 429 → read Retry-After → `await asyncio.sleep` → continue loop) | Proven, tested pattern; copy verbatim |
| Message filtering (bots, subtypes) | New filter function | `slack_events._should_filter` minus the `<10 char` line | CONTEXT.md decision — keep other filters, drop only the length filter |
| SlackMessage dedup | Any application-level check | `pg_insert().on_conflict_do_update(constraint="uq_slack_msg", ...)` | Existing `(workspace_id, channel_id, slack_ts)` unique index handles it atomically |
| Incremental cursor storage | A new sync_cursors row | Integration config JSONB field `last_user_poll_at` | Same pattern as `last_huddle_poll_at`, `code_index_last_at`; no schema change |

**Key insight:** Every sub-problem in Phase 39 has a working precedent in the existing Slack services. The phase is 90% composition of patterns already in the codebase and 10% genuinely new work (OAuth response parsing, DM toggle UI).

## Rate Limit Strategy (Critical — HIGH Confidence)

This is the single most important external finding. Slack changed rate limits for non-Marketplace apps on **May 29, 2025**, and clarified the rules on **June 3, 2025**:

| App Classification | `conversations.history` & `conversations.replies` limits |
|--------------------|-----------------------------------------------------------|
| Marketplace-approved app | Tier 3: 50+ req/min, `limit` up to 999 (no change) |
| Custom/internal app (used only within your own org) | Tier 3: 50+ req/min, `limit` up to 999 (no change) |
| Non-Marketplace commercially distributed app — **existing install before May 29, 2025** | Grandfathered at Tier 3 (no change) |
| Non-Marketplace commercially distributed app — **new install on/after May 29, 2025** | **1 req/min per workspace, max `limit`=15** |

**ContextOS classification:** Commercial product distributed to customers, not on Slack Marketplace → falls into the "non-Marketplace distributed" bucket. New installs get the tight cap; the founding-team dogfood install (created in v1.0, pre-Feb-2026) is also post-May-2025, so is ALSO capped unless ContextOS is treated as an internal custom app. Slack's classification is based on *distribution*, not a developer declaration — if other teams outside the founding team install the same app, it's distributed.

**What this means for Phase 39's polling design:**

Given the 1-rpm cap with limit=15:
- Workspace with 20 active channels + 5 DMs = 25 conversations → needs 25 minutes per full poll cycle → breaks the 15-minute cadence for capped installs.
- Workspace with 5 DMs only (channels via Events API) = 5 conversations → 5 minutes per cycle → fits comfortably.

**Recommended architecture** (matches CONTEXT.md's dual-mode decision):

1. **Channels via Events API (bot webhook)** — free, real-time, not rate-limited (Events API delivery limits are much higher and separate from `conversations.history` quotas). The bot stays invited to channels it was already in; no new invites required for Phase 39.
2. **DMs + group DMs via user-token polling** — small N (typically 5-20 per user), well within the 1-rpm cap even if classified as non-Marketplace-distributed.
3. **Channel enumeration via `conversations.list`** — Tier 2 (20+ req/min), NOT affected by the non-Marketplace cap. Use this to *discover* conversations; polling then iterates only the DM/mpim IDs.

This reframes Phase 39 from "replace the bot" to "add user-token polling for DMs on top of the existing bot." The bot deprecation phase mentioned in CONTEXT.md "Deferred Ideas" can only happen safely if ContextOS either (a) gets Marketplace approval, or (b) migrates to `conversations.list` + Events API subscriptions for all conversation types (Events API DOES support DMs via `message.im` and `message.mpim` event types with user-token-authenticated app installs).

**Alternative if user prefers polling-only channels too:** Either apply for Slack Marketplace (multi-month approval process), or accept that capped workspaces with many channels will poll slowly (e.g., 25 channels = 25 minutes). CONTEXT.md already said dual mode, so this phase goes dual.

**Rate-limit handling code** (every Slack API call in the poll path must include this):
```python
# Source: slack_huddles.py:_find_huddle_messages — proven pattern
if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", "1"))
    logger.warning("Slack rate limited on %s, retrying after %ds", method, retry_after)
    await asyncio.sleep(retry_after)
    continue  # retry same request
```

## Common Pitfalls

### Pitfall 1: Empty `authed_user` in OAuth response when user_scope was not sent
**What goes wrong:** `data["authed_user"]["access_token"]` raises `KeyError` because OAuth was initiated with `user_scope=""` (current `build_auth_url` literally hardcodes this).
**Why it happens:** Slack only returns `authed_user.access_token` when the initial authorize URL included at least one `user_scope` value.
**How to avoid:** Update `build_auth_url` FIRST to send `user_scope=im:read,im:history,mpim:read,mpim:history,users:read,users:read.email` (DM-only per revised CONTEXT.md). Then update `exchange_code` to read `authed_user.access_token` via `.get()` with None fallback.
**Warning signs:** `needs_reauth=true` for every workspace after deploy, or `KeyError: 'authed_user'` in logs.

### Pitfall 2: Existing workspaces have OAuth sessions tied to old scopes
**What goes wrong:** Existing users' `OAuthToken` rows have the old bot-only scope set; their bot tokens work but they have no user token. Polling silently does nothing.
**Why it happens:** Slack OAuth scope changes are not retroactive — the user must re-authorize.
**How to avoid:** Implement the `needs_reauth` status flag (Pattern 5) and show a prominent banner in settings + onboarding. The `connectSlack()` URL-redirect flow handles the re-authorization correctly as long as Pitfall 1 is fixed.
**Warning signs:** Silent zero-ingest for pre-deploy workspaces.

### Pitfall 3: `slack_user_id` drift — polling uses wrong user's perspective
**What goes wrong:** The user token is scoped to the *individual who authorized* — if the workspace owner changes, or the original authorizer leaves the company, the user token eventually becomes invalid (token revoked when user deactivated).
**Why it happens:** User tokens are tied to a specific Slack user; their conversations.list and conversations.history views differ per person.
**How to avoid:** Store `authed_user.id` in `integration.config.slack_user_id`. On 401/`invalid_auth` during polling, mark the integration as `needs_reauth` and stop polling for that workspace until someone reconnects. Log the failure loudly.
**Warning signs:** HTTP 401 or `{"error": "invalid_auth"}` responses during polling, especially for older workspaces.

### Pitfall 4: Token rotation surprises
**What goes wrong:** If token rotation is enabled at the Slack app level, user tokens expire every 12 hours and need refresh via `oauth.v2.access` with `grant_type=refresh_token`. Without a refresh pipeline, polling stops working after 12h.
**Why it happens:** Rotation is opt-in at the Slack app config level — NOT enabled by default. If the app has it disabled, tokens don't expire.
**How to avoid:** Check the current ContextOS Slack app settings — rotation should remain DISABLED for this phase (bot tokens don't rotate either in the current setup, and Phase 39 is additive). If rotation is somehow enabled on the Slack app, build the refresh pipeline (store refresh_token in Vault under `user_refresh`, detect `expires_in`, schedule refresh at T-5min). Linear's `refresh_access_token` is the precedent.
**Warning signs:** User token works for 12 hours then every call returns `token_expired`.

### Pitfall 5: DM ingestion creates missing-channel-metadata gaps
**What goes wrong:** `SlackMessage.channel_name` is stored as NULL for polled messages (existing events code leaves it NULL too). For DMs, `channel_id` like `D0123ABCDEF` has no human-readable name — the UI shows "DM in D0123ABCDEF" which is useless.
**Why it happens:** `channel_name` enrichment was always deferred.
**How to avoid:** At first poll for a DM channel ID starting with `D`, call `conversations.info` once and cache `user` (other participant's Slack user ID) → resolve through `identity_resolution.ResolvedIdentity` → display-name. Store in `integration.config.dm_names_cache: {channel_id: "Alice Smith"}` keyed by Slack channel ID. Refresh lazily.
**Warning signs:** Context pages show raw `D0123ABCDEF` or opaque IDs in source attributions.

### Pitfall 6: `conversations.list` pagination with mixed types returns huge pages
**What goes wrong:** Passing all four types `public_channel,private_channel,im,mpim` with `limit=200` in a large Slack org returns thousands of channels that the user is NOT a member of (for public_channel). Polling iterates them all and hits 404/`not_in_channel` errors.
**Why it happens:** `conversations.list` with a user token returns all conversations the user *can see*, which for public channels means all non-archived public channels in the workspace.
**How to avoid:** For Phase 39, this pitfall is avoided by design: the poll path uses `users.conversations` with `types=im,mpim` (DM-only). No public channels are enumerated. If a future phase extends to channels, prefer `users.conversations` (is_member implicit) over `conversations.list` + client-side filter.
**Warning signs:** `conversations.history` calls returning `not_in_channel` errors en masse; polling time grows linearly with workspace size.

### Pitfall 7: Overlap between bot-delivered and user-polled messages
**What goes wrong:** During dual-mode, a new channel message arrives via the bot webhook AND via the user-token poll. Two insert attempts race.
**Why it happens:** That's exactly what dual-mode looks like.
**How to avoid:** The existing `uq_slack_msg = (workspace_id, channel_id, slack_ts)` unique constraint + `on_conflict_do_update` handles this atomically. No extra logic needed — it's already correct. BUT: double-check that the `on_conflict_do_update` SET list in the poll path overwrites the same fields as the events path, so the "last write wins" doesn't corrupt anything. If they set different fields, merge the SET clauses. **Phase 39 enforces SET-clause parity explicitly** — see Plan 39-02's `_upsert_messages` must exactly match `slack_events._handle_message` fields: `text, user_id, thread_ts, parent_ts, is_thread_reply, raw_data`.
**Warning signs:** Sporadic IntegrityError from uq_slack_msg violations during deploy window; silent data drift between webhook- and poll-inserted rows on re-upsert.

### Pitfall 8: 7-day backfill on first connect blows the rate-limit budget
**What goes wrong:** For a capped workspace, fetching 7 days of history across 20 DMs at limit=15 per call could mean 20 DMs × (100 msgs/7d / 15 per call) ≈ 135 requests → 135 minutes just for backfill.
**Why it happens:** The 1-rpm cap applies uniformly, including backfill.
**How to avoid:** Run backfill as a background task (not blocking the OAuth redirect). Show "Syncing Slack history — this may take some minutes" in the UI, similar to Telegram's sync-status pattern in `step-sources.tsx`. For non-capped installs (Marketplace/internal), backfill completes in seconds. Also: cap individual-conversation backfill depth at, say, 100 messages to stay reasonable even for chatty DMs.
**Warning signs:** Users hit "go to dashboard" after OAuth and see no Slack data for 10+ minutes.

## Code Examples

Verified patterns from official sources and existing code:

### Building the OAuth URL with user scopes
```python
# Source: docs.slack.dev/reference/methods/oauth.v2.access, existing slack_oauth.py
# NOTE (SUPERSEDED 2026-04-22): the ORIGINAL research snippet included channels/groups
# user scopes. Per revised CONTEXT.md, Phase 39 uses DM-ONLY user scopes:
SLACK_BOT_SCOPES = "channels:read,channels:history,groups:read,groups:history,users:read,users:read.email,canvases:read,files:read"
SLACK_USER_SCOPES = "im:read,im:history,mpim:read,mpim:history,users:read,users:read.email"

def build_auth_url(state: str, settings: Settings) -> str:
    params = {
        "client_id": settings.SLACK_CLIENT_ID,
        "redirect_uri": settings.slack_redirect_uri,
        "scope": SLACK_BOT_SCOPES,
        "user_scope": SLACK_USER_SCOPES,  # <-- DM-only; no channels:* or groups:* user scopes
        "state": state,
    }
    return f"{SLACK_AUTHORIZE_URL}?{urlencode(params)}"
```

### Parsing dual tokens from oauth.v2.access
```python
# Source: docs.slack.dev/reference/methods/oauth.v2.access
# Response shape (truncated):
# {
#   "ok": true,
#   "access_token": "xoxb-...",           # bot token
#   "scope": "channels:read,...",
#   "team": {"id": "T...", "name": "..."},
#   "authed_user": {
#     "id": "U...",
#     "scope": "channels:history,im:history,...",
#     "access_token": "xoxp-..."          # user token  <-- NEW
#   }
# }

bot_token_value = data["access_token"]
authed_user = data.get("authed_user") or {}
user_token_value = authed_user.get("access_token")
slack_user_id = authed_user.get("id")
```

### Fetching conversations for the authorized user
```python
# Source: docs.slack.dev/reference/methods/users.conversations
# Scopes: im:read, mpim:read (user token) — DM-only per Phase 39.
# NOTE (SUPERSEDED 2026-04-22): original snippet optionally included public_channel,
# private_channel. Phase 39 hard-codes types=im,mpim because channels stay on the
# bot Events API webhook.
params = {
    "types": "im,mpim",
    "exclude_archived": "true",
    "limit": 200,
}
response = await client.get(
    f"{SLACK_API_BASE}/users.conversations",
    params=params,
    headers={"Authorization": f"Bearer {user_token}"},
)
```

### Incremental poll of one conversation
```python
# Source: slack_huddles.py:_find_huddle_messages pattern + docs.slack.dev/reference/methods/conversations.history
async def _poll_conversation(
    client: httpx.AsyncClient,
    user_token: str,
    conv_id: str,
    oldest_ts: str | None,
    limit: int = 200,  # reduce to 15 if non-Marketplace cap applies
) -> list[dict]:
    messages: list[dict] = []
    cursor: str | None = None
    while True:
        params: dict = {"channel": conv_id, "limit": str(limit)}
        if oldest_ts:
            params["oldest"] = oldest_ts
        if cursor:
            params["cursor"] = cursor

        response = await client.get(
            f"{SLACK_API_BASE}/conversations.history",
            params=params,
            headers={"Authorization": f"Bearer {user_token}"},
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "1"))
            await asyncio.sleep(retry_after)
            continue

        if response.status_code != 200:
            logger.error("Slack API %d for %s", response.status_code, conv_id)
            break

        data = response.json()
        if not data.get("ok"):
            err = data.get("error", "unknown")
            if err in ("not_in_channel", "channel_not_found", "missing_scope", "invalid_auth"):
                logger.warning("Skip %s: %s", conv_id, err)
                break
            logger.error("history error for %s: %s", conv_id, err)
            break

        messages.extend(data.get("messages", []))

        if data.get("has_more") and data.get("response_metadata", {}).get("next_cursor"):
            cursor = data["response_metadata"]["next_cursor"]
        else:
            break
    return messages
```

### Upsert polled messages (parity with webhook path)
```python
# Source: existing slack_events._handle_message
# ⚠ SET-clause parity is mandatory (SLACK-USR-04). Fields MUST match webhook path:
#   text, user_id, thread_ts, parent_ts, is_thread_reply, raw_data
from sqlalchemy.dialects.postgresql import insert as pg_insert

for msg in polled_messages:
    if _should_filter_user_token(msg):  # bots, system subtypes — NOT <10 char
        continue
    values = {
        "workspace_id": workspace_id,
        "slack_ts": msg["ts"],
        "channel_id": conv_id,
        "channel_name": None,
        "user_id": msg.get("user"),
        "user_name": None,
        "text": msg.get("text", ""),
        "thread_ts": msg.get("thread_ts"),
        "parent_ts": msg.get("thread_ts") if msg.get("thread_ts") and msg["thread_ts"] != msg["ts"] else None,
        "is_thread_reply": bool(msg.get("thread_ts") and msg["thread_ts"] != msg["ts"]),
        "slack_created_at": _ts_to_datetime(msg["ts"]),
        "raw_data": msg,
    }
    stmt = pg_insert(SlackMessage).values(**values).on_conflict_do_update(
        constraint="uq_slack_msg",
        set_={k: pg_insert(SlackMessage).excluded[k] for k in
              ("text", "user_id", "thread_ts", "parent_ts", "is_thread_reply", "raw_data")},
    )
    await session.execute(stmt)
# after loop: commit once, then queue embeddings in batch
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bot token + Events API covers all channel messages | Bot for channels (via Events API) + user-token polling for DMs/mpim | Phase 39 (this phase) | Eliminates the need to invite the bot to every channel; enables DM ingestion |
| `conversations.history` Tier 3 (50+ rpm) for all apps | Tier 3 for Marketplace/internal; **1 rpm + limit=15 for non-Marketplace distributed** | May 29, 2025 (Slack policy change) | Design must account for tight caps on new commercial installs |
| Long-lived bot tokens (no expiry, no refresh) | Same by default; optional opt-in token rotation (12h expiry, refresh_token) | Feature existed for a while; relevant now that user tokens are also in scope | If rotation is enabled, need refresh pipeline. Default = off. |
| ~~Channel picker UI~~ → ~~No channel picker — user-token polling discovers automatically~~ | **Channel picker KEPT per revised CONTEXT.md (2026-04-22)** — bot still monitors selected channels via Events API; only DM opt-in is new | Phase 39 CONTEXT.md revision | Simpler migration (no existing config churn); rate-limit safe |
| <10 character message filter | No length filter — short replies carry signal | Phase 39 | More messages ingested; embedding/graph pipeline must handle them gracefully (existing code does) |

**Deprecated/outdated:**
- **The current `slack_manifest`'s `user_scope=""`** in `build_auth_url` — this emits an OAuth URL that cannot return a user token, so the CONTEXT.md claim "OAuth scopes already configured" may refer to the Slack app dashboard config, but the code-side URL builder still sends empty `user_scope`. Verify both sides during implementation.
- **`slack_channels.py:list_channels`** hardcoded `types=public_channel,private_channel` — KEEP AS-IS. Phase 39's DM poll uses a separate `users.conversations` call; the existing channel list helper is still used by the channel picker UI (which stays per CONTEXT.md revision).

## Open Questions

1. **Is the ContextOS Slack app classified by Slack as "non-Marketplace commercial" or "internal custom"?**
   - What we know: Not on Slack Marketplace. Currently only installed by the founding team. But commercially positioned for customer distribution per PROJECT.md.
   - What's unclear: Slack's classification is based on distribution behavior — a single-org install defaults to "custom internal"; first install by any other org may flip classification to distributed. There's no UI indicator in the app admin panel; the classification is implicit.
   - Recommendation: Design polling code for the worst case (limit=15, 1 rpm). For internal/Marketplace installs the code still works (just finishes faster). Confirm with Slack support before launching to external customers.

2. **Should we use `users.conversations` (user-only) or `conversations.list` (everything visible)?**
   - What we know: `users.conversations` returns only conversations the user is a member of. `conversations.list` returns all visible — which for public channels means every non-archived public channel in a potentially huge org.
   - What's unclear: Does `users.conversations` have the same 4-type support (`public_channel,private_channel,im,mpim`)? Slack docs suggest yes.
   - Recommendation (2026-04-22 update): **Use `users.conversations` with types=im,mpim ONLY.** Channel enumeration is not part of the Phase 39 poll path per revised CONTEXT.md.

3. **What happens to existing `selected_channels` config and the `SlackChannels` UI?**
   - What we know: CONTEXT.md was revised 2026-04-22 — the channel picker UI STAYS. Existing integration configs keep `selected_channels: [...]` and `available_channels: [...]` arrays.
   - What's unclear: N/A — channel picker remains the source of truth for the Events API webhook filter.
   - Recommendation: No change to `selected_channels` handling. Continue writing to it from the channel picker UI. Keep `slack_events._is_channel_monitored` unchanged.

4. **Do we backfill channels that the user-token newly reveals but the bot isn't in?**
   - Not applicable for Phase 39 as revised — channels are not enumerated from the user-token path. Backfill applies to DMs/mpim only (7-day window, 100-message-per-conversation cap).

5. **How to surface the DM toggle in onboarding without adding a whole new step?**
   - What we know: Onboarding wizard is 4 steps (per STATE.md). Adding a 5th step to "ask about DMs" fights the existing flow.
   - What's unclear: Should DM consent be a post-Slack-OAuth inline panel (like `OnboardingNotionSync` and `OnboardingRepoPicker`), or a modal, or a settings-only concern?
   - Recommendation: Post-connect inline panel in `step-sources.tsx` that appears when Slack just connected, similar to how GitHub's repo picker auto-expands after OAuth redirect. Default toggle = OFF per CONTEXT.md. Use `make-interfaces-feel-better` skill for the UI critique as CONTEXT.md explicitly requests.

## Sources

### Primary (HIGH confidence)
- `backend/src/services/slack_oauth.py` — current OAuth v2 exchange code, Vault token storage, token_name convention
- `backend/src/services/slack_huddles.py` — `poll_huddle_transcripts()` polling template, rate-limit 429 handler, cursor pagination
- `backend/src/services/slack_events.py` — `_should_filter()`, upsert-on-conflict, embedding + graph extraction pipeline
- `backend/src/services/slack_channels.py` — `conversations.list` wrapper
- `backend/src/services/sync_scheduler.py` — `run_polling_fallback()` loop pattern
- `backend/src/main.py` — `_supervised()` worker wrapper
- `backend/src/services/vault.py` — `token_name()` convention and encrypted storage helpers
- `backend/src/services/identity_resolution.py:fetch_slack_roster` — users.list pattern, roster seeding
- [conversations.history | Slack Developer Docs](https://docs.slack.dev/reference/methods/conversations.history) — scopes, parameters, user-vs-bot behavior
- [conversations.list | Slack Developer Docs](https://docs.slack.dev/reference/methods/conversations.list) — type filtering, Tier 2, pagination
- [conversations.replies | Slack Developer Docs](https://docs.slack.dev/reference/methods/conversations.replies) — same rate-limit cap as conversations.history
- [oauth.v2.access | Slack Developer Docs](https://docs.slack.dev/reference/methods/oauth.v2.access) — authed_user.access_token structure
- [Rate limit changes for non-Marketplace apps (May 29, 2025) | Slack Developer Docs](https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps/) — 1 rpm / 15 msg cap, grandfathering rules
- [Clarifying rate limit changes for non-Marketplace apps (June 3, 2025) | Slack Developer Docs](https://docs.slack.dev/changelog/2025/06/03/rate-limits-clarity/) — internal custom apps exempt
- [Using token rotation | Slack Developer Docs](https://docs.slack.dev/authentication/using-token-rotation/) — opt-in rotation, 12h expiry, refresh flow
- [Rate limits | Slack Developer Docs](https://docs.slack.dev/apis/web-api/rate-limits/) — tier definitions, 429 Retry-After handling

### Secondary (MEDIUM confidence)
- [About Slack's new rate limits | APIs You Won't Hate](https://apisyouwonthate.com/newsletter/about-slacks-new-rate-limits/) — third-party summary of May 2025 changes, corroborates primary source
- [How to get a Slack OAuth user access token | Nango Blog](https://nango.dev/blog/how-to-get-slack-user-access-token-oauth/) — third-party walkthrough of dual-token OAuth flow, corroborates oauth.v2.access behavior

### Tertiary (LOW confidence)
- None — all material findings verified against primary Slack documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library is already in use; no new dependencies
- Architecture patterns: HIGH — five precedent patterns in the same codebase (`poll_huddle_transcripts`, `_supervised`, upsert-on-conflict, Vault key convention, rate-limit 429 handler)
- OAuth v2 dual-token flow: HIGH — directly documented at docs.slack.dev, matches existing bot-only code
- Rate-limit strategy: HIGH — authoritative Slack policy source cited with clarification changelog; classification of ContextOS's app is the one open question (Open Question #1)
- Pitfalls: HIGH — derived from existing bot-token code paths + the May 2025 policy change; token rotation / DM metadata gaps are corroborated by Slack docs

**Research date:** 2026-04-22
**Superseded sections noted:** 2026-04-22 (CONTEXT.md revision — channels stay on bot webhook, user scopes DM-only, SLACK-USR-06 dropped)
**Valid until:** 2026-07-22 (90 days — Slack API is stable; the May 2025 rate-limit change is the only recent shift and it's documented. Re-check Slack changelog before launch.)
