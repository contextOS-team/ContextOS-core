# Phase 40: Telegram Shared-Bot Migration — Research

**Researched:** 2026-05-03
**Domain:** Telegram Bot API (group ingestion via shared bot), pairing-token lifecycle, webhook fan-out, Supabase Realtime UI
**Confidence:** HIGH on Telegram API behavior, HIGH on existing-code reuse paths, MEDIUM on pairing-code copy/UI ergonomics

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Pairing code lifecycle**
- Format: 16-character base64url random string (~96 bits entropy). Generated server-side, stored in `telegram_pairing_codes` table.
- TTL: 15 minutes from creation.
- Single-use: Code is burned (deleted) on successful claim. No multi-use within window.
- Cleanup: Lazy delete — index on `expires_at`; rows removed when consumed or when found expired during a claim attempt. No background sweep.
- Reissue: UI regenerate button creates a fresh code and invalidates the previous one for that workspace.

**`/start@bot <code>` claim handler (in groups + supergroups only)**
- Valid + unused code: Insert row into `telegram_chat_workspace` (PK `chat_id`), bot replies with branded confirmation referencing dashboard link. Burn the code.
- Expired / invalid / already-used code: Bot replies in-chat with reason + dashboard link. Visible to group members — accepted tradeoff.
- Chat already claimed by another workspace: Bot replies "already paired" message. Mapping is sticky; no cross-workspace re-claim allowed.
- Chat already claimed by SAME workspace: Treat as no-op (idempotent), don't burn the code.
- `my_chat_member` events: Always log for visibility. On `kicked`/`left`/`banned`, soft-delete the `telegram_chat_workspace` row (or mark inactive). Existing `telegram_messages` retained.

**Deprecation strategy (simplified)**
- No dual-mode, no migration banner, no backfill. Phase-26 code paths replaced cleanly in this phase.
- Reason: No real Phase-26 production users to migrate; founding team re-pairs their own dogfood workspace manually.
- Legacy per-workspace webhook handler (`/api/telegram/webhook/{workspace_id}`), `connect_telegram_bot()`, `disconnect_telegram_bot()`, BYO-bot UI form, and per-workspace Vault token storage are removed in this phase.
- Existing `telegram_messages` rows remain untouched — schema is unchanged.
- The new global webhook is the only Telegram entry point after this phase ships.

**Environment variables**
- New: `TELEGRAM_BOT_TOKEN_GLOBAL` (shared bot token), `TELEGRAM_BOT_USERNAME` (e.g. `ContextOSBot`).
- Existing `TELEGRAM_BOT_TOKEN` (Sentry alerts) is kept distinct — do not collapse them.
- Existing `TELEGRAM_WEBHOOK_SECRET` reused for the global webhook secret-token header check.

**Connect UX**
- Surfaces: Both Settings → Integrations card AND Onboarding `step-sources.tsx` slot. Replace existing `TelegramConnect`.
- Click flow: button → `POST /api/telegram/pairing-code` → `{ code, deep_link, expires_at }` → open `https://t.me/<TELEGRAM_BOT_USERNAME>?startgroup=<code>` in new tab → inline progress block with countdown + Cancel + Regenerate.
- Success detection: Supabase Realtime subscription on `telegram_chat_workspace` inserts filtered by `workspace_id`.
- Failure / expiry detection: Frontend timer hits `expires_at` → progress block shows "Link expired" + single Regenerate button.

**Filter rules (carried forward from Phase 26)**
- Filter out: non-text messages (photos, stickers), bot messages (`from.is_bot`), system join/leave/topic messages.
- Edited messages: upsert via existing `uq_tg_msg(workspace_id, chat_id, message_id)` constraint.
- The current Phase-26 short-message filter is already removed (unchanged here).

### Claude's Discretion

- Exact wording of bot replies (success, expired-code, already-claimed) — subject to design review during implementation.
- Pairing-code table column shape beyond the `code, workspace_id, expires_at, created_by` minimum (e.g., adding `revoked_at` is open).
- Claim-handler placement: extend `process_telegram_update` to detect `/start@bot` text + entities, vs. add a dedicated dispatcher before the message-ingestion path.
- Whether to render the deep link as `?startgroup=<code>` or `?startgroup=true&start=<code>`.
- Worker placement for soft-deleting mappings on `my_chat_member` events (inline in webhook handler vs. background task).
- Test fixtures for global webhook payloads (multi-chat, multi-workspace dispatch).

### Deferred Ideas (OUT OF SCOPE)

- DMs to the shared bot — explicitly out of scope per ROADMAP (and Telegram terms make this very different from group ingestion).
- Channel-broadcast post ingestion — explicitly out of scope per ROADMAP.
- Per-chat enable/disable toggle — for now, joining + pairing the bot equals consent. Future enhancement.
- Bot DM to inviter on success — in-chat confirmation + UI Realtime is sufficient.
- Bulk pair (multi-group via single code) — explicitly rejected: codes are single-use.
- Migration banner + backfill for Phase-26 installs — dropped (no real Phase-26 users to migrate).
</user_constraints>

<phase_requirements>
## Phase Requirements

The roadmap entry for Phase 40 references `TG-05, TG-06, TG-07 (TBD — define during planning)`. They are not yet rows in REQUIREMENTS.md. Below is the proposed mapping the planner can lift verbatim into REQUIREMENTS.md (matches the locked CONTEXT decisions and the ROADMAP success surface).

| ID | Description | Research Support |
|----|-------------|-----------------|
| TG-05 | Users connect Telegram in one click via a shared `@ContextOSBot` deep link — no BotFather, no token paste, no group-privacy toggle | Telegram `?startgroup=PAYLOAD` deep link delivers `/start@bot PAYLOAD` to the group as the bot's first message — see *Telegram API Findings* §A. Pairing-code endpoint + `IntegrationCard` + `step-sources.tsx` slot — see *Existing Code Insights*. |
| TG-06 | Group/supergroup chats are bound to a workspace via a single-use, ~15-min TTL pairing code; mapping is sticky (no cross-workspace re-claim) | `telegram_pairing_codes` (codes) + `telegram_chat_workspace` (mapping, PK chat_id) — see *Pairing Token Storage Pattern*. ON CONFLICT DO NOTHING on chat_id PK enforces stickiness. |
| TG-07 | A single global webhook `/api/telegram/webhook` routes all updates by `chat_id` lookup; messages are ingested with the existing filter + upsert + graph pipeline | Telegram has one webhook URL per bot, not per chat — see *Webhook Routing*. `process_telegram_update` is reusable as-is once workspace resolution moves from path-param to `chat_id`-lookup — see *Reusable Assets*. |

**Note for planner:** when first plan starts, write these IDs into `.planning/REQUIREMENTS.md` under a new `### Telegram Shared Bot` section (mirroring `### Activity Events`) and update the Traceability table. Phase requirement IDs are required to be real, not TBD, before plan writeup begins.
</phase_requirements>

## Summary

The phase is technically straightforward because Telegram's bot platform is *built* for this exact pattern: one bot, one webhook, deep links that route group joins. The risky surface is internal — a clean cutover from per-workspace bots to the shared bot, plus a new pairing primitive that resembles a magic-link token.

Three findings shape the plan:

1. **Telegram delivers the deep-link payload as a regular message** (`/start@bot <payload>` in the group), not as a structured `start_parameter` field. The claim handler is a string-prefix check on `message.text`, not a special update type. This means the pairing event arrives on the same `message` update we already process — and **must be detected and routed BEFORE the existing filter/upsert path** (the message itself is `is_bot: false` content from a real user, so it would otherwise be ingested as a normal text message into `telegram_messages`).

2. **One bot = one webhook URL.** Telegram does not let us register a per-chat or per-workspace webhook against the shared bot. The new `/api/telegram/webhook` (no path param) receives every update for `@ContextOSBot` across the whole user base; the only workspace-resolution input is `chat.id`. Lookup via `telegram_chat_workspace` (chat_id PK) is the routing primitive.

3. **`my_chat_member` is in the default `allowed_updates` set, but the current Phase-26 code explicitly opts out** (`allowed_updates=["message", "edited_message"]`). The new global `setWebhook` call must include `["message", "edited_message", "my_chat_member"]` so kicked/left detection works.

**Primary recommendation:** Build a thin dispatcher in `routers/telegram.py:webhook` that branches on update shape — `my_chat_member` → bookkeeping path (mapping soft-delete on kicked/left/banned), `message.text.startswith("/start")` → pairing-claim path, everything else → existing `process_telegram_update` (after looking up `workspace_id` from `chat_id`). Keep the claim handler in a new `services/telegram_pairing.py`; keep `process_telegram_update` itself unchanged in shape — only its caller resolves `workspace_id` differently.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | already pinned (used in `telegram_bot.py`) | Telegram Bot API HTTP calls (`sendMessage`, `setWebhook`) | Already used for `telegram_api_call` — no new dep |
| `secrets` (stdlib) | py3.13 | `secrets.token_urlsafe(12)` → 16-char base64url string (~96 bits) | Stdlib, FIPS-style RNG, exact match for "16-char base64url" decision |
| `sqlalchemy.dialects.postgresql.insert` | already pinned | `pg_insert(...).on_conflict_do_*` for sticky chat→workspace mapping + idempotent code insert | Established pattern in `telegram_events.py`, `slack_events.py` |
| `fastapi.BackgroundTasks` | already pinned | Run `process_telegram_update` async after returning 200 | Already used by Phase-26 webhook |
| `@supabase/supabase-js` realtime channel | already pinned | Frontend listens for `telegram_chat_workspace` INSERT filtered by `workspace_id` | Established pattern in `useContextPagesRealtime` and `activity-timeline.tsx` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sonner` toast | existing | UX for "Code expired", "Bot connected" notifications | Mirrors Phase 26 + Slack patterns |
| `lucide-react` | existing | Icon set (Loader2, AlertTriangle, Check) | Same as `SlackReauthBanner` |
| Telegram TDLib `t.me` URLs | n/a | Render `https://t.me/<bot>?startgroup=<code>` | Plain URL string, no SDK needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `secrets.token_urlsafe(12)` | UUID4 (32 hex chars) | Longer, not base64url-compatible with 64-char Telegram payload limit. CONTEXT locks 16 chars. |
| Inline `httpx.post` to send bot replies | A `TelegramBotAPI` client wrapper | The existing `telegram_api_call(token, method, **params)` helper already does this — reuse it (just pass the global token instead of per-workspace). |
| Polling for pairing success on the client | Realtime subscription to `telegram_chat_workspace` | Polling adds latency + load; Realtime gives instant flip. Pattern already established in this codebase. |
| Storing the payload hashed (like password) | Plaintext code with strict TTL + single-use | Magic-link convention for short-TTL tokens is plaintext; the 15-min window + single-use semantics are the security boundary, not at-rest encryption. The Telegram client itself sees the plaintext payload in the URL bar. |

**Installation:** No new packages required. All dependencies are already in `backend/pyproject.toml` and `apps/web/package.json`.

## Architecture Patterns

### Recommended Project Structure (delta only)

```
backend/src/
├── routers/
│   └── telegram.py                # REPLACE: drop /webhook/{workspace_id}; add /webhook (global) + /pairing-code
├── services/
│   ├── telegram_bot.py            # SHRINK: keep telegram_api_call(); delete connect_telegram_bot, disconnect_telegram_bot
│   ├── telegram_events.py         # KEEP: process_telegram_update unchanged in shape
│   ├── telegram_pairing.py        # NEW: generate_pairing_code, claim_chat, handle_my_chat_member, _send_bot_reply
│   └── telegram_sync.py           # SHRINK / DELETE: drain_pending_updates + setWebhook/deleteWebhook code go away
├── models/
│   └── telegram.py                # ADD: TelegramChatWorkspace, TelegramPairingCode SQLModel classes
├── config.py                      # ADD: TELEGRAM_BOT_TOKEN_GLOBAL, TELEGRAM_BOT_USERNAME

supabase/migrations/
└── 00039_telegram_shared_bot.sql  # NEW: two tables + RLS + cleanup of oauth_tokens telegram rows

apps/web/src/
├── app/dashboard/settings/tabs/
│   └── telegram-connect.tsx       # REPLACE: token form → "Connect via @ContextOSBot" deep-link button + progress
├── app/dashboard/integrations/
│   └── telegram-pairing-progress.tsx  # NEW (suggested): inline waiting block (countdown, Cancel, Regenerate)
├── components/onboarding/
│   └── step-sources.tsx           # UPDATE: drop showTelegramForm/handleTelegramSubmit; render new connect component
└── lib/api.ts                     # UPDATE: remove connectTelegram(token); add createTelegramPairingCode()
```

### Pattern 1: Webhook Dispatcher (single global route, fan-out by update shape)

**What:** A single FastAPI route handles every update for the bot. The handler verifies the secret-token header, then dispatches by update type to `pairing` / `bookkeeping` / `ingestion`.

**When to use:** Always — Telegram allows only one webhook URL per bot.

**Example (sketch — adapt to project conventions):**
```python
# backend/src/routers/telegram.py
@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    settings = get_settings()
    if not hmac.compare_digest(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""),
        settings.TELEGRAM_WEBHOOK_SECRET,
    ):
        raise HTTPException(status_code=403, detail="Invalid secret token")

    payload = await request.json()
    background_tasks.add_task(_dispatch_update, payload)
    return {"ok": True}


async def _dispatch_update(payload: dict) -> None:
    async with async_session() as session:
        try:
            # 1) my_chat_member: bot was added/kicked/left
            if "my_chat_member" in payload:
                await handle_my_chat_member(session, payload["my_chat_member"])
                return

            message = payload.get("message") or payload.get("edited_message")
            if not message:
                return

            chat_id = message["chat"]["id"]
            text = message.get("text", "") or ""

            # 2) /start@bot <code> in group — pairing claim path
            if text.startswith("/start") and message["chat"]["type"] in ("group", "supergroup"):
                await claim_chat(session, message)
                return

            # 3) Normal ingestion — resolve workspace from chat mapping
            workspace_id = await resolve_workspace_for_chat(session, chat_id)
            if workspace_id is None:
                logger.info("telegram_unmapped_chat chat_id=%s", chat_id)
                return  # no mapping → drop silently
            await process_telegram_update(session, workspace_id, payload)
        except Exception:
            logger.exception("telegram_dispatch_error")
            await session.rollback()
```

### Pattern 2: Sticky chat→workspace mapping via PK conflict

**What:** `telegram_chat_workspace` has `chat_id` as PRIMARY KEY (not unique-on-pair). `INSERT … ON CONFLICT (chat_id) DO NOTHING` enforces "first claim wins."

**When to use:** Always for the chat-mapping table.

**Example:**
```python
# backend/src/services/telegram_pairing.py
stmt = pg_insert(TelegramChatWorkspace).values(
    chat_id=chat_id,
    workspace_id=workspace_id,
    chat_title=chat_title,
    chat_type=chat_type,
    paired_by=user_id,
).on_conflict_do_nothing(index_elements=["chat_id"])
result = await session.execute(stmt)
inserted = result.rowcount == 1  # If 0, chat was already mapped — return existing row to decide reply
```

After the upsert, SELECT the row to detect "same workspace (no-op)" vs "other workspace (reject)".

### Pattern 3: Pairing-code one-shot consume (DELETE … RETURNING)

**What:** Atomic claim + burn in one statement. Eliminates the TOCTOU window between "found valid code" and "delete it before someone else uses it."

**When to use:** Always for code redemption.

**Example:**
```python
# backend/src/services/telegram_pairing.py
from sqlalchemy import delete

stmt = (
    delete(TelegramPairingCode)
    .where(
        TelegramPairingCode.code == code,
        TelegramPairingCode.expires_at > func.now(),
    )
    .returning(TelegramPairingCode.workspace_id, TelegramPairingCode.created_by)
)
row = (await session.execute(stmt)).first()
if row is None:
    return None  # invalid, expired, or already claimed
workspace_id, created_by = row
```

### Pattern 4: Realtime success-detection on insert

**What:** Frontend opens a Supabase Realtime channel for `telegram_chat_workspace` INSERT events filtered by `workspace_id`, and flips state on first match.

**When to use:** Connect-flow waiting screen.

**Example (mirroring `activity-timeline.tsx`):**
```typescript
// apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx
useEffect(() => {
  const supabase = createClient()
  const channel = supabase
    .channel(`telegram-pairing-${workspaceId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'telegram_chat_workspace',
        filter: `workspace_id=eq.${workspaceId}`,
      },
      (payload) => {
        onConnected(payload.new as { chat_id: number; chat_title: string })
      }
    )
    .subscribe()
  return () => { supabase.removeChannel(channel) }
}, [workspaceId, onConnected])
```

**Critical:** RLS must allow the user's JWT to SELECT the new row, otherwise Realtime suppresses it (Supabase evaluates RLS per subscriber). The workspace-scoped policy below covers this.

### Pattern 5: RLS — workspace-scoped reads, service-role writes only

**What:** Frontend can SELECT rows for its own workspace (Realtime depends on this); writes only happen from the backend with the service role key.

**Example:**
```sql
-- Following the established workspace_member_select pattern
ALTER TABLE public.telegram_chat_workspace ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_member_select" ON public.telegram_chat_workspace
    FOR SELECT USING (
        workspace_id IN (
            SELECT ws.id FROM public.workspaces ws
            JOIN public.workspace_members wm ON ws.id = wm.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );
-- No INSERT/UPDATE/DELETE policy → only service_role (which bypasses RLS) can write.
```

Same shape for `telegram_pairing_codes` (workspace-scoped SELECT only — backend writes via service role).

### Anti-Patterns to Avoid

- **Per-chat webhook registration via the shared bot.** Telegram doesn't allow it; the URL is bot-scoped. Don't try.
- **Trusting `chat_id` from the webhook URL path.** That was the Phase-26 model and is exactly what the migration removes. The new route has no path param. Workspace must be resolved from `telegram_chat_workspace`.
- **Claim handler runs the ingestion filter.** The `/start@bot <code>` text passes the existing filter (text, not bot, not system). If the dispatcher branch order is wrong, the pairing message gets ingested into `telegram_messages` for the wrong (or no) workspace and pollutes the graph. Branch on `text.startswith("/start")` BEFORE calling `process_telegram_update`.
- **Hashed pairing codes.** The Telegram client and group members can see the URL anyway — adding bcrypt at rest is theater that complicates the DELETE…RETURNING redemption path.
- **Storing `chat_id` as `INTEGER` (32-bit).** Supergroup IDs are int64 negative numbers (range up to ~`-1_000_997_852_516`). Use `BIGINT` (Postgres) / `BigInteger` (SQLAlchemy) — already the case for `telegram_messages.chat_id`.
- **Forgetting `my_chat_member` in `setWebhook` allowed_updates.** Phase 26 explicitly opted *out* by passing `["message", "edited_message"]`. The new global webhook must register `["message", "edited_message", "my_chat_member"]` (it's normally on by default, but the Phase-26 code shows we need to be explicit because we override the list).
- **Leaving Group Privacy ON in BotFather.** Bot will only receive messages addressed to it (`@ContextOSBot foo` or replies to its messages), not the chat content we want to ingest. Operator-side step — record in deploy runbook.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Random secret generation | A custom `random.choice(alphabet)` loop | `secrets.token_urlsafe(12)` | Cryptographically strong, exact 16-char base64url output, stdlib. |
| Telegram API HTTP client | A new httpx wrapper for the global bot | Existing `telegram_api_call(token, method, **params)` from `telegram_bot.py` | Already handles error envelopes, JSON encoding, timeouts. Just call it with `settings.TELEGRAM_BOT_TOKEN_GLOBAL`. |
| Webhook secret verification | Manual string compare on the secret header | `hmac.compare_digest(...)` against `X-Telegram-Bot-Api-Secret-Token` | Already used by Phase-26 webhook. Constant-time. |
| Realtime subscription plumbing | A polling loop on `/api/telegram/status` | `supabase.channel().on('postgres_changes', {...filter...})` (mirror `useContextPagesRealtime` / `activity-timeline.tsx`) | Push-based, sub-second latency, RLS-aware, established codebase pattern. |
| Periodic expired-code sweep | A cron / `BackgroundScheduler` task | Lazy delete on claim attempt + index on `expires_at` | CONTEXT locks lazy delete. Periodic sweep is wasted infra for ~15-min TTL tokens with low write rate. |
| Per-workspace Telegram bot tokens | A new Vault key scheme | One global token from env (`TELEGRAM_BOT_TOKEN_GLOBAL`) + the new `oauth_tokens` purge in this migration | Phase-26 vault entries are deliberately purged in the deletion section of CONTEXT. |
| Multi-tenant message routing | Custom code mapping each update to a tenant | A 1-row PK-on-`chat_id` join table with a single `SELECT … WHERE chat_id = $1` lookup | Linear, indexed, the only reliable input from Telegram is `chat_id`. |

**Key insight:** Almost everything Phase 40 needs already exists in the codebase as patterns from Phase 26 (Telegram), Phase 32 (activity events), Phase 33 (Realtime UI), and Phase 39 (Slack reauth banner ergonomics). The work is wiring + cutover, not invention.

## Common Pitfalls

### Pitfall 1: `start_parameter` is not a real Telegram field on Message
**What goes wrong:** Engineer searches "telegram start parameter" and finds the term `start_parameter` (which exists in MTProto / `messages.startBot` and on Mini-App `WebAppInitData`). They expect the bot webhook payload to contain `message.start_parameter = "<code>"`. It doesn't.
**Why it happens:** Documentation conflates Bot API behavior with MTProto and Mini Apps. On the Bot API specifically, the deep-link payload for `?startgroup=<code>` is delivered as the *message text* of the bot's first group message: `/start@<botusername> <code>`.
**How to avoid:** Implement the claim handler as a `text` parser. Tokenize on whitespace; the second token is the payload. Strip the `@<botusername>` suffix before matching the command.
**Warning signs:** Code references `message["start_parameter"]` or `update.start_parameter`. None of those exist on the Bot API webhook payload.
*Confidence: HIGH — verified at https://core.telegram.org/bots/features#deep-linking ("the resulting update will contain text in the form: `/start@your_bot spaceship`") and via the Update spec at https://core.telegram.org/bots/api#update (no `start_parameter` field on Message).*

### Pitfall 2: Order of handlers — pairing message gets ingested as content
**What goes wrong:** The `/start@bot <code>` message reaches `process_telegram_update`, passes the filter (it's text, from a real user, not a bot), and is upserted into `telegram_messages`. The chat is now claimed (good) but the bot also ingested a "message" that's actually a control command (bad — pollutes graph, embeddings, RAG).
**Why it happens:** Naive dispatcher pipes every update through `process_telegram_update` first, then runs claim logic on the side.
**How to avoid:** Branch on `text.startswith("/start")` BEFORE the ingestion path. Return early after pairing.
**Warning signs:** Telegram messages with text starting with `/start` appear in the workspace context feed.

### Pitfall 3: `my_chat_member` silently dropped because of `allowed_updates` override
**What goes wrong:** New webhook is registered with `allowed_updates=["message", "edited_message"]` (copied from Phase-26 code). Kicked/left detection never fires, mappings linger forever.
**Why it happens:** `my_chat_member` is in the *default* set, but once you pass an explicit `allowed_updates` list, Telegram replaces (not unions) with your list.
**How to avoid:** Explicitly include `"my_chat_member"` in `allowed_updates` when calling `setWebhook` for the global bot. Recommended set: `["message", "edited_message", "my_chat_member"]`.
**Warning signs:** Bot was kicked from a group, but `telegram_chat_workspace` row still exists; reconnecting in another workspace says "already paired" forever.
*Confidence: HIGH — https://core.telegram.org/bots/api#setwebhook and https://core.telegram.org/bots/api#getupdates: "Specify an empty list to receive all update types except chat_member, message_reaction, and message_reaction_count (default)". Empty/omitted = default; explicit list = exact.*

### Pitfall 4: Group Privacy ON in BotFather → bot sees only its own commands
**What goes wrong:** Bot joins the group, claim handler fires (it's addressed `/start@bot`), but no further messages arrive — ingestion is silently empty.
**Why it happens:** "Group Privacy" mode (BotFather → Bot Settings → Group Privacy) restricts the bot to messages explicitly addressed to it.
**How to avoid:** This is a one-time BotFather setup step. Document in the deploy runbook. Add a startup self-check (bot calls `getMe` + `getMyDefaultAdministratorRights`?) — at minimum, mention in the README.
**Warning signs:** Pairing succeeds, no other messages flow into `telegram_messages` for that chat.
*Confidence: HIGH — well-known Telegram bot ops detail; CONTEXT.md already calls this out as a runbook step.*

### Pitfall 5: Race — two users in the same workspace generate codes back-to-back
**What goes wrong:** User A clicks Connect (code A). User B clicks Connect on the same workspace (code B). Whichever code is used "wins"; the other points to a code that no longer matches.
**Why it happens:** No invalidation when a new code is generated.
**How to avoid:** On `POST /api/telegram/pairing-code`, DELETE all unclaimed codes for `workspace_id` before INSERTing the new one (single transaction). CONTEXT locks "Reissue invalidates the previous code" — same logic applies to natural concurrency.
**Warning signs:** "Code expired" error in UI even though countdown shows time remaining (because someone else's regenerate burned it).

### Pitfall 6: Bot reply fails (e.g., bot was muted) → claim still committed
**What goes wrong:** `telegram_api_call(token, "sendMessage", ...)` raises after the DELETE-RETURNING already burned the code. Code is gone, mapping was inserted, but the user got no in-chat confirmation.
**Why it happens:** Reply send is a side effect after DB commit.
**How to avoid:** Call `sendMessage` AFTER `session.commit()` and treat its failure as non-fatal (log + Sentry). The Realtime UI flip is the user-visible acknowledgement; the bot reply is a courtesy. Don't roll back the claim if the reply fails.
**Warning signs:** Logs show `sendMessage` errors paired with successful claims.

### Pitfall 7: Forgetting that supergroup chat_id can change on upgrade
**What goes wrong:** A regular group is upgraded to a supergroup. Telegram sends a `migrate_to_chat_id` event. The old `chat_id` in `telegram_chat_workspace` no longer matches incoming messages.
**Why it happens:** Out-of-scope edge case in the current decisions, but worth flagging.
**How to avoid:** Listen for `message.migrate_to_chat_id` and update the mapping (or, simplest: leave it as a known limitation — bot leaves and re-pair is needed). Not blocking for v1; document as known issue.
**Warning signs:** Group works, then suddenly stops receiving updates after admin upgrades to supergroup.
*Confidence: MEDIUM — documented Telegram behavior, likely affects very few founding-team groups; recommend tracking as a known limitation rather than blocking the phase.*

### Pitfall 8: Realtime channel scoped too broadly → security smell + cross-tenant noise
**What goes wrong:** Frontend subscribes to all of `telegram_chat_workspace` without a filter, relies entirely on RLS to prune.
**Why it happens:** Easy to write `event: 'INSERT', table: 'telegram_chat_workspace'` and forget the filter.
**How to avoid:** Always include `filter: 'workspace_id=eq.${workspaceId}'` on the channel. Defense in depth even though RLS would also block cross-workspace rows.
**Warning signs:** Devtools shows messages with `workspace_id` ≠ current workspace (RLS misconfigured) — UI flips on someone else's pairing.

### Pitfall 9: `chat_id` typed as INTEGER instead of BIGINT
**What goes wrong:** Supergroup IDs are 13-digit negative numbers (e.g., `-1001234567890`); they overflow signed 32-bit `INTEGER` (range ~±2.1B). INSERT fails or, worse, silently truncates if a serializer is forgiving.
**Why it happens:** Default SQLAlchemy `Integer` type is 32-bit.
**How to avoid:** Use `BIGINT` in the migration and `Column(BigInteger, ...)` in the SQLModel. The existing `TelegramMessage.chat_id` already uses `BigInteger` — copy that pattern.
**Warning signs:** "value out of range for type integer" errors on production groups.
*Confidence: HIGH — Telegram chat_id semantics + existing codebase already uses BigInt for `telegram_messages.chat_id`.*

## Code Examples

Verified patterns from official sources or in-repo code:

### Generate a 16-char base64url pairing code
```python
# backend/src/services/telegram_pairing.py
# Source: stdlib (Python 3.13 docs); CONTEXT.md locks "16-char base64url"
import secrets

def generate_pairing_code() -> str:
    # token_urlsafe(12) → 16 base64url chars (12 bytes × 4/3 = 16) → ~96 bits entropy
    return secrets.token_urlsafe(12)
```

### Sticky chat→workspace upsert (PK conflict)
```python
# Source: in-repo pattern from telegram_events.py + slack_events.py
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(TelegramChatWorkspace).values(
    chat_id=chat_id,
    workspace_id=workspace_id,
    chat_title=chat_title,
    chat_type=chat_type,
    paired_by=user_id,
).on_conflict_do_nothing(index_elements=["chat_id"])
inserted = (await session.execute(stmt)).rowcount == 1
# If not inserted, fetch existing row to decide if same-workspace no-op or cross-workspace reject:
if not inserted:
    existing = await session.scalar(
        select(TelegramChatWorkspace).where(TelegramChatWorkspace.chat_id == chat_id)
    )
    if existing.workspace_id == workspace_id:
        return ClaimResult.NOOP
    return ClaimResult.ALREADY_CLAIMED_BY_OTHER
```

### Atomic code redemption (DELETE … RETURNING)
```python
# Source: standard Postgres pattern for one-shot tokens
from sqlalchemy import delete, func

stmt = (
    delete(TelegramPairingCode)
    .where(
        TelegramPairingCode.code == code,
        TelegramPairingCode.expires_at > func.now(),
    )
    .returning(TelegramPairingCode.workspace_id, TelegramPairingCode.created_by)
)
row = (await session.execute(stmt)).first()
if row is None:
    return None  # invalid / expired / already used (single-use)
workspace_id, created_by = row
```

### Detect bot-removed via my_chat_member
```python
# Source: Telegram Bot API ChatMemberUpdated, https://core.telegram.org/bots/api#chatmemberupdated
async def handle_my_chat_member(session, update: dict) -> None:
    chat_id = update["chat"]["id"]
    new_status = update["new_chat_member"]["status"]
    # 'left' (bot called leaveChat or was removed), 'kicked' (banned), 'restricted' with can_send_messages=false
    if new_status in ("left", "kicked"):
        await session.execute(
            update(TelegramChatWorkspace)
            .where(TelegramChatWorkspace.chat_id == chat_id)
            .values(removed_at=func.now())
        )
        await session.commit()
        # Always log for visibility (CONTEXT decision)
        logger.info("telegram_bot_removed chat_id=%s status=%s", chat_id, new_status)
```

### Realtime channel for pairing success (frontend)
```typescript
// Source: in-repo apps/web/src/hooks/use-context-pages-realtime.ts + activity-timeline.tsx
useEffect(() => {
  const supabase = createClient()
  const channel = supabase
    .channel(`telegram-pairing-${workspaceId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'telegram_chat_workspace',
        filter: `workspace_id=eq.${workspaceId}`,
      },
      (payload) => {
        const row = payload.new as { chat_id: number; chat_title: string | null }
        onConnected(row)
      }
    )
    .subscribe()
  return () => { supabase.removeChannel(channel) }
}, [workspaceId, onConnected])
```

### Set the global webhook with `my_chat_member` allowed
```python
# Source: in-repo telegram_bot.py:telegram_api_call + Telegram setWebhook docs
# This is a one-shot deploy script (or runbook curl) — NOT runtime code.
await telegram_api_call(
    settings.TELEGRAM_BOT_TOKEN_GLOBAL,
    "setWebhook",
    url=f"{settings.BACKEND_URL}/api/telegram/webhook",
    secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
    allowed_updates=["message", "edited_message", "my_chat_member"],
    drop_pending_updates=True,  # one-shot at cutover so we don't re-process Phase-26 backlog
)
```

### Migration shape (`00039_telegram_shared_bot.sql`)
```sql
-- Source: in-repo patterns from 00030_telegram_messages.sql, 00038_early_access_allowlist.sql

-- Sticky chat → workspace mapping (PK chat_id ensures first-claim-wins)
CREATE TABLE IF NOT EXISTS public.telegram_chat_workspace (
    chat_id      BIGINT PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    chat_title   TEXT,
    chat_type    TEXT,
    paired_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    paired_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tg_cw_workspace ON public.telegram_chat_workspace(workspace_id);

-- Single-use, ~15min TTL pairing codes
CREATE TABLE IF NOT EXISTS public.telegram_pairing_codes (
    code         TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    created_by   UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tg_pc_workspace ON public.telegram_pairing_codes(workspace_id);
CREATE INDEX IF NOT EXISTS idx_tg_pc_expires ON public.telegram_pairing_codes(expires_at);

-- RLS — workspace-scoped reads only (writes via service role)
ALTER TABLE public.telegram_chat_workspace ENABLE ROW LEVEL SECURITY;
CREATE POLICY "workspace_member_select" ON public.telegram_chat_workspace
    FOR SELECT USING (
        workspace_id IN (
            SELECT ws.id FROM public.workspaces ws
            JOIN public.workspace_members wm ON ws.id = wm.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

ALTER TABLE public.telegram_pairing_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "workspace_member_select" ON public.telegram_pairing_codes
    FOR SELECT USING (
        workspace_id IN (
            SELECT ws.id FROM public.workspaces ws
            JOIN public.workspace_members wm ON ws.id = wm.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

-- Phase-26 cleanup: drop legacy per-workspace bot tokens from oauth_tokens.
-- Vault entries are purged via a deploy script (not migration — Vault is not a regular table).
DELETE FROM public.oauth_tokens WHERE provider = 'telegram';
DELETE FROM public.workspace_integrations WHERE provider = 'telegram';
```
*(Vault token names follow `telegram_<workspace_id>_bot_token` convention from `vault.token_name`. They must be purged via a one-shot deploy script that calls `delete_token(...)` for each leftover entry — separate from this migration.)*

## State of the Art

| Old Approach (Phase 26) | Current Approach (Phase 40) | When Changed | Impact |
|-------------------------|------------------------------|--------------|--------|
| Per-workspace bot via BotFather → token paste | Single shared bot via deep-link pairing | Phase 40 | One-click connect, no token in user hands |
| `/api/telegram/webhook/{workspace_id}` (workspace from URL) | `/api/telegram/webhook` global, workspace from `chat_id` lookup | Phase 40 | One webhook, scaleable to N workspaces |
| Vault entry per workspace bot token | One env-var `TELEGRAM_BOT_TOKEN_GLOBAL` | Phase 40 | No per-tenant secret rotation |
| `setWebhook` / `deleteWebhook` per connect/disconnect | Webhook set once at deploy | Phase 40 | Deploy-time config, not runtime |
| `telegram_messages` workspace_id from path param | Same column, but populated from `telegram_chat_workspace` lookup | Phase 40 | Schema unchanged — purely the resolution path moves |
| `oauth_tokens` rows for `provider='telegram'` | Removed in this migration | Phase 40 | Schema constraint kept (still allows 'telegram'), rows deleted |
| `connect_telegram_bot()` / `disconnect_telegram_bot()` | `claim_chat()` / soft-delete via `my_chat_member` | Phase 40 | Connect is implicit; disconnect is "remove the bot from your group" |
| `allowed_updates=["message", "edited_message"]` | `["message", "edited_message", "my_chat_member"]` | Phase 40 | Required for kicked/left detection |

**Deprecated/outdated:**
- `connect_telegram_bot()` in `services/telegram_bot.py` — delete after migration commits.
- `disconnect_telegram_bot()` in `services/telegram_bot.py` — delete.
- `telegram_sync.py:drain_pending_updates()` and `_run_bot_api_sync()` — delete (no per-workspace bot to drain). The `run_telegram_history_sync()` entry point and `/api/telegram/sync` route can both go since the new bot has no concept of "drain a workspace's pending queue at connect time" (it just receives updates as they happen).
- `connectTelegram(token)` in `apps/web/src/lib/api.ts` — remove.
- `TelegramConnect` (token form) in `apps/web/src/app/dashboard/settings/tabs/telegram-connect.tsx` — replace.
- `TelegramSyncSection` and `getTelegramSyncStatus` / `syncTelegramHistory` API helpers — delete (no per-workspace history sync). Display "X messages indexed" can be derived from `SELECT COUNT(*) FROM telegram_messages WHERE workspace_id = $1` if desired in the new UI.
- The `showTelegramForm`, `telegramToken`, `handleTelegramSubmit`, `telegramSyncStatus` / `telegramSyncCount` polling logic in `step-sources.tsx` — replace with the new pairing component.
- Settings: `TELEGRAM_WEBHOOK_BASE_URL` was used to override `BACKEND_URL` for ngrok-style dev; still useful for the global webhook. Keep.
- Settings: `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` (Telethon MTProto) — were optional for full history sync. **No longer needed** for Phase 40 (the shared bot has no special history access). Recommend dropping from `config.py` and `.env.example` to reduce surface.

## Open Questions

1. **Should `/start@bot <code>` be valid in private chats (DMs to the bot)?**
   - What we know: CONTEXT scopes pairing to "groups + supergroups only" and DMs are out of scope.
   - What's unclear: If a user clicks `?start=<code>` (no group selector), they end up in a 1:1 DM with the bot and Telegram delivers `/start <code>` to the bot in a private chat. Do we silently ignore? Reply "Telegram DMs are not supported"?
   - Recommendation: Silently drop `message.chat.type == "private"` updates in the dispatcher. If we want to be helpful, send a single canned reply pointing them at the dashboard. Defer the "helpful reply" decision to Claude's discretion (CONTEXT marks bot wording as discretion).

2. **Single-use code: should the regenerate button always invalidate, or only on TTL boundary?**
   - What we know: CONTEXT says "UI regenerate button creates a fresh code and invalidates the previous one for that workspace."
   - What's unclear: What about a sibling user generating concurrently?
   - Recommendation: `POST /api/telegram/pairing-code` always deletes any unexpired codes for `workspace_id` before INSERT. One-active-code-per-workspace invariant. (See Pitfall 5.)

3. **Display "connected groups" in Settings — UX scope?**
   - What we know: CONTEXT requires a connected/disconnected status at the IntegrationCard level. Doesn't specify whether to list each connected group.
   - What's unclear: Should the expanded card show the list of paired chats (titles + chat_type) and let users disconnect individually?
   - Recommendation: For v1 of this phase, render a simple "Connected to N groups" line + "Manage in Telegram (kick the bot from a chat to unpair)". Surfacing per-chat removal via API is more code than the founding team needs. Note as a follow-up.

4. **Activity events on connect/disconnect — keep firing them?**
   - What we know: CONTEXT.md:97 says `sync_adapter.emit_activity(...)` continues to emit `integration_connected` / `integration_disconnected` events on pair/unpair.
   - What's unclear: At a per-chat level (one event per group joined?) or at a workspace level (one event for first chat connected)?
   - Recommendation: Emit `integration_connected` once per chat_id claim (when `claim_chat` actually inserts a new mapping row), with metadata `{integration: "telegram", chat_title: "..."}`. Emit `integration_disconnected` on each `kicked`/`left` for an existing mapping. This mirrors the granularity of GitHub repo connect events.

5. **Should the deep-link form be `?startgroup=<code>` or `?startgroup=true&start=<code>`?**
   - What we know: CONTEXT marks this as Claude's discretion.
   - What's unclear: Both work. `?startgroup=<code>` puts the payload inline (bot receives `/start@bot <code>`). `?startgroup=true&start=<code>` is mostly used for Mini-App startup parameters and is *not* needed for the Bot API claim flow.
   - Recommendation: Use `?startgroup=<code>`. It's the canonical form documented at https://core.telegram.org/bots/features#deep-linking and produces exactly the `/start@bot <code>` text we parse.

6. **`telegram_messages.workspace_id` for unmapped chats — drop or buffer?**
   - What we know: The dispatcher resolves `workspace_id` from `telegram_chat_workspace`. If no mapping exists (e.g., bot received an update from a chat it was added to without a `/start` claim — unusual but possible if bot was added by an admin user without using the deep link), what happens?
   - What's unclear: Drop silently? Reply with "click here to pair"? Buffer?
   - Recommendation: Drop silently and log at INFO. Bots only receive group messages once added by a human; that human can just regenerate a code if they want pairing. Reply-on-unmapped is noisy in groups where ContextOS isn't wanted.

## Sources

### Primary (HIGH confidence)
- **Telegram Bot API — Deep Linking** (https://core.telegram.org/bots/features#deep-linking): payload character set `[A-Za-z0-9_-]`, max 64 chars, `?startgroup=PAYLOAD` → bot receives `/start@<botusername> PAYLOAD` text.
- **Telegram Bot API — `setWebhook`** (https://core.telegram.org/bots/api#setwebhook): one webhook URL per bot, `secret_token` 1-256 chars, `allowed_updates` replaces (not unions) defaults.
- **Telegram Bot API — `Update`** (https://core.telegram.org/bots/api#update): `my_chat_member` IS in default `allowed_updates`; only `chat_member`, `message_reaction`, `message_reaction_count` are excluded by default.
- **Telegram Bot API — `ChatMemberUpdated`** (https://core.telegram.org/bots/api#chatmemberupdated): old/new status fields (`member`, `administrator`, `left`, `kicked`, `restricted`); detection logic for added/kicked.
- **Telegram Bot API — `getUpdates`** (https://core.telegram.org/bots/api#getupdates): default exclusion list confirms `my_chat_member` is on by default.
- **Supabase Realtime — Postgres Changes** (https://supabase.com/docs/guides/realtime/postgres-changes): RLS is evaluated per subscriber; `filter: 'col=eq.value'` syntax.
- **Supabase Realtime Authorization** (https://supabase.com/docs/guides/realtime/authorization): service-role bypass; subscriber RLS.
- **In-repo:** `backend/src/services/telegram_events.py` (`process_telegram_update`, filter logic), `backend/src/services/telegram_bot.py` (`telegram_api_call`, secret-token verification pattern), `backend/src/routers/telegram.py:webhook` (current per-workspace webhook to be replaced), `backend/src/models/telegram.py` (TelegramMessage + uq_tg_msg constraint), `supabase/migrations/00030_telegram_messages.sql` (RLS pattern), `supabase/migrations/00038_early_access_allowlist.sql` (table + service-role write idiom), `apps/web/src/hooks/use-context-pages-realtime.ts` (Realtime hook pattern), `apps/web/src/app/dashboard/activity/activity-timeline.tsx` (filtered postgres_changes pattern), `apps/web/src/app/dashboard/integrations/integration-card.tsx` (card shell + connectForm slot), `apps/web/src/app/dashboard/integrations/slack-reauth-banner.tsx` (banner ergonomics for if-needed-later).

### Secondary (MEDIUM confidence)
- **aiogram Deep Linking** (https://docs.aiogram.dev/en/latest/utils/deep_linking.html): confirms three deep-link modes (`start`, `startgroup`, `startapp`); base64url encode helper convention.
- **Bot API dialog IDs** (https://core.telegram.org/api/bots/ids): supergroup ID range, `-100` prefix convention; supports BIGINT decision.
- **grammY Commands docs** (https://grammy.dev/guide/commands): community confirmation that group-deep-link payloads arrive as `/start@bot <payload>` text.

### Tertiary (LOW confidence — flagged for validation if relied on)
- **WebSearch result on "telegram chat_id range"** (https://am10code.github.io/get-telegram-id/chat-id-guides/): community write-up; verified independently against the official Bot API ID page.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library is already in the codebase; no new deps.
- Architecture (dispatcher + sticky upsert + delete-returning + Realtime): HIGH — verified against in-repo patterns and Telegram official docs.
- Pitfalls: HIGH on Telegram-API mechanics (verified via core.telegram.org); MEDIUM on the supergroup-migration edge case (Pitfall 7) which is a known limitation rather than a near-term blocker.
- UX wording / discretion items: MEDIUM — CONTEXT explicitly leaves these to design review.

**Research date:** 2026-05-03
**Valid until:** ~2026-06-02 (30 days; Telegram Bot API is slow-moving — quarterly cadence with backward-compatible changes; the supergroup chat_id range and `?startgroup=` semantics have been stable for years).
