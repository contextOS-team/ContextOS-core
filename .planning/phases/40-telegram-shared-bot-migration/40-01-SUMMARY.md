---
phase: 40-telegram-shared-bot-migration
plan: 01
subsystem: api

tags: [telegram, fastapi, sqlalchemy, sqlmodel, supabase, postgres, rls, deep-link, webhook, base64url, secrets, pytest]

# Dependency graph
requires:
  - phase: 26-telegram-chat-integration
    provides: telegram_messages table + filter/upsert/graph pipeline + telegram_api_call helper + secret-token verification pattern
  - phase: 32-activity-events
    provides: emit_activity('integration_connected'/'integration_disconnected') primitive
provides:
  - "telegram_chat_workspace table (PK chat_id BIGINT, sticky first-claim-wins via ON CONFLICT DO NOTHING)"
  - "telegram_pairing_codes table (PK code TEXT, single-use, ~15min TTL, lazy delete)"
  - "telegram_pairing.py service: generate_pairing_code, claim_chat, handle_my_chat_member, resolve_workspace_for_chat"
  - "POST /api/telegram/pairing-code (authenticated) -> {code, deep_link, expires_at}"
  - "POST /api/telegram/webhook (no path param) global dispatcher; claim_chat runs BEFORE process_telegram_update"
  - "TELEGRAM_BOT_TOKEN_GLOBAL + TELEGRAM_BOT_USERNAME settings"
  - "Migration 00039 purges legacy oauth_tokens + workspace_integrations rows for provider='telegram'"
affects: [40-02-frontend-pairing-ui, 40-03-cutover-cleanup]

# Tech tracking
tech-stack:
  added: []  # zero new packages -- everything was already in pyproject.toml
  patterns:
    - "Atomic single-use token redemption via DELETE...RETURNING (no TOCTOU window)"
    - "Sticky chat ownership via PRIMARY KEY conflict (INSERT...ON CONFLICT DO NOTHING)"
    - "Check-before-redeem ordering: peek code -> compare to chat mapping -> only burn on fresh claim"
    - "Workspace resolution by chat_id lookup (not URL path-param) for shared-bot model"
    - "Pairing claim path runs BEFORE message ingestion in the dispatcher (Pitfall 2 mitigation)"

key-files:
  created:
    - "supabase/migrations/00039_telegram_shared_bot.sql"
    - "backend/src/services/telegram_pairing.py"
    - "backend/tests/test_telegram_pairing.py"
    - ".planning/phases/40-telegram-shared-bot-migration/deferred-items.md"
  modified:
    - "backend/src/models/telegram.py"   # added TelegramChatWorkspace + TelegramPairingCode (TelegramMessage unchanged)
    - "backend/src/config.py"            # added TELEGRAM_BOT_TOKEN_GLOBAL + TELEGRAM_BOT_USERNAME
    - "backend/src/routers/telegram.py"  # added /pairing-code + global /webhook + _dispatch_global_update
    - "backend/tests/test_telegram.py"   # added 27 Phase-40 tests (model, migration, endpoints, dispatcher)

key-decisions:
  - "[40-01] Pairing-code redemption uses peek-then-burn: SELECT for ownership, then DELETE...RETURNING only on fresh claim (so cross-workspace and same-workspace re-claim NEVER burn the code, matching CONTEXT idempotency rule)"
  - "[40-01] secrets.token_urlsafe(12) -> exact 16-char base64url alphabet (~96 bits entropy); plaintext storage with TTL+single-use is the security boundary, not at-rest encryption"
  - "[40-01] _send_reply_safe swallows TelegramError so a muted/banned bot never rolls back a successful claim (Pitfall 6); Realtime UI flip is the user-visible ack"
  - "[40-01] Dispatcher branch order load-bearing: my_chat_member first, then private-chat drop, then /start in group/supergroup -> claim_chat, only THEN resolve_workspace -> process_telegram_update (prevents pairing commands from being ingested as content -- Pitfall 2)"
  - "[40-01] handle_my_chat_member resolves workspace BEFORE soft-deleting so the integration_disconnected activity event has the correct workspace_id"
  - "[40-01] Bot reply text inlines a hardcoded https://contextos.app/dashboard/settings link (no settings-derived frontend URL field exists yet); Plan 02 may parameterize"
  - "[40-01] Legacy /webhook/{workspace_id}, /connect, /disconnect, /sync routes left intact in this plan to keep it independently mergeable; Plan 03 deletes them"
  - "[40-01] Migration 00039 uses CREATE TABLE IF NOT EXISTS + DROP POLICY IF EXISTS for idempotency; the legacy oauth_tokens + workspace_integrations purge runs at the bottom (Vault key cleanup is a Plan 03 deploy script)"

patterns-established:
  - "Pairing-code lifecycle: DELETE unexpired-for-workspace BEFORE INSERT (one-active-code-per-workspace invariant)"
  - "Sticky chat->workspace mapping table: chat_id BIGINT PRIMARY KEY + workspace_member_select RLS (writes via service role only)"
  - "Global webhook dispatcher pattern: branch on update shape, resolve tenant by chat_id, fail-silent rollback on internal exception"

requirements-completed:
  - TG-06   # tables, single-use 15min TTL, sticky mapping, my_chat_member soft-delete
  - TG-07   # global /api/telegram/webhook, dispatcher with claim BEFORE ingestion, chat_id lookup
  # TG-05 is partial -- backend pairing-code endpoint shipped; frontend wiring lands in Plan 02

# Metrics
duration: 12min
completed: 2026-05-03
---

# Phase 40 Plan 01: Telegram Shared-Bot Backend Summary

**Single global webhook routing by chat_id + atomic peek-then-burn pairing codes (16-char base64url, 15-min TTL) replacing the Phase-26 per-workspace BotFather flow**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-03T14:31:46Z
- **Completed:** 2026-05-03T14:43:48Z
- **Tasks:** 3 (all autonomous, no checkpoints)
- **Files created:** 4 (migration, service, test file, deferred-items)
- **Files modified:** 4 (model, config, router, test_telegram)
- **Tests added:** 49 (all green)

## Accomplishments

- **Migration 00039** creates `telegram_chat_workspace` (PK `chat_id` BIGINT) and `telegram_pairing_codes` (PK `code` TEXT, `expires_at` NOT NULL) with workspace-scoped RLS; legacy Phase-26 `oauth_tokens`/`workspace_integrations` rows purged at the bottom.
- **`telegram_pairing.py`** service implements the full claim lifecycle: mint via `secrets.token_urlsafe(12)`, peek-then-burn redemption (`DELETE…RETURNING` only on fresh claim), sticky upsert (`pg_insert(...).on_conflict_do_nothing(index_elements=["chat_id"])`), idempotent same-workspace NOOP (no burn), cross-workspace rejection (no burn), `my_chat_member` soft-delete on `left`/`kicked` with activity emission.
- **Global webhook dispatcher** in `routers/telegram.py`: hmac-verified secret-token check, BackgroundTasks 200-fast, per-update DB session, branch order = `my_chat_member` → private-drop → `/start`-in-group → `claim_chat` → resolve-workspace → `process_telegram_update`. Pairing commands NEVER reach the ingestion path (Pitfall 2 mitigation tested explicitly).
- **`POST /api/telegram/pairing-code`** authenticated endpoint returns `{code, deep_link, expires_at(ISO 8601)}`; deletes any unexpired prior codes for the workspace before insert (Pitfall 5).
- **49 new tests** across `test_telegram.py` (model shape, migration DDL, pairing-code endpoint, global webhook 200/403, dispatcher routing) and `test_telegram_pairing.py` (full claim_chat branch matrix, race-loss path, tokenization variants, reply-failure isolation, my_chat_member soft-delete + log-only paths).

## Task Commits

Each task was committed atomically (TDD pairs visible where applicable):

1. **Task 1: Migration 00039 + SQLModel classes** — `546b1b4` (feat)
   - Single combined commit (TDD test additions in same file as code; assertions are static so RED → GREEN was atomic).
2. **Task 2: telegram_pairing.py service** — `38d2827` (test, RED) + `3fb8921` (feat, GREEN)
3. **Task 3: Global webhook + /pairing-code endpoint** — `a3b9d1d` (test, RED) + `c7f655c` (feat, GREEN)

## Files Created/Modified

### Created
- `supabase/migrations/00039_telegram_shared_bot.sql` — Two tables, RLS, legacy oauth_tokens/workspace_integrations purge.
- `backend/src/services/telegram_pairing.py` — Full pairing service (~310 lines).
- `backend/tests/test_telegram_pairing.py` — 22 unit tests covering pairing service.
- `.planning/phases/40-telegram-shared-bot-migration/deferred-items.md` — Tracks 7 pre-existing test failures (out-of-scope, will be cleaned up by Plan 03).

### Modified
- `backend/src/models/telegram.py` — Added `TelegramChatWorkspace` + `TelegramPairingCode` SQLModel classes; `TelegramMessage` UNCHANGED. Module docstring updated.
- `backend/src/config.py` — Added `TELEGRAM_BOT_TOKEN_GLOBAL` and `TELEGRAM_BOT_USERNAME` settings (kept distinct from existing `TELEGRAM_BOT_TOKEN` for Sentry alerts).
- `backend/src/routers/telegram.py` — Added `POST /pairing-code`, `POST /webhook` (no path param), `_dispatch_global_update()` background dispatcher; legacy routes preserved for Plan 03 cleanup.
- `backend/tests/test_telegram.py` — Added 27 Phase-40 tests (model, migration DDL, endpoint, dispatcher).

## Decisions Made

All key decisions captured in the frontmatter above. Notable ones:

1. **Peek-then-burn redemption** — Implemented `claim_chat` to SELECT the code's owner first, compare to the chat's existing mapping, and only run `DELETE…RETURNING` if the chat is unmapped or owned by the same workspace. This satisfies the CONTEXT requirement that cross-workspace and same-workspace re-claim must NOT burn the code, while still keeping the actual redemption atomic for the fresh-claim path.
2. **Reply failure isolation** — `_send_reply_safe` catches `TelegramError` and `Exception` separately, both swallowed (Pitfall 6). Realtime UI flip via the inserted mapping row is the user-visible ack; the in-chat reply is courtesy.
3. **Bot reply wording** — Three variants (CLAIMED / INVALID_CODE / ALREADY_CLAIMED_BY_OTHER) with `https://contextos.app/dashboard/settings` link. NOOP and IGNORE_PRIVATE produce no reply (silent, matches CONTEXT decision to drop private-chat updates without responding).
4. **Legacy routes preserved** — `/webhook/{workspace_id}`, `/connect`, `/disconnect`, `/sync`, `/sync/status` left intact in this plan; deletion is Plan 03's job per the plan boundary. This keeps Plan 01 independently mergeable.
5. **Migration purges Phase-26 OAuth rows** — `DELETE FROM public.oauth_tokens WHERE provider = 'telegram'` runs at the bottom of `00039`. Vault key cleanup (`telegram_<workspace_id>_bot_token`) is deferred to a Plan 03 deploy script (Vault is not a regular table).
6. **`ClaimResult(str, Enum)`** — Matches existing `Environment(str, Enum)` precedent in `config.py`. Ruff flags `UP042` (suggests `StrEnum`) but switching changes behavior subtly; consistent with project precedent.

## Deviations from Plan

**None — plan executed as written.**

The PLAN.md sketch had an early `claim_chat` outline using DELETE…RETURNING first then a same-workspace re-burn discussion; the PLAN already directed me to the "FINAL STRUCTURE: check chat mapping first" version, which is what I implemented. No actual deviation, just following the plan's "use this final shape" guidance.

## Issues Encountered

### Pre-existing test failures (out of scope)

7 tests in `test_telegram.py` were already failing before this plan started, all in legacy Phase-26 paths:

- `TestWebhookEndpoint::test_accepts_valid_secret` — Asserts `{"status": "ok"}` but legacy webhook returns `{"ok": True}`.
- `TestProcessTelegramUpdate::test_*` (6 tests) — Assert `mock_session.execute.assert_called_once()` but `process_telegram_update` now calls `extract_and_populate_graph` (added later) which also runs `execute`.

Verified pre-existing via `git stash` of all Phase-40 changes — the same failures reproduce on the unmodified codebase. Documented in `.planning/phases/40-telegram-shared-bot-migration/deferred-items.md`. Plan 03 (cutover/cleanup) deletes the legacy routes these tests cover, so they will be removed/rewritten there. Per the SCOPE BOUNDARY rule, not fixed here.

### Mypy/ruff caveats (non-blocking, pre-existing patterns)

- Mypy reports SQLModel descriptor-typing errors (`No overload variant of "select" matches argument type "UUID"`, `Argument 1 to "where" of "DMLWhereBase" has incompatible type "bool"`) on the new service file. These are identical-pattern false-positives that already exist in `telegram_events.py` due to SQLModel's `Field(...)` not being recognized as `InstrumentedAttribute` by mypy. Tests prove correct runtime behavior.
- Ruff `UP042` warns on `class ClaimResult(str, Enum)`. Existing `class Environment(str, Enum)` in `config.py` uses the same pattern; switching to `StrEnum` would change runtime behavior. Left as-is to match project precedent.
- Two pre-existing `E501` line-length errors in legacy `_process_update_background` are unchanged.

## User Setup Required

None for this plan — backend-only.

The shared bot itself (BotFather setup, **Group Privacy OFF**, `setWebhook` registration with `allowed_updates=["message", "edited_message", "my_chat_member"]`) is a deploy/runbook step landed in Plan 03's deploy checklist. Plan 02 (frontend) will surface the env-var requirement in its docs.

## Next Phase Readiness

- **Plan 02 (frontend pairing UI)** can consume `POST /api/telegram/pairing-code` directly. Realtime subscription target is `telegram_chat_workspace` filtered by `workspace_id` (RLS allows the user's JWT to SELECT their own rows -- verified policy shape in migration).
- **Plan 03 (cutover/cleanup)** will delete the legacy `/connect`, `/disconnect`, `/sync`, `/sync/status`, `/webhook/{workspace_id}` routes and the `connect_telegram_bot`/`disconnect_telegram_bot` service helpers. The pre-existing test failures noted above will go away with that deletion.

## Self-Check: PASSED

Verified during execution:
- `supabase/migrations/00039_telegram_shared_bot.sql` exists and contains both tables, BIGINT PK, RLS enable + workspace_member_select policies, oauth_tokens cleanup.
- `backend/src/services/telegram_pairing.py` exists with `ClaimResult` enum + `generate_pairing_code`, `claim_chat`, `handle_my_chat_member`, `resolve_workspace_for_chat` exports.
- Commits `546b1b4`, `38d2827`, `3fb8921`, `a3b9d1d`, `c7f655c` all present on `main` (verified via `git log --oneline`).
- 49 new Phase-40 tests pass (`pytest tests/test_telegram_pairing.py tests/test_telegram.py::Test{Pairing,Global,TelegramChat,TelegramPairingCode,Phase40}*`).

---
*Phase: 40-telegram-shared-bot-migration*
*Plan: 01*
*Completed: 2026-05-03*
