# Phase 30: Slack Huddle Transcript Ingestion - Research

**Researched:** 2026-03-12
**Domain:** Slack API (Huddles, Canvases, Events), Meeting Transcript Ingestion
**Confidence:** MEDIUM

## Summary

Slack huddle transcripts and AI-generated notes are stored as **canvases** posted in the huddle thread within a channel. The Slack API provides limited but workable access to this data through a combination of: (1) detecting huddle messages via `conversations.history` (messages with a `room` object where `call_family == "huddle"`), (2) reading the huddle thread via `conversations.replies` using the `canvas_thread_ts`, (3) listing canvas files attached to the thread via `files.list`, and (4) reading canvas content using the `canvases:read` scope and canvas API methods.

The project already has a complete meeting transcript pipeline (MeetingTranscript + MeetingSegment models, Fathom ingestion pattern, embedding generation, linking engine integration). The new huddle ingestion service follows the same pattern with `source = "slack_huddle"`. The critical constraint is OAuth scopes: current scopes are `channels:read,channels:history,groups:read,groups:history,users:read`. Canvas access requires adding `canvases:read` and possibly `files:read` scopes, which means users must **re-authorize** the Slack integration.

**Primary recommendation:** Build a poll-based huddle transcript ingestion service (mirroring the Fathom pattern) that scans monitored channels for huddle messages, retrieves canvas content from huddle threads, and stores as MeetingTranscript records with `source = "slack_huddle"`. Add `canvases:read` and `files:read` to OAuth scopes. Trigger via manual poll endpoint and/or periodic sync.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HUDDLE-01 | Slack huddle transcripts and AI-generated summaries are ingested from Slack canvases/files attached to huddle channels | Huddle detection via `room.call_family == "huddle"` in channel history, canvas content via `canvases:read` scope, thread replies for canvas file discovery |
| HUDDLE-02 | Meeting records are stored with participant info, duration, and transcript text | Reuse existing MeetingTranscript model -- `room` object provides `participant_history`, `date_start`/`date_end` for duration, canvas markdown for transcript/summary |
| HUDDLE-03 | Meetings appear in the linking engine for ticket-to-meeting association | Linking engine already supports `meeting_transcript` and `meeting_segment` source types via `_SOURCE_SUMMARY_MAP` and `SOURCE_TYPE_MAP["fathom"]`; needs a `"slack_huddle"` key added to `SOURCE_TYPE_MAP` |
| HUDDLE-04 | Huddle data feeds into context page generation with meeting summaries | Synthesis pipeline already includes `fathom` in `connected_sources` list; add `"slack_huddle"` or map huddle meetings under existing source type |
| HUDDLE-05 | No new OAuth scopes break existing Slack message ingestion | New scopes (`canvases:read`, `files:read`) are additive and do not affect existing `channels:read/history` permissions; re-auth required for existing users |
</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | existing | Slack API HTTP calls | Already used for all Slack/Fathom API calls |
| SQLModel | existing | MeetingTranscript/MeetingSegment ORM | Existing meeting models |
| FastAPI | existing | Poll endpoint, Events API | Existing router pattern |

### No New Dependencies
This phase requires zero new Python packages. All work uses existing Slack API via httpx, existing DB models, and existing embedding/linking infrastructure.

## Architecture Patterns

### Recommended Approach

```
backend/src/
├── services/
│   └── slack_huddles.py      # NEW: Huddle transcript ingestion service
├── routers/
│   └── slack.py              # MODIFIED: Add /poll-huddles endpoint
├── models/
│   └── meeting.py            # UNCHANGED: Reuse MeetingTranscript/MeetingSegment
└── services/
    ├── linking.py            # MODIFIED: Add "slack_huddle" to SOURCE_TYPE_MAP
    ├── embedding.py          # UNCHANGED: Already handles meeting_transcript
    └── synthesis.py          # MODIFIED: Include slack_huddle in connected_sources
```

### Pattern 1: Huddle Detection via Channel History Scan

**What:** Scan `conversations.history` for messages containing a `room` object with `call_family == "huddle"` and `has_ended == true`.

**When to use:** During poll/sync operations.

**How it works:**
1. For each monitored channel, call `conversations.history`
2. Filter messages where `msg.get("room", {}).get("call_family") == "huddle"` and `room.has_ended == true`
3. Extract `room.canvas_thread_ts` to find the huddle notes thread
4. Use `room.participant_history` for participant list
5. Calculate duration from `room.date_start` and `room.date_end`

**Example huddle message structure (from Slack API docs):**
```json
{
  "type": "message",
  "user": "USLACKBOT",
  "room": {
    "id": "R12345ABCDE",
    "call_family": "huddle",
    "has_ended": true,
    "date_start": 1689964161,
    "date_end": 1689965000,
    "participant_history": ["U12345", "U67890"],
    "canvas_thread_ts": "1689964161.419229",
    "channels": ["C12345ABCDE"],
    "attached_file_ids": []
  }
}
```

### Pattern 2: Canvas Content Retrieval

**What:** After finding a huddle message, retrieve the AI-generated notes canvas from the huddle thread.

**When to use:** For each detected huddle.

**Approach (two strategies, try in order):**

**Strategy A -- Thread scan for canvas files:**
1. Call `conversations.replies(channel=channel_id, ts=canvas_thread_ts)`
2. Look for messages with `files` array containing items with `filetype == "canvas"` or `mimetype == "application/vnd.slack-docs"`
3. Use the canvas `id` (file ID like `F1234ABCD`) to read content

**Strategy B -- Direct files.list filter:**
1. Call `files.list(channel=channel_id, types=canvas, ts_from=huddle_start, ts_to=huddle_end+buffer)`
2. Match canvases by time proximity to the huddle

**Reading canvas content:**
- Use `canvases.sections.lookup(canvas_id=file_id, criteria={"section_type": "any_header"})` to get section IDs
- OR use the canvas edit API workaround: `canvases.edit` with a no-op to get current content
- OR download canvas via `url_private` from `files.info` response (requires `files:read` scope + bot token auth)

**IMPORTANT NOTE:** The Slack Canvas API has a known limitation -- there is no explicit `canvases.read` or `canvases.get` method. The `canvases:read` scope grants permission but the retrieval mechanism is indirect. The most reliable approach is:
1. Get canvas file ID from thread messages
2. Call `files.info` to get file metadata including `url_private`
3. Download content from `url_private` with Authorization header

### Pattern 3: Follow Fathom Ingestion Pattern

**What:** Mirror the existing `fathom.py` poll_transcripts pattern exactly.

**Key similarities:**
- Poll-based (not real-time event-driven) -- same as Fathom
- Background task execution -- same `_poll_background` pattern
- Dedup via `raw_data["huddle_room_id"]` -- same as `raw_data["fathom_id"]`
- Create MeetingTranscript + MeetingSegment records
- Queue embedding generation after ingestion
- Update `last_poll_at` in workspace_integrations.config

**Example service structure:**
```python
# backend/src/services/slack_huddles.py

async def poll_huddle_transcripts(
    session: AsyncSession,
    workspace_id: UUID,
) -> dict:
    """Poll Slack channels for huddle transcripts with AI notes."""
    bot_token = await get_bot_token(session, workspace_id)

    # Get monitored channels
    channels = await _get_monitored_channels(session, workspace_id)

    for channel_id in channels:
        # Scan channel history for huddle messages
        huddle_messages = await _find_huddle_messages(bot_token, channel_id)

        for msg in huddle_messages:
            room = msg["room"]
            room_id = room["id"]

            # Dedup check
            if await _already_ingested(session, workspace_id, room_id):
                continue

            # Get canvas content from huddle thread
            canvas_content = await _get_huddle_canvas_content(
                bot_token, channel_id, room["canvas_thread_ts"]
            )

            if not canvas_content:
                continue

            # Create MeetingTranscript record
            meeting = MeetingTranscript(
                workspace_id=workspace_id,
                source="slack_huddle",
                title=f"Huddle in #{channel_name}",
                transcript=canvas_content,
                summary=_extract_summary(canvas_content),
                participants=await _resolve_user_names(bot_token, room["participant_history"]),
                meeting_date=datetime.fromtimestamp(room["date_start"], tz=timezone.utc),
                duration_minutes=_calc_duration(room),
                raw_data={"huddle_room_id": room_id, **msg},
            )
            session.add(meeting)
            await session.flush()

            # Queue embedding
            await embedding.queue_embedding_generation(
                session, workspace_id, "meeting_transcript", [meeting.id]
            )

    return {"ingested": ingested_count, "skipped": skipped_count}
```

### Anti-Patterns to Avoid
- **Real-time event processing for huddles:** Unlike Slack messages which arrive via Events API, huddle transcripts are only available AFTER the huddle ends. Poll-based is the correct pattern.
- **Adding huddle scopes on first connect:** This would break existing Slack users. Scopes should be added to `SLACK_BOT_SCOPES` and users prompted to re-authorize if they want huddle support.
- **Treating canvases as plain text files:** Canvas content is markdown with Slack-specific formatting. Parse it properly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Meeting storage | Custom meeting table | Existing `MeetingTranscript`/`MeetingSegment` models | Already has participants, duration, summary, segments |
| Dedup logic | Custom dedup tracking | `raw_data["huddle_room_id"]` pattern (same as Fathom's `fathom_id`) | Proven pattern, JSONB query |
| Embedding pipeline | Custom embedding flow | `embedding.queue_embedding_generation()` | Already handles `meeting_transcript` source type |
| Linking engine | Custom linking logic | Existing `SOURCE_TYPE_MAP` in `linking.py` | Just add `"slack_huddle"` key mapping to `meeting_transcript`/`meeting_segment` |
| User name resolution | Custom user lookup | Slack `users.info` API (already have `users:read` scope) | Convert Slack user IDs to display names |
| Canvas content parsing | Custom HTML parser | Slack canvas markdown content (already markdown) | Canvas API returns markdown natively |

## Common Pitfalls

### Pitfall 1: OAuth Scope Migration
**What goes wrong:** Adding `canvases:read` and `files:read` to `SLACK_BOT_SCOPES` breaks nothing for NEW connections but existing workspaces have tokens with old scopes that cannot read canvases.
**Why it happens:** Slack bot tokens have fixed scopes from the time of authorization. Adding scopes requires re-authorization.
**How to avoid:**
1. Update `SLACK_BOT_SCOPES` constant for new connections
2. Check token scopes before attempting canvas reads
3. Show a "re-authorize" prompt in the UI when huddle feature is enabled but scopes are insufficient
4. Store granted scopes in `oauth_tokens.scopes` for runtime checking
**Warning signs:** 403/missing_scope errors from Slack API when calling canvas/file methods.

### Pitfall 2: Huddle Without AI Notes
**What goes wrong:** Not all huddles have AI-generated notes. Free plans and workspaces without Slack AI won't have canvas content.
**Why it happens:** AI notes require Slack AI add-on (paid feature).
**How to avoid:** Gracefully handle empty canvas threads. If no canvas found in huddle thread, still create a minimal MeetingTranscript with participants and duration but no transcript text. Log a warning, don't error.
**Warning signs:** Empty `conversations.replies` for huddle threads, no canvas files found.

### Pitfall 3: Canvas Content Format Uncertainty
**What goes wrong:** Canvas content structure may vary. AI-generated notes include sections like attendees, topics, action items in a Slack-specific markdown format.
**Why it happens:** Slack's canvas markdown is not fully standardized/documented for programmatic consumption.
**How to avoid:** Store raw canvas content as-is in `transcript` field. Do NOT attempt to parse sections into structured data. Let the LLM synthesis handle extraction.
**Warning signs:** Canvas content with unexpected formatting or missing sections.

### Pitfall 4: Rate Limiting on Channel Scan
**What goes wrong:** Scanning every monitored channel's full history on each poll is slow and hits rate limits.
**Why it happens:** `conversations.history` is tier 3 (50+ calls per minute) but scanning many channels adds up.
**How to avoid:**
1. Use `oldest` parameter with last poll timestamp to only fetch new messages
2. Store `last_huddle_poll_at` per channel in workspace_integrations.config
3. Limit to recent history (e.g., last 7 days on first poll)
**Warning signs:** Slack returning 429 rate limit errors during polling.

### Pitfall 5: No Direct Canvas Read API
**What goes wrong:** Assuming there's a `canvases.get` or `canvases.read` method to retrieve content.
**Why it happens:** The `canvases:read` scope exists but there's no single "get content" method.
**How to avoid:** Use the file-based approach: find canvas file ID in thread messages, call `files.info` for metadata, download content via `url_private` URL with bot token Authorization header. Alternatively, use `canvases.sections.lookup` to enumerate sections then `canvases.edit` (with empty changes) to read.
**Warning signs:** 404 or "method_not_found" errors when calling non-existent canvas read methods.

## Code Examples

### Detecting Huddle Messages in Channel History
```python
# Source: Slack API conversations.history docs
async def _find_huddle_messages(
    bot_token: str,
    channel_id: str,
    oldest: str | None = None,
) -> list[dict]:
    """Find completed huddle messages in channel history."""
    huddles = []
    cursor = None

    async with httpx.AsyncClient() as client:
        while True:
            params = {"channel": channel_id, "limit": 200}
            if oldest:
                params["oldest"] = oldest
            if cursor:
                params["cursor"] = cursor

            resp = await client.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {bot_token}"},
                params=params,
            )
            data = resp.json()
            if not data.get("ok"):
                break

            for msg in data.get("messages", []):
                room = msg.get("room")
                if (room
                    and room.get("call_family") == "huddle"
                    and room.get("has_ended")):
                    huddles.append(msg)

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    return huddles
```

### Getting Canvas Content from Huddle Thread
```python
# Source: Slack API conversations.replies + files.info docs
async def _get_huddle_canvas_content(
    bot_token: str,
    channel_id: str,
    thread_ts: str,
) -> str | None:
    """Retrieve canvas content from a huddle thread."""
    async with httpx.AsyncClient() as client:
        # Get thread replies to find canvas file
        resp = await client.get(
            "https://slack.com/api/conversations.replies",
            headers={"Authorization": f"Bearer {bot_token}"},
            params={"channel": channel_id, "ts": thread_ts},
        )
        data = resp.json()
        if not data.get("ok"):
            return None

        # Look for canvas files in thread messages
        for msg in data.get("messages", []):
            for file in msg.get("files", []):
                if file.get("filetype") == "canvas" or file.get("mimetype", "").startswith("application/vnd.slack"):
                    canvas_id = file.get("id")
                    if canvas_id:
                        return await _download_canvas_content(client, bot_token, canvas_id)

        return None


async def _download_canvas_content(
    client: httpx.AsyncClient,
    bot_token: str,
    canvas_id: str,
) -> str | None:
    """Download canvas content via files.info url_private."""
    resp = await client.get(
        "https://slack.com/api/files.info",
        headers={"Authorization": f"Bearer {bot_token}"},
        params={"file": canvas_id},
    )
    data = resp.json()
    if not data.get("ok"):
        return None

    url_private = data.get("file", {}).get("url_private")
    if not url_private:
        return None

    # Download the actual content
    content_resp = await client.get(
        url_private,
        headers={"Authorization": f"Bearer {bot_token}"},
    )
    if content_resp.status_code == 200:
        return content_resp.text

    return None
```

### Database Migration: Add slack_huddle to meeting_transcripts.source CHECK
```sql
-- Migration 00025: Add slack_huddle source type to meeting_transcripts
ALTER TABLE public.meeting_transcripts
  DROP CONSTRAINT IF EXISTS meeting_transcripts_source_check;

ALTER TABLE public.meeting_transcripts
  ADD CONSTRAINT meeting_transcripts_source_check
  CHECK (source IN ('google_meet', 'zoom', 'teams', 'fathom', 'manual', 'slack_huddle'));
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fathom API key auth | Slack OAuth with canvas scopes | Phase 30 | Huddles don't need a separate service -- reuse Slack's existing OAuth |
| No huddle access | Slack AI notes in canvases | July 2025 (Slack AI update) | Canvases are the output format for huddle transcripts |
| Recall.ai bot-in-huddle | Native canvas reading | 2025 | No third-party bot needed if workspace has Slack AI |

## Open Questions

1. **Canvas content retrieval method**
   - What we know: `canvases:read` scope exists, `files.info` returns `url_private`, `canvases.sections.lookup` returns section IDs
   - What's unclear: Whether downloading `url_private` for canvas files returns markdown or HTML; whether there's a cleaner undocumented method
   - Recommendation: Implement `files.info` + `url_private` download approach first; if content is HTML, add html-to-markdown conversion. Test with actual Slack workspace.

2. **Scope migration UX**
   - What we know: Existing Slack tokens won't have `canvases:read`/`files:read` scopes
   - What's unclear: Best UX for prompting re-authorization
   - Recommendation: Add a "Huddle transcripts require re-authorization" banner in settings when old scopes detected. For MVP, rely on the existing disconnect/reconnect flow.

3. **Huddle notes availability**
   - What we know: Only Slack AI add-on (paid) generates automatic notes. Free plans have no canvas notes after huddles.
   - What's unclear: What percentage of target users have Slack AI
   - Recommendation: Handle gracefully -- create meeting record with participants/duration even without transcript content. The participant and duration data alone has value for context pages.

## Sources

### Primary (HIGH confidence)
- Slack API `conversations.history` response with `room` object -- [Slack Developer Docs](https://docs.slack.dev/reference/methods/conversations.history/) -- verified `call_family: "huddle"`, `canvas_thread_ts`, `participant_history` fields
- Slack Canvases API -- [Slack Developer Docs](https://docs.slack.dev/surfaces/canvases/) -- `canvases:read` scope, `files.list` with `types=canvas`, canvas markdown format
- Existing codebase: `backend/src/services/fathom.py` -- proven poll-based transcript ingestion pattern
- Existing codebase: `backend/src/models/meeting.py` -- MeetingTranscript/MeetingSegment models
- Existing codebase: `backend/src/services/linking.py` -- SOURCE_TYPE_MAP, already handles meeting_transcript/meeting_segment
- Existing codebase: `backend/src/services/embedding.py` -- already handles meeting_transcript/meeting_segment source types

### Secondary (MEDIUM confidence)
- [Recall.ai blog: Get Recordings and Transcripts from Slack Huddles](https://www.recall.ai/blog/get-recordings-and-transcripts-from-slack-huddles-api) -- Confirms no direct huddle transcript API, but canvas-based approach works
- [Slack Help: Use AI to take huddle notes](https://slack.com/help/articles/31377193680019-Use-AI-to-take-huddle-notes-in-Slack) -- Confirms notes posted as canvas in huddle thread
- [TechCrunch: Slack huddle transcriptions](https://techcrunch.com/2025/07/17/slack-bolsters-search-with-ai-adds-transcriptions-and-summaries-for-huddles/) -- Feature announced July 2025

### Tertiary (LOW confidence)
- Canvas content download via `url_private` -- not fully verified with real Slack workspace; may return HTML instead of markdown
- `canvases.sections.lookup` as content reading workaround -- sections only return IDs, not content

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - reuses existing models and services entirely
- Architecture: MEDIUM - huddle detection pattern verified from API docs, but canvas content retrieval has uncertainty
- Pitfalls: HIGH - OAuth scope migration, rate limiting, and empty canvas handling are well-understood from similar integrations
- Canvas content access: LOW - no explicit "read canvas" method; approach needs runtime validation

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (Slack API changes infrequently; canvas API may evolve)
