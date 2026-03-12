# Phase 29: Codebase Hardening - Security, Bug Fixes, Architecture, and UI/UX Polish - Research

**Researched:** 2026-03-12
**Domain:** Security hardening, bug fixes, code architecture, UI/UX improvements (Python/FastAPI backend + Next.js frontend)
**Confidence:** HIGH

## Summary

Phase 29 addresses all concerns identified in the codebase audit (`.planning/codebase/CONCERNS.md`). The work spans six categories: security fixes (JQL injection, IP spoofing, OAuth state signing, API key hashing), bug fixes (stuck "generating" status, duplicate migration, synthesis double flush, Telegram sync), architecture improvements (shared utils extraction, synthesis deduplication, settings decomposition), UI/UX polish (AlertDialog replacement, error messages, eslint-disable fixes), performance (token limit guard, skip disconnected sources, Slack ILIKE), and reliability (Redis consumer names, single-workspace assumption).

All issues are well-documented with exact file locations and fix approaches in CONCERNS.md. The fixes use existing patterns already established in the codebase -- no new libraries or frameworks are needed. The primary risk is regression in the synthesis pipeline (both stream and non-stream paths) and in the OAuth flows.

**Primary recommendation:** Group fixes into waves by risk level -- security and bugs first (highest impact, most testable), then architecture refactoring (higher regression risk), then UI/UX and performance last (lowest risk, most visible).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEC-01 | JQL injection sanitization | Regex validation `^[A-Z]+-\d+$` on ticket_identifier before JQL build |
| SEC-02 | X-Forwarded-For spoofing prevention | Trusted proxy validation or use `request.client.host` as fallback |
| SEC-03 | OAuth state signing with dedicated key | New `OAUTH_STATE_SECRET` env var, update `oauth_common.py` |
| SEC-04 | API key hashing with per-key salt | Add salt column to api_keys, update hash/verify functions |
| SEC-05 | Rate limiter Redis migration | Move counters to Redis atomic increment + TTL |
| SEC-06 | Bot token logging protection | Audit logging config, ensure no request body logging |
| BUG-01 | Stuck "generating" status on LLM failure | Write `status="error"` in exception handler of both synthesis paths |
| BUG-02 | Duplicate migration 00019 | Renumber `00019_jira_tables.sql` to `00020_jira_tables.sql` |
| BUG-03 | Non-stream synthesis double flush/commit | Ensure final flush has corresponding commit or remove redundant flush |
| BUG-04 | Telegram webhook synchronous processing | Restore `background_tasks.add_task()` pattern |
| ARCH-01 | Move `_parse_notion_datetime` to shared utils | Create `backend/src/utils/datetime.py` |
| ARCH-02 | Extract shared synthesis logic | Private helpers for ticket lookup, placeholder upsert, prompt build |
| ARCH-03 | Move deferred `import json` to top-level | Module-level imports in synthesis.py and jira.py |
| ARCH-04 | Settings page decomposition | Extract tab components to `settings/tabs/*.tsx` |
| ARCH-05 | Remove dead `LLMClient.generate_context_page` method | Delete unused method from llm_client.py |
| UI-01 | Replace window.confirm with AlertDialog | Use existing AlertDialog in integration-card.tsx |
| UI-02 | User-friendly error messages in generation progress | Map known error types to user-facing messages |
| UI-03 | Fix eslint-disable exhaustive-deps suppressions | Audit 4 locations, apply useCallback/useRef patterns |
| PERF-01 | LLM token limit guard | Approximate token count, truncate to model context window |
| PERF-02 | Skip disconnected source queries in linking | Pass connected_sources to find_content_by_source |
| PERF-03 | Slack ILIKE scan optimization | GIN index or delegate to hybrid search |
| REL-01 | Dynamic Redis consumer names | `f"worker-{socket.gethostname()}-{os.getpid()}"` |
| REL-02 | Single-workspace assumption safety | Add ORDER BY + LIMIT 1 to get_current_user query |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| FastAPI + Starlette | Backend framework | Already used, rate limiter is Starlette middleware |
| SQLAlchemy + SQLModel | ORM/models | Already used for all DB operations |
| redis.asyncio (aioredis) | Redis client | Already used for embedding/code-index workers |
| Radix UI AlertDialog | Modal confirmations | Already imported in settings page, just not in integration-card |
| Supabase migrations | Schema changes | Already used for all DB migrations |

### No new dependencies needed
This phase requires zero new libraries. Every fix uses patterns and tools already in the codebase.

## Architecture Patterns

### Pattern 1: Shared Utils Extraction
**What:** Move `_parse_notion_datetime` from `routers/notion.py` to `utils/datetime.py`
**Current state:** Services import a private function from a router (inverted dependency)
**Target structure:**
```
backend/src/utils/
  datetime.py          # _parse_notion_datetime (renamed to parse_notion_datetime)
```
**Importers to update:** `services/notion_sync.py:83`, `services/sync_scheduler.py:101`

### Pattern 2: Synthesis Deduplication
**What:** Extract shared logic from `generate_context_page` and `generate_context_page_stream` into private helpers
**Current state:** ~150 lines of duplicated ticket lookup, placeholder upsert, and prompt building
**Target helpers:**
```python
async def _lookup_ticket(session, workspace_id, ticket_identifier) -> tuple[ticket, ticket_id_for_fk]
async def _upsert_context_page_placeholder(session, workspace_id, ticket, ticket_id_for_fk) -> ContextPage
def _build_synthesis_prompt(ticket, related_items) -> str
```
**Critical:** The stream path yields events between steps -- helpers must not break the generator flow. Only extract pure lookups and prompt building, not the event emission logic.

### Pattern 3: Settings Page Decomposition
**What:** Break 1,018-line monolith into tab components
**Current state:** All four sections (General, API Keys, Team, Integrations) inline in one file
**Target structure:**
```
apps/web/src/app/dashboard/settings/
  page.tsx              # Shell with tab routing, data fetching
  tabs/
    general-tab.tsx     # Workspace name editing
    api-keys-tab.tsx    # Key CRUD with AlertDialog
    team-tab.tsx        # Member list
    integrations-tab.tsx # Connect/disconnect cards
```

### Pattern 4: Error Status Propagation in Synthesis
**What:** Write `status="error"` to context_page when LLM fails
**Current behavior:** Exception in stream path yields `{"event": "error"}` SSE but never writes error status to DB. Page stays `"generating"` forever.
**Fix pattern:**
```python
except Exception as e:
    logger.exception("Stream generation failed for %s", ticket_identifier)
    # Write error status to DB
    if context_page:
        context_page.status = "error"
        await session.flush()
        await session.commit()
    yield {"event": "error", "message": str(e)}
```
**Note:** The non-stream path also needs this -- the caller at `context.py:232` wraps in try/except but doesn't set error status either.

### Pattern 5: Redis Rate Limiter
**What:** Replace in-memory sliding window with Redis-backed counters
**Current pattern in codebase:** `embedding_worker.py` already uses `redis.asyncio` for Redis Streams
**Fix pattern:**
```python
async def _check_rate_limit(redis: aioredis.Redis, key: str, limit: int, window: int) -> bool:
    pipe = redis.pipeline()
    now = time.time()
    pipe.zremrangebyscore(key, 0, now - window)  # Remove expired
    pipe.zadd(key, {str(now): now})               # Add current
    pipe.zcard(key)                                # Count
    pipe.expire(key, window)                       # TTL
    results = await pipe.execute()
    return results[2] <= limit
```
**Uses sorted sets for sliding window -- standard Redis rate limiting pattern.**

### Anti-Patterns to Avoid
- **Modifying both synthesis paths independently:** After extracting shared helpers, both paths must call the same functions. Never copy-paste a fix to one path without the other.
- **Breaking SSE generator flow:** The stream path is an `async def ... -> AsyncGenerator`. Any helper extraction must not interfere with `yield` statements.
- **Migration ordering assumptions:** Renumbering 00019 requires checking that no production environment has applied the conflicting migration.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting with Redis | Custom counter logic | Redis sorted sets (ZADD/ZRANGEBYSCORE) | Atomic, survives restarts, scales horizontally |
| JQL sanitization | Character-by-character stripping | Regex `^[A-Z]+-\d+$` allowlist | Allowlists are always safer than denylists |
| Token counting | Exact tokenizer | `len(text) // 4` approximation | Good enough for context window guard; tiktoken adds complexity |
| API key hashing with salt | Custom salt scheme | `hashlib.sha256(salt + key)` with `os.urandom(16)` | Standard pattern, salt stored alongside hash |
| Confirmation dialogs | Custom modal | Existing AlertDialog from `@/components/ui/alert-dialog` | Already built and styled for the project |

## Common Pitfalls

### Pitfall 1: Breaking the SSE Stream During Synthesis Refactor
**What goes wrong:** Extracting shared logic from `generate_context_page_stream` accidentally moves a `yield` into a non-generator helper function.
**Why it happens:** The stream function yields events between database operations and LLM calls.
**How to avoid:** Only extract pure async functions (ticket lookup, prompt building). Keep all `yield` statements in the generator itself.
**Warning signs:** `TypeError: 'coroutine' object is not an async generator` at runtime.

### Pitfall 2: Migration Renumbering in Production
**What goes wrong:** Renumbering `00019_jira_tables.sql` to `00020` when some environments have already applied it as `00019`.
**Why it happens:** Supabase tracks applied migrations by filename.
**How to avoid:** Check `supabase_migrations.version` table in all environments. If already applied, use a new migration number instead.
**Warning signs:** `supabase db push` shows "already applied" errors.

### Pitfall 3: OAuth State Signing Key Rotation
**What goes wrong:** Switching from client_secret to OAUTH_STATE_SECRET breaks all in-flight OAuth flows.
**Why it happens:** Users who started OAuth before the change have state signed with the old key.
**How to avoid:** Support both keys during transition (try new key first, fall back to old), or accept that in-flight flows will fail (they are short-lived browser redirects).

### Pitfall 4: Redis Connection in Rate Limiter Middleware
**What goes wrong:** Redis connection failure in middleware causes 500 errors on every request.
**Why it happens:** Middleware runs before the route handler -- no try/except.
**How to avoid:** Catch Redis exceptions and fall back to allowing the request (fail open for rate limiting is safer than fail closed).

### Pitfall 5: Settings Page State During Decomposition
**What goes wrong:** Extracting tab components breaks shared state (e.g., workspace data, loading flags).
**Why it happens:** The monolith shares state via local variables; extracted components need props or context.
**How to avoid:** Pass workspace data and callbacks as props to each tab component. Don't over-engineer with context providers for a single page.

## Code Examples

### JQL Injection Fix
```python
# backend/src/routers/context.py — replace character stripping
import re

TICKET_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")

def _validate_ticket_identifier(identifier: str) -> str:
    """Validate ticket identifier matches KEY-123 format."""
    if not TICKET_ID_PATTERN.match(identifier):
        raise ValueError(f"Invalid ticket identifier format: {identifier}")
    return identifier
```

### Error Status Propagation in Stream Path
```python
# backend/src/services/synthesis.py — inside generate_context_page_stream
except Exception as e:
    logger.exception("Stream generation failed for %s", ticket_identifier)
    # Persist error status so UI shows failure instead of stuck "generating"
    try:
        context_page.status = "error"
        await session.flush()
        await session.commit()
    except Exception:
        logger.warning("Failed to persist error status for %s", ticket_identifier)
    yield {"event": "error", "message": str(e)}
```

### Dynamic Redis Consumer Name
```python
# backend/src/services/embedding_worker.py
import os
import socket

CONSUMER_NAME = f"worker-{socket.gethostname()}-{os.getpid()}"
```

### AlertDialog Replacement for Disconnect
```typescript
// apps/web/src/app/dashboard/integrations/integration-card.tsx
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="ghost" size="sm" disabled={isLoading}>
      Disconnect
    </Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Disconnect {name}?</AlertDialogTitle>
      <AlertDialogDescription>
        This will stop syncing data. Existing data is kept.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={handleDisconnect}>
        Disconnect
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

### Token Limit Guard
```python
# backend/src/services/synthesis.py
MAX_PROMPT_CHARS = 100_000  # ~25k tokens, leaves room for system prompt + response

def _format_related_content(items: list[LinkedItem], max_chars: int = MAX_PROMPT_CHARS) -> str:
    """Format related content with a character budget."""
    parts = []
    char_count = 0
    for item in items:
        section = f"### {item.source_type}: {item.title}\n{item.snippet}\n---\n"
        if char_count + len(section) > max_chars:
            parts.append(f"\n[Truncated: {len(items) - len(parts)} more items omitted]")
            break
        parts.append(section)
        char_count += len(section)
    return "\n".join(parts)
```

### User-Friendly Error Messages
```typescript
// apps/web/src/components/generation-progress.tsx
const ERROR_MESSAGES: Record<string, string> = {
  'not found': 'The ticket could not be found. Please check the identifier.',
  'rate limit': 'AI service is temporarily busy. Please try again in a moment.',
  'quota': 'AI service quota exceeded. Please contact your admin.',
  'timeout': 'Generation took too long. Please try again.',
}

function friendlyError(raw: string): string {
  const lower = raw.toLowerCase()
  for (const [key, msg] of Object.entries(ERROR_MESSAGES)) {
    if (lower.includes(key)) return msg
  }
  return 'Something went wrong during generation. Please try again.'
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-memory rate limiting | Redis sorted set sliding window | Standard for multi-process | Survives restarts, scales horizontally |
| Character stripping for JQL | Allowlist regex validation | Security best practice | Eliminates injection by design |
| Client secret for OAuth state | Dedicated signing key | Separation of concerns | Key rotation doesn't break OAuth flows |
| `window.confirm()` | Radix AlertDialog | Already in project | Styled, accessible, not blocked in iframes |

## Open Questions

1. **Migration 00019 production state**
   - What we know: Git status shows 00021 as newest, so 00019 may or may not be applied in production
   - What's unclear: Whether any staging/production environment has applied either 00019 migration
   - Recommendation: Check `supabase_migrations` table before renumbering. If applied, create a net-new fixup migration instead.

2. **Rate limiter Redis migration scope**
   - What we know: Redis is already available and used for embedding/code-index workers
   - What's unclear: Whether the rate limiter should also protect non-webhook paths (currently only webhooks/OAuth)
   - Recommendation: Keep the same path scope, just move the storage backend. Expanding scope is a separate concern.

3. **BackgroundTasks -> Redis Streams migration**
   - What we know: CONCERNS.md identifies this for Linear, Notion, Fathom, Jira, GitLab, Context
   - What's unclear: Whether this full migration belongs in Phase 29 or is too large
   - Recommendation: Exclude from Phase 29. The Telegram fix (restoring background_tasks) is quick. Full Redis Streams migration is a separate phase of work.

4. **API key salt migration**
   - What we know: Current keys use unsalted SHA-256
   - What's unclear: Whether existing keys need re-hashing (requires knowing the plaintext, which is only shown once)
   - Recommendation: Add salt for new keys only. Existing keys remain with unsalted hash (they are long random strings, making rainbow tables impractical).

## Sources

### Primary (HIGH confidence)
- `backend/src/services/synthesis.py` -- Verified duplicate logic at lines 146-289 (non-stream) and 292-500 (stream)
- `backend/src/middleware/rate_limit.py` -- Verified X-Forwarded-For handling at line 67-73
- `backend/src/services/oauth_common.py` -- Verified HMAC signing with client secret at lines 25-41
- `backend/src/routers/context.py` -- Verified JQL injection risk at lines 139-142
- `backend/src/services/embedding_worker.py` -- Verified hardcoded consumer name at line 30
- `backend/src/services/code_index_worker.py` -- Verified hardcoded consumer name at line 34
- `apps/web/src/app/dashboard/integrations/integration-card.tsx` -- Verified window.confirm at line 96
- `apps/web/src/app/dashboard/settings/page.tsx` -- Verified 1,018 lines, AlertDialog already imported
- `.planning/codebase/CONCERNS.md` -- Primary source for all issues

### Secondary (MEDIUM confidence)
- Redis sorted set rate limiting pattern -- well-established, used by rate-limiter-flexible, Upstash, and others

## Metadata

**Confidence breakdown:**
- Security fixes: HIGH -- exact file locations and fix approaches verified in source
- Bug fixes: HIGH -- root causes confirmed by reading the actual code
- Architecture: HIGH -- patterns already exist in codebase (just need extraction/decomposition)
- UI/UX: HIGH -- AlertDialog component already built, eslint-disable locations verified
- Performance: MEDIUM -- token counting approximation is standard but model context windows vary

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable -- internal codebase fixes, no external API dependency)
