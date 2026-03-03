# Phase 12: Org-wide Code Intelligence for Context - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a code indexing pipeline that makes org-wide code searchable for the context generation system. Clone selected repos, parse code with tree-sitter, extract function/class definitions, embed in pgvector, and query during context page generation — so engineers get relevant code from ANY repo (including repos they've never worked in) surfaced in their ticket context.

**This is NOT a code search product.** ContextOS's differentiator is cross-tool synthesis (Slack + Linear + Notion + meetings + code). The code graph is context input, not the product itself. Build the minimum viable indexing layer, borrow patterns from Aider/RepoMapper, ship and iterate.

**Deferred to later phases:**
- Cross-repo relationship detection (API consumer/provider matching, route pattern normalization)
- NL description layer (LLM-generated summaries per code chunk for better search quality)
- Dependency graph building (import tracing, contract/schema detection)
- Aider-style repo maps with PageRank ranking
- Git history context in context pages (who changed what, when, in which PR)

</domain>

<decisions>
## Implementation Decisions

### Repo management
- **Repo selection**: Claude's Discretion — either reuse existing Phase 7 GitHub repo selection (simplest) or add a separate "index code" toggle per repo
- **Clone strategy**: Shallow clone (`git clone --depth 1 --single-branch`) using existing GitHub App installation token for auth. Shallow clones are ~9x faster than full clones
- **Clone storage**: Claude's Discretion — either persistent local filesystem or ephemeral (clone, parse, delete, re-clone on re-index)
- **Freshness**: Claude's Discretion — webhook-driven (push events), periodic polling, or webhook + polling fallback (same pattern as Notion sync)

### Indexing pipeline
- **NL description layer**: SKIP for MVP. Just embed raw code + metadata header. Add LLM-generated descriptions later if search quality is insufficient
- **Embedding model**: Use existing OpenAI text-embedding-3-small (768 dims) for code too. Unified model, unified search, no dual-model complexity. Upgrade to voyage-code-3 later if code search quality needs improvement
- **Language scope**: Language-agnostic from day one. tree-sitter supports 165+ languages — don't scope to specific languages. Use `tree-sitter-language-pack` (pre-compiled wheels, zero GPL deps)
- **Chunk types**: Claude's Discretion — at minimum function + class definitions with docstrings/decorators. Optionally include route decorators, data model definitions, type definitions
- **Job execution**: Claude's Discretion — use existing Redis Streams (consistent with embedding pipeline) or background asyncio tasks
- **Git log analysis**: Extract basic metadata from git log (recent changes, authors) as supplementary signal. Don't over-invest here for MVP

### Context page integration
- **How code appears**: Claude's Discretion — either a new "Relevant Code" section, or woven into existing sections, or both
- **Code depth**: Claude's Discretion — references only (file paths + function names) or inline code snippets
- **Git history in context pages**: SKIP for MVP. Just show the relevant code/references. Add "last modified by X in PR #Y" later
- **Cross-repo search**: YES — this is the core value. A frontend engineer assigned a ticket should see relevant backend API routes, data models, and service logic from repos they've never worked in

### Storage & schema
- **Code chunk storage**: Claude's Discretion — either reuse existing `embeddings` table with `source_type='code_chunk'` and metadata JSONB, or create a dedicated `code_chunks` table with typed columns
- **Repo tracking**: Claude's Discretion — either new `indexed_repos` table or extend existing GitHub integration state
- **Vector index**: Use existing HNSW index config on pgvector. At 10 repos / ~50K chunks, storage is ~500MB-1GB total

### Claude's Discretion
The user gave broad discretion on most technical implementation choices. The following are explicitly left to Claude's judgment during planning:
- Repo selection mechanism (reuse Phase 7 vs separate toggle)
- Clone storage strategy (persistent vs ephemeral)
- Freshness mechanism (webhooks vs polling vs hybrid)
- Exact tree-sitter extraction targets (function/class minimum, optionally more)
- Job runner choice (Redis Streams vs background tasks)
- Context page presentation (new section vs weave vs both, references vs snippets)
- Schema design (reuse embeddings table vs new table, repo tracking approach)

</decisions>

<specifics>
## Specific Ideas

- "If I'm a frontend engineer, I don't know about backend specs. The product scans the backend repo and finds relevant specs" — this is THE use case. Cross-repo code discovery for engineers working on tickets that span service boundaries.
- Borrow patterns from Aider's repomap.py and RepoMapper (tree-sitter + graph + PageRank) but don't build the full thing for MVP. Just the extraction + embedding layer.
- "The code graph is context input, not the product itself. Keep it simple, ship the MVP, upgrade later if customers need deeper code understanding."
- "The real magic of ContextOS is the cross-tool synthesis — connecting a Slack thread to a Notion doc to a code change to a meeting transcript. That's what nobody else does well."

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- **GitHub App integration** (Phase 7): OAuth flow, repo selection model, webhook processing. Clone auth via installation tokens already available
- **Embedding service** (`backend/src/services/embedding.py`): Content-hash deduplication, batch processing (25 texts/request), Redis Streams job queue. Can be extended for code chunks
- **Hybrid search** (`hybrid_search()` PostgreSQL function): pgvector cosine similarity + FTS (tsvector), configurable weights (70% vector / 30% keyword). Already production-ready
- **Linking engine** (`backend/src/services/linking.py`): Multi-signal linking with weighted scoring. Code chunks become a new signal type
- **Synthesis service** (`backend/src/services/synthesis.py`): LLM context generation with 6-section template. Needs modification to accept code context as input

### Established Patterns
- **Source types in embeddings**: tickets, comments, PRs, reviews, slack, meetings, notion, context_pages. Add `code_chunk` as new source type
- **Webhook + polling fallback**: Used by Notion sync (webhook-first, 15-min polling fallback). Same pattern applicable for code index freshness
- **Redis Streams for async jobs**: `embedding:jobs` stream with consumer worker. Proven pattern for background processing
- **Content hash deduplication**: SHA-256 hash to skip unchanged records. Critical for incremental re-indexing

### Integration Points
- **Context generation pipeline** (`backend/src/routers/context.py`): `find_related_content()` gathers all signals. Code chunks need to be included here
- **Embedding worker** (`backend/src/services/embedding.py`): Processes `embedding:jobs` Redis stream. Needs new handler for code chunk source type
- **GitHub router** (`backend/src/routers/github.py`): Webhook receiver. May need `push` event handler for incremental code re-indexing

</code_context>

<deferred>
## Deferred Ideas

- **Cross-repo relationship detection**: API consumer/provider matching (frontend fetch calls ↔ backend route decorators), contract/schema detection (OpenAPI, protobuf, GraphQL), import graph tracing. High value but complex — own phase.
- **NL description layer**: LLM-generated natural language descriptions per code chunk (proven 12% search quality improvement by Greptile). Skip for MVP, add when search quality needs improvement.
- **Aider-style repo maps**: PageRank-weighted code context generation using NetworkX graph of file relationships. Powerful for LLM context assembly but not needed for basic code search.
- **voyage-code-3 embeddings**: SOTA code embedding model (13.8% better than OpenAI). Upgrade path if search quality with OpenAI text-embedding-3-small is insufficient for code.
- **Git history in context pages**: "Last modified by @sarah 3 days ago in PR #142" annotations on code references. Useful but skipped for MVP simplicity.
- **Greptile API integration**: Managed code intelligence API ($0.45/request). Fallback option if building custom indexing proves too complex or quality is insufficient.
- **Reranking stage**: Voyage rerank-2.5 to reorder top 20 hybrid search results down to top 5. Improves RAG accuracy by 20-35%. Add when optimizing search quality.

</deferred>

---

*Phase: 12-org-wide-code-intelligence-for-context*
*Context gathered: 2026-03-03*
