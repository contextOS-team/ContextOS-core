# Pitfalls Research

**Domain:** AI-powered developer context synthesis platform (Linear + Slack + LLM integration)
**Researched:** 2026-02-24
**Confidence:** HIGH (verified across official docs, multiple credible sources, and community post-mortems)

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or multi-day debugging sessions.

### Pitfall 1: OAuth Token Refresh Race Conditions

**What goes wrong:**
Linear's new OAuth apps (created after Oct 1, 2025) have short-lived access tokens (24 hours) with mandatory refresh tokens. When multiple concurrent requests detect an expired token simultaneously, they all attempt to refresh it. The first refresh succeeds, but subsequent attempts use the now-invalidated refresh token, getting `invalid_grant` errors. The last write wins, potentially overwriting the valid new refresh token with a stale one. Result: the integration silently breaks and requires the user to re-authenticate.

**Why it happens:**
Developers build the "happy path" -- single-request token refresh -- and never test concurrent access patterns. With ContextOS pulling Linear data from webhook handlers, background synthesis tasks, and user-initiated refreshes simultaneously, concurrent refresh attempts are inevitable, not edge cases.

**How to avoid:**
Implement a token refresh lock per-integration using Redis `SET NX` with a 30-second TTL. When a request detects an expired token: (1) attempt to acquire the lock, (2) if acquired, refresh and store new tokens, (3) if not acquired, wait for the lock holder to complete and use the new token. Cache valid tokens for 1-2 minutes to reduce lock contention. On any 401 response, invalidate the cache and retry once with a fresh token.

**Warning signs:**
- Intermittent "invalid_grant" or "access token invalid" errors in logs
- Users randomly getting disconnected from Linear integration
- Errors that only appear under load, never in development

**Phase to address:**
OAuth integration phase (Linear OAuth flow). Must be designed correctly from the start -- retrofitting token locking onto a working OAuth flow is painful because the token storage layer needs to be lock-aware.

---

### Pitfall 2: Slack Bot Token vs User Token Scope Confusion

**What goes wrong:**
Slack OAuth v2 returns TWO different tokens in a single auth response: a bot token (`xoxb-`) in the top-level `access_token` field and a user token (`xoxp-`) nested in the `authed_user` object. Developers store the bot token and ignore the user token, then discover that certain operations (reading DMs, accessing user-specific channels, impersonating users) require the user token. Or worse: they request `user_scope` parameters but store only `bot_scope` tokens, silently losing access they thought they had.

Additionally, event subscriptions behave differently depending on which token type initialized the app. Using only the bot token means you miss events that require user token scopes, and vice versa.

**Why it happens:**
Slack's dual-token model in OAuth v2 is unusual. Most OAuth providers return one token. The separate `scope` vs `user_scope` parameters in the authorization URL are easy to confuse, and the response JSON structure nests user credentials in a way that's easy to overlook.

**How to avoid:**
Design the OAuth callback handler to explicitly extract and store BOTH tokens from the response. Map each token to its purpose:
- Bot token (`xoxb-`): channel messages, posting, reactions, bot-level actions
- User token (`xoxp-`): only if you need user-impersonation (likely not needed for ContextOS v1)

For ContextOS, the bot token is sufficient for reading `message.channels` and `message.groups` events. Only request `user_scope` if you specifically need user-level access. Document which scopes map to which token in the codebase.

**Warning signs:**
- "missing_scope" errors when calling Slack API methods
- Events not arriving that you expect based on your scope configuration
- OAuth flow succeeds but subsequent API calls fail with "not_authed"

**Phase to address:**
Slack OAuth integration phase. Get the scope design right in the OAuth authorization URL construction, and the callback handler's token extraction logic. Changing scopes later forces all users to re-authorize.

---

### Pitfall 3: Webhook Signature Verification Against Parsed Body (Not Raw Bytes)

**What goes wrong:**
Both Linear (HMAC-SHA256) and Slack (signing secret) compute signatures over the raw HTTP request body bytes. If FastAPI's JSON middleware parses the body before you read it, or if you verify the signature against `json.dumps(parsed_data)` instead of the original raw bytes, the signature will NEVER match. The JSON re-serialization changes key ordering, whitespace, and unicode escaping, producing different bytes than what the sender signed.

This is the #1 webhook integration bug and it's extremely frustrating to debug because everything looks correct -- you have the right secret, the right algorithm, the right header -- but verification always fails.

**Why it happens:**
FastAPI automatically parses JSON request bodies when you type-hint a parameter as a Pydantic model. By the time your handler runs, the raw bytes are gone. Developers then try to reconstruct the raw body from the parsed data, which produces different bytes.

**How to avoid:**
Read the raw request body BEFORE any JSON parsing:
```python
@app.post("/webhooks/linear")
async def linear_webhook(request: Request):
    raw_body = await request.body()  # Raw bytes - use this for HMAC
    signature = request.headers.get("Linear-Signature")
    if not verify_linear_signature(raw_body, signature, webhook_secret):
        raise HTTPException(status_code=401)
    payload = json.loads(raw_body)  # Parse AFTER verification
```
Never use Pydantic model injection for webhook endpoints. Always use `Request` directly.

For Slack specifically, also include the timestamp header in the signing base string: `v0:{timestamp}:{raw_body}`.

**Warning signs:**
- Webhook signature verification fails 100% of the time (not intermittently)
- Verification works in unit tests (where you control the raw body) but fails in production
- Switching to "skip verification" makes everything work (DO NOT ship this)

**Phase to address:**
Webhook listener phase (Linear webhooks, Slack events). This must be the FIRST thing implemented in every webhook endpoint. Template the pattern once and reuse it.

---

### Pitfall 4: Supabase RLS Performance Cliff with Unoptimized Policies

**What goes wrong:**
RLS policies execute per-row for every query. A policy like `auth.uid() IN (SELECT user_id FROM workspace_members WHERE workspace_id = table.workspace_id)` runs a subquery for every single row in the table, turning a 5ms query into an 11-second query on tables with a few thousand rows. This gets worse linearly with table size and is invisible during development with small datasets.

**Why it happens:**
RLS policies look like simple SQL but the Postgres optimizer treats them differently. Function calls like `auth.uid()` are re-evaluated per row unless wrapped in a `SELECT` subquery. Missing indexes on columns referenced in RLS policies (like `workspace_id`) cause full table scans inside the per-row policy evaluation.

**How to avoid:**
Three mandatory optimizations for every RLS policy:
1. **Wrap function calls in SELECT**: `(SELECT auth.uid()) = user_id` instead of `auth.uid() = user_id` -- enables the optimizer to cache the result
2. **Index all RLS-referenced columns**: Every column in a policy WHERE clause needs a btree index
3. **Invert join direction**: `workspace_id IN (SELECT workspace_id FROM workspace_members WHERE user_id = (SELECT auth.uid()))` is dramatically faster than the reverse because it resolves the fixed user first, then matches

Always test RLS performance with `EXPLAIN ANALYZE` using realistic data volumes (1000+ rows per table).

**Warning signs:**
- Queries that are fast in the SQL Editor (which bypasses RLS) but slow from the client SDK
- Dashboard pages that load slowly only when the database has real data
- Supabase dashboard showing high query times on simple SELECT operations

**Phase to address:**
Database schema phase. RLS policies must be written correctly from the start. Retrofitting optimized policies onto existing queries is possible but every policy needs audit. Establish the `(SELECT auth.uid())` wrapper pattern as a team convention from day one.

---

### Pitfall 5: LLM Synthesis Quality Collapse from Poor Context Assembly

**What goes wrong:**
The context synthesis prompt receives a dump of all gathered data -- Linear ticket details, Slack messages, related tickets -- and the LLM produces generic, unhelpful summaries. Engineers look at the generated context page and think "I could have gotten this from reading the ticket title." The AI-generated implementation prompt is too vague to be useful in Cursor/Claude Code. Users stop trusting the product within the first week.

This is the existential threat to ContextOS. The integrations are plumbing; the synthesis quality IS the product.

**Why it happens:**
Two root causes: (1) Retrieved context is noisy -- Slack messages include greetings, off-topic tangents, bot notifications mixed with actual technical decisions. Feeding everything to the LLM dilutes the signal. (2) The synthesis prompt doesn't specify the output structure tightly enough, or doesn't give the LLM enough guidance on what "good context" looks like for an engineering ticket.

Research shows that increasing retrieved passages doesn't consistently improve LLM output -- performance improves initially then DECLINES as noise increases. Hard negatives (retrieved content that looks relevant but isn't) actively degrade quality.

**How to avoid:**
- **Pre-filter aggressively**: Remove bot messages, join/leave notifications, single-emoji reactions, and messages under 10 characters before sending to the LLM
- **Structure the prompt with explicit sections**: Don't ask for "a summary" -- ask for exactly the 5 sections defined in the product spec (origin story, business requirements, technical decisions, related work, AI prompt) with specific instructions for each
- **Include few-shot examples**: Show the LLM what a GOOD context page looks like for a sample ticket
- **Separate data gathering from synthesis**: LangGraph for gathering (parallel API calls), single focused LLM call for synthesis. Don't let the agent decide what to retrieve -- deterministically gather everything, then synthesize
- **Token budget awareness**: Gemini Flash context windows are generous, but cramming 100 Slack messages into one prompt wastes tokens on noise. Limit to 20-30 most relevant messages

**Warning signs:**
- Context pages that read like generic summaries of the ticket title
- AI prompts that don't reference specific technical decisions from Slack/Notion
- Engineers not copying the AI prompt (the hero feature) -- track this
- Context pages that are almost identical for different tickets

**Phase to address:**
Context synthesis phase. Build the prompt engineering and context assembly pipeline with quality evaluation from the start. Create 3-5 "golden" test cases with known-good Slack threads and Linear tickets, and evaluate every prompt change against them.

---

### Pitfall 6: FastAPI Background Tasks Silently Losing Work

**What goes wrong:**
ContextOS uses FastAPI `BackgroundTasks` for synthesis jobs (the PROJECT.md explicitly chose this over Celery). Background tasks run in the same process as the web server. If the server restarts, crashes, or is redeployed during a synthesis job, the job is silently lost -- no error, no retry, no record that it was ever started. The webhook returns 200 (as it should for responsiveness), but the context page never gets generated.

On Railway (the chosen deployment platform), deploys trigger process restarts. During a 2-3 week sprint with frequent deploys, this means regularly losing in-flight synthesis jobs.

**Why it happens:**
FastAPI BackgroundTasks has no persistence, no status tracking, and no retry mechanism. It's designed for fire-and-forget tasks like sending emails, not for business-critical jobs that must complete. Developers choose it for simplicity (the PROJECT.md explicitly acknowledges this tradeoff) but underestimate how often servers restart in production.

**How to avoid:**
Accept this limitation for v1 but build a safety net:
1. **Track job status in the database**: Before starting a background task, insert a row with status `pending`. Update to `processing` when the task starts, `completed` when done, `failed` on error
2. **Build a sweep job**: A periodic task (even a simple cron endpoint) that finds `pending` or `processing` jobs older than 5 minutes and re-queues them
3. **Idempotent synthesis**: Ensure re-running synthesis for the same ticket is safe (overwrite, don't duplicate)
4. **Return the job ID**: Webhook handlers should return 200 immediately but also create a trackable job, so the dashboard can show "generation in progress" vs "generation failed"

This gives you 80% of Celery's reliability with 10% of the complexity. Migrate to a proper job queue (Celery or arq) in v2 if the sweep job fires frequently.

**Warning signs:**
- Context pages that never appear after ticket assignment
- Dashboard showing "generating..." indefinitely
- Users manually regenerating context that should have been auto-generated
- Gaps in context generation that correlate with deploy times

**Phase to address:**
Context synthesis phase, but the job tracking table should be in the database schema phase. The schema needs a `context_generation_jobs` table from the start.

---

### Pitfall 7: Slack Rate Limit Cliff for Non-Marketplace Apps

**What goes wrong:**
As of May 2025, Slack dramatically reduced rate limits for commercially distributed apps not on the Slack Marketplace. `conversations.history` and `conversations.replies` dropped from Tier 3 (50+ RPM) to Tier 1 (1 RPM) with only 15 objects per request. If ContextOS is classified as "commercially distributed" but not on the Marketplace, initial data sync or intensive Slack message retrieval becomes essentially impossible -- fetching 100 messages from a channel would take 7+ minutes.

Even for internal apps (which retain Tier 3 limits), `chat.postMessage` is limited to 1 message per second per channel, and exceeding this causes HTTP 429 errors with potential app disconnection.

**Why it happens:**
Slack made these changes to push apps toward the Marketplace and prevent bulk data exfiltration. The distinction between "internal" and "commercially distributed" apps is subtle, and developers often don't realize which category their app falls into until they hit the limits.

**How to avoid:**
- **Register as an internal app** during v1 dogfooding -- this retains Tier 3 limits (50+ RPM). ContextOS is being used by the founding team, so this is accurate
- **Design for rate limits from day one**: Implement exponential backoff with jitter on all Slack API calls, respect the `Retry-After` header
- **Cache aggressively**: Store Slack messages in Supabase after retrieval. Never re-fetch messages you already have
- **Prefer real-time events over polling**: The Events API delivers messages as they happen, no API calls needed. Only use `conversations.history` for backfill (which is deferred to v2 anyway)
- **Plan Marketplace submission** before commercial distribution

**Warning signs:**
- HTTP 429 responses from Slack API
- Initial sync jobs taking 10x longer than expected
- Slack threatening to disable the app via email

**Phase to address:**
Slack integration phase. The rate limit handling must be built into the Slack API client wrapper from the first line of code. Don't add it later.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skipping webhook idempotency (no dedup by event ID) | Faster webhook handler development | Duplicate context regeneration, wasted LLM tokens, confusing Linear comments | Never -- Linear retries up to 3x, Slack retries 3x. You WILL get duplicates |
| Storing OAuth tokens in plain columns instead of Vault | Simpler SQL queries for token access | Tokens visible in backups, logs, and Supabase dashboard to anyone with DB access | Only in local dev. Production must use Vault |
| Hardcoding Gemini model name (`gemini-2.0-flash`) | Works today | Google renames/deprecates models without warning (Dec 2025 quota changes had no announcement). Deployment breaks | Never -- use environment variable for model name |
| No embedding model version tracking | Simpler embedding table schema | When you switch embedding models, old and new embeddings are incompatible. Search quality degrades silently | Only if you're certain you'll never change models (you will) |
| Using Supabase Auth external providers for OAuth | Quick setup via config.toml | Supabase Auth providers handle user-login OAuth, not service-integration OAuth. Linear/Slack OAuth for data access requires custom flows | Never for ContextOS -- the config.toml already has `[auth.external.linear]` which is WRONG for this use case |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Linear OAuth | Using Supabase Auth's built-in Linear provider for data-access OAuth | Supabase Auth's external providers are for user login, not API integration. Build a custom OAuth2 flow in Python that stores workspace-level tokens separately |
| Linear Webhooks | Not validating `webhookTimestamp` (only checking HMAC) | Verify both the HMAC-SHA256 signature AND that `webhookTimestamp` is within 60 seconds of current time to prevent replay attacks |
| Linear API | Ignoring GraphQL pagination, assuming all results fit in one response | Linear's GraphQL API paginates by default. Always check `pageInfo.hasNextPage` and use cursor-based pagination |
| Slack OAuth | Requesting bot scopes via `user_scope` parameter (or vice versa) | Bot scopes go in `scope=`, user scopes in `user_scope=`. The parameters have different token implications |
| Slack Events | Processing events synchronously before returning 200 | Return HTTP 200 within 3 seconds. Queue the event for background processing. Slack will retry (and you'll get duplicates) if you respond slowly |
| Slack Events | Not handling the `url_verification` challenge event | First event Slack sends is a challenge. Handler must respond with the challenge value. Test this FIRST |
| Gemini API | Relying on free tier for production | Google cut free tier limits by 92% in Dec 2025 with zero notice. Use paid Tier 1 (150-300 RPM) for any production workload |
| Supabase Vault | Inserting secrets via SQL statements (logged in Supabase logs) | Use the Vault UI or disable statement logging when inserting secrets programmatically. Raw SQL INSERT of tokens gets logged unencrypted |
| pgvector | Creating IVFFlat index before having data | IVFFlat builds clusters from existing data. An index built on 100 rows is useless for 10,000 rows. Use HNSW instead, or wait until you have representative data volume |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| RLS without indexed policy columns | Queries slow linearly with table size, 10x slower than expected | Index every column referenced in RLS policies. Use `EXPLAIN ANALYZE` | 1,000+ rows per table |
| Un-wrapped `auth.uid()` in RLS policies | Dashboard pages load in 5+ seconds | Wrap all function calls: `(SELECT auth.uid())` not `auth.uid()` | 500+ rows with RLS |
| Embedding search without pre-filtering | Vector search returns irrelevant results from other workspaces, or searches entire table | Always filter by `workspace_id` BEFORE vector similarity, not after. Use pgvector's `WHERE` clause | 10,000+ embeddings |
| Gemini Flash token-per-minute (TPM) exhaustion | 429 errors despite low request count | Large context windows (100K+ tokens per request) hit TPM limits at low RPM. Monitor token usage, not just request count | 50+ concurrent synthesis jobs, or prompts >50K tokens |
| Unbounded Slack message fetching | Synthesis jobs that take 30+ seconds, high Gemini costs | Cap Slack messages per context page (20-30 most relevant). Don't feed the LLM everything | Channels with 500+ messages mentioning a ticket keyword |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing OAuth tokens outside Supabase Vault | Tokens visible in database backups, Supabase dashboard logs, and to anyone with table access | Use Vault `vault.create_secret()` function. Access via decrypted view only in backend service role |
| Exposing Slack/Linear tokens to the frontend | Frontend JS can read tokens, enabling unauthorized API access | Tokens live ONLY in the Python backend. Frontend calls Python API, never touches integration tokens. RLS policies should block the `vault.decrypted_secrets` view from client roles |
| Not validating webhook source before processing | Attacker can forge webhooks to trigger context regeneration, wasting LLM tokens or injecting false data | Verify HMAC signature on EVERY webhook. No exceptions, no "skip in dev" flags that ship to prod |
| MCP API keys with no rate limiting | A misbehaving or compromised MCP client makes unlimited API calls, running up Gemini costs | Rate limit MCP API key usage (per key, per minute). Track usage in Redis |
| Logging raw OAuth tokens or webhook payloads | Tokens and sensitive data visible in Railway logs, Sentry breadcrumbs | Sanitize logs: redact any field matching `*token*`, `*secret*`, `*key*`. Configure Sentry `before_send` to strip sensitive data |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress indicator during context generation | User assigns ticket, nothing happens for 10-30 seconds. They wonder if the integration is broken | Show "Generating context..." status in dashboard immediately. Use Supabase realtime to update when synthesis completes |
| Context page shows stale data after ticket update | Engineer reads context, starts coding, doesn't realize the ticket was updated 5 minutes ago | Show "Last generated: X minutes ago" prominently. Auto-regenerate when ticket is updated (not just on assignment) |
| AI prompt is too generic to be useful | Engineer copies prompt into Cursor, gets unhelpful output. Stops using the feature entirely | Include specific file paths, function names, API endpoints from technical decisions. Reference actual Slack discussion points, not summaries of summaries |
| Slack linking misses relevant threads | Context page says "no Slack context found" when there's a whole thread discussing the feature | Start with explicit link detection (Linear ticket URLs in Slack) + keyword matching against ticket title/identifier. Show "X Slack threads found" count so users can verify |
| OAuth disconnect with no clear re-auth path | Integration breaks silently. Dashboard shows stale data without explaining why | Show integration health status on the dashboard. If a token refresh fails, immediately show "Reconnect Linear" banner with one-click re-auth |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **OAuth flow:** Token refresh works -- verify that refresh tokens are stored AND that the refresh flow handles concurrent requests safely (test with 3 simultaneous requests to an expired token)
- [ ] **Webhook handler:** Idempotency works -- send the same webhook payload twice and verify only one synthesis job runs (check the dedup table/cache)
- [ ] **RLS policies:** Performance is acceptable -- run `EXPLAIN ANALYZE` on key queries with 1000+ rows and RLS enabled. Query time should be under 100ms
- [ ] **Context synthesis:** Output quality is evaluated -- don't just check that it runs. Read 5 generated context pages and rate them honestly. Would you use this AI prompt in Cursor?
- [ ] **Slack event handling:** URL verification challenge works -- Slack sends this on first subscription setup. If it fails, no events will ever arrive
- [ ] **Linear webhook:** Signature verification uses raw bytes -- test with a real Linear webhook, not a hand-crafted test payload
- [ ] **Error handling:** Failed synthesis doesn't leave ghost jobs -- verify that a crashed synthesis job gets detected and retried by the sweep mechanism
- [ ] **Supabase Vault:** Tokens are actually encrypted -- query `vault.secrets` (encrypted) vs `vault.decrypted_secrets` (decrypted view) to confirm encryption is working
- [ ] **Gemini API:** Model name is configurable -- verify the model name comes from an environment variable, not a hardcoded string
- [ ] **Rate limiting:** Slack API client has backoff logic -- trigger a 429 response and verify the client waits and retries (mock the response in tests)

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| OAuth tokens lost/corrupted | LOW | Users re-authorize via dashboard. One-click flow if OAuth app is still registered. No data loss, just a re-auth |
| Webhook dedup missing (duplicate context pages) | LOW | Add dedup table, run migration, deduplicate existing pages by keeping the most recent per ticket |
| RLS performance is terrible | MEDIUM | Add indexes, wrap function calls in SELECT, re-test. Requires migration but no schema redesign |
| Synthesis quality is poor | MEDIUM | Iterative prompt engineering. Add pre-filtering. Create golden test cases. Does NOT require architecture changes |
| Background tasks losing jobs | MEDIUM | Add job tracking table (migration), implement sweep endpoint, backfill any missing context pages |
| Wrong OAuth model (using Supabase Auth providers for integration OAuth) | HIGH | Requires rewriting the entire OAuth flow, new token storage, migration of existing tokens. This is a multi-day rewrite |
| Embedding model change without versioning | HIGH | Must re-embed ALL existing data. If you have 10,000 embeddings, this takes significant time and API cost. Mark old embeddings as stale, re-process in background |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| OAuth token refresh race condition | OAuth integration (Linear + Slack) | Test 3 concurrent requests with an expired token. All should succeed without `invalid_grant` |
| Slack bot vs user token confusion | Slack OAuth integration | Verify both token types are properly extracted (or only bot token if user token not needed). Test API calls with the stored token |
| Webhook signature on raw bytes | Webhook listeners (Linear + Slack) | Send a real webhook from Linear/Slack. Verification passes. Then tamper with one byte of the payload -- verification fails |
| RLS performance cliff | Database schema + RLS policies | `EXPLAIN ANALYZE` on every RLS-protected table with 1000+ rows. All queries under 100ms |
| LLM synthesis quality collapse | Context synthesis pipeline | 5 golden test cases evaluated by a human. AI prompts are specific enough to use in Cursor |
| Background tasks losing work | Context synthesis + job tracking | Deploy during active synthesis. Verify job recovers after deploy completes (sweep job picks it up) |
| Slack rate limit cliff | Slack API client wrapper | Run Slack API calls in a loop. Verify 429 responses trigger backoff. Verify cached messages avoid re-fetch |
| Supabase Auth provider misuse for integration OAuth | OAuth integration | Verify Linear/Slack OAuth uses custom Python flow, NOT `[auth.external.linear]` from Supabase config |
| Webhook idempotency missing | Webhook listeners | Send identical webhook payload 3 times. Verify only 1 synthesis job is created |
| Gemini model hardcoding | Context synthesis | Change model name in env var. Verify synthesis uses the new model without code changes |

---

## Sources

- [Linear OAuth 2.0 Authentication Docs](https://linear.app/developers/oauth-2-0-authentication) -- Refresh token migration timeline, 24h token expiry (HIGH confidence)
- [Linear Webhooks Docs](https://linear.app/developers/webhooks) -- HMAC-SHA256 signing, 5s timeout, 3 retries (HIGH confidence)
- [Slack Rate Limits Docs](https://docs.slack.dev/apis/web-api/rate-limits/) -- Tier system, 429 handling (HIGH confidence)
- [Slack Rate Limit Changes for Non-Marketplace Apps](https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps/) -- conversations.history dropped to 1 RPM (HIGH confidence)
- [Slack Token Types](https://docs.slack.dev/authentication/tokens/) -- Bot vs user token differences (HIGH confidence)
- [Slack Events API: HTTP vs Socket Mode](https://docs.slack.dev/apis/events-api/comparing-http-socket-mode/) -- HTTP recommended for production (HIGH confidence)
- [Supabase RLS Performance and Best Practices](https://supabase.com/docs/guides/troubleshooting/rls-performance-and-best-practices-Z5Jjwv) -- SELECT wrapper, index strategies (HIGH confidence)
- [Supabase Vault Docs](https://supabase.com/docs/guides/database/vault) -- Statement logging leak, access control (HIGH confidence)
- [Nango: Concurrency with OAuth Token Refreshes](https://nango.dev/blog/concurrency-with-oauth-token-refreshes) -- Redis lock pattern, race condition solutions (MEDIUM confidence)
- [Nango: Why is OAuth still hard in 2026?](https://nango.dev/blog/why-is-oauth-still-hard) -- Ecosystem-wide OAuth pitfalls (MEDIUM confidence)
- [FastAPI Background Tasks vs Celery](https://medium.com/@komalbaparmar007/fastapi-background-tasks-vs-celery-vs-arq-picking-the-right-asynchronous-workhorse-b6e0478ecf4a) -- No persistence, no retry, same-process (MEDIUM confidence)
- [Gemini API Rate Limits 2026 Guide](https://blog.laozhang.ai/en/posts/gemini-api-rate-limits-guide) -- Free tier 92% reduction, TPM considerations (MEDIUM confidence)
- [Six Lessons Learned Building RAG Systems in Production](https://towardsdatascience.com/six-lessons-learned-building-rag-systems-in-production/) -- Context quality > quantity, hard negatives (MEDIUM confidence)
- [pgvector 2026 Guide](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/) -- Scaling limits, index rebuild requirements (MEDIUM confidence)
- [LangGraph Limitations 2025 Discussion](https://community.latenode.com/t/current-limitations-of-langchain-and-langgraph-frameworks-in-2025/30994) -- Production gaps, observability needs (LOW confidence -- community forum)

---
*Pitfalls research for: ContextOS -- AI-powered developer context synthesis platform*
*Researched: 2026-02-24*
