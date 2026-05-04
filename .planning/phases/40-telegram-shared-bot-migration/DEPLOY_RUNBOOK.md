# Phase 40 Deploy Runbook — Telegram Shared-Bot Migration

Operator-facing checklist for taking the shared-bot rollout from a merged
PR to live, including BotFather setup, env vars, webhook registration,
the legacy Vault purge, and post-deploy smoke tests.

This replaces the Phase-26 per-workspace BotFather flow with a single
shared bot (e.g. `@ContextOSBot`) that is bound to workspaces via
single-use 15-minute pairing codes.

---

## a. BotFather setup (one-time, per environment)

1. Open Telegram, message `@BotFather`.
2. `/newbot` → name it `ContextOS` (or env-appropriate).
3. Choose a username — e.g. `ContextOSBot` for production,
   `contextOSdev_bot` for dev. Save the bot token from BotFather's
   `/token` reply.
4. **Bot Settings → Group Privacy → turn OFF.** (Pitfall 4 — without
   this the bot only sees commands and never the regular messages we
   need to ingest.)
5. **Bot Settings → Allow Groups? → ON.**
6. (Optional) `Edit Bot` → set description / about / picture so users
   recognise the bot when it joins their group.

Verify the bot is set up correctly:

```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN_GLOBAL}/getMe" | jq
```

The returned object should include `"can_read_all_group_messages": true`.

---

## b. Backend env vars

Set these in `backend/.env` (or your prod secrets manager). The webhook
secret can be reused from a previous Phase-26 deploy or freshly minted.

```dotenv
# NEW (Phase 40)
TELEGRAM_BOT_TOKEN_GLOBAL=<token from BotFather>
TELEGRAM_BOT_USERNAME=<bot_handle_without_@>   # e.g. ContextOSBot
TELEGRAM_WEBHOOK_SECRET=<reuse existing or generate fresh, 16+ chars>

# KEEP (unrelated to integration; do NOT collapse with TELEGRAM_BOT_TOKEN_GLOBAL)
TELEGRAM_BOT_TOKEN=<sentry alerts bot, distinct from integration bot>
TELEGRAM_CHAT_ID=<sentry alerts chat>
TELEGRAM_WEBHOOK_BASE_URL=<dev-only ngrok URL override; leave unset in prod>

# REMOVED (Phase 40 deletes these settings):
# TELEGRAM_API_ID
# TELEGRAM_API_HASH
```

`TELEGRAM_BOT_USERNAME` must match the BotFather handle exactly; the
backend raises `RuntimeError` on `/api/telegram/pairing-code` if it's
unset (fail-loud — silent fallbacks hid this misconfiguration during
Plan 02 verification).

---

## c. Frontend env vars

Set this in `apps/web/.env.local` (and the Vercel/Netlify env for prod):

```dotenv
NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=<bot_handle_without_@>   # match backend
```

The frontend renders `Waiting for @<NEXT_PUBLIC_TELEGRAM_BOT_USERNAME>…`
in the pairing UI. The deep link itself is built server-side from
`TELEGRAM_BOT_USERNAME`, so the env var is purely cosmetic on the
frontend — but having both set keeps the UI text and the deep-link bot
in sync.

---

## d. Apply migration 00039

The migration creates `telegram_chat_workspace` and
`telegram_pairing_codes`, adds the workspace_member_select RLS policies,
adds the table to `supabase_realtime` publication, and deletes the
Phase-26 `oauth_tokens` + `workspace_integrations` rows for
`provider='telegram'`.

**Production / linked Supabase project:**

```bash
cd supabase
supabase db push
```

**Local Supabase container (linked-only `db push` won't apply locally):**

```bash
psql -f supabase/migrations/00039_telegram_shared_bot.sql "$LOCAL_SUPABASE_URL"
```

Verify the table:

```bash
psql "$SUPABASE_DB_URL" -c "\d public.telegram_chat_workspace"
psql "$SUPABASE_DB_URL" -c "\d public.telegram_pairing_codes"
```

---

## e. Register the global webhook (one-shot per environment)

After the new backend is deployed and reachable via HTTPS:

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN_GLOBAL}/setWebhook" \
  -d "url=${BACKEND_URL}/api/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
  -d 'allowed_updates=["message","edited_message","my_chat_member"]' \
  -d "drop_pending_updates=true"
```

`my_chat_member` MUST be in `allowed_updates` (Pitfall 3) — without it
the bot's add/kick/leave events never reach the backend, and the
sticky chat→workspace mapping can't be soft-deleted on disconnect.

Expected response: `{"ok":true,"result":true,"description":"Webhook was set"}`.

For local dev with ngrok, replace `${BACKEND_URL}` with the public ngrok
URL (e.g. `https://bronwyn-saltless-munificently.ngrok-free.dev`) or
set `TELEGRAM_WEBHOOK_BASE_URL` and reuse it from the backend config.

Verify registration:

```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN_GLOBAL}/getWebhookInfo" | jq
```

`url` should match what you posted, `pending_update_count` should be 0,
and `allowed_updates` should include all three events.

---

## f. Purge legacy per-workspace Vault tokens

Phase-26 stored each workspace's bot token in `vault.secrets` under the
name `oauth_telegram_<workspace_id>_bot_token`. The migration deletes
the corresponding `oauth_tokens` rows; this script cleans up the
matching Vault entries (Vault is not a regular DB table so the migration
can't touch it).

**Inspect first:**

```bash
cd backend
uv run python scripts/purge_legacy_telegram_vault.py --dry-run
```

The output lists each entry it would delete (one line per workspace).

**Apply:**

```bash
cd backend
uv run python scripts/purge_legacy_telegram_vault.py
```

The script catches per-row exceptions and continues, so a single
permission glitch won't abort the whole run. At the end you'll see
`Purge complete: <deleted>/<total> entries removed`.

---

## g. Smoke test (production)

1. **Connect from Settings.** Visit `/dashboard/settings` →
   **Integrations** → Telegram → Connect.
   - Inline pairing block opens with countdown.
   - A new tab opens to `https://t.me/<bot>?startgroup=<code>`.
2. **Pair a test group.** In Telegram, choose a fresh test group when
   prompted.
   - Bot joins the group.
   - Bot posts the confirmation reply ("ContextOS connected …").
   - Dashboard card flips to **connected** within ~1 second (Realtime).
3. **Ingest a message.** Send a normal message in the group.
   - SELECT from `public.telegram_messages WHERE chat_id = <id>` shows
     the row.
   - The embedding worker picks it up and (eventually) the message
     surfaces in `/api/context/.../search`.
4. **Disconnect (kick the bot).** In Telegram, remove the bot from
   the test group.
   - `telegram_chat_workspace.removed_at` is set within ~1s.
   - An `integration_disconnected` event with metadata
     `{integration: "telegram", chat_id: ..., reason: "kicked"|"left"}`
     appears in `/dashboard/activity`.

Repeat steps 1–3 from the **onboarding** flow on a second account to
confirm parity (the Sources step now opens the same pairing block as
Settings).

---

## h. Rollback

The migration is forward-only but additive (new tables don't break old
code). To roll back the application layer, redeploy the previous
backend Docker image; `telegram_chat_workspace` and
`telegram_pairing_codes` will simply sit unused.

The founding team explicitly accepted manual re-pair as the rollback
path (no automated re-write of Phase-26 per-workspace bot tokens).
Workspaces that need fast restore can re-pair via the new Settings
flow once the backend is healthy again.

---

## i. Known limitations (v1)

Linked from `40-RESEARCH.md` § Open Questions:

- **Supergroup migration not handled.** When a regular group is
  upgraded to a supergroup, Telegram emits a `migrate_to_chat_id`
  field; the v1 dispatcher ignores it. Workaround: the operator
  re-pairs the supergroup.
- **No per-chat disconnect via UI.** Users disconnect by removing
  the bot from a chat — there is no "disconnect this chat only"
  button in Settings. The Settings disconnect button now shows a toast
  pointing the user at the in-Telegram remove flow.
- **Activity event granularity:** one `integration_connected` event per
  successful chat claim, one `integration_disconnected` per kick/leave.
  No batched "N chats disconnected" rollup.
- **Pairing-code TTL is fixed at 15 min.** No UI to configure;
  Regenerate produces a new 15-min code.

---

## Reference

- Plan 01: `40-01-PLAN.md` (backend data plane + global webhook + claim
  handler)
- Plan 02: `40-02-PLAN.md` (frontend pairing UI + 4 deviations)
- Plan 03: `40-03-PLAN.md` (this cutover; deletions + onboarding wiring
  + this runbook)
- Migration: `supabase/migrations/00039_telegram_shared_bot.sql`
- Purge script: `backend/scripts/purge_legacy_telegram_vault.py`
