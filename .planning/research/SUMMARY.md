# Project Research Summary

**Project:** ContextOS
**Domain:** AI-powered developer context synthesis platform (Linear + Slack + MCP)
**Researched:** 2026-02-24
**Confidence:** HIGH

## Executive Summary

ContextOS is an AI context layer for engineering teams that automatically synthesizes structured context pages from Linear tickets, Slack conversations, and future integrations. The product's core value is turning fragmented signals (Linear ticket history, related Slack threads, past decisions) into a single structured artifact — a 5-section context page — that gets delivered where engineers actually work: as a Linear comment, through a web dashboard, and via an MCP server into Cursor/Claude Code. No competitor does exactly this. The closest adjacents (Unblocked, Notion AI Connectors, Greptile) do multi-source search or ticket enrichment, but none generate a structured narrative with a ready-to-paste AI implementation prompt.

The recommended approach is a gather-then-synthesize pipeline: LangGraph orchestrates deterministic parallel data gathering (Linear ticket data, related Slack threads, embedding search), then a single Gemini Flash call synthesizes the context page from the assembled inputs. The stack is fully pre-selected and scaffolded — Next.js 15 + FastAPI + Supabase + MCP TypeScript SDK — with the primary dependency changes being swapping `anthropic` for `google-genai`, removing `llama-index` in favor of direct `httpx` + `slack-bolt` API calls, and removing `celery` in favor of FastAPI BackgroundTasks with a database-tracked job system.

The key risks are tightly coupled: synthesis quality is the existential risk (generic output = users stop trusting it within days), and data pipeline reliability is the enabling risk (Slack rate limits, OAuth token race conditions, and webhook idempotency issues can silently degrade the context quality the synthesis depends on). Both must be designed correctly from the first phase, not retrofitted. The architecture is well-understood and follows established patterns throughout; the hard problems are prompt engineering, pre-filtering noisy Slack data, and building the Slack-to-ticket linking logic that connects raw messages to specific tickets.

## Key Findings

### Recommended Stack

The stack is already selected and scaffolded. Research validates all choices and identifies specific corrections to `pyproject.toml`. The critical changes: replace `anthropic` with `google-genai>=1.64.0` (Gemini Flash is the team's choice, ~$0.15/1M tokens), remove `llama-index` and its readers in favor of direct `httpx` + `slack-bolt` API calls (LlamaIndex adds 50+ transitive deps for what is essentially pagination wrappers), and remove `celery[redis]` in favor of FastAPI BackgroundTasks plus a database-tracked job sweep pattern. Gemini `gemini-embedding-001` at 768 dimensions is free via AI Studio and uses the same SDK as synthesis — zero additional cost for embeddings.

**Core technologies:**
- **Next.js 15 + React 19**: Web dashboard — Server Components for Supabase reads, Turbopack for dev speed, Vercel-native deployment
- **FastAPI + uvicorn**: Backend API, webhook handlers, OAuth flows — async-native, auto OpenAPI docs
- **Supabase (PostgreSQL + pgvector + Auth + Vault + Realtime)**: Single platform replaces 4+ services — auth, DB with RLS multi-tenancy, vector embeddings, real-time subscriptions, encrypted token storage
- **Gemini Flash (gemini-2.5-flash)**: LLM synthesis engine — cheapest fast model, $0.15/1M tokens, team decision
- **LangGraph**: Data gathering orchestration — stateful parallel graph for the gather-then-synthesize pipeline
- **MCP TypeScript SDK ^1.27.0**: IDE integration delivery — stdio transport, thin client calling Railway backend
- **slack-bolt + slack-sdk**: Slack event handling + API — official framework with built-in verification and rate limiting

**Critical pyproject.toml changes:** Remove `anthropic`, `llama-index`, `llama-index-readers-slack`, `llama-index-readers-notion`, `celery[redis]`. Add `google-genai>=1.64.0`, `slack-bolt>=1.27.0`. Change `lmnr` to `lmnr[all]`.

### Expected Features

No competitor auto-generates structured multi-section context pages from across Linear + Slack with a ready-to-paste AI implementation prompt. This is the white space ContextOS fills. Linear AI does ticket enrichment but stays Linear-only. Unblocked does multi-source search but not structured synthesis. Nobody delivers structured ticket context via MCP to IDEs.

**Must have (table stakes):**
- Linear OAuth + webhook-driven ticket sync — the entire pipeline depends on this
- Slack OAuth + Events API ingestion — context pages without Slack context are thin
- Slack-to-ticket linking (explicit URLs + keyword matching + thread following) — highest-complexity table-stakes feature
- Context page generation with 5 sections (origin, business requirements, technical decisions, related work, AI prompt) — the core product
- Web dashboard: feed + detail view + copy AI prompt button — primary consumption UI
- Linear comment bot auto-posting on assignment — in-workflow delivery, no context switching
- MCP server with 3 tools (get_feature_context, search_context, get_related_work) — IDE delivery for power users
- Source attribution with links back to original Slack messages and Linear comments — essential for trust
- Integration setup page + manual regeneration + API key generation

**Should have (differentiators, post-launch):**
- Staleness detection + auto-regeneration — trust signal when tickets get updated
- Related work discovery via keyword/label matching — surface connections between tickets
- Thread deep-following — extract more signal from Slack decision threads
- Webhook retry logic + dead letter queue — reliability when synthesis jobs fail
- Sentry + Laminar observability — essential for debugging synthesis quality

**Defer to v2+:**
- Notion integration — defer until Linear + Slack quality is validated
- Semantic Slack linking via embeddings — measure keyword matching miss rate first
- Slack historical backfill — real-time ingestion first
- Usage analytics (PostHog), team management, GitHub PR integration
- Chat/Q&A interface — MCP server serves this need better

**Explicit anti-features (do not build):**
- Collaborative editing of context pages (defeats the auto-generation purpose)
- Custom section templates (premature abstraction before 50+ user validation)
- Bidirectional sync with Linear (ContextOS is read-synthesize-deliver, not an editor)

### Architecture Approach

The architecture follows a split read/write pattern: Next.js reads directly from Supabase (instant, RLS-filtered, real-time subscriptions), while all writes and business logic go through FastAPI. The central processing flow is: webhook event → verify/ACK → BackgroundTask → LangGraph gather pipeline (parallel: fetch ticket, find Slack threads, search embeddings) → single Gemini Flash synthesis call → write context_pages → Supabase Realtime pushes update to dashboard. The MCP server is a thin HTTP client running locally via stdio, all business logic stays on Railway. Supabase Vault encrypts all OAuth tokens at rest; RLS enforces workspace-scoped multi-tenancy at the database level.

**Major components:**
1. **FastAPI Backend** — webhook handlers, OAuth flows, context generation orchestration, MCP API endpoints
2. **LangGraph Pipeline** — deterministic parallel data gathering (not a multi-turn agent — only the final synthesis node calls the LLM)
3. **Gemini Flash Synthesis** — single structured call with tight prompt defining all 5 sections; quality here IS the product
4. **Supabase** — data layer, auth, RLS multi-tenancy, encrypted token storage (Vault), real-time status updates
5. **Next.js Dashboard** — direct Supabase reads, real-time subscriptions, FastAPI calls for actions
6. **MCP Server** — thin stdio-to-HTTP client; no business logic, no database access, no credentials

### Critical Pitfalls

1. **Webhook signature verification against raw bytes (not parsed body)** — FastAPI parses JSON before your handler runs; verify HMAC against `await request.body()` and parse AFTER. Never use Pydantic model injection for webhook endpoints. Verification fails 100% of the time if you re-serialize the parsed data.

2. **OAuth token refresh race conditions** — Linear tokens expire in 24 hours; concurrent requests all detect expiry simultaneously and corrupt each other's refresh tokens. Implement Redis `SET NX` lock per-integration with 30s TTL; cache valid tokens for 1-2 minutes to reduce contention.

3. **LLM synthesis quality collapse from noisy context** — feeding raw Slack dumps to Gemini produces generic summaries. Pre-filter bot messages, join notifications, and messages under 10 chars. Cap at 20-30 most relevant messages. Use few-shot examples in the prompt. Create 5 golden test cases and evaluate every prompt change against them.

4. **FastAPI BackgroundTasks silently losing work on deploy** — Railway deploys restart the process, silently dropping in-flight synthesis jobs. Track every job in a `context_generation_jobs` DB table (status: pending → processing → completed/failed). Build a sweep endpoint that re-queues jobs stuck in processing for 5+ minutes.

5. **Supabase RLS performance cliff** — policies with unoptimized function calls cause 5-11 second queries at 500+ rows. Always wrap: `(SELECT auth.uid())` not `auth.uid()`. Index every column referenced in RLS policies. Test with `EXPLAIN ANALYZE` at 1000+ rows.

6. **Slack rate limits for non-Marketplace apps** — as of May 2025, `conversations.history` dropped to 1 RPM for commercially distributed non-Marketplace apps. Register as internal app during dogfooding. Cache all fetched messages. Prefer real-time Events API over polling.

7. **Supabase Auth provider misuse for integration OAuth** — `[auth.external.linear]` in `config.toml` handles user login, not API integration. Linear/Slack OAuth for data access requires a custom Python OAuth2 flow storing workspace-level tokens separately in Vault. Using the wrong model requires a multi-day rewrite.

## Implications for Roadmap

The build order has clear dependencies that dictate phase structure. Linear is the primary data source (tickets are the unit of work), so it comes before Slack. Context generation is the central node everything else depends on, so it must work before the UI or MCP server. Research suggests 6 phases.

### Phase 1: Foundation and Auth
**Rationale:** Everything depends on auth working correctly. The database schema (already drafted) and RLS policies must be optimized from day one — retrofitting is painful. Establish the project skeleton and Supabase auth flow before touching integrations.
**Delivers:** Auth-gated dashboard shell, optimized DB schema with RLS, FastAPI skeleton with health endpoint, local Supabase working
**Addresses:** User auth flow, integration setup page foundations
**Avoids:** RLS performance cliff (set up indexes and SELECT wrappers now), Supabase Auth provider misuse (establish custom OAuth pattern before any OAuth code is written)

### Phase 2: Linear Integration and Data Pipeline
**Rationale:** Linear is the critical path — without ticket data, nothing can be generated. OAuth, webhook handling, and initial sync must all work before synthesis is possible. The webhook idempotency and signature verification patterns established here are reused for Slack.
**Delivers:** Linear OAuth + token storage in Vault, webhook listener with HMAC verification on raw bytes, ticket sync and ingestion, embedding generation service
**Addresses:** Linear OAuth table-stakes feature, webhook-driven updates
**Avoids:** OAuth token refresh race conditions (implement Redis lock here), webhook signature verification bug (template the raw-bytes pattern), webhook idempotency (implement dedup table now)

### Phase 3: Context Generation Core
**Rationale:** This is the heart of the product. The LangGraph gather pipeline and Gemini Flash synthesis must be built with quality evaluation from day one — not "make it run, improve quality later." The job tracking table belongs in Phase 1 schema but the synthesis logic lives here.
**Delivers:** LangGraph gather-then-synthesize pipeline, Gemini Flash 5-section context page output, auto-trigger on ticket assignment, job status tracking, context pages in the database
**Addresses:** Context page generation (table stakes), AI implementation prompt (hero differentiator), source attribution
**Avoids:** Synthesis quality collapse (pre-filtering, tight prompt structure, few-shot examples, 5 golden test cases), BackgroundTasks silent job loss (job tracking + sweep endpoint)

### Phase 4: Web Dashboard and Linear Comment Bot
**Rationale:** Once context pages exist in the database, the UI and comment bot are straightforward. Supabase Realtime enables live status updates without polling. The comment bot is a small addition once the pipeline works.
**Delivers:** Context pages feed, detail view, copy AI prompt button, Supabase Realtime status updates, manual regeneration, Linear comment auto-posting on assignment
**Addresses:** Web dashboard (table stakes), copy AI prompt (P1), Linear comment bot (differentiator), integration setup page
**Avoids:** Polling anti-pattern (use Supabase Realtime), no progress indicator UX pitfall

### Phase 5: MCP Server
**Rationale:** The MCP server is a thin client over already-existing backend endpoints. It can be built in parallel with Phase 4 once Phase 3 is complete. API key generation and auth is the new concern here.
**Delivers:** MCP server with get_feature_context, search_context, get_related_work tools, API key generation and validation, rate limiting per API key
**Addresses:** MCP server delivery (differentiator), API key generation (P1)
**Avoids:** MCP API key abuse (rate limit per key in Redis)

### Phase 6: Slack Integration and Full Context
**Rationale:** Slack is complex (dual tokens, rate limits, event verification, Slack-to-ticket linking is the hardest table-stakes feature) and can start after the Linear + synthesis pipeline is proven. Adding Slack context to already-working context pages is additive, not blocking.
**Delivers:** Slack OAuth + bot token storage, Events API ingestion, Slack-to-ticket linking (explicit URL detection + keyword matching + thread following), Slack message embedding, full context pages with Slack context
**Addresses:** Slack OAuth + event ingestion (table stakes), Slack-to-ticket linking (high-complexity P1), conversation thread following (differentiator)
**Avoids:** Slack bot vs user token confusion (extract only bot token, document why), Slack rate limit cliff (internal app registration, exponential backoff client, cache all fetched messages), Slack URL verification challenge (test this first)

### Phase Ordering Rationale

- Linear before Slack: tickets are the unit of work; everything flows from ticket data being present
- Context generation before UI: building UI against real generated data produces better UX decisions; building against mock data wastes iteration cycles
- MCP after context generation but can parallel with Phase 4: MCP is purely additive over existing API endpoints
- Slack last: it is the most complex integration but additive; the core loop (Linear + synthesis) can be dogfooded without it
- Schema and RLS in Phase 1, not deferred: RLS performance and OAuth model decisions are the two highest-recovery-cost pitfalls if gotten wrong

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Context Generation):** Prompt engineering for the 5-section synthesis is not documented — it must be developed empirically. Gemini Flash structured output schema design, few-shot example quality, and pre-filtering strategy all need iteration. Plan for prompt engineering as first-class work, not an afterthought.
- **Phase 6 (Slack Integration):** Slack-to-ticket linking logic (keyword matching heuristics, thread following depth, disambiguation when multiple tickets match) is novel — no established pattern. Budget extra time here.
- **Phase 2 (Linear OAuth):** Linear's new short-lived token (24h) + refresh flow with race condition handling is well-documented in pitfalls but the Redis lock pattern needs careful implementation. Single source of truth for token locking.

Phases with standard patterns (research phase likely unnecessary):
- **Phase 1 (Foundation):** Supabase + Next.js + FastAPI auth integration is well-documented with official examples. RLS patterns are documented.
- **Phase 4 (Web Dashboard):** Next.js App Router + Supabase Realtime + shadcn/ui is a well-traveled path with official guides.
- **Phase 5 (MCP Server):** MCP TypeScript SDK is straightforward; the server is explicitly thin-client, minimal logic.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies pre-selected and scaffolded. Research validates choices and identifies specific corrections (pyproject.toml diff is clear). Version compatibility matrix verified against PyPI and npm. |
| Features | MEDIUM-HIGH | Competitive landscape analysis is strong. Table stakes and differentiators are clear. Slack-to-ticket linking complexity acknowledged but specific heuristics need empirical validation. |
| Architecture | HIGH | Standard patterns throughout. LangGraph gather-then-synthesize pipeline is well-precedented. Supabase RLS + Vault patterns verified against official docs. All 5 architectural patterns have concrete code examples. |
| Pitfalls | HIGH | Most pitfalls verified against official docs or post-mortems. OAuth race condition and RLS performance cliff are industry-acknowledged. Slack rate limit changes from May 2025 are documented in official Slack changelog. |

**Overall confidence:** HIGH

### Gaps to Address

- **Embedding model decision:** Marked as "Dulat decides" in STACK.md. Gemini `gemini-embedding-001` (free, 768 dims) is the recommended default. Validate embedding quality on actual Linear ticket + Slack message pairs before committing. This is a config change, not an architecture change, so low risk to defer the final decision.
- **Synthesis prompt quality:** Cannot be pre-researched — must be developed against real ContextOS data. Create 5 golden test cases (real Linear tickets with real Slack threads) in Phase 3 before considering synthesis "done." Track "AI prompt copy rate" as the primary quality signal.
- **Slack classification (internal vs commercially distributed):** During dogfooding, register as internal app to retain Tier 3 rate limits. Marketplace submission path must be planned before any commercial distribution.
- **pgvector index strategy:** ARCHITECTURE.md notes HNSW for initial data, possible switch to IVFFlat at scale. Use HNSW from the start; revisit at 100K+ embeddings.
- **LangGraph necessity:** STACK.md flags MEDIUM confidence — if data gathering stays to 3 simple parallel API calls, plain `asyncio.gather` may suffice. Evaluate after Phase 3 implementation. LangGraph adds value when conditional routing and error recovery per-node are needed.

## Sources

### Primary (HIGH confidence)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/) — SDK docs, GA status, model naming
- [Gemini Embedding Docs](https://ai.google.dev/gemini-api/docs/embeddings) — gemini-embedding-001, MRL dimensions
- [Linear OAuth 2.0 Docs](https://linear.app/developers/oauth-2-0-authentication) — 24h token expiry, refresh token behavior
- [Linear Webhooks Docs](https://linear.app/developers/webhooks) — HMAC-SHA256, 5s timeout, 3 retries
- [Slack Rate Limits Changelog](https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps/) — conversations.history Tier 1 for non-Marketplace apps
- [Slack Token Types](https://docs.slack.dev/authentication/tokens/) — bot vs user token differences
- [Supabase RLS Performance](https://supabase.com/docs/guides/troubleshooting/rls-performance-and-best-practices-Z5Jjwv) — SELECT wrapper, index strategies
- [Supabase Vault Docs](https://supabase.com/docs/guides/database/vault) — encryption, statement logging leak
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — persistence and retry limitations
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) — transport, auth, tool schemas
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) — official SDK reference

### Secondary (MEDIUM confidence)
- [Nango: OAuth Token Refresh Concurrency](https://nango.dev/blog/concurrency-with-oauth-token-refreshes) — Redis lock pattern for race conditions
- [FastAPI BackgroundTasks vs Celery comparison](https://medium.com/@komalbaparmar007/fastapi-background-tasks-vs-celery-vs-arq-picking-the-right-asynchronous-workhorse-b6e0478ecf4a) — production limitations
- [Six Lessons Building RAG Systems in Production](https://towardsdatascience.com/six-lessons-learned-building-rag-systems-in-production/) — context quality vs quantity, hard negatives
- [Gemini API Rate Limits 2026](https://blog.laozhang.ai/en/posts/gemini-api-rate-limits-guide) — free tier 92% reduction, TPM limits
- [Linear AI feature page](https://linear.app/ai) — competitive positioning

### Tertiary (LOW confidence)
- [LangGraph Limitations Community Discussion](https://community.latenode.com/t/current-limitations-of-langchain-and-langgraph-frameworks-in-2025/30994) — production observability gaps; validate against official LangGraph docs

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
