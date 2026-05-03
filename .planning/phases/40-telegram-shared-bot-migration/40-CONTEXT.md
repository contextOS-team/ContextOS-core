# Phase 40: Telegram Shared-Bot Migration - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the Phase-26 bring-your-own-bot Telegram flow with a single shared `@ContextOSBot`. New users connect Telegram in one click via a `t.me/<bot>?startgroup=<code>` deep link — pick a group, bot joins, posts a pairing message, ingestion starts. No BotFather, no token paste, no per-workspace webhooks.

**In scope:** Group + supergroup ingestion via the shared bot, pairing-code lifecycle, global webhook routing by `chat_id`, deep-link Connect UX in settings + onboarding, clean cutover replacing Phase-26 code paths.

**Out of scope (locked by ROADMAP):** DMs to the bot, channel-broadcast posts.

</domain>

<decisions>
## Implementation Decisions

### Pairing code lifecycle
- **Format:** 16-character base64url random string (~96 bits entropy). Generated server-side, stored in `telegram_pairing_codes` table.
- **TTL:** 15 minutes from creation (matches roadmap).
- **Single-use:** Code is burned (deleted) on successful claim. No multi-use within window.
- **Cleanup:** Lazy delete — index on `expires_at`; rows removed when consumed or when found expired during a claim attempt. No background sweep needed.
- **Reissue:** UI regenerate button creates a fresh code and invalidates the previous one for that workspace.

### `/start@bot <code>` claim handler (in groups + supergroups only)
- **Valid + unused code:** Insert row into `telegram_chat_workspace` (PK `chat_id`), bot replies with branded confirmation: *"ContextOS connected. Messages in this chat will be indexed for context generation. Manage at <link>."* Burn the code.
- **Expired / invalid / already-used code:** Bot replies in-chat with reason + dashboard link, e.g. *"This pairing link expired. Generate a new one at <link>."* Visible to group members — accepted tradeoff for UX clarity.
- **Chat already claimed by another workspace:** Bot replies *"This chat is already paired with another ContextOS workspace."* Mapping is sticky; ownership requires removing the bot first. **No cross-workspace re-claim allowed.**
- **Chat already claimed by SAME workspace:** Treat as no-op (idempotent), don't burn the code.
- **`my_chat_member` events:** Always log for visibility (per roadmap). On `kicked`/`left`/`banned`, soft-delete the `telegram_chat_workspace` row (or mark inactive). Existing `telegram_messages` retained — re-pair restores ingestion without losing history.

### Deprecation strategy (simplified)
- **No dual-mode, no migration banner, no backfill.** Phase-26 code paths replaced cleanly in this phase.
  - Reason: There are no real Phase-26 production users to migrate; founding team re-pairs their own dogfood workspace manually.
- The legacy per-workspace webhook handler (`/api/telegram/webhook/{workspace_id}`), `connect_telegram_bot()`, `disconnect_telegram_bot()`, BYO-bot UI form, and per-workspace Vault token storage are **removed in this phase**.
- Existing `telegram_messages` rows remain untouched — they're still searchable; the schema is unchanged.
- The new global webhook is the only Telegram entry point after this phase ships.

### Environment variables
- New: `TELEGRAM_BOT_TOKEN_GLOBAL` (shared bot token), `TELEGRAM_BOT_USERNAME` (e.g. `ContextOSBot`, used to render deep links).
- Existing `TELEGRAM_BOT_TOKEN` (Sentry alerts) is kept distinct — do not collapse them.
- Existing `TELEGRAM_WEBHOOK_SECRET` reused for the global webhook secret-token header check.

### Connect UX
- **Surfaces:** Both Settings → Integrations card AND Onboarding `step-sources.tsx` slot. Replace existing `TelegramConnect` (token paste form).
- **Click flow:**
  1. User clicks "Connect via @ContextOSBot".
  2. Frontend calls `POST /api/telegram/pairing-code` → returns `{ code, deep_link, expires_at }`.
  3. Frontend opens `https://t.me/<TELEGRAM_BOT_USERNAME>?startgroup=<code>` in a new tab.
  4. Inline progress block renders: *"Waiting for bot to join a group…"* with countdown to expiry + Cancel + Regenerate buttons.
- **Success detection:** Supabase Realtime subscription on `telegram_chat_workspace` inserts filtered by `workspace_id`. UI flips to "connected" state instantly when the bot's claim handler inserts the mapping row.
- **Failure / expiry detection:** Frontend timer hits `expires_at` → progress block shows "Link expired" + single Regenerate button.

### Filter rules (carried forward from Phase 26)
- Filter out: non-text messages (photos, stickers), bot messages (`from.is_bot`), system join/leave/topic messages.
- Edited messages: upsert via existing `uq_tg_msg(workspace_id, chat_id, message_id)` constraint.
- The current Phase-26 short-message filter is already removed via the existing code path (unchanged here).

### Claude's Discretion
- Exact wording of bot replies (success, expired-code, already-claimed) — subject to design review during implementation.
- Pairing-code table column shape beyond the `code, workspace_id, expires_at, created_by` minimum (decisions like adding `revoked_at` are open).
- Claim-handler placement: extend `process_telegram_update` to detect `/start@bot` text + entities, vs. add a dedicated dispatcher before the message-ingestion path.
- Whether to render the deep link as `?startgroup=<code>` or `?startgroup=true&start=<code>` (Telegram supports both for groups; pick whichever pairs cleaner with `/start@bot <payload>` on the bot side).
- Worker placement for soft-deleting mappings on `my_chat_member` events (inline in webhook handler vs. background task).
- Test fixtures for global webhook payloads (multi-chat, multi-workspace dispatch).

</decisions>

<specifics>
## Specific Ideas

- The shared bot must have **Group Privacy OFF** in BotFather (operator-side configuration). Without it, the bot only sees `/commands` directed at it, not the messages we need to ingest. This is a **deployment/runbook step**, not code — note in the phase deploy checklist.
- Reuse `process_telegram_update` filtering and upsert logic from `telegram_events.py` — only the workspace-resolution step changes (look up `chat_id` in `telegram_chat_workspace` instead of trusting the path-parameter `workspace_id`).
- Reuse `_format_decision_node`-style branded copy patterns for in-chat bot replies — keep messages short and link-driven.
- Mirror the Slack `SlackReauthBanner` pattern only structurally if a re-pair flow ever becomes necessary in future — for this phase no banner is needed.
- The pairing-code generation and claim flow is conceptually similar to magic-link tokens (stored, hashed-or-plaintext-with-strict-TTL, single-use). Researcher should look at `early_access_allowlist` migration and Supabase Auth magic-link patterns for storage style.
- `IntegrationCard` component (`apps/web/src/app/dashboard/integrations/integration-card.tsx`) is the shared shell — Telegram card slot needs the new connect button + inline progress block in place of `TelegramConnect`.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/services/telegram_events.py:process_telegram_update` — message filtering + upsert + graph extraction; **keep core logic, replace workspace-resolution input**.
- `backend/src/models/telegram.py:TelegramMessage` — schema unchanged. `chat_id` already BigInteger and indexed alongside `workspace_id`.
- `backend/src/routers/telegram.py:webhook` — secret-token header verification pattern (X-Telegram-Bot-Api-Secret-Token + `hmac.compare_digest`) reused for the new global webhook.
- `backend/src/services/embedding.py:queue_embedding_generation` — unchanged downstream consumer of new messages.
- `backend/src/services/graph_extractor.py:extract_and_populate_graph` — unchanged; called fail-silent after upsert (Phase 22 pattern preserved).
- `backend/src/services/sync_adapter.py:emit_activity` — emit `integration_connected`/`integration_disconnected` events on pair/unpair (ACT-06 carry-forward).
- `apps/web/src/app/dashboard/integrations/integration-card.tsx` — shared card shell (used by all integrations).
- `apps/web/src/components/onboarding/step-sources.tsx` — onboarding slot for integration connect actions.
- `apps/web/src/lib/api.ts` — typed `apiFetch` for the new pairing-code endpoint.
- `apps/web/src/components/icons/brand-logos.tsx:TelegramLogo` — unchanged.

### Established Patterns
- **Webhook secret verification:** `hmac.compare_digest` against `X-Telegram-Bot-Api-Secret-Token` (existing pattern, reused on global webhook).
- **Background-task processing:** `BackgroundTasks.add_task(...)` with isolated `async_session()` per task; webhook returns 200 fast (current Phase-26 pattern, unchanged).
- **Idempotent upserts:** `pg_insert(...).on_conflict_do_update(constraint=...)` against `uq_tg_msg`.
- **Realtime UI updates:** Supabase Realtime subscription pattern from Phase 32 activity events / Phase 33 graph reactivity.
- **Provider check constraints:** `oauth_tokens`, `workspace_integrations`, `webhook_deliveries`, `sync_cursors` already include `'telegram'` (migration `00030_telegram_messages.sql`) — no changes needed for this phase since we're shedding `oauth_tokens` rows for telegram, not adding a new provider.
- **Migration numbering:** Next free slot is `00039_*`.
- **Fail-silent graph extraction:** Phase 22 pattern preserved (graph errors logged, never raised).

### Integration Points
- New: `backend/src/routers/telegram.py` — replace per-workspace `/webhook/{workspace_id}` with global `/webhook` route; add `/pairing-code` POST endpoint.
- New: `backend/src/services/telegram_pairing.py` (or extend `telegram_bot.py` after stripping legacy connect code) — generate codes, validate codes, claim chats, handle `/start@bot` payloads.
- New: `backend/src/models/telegram.py` — add `TelegramChatWorkspace` and `TelegramPairingCode` SQLModel entries; `TelegramMessage` unchanged.
- New: `supabase/migrations/00039_telegram_shared_bot.sql` — create both new tables with RLS (workspace-scoped on the chat-workspace mapping; pairing codes are workspace-scoped too).
- New: `backend/src/config.py` — add `TELEGRAM_BOT_TOKEN_GLOBAL`, `TELEGRAM_BOT_USERNAME`.
- Replace: `apps/web/src/app/dashboard/settings/tabs/telegram-connect.tsx` — swap token form for deep-link button + inline progress block.
- Update: `apps/web/src/lib/api.ts` — add `createTelegramPairingCode()`; remove `connectTelegram(token)` (token-paste flow gone).
- Update: `apps/web/src/components/onboarding/step-sources.tsx` — Telegram slot uses the new connect component.

### Deletions (Phase-26 cleanup, this phase)
- `connect_telegram_bot()` and `disconnect_telegram_bot()` in `telegram_bot.py` — gone (replaced by claim handler).
- Per-workspace `setWebhook` / `deleteWebhook` calls — gone.
- `oauth_tokens` rows for `provider='telegram'` and Vault entries `telegram_<workspace>_bot_token` — purged in the migration (or in a one-shot cleanup script run during deploy).
- Token-paste UI (`TelegramConnect` token form) — replaced.
- Frontend `connectTelegram(token)` API helper — removed.

</code_context>

<deferred>
## Deferred Ideas

- **DMs to the shared bot** — explicitly out of scope per ROADMAP (and Telegram terms make this very different from group ingestion).
- **Channel-broadcast post ingestion** — explicitly out of scope per ROADMAP (one-way broadcasts, different content surface).
- **Per-chat enable/disable toggle** — for now, joining + pairing the bot equals consent. A finer-grained "ingest only these chats" UI is a future enhancement.
- **Bot DM to inviter on success** — could complement the in-chat reply, but the in-chat confirmation is sufficient and the UI realtime update covers acknowledgement.
- **Bulk pair (multi-group via single code)** — explicitly rejected: codes are single-use.
- **Migration banner + backfill for Phase-26 installs** — dropped (no real Phase-26 users to migrate). If we ever ship to external users on the legacy bot, this becomes a v2 follow-up.

</deferred>

---

*Phase: 40-telegram-shared-bot-migration*
*Context gathered: 2026-05-03*
