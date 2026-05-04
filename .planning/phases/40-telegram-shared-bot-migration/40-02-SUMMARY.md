---
phase: 40-telegram-shared-bot-migration
plan: 02
subsystem: ui

tags: [telegram, supabase-realtime, nextjs, react, deep-link, shared-bot, postgres-changes, tailwind]

# Dependency graph
requires:
  - phase: 40-telegram-shared-bot-migration
    provides: "Plan 01 backend — telegram_chat_workspace + telegram_pairing_codes tables, /api/telegram/pairing-code endpoint, global webhook dispatcher with claim_chat (peek-then-burn) running BEFORE process_telegram_update"
  - phase: 26-telegram-chat-integration
    provides: "Existing TelegramConnect surface in Settings → Integrations and the IntegrationCard connectForm prop pattern"
provides:
  - "createTelegramPairingCode() typed API client (POST /api/telegram/pairing-code → {code, deep_link, expires_at})"
  - "TelegramPairingProgress component — 5-phase state machine (idle/minting/waiting/expired/connected), 15-min countdown, Cancel + Regenerate, Supabase Realtime channel filtered by workspace_id=eq.${workspaceId} with removeChannel cleanup"
  - "Rewritten TelegramConnect wrapper that resolves workspace_id client-side via auth.getUser → workspace_members.maybeSingle (mirroring dashboard/page.tsx + activity/page.tsx patterns)"
  - "Realtime publication entry for telegram_chat_workspace (added in migration 00039 patch)"
  - "Tz-aware columns on TelegramPairingCode + TelegramChatWorkspace (DateTime(timezone=True) — matches TIMESTAMPTZ DDL)"
  - "/api/integrations/status Telegram override that surfaces telegram_chat_workspace state as the connected signal"
  - "Env-driven bot username via NEXT_PUBLIC_TELEGRAM_BOT_USERNAME (frontend) and required TELEGRAM_BOT_USERNAME (backend, fail-loud if unset)"
affects: [40-03-cutover-cleanup]

# Tech tracking
tech-stack:
  added: []  # zero new packages — all dependencies already in package.json (lucide-react, sonner, @supabase/supabase-js)
  patterns:
    - "Auto-mint-on-mount for IntegrationCard connectForms (parent only renders the form after the user clicks Connect, so mounting === intent — avoids a redundant 'Start' button)"
    - "Realtime channel name keyed by workspace_id (telegram-pairing-${workspaceId}) so multi-tab/multi-window opens don't share state"
    - "Defense-in-depth Realtime filter (workspace_id=eq.${workspaceId}) layered on top of RLS — RLS would already restrict, but the explicit filter saves payload routing"
    - "Tz-aware datetime columns via Column(DateTime(timezone=True), ...) when DDL declares TIMESTAMPTZ — keeps SQLAlchemy in sync with Postgres types"
    - "Status-endpoint override pattern for cross-table provider state (workspace_integrations stays the default source; per-provider blocks can override after the loop)"
    - "Client-side workspace_id resolution via auth.getUser → workspace_members.maybeSingle (RLS-scoped, safe in untrusted browser context)"

key-files:
  created:
    - "apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx"
  modified:
    - "apps/web/src/lib/api.ts"  # added createTelegramPairingCode + TelegramPairingCodeResponse
    - "apps/web/src/app/dashboard/settings/tabs/telegram-connect.tsx"  # body replaced with TelegramPairingProgress wrapper
    - "supabase/migrations/00039_telegram_shared_bot.sql"  # added Realtime publication entry
    - "backend/src/models/telegram.py"  # tz-aware columns on TelegramPairingCode + TelegramChatWorkspace
    - "backend/src/routers/integrations.py"  # Telegram override on GET /api/integrations/status
    - "backend/src/services/telegram_pairing.py"  # required TELEGRAM_BOT_USERNAME (no fallback)
    - ".planning/phases/40-telegram-shared-bot-migration/deferred-items.md"  # logged 2 pre-existing eslint warnings in integration-cards.tsx

key-decisions:
  - "[40-02] Bot username driven by env var (NEXT_PUBLIC_TELEGRAM_BOT_USERNAME on frontend, TELEGRAM_BOT_USERNAME on backend — fail-loud if missing) instead of a hardcoded literal — operator's real bot is @contextOSdev_bot, not the placeholder @ContextOSBot the plan assumed"
  - "[40-02] /api/integrations/status reads telegram_chat_workspace as the Phase-40 source of truth, OVERRIDING the workspace_integrations row (which is Phase-26 leftover, deleted in Plan 03) — keeps the existing aggregator endpoint shape"
  - "[40-02] Local migration apply pattern: psql -f against the local Supabase DB (supabase db push targets remote only) — should be standardized in a runbook but is operator-side for now"
  - "[40-02] Auto-mint-on-mount inside the connectForm — the IntegrationCard only renders connectForm after the user clicks Connect, so mounting is unambiguous user intent and a separate 'Start' button would be redundant"
  - "[40-02] Workspace_id resolved client-side via auth.getUser → workspace_members.maybeSingle (RLS-scoped) instead of plumbing it through props — matches the existing dashboard/page.tsx + activity/page.tsx pattern, keeps TelegramConnect's prop signature unchanged"
  - "[40-02] Realtime publication entry added to migration 00039 itself (not a separate 00040 patch) — Plan 01's data plane and Plan 02's UI consumer are coupled at the Realtime contract, so the publication grant belongs with the table DDL"
  - "[40-02] Tz-aware columns via Column(DateTime(timezone=True), ...) matching api_key.py — sa_column_kwargs={'server_default': ...} alone produces TIMESTAMP WITHOUT TIME ZONE in SQLAlchemy, which mismatches the migration's TIMESTAMPTZ declaration"

patterns-established:
  - "Auto-mint-on-mount inside IntegrationCard connectForm — apply this same pattern to future deep-link integrations (Discord, etc.) instead of a two-button (Connect → Start) flow"
  - "Per-provider override block in the integrations-status aggregator — when provider state lives outside workspace_integrations, override after the standard loop"
  - "Client-side workspace_id resolution via auth.getUser → workspace_members.maybeSingle for any component that needs to subscribe to a workspace-filtered Realtime channel"
  - "Migration files include their Realtime publication grants alongside the table DDL — keeps the Realtime contract co-located with the schema"

requirements-completed:
  - TG-05  # one-click Connect via @<bot> deep link, inline progress block with countdown + Cancel + Regenerate, Realtime flip to connected without page reload

# Metrics
duration: ~30min active execution (Task 3 human-verify gate spanned ~19h wall-clock for operator BotFather/ngrok setup)
completed: 2026-05-04
---

# Phase 40 Plan 02: Telegram Shared-Bot Frontend Pairing UI Summary

**One-click "Connect via @ContextOSBot" deep-link flow with inline progress block (countdown + Cancel + Regenerate) and Supabase Realtime subscription that flips Settings → Integrations Telegram card to "connected" within ~1s of the bot's claim — replacing the Phase-26 bot-token paste form**

## Performance

- **Duration:** ~30 min active execution. Total wall-clock: 2026-05-03T14:47:45Z → 2026-05-04T10:01:39Z (~19h 14m), driven by the Task 3 human-verify gate where the operator did one-time BotFather setup, env var configuration, ngrok webhook registration, manual local migration apply, and the live pair test.
- **Started:** 2026-05-03T14:47:45Z
- **Completed:** 2026-05-04T10:01:39Z
- **Tasks:** 3 (Tasks 1+2 autonomous, Task 3 human-verify checkpoint with 4 deviations fixed inline)
- **Files created:** 1 (`telegram-pairing-progress.tsx`)
- **Files modified:** 7 (api.ts, telegram-connect.tsx, integration-cards.tsx wiring confirmed unchanged, migration 00039, models/telegram.py, routers/integrations.py, services/telegram_pairing.py, deferred-items.md)

## Accomplishments

- **One-click pairing UI live end-to-end** — operator paired chat -1003644773967 ("contextOS team") to workspace c16bbb85-6ce7-4ed9-85e1-a9d8355e23e7 via the new flow. UI flipped to connected within ~1s of the bot's claim; page reload preserved connected state with chat_title displayed.
- **TelegramPairingProgress component** — 5-phase state machine with auto-mint-on-mount, 1-second countdown ticker, Realtime subscription filtered by workspace_id, StrictMode-safe cleanup via supabase.removeChannel.
- **TelegramConnect rewritten as a thin wrapper** — bot-token form gone; the file now resolves workspace_id (auth.getUser → workspace_members.maybeSingle) and renders TelegramPairingProgress.
- **Four runtime gaps closed during Task 3** — Realtime publication entry, tz-aware datetime columns, /api/integrations/status Telegram override, env-driven bot username (see Deviations from Plan).
- **TG-05 satisfied** on the Settings surface. Onboarding (`step-sources.tsx`) wiring is Plan 03's scope per the plan's explicit boundary.

## Task Commits

Each task was committed atomically:

1. **Task 1: createTelegramPairingCode + TelegramPairingProgress** — `53ad5b1` (feat)
2. **Task 2: TelegramConnect wrapper rewrite + integration-cards.tsx wiring confirmation** — `6655c14` (feat)
3. **Task 3: Live UX verification + 4 inline-fix deviations** — `aab5bed` (fix)

**Plan metadata:** to be appended via `docs(40-02): complete telegram-frontend-pairing-ui plan` after this SUMMARY lands.

## Files Created/Modified

### Created

- `apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx` — 5-phase state machine, auto-mint-on-mount, Realtime channel `telegram-pairing-${workspaceId}` filtered on `workspace_id=eq.${workspaceId}`, 1-second countdown ticker, env-driven user-facing bot username, removeChannel cleanup. ~230 lines including comments.

### Modified

- `apps/web/src/lib/api.ts` — Added `TelegramPairingCodeResponse` interface and `createTelegramPairingCode()` typed client. Legacy `connectTelegram(botToken)` preserved for Plan 03 cleanup.
- `apps/web/src/app/dashboard/settings/tabs/telegram-connect.tsx` — Body replaced with a thin shell that resolves workspace_id and renders `<TelegramPairingProgress />`. Bot-token paste form removed.
- `supabase/migrations/00039_telegram_shared_bot.sql` — Added idempotent `ALTER PUBLICATION supabase_realtime ADD TABLE public.telegram_chat_workspace` block. Without this, Realtime INSERT events never fire (root cause of why Task 3 initially didn't flip to connected).
- `backend/src/models/telegram.py` — Switched `TelegramPairingCode.{expires_at, created_at}` and `TelegramChatWorkspace.{paired_at, removed_at}` from plain `datetime` (which SQLAlchemy maps to `TIMESTAMP WITHOUT TIME ZONE`) to `Column(DateTime(timezone=True), ...)` matching the migration's `TIMESTAMPTZ` DDL.
- `backend/src/routers/integrations.py` — Added a Telegram-specific block after the standard provider loop in `GET /api/integrations/status` that overrides `statuses[Provider.TELEGRAM]` from `telegram_chat_workspace` (Phase-40 source of truth) instead of `workspace_integrations` (Phase-26 leftover).
- `backend/src/services/telegram_pairing.py` — Removed the `or "ContextOSBot"` fallback in `generate_pairing_code`; raises `RuntimeError` if `TELEGRAM_BOT_USERNAME` is unset (fail-loud — silent fallback hid the misconfiguration during Task 3).
- `.planning/phases/40-telegram-shared-bot-migration/deferred-items.md` — Logged 2 pre-existing eslint warnings in `integration-cards.tsx` (unused `Skeleton` import, stale `eslint-disable`) for Plan 03 cleanup. Plan 40-02 made zero edits to `integration-cards.tsx`.

## Decisions Made

All key decisions captured in frontmatter. Highlights:

1. **Env-driven bot username (NEXT_PUBLIC_TELEGRAM_BOT_USERNAME + TELEGRAM_BOT_USERNAME, no fallback).** Plan assumed the bot would be `@ContextOSBot`; operator reserved `@contextOSdev_bot` instead. Both surfaces (frontend copy + backend deep-link generator) now read from env. Backend raises if unset to surface misconfigurations early.
2. **`/api/integrations/status` Telegram override.** The aggregator queries `workspace_integrations` for every provider — but Phase-40 connection state lives in `telegram_chat_workspace`. Rather than refactoring the aggregator, a per-provider override after the standard loop surfaces `telegram_chat_workspace` data when active rows exist. Cheap, contained, doesn't affect other providers.
3. **Local migration apply via `psql -f`.** `supabase db push` only targets the linked remote project. For local Supabase containers (used here for verification) the migration must be applied with `psql -f supabase/migrations/00039_telegram_shared_bot.sql ${LOCAL_SUPABASE_URL}`. Should be standardized in a runbook later; tracked as future work in `.planning/phases/40-telegram-shared-bot-migration/40-CONTEXT.md` candidates.
4. **Auto-mint-on-mount inside connectForm.** IntegrationCard already gates `connectForm` rendering behind a Connect button click — so mounting === user intent. Adding a separate "Start" button would be redundant. The `phase === 'idle'` check in the mount effect handles the brief window before `startPairing` flips state.
5. **Client-side workspace_id resolution.** `auth.getUser → workspace_members.maybeSingle` mirrors `dashboard/page.tsx` and `activity/page.tsx`. RLS scopes the SELECT to the user's own membership row, so this is safe in the browser. Avoids plumbing a workspace_id prop through `IntegrationCards → IntegrationCard → connectForm`.
6. **Realtime publication entry lives in migration 00039 itself, not a 00040 patch.** Plan 01 introduced the table; Plan 02's UI is the only consumer of the Realtime stream. Coupling the publication grant to the table DDL means future drops/recreates carry the grant automatically.
7. **`Column(DateTime(timezone=True), ...)` over `sa_column_kwargs`.** `sa_column_kwargs={"server_default": sa_text("now()")}` alone leaves SQLAlchemy emitting `TIMESTAMP WITHOUT TIME ZONE` for the column, which mismatches `00039`'s `TIMESTAMPTZ`. Explicit `Column(DateTime(timezone=True), ...)` matches the existing `api_key.py` pattern and makes the typing intent unambiguous.

## Deviations from Plan

The plan assumed Wave 1 had shipped a complete Realtime contract and that the
operator bot would be `@ContextOSBot`. Live verification surfaced four runtime
gaps that violated must_have invariants ("Settings UI flips to 'connected'
state within ~1s without a page reload"). All four were within Plan 40-02 scope
and were fixed inline as deviations rather than deferred.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Realtime publication missing for `telegram_chat_workspace`**

- **Found during:** Task 3 (live pair test step 8 — bot's reply landed in chat but the dashboard UI did not flip)
- **Issue:** `00039` created `telegram_chat_workspace` but did NOT add it to the `supabase_realtime` publication. Without that grant, INSERT events never reach connected clients, so the `TelegramPairingProgress` Realtime channel received nothing.
- **Fix:** Added an idempotent `DO $$ ALTER PUBLICATION supabase_realtime ADD TABLE public.telegram_chat_workspace; EXCEPTION WHEN duplicate_object THEN NULL; END $$;` block to `00039`. Applied to local DB via `psql -f`.
- **Files modified:** `supabase/migrations/00039_telegram_shared_bot.sql`
- **Verification:** Re-ran live pair test post-fix — INSERT delivered to client, UI flipped to connected within ~1s.
- **Committed in:** `aab5bed`

**2. [Rule 1 - Bug] tz-naive datetime columns mismatch `TIMESTAMPTZ` DDL**

- **Found during:** Task 3 (POST /api/telegram/pairing-code returning 500 with `TypeError: can't subtract offset-naive and offset-aware datetimes`)
- **Issue:** `TelegramPairingCode.{expires_at, created_at}` and `TelegramChatWorkspace.{paired_at, removed_at}` were declared as plain `datetime` fields. SQLAlchemy mapped these to `TIMESTAMP WITHOUT TIME ZONE`. Migration `00039` declares the columns as `TIMESTAMPTZ`. INSERT comparisons (`expires_at = now() + interval '15 min'` against the model's tz-naive value) blew up at runtime.
- **Fix:** Switched all four columns to `Column(DateTime(timezone=True), ...)` matching the existing `api_key.py` pattern. Preserves `server_default=now()` on `paired_at` / `created_at`.
- **Files modified:** `backend/src/models/telegram.py`
- **Verification:** Re-ran pytest `tests/test_telegram_pairing.py` (22/22 pass) and re-ran live pair flow end-to-end.
- **Committed in:** `aab5bed`

**3. [Rule 1 - Bug] `/api/integrations/status` ignored Phase-40 connection state**

- **Found during:** Task 3 (after a successful claim, Settings card briefly showed "Connected — refreshing…" then reverted to "disconnected" because `fetchStatuses` returned the old state)
- **Issue:** The aggregator endpoint only consulted `workspace_integrations` (Phase-26 table). Phase-40 inserts a row into `telegram_chat_workspace` instead. Result: post-claim refresh said "disconnected" and the UI flickered.
- **Fix:** Added a Telegram-specific block after the standard provider loop that queries `telegram_chat_workspace` for `removed_at IS NULL` rows for the current workspace; if any exist, overrides `statuses[Provider.TELEGRAM]` with `{status: "connected", external_name: chat_title, connected_at: paired_at, chat_count: len(rows)}`.
- **Files modified:** `backend/src/routers/integrations.py`
- **Verification:** Re-ran pair flow; post-claim refresh now returns `connected` with chat title; page reload preserves connected state.
- **Committed in:** `aab5bed`

**4. [Rule 1 - Bug + Rule 2 - Missing Critical] Hard-coded bot username diverged from real bot**

- **Found during:** Task 3 (operator created `@contextOSdev_bot`, not `@ContextOSBot`; deep link from `/api/telegram/pairing-code` pointed to a bot that doesn't exist)
- **Issue:** Plan 01's `generate_pairing_code` had `bot_username = settings.TELEGRAM_BOT_USERNAME or "ContextOSBot"` — silent fallback hid the misconfiguration. Plan 02's `TelegramPairingProgress` had `Waiting for @ContextOSBot…` hard-coded in the user-facing copy. Both broke for any operator whose reserved BotFather name differs from `ContextOSBot`.
- **Fix:**
  - Backend: removed the fallback; raises `RuntimeError("TELEGRAM_BOT_USERNAME is not configured…")` if unset (fail-loud).
  - Frontend: copy now reads `process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? 'ContextOSBot'` (the literal stays as a sane production default for the eventual public bot, but operator dev environments override it).
- **Files modified:** `backend/src/services/telegram_pairing.py`, `apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx`
- **Verification:** Set `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=contextOSdev_bot` in `apps/web/.env.local` and `TELEGRAM_BOT_TOKEN_GLOBAL` + `TELEGRAM_BOT_USERNAME=contextOSdev_bot` in root `.env`; deep link minted correctly, UI copy displayed `@contextOSdev_bot`.
- **Committed in:** `aab5bed`

---

**Total deviations:** 4 auto-fixed (1 Rule 3 blocking, 2 Rule 1 bugs, 1 mixed Rule 1 + Rule 2)
**Impact on plan:** All four were within scope (must_have requires the Settings UI to flip to "connected" — none of that works without these four fixes). No scope creep; legacy `TelegramSyncSection` and `disconnectTelegram` import in `integration-cards.tsx` left intact for Plan 03 per the plan's explicit boundary.

## Issues Encountered

### Operator-side prerequisites the plan didn't surface explicitly

The plan's "Prerequisites — operator side" block in the Task 3 checkpoint
listed BotFather setup and webhook registration but did NOT call out:

1. **Realtime publication grant.** Required for `TelegramPairingProgress` to receive INSERT events. Now part of migration `00039` so future operators get it for free.
2. **Local migration apply pattern.** `supabase db push` only targets the remote project — local containers need `psql -f supabase/migrations/00039_telegram_shared_bot.sql ${LOCAL_SUPABASE_URL}`. Should be standardized in a runbook.
3. **Env var names — `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` (frontend), `TELEGRAM_BOT_TOKEN_GLOBAL` + `TELEGRAM_BOT_USERNAME` (backend).** Plan referenced the backend pair but not the frontend one. Added defensively to `apps/web/.env.local` template (not committed; gitignored). Plan 03 should add a `40-USER-SETUP.md` covering all three.
4. **BotFather → Bot Settings → Group Privacy OFF.** Plan called this out (Pitfall 4); operator confirmed via `getMe` that `can_read_all_group_messages: true` on the live bot. No issue, just noting for completeness.

### Pre-existing test failures (out of scope, unchanged)

7 `test_telegram.py` failures (`TestWebhookEndpoint::test_accepts_valid_secret`
+ 6 `TestProcessTelegramUpdate::*`) remain. Verified pre-existing in
`deferred-items.md` during Plan 40-01 and re-verified untouched here:
22/22 `test_telegram_pairing.py` pass after the Plan 40-02 model changes;
the 7 legacy failures are unaffected. Plan 40-03 will delete the legacy
routes these tests cover.

### Two pre-existing eslint warnings in `integration-cards.tsx`

Already logged in `deferred-items.md` during Task 2 — Plan 40-02 makes zero
edits to that file. Plan 03 will clean them up alongside the
`<TelegramSyncSection />` removal.

## User Setup Required

The frontend env var `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` is now operator-side.
For the production rollout, Plan 03 should generate a `40-USER-SETUP.md`
covering (consolidated for convenience):

- Frontend (`apps/web/.env.local`): `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=<bot_handle_without_@>`
- Backend (`backend/.env` or root `.env`): `TELEGRAM_BOT_TOKEN_GLOBAL=<token>`, `TELEGRAM_BOT_USERNAME=<bot_handle>`, `TELEGRAM_WEBHOOK_SECRET=<secret>`
- BotFather: `/newbot` → reserve handle → **Bot Settings → Group Privacy OFF** (required for the bot to read group messages — Pitfall 4)
- Local DB: apply migration via `psql -f supabase/migrations/00039_telegram_shared_bot.sql "$LOCAL_SUPABASE_URL"` (`supabase db push` is for remote)
- Webhook: one-shot `curl POST https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN_GLOBAL}/setWebhook` with `allowed_updates=[message,edited_message,my_chat_member]` and `secret_token=${TELEGRAM_WEBHOOK_SECRET}`

This plan does not create `40-USER-SETUP.md` because the plan frontmatter
didn't declare `user_setup`. Plan 03 (cutover/cleanup) is the natural place.

## Next Phase Readiness

- **Plan 40-03 (cutover/cleanup) ready to execute.** Scope:
  - Delete `connectTelegram(botToken)`, `disconnectTelegram` legacy import in `integration-cards.tsx`, `<TelegramSyncSection />`, the legacy `/connect`/`/disconnect`/`/sync`/`/sync/status`/`/webhook/{workspace_id}` routes, the `connect_telegram_bot`/`disconnect_telegram_bot` service helpers, and the 7 pre-existing legacy tests in `test_telegram.py`.
  - Wire `TelegramPairingProgress` into `step-sources.tsx` (onboarding surface — Plan 02 explicit boundary).
  - Generate `40-USER-SETUP.md` as outlined above.
  - Address pre-existing `Skeleton` + `eslint-disable` warnings in `integration-cards.tsx` while editing it.
- **No blockers.** The Realtime contract, tz columns, status-endpoint override, and env-driven bot identity are all live. Operator's bot `@contextOSdev_bot` is registered, webhook is live on ngrok, and the live pair test confirms end-to-end flow.

## Self-Check: PASSED

Verified after final metadata commit:
- `40-02-SUMMARY.md` exists (237 lines).
- All four commits present on `main`: `53ad5b1` (Task 1 feat), `6655c14` (Task 2 feat), `aab5bed` (Task 3 deviations fix), `2d3c58a` (docs metadata).
- All 7 plan files present on disk (1 created + 6 modified).
- `createTelegramPairingCode` symbol resolves in `apps/web/src/lib/api.ts`; `TelegramPairingProgress` resolves in `telegram-pairing-progress.tsx` and `telegram-connect.tsx`.
- TG-05 marked `[x]` in `REQUIREMENTS.md` (line 52) and traceability row shows Complete (line 109).
- ROADMAP.md plans `40-01` and `40-02` checkboxes flipped to `[x]`; `40-03` remains `[ ]`.
- STATE.md `current_plan: 3`, `completed_plans: 11/12`, last_activity reflects Plan 40-02.

---

*Phase: 40-telegram-shared-bot-migration*
*Plan: 02*
*Completed: 2026-05-04*
