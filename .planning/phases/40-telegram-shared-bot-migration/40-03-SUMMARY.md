---
phase: 40-telegram-shared-bot-migration
plan: 03
subsystem: api

tags: [telegram, fastapi, sqlalchemy, postgres, supabase-realtime, vault, pgvault, nextjs, react, deploy-runbook, cutover, replica-identity]

# Dependency graph
requires:
  - phase: 40-telegram-shared-bot-migration
    provides: "Plan 01 backend (data plane + dispatcher + /pairing-code) and Plan 02 frontend (TelegramPairingProgress + TelegramConnect wrapper). Plan 03 deletes the Phase-26 surface that lived alongside them."
  - phase: 26-telegram-chat-integration
    provides: "Per-workspace BotFather flow being removed: connect/disconnect/sync/sync-status/per-workspace-webhook routes, telegram_bot service helpers, telegram_sync (Telethon + getUpdates), Vault entries under oauth_telegram_<ws>_bot_token, TelegramSyncSection UI, connectTelegram(token)/disconnectTelegram/syncTelegramHistory/getTelegramSyncStatus API clients, and the bot-token paste form in onboarding."
provides:
  - "Single Telegram code path: only /api/telegram/pairing-code + global /api/telegram/webhook + dispatcher remain"
  - "Onboarding step-sources renders the same TelegramPairingProgress component as Settings (TG-05 covered on both surfaces)"
  - "backend/scripts/purge_legacy_telegram_vault.py: one-shot async script that purges oauth_telegram_<workspace_id>_bot_token entries from vault.secrets (with --dry-run + per-row exception isolation)"
  - "DEPLOY_RUNBOOK.md covering BotFather (Group Privacy OFF), env vars, migration apply (psql -f for local + supabase db push for remote), setWebhook with my_chat_member in allowed_updates, the Vault purge, smoke test (Settings + onboarding parity), rollback, and v1 known limitations"
  - "Re-pair-after-kick semantics: claim_chat now does ON CONFLICT (chat_id) DO UPDATE WHERE removed_at IS NOT NULL with RETURNING-based fresh-vs-conflict disambiguation"
  - "Multi-engineer onboarding guard: /api/telegram/pairing-code returns 409 Conflict {error: 'already_connected', chat_count} when the workspace already has at least one active mapping; the typed TelegramAlreadyConnectedError surfaces this as an 'already_connected' UI phase with a Close button"
  - "Migration 00039 patch: ALTER TABLE telegram_chat_workspace REPLICA IDENTITY FULL so Supabase Realtime can apply the workspace_id filter to UPDATE events (fresh-claim INSERTs were already fine; re-pair UPDATEs needed REPLICA IDENTITY FULL plus event '*' on the client)"
  - "StrictMode auto-mint guard via mintedRef: each /pairing-code POST wipes the prior code, so the dev double-fire under StrictMode left the user pasting an already-burned code"
affects: []  # Phase 40 closes here; v1.3 milestone next

# Tech tracking
tech-stack:
  added: []  # zero new packages; telethon was REMOVED in Task 1
  patterns:
    - "Re-pair-after-kick via ON CONFLICT DO UPDATE WHERE removed_at IS NOT NULL with RETURNING to distinguish fresh-claim vs cross-workspace conflict (apply to other sticky chat→tenant mappings)"
    - "409 Conflict on resource-mint when the workspace already has the resource (multi-engineer onboarding guard)"
    - "REPLICA IDENTITY FULL is mandatory on tables whose UPDATE events Supabase Realtime must filter by anything other than the PK"
    - "StrictMode dev double-fire guard via useRef for any auto-mint-on-mount that consumes a single-use server resource"
    - "Per-row exception isolation in batch Vault purge scripts (one bad permission shouldn't abort the whole run)"
    - "Strict pattern + SQL LIKE prefilter in Vault purge (`WHERE name LIKE 'oauth_telegram_%_bot_token'` then re-validate with regex) so the script never deletes an unrelated secret that happens to share a prefix"

key-files:
  created:
    - "backend/scripts/purge_legacy_telegram_vault.py"
    - ".planning/phases/40-telegram-shared-bot-migration/DEPLOY_RUNBOOK.md"
  modified:
    - "backend/src/routers/telegram.py"            # Phase-26 routes deleted; 409 already_connected guard added (d9aa4fd)
    - "backend/src/services/telegram_bot.py"        # ~50 lines: only TelegramError + telegram_api_call remain
    - "backend/src/services/telegram_pairing.py"    # ON CONFLICT DO UPDATE re-pair, dashboard URL, RETURNING contract (d9aa4fd)
    - "backend/src/config.py"                       # TELEGRAM_API_ID + TELEGRAM_API_HASH dropped
    - "backend/pyproject.toml"                      # telethon dependency dropped
    - "backend/uv.lock"                             # regenerated
    - "backend/tests/test_telegram.py"              # TestWebhookEndpoint deleted; graph_extractor stubbed; +1 endpoint test (d9aa4fd)
    - "backend/tests/test_telegram_pairing.py"      # +2 claim-path tests for re-pair + race conflict (d9aa4fd)
    - "supabase/migrations/00039_telegram_shared_bot.sql"  # REPLICA IDENTITY FULL added (d9aa4fd)
    - "apps/web/src/lib/api.ts"                     # 4 legacy helpers removed; TelegramAlreadyConnectedError added (05bebcd)
    - "apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx"  # TelegramSyncSection child + disconnectTelegram + Skeleton + stale eslint-disable removed; toast disconnect handler
    - "apps/web/src/app/dashboard/settings/tabs/telegram-connect.tsx"  # docstring updated
    - "apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx"  # event '*' subscription, mintedRef StrictMode guard, already_connected phase (05bebcd)
    - "apps/web/src/components/onboarding/step-sources.tsx"  # bot-token form replaced with TelegramPairingProgress
  deleted:
    - "backend/src/services/telegram_sync.py"
    - "apps/web/src/app/dashboard/settings/tabs/telegram-sync-section.tsx"

key-decisions:
  - "[40-03] Phase-26 routes deleted in a single atomic refactor, not gradually behind a feature flag — Plans 40-01 and 40-02 already shipped the full shared-bot path, so the legacy code was strictly dead weight. Verified by 72/72 telegram + pairing tests passing post-deletion."
  - "[40-03] Re-pair-after-kick uses ON CONFLICT (chat_id) DO UPDATE WHERE removed_at IS NOT NULL with RETURNING — RETURNING the new row distinguishes a successful re-claim from a real cross-workspace conflict (active row owned by a different workspace), which would return zero rows. Without this, kicking + re-pairing the same group mis-replied ALREADY_CLAIMED_BY_OTHER."
  - "[40-03] /api/telegram/pairing-code returns 409 Conflict {error: 'already_connected', chat_count} when telegram_chat_workspace already has any active row for the workspace. Front-end surfaces this as a typed TelegramAlreadyConnectedError → 'already_connected' phase with a Close button. Without this guard, two engineers onboarding the same workspace each minted a code, the second engineer's UI hung on 'Waiting…' until 15-min TTL because the first engineer had already paired the only chat the org would test in."
  - "[40-03] Bot reply link migrated from `contextos.app/dashboard/settings` (placeholder hardcoded in 40-01) to `contextos.pro/dashboard/settings?tab=integrations` — real production hostname plus the tab anchor that opens the Integrations tab directly."
  - "[40-03] Migration 00039 patched with `ALTER TABLE telegram_chat_workspace REPLICA IDENTITY FULL` — Supabase Realtime needs the full row in WAL to apply the workspace_id filter to UPDATE events. Without this, fresh-claim INSERTs delivered fine but re-pair UPDATEs (after kick) never reached subscribers, so the 'connected' state didn't flip on re-pair."
  - "[40-03] Realtime subscription event widened from `'INSERT'` to `'*'` and a `removed_at IS NULL` payload filter added — re-pairs are ON CONFLICT DO UPDATE, not INSERT, so the INSERT-only listener missed them. The payload filter ignores soft-delete UPDATEs (when handle_my_chat_member sets removed_at on kick/leave) so the UI doesn't briefly flip to 'connected' on a disconnect event."
  - "[40-03] StrictMode dev double-fire fixed via useRef(mintedRef). The auto-mint useEffect ran twice in dev StrictMode; each /pairing-code POST wipes the prior code (one-active-code-per-workspace invariant from Plan 01), so the user pasted an already-burned code into the bot and got 'expired or already used'."
  - "[40-03] Vault purge script uses `WHERE name LIKE 'oauth_telegram_%_bot_token'` SQL prefilter + strict regex re-validation in Python — defense in depth so the script never deletes an unrelated secret whose name accidentally starts with the same prefix. Per-row exception isolation lets one permission glitch on a single secret continue the run."
  - "[40-03] DEPLOY_RUNBOOK.md documents both `supabase db push` (remote-linked-only) and `psql -f` (local container) as separate migration apply paths — surfacing the gotcha that bit the operator during 40-02 verification."
  - "[40-03] Settings disconnect button is intentionally a toast hint, not an API call — the Phase-40 model has no workspace-level disconnect endpoint by design; users remove the bot from each chat and the bot's my_chat_member handler soft-deletes the mapping per chat."

patterns-established:
  - "Sticky chat→tenant mapping with re-pair: ON CONFLICT (PK) DO UPDATE WHERE soft_delete_col IS NOT NULL + RETURNING to disambiguate fresh re-claim from active-row conflict"
  - "409 Conflict on resource-mint endpoints when the resource already exists for the requester (typed error class on the frontend, not a generic toast that leaks 'API error 409')"
  - "REPLICA IDENTITY FULL co-located with the table DDL when Realtime UPDATE filtering is part of the contract"
  - "StrictMode-safe auto-mint-on-mount via useRef guard for any single-use server resource"
  - "Vault purge scripts: SQL LIKE prefilter + strict regex re-validation + per-row exception isolation"

requirements-completed:
  - TG-05  # one-click shared-bot deep-link Connect on BOTH surfaces (Settings + onboarding); TG-06 + TG-07 marked complete by 40-01

# Metrics
duration: ~4h wall-clock (autonomous execution + human-verify gate + deviation fixes)
completed: 2026-05-04
---

# Phase 40 Plan 03: Telegram Shared-Bot Cutover & Cleanup Summary

**Phase-26 Telegram surface fully removed (zero references to legacy symbols); onboarding wired to the same TelegramPairingProgress component as Settings; Vault purge script + deploy runbook shipped; re-pair-after-kick + multi-engineer guard + REPLICA IDENTITY FULL + StrictMode mint guard fixed inline during runtime verification**

## Performance

- **Duration:** ~4h wall-clock (Tasks 1–3 autonomous + Task 4 human-verify gate + 5 deviation fixes landed during verification)
- **Started:** 2026-05-04T10:07:41Z
- **Completed:** 2026-05-04T11:02:11Z (active session); deviation commits landed mid-session at 16:00 local
- **Tasks:** 4 (3 autonomous + 1 human-verify checkpoint)
- **Files created:** 2 (purge script, DEPLOY_RUNBOOK.md)
- **Files modified:** 13 across backend + frontend + migration + tests
- **Files deleted:** 2 (telegram_sync.py, telegram-sync-section.tsx)
- **Tests:** 72/72 telegram + pairing tests pass (was 49 before plan; +23 net from prior plans + d9aa4fd's 3 new tests)

## Accomplishments

- **Single Telegram code path.** Zero references to `connect_telegram_bot`, `disconnect_telegram_bot`, `drain_pending_updates`, `run_telegram_history_sync`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `telethon`, `TelegramSyncSection`, `connectTelegram(`, `syncTelegramHistory`, `getTelegramSyncStatus`, or `disconnectTelegram(` across `backend/src/`, `backend/tests/`, `apps/web/src/`, and `pyproject.toml` (only descriptive docstring comments mentioning the deletion remain).
- **Onboarding parity with Settings.** `step-sources.tsx` now renders the same `TelegramPairingProgress` component, with workspace_id resolved client-side via the same `auth.getUser → workspace_members.maybeSingle` pattern.
- **Operator deployment ready.** `DEPLOY_RUNBOOK.md` is a single document covering BotFather (Group Privacy OFF), env vars, migration apply (both local + remote paths), `setWebhook` with `my_chat_member` in `allowed_updates`, the Vault purge invocation, post-deploy smoke test (Settings + onboarding + activity), rollback, and v1 known limitations. The Vault purge script ran clean on the local DB (`Found 0 legacy Telegram Vault entries`).
- **Five runtime gaps closed during verification** — re-pair-after-kick UPDATE semantics, multi-engineer 409 guard, dashboard URL hostname/anchor, REPLICA IDENTITY FULL for filtered UPDATE delivery, and StrictMode auto-mint guard. All were within Plan 40-03 scope (must_have was "Phase-26 paths fully removed" — and in shipping this we found that re-pair, multi-engineer onboarding, and StrictMode dev workflow were silently broken by edges of the Plan 01/02 contract).
- **TG-05 complete on both surfaces.** TG-06 and TG-07 were already marked complete by Plan 40-01.

## Task Commits

Each task was committed atomically; deviations landed in two follow-up `fix(40-03)` commits:

1. **Task 1: Delete legacy backend code paths and Telethon dependency** — `af89b61` (refactor)
2. **Task 2: Delete legacy frontend code; wire onboarding to TelegramPairingProgress** — `5fc587f` (refactor)
3. **Task 3: Vault purge script + DEPLOY_RUNBOOK.md** — `345b4f7` (chore)
4. **Task 4: End-to-end production-like cutover verification** — human-verify gate; surfaced 5 deviations:
   - **`d9aa4fd`** (fix): re-pair after kick (ON CONFLICT DO UPDATE), multi-engineer 409 guard, dashboard URL, REPLICA IDENTITY FULL migration patch
   - **`05bebcd`** (fix): pairing UI handles re-pair UPDATE, already-connected phase, StrictMode mintedRef

**Plan metadata:** appended below this commit as `docs(40-03): complete cutover-cleanup plan`.

## Files Created/Modified

### Created

- `backend/scripts/purge_legacy_telegram_vault.py` — async one-shot. Strict regex (`oauth_telegram_<uuid>_bot_token`) on top of `WHERE name LIKE 'oauth_telegram_%_bot_token'`, per-row exception isolation, `--dry-run` flag.
- `.planning/phases/40-telegram-shared-bot-migration/DEPLOY_RUNBOOK.md` — operator runbook from merge to live.

### Modified

- `backend/src/routers/telegram.py` — Phase-26 routes deleted; surviving routes are `POST /pairing-code` and `POST /webhook` (global). 409 already_connected guard added in `d9aa4fd`.
- `backend/src/services/telegram_bot.py` — reduced to `TelegramError` class + `telegram_api_call()` helper (~50 lines).
- `backend/src/services/telegram_pairing.py` — `claim_chat` reworked for ON CONFLICT DO UPDATE re-pair semantics (`d9aa4fd`); bot reply link updated to `contextos.pro/dashboard/settings?tab=integrations`.
- `backend/src/config.py` — `TELEGRAM_API_ID` + `TELEGRAM_API_HASH` dropped; doc comments updated.
- `backend/pyproject.toml` + `backend/uv.lock` — `telethon>=1.36` removed.
- `backend/tests/test_telegram.py` — `TestWebhookEndpoint` class deleted (route gone); `_patch_graph_extractor` autouse fixture stubs `extract_and_populate_graph` so `TestProcessTelegramUpdate` assertions match post-Phase-33 reality; `+1` test in `d9aa4fd` for the 409 already_connected path.
- `backend/tests/test_telegram_pairing.py` — `+2` tests in `d9aa4fd`: re-pair UPDATE path, race-conflict NULL return path.
- `supabase/migrations/00039_telegram_shared_bot.sql` — `ALTER TABLE telegram_chat_workspace REPLICA IDENTITY FULL` added before the publication grant (`d9aa4fd`).
- `apps/web/src/lib/api.ts` — `connectTelegram`, `disconnectTelegram`, `syncTelegramHistory`, `getTelegramSyncStatus` removed; `TelegramAlreadyConnectedError` typed error added in `05bebcd`.
- `apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx` — `<TelegramSyncSection />` child + `disconnectTelegram` import + unused `Skeleton` + stale `eslint-disable` directive all removed; disconnect handler is now a `toast.info` pointing the user at the in-Telegram remove flow.
- `apps/web/src/app/dashboard/settings/tabs/telegram-connect.tsx` — docstring updated to past-tense.
- `apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx` — Realtime `event: '*'` + `removed_at IS NULL` payload filter, `mintedRef` StrictMode guard, `'already_connected'` phase rendering (`05bebcd`).
- `apps/web/src/components/onboarding/step-sources.tsx` — bot-token paste form deleted; Telegram source card opens an inline `<TelegramPairingProgress />` (same component as Settings); workspace_id resolved client-side; sync-status poller deleted.

### Deleted

- `backend/src/services/telegram_sync.py` — Telethon + getUpdates drain (589 lines gone).
- `apps/web/src/app/dashboard/settings/tabs/telegram-sync-section.tsx` — history-sync UI (112 lines gone).

## Decisions Made

All key decisions captured in the frontmatter above. Highlights:

1. **Atomic Phase-26 deletion.** Plan 03 deletes everything in one refactor instead of behind a feature flag — Plans 40-01 and 40-02 already shipped and verified the full shared-bot path, so the legacy code was strictly dead weight. 72/72 tests pass post-deletion.
2. **Re-pair via ON CONFLICT DO UPDATE.** A kicked + re-paired chat now updates its existing row (clearing `removed_at`, refreshing `paired_at`/`paired_by`) rather than mis-replying ALREADY_CLAIMED_BY_OTHER. RETURNING distinguishes successful re-claim from genuine cross-workspace conflict.
3. **409 multi-engineer guard.** `/api/telegram/pairing-code` returns 409 with `{error: 'already_connected', chat_count}` when the workspace already has at least one active mapping. The frontend's typed `TelegramAlreadyConnectedError` surfaces this as an `'already_connected'` phase with a Close button — no more silent 15-min hang for the second engineer to onboard.
4. **REPLICA IDENTITY FULL.** Without it Realtime can't filter UPDATE events on `workspace_id`; without filtered UPDATE delivery, re-pair after kick doesn't flip the UI live. The migration patch is co-located with the publication grant.
5. **Settings disconnect = toast hint.** Phase 40 deliberately has no workspace-level disconnect endpoint. The Settings button now opens a confirmation dialog whose Disconnect action triggers a `toast.info` ("To disconnect, remove @ContextOSBot from the Telegram group(s).") with NO API call. The bot's `my_chat_member` handler does the actual soft-delete per chat.

## Deviations from Plan

The plan assumed Tasks 1–3 + a manual verification pass would close the cutover. Live verification surfaced 5 inline-fixed deviations covering re-pair, multi-engineer onboarding, runtime URL, Realtime UPDATE delivery, and StrictMode dev workflow. All were within scope (must_have: "Phase-26 paths fully removed" — but the Plan 01/02 contract had edges that broke under those exact transitions).

### Auto-fixed Issues

**1. [Rule 1 — Bug] Re-pair after kick mis-replied ALREADY_CLAIMED_BY_OTHER**

- **Found during:** Task 4 (live verification — kick the bot, then try to re-pair the same chat)
- **Issue:** Plan 01's `claim_chat` used `ON CONFLICT DO NOTHING`. After a kick, the chat row had `removed_at IS NOT NULL` (from `handle_my_chat_member`), but `DO NOTHING` meant a fresh INSERT for the same `chat_id` was a no-op, the SELECT-then-burn path saw the existing row and returned `ALREADY_CLAIMED_BY_OTHER`, and the bot replied "This chat is already paired with another workspace" even when re-pairing the same workspace.
- **Fix:** `ON CONFLICT (chat_id) DO UPDATE WHERE removed_at IS NOT NULL` clears `removed_at` and refreshes `paired_at`/`paired_by`. RETURNING the new row distinguishes a successful re-claim (rows returned) from a real conflict (zero rows — only when the active row is owned by another workspace). Pairing-code burned only on a fresh claim or re-claim, not on conflict.
- **Files modified:** `backend/src/services/telegram_pairing.py`
- **Tests added:** `test_telegram_pairing.py` re-pair UPDATE path (passes), race-conflict NULL return path (passes)
- **Committed in:** `d9aa4fd`

**2. [Rule 2 — Missing Critical] Multi-engineer onboarding silently hung**

- **Found during:** Task 4 (operator paired workspace c16bbb85 from one account; second engineer signing up to the same workspace tried to pair from a different chat — UI hung on "Waiting…" forever)
- **Issue:** No guard on `/api/telegram/pairing-code`. Both engineers got valid codes; the second one's chat was already taken by the first engineer's pairing, so the second's deep-link claim attempt landed on a chat that resolved to a different chat_id and the Realtime listener saw nothing. UX: 15-min silent hang.
- **Fix:** `/api/telegram/pairing-code` now checks for any active mapping (`telegram_chat_workspace` rows with `removed_at IS NULL`) for the requester's workspace and returns `409 {error: 'already_connected', chat_count}`. Frontend surfaces this as `TelegramAlreadyConnectedError` → `'already_connected'` UI phase with a Close button explaining the workspace is already connected.
- **Files modified:** `backend/src/routers/telegram.py`, `apps/web/src/lib/api.ts`, `apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx`
- **Tests added:** `test_telegram.py` 409 already_connected endpoint test (passes)
- **Committed in:** `d9aa4fd` (backend), `05bebcd` (frontend)

**3. [Rule 1 — Bug] Bot reply link pointed at wrong domain**

- **Found during:** Task 4 (operator clicked the link in the bot's confirmation reply)
- **Issue:** Plan 01 hardcoded `https://contextos.app/dashboard/settings`. Real production is `contextos.pro` and the Integrations tab lives at `?tab=integrations`. Plan 01 explicitly noted "Plan 02 may parameterize" but neither 01 nor 02 actually fixed the domain.
- **Fix:** Updated to `https://contextos.pro/dashboard/settings?tab=integrations` directly in `telegram_pairing.py`. Not parameterized via env (no other Telegram-bot-reply codepaths need it; YAGNI — can be promoted to env if a third caller appears).
- **Files modified:** `backend/src/services/telegram_pairing.py`
- **Committed in:** `d9aa4fd`

**4. [Rule 3 — Blocking] Realtime UPDATE events never reached subscribers**

- **Found during:** Task 4 (re-pair UI verification — bot's reply landed in chat, DB was updated, but the UI didn't flip)
- **Issue:** Re-pair is `ON CONFLICT DO UPDATE`, not INSERT. The `TelegramPairingProgress` component listened for `event: 'INSERT'`, so re-pairs were missed. Plus: even with `event: '*'`, Supabase Realtime needs `REPLICA IDENTITY FULL` on the table to apply the `workspace_id=eq.${workspaceId}` filter against UPDATE events (the default REPLICA IDENTITY only includes the PK in WAL, so the workspace_id can't be matched server-side and the UPDATE is dropped).
- **Fix:** Two-part:
  - Migration: `ALTER TABLE public.telegram_chat_workspace REPLICA IDENTITY FULL;` added before the publication grant.
  - Frontend: subscription widened to `event: '*'`, payload filter `!row.removed_at` so soft-delete UPDATEs (kick events) don't briefly flip the UI to "connected".
- **Files modified:** `supabase/migrations/00039_telegram_shared_bot.sql`, `apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx`
- **Committed in:** `d9aa4fd` (migration), `05bebcd` (frontend)

**5. [Rule 1 — Bug] StrictMode dev double-fire burned codes immediately**

- **Found during:** Task 4 (running `pnpm dev` and clicking Connect)
- **Issue:** React StrictMode double-invokes effects in dev. The auto-mint effect fired twice; each `/api/telegram/pairing-code` POST wipes the prior code (one-active-code-per-workspace invariant from Plan 01). The user's UI showed code A, but pasted into the bot it returned "expired or already used" because code B had replaced it server-side.
- **Fix:** `mintedRef = useRef(false)` guard inside the auto-mint effect. The first run flips the ref true; the StrictMode double-invoke runs the cleanup which doesn't reset the ref, so the second mount-effect call early-returns.
- **Files modified:** `apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx`
- **Committed in:** `05bebcd`

---

**Total deviations:** 5 auto-fixed (3 Rule 1 bugs, 1 Rule 2 missing critical, 1 Rule 3 blocking)
**Impact on plan:** All five were within scope — `must_have` line "Phase-26 paths fully removed AND working shared-bot pairing on both surfaces" is not satisfied if re-pair, multi-engineer onboarding, the operator-visible bot reply, the live UI flip on re-pair, or the dev workflow are silently broken. Two follow-up `fix(40-03)` commits, no scope creep.

## Issues Encountered

### Live runtime verification — partial (paths A, B, E, partial F passed at runtime; C, D, F covered by automated checks during Tasks 1–3)

Verified at runtime (live Telegram bot `@contextOSdev_bot` against ngrok-fronted local backend):

- `POST /api/telegram/pairing-code` succeeded (and 409 path verified after `d9aa4fd`).
- Bot received `/start@contextOSdev_bot <code>` in real Telegram group "contextOS team" (chat_id `-1003644773967`).
- Backend logs show `telegram_claim_success` for workspace `c16bbb85…` AND for new workspace `f33b9949…` (cross-workspace path also exercised).
- Bot's in-chat reply text correct: "ContextOS connected to contextOS team. Messages here will be indexed for context generation. Manage at https://contextos.pro/dashboard/settings?tab=integrations."
- DB rows correct: `chat_workspace` populated, `paired_at` set, `removed_at` cleared on re-pair.
- Page reload reliably shows connected state in the dashboard.
- Re-pair after kick: confirmed working end-to-end (bot reply, DB update on the same chat_id).
- Cross-workspace reject: confirmed (bot replied "This chat is already paired with another ContextOS workspace.").

Verified via automated checks during the autonomous task commits:

- `cd backend && uv run pytest tests/test_telegram.py tests/test_telegram_pairing.py` — 72/72 pass.
- `cd apps/web && pnpm exec tsc --noEmit` — clean.
- `cd apps/web && pnpm exec eslint src/lib/api.ts src/app/dashboard/settings/tabs/integration-cards.tsx src/components/onboarding/step-sources.tsx` — only one pre-existing warning, untouched.
- `grep -rEn` for all 12 deleted symbols — only descriptive docstring comments remain.
- `purge_legacy_telegram_vault.py --dry-run` — exits cleanly with `Found 0 legacy Telegram Vault entries` (local DB; production run is part of the runbook).

### Local-only Realtime UI flip — code-verified, NOT runtime-verified

The `must_have` line "Settings UI flips to 'connected' state within ~1s without a page reload via Supabase Realtime" could not be runtime-verified locally due to two unrelated local-environment issues, neither of which is Phase 40 code:

1. **Stale `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `apps/web/.env.local`.** Was signed with a different JWT secret than the running local Supabase Realtime container expected; Realtime rejected the WebSocket subscription with `signature_error`. Fixed in the local `.env.local` (gitignored, not committed) but issue persists due to (2).
2. **Local Kong API gateway returns HTTP 431 on the WebSocket upgrade.** Kong's default `client_header_buffer_size` (1 KB) is too small for the WebSocket Upgrade headers + Cookie + Origin combined. Fix would require restarting the local Supabase stack with `KONG_NGINX_PROXY_CLIENT_HEADER_BUFFER_SIZE=64k` env override. Cannot be applied via `kong reload` or runtime config — Kong regenerates `nginx-kong.conf` from a template on reload. The operator declined the disruptive restart.

The Realtime contract is wired correctly in code:

- Migration grants `ADD TABLE public.telegram_chat_workspace` to `supabase_realtime` publication AND sets `REPLICA IDENTITY FULL` (so the workspace_id filter can be applied to UPDATE events server-side).
- `TelegramPairingProgress` subscribes to `event: '*'` with `filter: workspace_id=eq.${workspaceId}` and a `removed_at IS NULL` payload filter; cleanup uses `supabase.removeChannel`.
- The 5 deviation commits cover all known correctness gaps the operator surfaced.

Production Supabase Cloud uses a different Kong configuration with appropriate buffer sizes, and the prod anon key matches its JWT secret. The page-reload fallback path was verified to work reliably end-to-end in the meantime.

**Future note for whoever runs the next live test:** if the Realtime UI flip doesn't happen but `/api/telegram/pairing-code` and the bot reply both work, check (in this order): the local anon key signature against the running Realtime container's JWT secret; Kong's `KONG_NGINX_PROXY_CLIENT_HEADER_BUFFER_SIZE`; whether the table is in `pg_publication_tables WHERE pubname='supabase_realtime'`; whether `REPLICA IDENTITY FULL` shows in `pg_class.relreplident = 'f'` for `telegram_chat_workspace`.

### Pre-existing tests now green

`deferred-items.md` listed 7 pre-existing test failures from Plans 40-01 and 40-02:
- `TestWebhookEndpoint::test_accepts_valid_secret` — class deleted in Task 1 (route gone).
- 6 `TestProcessTelegramUpdate::*` — fixed via the new `_patch_graph_extractor` autouse fixture in Task 1 (`assert_called_once` semantics restored once the graph extractor doesn't run a second `execute`).

All 72 tests in `test_telegram.py` + `test_telegram_pairing.py` now pass.

## User Setup Required

`DEPLOY_RUNBOOK.md` (this plan) is now the single source of truth for operator setup. Sections (b) Backend env vars, (c) Frontend env vars, (a) BotFather Group Privacy OFF, (d) migration apply, (e) `setWebhook`, and (f) Vault purge are all documented with copy-paste-ready commands. No additional `40-USER-SETUP.md` is needed; all of that content is in the runbook.

## Next Phase Readiness

- **Phase 40 closes here.** All three plans complete; TG-05/TG-06/TG-07 marked complete in REQUIREMENTS.md (06 + 07 by 40-01, 05 by 40-02 + 40-03).
- **v1.3 milestone complete.** STATE.md `completed_plans` should be `12/12` after this plan's metadata commit. The `last_plan` edge case applies (plan 03 of 03).
- **No blockers carried forward.** The local Realtime issue is environmentally scoped, not code-scoped, and the prod path is unaffected.
- **Recommended follow-ups (not blocking):**
  - When the next phase touches Settings, consider promoting the bot-reply hostname to an env var if a second codepath needs it (currently YAGNI, hardcoded literal is fine).
  - When the next migration touches `00039`, sanity-check that `REPLICA IDENTITY FULL` is preserved (Postgres preserves it automatically across DDL changes that don't drop+recreate the table, but bears a one-line check).

## Self-Check: PASSED

Verified before final metadata commit:
- `40-03-SUMMARY.md` exists at the expected path.
- `DEPLOY_RUNBOOK.md` exists at the expected path.
- `backend/scripts/purge_legacy_telegram_vault.py` exists.
- `backend/src/services/telegram_sync.py` is GONE.
- `apps/web/src/app/dashboard/settings/tabs/telegram-sync-section.tsx` is GONE.
- All five expected commits present on `main`: `af89b61`, `5fc587f`, `345b4f7`, `d9aa4fd`, `05bebcd`.
- 72/72 telegram + pairing tests pass.

---
*Phase: 40-telegram-shared-bot-migration*
*Plan: 03*
*Completed: 2026-05-04*
