# Phase 22: Real-time Context Generation Progress UI - Research

**Researched:** 2026-03-06
**Domain:** SSE streaming, CSS animations, FastAPI async generators, fetch-based SSE consumption
**Confidence:** HIGH

## Summary

This phase replaces the silent toast-based generation flow with a real-time progress UI driven by Server-Sent Events (SSE). The backend needs a new streaming endpoint that runs generation inline (not in a BackgroundTask) and yields progress events as each integration source completes. The frontend needs a `fetch()`-based SSE consumer (not `EventSource`, which cannot send auth headers) and an inline progress component with CSS-only animations.

The current `generate_context_page()` in `synthesis.py` calls `find_related_content()` as a single monolithic step. This must be decomposed into per-source steps (Slack, GitHub, Notion, Fathom, Linear comments) that yield progress events individually. The LLM synthesis step then becomes the final "Synthesize" event.

**Primary recommendation:** Use `sse-starlette` (v3.3.2) for the SSE endpoint since the project's FastAPI is at v0.133.0 (native SSE requires v0.135.0+). On the frontend, use the standard `fetch()` API with `ReadableStream` to parse SSE events -- this allows sending the `Authorization: Bearer` header that the native `EventSource` API cannot support.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **SSE for progress delivery** -- new `GET /api/context/{ticket}/generate-stream` endpoint
- **Server continues on client disconnect** -- generation completes regardless
- **Keep existing POST /generate endpoint** -- no breaking changes for MCP/API key consumers
- **Supabase Realtime as fallback** -- existing subscription picks up final status on return
- **Vertical step list layout** -- icon + source label + status text per row
- **CSS transitions + keyframes only** -- no framer-motion. Build on existing `shimmer-sweep`, `event-enter`, `fade-in-up` keyframes
- **Monochrome teal icon scheme** -- muted-foreground waiting, teal active, foreground complete
- **Progress UI inline in context feed** -- expands from the generating card row
- **One step per connected integration + synthesis step** (Slack, GitHub, Notion, Fathom, Linear, Synthesize)
- **Disconnected integrations hidden** -- no "not connected" rows
- **Result counts specific per type** -- "Found 2 PRs, 5 code files" not "Found 7 items"
- **Zero results show as completed** -- "No messages found" (honest)
- **Integration status fetched via `getIntegrationStatus()` before starting**
- **On completion**: collapse animation into normal card row, then auto-navigate to detail page
- **On error**: failed step red with error icon + Retry/Dismiss buttons inline

### Claude's Discretion
- Exact collapse-to-card animation timing before auto-navigate
- CSS keyframe details (easing curves, durations, stagger delays)
- Progress bar inclusion (optional)
- Exact shimmer/pulse animation for active step
- How SSE endpoint handles concurrent generation requests for same ticket

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sse-starlette | 3.3.2 | SSE response class for FastAPI | Project FastAPI is v0.133.0; native SSE needs v0.135.0+. sse-starlette is the de facto standard, production-stable |
| fetch API + ReadableStream | Browser native | SSE consumption with auth headers | EventSource API cannot send custom headers (no Authorization Bearer support). fetch + stream parsing is the standard workaround |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| TextDecoder | Browser native | Decode SSE stream chunks to strings | Always -- decode Uint8Array from ReadableStream |
| lucide-react | existing | Step icons (Check, Circle, Loader2, AlertCircle) | Already in project for all icons |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette | Upgrade FastAPI to 0.135.0+ | Risk of breaking changes in upgrade; sse-starlette is a single-purpose dep with zero risk |
| fetch + ReadableStream | event-source-polyfill | Extra dependency for something achievable in ~30 lines of vanilla JS |
| sse-starlette | Starlette StreamingResponse | Would work but sse-starlette handles keep-alive pings, X-Accel-Buffering header, and disconnect detection automatically |

**Installation:**
```bash
cd backend && uv add sse-starlette
```

No frontend dependencies needed -- all browser-native APIs.

## Architecture Patterns

### Backend: Decomposed Generation with Progress Yielding

The current `generate_context_page()` is monolithic. It needs to be decomposed so each source search step can report progress independently.

**Current flow:**
```
generate_context_page()
  -> find_related_content()  [single call, queries all sources]
  -> llm.generate()          [single call]
  -> update DB
```

**New flow:**
```
generate_context_page_stream()
  -> yield {"event": "start", "steps": [...connected sources...]}
  -> for each connected source:
      -> yield {"event": "step_start", "source": "slack"}
      -> search slack messages
      -> yield {"event": "step_complete", "source": "slack", "count": 3, "detail": "Found 3 messages"}
  -> yield {"event": "step_start", "source": "synthesize"}
  -> llm.generate()
  -> yield {"event": "step_complete", "source": "synthesize", "detail": "Context generated"}
  -> yield {"event": "complete", "context_page_id": "..."}
```

### SSE Event Protocol

```typescript
// Event types the client receives:
type SSEEvent =
  | { event: 'start'; steps: string[] }           // Which steps will run
  | { event: 'step_start'; source: string }        // Step begins
  | { event: 'step_complete'; source: string; count: number; detail: string }
  | { event: 'step_error'; source: string; error: string }
  | { event: 'complete'; context_page_id: string }  // All done
  | { event: 'error'; message: string }              // Fatal error
```

### Backend SSE Endpoint Pattern

```python
# Source: sse-starlette docs + FastAPI patterns
from sse_starlette import EventSourceResponse, ServerSentEvent
import json

@router.get("/{ticket_identifier}/generate-stream")
async def stream_context_generation(
    ticket_identifier: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    async def event_generator():
        # yield progress events as generation proceeds
        async for event in generate_context_page_stream(
            session, user.workspace_id, ticket_identifier
        ):
            yield ServerSentEvent(
                data=json.dumps(event),
                event=event["event"],
            )

    return EventSourceResponse(event_generator())
```

### Frontend: fetch-based SSE Client

```typescript
// apiFetchSSE in lib/api.ts
export async function apiFetchSSE(
  path: string,
  onEvent: (event: { event: string; data: unknown }) => void,
  onError?: (error: Error) => void,
): Promise<void> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  const accessToken = session?.access_token ?? ''

  const response = await fetch(`${BACKEND_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: 'text/event-stream',
    },
  })

  if (!response.ok) throw new Error(`SSE error ${response.status}`)
  if (!response.body) throw new Error('No response body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    let currentEvent = ''
    let currentData = ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7)
      } else if (line.startsWith('data: ')) {
        currentData = line.slice(6)
      } else if (line === '' && currentData) {
        onEvent({
          event: currentEvent,
          data: JSON.parse(currentData),
        })
        currentEvent = ''
        currentData = ''
      }
    }
  }
}
```

### Frontend: Progress Component Structure

```
<ContextFeedPage>
  {filteredPages.map(page =>
    page.status === 'generating' && activeGeneration?.ticket === page.ticket_identifier
      ? <GenerationProgress ticket={page.ticket_identifier} steps={...} />
      : <ContextFeedRow page={page} />
  )}
```

### Anti-Patterns to Avoid
- **Do NOT use BackgroundTasks for the SSE endpoint** -- the async generator must run inline so it can yield events. BackgroundTasks fire-and-forget.
- **Do NOT use EventSource on the frontend** -- it cannot send Authorization headers. Use fetch + ReadableStream.
- **Do NOT create a separate DB session per step** -- use a single session across the entire generation flow, committing at the end.
- **Do NOT block the event loop** -- all source searches are already async, so the generator naturally yields between steps.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE response formatting | Manual text/event-stream response | sse-starlette `EventSourceResponse` | Handles keep-alive pings, X-Accel-Buffering, disconnect detection, proper formatting |
| SSE event framing | Manual `data: ...\n\n` string concat | sse-starlette `ServerSentEvent` | Handles multi-line data, event names, IDs, retry fields correctly |
| CSS animations | framer-motion or react-spring | CSS @keyframes + transitions | Project convention -- zero bundle cost, existing keyframes to extend |

**Key insight:** The SSE protocol is simple on paper but has edge cases (multi-line data fields, keep-alive requirements, proxy buffering). `sse-starlette` handles all of these. On the frontend, the SSE parsing is simple enough (~30 lines) that a library is unnecessary.

## Common Pitfalls

### Pitfall 1: Session Lifecycle in SSE Generator
**What goes wrong:** The DB session closes before the generator finishes because FastAPI's dependency injection closes the session when the response "completes" (which for SSE is immediately after returning EventSourceResponse).
**Why it happens:** FastAPI runs dependency cleanup when the response object is returned, not when the stream ends.
**How to avoid:** Create a dedicated session inside the async generator using `async with async_session() as session:` (same pattern as `_generate_in_background`). Do NOT rely on `Depends(get_session)`.
**Warning signs:** "Session is closed" errors mid-stream.

### Pitfall 2: EventSource Cannot Send Headers
**What goes wrong:** Using browser's native `EventSource` fails auth because it sends no Authorization header.
**Why it happens:** The EventSource API has no option for custom headers -- this is a known limitation of the spec.
**How to avoid:** Use `fetch()` with `ReadableStream` parsing. The `apiFetchSSE` pattern shown above handles this.
**Warning signs:** 401 errors on SSE endpoint.

### Pitfall 3: Token in Query String Security Risk
**What goes wrong:** Passing JWT as a query parameter to work around EventSource limitation exposes tokens in server logs, browser history, and proxy logs.
**Why it happens:** Common but insecure workaround for EventSource header limitation.
**How to avoid:** Use fetch-based approach instead. No query string tokens.
**Warning signs:** Token visible in URL bar or server access logs.

### Pitfall 4: Stale Closure in React SSE Callbacks
**What goes wrong:** The onEvent callback captures stale state, causing UI to not update or update incorrectly.
**Why it happens:** The fetch streaming loop holds a reference to the initial closure.
**How to avoid:** Use useRef pattern for callbacks (same pattern as `useContextPagesRealtime` -- store callback in ref, read from ref in the stream handler).
**Warning signs:** Steps appear to not update or show stale data.

### Pitfall 5: Server Continues but Client Shows Error
**What goes wrong:** User navigates away, generation completes on server, user returns and sees no result.
**Why it happens:** SSE connection was dropped, no retry mechanism.
**How to avoid:** The existing Supabase Realtime subscription (`useContextPagesRealtime`) already watches for status changes on `context_pages`. When the page transitions from "generating" to "ready", the feed updates automatically. This is the designed fallback per CONTEXT.md.
**Warning signs:** Page stuck on "generating" after navigation.

### Pitfall 6: Concurrent Generation Requests
**What goes wrong:** Two SSE streams start for the same ticket, causing duplicate work or DB conflicts.
**How to avoid:** Check if a context_page already has status="generating" before starting. If so, return a single SSE event indicating generation is already in progress, and let the Realtime subscription handle the final update.

## Code Examples

### Backend: Decomposed find_related_content per source

The current `find_related_content` in `linking.py` runs `_find_explicit_refs` + `_find_hybrid_matches` as two monolithic calls that query ALL source types at once. To yield per-source progress, decompose the explicit refs and hybrid matches into per-source queries:

```python
# New function in linking.py
async def find_source_content(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    source: str,  # "slack", "github", "notion", "fathom", "linear"
) -> tuple[list[LinkedItem], str]:
    """Find content for a single source type. Returns (items, detail_string)."""
    items = []

    if source == "slack":
        # Query SlackMessage for explicit refs + hybrid matches filtered to slack_message
        # Return items and "Found N messages"
        pass
    elif source == "github":
        # Query GithubPullRequest, GithubReview, CodeChunk
        # Return items and "Found N PRs, M code files"
        pass
    # ... etc

    return items, detail
```

### Frontend: SSE-aware progress state

```typescript
interface GenerationStep {
  source: string
  label: string
  status: 'waiting' | 'active' | 'complete' | 'error'
  detail?: string
  count?: number
}

interface GenerationState {
  ticket: string
  steps: GenerationStep[]
  status: 'streaming' | 'complete' | 'error'
  contextPageId?: string
}
```

### CSS: Progress step animations

```css
/* Pulse/shimmer for active step */
@keyframes step-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.step-active {
  animation: step-pulse 1.5s ease-in-out infinite;
  color: oklch(0.75 0.15 175); /* teal */
}

/* Collapse animation for transition to card */
@keyframes progress-collapse {
  from {
    max-height: 300px;
    opacity: 1;
  }
  to {
    max-height: 0;
    opacity: 0;
    padding: 0;
    margin: 0;
  }
}
```

### Integration status to step mapping

```typescript
const SOURCE_STEPS: Record<string, { label: string; key: keyof IntegrationStatusResponse }> = {
  slack: { label: 'Slack', key: 'slack' },
  github: { label: 'GitHub', key: 'github' },
  notion: { label: 'Notion', key: 'notion' },
  fathom: { label: 'Fathom', key: 'fathom' },
  linear: { label: 'Linear', key: 'linear' },
}

function getConnectedSteps(status: IntegrationStatusResponse): string[] {
  return Object.entries(SOURCE_STEPS)
    .filter(([_, config]) => status[config.key].status === 'connected')
    .map(([source]) => source)
    .concat(['synthesize']) // Always present
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| EventSource API | fetch + ReadableStream for auth'd SSE | 2023+ | Allows custom headers; EventSource still fine for public endpoints |
| sse-starlette external lib | FastAPI native EventSourceResponse | FastAPI 0.135.0 (Jan 2025) | Native support, but this project is on 0.133.0 so use sse-starlette |
| Polling for generation status | SSE streaming with Supabase Realtime fallback | This phase | Real-time progress instead of silent background processing |

**Note:** Upgrading FastAPI from 0.133.0 to 0.135.0+ would enable native SSE and eliminate the sse-starlette dependency. However, this is a discretionary optimization and not required -- sse-starlette is lightweight (single file, zero transitive deps beyond starlette which is already installed).

## Open Questions

1. **FastAPI version upgrade vs sse-starlette**
   - What we know: FastAPI 0.135.0+ has native SSE. Project is on 0.133.0. sse-starlette works on current version.
   - What's unclear: Whether upgrading FastAPI would introduce breaking changes.
   - Recommendation: Use sse-starlette (safest). Upgrading FastAPI can be done in a separate task if desired.

2. **Decomposition granularity of linking.py**
   - What we know: `_find_explicit_refs` queries all source types in one pass. `_find_hybrid_matches` runs a single hybrid_search SQL call that returns mixed source types.
   - What's unclear: Whether to decompose hybrid_search into per-source-type calls (adds latency) or post-filter results by source type (simpler, same total time).
   - Recommendation: Run the existing queries as-is but group/filter results by source type after fetching. Yield progress per source by processing items in source order. This avoids changing the DB query pattern while still providing per-source progress events.

3. **Linear comments as a separate step**
   - What we know: The CONTEXT.md lists "Linear (comments & context)" as a step. Linear comments come from `_find_explicit_refs` via the `LinearComment` FK query.
   - What's unclear: Whether Linear comments should be a visible step (Linear is always connected since it's required).
   - Recommendation: Include Linear as a step since the user explicitly listed it. It will always be visible (Linear is always connected per onboarding requirements).

## Sources

### Primary (HIGH confidence)
- FastAPI official SSE docs: https://fastapi.tiangolo.com/tutorial/server-sent-events/ -- native SSE added in v0.135.0
- sse-starlette PyPI: https://pypi.org/project/sse-starlette/ -- v3.3.2, production-stable
- Project codebase: `backend/src/services/synthesis.py`, `backend/src/services/linking.py`, `backend/src/routers/context.py` -- current generation flow
- Project codebase: `apps/web/src/lib/api.ts` -- existing `apiFetch` wrapper pattern
- Project codebase: `apps/web/src/hooks/use-context-pages-realtime.ts` -- ref-based callback pattern for Realtime
- Project codebase: `apps/web/src/app/globals.css` -- existing CSS keyframes

### Secondary (MEDIUM confidence)
- WHATWG HTML spec EventSource header issue: https://github.com/whatwg/html/issues/2177 -- confirms EventSource cannot send custom headers
- MDN Server-Sent Events: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events

### Tertiary (LOW confidence)
- None -- all findings verified with primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- sse-starlette is well-established, fetch+ReadableStream is browser-native
- Architecture: HIGH -- decomposition pattern is straightforward, existing code is well-understood
- Pitfalls: HIGH -- EventSource header limitation is well-documented, session lifecycle is a known FastAPI pattern

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain, no fast-moving deps)
