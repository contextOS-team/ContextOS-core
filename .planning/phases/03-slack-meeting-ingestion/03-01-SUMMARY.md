---
phase: 03-slack-meeting-ingestion
plan: 01
subsystem: api
tags: [slack, oauth2, events-api, hmac, httpx, vault, websocket-alternative]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "BaseModel, TimestampMixin, Settings, get_current_user dependency, async session"
  - phase: 02-linear-integration
    provides: "Vault service, OAuthToken/WorkspaceIntegration models, HMAC signing pattern, background task delegation pattern"
provides:
  - "Slack OAuth V2 connect/callback/disconnect/status endpoints"
  - "Slack Events API endpoint with HMAC-SHA256 signature verification"
  - "SlackMessage SQLModel mapping to public.slack_messages"
  - "Message filtering (bot, <10 chars, system messages)"
  - "Thread reply tracking with parent_ts relationship"
  - "Message edit overwrite and soft-delete support"
  - "Vault-encrypted bot token storage (same pattern as Linear)"
affects: [03-02-PLAN, 03-03-PLAN, 04-context-synthesis, 05-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [slack-oauth-v2, slack-events-api, slack-hmac-signature, message-filtering-pipeline, upsert-on-conflict]

key-files:
  created:
    - backend/src/models/slack.py
    - backend/src/services/slack_oauth.py
    - backend/src/services/slack_events.py
    - backend/src/routers/slack.py
    - backend/tests/test_slack.py
  modified:
    - backend/src/config.py
    - backend/src/main.py
    - backend/src/models/__init__.py
    - .env.example

key-decisions:
  - "Slack bot tokens do not expire and have no refresh tokens -- simpler than Linear OAuth"
  - "Module-level config import (import src.config) for slack router to match webhook pattern for reliable test patching"
  - "Background task delegation for event processing to ensure fast 200 response to Slack"
  - "Events endpoint creates its own session via async_session() for background processing isolation"
  - "Channel monitoring defaults to all channels if no selected_channels configured in integration config"
  - "Aliased sqlalchemy.text as sa_text to avoid SQLModel/Field namespace collision in model definition"

patterns-established:
  - "Slack OAuth V2 pattern: build_auth_url, exchange_code, disconnect, get_bot_token (no refresh needed)"
  - "Slack signature verification: v0={hmac(signing_secret, v0:timestamp:body)} with 5-minute replay protection"
  - "Message filtering pipeline: bot check -> system subtype check -> length check"
  - "PostgreSQL upsert via pg_insert().on_conflict_do_update() for idempotent message ingestion"

requirements-completed: [SLCK-01, SLCK-02, SLCK-04, SLCK-05, SLCK-06]

# Metrics
duration: 6min
completed: 2026-02-24
---

# Phase 03 Plan 01: Slack OAuth and Events API Summary

**Slack OAuth V2 with Vault-encrypted bot tokens, Events API with HMAC-SHA256 verification, and real-time message ingestion with filtering, threading, and edit/delete support**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-24T21:03:43Z
- **Completed:** 2026-02-24T21:09:45Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Slack OAuth V2 connect/callback/disconnect/status endpoints with Vault-encrypted bot token storage
- Events API endpoint with HMAC-SHA256 signature verification and 5-minute replay protection
- Message filtering pipeline: bot messages, short messages (<10 chars), and system messages filtered out
- Thread reply tracking with parent_ts relationship intact
- Message edit overwrites stored text; message delete soft-deletes the record
- URL verification challenge handler for Slack app event subscription setup
- 26 comprehensive tests covering OAuth, events, filtering, threading, edit, delete, and channel monitoring

## Task Commits

Each task was committed atomically:

1. **Task 1: Slack config, SlackMessage model, and OAuth service** - `a007fc1` (feat)
2. **Task 2: Slack router, Events API endpoint, message processor, and tests** - `7b2e51a` (feat)

## Files Created/Modified
- `backend/src/models/slack.py` - SlackMessage SQLModel mapping to public.slack_messages with UniqueConstraint
- `backend/src/services/slack_oauth.py` - Slack OAuth V2 lifecycle (build_auth_url, exchange_code, disconnect, get_bot_token)
- `backend/src/services/slack_events.py` - Events API message processor with filtering, threading, edit/delete
- `backend/src/routers/slack.py` - HTTP endpoints for OAuth + Events API (5 routes)
- `backend/tests/test_slack.py` - 26 tests for OAuth, events, filtering, processing
- `backend/src/config.py` - Added SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_SIGNING_SECRET, SLACK_REDIRECT_URI, slack_redirect_uri property
- `backend/src/main.py` - Registered slack router
- `backend/src/models/__init__.py` - Re-exported SlackMessage
- `.env.example` - Added SLACK_REDIRECT_URI documentation

## Decisions Made
- Slack bot tokens do not expire and have no refresh tokens, making the OAuth flow simpler than Linear (no advisory lock refresh needed)
- Used `import src.config as config_module` pattern in slack router for reliable test settings patching (learned from 02-03 decision)
- Background task delegation for event processing ensures fast 200 response to Slack to avoid retries
- Channel monitoring defaults to all channels when no `selected_channels` is configured in integration config JSONB
- Aliased `sqlalchemy.text` as `sa_text` in slack model to avoid FieldInfo collision when `text` is used as a field name in SQLModel

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SQLAlchemy text() collision with SQLModel Field**
- **Found during:** Task 1
- **Issue:** `from sqlalchemy import text` collided with SQLModel's internal processing of `Field()` when `sa_column=Column(JSONB, ..., server_default=text(...))` was used, causing `TypeError: 'FieldInfo' object is not callable`
- **Fix:** Aliased the import as `from sqlalchemy import text as sa_text` to avoid namespace collision
- **Files modified:** backend/src/models/slack.py
- **Verification:** Import succeeds, model class created correctly
- **Committed in:** a007fc1 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor import alias fix. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
Slack app registration is required before using the integration. Users need to:
- Create a Slack app at api.slack.com/apps
- Set SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_SIGNING_SECRET in .env
- Configure OAuth redirect URL and bot token scopes in Slack dashboard
- Enable Events API and subscribe to message events

This is documented in the plan's user_setup section and in .env.example.

## Next Phase Readiness
- Slack OAuth and Events API endpoints are live, ready for Phase 3 Plan 2 (channel selection and management)
- Message ingestion pipeline ready for real-time data once a Slack app is configured
- Vault pattern reused successfully from Linear OAuth -- consistent token management
- Embedding generation stubs called correctly; Phase 4 will implement actual embedding

## Self-Check: PASSED

All created files verified present:
- backend/src/models/slack.py - FOUND
- backend/src/services/slack_oauth.py - FOUND
- backend/src/services/slack_events.py - FOUND
- backend/src/routers/slack.py - FOUND
- backend/tests/test_slack.py - FOUND
- backend/src/config.py - FOUND (modified)
- backend/src/main.py - FOUND (modified)
- backend/src/models/__init__.py - FOUND (modified)
- .env.example - FOUND (modified)

All commits verified:
- a007fc1 (Task 1) - FOUND
- 7b2e51a (Task 2) - FOUND

---
*Phase: 03-slack-meeting-ingestion*
*Completed: 2026-02-24*
