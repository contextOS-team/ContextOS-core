# Codebase Concerns

**Analysis Date:** 2026-03-12

---

## Tech Debt

**Telegram webhook runs synchronously (production blocker):**
- Issue: Telegram webhook processing runs synchronously instead of via background task. The TODO comment explicitly acknowledges this: "Process synchronously for debugging (TODO: move back to background_tasks)". This blocks the Telegram HTTP response for the full event processing time, risking Telegram retrying events.
- Files: `backend/src/routers/telegram.py:98-99`
- Impact: Webhook response time directly equals processing time. Telegram may retry, causing duplicate processing. Production reliability issue.
- Fix approach: Restore `background_tasks.add_task(_process_update_background, payload, workspace_id)` pattern.

**`_parse_notion_datetime` imported from router layer into service layer:**
- Issue: `notion_sync.py` and `sync_scheduler.py` import a private helper `_parse_notion_datetime` directly from `src.routers.notion`. This inverts the dependency direction — services should never import from routers.
- Files: `backend/src/services/notion_sync.py:83`, `backend/src/services/sync_scheduler.py:101`
- Impact: Creates a circular dependency risk and couples the service to router internals. The function cannot be moved or renamed without breaking the service layer.
- Fix approach: Move `_parse_notion_datetime` to a shared utility module (e.g., `backend/src/utils/datetime.py`) and update all importers.

**Duplicate `generate_context_page` + `generate_context_page_stream` logic:**
- Issue: Both functions in `backend/src/services/synthesis.py` duplicate the ticket lookup logic (Linear-first, then Jira), the context page placeholder creation/status-update logic, and the prompt building logic. If one is changed, the other must also be updated.
- Files: `backend/src/services/synthesis.py:146-289` (non-stream), `backend/src/services/synthesis.py:292-500` (stream)
- Impact: Bug fixes in one path may not be applied to the other. Already observed inconsistency: non-stream does `flush + commit` twice; stream does `flush` without intermediate commit.
- Fix approach: Extract shared logic (ticket lookup, placeholder upsert, prompt build) into private helpers that both paths call.

**`import json` inside functions (deferred imports scattered throughout):**
- Issue: `json` is imported inside a function body in `synthesis.py:255` and `jira.py:299`. This is a non-standard pattern that obscures module dependencies.
- Files: `backend/src/services/synthesis.py:255`, `backend/src/routers/jira.py:299`
- Impact: Minor — deferred imports work, but violate Python convention and make dependency tracking harder.
- Fix approach: Move `import json` to module top-level.

**GitLab sync uses `BackgroundTasks` (not Redis), acknowledged as tech debt:**
- Issue: GitLab sync trigger uses FastAPI `BackgroundTasks`, which are lost on server restart. The TODO comment explicitly calls for migration to Redis Streams (same pattern as GitHub/embedding workers).
- Files: `backend/src/routers/gitlab.py:268-271`
- Impact: Any server restart during a GitLab sync silently drops the sync job. Users won't see updated data and won't be notified.
- Fix approach: Implement a Redis Stream job for GitLab sync following the pattern in `backend/src/services/embedding_worker.py`.

**Linear, Notion, Fathom, Context, and Jira also use `BackgroundTasks` (same issue):**
- Issue: Multiple routers still use `BackgroundTasks` rather than Redis Streams for sync jobs, making sync unreliable across restarts.
- Files: `backend/src/routers/linear.py:269`, `backend/src/routers/notion.py:276,307`, `backend/src/routers/fathom.py:100`, `backend/src/routers/context.py:262`, `backend/src/routers/jira.py:238`
- Impact: Any sync job in flight during a deployment/restart is silently lost.
- Fix approach: Phase-by-phase migration to Redis Streams using the existing `embedding_worker.py` pattern.

**Hardcoded Redis consumer name prevents horizontal scaling:**
- Issue: Both worker files use `CONSUMER_NAME = "worker-1"` as a module-level constant. With multiple replicas, all workers compete on the same consumer identity, which prevents proper consumer-group fan-out in Redis Streams.
- Files: `backend/src/services/embedding_worker.py:30`, `backend/src/services/code_index_worker.py:34`
- Impact: Consumer group delivery becomes unreliable with >1 replica.
- Fix approach: Generate the consumer name from hostname + PID: `f"worker-{socket.gethostname()}-{os.getpid()}"`.

**Single-workspace assumption in `get_current_user`:**
- Issue: `get_current_user` queries `workspace_members` and returns the first workspace membership found. If a user is ever a member of multiple workspaces, the wrong workspace may be selected non-deterministically (SQLAlchemy's `scalar_one_or_none` with no `ORDER BY`).
- Files: `backend/src/dependencies.py:44-49`
- Impact: For current single-workspace-per-user design, no immediate issue. Any future multi-workspace feature would cause silent workspace misrouting.
- Fix approach: Add `ORDER BY created_at ASC LIMIT 1` or implement explicit workspace selection header.

**`settings.py` loads `.env` from `../` (parent directory relative path):**
- Issue: `model_config = { "env_file": "../.env" }` uses a relative path from the `backend/` directory. This works only when the server is started from `backend/`, not from the repo root or via Docker without explicit WORKDIR.
- Files: `backend/src/config.py:141`
- Impact: Silent missing-env-var failures when started from unexpected working directories.
- Fix approach: Use an absolute path based on `__file__` or rely solely on real environment variables in production.

---

## Known Bugs

**Non-stream `generate_context_page` does a second flush+commit after the session may already be committed:**
- Symptoms: The non-stream path calls `flush + commit` twice (line 211-226 for placeholder, then `flush` at line 280). The session remains open across the commit, which is correct, but the final `flush` without a corresponding `commit` means the page status change to `"ready"` is only persisted when the caller commits.
- Files: `backend/src/services/synthesis.py:209-226`, `backend/src/services/synthesis.py:280`
- Trigger: Any caller that doesn't commit after `generate_context_page` returns will leave the context page in `"generating"` status permanently.
- Workaround: The background task caller at `backend/src/routers/context.py:232` does `await session.commit()` after the call.

**Historical fractional migration numbers require normalized local repair:**
- Symptoms: Older files used short versions next to pseudo-fractional versions, e.g. `00004` before `000045` and `00019` before `000195`; Supabase CLI can report local/remote mismatch even when the schema exists.
- Files: `supabase/migrations/000040_github_tables.sql`, `supabase/migrations/000045_vault_lazy_migration.sql`, `supabase/migrations/000190_gitlab_tables.sql`, `supabase/migrations/000195_jira_tables.sql`
- Trigger: Running Supabase migration commands against a DB whose ledger still has the old `00004` or `00019` version IDs.
- Workaround: Repair the migration ledger to `000040` and `000190` after confirming the GitHub/GitLab tables already exist; do not replay those SQL files against an existing DB.

**JQL injection sanitization is incomplete:**
- Symptoms: The Jira sync JQL query only strips backslashes and double-quotes from `ticket_identifier`, but does not validate that the remaining string matches the expected `KEY-123` format.
- Files: `backend/src/routers/context.py:139-142`, `backend/src/routers/context.py:220-223`
- Trigger: A `ticket_identifier` containing characters like `;`, `OR`, `AND` could manipulate the JQL query.
- Workaround: Pattern-match `ticket_identifier` against `^[A-Z]+-\d+$` before building the JQL string.

**`X-Forwarded-For` trusted unconditionally in rate limiter:**
- Symptoms: `_get_client_ip` uses the first value in `X-Forwarded-For` header without verifying the request came through a trusted proxy. Any client can spoof their IP to bypass rate limits.
- Files: `backend/src/middleware/rate_limit.py:67-73`
- Trigger: Sending `X-Forwarded-For: 1.2.3.4` bypasses per-IP rate limits entirely.
- Workaround: In production behind nginx, the real client IP is set correctly by nginx. Risk is low if the backend port is not directly exposed.

---

## Security Considerations

**Bot token sent as plain JSON to `/api/telegram/connect`:**
- Risk: Telegram bot tokens are sent in request body JSON, logged by default middleware if request bodies are logged.
- Files: `backend/src/routers/telegram.py:37-44`
- Current mitigation: Structured logging is configured; the token is not explicitly logged.
- Recommendations: Ensure request body logging is never enabled in production. Treat the bot token like a password in all logging contexts.

**OAuth state signed with client secret, not a dedicated signing key:**
- Risk: The HMAC signature for OAuth CSRF state uses the provider's client secret (e.g., `NOTION_CLIENT_SECRET`, `GITLAB_CLIENT_SECRET`). If a client secret rotates, all in-flight OAuth flows break silently with no error message distinguishing rotation from CSRF.
- Files: `backend/src/services/oauth_common.py:25-41`, `backend/src/routers/notion.py:50`, `backend/src/routers/gitlab.py:56`
- Current mitigation: State expires with the OAuth flow TTL (browser redirect).
- Recommendations: Use a dedicated `OAUTH_STATE_SECRET` for signing; separate concerns.

**`CORS_ORIGINS` used as redirect base in OAuth callbacks:**
- Risk: `frontend_url = settings.CORS_ORIGINS.split(",")[0].strip()` is used to build OAuth redirect URLs. If `CORS_ORIGINS` contains multiple origins, only the first is used, which is fragile. A misconfigured env var can redirect users to an unintended domain.
- Files: `backend/src/routers/notion.py:70`, `backend/src/routers/gitlab.py` (same pattern)
- Current mitigation: Production validation checks `CORS_ORIGINS` doesn't contain localhost.
- Recommendations: Add a dedicated `FRONTEND_URL` config variable used only for OAuth redirects.

**API key stored with only SHA-256 hash, no salt:**
- Risk: API keys are hashed for storage. Without per-key salts, rainbow table attacks against the hash column are feasible if the DB is compromised.
- Files: `backend/src/services/api_key.py`, `backend/src/utils/hashing.py`
- Current mitigation: Keys are long random strings, making rainbow tables impractical in practice.
- Recommendations: Add per-key salt stored alongside the hash.

**In-memory rate limiter does not survive process restarts:**
- Risk: Rate limit state is lost on every restart/deploy, allowing burst attacks immediately after a deployment.
- Files: `backend/src/middleware/rate_limit.py:62-65`
- Current mitigation: Webhook endpoints have 120 req/min limits.
- Recommendations: Move rate limit state to Redis for persistence across restarts (already have Redis available).

---

## Performance Bottlenecks

**No LLM token limit guard on synthesis prompt:**
- Problem: The synthesis prompt concatenates all related content from `linking_result.items` without a cap. A ticket with many PRs, Slack messages, and code chunks can produce prompts exceeding the model's context window.
- Files: `backend/src/services/synthesis.py:232-243`
- Cause: `_format_related_content` joins all items with `---` separators but has no token budget enforcement.
- Improvement path: Count approximate tokens (chars/4) and truncate `all_items` to fit the model's context window minus system prompt + response buffer.

**N+1 eliminated in `_bulk_lookup_source_summaries` but `find_content_by_source` still executes all source queries upfront:**
- Problem: `find_content_by_source` runs `_find_explicit_refs` and `_find_hybrid_matches` for every generation request, even for sources not connected to the workspace.
- Files: `backend/src/services/linking.py:461-462`
- Cause: Both query functions run regardless of which integrations are connected, then `generate_context_page_stream` filters afterward.
- Improvement path: Pass `connected_sources` into `find_content_by_source` to skip queries for disconnected providers.

**Slack message linking does ILIKE scan on entire workspace messages:**
- Problem: Finding Slack messages that reference a ticket identifier uses `SlackMessage.text.ilike(f"%{ticket.identifier}%")` — a full table scan with no index support on the `text` column.
- Files: `backend/src/services/linking.py:199-202`
- Cause: `ILIKE '%...'` prevents index use; scales linearly with workspace message count.
- Improvement path: Add a GIN text search index on `slack_messages.text` and use `@@` full-text operator, or rely on the hybrid search path for Slack messages instead.

**Code indexer clones full repos to disk for every re-index:**
- Problem: `index_repo` clones the entire repository to a temp directory using `git clone`, even for incremental re-indexes where only a few files changed.
- Files: `backend/src/services/code_indexer.py`
- Cause: No shallow clone (`--depth 1`) or sparse checkout. Large repos (>100MB) block the code index worker for extended periods.
- Improvement path: Use `git clone --depth 1` or `git archive` to fetch only current state without full history.

**Notion reconciliation fetches only the first 100 pages:**
- Problem: `reconcile_notion` calls `client.search_pages(page_size=100)` and only processes that single page of results, missing any updates beyond the first 100 pages.
- Files: `backend/src/services/sync_scheduler.py:80-82`
- Cause: No pagination loop in the reconciliation function.
- Improvement path: Paginate through all results using the Notion API cursor, matching the behavior of the full sync path.

---

## Fragile Areas

**`generate_context_page_stream` SSE generator has no timeout:**
- Files: `backend/src/routers/context.py:87-168`
- Why fragile: If `llm.generate()` hangs (e.g., OpenAI quota, network issue), the SSE stream will stay open indefinitely, holding the DB session open and consuming a connection pool slot.
- Safe modification: Add `asyncio.wait_for(..., timeout=120)` around the LLM call and emit an error event on timeout.
- Test coverage: `backend/tests/test_synthesis_stream.py` mocks the LLM call; timeout behavior is untested.

**Realtime subscription uses hardcoded channel name `context-pages-changes`:**
- Files: `apps/web/src/hooks/use-context-pages-realtime.ts:39`
- Why fragile: If two instances of `useContextPagesRealtime` are mounted (e.g., under React StrictMode double-invoke race), they both attempt to subscribe to the same channel name. The hook handles cleanup via `removeChannel`, but a brief window exists where two subscriptions may be active.
- Safe modification: Append a unique suffix to the channel name, e.g., using `useId()`.
- Test coverage: None (realtime hook is not tested).

**`scalar_one()` calls will throw `NoResultFound` on empty upsert results:**
- Files: `backend/src/services/linear_sync.py:324`, `backend/src/services/github_sync.py:308,314`, `backend/src/services/jira_sync.py:373`, `backend/src/services/notion_sync.py:145`, `backend/src/services/gitlab_sync.py:283,289`, `backend/src/services/telegram_events.py:108`
- Why fragile: These calls follow `INSERT ... ON CONFLICT DO UPDATE ... RETURNING id` patterns. If the upsert produces no row (e.g., RLS blocks the insert, or a DB trigger fails silently), `scalar_one()` raises `sqlalchemy.exc.NoResultFound`, which propagates as an unhandled 500.
- Safe modification: Replace with `scalar_one_or_none()` followed by explicit handling for `None`.
- Test coverage: Upsert failure paths are not tested.

**Activity timeline loads `workspaceId` from URL search params without validation:**
- Files: `apps/web/src/app/dashboard/activity/activity-timeline.tsx:160-174`
- Why fragile: Direct Supabase queries using `workspaceId` from props. If `workspaceId` is ever `undefined` or null, the query returns data for all workspaces (or errors silently).
- Safe modification: Validate `workspaceId` is a valid UUID before executing the query, redirect to error page if invalid.

**`LLMClient.generate_context_page` method is a dead code stub:**
- Files: `backend/src/services/llm_client.py:120-168`
- Why fragile: The `LLMClient.generate_context_page` method builds its own prompt independently of the main `SYNTHESIS_TEMPLATE` in `synthesis.py`. It is never called in production. If `synthesis.py` prompt is updated, this stub will silently diverge.
- Safe modification: Remove the dead method or mark it `@deprecated`.

---

## Scaling Limits

**In-memory rate limiter:**
- Current capacity: Single-process memory, unbounded growth up to `_CLEANUP_THRESHOLD`.
- Limit: With horizontal scaling (multiple FastAPI replicas), each replica maintains its own rate limit counter. An attacker can bypass limits by distributing requests across replicas.
- Scaling path: Move counters to Redis using an atomic increment + expiry pattern.

**Redis consumer group with single fixed consumer name:**
- Current capacity: Single consumer (`worker-1`) processes all embedding and code index jobs.
- Limit: Cannot scale to multiple embedding/code-index workers without consumer name collisions.
- Scaling path: Dynamic consumer names from hostname/PID as described above.

**Code indexer writes full repo clone to local disk:**
- Current capacity: Limited by available disk on the single host.
- Limit: Large monorepos (>1GB) or many concurrent index jobs will exhaust disk.
- Scaling path: Use object storage (S3) as temporary staging or stream content without full clone.

---

## Dependencies at Risk

**`BackgroundTasks` for sync jobs (architectural risk, not a package):**
- Risk: FastAPI `BackgroundTasks` are process-local and lost on crash/restart. Only embedding/code-index use Redis Streams for durability.
- Impact: Linear, Notion, Fathom, Jira, GitLab, and context generation syncs are dropped on any restart.
- Migration plan: Extend the Redis Stream pattern from `embedding_worker.py` to all sync job types.

---

## Missing Critical Features

**No LLM error status propagation to context page on synthesis failure:**
- Problem: If `llm.generate()` throws (rate limit, invalid API key, quota exceeded), the exception propagates out of `generate_context_page_stream`, which catches it and yields `{"event": "error"}`. However, the `context_page` record in the DB remains with `status="generating"` forever — no `status="error"` is written.
- Files: `backend/src/services/synthesis.py:498-500`, `backend/src/routers/context.py:160-165`
- Blocks: Users see a spinning "generating" state forever after an LLM failure. No retry is possible from the UI since the page appears in-progress.

**No GitLab sync tests:**
- Problem: There are no dedicated test files for GitLab OAuth (`gitlab_oauth.py`), GitLab sync (`gitlab_sync.py`), or GitLab webhook (`gitlab_webhook.py`). Only synthesis stream tests incidentally mention GitLab.
- Files: `backend/src/services/gitlab_oauth.py`, `backend/src/services/gitlab_sync.py`, `backend/src/services/gitlab_webhook.py`
- Blocks: GitLab integration regressions will be invisible until production.

**No per-workspace LLM cost tracking:**
- Problem: `generation_tokens_used` is stored on the `context_page` record, but there is no aggregation, alerting, or billing guard. A single workspace could generate unlimited context pages consuming unbounded LLM tokens.
- Files: `backend/src/models/context_page.py`, `backend/src/services/synthesis.py:277`
- Blocks: Cost runaway is undetectable without querying each context page individually.

---

## Test Coverage Gaps

**GitLab integration services:**
- What's not tested: OAuth flow, token refresh, MR sync, webhook event routing, MR-to-ticket linking for GitLab.
- Files: `backend/src/services/gitlab_oauth.py`, `backend/src/services/gitlab_sync.py`, `backend/src/services/gitlab_webhook.py`, `backend/src/services/gitlab_linking.py`
- Risk: Regressions in GitLab sync go undetected.
- Priority: High (recently added, production-facing)

**SSE stream error paths (LLM failure, DB failure during generation):**
- What's not tested: What happens when `llm.generate()` raises an exception mid-stream, or when the DB session fails after the SSE stream has started. The `status="generating"` stuck-state bug is in this untested path.
- Files: `backend/src/services/synthesis.py:498-500`, `backend/tests/test_synthesis_stream.py`
- Risk: LLM quota errors leave context pages permanently stuck in `"generating"` status.
- Priority: High

**Frontend API client token expiry behavior:**
- What's not tested: `apiFetch` and `apiFetchSSE` both call `supabase.auth.getSession()` to get the token. If the session is expired or null, `accessToken` silently becomes `""` and the request is sent with `Authorization: Bearer ` (empty), resulting in a 401 that is not specially handled.
- Files: `apps/web/src/lib/api.ts:27-29`, `apps/web/src/lib/api.ts:597-600`
- Risk: Silent 401 errors appear to the user as generic API errors with no prompt to re-authenticate.
- Priority: Medium

**Realtime hook under React StrictMode / unmount races:**
- What's not tested: The `useContextPagesRealtime` hook is not tested. Supabase realtime channel cleanup under React StrictMode (double-invoke of effects) is not verified.
- Files: `apps/web/src/hooks/use-context-pages-realtime.ts`
- Risk: Duplicate realtime subscriptions or missing cleanup leads to stale event callbacks.
- Priority: Medium

**Telegram integration end-to-end webhook processing:**
- What's not tested: The synchronous webhook processing path (currently forced sync for debugging — see TODOs) has no integration tests verifying message persistence, de-duplication, or error rollback.
- Files: `backend/src/routers/telegram.py:98-99`, `backend/src/services/telegram_events.py`
- Risk: Silent message loss or duplicate message storage on re-delivery.
- Priority: Medium

---

## UI/UX Issues

**`window.confirm()` used for disconnect confirmation:**
- Issue: The integration card disconnect flow uses the browser's native `window.confirm()` dialog, which is unstyled, cannot be customized, and is blocked in some browser contexts (iframes, certain security policies).
- Files: `apps/web/src/app/dashboard/integrations/integration-card.tsx:96-99`
- Impact: Inconsistent UX; blocked in embedded contexts.
- Fix approach: Replace with the existing `AlertDialog` component already imported in `settings/page.tsx`.

**Settings page is a 1,018-line monolith:**
- Issue: `apps/web/src/app/dashboard/settings/page.tsx` is a 1,018-line file containing all tab content (General, API Keys, Team, Integrations) inline.
- Files: `apps/web/src/app/dashboard/settings/page.tsx`
- Impact: Hard to maintain; slow to parse for readers; adding new settings sections compounds the issue.
- Fix approach: Extract each tab into its own component file, e.g., `settings/tabs/GeneralTab.tsx`, `settings/tabs/ApiKeysTab.tsx`.

**Context generation page does not surface the full error message from the backend:**
- Issue: When context generation fails, the `errorMessage` shown in `GenerationProgress` comes from the SSE `{"event": "error", "message": "..."}` payload, which includes raw Python exception text (e.g., "Ticket CON-99 not found"). This exposes internal implementation details to users.
- Files: `apps/web/src/components/generation-progress.tsx:196-199`, `backend/src/services/synthesis.py:499`
- Impact: Users see Python stack trace-like messages; poor UX; potential security-adjacent info leakage.
- Fix approach: Map known error types to user-friendly messages in the SSE event handler.

**`eslint-disable react-hooks/exhaustive-deps` comments indicate stale closure risks:**
- Issue: Four places suppress exhaustive-deps warnings by disabling the ESLint rule, indicating potential stale closure bugs where hooks capture outdated values.
- Files: `apps/web/src/hooks/use-context-pages-realtime.ts:61`, `apps/web/src/app/dashboard/activity/activity-timeline.tsx:147`, `apps/web/src/app/dashboard/settings/page.tsx:688`, `apps/web/src/app/dashboard/context/generate/page.tsx:139`
- Impact: Each suppression is a potential bug that may surface as missed re-renders or outdated data being used after state changes.
- Fix approach: Audit each suppression individually; prefer using `useCallback` with correct deps or `useRef` for stable callbacks.

---

*Concerns audit: 2026-03-12*
