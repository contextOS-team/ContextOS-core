---
phase: 40-telegram-shared-bot-migration
verified: 2026-05-03T00:00:00Z
status: human_needed
score: 11/12 must-haves verified
re_verification: false
human_verification:
  - test: "Realtime UI flip to 'connected' without page reload (fresh claim, re-claim after kick)"
    expected: "After bot joins a Telegram group, the Settings and Onboarding pairing block flips from 'waiting' to 'Connected — refreshing…' within ~1s. After kick + re-pair, the same flip occurs via the re-pair UPDATE event."
    why_human: "Local Realtime was blocked by two env-independent issues (stale anon JWT signature + Kong HTTP 431 on WebSocket upgrade). The code path is wired correctly at the source level (publication membership, REPLICA IDENTITY FULL, event:'*' subscription, payload filter, mintedRef guard all verified), but the specific end-to-end UI-flip was not confirmed locally. Production Supabase Cloud is unaffected by these local issues, but the check is not yet green in a working environment."
---

# Phase 40: Telegram Shared-Bot Migration — Verification Report

**Phase Goal:** TG-05 (one-click shared-bot deep-link connect), TG-06 (sticky chat→workspace mapping via single-use 15-min pairing code), TG-07 (single global webhook routing by chat_id with claim-before-ingest dispatcher)
**Verified:** 2026-05-03
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | POST /api/telegram/pairing-code returns {code, deep_link, expires_at} with 16-char base64url code, 15-min TTL | VERIFIED | `routers/telegram.py:47-86`; `telegram_pairing.py:69-111`; `secrets.token_urlsafe(12)` confirmed |
| 2  | Generating a fresh code deletes any unexpired prior codes (one-active-code-per-workspace) | VERIFIED | `telegram_pairing.py:83-87` DELETE WHERE expires_at > now() before INSERT |
| 3  | Global webhook validates X-Telegram-Bot-Api-Secret-Token via hmac.compare_digest before accepting any update | VERIFIED | `routers/telegram.py:114-120`; 403 on mismatch |
| 4  | /start@bot claim path runs BEFORE process_telegram_update in the dispatcher | VERIFIED | `routers/telegram.py:156-158`; startswith('/start') branch at line 156 precedes resolve_workspace_for_chat/process_telegram_update at 161-166 |
| 5  | Fresh claim: code is atomically burned (DELETE…RETURNING) and row inserted into telegram_chat_workspace; ON CONFLICT DO UPDATE clears removed_at for re-pair after kick | VERIFIED | `telegram_pairing.py:225-271`; ON CONFLICT DO UPDATE WHERE removed_at IS NOT NULL confirmed |
| 6  | Cross-workspace claim rejected without burning code; same-workspace re-claim is idempotent NOOP without burning code | VERIFIED | `telegram_pairing.py:205-222`; peek-before-redeem logic; NOOP returns before redeem_stmt |
| 7  | my_chat_member left/kicked soft-deletes mapping (removed_at = now()) and emits integration_disconnected | VERIFIED | `telegram_pairing.py:317-365`; resolve_workspace_for_chat before soft-delete so activity event has correct workspace_id |
| 8  | Settings → Integrations Telegram card uses TelegramPairingProgress (no bot-token form) | VERIFIED | `telegram-connect.tsx` body is entirely TelegramPairingProgress wrapper; `integration-cards.tsx:278` passes connectForm={<TelegramConnect />} |
| 9  | Onboarding step-sources renders TelegramPairingProgress inline; bot-token form deleted | VERIFIED | `step-sources.tsx:36,290-302`; TelegramPairingProgress imported and wired to expandedSource === 'telegram'; no legacy token state |
| 10 | All Phase-26 symbols removed: connect_telegram_bot, disconnect_telegram_bot, drain_pending_updates, TELEGRAM_API_ID, TELEGRAM_API_HASH, telethon, TelegramSyncSection, connectTelegram(), syncTelegramHistory(), getTelegramSyncStatus(), disconnectTelegram(), telegram_sync.py, telegram-sync-section.tsx | VERIFIED | grep sweep returned zero functional-code hits; only docstring/comment references mentioning the deletion remain; both files confirmed DELETED on disk |
| 11 | Realtime subscription wired correctly: event:'*', workspace_id=eq.${workspaceId} filter, removed_at IS NULL payload guard, removeChannel cleanup, REPLICA IDENTITY FULL in migration, publication membership | VERIFIED (code-level) | `telegram-pairing-progress.tsx:138-165`; migration line 88 (REPLICA IDENTITY FULL), line 92 (publication ADD TABLE); mintedRef StrictMode guard at lines 69,97-99 |
| 12 | Realtime UI flip confirmed in a working Realtime environment (production or correctly-configured local) | HUMAN NEEDED | Not runtime-verified locally due to stale anon JWT + Kong HTTP 431 on WebSocket. Code path verified correct. Production Supabase Cloud unaffected per SUMMARY. |

**Score:** 11/12 truths verified (1 needs human confirmation in a working Realtime environment)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/00039_telegram_shared_bot.sql` | telegram_chat_workspace + telegram_pairing_codes tables, BIGINT PK, RLS, REPLICA IDENTITY FULL, publication, Phase-26 cleanup | VERIFIED | All elements confirmed: chat_id BIGINT PRIMARY KEY, code TEXT PRIMARY KEY, RLS enabled + workspace_member_select policies, REPLICA IDENTITY FULL, ADD TABLE to supabase_realtime, DELETE FROM oauth_tokens/workspace_integrations |
| `backend/src/models/telegram.py` | TelegramChatWorkspace + TelegramPairingCode classes alongside unchanged TelegramMessage | VERIFIED | All three classes present at lines 17, 57, 85 |
| `backend/src/services/telegram_pairing.py` | generate_pairing_code, claim_chat, handle_my_chat_member, ClaimResult, resolve_workspace_for_chat | VERIFIED | All exports present; ~426 lines, substantive implementation with full claim lifecycle |
| `backend/src/routers/telegram.py` | Only /webhook (global) and /pairing-code remain; dispatcher with claim-before-ingest | VERIFIED | 175 lines; exactly two endpoints; no legacy routes; dispatch order confirmed |
| `backend/src/services/telegram_bot.py` | Only TelegramError + telegram_api_call (~50 lines) | VERIFIED | 52 lines; only two exports; docstring notes Phase-26 helpers removed |
| `apps/web/src/app/dashboard/integrations/telegram-pairing-progress.tsx` | 5-phase state machine with auto-mint, countdown, Realtime, StrictMode guard | VERIFIED | 272 lines; all 6 phases present (idle/minting/waiting/expired/connected/already_connected); mintedRef guard; event:'*' subscription; removeChannel cleanup |
| `apps/web/src/lib/api.ts` | createTelegramPairingCode() exported; TelegramAlreadyConnectedError; legacy helpers deleted | VERIFIED | createTelegramPairingCode at line 492; TelegramAlreadyConnectedError class at line 483; connectTelegram/disconnectTelegram/syncTelegramHistory/getTelegramSyncStatus absent |
| `apps/web/src/app/dashboard/settings/tabs/telegram-connect.tsx` | Thin wrapper rendering TelegramPairingProgress, no bot-token form | VERIFIED | 77 lines; entirely workspace_id resolver + TelegramPairingProgress render |
| `apps/web/src/components/onboarding/step-sources.tsx` | TelegramPairingProgress inline block; expandedSource 'telegram' gated | VERIFIED | Import at line 36; expandedSource type includes 'telegram'; inline block at lines 290-302 |
| `backend/scripts/purge_legacy_telegram_vault.py` | One-shot async script with --dry-run, strict regex, per-row exception isolation | VERIFIED | NAME_PATTERN regex confirmed; --dry-run flag; per-row try/except |
| `.planning/phases/40-telegram-shared-bot-migration/DEPLOY_RUNBOOK.md` | BotFather setup, env vars, setWebhook with my_chat_member, Vault purge | VERIFIED | Group Privacy OFF at line 20; setWebhook at line 116; allowed_updates with my_chat_member at line 119 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `routers/telegram.py:webhook` | `telegram_pairing.py:claim_chat` | text.startswith('/start') check at line 156 BEFORE resolve_workspace_for_chat | VERIFIED | Line 156-158 precedes lines 161-166 in dispatcher |
| `routers/telegram.py:webhook` | `telegram_events.py:process_telegram_update` | resolve_workspace_for_chat(chat_id) at line 161 | VERIFIED | Not a path param; chat_id lookup only |
| `telegram_pairing.py:claim_chat` | telegram_pairing_codes table | DELETE…RETURNING at lines 225-233 | VERIFIED | Atomic single-use redemption confirmed |
| `telegram_pairing.py:claim_chat` | telegram_chat_workspace table | ON CONFLICT DO UPDATE WHERE removed_at IS NOT NULL at lines 247-269 | VERIFIED | Re-pair semantics confirmed; RETURNING distinguishes success from conflict |
| `POST /api/telegram/pairing-code` | telegram_pairing_codes table | DELETE unexpired THEN INSERT in generate_pairing_code | VERIFIED | Lines 83-100 in telegram_pairing.py |
| `TelegramPairingProgress` | `POST /api/telegram/pairing-code` | createTelegramPairingCode() in api.ts | VERIFIED | Import at telegram-pairing-progress.tsx:37; called in startPairing() |
| `TelegramPairingProgress` | Supabase Realtime on telegram_chat_workspace | useEffect subscribes with filter workspace_id=eq.${workspaceId}; removeChannel on cleanup | VERIFIED | Lines 126-166 in telegram-pairing-progress.tsx; REPLICA IDENTITY FULL + publication in migration |
| `TelegramConnect` | `TelegramPairingProgress` | Renders <TelegramPairingProgress /> in place of bot-token form | VERIFIED | telegram-connect.tsx:70-74 |
| `step-sources.tsx Telegram slot` | `TelegramPairingProgress` | expandedSource === 'telegram' renders inline TelegramPairingProgress | VERIFIED | Lines 290-302 in step-sources.tsx |
| `DEPLOY_RUNBOOK.md` | setWebhook with my_chat_member in allowed_updates | Documented curl command at line 116-119 | VERIFIED | Confirmed my_chat_member in allowed_updates string |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TG-05 | Plans 01, 02, 03 | One-click shared-bot deep-link connect from Settings and Onboarding | SATISFIED | createTelegramPairingCode endpoint, TelegramPairingProgress component, TelegramConnect wrapper, step-sources wiring — all confirmed at code level; live runtime test confirmed Settings pair, bot reply, and page-reload connected state |
| TG-06 | Plan 01 | Sticky chat→workspace mapping, single-use 15-min code, first-claim-wins, soft-delete on kick | SATISFIED | telegram_chat_workspace table with BIGINT PK, ON CONFLICT DO UPDATE for re-pair, handle_my_chat_member soft-delete, runtime verified against real group chat_id -1003644773967 |
| TG-07 | Plan 01 | Single global /api/telegram/webhook routing by chat_id, claim-before-ingest | SATISFIED | Single /webhook endpoint (no path param), dispatcher branch order verified at code and runtime level; /start claim path confirmed before process_telegram_update |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | No stubs, placeholder returns, TODO blockers, or unimplemented handlers found across all modified files |

### Human Verification Required

#### 1. Realtime UI Flip (Fresh Claim and Re-pair After Kick)

**Test:** In a working Realtime environment (production Supabase Cloud or a local stack with corrected anon JWT and Kong header buffer):
1. Navigate to Settings → Integrations → Telegram → click Connect.
2. Wait for the deep-link to open in a new tab; choose a test group.
3. The bot should join the group and post the confirmation reply.
4. Verify the Settings pairing block flips to "Connected — refreshing…" within ~1s WITHOUT a page reload.
5. Then kick the bot from the group and re-generate a pairing code.
6. Re-invite the bot to the same group via the new deep-link.
7. Verify the pairing block flips to connected again (re-pair UPDATE event, not INSERT).

**Expected:**
- Steps 1-4: UI flips to connected via INSERT Realtime event.
- Steps 5-7: UI flips to connected via UPDATE Realtime event (re-pair via ON CONFLICT DO UPDATE).
- No page reload required in either case.
- Browser DevTools Network: Realtime WebSocket channel `telegram-pairing-<workspace_id>` connected.
- Browser DevTools Console: no duplicate-channel StrictMode warnings.

**Why human:** Local Supabase Realtime was blocked by two unrelated environment issues documented in 40-03-SUMMARY.md — stale anon JWT signature mismatch with the local Realtime container, and Kong API gateway returning HTTP 431 on WebSocket upgrade due to a 1 KB default header buffer. Both issues are local-environment only; production Supabase Cloud uses different Kong configuration and the prod anon key matches its JWT secret. The code path is correctly wired at every level verified via static analysis: publication membership, REPLICA IDENTITY FULL, event:'*' subscription with removed_at IS NULL filter, mintedRef StrictMode guard — but the specific browser-visible flip was not confirmed in a live session.

### Gaps Summary

No blocking gaps were found. All 11/12 must-haves are satisfied at code level with strong evidence. The one outstanding item (Realtime UI flip at runtime) could not be confirmed locally due to environment issues unrelated to Phase 40 code, but the wiring is correct and the claim/re-pair paths were confirmed end-to-end in production (bot reply, DB state, page-reload-driven connected state).

The human verification item is a confidence check on the already-wired Realtime path, not a code gap.

---

_Verified: 2026-05-03_
_Verifier: Claude (gsd-verifier)_
