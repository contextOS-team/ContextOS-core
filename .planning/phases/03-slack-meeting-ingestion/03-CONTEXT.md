# Phase 3: Slack and Meeting Ingestion - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingest real-time Slack messages from user-selected channels, store threaded conversations with sender info, filter noise, ingest Fathom meeting transcripts with speaker segmentation, and provide an integration setup page for managing Linear, Slack, and Fathom connections. Historical backfill and semantic Slack-to-ticket linking are out of scope (v2).

</domain>

<decisions>
## Implementation Decisions

### Channel Selection UX
- Flat list with checkboxes and a search/filter input for channel picker
- Show both public channels and private channels where bot has been invited
- Manual "Refresh channels" button to fetch new channels from Slack (no auto-sync on page visit)
- No channel limit for v1 — single team dogfooding won't hit scale issues

### Message Filtering Rules
- Filter out: bot messages, messages under 10 characters, join/leave/topic system messages
- Store file-sharing messages' text/comment but do not download or process attached files
- Store link-only messages (URLs are valuable signal for context)
- On message edit: overwrite stored text with latest version
- On message delete: soft-delete (set deleted_at), context generation skips deleted messages
- Store Slack user ID + display name at ingestion time for attribution in context pages
- Skip reactions/emoji tracking for v1
- Respect Slack Retry-After header on 429 rate limit responses

### Fathom Transcript Ingestion
- Poll Fathom API every 15 minutes for new/updated transcripts
- If transcript is still processing (no content yet), skip and retry on next poll cycle
- Fathom authentication via API key entered by user, stored in Vault (not OAuth)
- Store transcripts as speaker-segmented turns (speaker name, timestamp, text per segment)

### Integration Setup Page
- Card-based layout: one card each for Linear, Slack, Fathom
- Each card shows: service icon, name, status badge (connected/disconnected), connect/disconnect button
- Connected state shows: workspace name + "Connected X ago" timestamp
- Disconnect requires simple confirmation dialog ("This will stop syncing data. Existing data is kept.")
- Slack channel selection lives as an expandable section within the Slack card after connecting

### Claude's Discretion
- Exact Slack OAuth scopes (bot vs user token)
- Events API implementation details (HTTP mode vs Socket Mode)
- Slack event signature verification implementation
- Error states and loading states on the integration setup page
- Channel list pagination if workspace has many channels
- Fathom API pagination and cursor handling

</decisions>

<specifics>
## Specific Ideas

- Integration page cards should feel like Notion's integrations page — clean, one card per service
- Reuse Vault storage patterns from Phase 2 Linear integration for Slack tokens and Fathom API key
- Reuse HMAC-SHA256 signature verification pattern from Phase 2 webhooks for Slack event verification

</specifics>

<deferred>
## Deferred Ideas

- Slack historical backfill (last 90 days) — v2 requirement SLCK-07
- Semantic similarity for Slack-to-ticket linking — v2 requirement SLCK-08
- Reaction tracking for importance signaling — future enhancement
- File content processing (PDFs, images shared in Slack) — future enhancement

</deferred>

---

*Phase: 03-slack-meeting-ingestion*
*Context gathered: 2026-02-24*
