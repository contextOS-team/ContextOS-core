# Phase 10: Sync Engine Improvements - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Improve the speed, reliability, and architecture of the existing sync pipeline for all integrated providers (Notion, GitHub, Linear, Slack). This phase focuses on incremental sync, embedding pipeline optimization, concurrency controls, and sync state management. No new provider integrations — only improvements to existing sync infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Incremental Sync Strategy
- Webhook-first with polling fallback for all providers that support webhooks (Notion, GitHub, Linear)
- Polling fallback runs every 15 minutes to catch missed webhook events
- Skip body content refetch when only metadata changed — compare last_edited_time to decide if full content fetch is needed. Update metadata directly without re-downloading page/document body
- Full re-sync scheduling: Claude's discretion (auto daily vs user-triggered)

### Embedding Pipeline
- Decouple embedding generation from sync via Redis Streams — sync completes fast, embedding workers process asynchronously from queue
- Batch 20-50 texts per OpenAI embedding API call instead of one-at-a-time (OpenAI supports list inputs natively)
- Normalize whitespace and formatting before computing content hash for significance filtering — trivial edits (spacing, line breaks) should not trigger re-embedding
- Track embedding model version — add model_name and model_version columns to embeddings table for selective re-embedding on model upgrades

### Concurrency & Rate Limits
- asyncio.Semaphore per provider: Notion Semaphore(3), GitHub Semaphore(10), Linear Semaphore(5)
- Enable HTTP/2 for all httpx API clients (requires httpx[http2] / h2 dependency)
- Add random jitter to retry backoff: wait *= 0.5 + random.random() for 50-150% of base delay
- Configure explicit httpx connection pool limits per provider:
  - Notion: max_keepalive=5, max_connections=10 (low rate limit)
  - GitHub: max_keepalive=20, max_connections=30 (higher throughput)
  - All: keepalive_expiry=30s

### Sync State & Observability
- Dedicated sync_cursors table replacing JSONB in workspace_integrations.config
  - Columns: workspace_id, provider, resource_type, cursor_type, cursor_value, records_synced, sync_status, last_sync_at, error_message
- Structured logging with sync_run_id correlation — generate UUID per sync run, thread through all log messages. Add provider + workspace_id to log context
- SyncAdapter protocol (common interface) for all providers:
  - Methods: full_sync(), handle_webhook(), reconcile()
  - Shared orchestration layer for scheduling, state management, error handling

### Claude's Discretion
- Dead letter queue for failed sync operations (sync_failures table vs just logging errors)
- Full re-sync scheduling approach (auto daily vs keep user-triggered only)
- Circuit breaker implementation details per provider
- Exact Redis Streams consumer group configuration
- Whether to add OpenTelemetry metrics/tracing in this phase or defer

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `embedding.py`: Already has content-hash deduplication (SHA-256), SOURCE_TYPE_MAP for all providers, queue_embedding_generation() and process_pending_embeddings() functions
- `notion_client.py`: httpx.AsyncClient with retry on 429, exponential backoff (MAX_RETRIES=3), async context manager pattern
- `notion_sync.py`, `linear_sync.py`, `github_sync.py`: Per-provider sync services with PostgreSQL ON CONFLICT DO UPDATE upserts
- Redis already configured in docker-compose as Celery broker (redis:7-alpine)
- `workspace_integrations.config` JSONB: Current sync state storage (sync_status, last_sync_at, pages_synced)

### Established Patterns
- Background sync via FastAPI BackgroundTasks with own session via async_session()
- Concurrency guard in Notion router (_syncing_workspaces set) to prevent duplicate operations
- Webhook signature verification: HMAC-SHA256 for Linear, Slack, Notion
- OAuth token storage in Vault with provider-specific refresh patterns
- All DB timestamps use naive UTC (datetime.now(timezone.utc).replace(tzinfo=None))

### Integration Points
- `backend/src/routers/notion.py`: _run_sync() orchestrates fetch → upsert → embed pipeline
- `backend/src/routers/webhooks.py`: Webhook receiver endpoint
- `backend/src/services/embedding.py`: queue_embedding_generation() called by all sync services
- `backend/src/db.py`: async_session() factory for background task isolation
- `docker-compose.yml`: Redis service already available for Streams

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches informed by the research done on Notion/GitHub/Slack API best practices.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-sync-engine-improvements*
*Context gathered: 2026-03-02*
