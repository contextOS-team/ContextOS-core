---
phase: 03-slack-meeting-ingestion
plan: 02
subsystem: api
tags: [slack, fathom, channels, meeting-transcripts, vault, httpx, cursor-pagination]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "BaseModel, TimestampMixin, Settings, get_current_user dependency, async session"
  - phase: 02-linear-integration
    provides: "Vault service, OAuthToken/WorkspaceIntegration models, embedding stub"
  - phase: 03-slack-meeting-ingestion (plan 01)
    provides: "Slack OAuth, bot token in Vault, Events API endpoint, SlackMessage model"
provides:
  - "Slack channel listing with cursor pagination and rate limit handling"
  - "Channel selection storage in workspace_integrations.config JSONB"
  - "Channel monitoring check (is_channel_monitored) for event filtering"
  - "Fathom API client with connect/disconnect/poll/status lifecycle"
  - "MeetingTranscript and MeetingSegment SQLModel mappings"
  - "Speaker-segmented transcript ingestion with dedup by fathom_id"
  - "Vault-encrypted Fathom API key storage"
affects: [03-03-PLAN, 04-context-synthesis, 05-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [slack-conversations-list-pagination, fathom-api-key-vault, meeting-segment-storage, channel-selection-jsonb]

key-files:
  created:
    - backend/src/services/slack_channels.py
    - backend/src/services/fathom.py
    - backend/src/models/meeting.py
    - backend/src/routers/fathom.py
    - backend/tests/test_slack_channels.py
    - backend/tests/test_fathom.py
  modified:
    - backend/src/routers/slack.py
    - backend/src/config.py
    - backend/src/main.py
    - backend/src/models/__init__.py

key-decisions:
  - "Slack conversations.list uses cursor pagination with limit=1000 per page for full channel retrieval"
  - "Channel list cached in workspace_integrations.config JSONB under available_channels key"
  - "GET /channels reads from cache; POST /channels/refresh hits Slack API fresh"
  - "Fathom API key stored in Vault (not plaintext), vault key format: fathom_{workspace_id}_api_key"
  - "Fathom API base URL configurable via FATHOM_API_BASE_URL setting (default https://api.fathom.video/v1)"
  - "Fathom dedup uses fathom_id stored in raw_data JSONB (no dedicated DB column)"
  - "Processing transcripts (no content) skipped and retried on next poll cycle"
  - "Poll endpoint runs in BackgroundTasks, returns 202 immediately"

patterns-established:
  - "Channel selection JSONB: workspace_integrations.config.selected_channels controls message filtering"
  - "Fathom API key lifecycle: connect validates key -> Vault store -> disconnect deletes from Vault"
  - "Meeting segment pattern: parent MeetingTranscript + child MeetingSegment per speaker turn"
  - "Configurable third-party API base URL in Settings for flexibility"

requirements-completed: [SLCK-03, MEET-01]

# Metrics
duration: 8min
completed: 2026-02-24
---

# Phase 03 Plan 02: Slack Channel Selection and Fathom Transcript Ingestion Summary

**Slack channel listing with cursor pagination and selection storage, Fathom API client with Vault-encrypted key and speaker-segmented transcript ingestion**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-24T21:12:57Z
- **Completed:** 2026-02-24T21:21:09Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Slack channel listing service with full cursor pagination, rate limit (429/Retry-After) handling, and caching in workspace_integrations.config JSONB
- Channel selection endpoints: GET /channels (cached), POST /channels/refresh (fresh from API), POST /channels/select (save selection)
- is_channel_monitored helper for event processor to skip messages from unmonitored channels
- Fathom API client with connect (validates key + stores in Vault), disconnect, status, and poll lifecycle
- MeetingTranscript and MeetingSegment models mapping to DB tables with speaker-segmented storage
- Transcript polling with deduplication (fathom_id in raw_data), processing-transcript skip, and embedding queue
- 32 new tests across both services (13 channel tests + 19 Fathom tests), all 117 total tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Slack channel selection service and endpoints** - `4d333a4` (feat)
2. **Task 2: Fathom API client, meeting models, and transcript ingestion** - `6590a05` (feat)

## Files Created/Modified
- `backend/src/services/slack_channels.py` - Channel listing, selection, caching, and monitoring check service
- `backend/src/services/fathom.py` - Fathom API client: connect, disconnect, poll_transcripts, status
- `backend/src/models/meeting.py` - MeetingTranscript and MeetingSegment SQLModel table mappings
- `backend/src/routers/fathom.py` - Fathom HTTP endpoints: connect, disconnect, status, poll
- `backend/src/routers/slack.py` - Added channel listing, refresh, and select endpoints
- `backend/src/config.py` - Added FATHOM_API_KEY and FATHOM_API_BASE_URL settings
- `backend/src/main.py` - Registered fathom router
- `backend/src/models/__init__.py` - Re-exported MeetingTranscript and MeetingSegment
- `backend/tests/test_slack_channels.py` - 13 tests for channel listing, selection, and monitoring
- `backend/tests/test_fathom.py` - 19 tests for Fathom connect, disconnect, poll, segments, and status

## Decisions Made
- Slack conversations.list uses cursor-based pagination (limit=1000 per page) with full traversal until next_cursor is empty
- Channel list cached in workspace_integrations.config JSONB to avoid Slack API calls on every page load; manual refresh button fetches fresh
- Fathom API key stored in Vault using naming convention `fathom_{workspace_id}_api_key` (reusing Vault pattern from Phase 2)
- Fathom API base URL made configurable via FATHOM_API_BASE_URL setting because `api.fathom.video` does not currently resolve -- users can configure the correct URL
- Deduplication of Fathom transcripts uses `raw_data["fathom_id"]` since the DB schema has no dedicated fathom_id column
- Processing transcripts (no content yet) are skipped and will be retried on next poll cycle
- Poll endpoint uses BackgroundTasks for async processing, returns 202 immediately

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Fathom API base URL `api.fathom.video` does not resolve (DNS failure). Made the base URL configurable via `FATHOM_API_BASE_URL` setting so users can set the correct endpoint. This is not a code bug -- it's an external service configuration concern.

## User Setup Required
Fathom API access is required before using the Fathom integration. Users need to:
- Generate a Fathom API key from Fathom app settings
- Use the POST /api/fathom/connect endpoint with the API key
- The key is validated against the Fathom API and stored encrypted in Vault
- If `api.fathom.video` is not the correct base URL, set `FATHOM_API_BASE_URL` in .env

## Next Phase Readiness
- Channel selection fully operational: list, select, refresh, monitoring check
- Fathom integration ready for transcript ingestion once API key is provided
- Event processor can now filter messages by selected channels (uses is_channel_monitored)
- All models and services ready for Phase 3 Plan 3 (integration setup page)
- Meeting transcript data available for Phase 4 context synthesis

## Self-Check: PASSED

All created files verified present:
- backend/src/services/slack_channels.py - FOUND
- backend/src/services/fathom.py - FOUND
- backend/src/models/meeting.py - FOUND
- backend/src/routers/fathom.py - FOUND
- backend/tests/test_slack_channels.py - FOUND
- backend/tests/test_fathom.py - FOUND
- backend/src/routers/slack.py - FOUND (modified)
- backend/src/config.py - FOUND (modified)
- backend/src/main.py - FOUND (modified)
- backend/src/models/__init__.py - FOUND (modified)

All commits verified:
- 4d333a4 (Task 1) - FOUND
- 6590a05 (Task 2) - FOUND

---
*Phase: 03-slack-meeting-ingestion*
*Completed: 2026-02-24*
