# Phase 22: Graph Foundation + Rule-Based Extraction - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Create the knowledge graph schema (graph_nodes + graph_edges tables) in Supabase Postgres with workspace-scoped RLS, fingerprint-based deduplication, and performant recursive CTE traversal. Ship deterministic regex extractors that populate graph nodes and edges from all ingested content at zero LLM cost. This is the foundation every subsequent graph phase builds on.

</domain>

<decisions>
## Implementation Decisions

### Graph Schema Design
- Entity types: Expanded set from day one -- Person, Ticket, SlackThread, PR, CodeChunk, NotionPage, Meeting, Decision, Blocker, Feature, Component. Prepares schema for LLM extraction in Phase 24 even though rule-based extractors won't populate all types yet
- Source linking: Polymorphic source_type + source_id columns (same pattern as embeddings table). No nullable FK columns per type
- Fingerprint strategy: hash(entity_type + external_id), e.g. hash('Ticket:ENG-123') or hash('Person:slack:U12345'). Deterministic, survives re-ingestion. Unique constraint per workspace (workspace_id, fingerprint)
- Relationship types: Comprehensive taxonomy from start -- mentions, references, authored_by, assigned_to, discussed_in, implements, reviews, decided_in, blocks, same_as, parent_of. Ready for all phases
- Properties: JSONB column on both nodes and edges for flexible metadata storage
- Standard columns: workspace_id FK, created_at, updated_at, deleted_at (soft delete), follows existing schema conventions

### Extraction Scope
- Regex extractors: All five patterns -- ticket refs (ENG-123, CON-45), @mentions (Slack user IDs, Linear usernames), PR/commit refs (#123, SHA prefixes), file paths (/src/..., .ts/.py extensions), URLs (links to Linear, GitHub, Notion, Slack that resolve to known entities)
- Content sources: All ingested content -- Slack messages, Linear tickets + comments, GitHub PRs + reviews, Notion pages, meeting transcripts/segments
- Source nodes: Extractors also create nodes for the source content itself (e.g., SlackThread node for the message being extracted from) so edges connect entity -> source. Full graph neighborhood from the start
- Unresolved references: Create dangling nodes with status='unresolved' in properties. When the referenced entity syncs later, the node gets updated via fingerprint match. No broken edges

### Extraction Hook Point
- Hook location: Inline after upsert -- call extract_and_populate_graph() right after each record is upserted in webhook background tasks and sync services. Same transaction context, zero latency. Matches EXTR-02 requirement
- Backfill: One-time backfill script processes all existing content (Slack messages, tickets, PRs, Notion pages, meetings). Graph is immediately useful, not just for new content
- Error handling: Fail silently with warning logs. Graph extraction is additive -- if it fails, core ingestion (ticket upsert, embedding job) still succeeds. Graph data is best-effort
- Interface: Registry pattern -- each extractor (ticket_ref, mention, pr_ref, file_path, url) is a registered function. run_extractors(content, source_type) iterates the registry. Easy to add new extractors in Phase 24+

### Traversal Function
- Depth limits: Default 2 hops, maximum 4. Covers most useful paths (Ticket -> SlackThread -> Person) while keeping CTE performance predictable
- Direction: Supports outbound, inbound, or both (default). Optional direction parameter on traverse_graph()
- Return shape: Rich result -- (node_id, entity_type, name, properties, edge_relationship_type, depth, path). Callers can reconstruct subgraph or use flat list
- Filtering: Optional entity_types[] and relationship_types[] parameters for targeted queries (e.g., "all Person nodes connected via authored_by within 2 hops")
- Security: SECURITY DEFINER function validates workspace_id once at entry, bypasses per-row RLS overhead during recursive traversal

### Claude's Discretion
- Exact regex patterns and edge cases for each extractor
- SQL migration file numbering and ordering
- Backfill script batch size and concurrency
- Index selection beyond the required composites
- Test fixture design for graph traversal tests

</decisions>

<specifics>
## Specific Ideas

- Fingerprint pattern mirrors the content_hash deduplication already used in embeddings table
- Registry pattern for extractors should be extensible enough that Phase 24's LLM extractor can register alongside regex extractors
- URL extraction should match known integration URL patterns (linear.app/*, github.com/*/pull/*, notion.so/*, slack.com/archives/*) and resolve them to existing entities

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `embeddings` table: Same polymorphic source_type + source_id pattern to follow for graph_nodes
- `linking.py`: find_related_content() will gain graph traversal as third signal in Phase 25 -- graph schema must support the LinkedItem result shape
- `match_embeddings()` SQL function: Pattern for SECURITY DEFINER functions in Supabase
- Webhook background tasks: `process_webhook_event`, `process_github_event`, `process_notion_webhook_event` -- hook points for inline extraction
- `enqueue_embedding_job()`: Pattern for post-upsert side effects in sync services
- SQLModel models in `backend/src/models/`: Follow for new GraphNode and GraphEdge models

### Established Patterns
- Migration files: `NNNNN_description.sql` with idempotent DDL, UPPERCASE SQL keywords, lowercase identifiers
- RLS: All workspace-scoped tables use `workspace_id in (select workspace_id from workspace_members where user_id = auth.uid())`
- Soft deletes: `deleted_at timestamptz` column on all entities
- Auto-timestamps: `moddatetime` trigger for `updated_at`
- UUID PKs: `id uuid primary key default gen_random_uuid()`
- Check constraints: Used for provider enums, status enums

### Integration Points
- `backend/src/routers/webhooks.py`: Background tasks where inline extraction fires
- `backend/src/services/linear_sync.py`: After ticket/comment upsert, call extractors
- `backend/src/services/github_sync.py`: After PR/review upsert, call extractors
- `backend/src/services/notion_sync.py`: After page upsert, call extractors
- `supabase/migrations/`: Next migration number is 00017
- `backend/src/models/`: New graph_node.py and graph_edge.py model files
- `backend/src/services/`: New graph_extractor.py service with registry pattern

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 22-graph-foundation-rule-based-extraction*
*Context gathered: 2026-03-07*
