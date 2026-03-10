---
phase: 26-telegram-chat-integration
plan: 01
subsystem: api
tags: [telegram, bot-api, webhook, sqlmodel, postgresql, vault, embeddings]

requires:
  - phase: 01-foundation
    provides: workspaces table, workspace_members, RLS patterns
  - phase: 03-slack-meeting
    provides: SlackMessage model pattern, embedding service
  - phase: 07-github
    provides: Provider enum, CHECK constraint patterns

provides:
  - telegram_messages table with BIGINT chat_id/message_id, RLS, indexes
  - TelegramMessage SQLModel for message storage
  - Provider.TELEGRAM enum value
  - telegram_bot service (connect/disconnect via Vault + Telegram API)
  - telegram_events service (webhook update filtering and upsert)
  - telegram_message embedding support in SOURCE_TYPE_MAP

affects: [26-telegram-chat-integration, embedding-search]

tech-stack:
  added: [httpx (existing, used for Telegram Bot API)]
  patterns: [Bot token validation via getMe, Vault-based token storage, ON CONFLICT upsert for message edits]

key-files:
  created:
    - supabase/migrations/00019_telegram_messages.sql
    - backend/src/models/telegram.py
    - backend/src/services/telegram_bot.py
    - backend/src/services/telegram_events.py
  modified:
    - backend/src/models/integration.py
    - backend/src/config.py
    - backend/src/services/embedding.py

key-decisions:
  - "Followed SlackMessage pattern exactly for TelegramMessage (no BaseModel, no updated_at)"
  - "Used direct WorkspaceIntegration query in disconnect instead of upsert_workspace_integration (no status parameter)"
  - "Embeddings source_type CHECK removed in 00017; telegram_message added to SOURCE_TYPE_MAP only"

patterns-established:
  - "Bot token stored in Vault with naming: oauth_telegram_{workspace_id}_bot_token"
  - "Webhook secret_token header for Telegram webhook verification"
  - "Message filtering: skip bots, non-text, and messages under 10 chars"

requirements-completed: [TG-01, TG-02, TG-03, TG-04]

duration: 3min
completed: 2026-03-10
---

# Phase 26 Plan 01: Telegram Data Layer & Core Services Summary

**telegram_messages table with BIGINT IDs, TelegramMessage model, bot token management via Vault, and webhook event processing with ON CONFLICT upsert**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-10T00:45:04Z
- **Completed:** 2026-03-10T00:48:19Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Created telegram_messages migration with RLS, indexes, and all provider CHECK constraint updates
- Added TelegramMessage SQLModel following SlackMessage pattern with BIGINT columns for Telegram IDs
- Built telegram_bot service: validate token via getMe, store in Vault, register/unregister webhooks
- Built telegram_events service: filter non-text/bot/short messages, upsert with ON CONFLICT for edits
- Added telegram_message to embedding SOURCE_TYPE_MAP for vector search support

## Task Commits

Each task was committed atomically:

1. **Task 1: Database migration and TelegramMessage model** - `848f3f1` (feat)
2. **Task 2: Config, bot service, and webhook event processing** - `bffc4e4` (feat)

## Files Created/Modified

- `supabase/migrations/00019_telegram_messages.sql` - telegram_messages table, CHECK constraint updates, RLS, indexes
- `backend/src/models/telegram.py` - TelegramMessage SQLModel with UniqueConstraint for upsert
- `backend/src/models/integration.py` - Added Provider.TELEGRAM enum value
- `backend/src/config.py` - Added TELEGRAM_WEBHOOK_SECRET setting
- `backend/src/services/telegram_bot.py` - Bot token management: validate, connect, disconnect
- `backend/src/services/telegram_events.py` - Webhook update processing with message filtering
- `backend/src/services/embedding.py` - Added telegram_message to SOURCE_TYPE_MAP

## Decisions Made

- Followed SlackMessage pattern exactly for TelegramMessage (no BaseModel inheritance, no updated_at column)
- Used direct WorkspaceIntegration query in disconnect_telegram_bot instead of upsert_workspace_integration (which lacks a status parameter)
- Embeddings source_type CHECK constraint was already removed in migration 00017; only added telegram_message to Python SOURCE_TYPE_MAP

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed disconnect_telegram_bot calling upsert_workspace_integration with invalid status parameter**
- **Found during:** Task 2 (telegram_bot.py review)
- **Issue:** upsert_workspace_integration does not accept a `status` keyword argument; it always sets status to "connected"
- **Fix:** Replaced with direct WorkspaceIntegration query and status update, matching disconnect_provider pattern in oauth_common.py
- **Files modified:** backend/src/services/telegram_bot.py
- **Verification:** Import check passed successfully
- **Committed in:** bffc4e4 (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added telegram_message to embedding SOURCE_TYPE_MAP**
- **Found during:** Task 2 (telegram_events.py review)
- **Issue:** telegram_events.py calls embedding.queue_embedding_generation with source_type="telegram_message", but SOURCE_TYPE_MAP had no entry for it -- embeddings would silently fail
- **Fix:** Added TelegramMessage import and "telegram_message" entry to SOURCE_TYPE_MAP in embedding.py
- **Files modified:** backend/src/services/embedding.py
- **Verification:** Import check passed successfully
- **Committed in:** bffc4e4 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- Some files (telegram_bot.py, telegram_events.py, config.py) were already created by a prior Plan 02 execution commit (4e3befe). Task commits captured only the delta changes.

## User Setup Required

**External services require manual configuration:**
- Create a Telegram bot via @BotFather
- Disable Group Privacy in BotFather settings
- Generate TELEGRAM_WEBHOOK_SECRET (e.g., `openssl rand -hex 32`) and add to .env

## Next Phase Readiness

- Data layer complete: telegram_messages table, model, and embedding support ready
- Core services ready: Plan 02 router can call connect_telegram_bot and process_telegram_update
- All provider CHECK constraints updated for 'telegram'

---
*Phase: 26-telegram-chat-integration*
*Completed: 2026-03-10*

## Self-Check: PASSED

All 7 files verified present. Both task commits (848f3f1, bffc4e4) verified in git log.
