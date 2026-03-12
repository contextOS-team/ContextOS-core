# Project Research Summary

**Project:** ContextOS v1.2 -- GraphRAG Knowledge Graph Layer
**Domain:** GraphRAG knowledge graph for engineering context synthesis
**Researched:** 2026-03-06
**Confidence:** HIGH

## Executive Summary

ContextOS v1.2 adds a knowledge graph layer to an existing RAG application that already has hybrid search (pgvector + full-text), multi-source ingestion (Linear, Slack, GitHub, Notion, Fathom), and LLM synthesis producing context pages. The graph layer introduces entity extraction, identity resolution, and relationship-aware retrieval as a THIRD signal blended with existing vector + full-text search. The goal is to answer multi-hop questions that embedding similarity cannot -- "Who discussed the decision that affects this ticket?" requires traversal, not cosine distance. This is a well-understood extension pattern in GraphRAG literature, and the core approach (rule-based extraction for structured references, LLM extraction for semantic entities like decisions, blended retrieval with depth decay) is proven across multiple production deployments. Zero new Python backend dependencies are required; the existing stack (asyncpg, SQLAlchemy async, OpenAI SDK, Pydantic) handles everything.

**The single most important research finding is that Apache AGE cannot run on Supabase Cloud.** All four research tracks independently confirmed this. AGE is a C extension, not a Trusted Language Extension, and Supabase's Nix-based images reject it. The current PROJECT.md states "Apache AGE (Postgres) for knowledge graph -- stays in Supabase, no new infrastructure," which is factually wrong. The STACK researcher proposed a workaround (dedicated AGE Docker container on Railway as a second database), but the ARCHITECTURE and PITFALLS researchers additionally flagged that AGE's core R&D team was fired in October 2024, development has slowed to volunteer pace, and building a production dependency on it is a long-term liability regardless of hosting approach. **The recommended pivot: use plain PostgreSQL tables (`graph_nodes` + `graph_edges`) with recursive CTEs for traversal.** This requires zero extensions, works on Supabase Cloud today, supports RLS multi-tenancy, lives alongside existing pgvector + pg_trgm, and is sufficient for the 2-3 hop traversals this domain requires. The ARCHITECTURE research provides complete SQL schema, traversal function, and index definitions ready to use.

The top three risks are: (1) the AGE assumption blocking the milestone at day 1 if not corrected in PROJECT.md, (2) LLM entity extraction producing hallucinated or non-deterministic entities that corrupt the graph (GDELT Project research demonstrates that a single apostrophe correction can cause entities to appear and disappear), and (3) graph-retrieved context flooding synthesis prompts and making context pages worse instead of better (studies show ~20% accuracy drop when context grows from 5 to 30 documents). All three have concrete prevention strategies: pivot to plain PG tables, validate LLM output against source text spans, and enforce a fixed token budget for graph context.

---

## Key Findings

### Recommended Stack

The existing stack (FastAPI, Next.js 15, Supabase, Redis, pgvector, OpenAI SDK, SQLAlchemy async + asyncpg, Pydantic) handles the entire GraphRAG addition with zero new Python dependencies. Entity extraction uses the existing OpenAI SDK structured output (`response_format` with JSON schema). Identity resolution is custom code (~50-100 LOC). Graph queries run through existing asyncpg/SQLAlchemy as standard SQL with recursive CTEs. The only new frontend dependency is `react-force-graph-2d` (stretch goal only, requires `dynamic(() => import(...), { ssr: false })` for Next.js 15 compatibility).

**Core technologies:**
- **Plain PostgreSQL tables (graph_nodes + graph_edges):** Graph storage on Supabase Cloud -- no extensions needed, recursive CTEs for traversal, RLS-compatible via SECURITY DEFINER functions
- **OpenAI SDK structured output:** LLM-based entity extraction via `response_format` JSON schema -- already in the stack, works with both OpenAI and Gemini
- **Regex extractors (in-house, ~200 LOC):** Rule-based extraction for ticket IDs (`[A-Z]+-\d+`), @mentions (`<@U[A-Z0-9]+>`), PR numbers, file paths -- zero cost, deterministic, handles 80% of linking signals
- **Custom identity resolution (in-house, ~100 LOC):** Email-based cross-platform person matching -- bounded problem (~10-50 team members), no library needed
- **react-force-graph-2d ^1.48 (stretch only):** Graph visualization -- Canvas-based, performant for hundreds of nodes, SSR workaround verified

**What NOT to add:** apache-age-python (dead project, v0.0.7, Sep 2023, synchronous psycopg2), LangChain AGEGraph/LLMGraphTransformer (sync psycopg2, Gemini bug Issue #26624 closed NOT_PLANNED), spaCy/GLiNER (300MB+ models for generic NER when domain-specific entities are either trivially regex-extractable or require full LLM reasoning), Splink/dedupe/recordlinkage (census-scale deduplication for a ~10-person team), Neo4j (separate infrastructure category), networkx (in-memory graph when state belongs in DB).

See `.planning/research/STACK.md` for full version compatibility matrix, Docker Compose configuration, and integration code examples.

### Expected Features

**Must have (table stakes -- graph layer fails without these):**
- Knowledge graph schema (nodes + edges tables, recursive CTE traversal function, RLS policies, fingerprint deduplication)
- Rule-based entity extraction (regex for ticket IDs, @mentions, PR numbers, file paths -- inline during webhook ingestion, idempotent)
- Cross-source identity resolution (email-based deterministic matching across Linear, Slack, GitHub, Fathom, identity mapping table from team roster APIs)
- LLM entity extraction (decisions, rationale, blockers via Gemini Flash structured output -- batch via background tasks, content filtering to skip noise)
- Graph-enhanced retrieval (recursive CTE traversal results blended as third signal in `find_related_content()` with depth decay scoring)
- Updated synthesis prompts (decision trails, relationship paths, cross-referenced people in context pages, fixed token budget for graph context)

**Should have (differentiators that justify the milestone):**
- Decision extraction and linking -- the highest-value semantic entity. Decisions traced from Slack thread to meeting transcript to ticket. ContextOS's unique value proposition: cross-tool decision trails that no competing product (Linear, Notion, Confluence, Glean) offers.
- Code-to-discussion linking -- connects code_chunks (Phase 12) to conversations and tickets that motivated them. Uses PR-to-ticket links as primary bridge, extends to Slack only through threads that explicitly discuss those PRs or tickets.

**Defer (v2+):**
- Graph explorer UI frontend (build the API endpoint, defer the React visualization component)
- Person-centric aggregation views (emerges from graph data, dedicated UI can wait)
- Community detection / Leiden clustering (Microsoft GraphRAG overkill at this data scale -- hundreds to low-thousands of entities, not millions)
- Graph versioning / temporal graph (timestamp edges with `created_at`, defer full bitemporal queries)
- LazyGraphRAG / query-time extraction (adds latency, unnecessary with bounded ingestion volume)

See `.planning/research/FEATURES.md` for full prioritization matrix, entity type taxonomy, and complexity estimates (19-25 days for MVP backend, 24-31 days including stretch UI).

### Architecture Approach

The graph layer lives entirely within Supabase Cloud PostgreSQL as two new tables (`graph_nodes`, `graph_edges`) with JSONB properties for flexibility, fingerprint-based deduplication, and a `traverse_graph()` SECURITY DEFINER function for performant recursive CTE traversal that bypasses per-row RLS overhead. Entity extraction runs as async background tasks triggered after webhook ingestion (rule-based first for structured patterns, LLM second for semantic entities like decisions). The linking engine (`find_related_content()`) gains a third retrieval signal: graph traversal results scored with depth decay (1-hop = 0.9, 2-hop = 0.54, 3-hop = 0.32) and blended alongside existing explicit refs (weight 1.0) and hybrid search (weight 0.8). Synthesis prompts are extended with structured graph context sections (decision trails, people involvement, relationship paths) under a fixed token budget of ~2,000 tokens to prevent context overflow.

**Major components:**
1. **Graph tables + traversal function** -- `graph_nodes` (entity_type, canonical_name, properties JSONB, fingerprint, confidence, source_type, source_id) and `graph_edges` (relationship_type, source/target node IDs, weight, properties JSONB) with workspace_id RLS, composite indexes, and `traverse_graph()` SECURITY DEFINER function
2. **Entity extraction service (`services/graph/extraction.py`)** -- two-tier: regex extractors (ticket IDs, @mentions, PR numbers, file paths) run first at zero cost, then LLM extraction for decisions/concepts only on high-value content (messages >50 chars containing decision signal words)
3. **Identity resolution service (`services/graph/identity.py`)** -- deterministic email/platform-ID matching across sources, explicit identity mapping table seeded from team roster APIs during integration setup, `same_as` edges for fuzzy candidates (never auto-merge on name alone)
4. **Graph retrieval service (`services/graph/retrieval.py`)** -- recursive CTE traversal with depth decay scoring, returns scored `LinkedItem` dicts for the linking engine
5. **Modified linking engine (`services/linking.py`)** -- `find_related_content()` extended with `find_graph_connections()` as third retrieval path, items found by multiple signals get boosted scores
6. **Modified synthesis (`services/synthesis.py`)** -- prompts include decision trail section, people involvement section, relationship path descriptions; graceful degradation when no graph data exists

See `.planning/research/ARCHITECTURE.md` for complete SQL DDL, Python code examples, integration points with existing code, and suggested build order.

### Critical Pitfalls

1. **Apache AGE not available on Supabase Cloud + project health risk (CRITICAL, Pitfalls #1 and #2)** -- AGE is a C extension not supported by Supabase Cloud. The AGE project's core R&D team was fired Oct 2024; future PG version compatibility is uncertain. **Use plain PostgreSQL tables with recursive CTEs.** No extension dependencies, works on every PostgreSQL version, sufficient for 2-3 hop traversals.

2. **LLM entity extraction hallucination and non-determinism (CRITICAL, Pitfall #3)** -- Same input produces different entities across runs. LLMs hallucinate entities not in source text. A single apostrophe correction can cause entities to appear/disappear. **Prevention:** rule-based first always; validate LLM output against source text spans; structured output with strict Pydantic schema; batch and deduplicate before graph insertion; temperature 0.

3. **Graph retrieval floods synthesis prompt with noise (CRITICAL, Pitfall #4)** -- A 2-hop traversal can return hundreds of related items. Studies show ~20% accuracy drop when context grows from 5 to 30 documents. **Prevention:** fixed token budget for graph context (~2,000 tokens max); score paths by relevance with depth decay; summarize relationship paths into single sentences; A/B test quality impact before shipping.

4. **Cross-source identity resolution false merges (MODERATE, Pitfall #5)** -- "Alex" on Slack auto-merged with different "Alex" on Linear destroys user trust immediately. **Prevention:** anchor on platform user IDs (email, Slack user_id, GitHub login); never auto-merge on name alone; seed identity mapping from team roster APIs; flag fuzzy matches for manual review.

5. **Recursive CTE + RLS performance degradation (MODERATE, Pitfall #6)** -- RLS subquery fires per-row during recursive traversal, turning millisecond queries into seconds. **Prevention:** SECURITY DEFINER function validates workspace membership once at entry, traverses without per-row RLS overhead. Benchmark on Supabase Cloud, not just local dev.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Graph Foundation (Schema + Rule-Based Extraction)
**Rationale:** Everything depends on the graph tables existing. Rule-based extraction is zero-cost, deterministic, and immediately populates the graph with high-confidence edges. This phase validates the core architecture (plain PG tables + recursive CTEs) before investing in LLM extraction.
**Delivers:** Supabase migration with `graph_nodes` and `graph_edges` tables (RLS, indexes, fingerprint dedup constraint), `traverse_graph()` SECURITY DEFINER function, SQLModel classes (`GraphNode`, `GraphEdge`), regex extractors for ticket IDs / @mentions / PR numbers / file paths, webhook handler integration via `BackgroundTasks`, node fingerprint deduplication logic, embeddings CHECK constraint updated to include graph source types.
**Addresses features:** Knowledge graph schema, rule-based entity extraction
**Avoids pitfalls:** AGE dependency (#1, #2 -- plain PG from the start), schema over-engineering (#8 -- start with ~5 entity types, ~6 relationship types), embeddings CHECK constraint (#11)

### Phase 2: Identity Resolution + LLM Extraction
**Rationale:** Identity resolution needs person nodes from Phase 1 to merge against. LLM extraction builds on the same pipeline infrastructure. Both are independent code paths that can be developed in parallel (different services, same destination graph tables). This phase produces the semantic entities (decisions, concepts) that make the graph genuinely valuable beyond structural references.
**Delivers:** Deterministic identity resolution (email + platform ID matching), explicit `identity_mappings` table seeded from Linear/Slack/GitHub team roster APIs, `same_as` edges for fuzzy candidates with confidence scores, LLM extraction pipeline for decisions and semantic entities, content filtering (skip bot/short/emoji messages, process Slack threads as units), structured output via existing OpenAI SDK, content hash deduplication to prevent re-extraction, decision extraction with `decided_at` timestamps and SUPERSEDES edges for temporal ordering.
**Addresses features:** Cross-source identity resolution, LLM entity extraction, decision extraction and linking
**Avoids pitfalls:** LLM hallucination (#3 -- source text validation, structured output), Slack message noise (#7 -- filtering before extraction), false identity merges (#5 -- ID-anchored matching, never auto-merge on name), graph staleness (#9 -- content hash tracking from the start)

### Phase 3: Graph-Enhanced Retrieval + Synthesis
**Rationale:** Requires a populated graph (Phases 1-2) to be meaningful. This is where GraphRAG delivers user-visible value: context pages improve with decision trails and relationship paths. Must be built carefully to avoid making synthesis worse through context overflow.
**Delivers:** `find_graph_connections()` function with depth-decay scoring, modified `find_related_content()` with graph as third retrieval signal, modified synthesis prompts with decision trail / people involvement / relationship path sections, token budget enforcement for graph context (~2,000 tokens), graceful degradation when no graph data exists, code-to-discussion linking via PR-to-ticket bridges, per-signal score logging for debugging and weight tuning.
**Addresses features:** Graph-enhanced retrieval, updated synthesis prompts, code-to-discussion linking
**Avoids pitfalls:** Context overflow (#4 -- token budget, path summarization, A/B testing), black-box score blending (#10 -- separate retrieval channels, normalized scores, per-signal logging), RLS performance (#6 -- SECURITY DEFINER already in place from Phase 1), weak code-to-discussion edges (#13 -- multi-signal co-occurrence, PR-based primary bridge)

### Phase 4: Polish + Graph Explorer (Stretch)
**Rationale:** Backend must work and context pages must demonstrably improve before investing in visualization. Graph explorer requires real data to build against -- building against mock data is an explicitly documented anti-pattern.
**Delivers:** GET `/api/context/{ticket_identifier}/graph` endpoint returning subgraph JSON (nodes + edges), react-force-graph-2d visualization component (if time permits, dynamic import with SSR disabled), decision temporal ordering improvements, retrieval weight tuning based on empirical quality comparison data, person-centric aggregation surfaced in context pages.
**Addresses features:** Graph explorer UI (API + optional frontend), person-centric aggregation, decision temporal context
**Avoids pitfalls:** Building UI before backend works (ARCHITECTURE anti-pattern #5), conflicting temporal decisions (#12 -- SUPERSEDES edges from Phase 2)

### Phase Ordering Rationale

- **Schema before extraction:** You cannot store entities without tables. The traversal function must exist before retrieval testing.
- **Rule-based before LLM:** Validates the extraction -> graph pipeline with zero cost and deterministic data. If the pipeline has bugs, they surface before burning LLM budget. Rule-based person nodes provide the roster that identity resolution merges against.
- **Identity resolution alongside LLM extraction (Phase 2 parallelizable):** Independent code paths (different services, same destination tables). Developing in parallel shortens the critical path.
- **Retrieval after population:** Graph-enhanced retrieval with an empty graph produces nothing. Phases 1-2 must populate meaningful data before retrieval quality can be assessed.
- **Synthesis tuning last among core phases:** Synthesis changes are the user-facing output. They must be tuned against real retrieval results. A/B testing against pre-graph context pages requires the full pipeline working.
- **UI absolutely last:** The documented anti-pattern of building visualization against mock data. API endpoint ships with Phase 3; frontend component is stretch.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (LLM Extraction + Identity Resolution):** Decision extraction prompt engineering needs iteration. The exact content filtering thresholds (message length, decision signal words list) need tuning. LLM extraction accuracy (60-85% cited range) needs validation with a manually labeled evaluation set of 20-30 messages. Identity resolution edge cases (display name changes, external collaborators, multiple email addresses) need case-by-case design.
- **Phase 3 (Retrieval + Synthesis):** Score blending weights (explicit 1.0, hybrid 0.8, graph 0.9) are empirical starting points that need tuning against real data. Token budget for graph context needs experimentation. Quality comparison framework for A/B testing graph inclusion does not exist yet and must be built.

Phases with standard patterns (skip deep research):
- **Phase 1 (Schema + Rule-Based Extraction):** Plain PostgreSQL tables, recursive CTEs, regex extraction are all well-documented patterns with complete SQL DDL and Python code provided in ARCHITECTURE.md. No architectural decisions remain.
- **Phase 4 (Graph Explorer):** react-force-graph-2d integration with Next.js 15 is straightforward (dynamic import, SSR disabled, verified). The API endpoint is a standard graph neighborhood query wrapping `traverse_graph()`.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new backend dependencies confirmed. Plain PG approach verified via Supabase's own pgrouting blog, postgres-graph-rag library, and multiple CTE tutorials. AGE incompatibility verified via official Supabase docs and GitHub discussions #40285 and #13263. |
| Features | HIGH | Feature taxonomy grounded in direct competitor analysis and existing codebase inspection. Table stakes vs differentiators clearly separated. Complexity estimates (19-25 days MVP) align with architecture component count. Decision extraction as unique differentiator is a strong, defensible thesis. |
| Architecture | HIGH | Complete DDL for graph tables, traversal function, RLS policies, and indexes provided and ready to use. Integration points with existing code (linking.py, synthesis.py, webhook handlers) are specific to named functions and files. RLS performance pattern (SECURITY DEFINER) verified across multiple PostgreSQL optimization sources. |
| Pitfalls | HIGH | 13 pitfalls identified from 20+ verified sources. Top 3 critical pitfalls have concrete, actionable prevention strategies. The AGE blocker is unanimously confirmed across all 4 research tracks. LLM hallucination evidence comes from peer-reviewed-quality GDELT Project experiments. Context overflow risk backed by published research on "lost in the middle" effects. |

**Overall confidence:** HIGH

### Gaps to Address

- **PROJECT.md correction required:** The current PROJECT.md states "Apache AGE (Postgres) for knowledge graph -- stays in Supabase, no new infrastructure." This must be updated to "Plain PostgreSQL tables (graph_nodes + graph_edges) with recursive CTEs -- stays in Supabase, no new infrastructure" before development begins. All four research tracks confirm this change is necessary.
- **LLM extraction accuracy validation:** Research cites 60-85% as typical for LLM entity extraction. Build an evaluation set of 20-30 manually labeled messages during Phase 2 to measure actual accuracy for engineering decisions from Slack and meeting transcripts.
- **Retrieval weight tuning framework:** Starting weights are reasonable defaults but need empirical tuning. Build a quality comparison framework (before/after graph context page side-by-side) before shipping graph-enhanced synthesis to users.
- **Recursive CTE performance benchmarking:** The 2-3 hop traversal with SECURITY DEFINER is expected to perform well at this scale (~1K-10K nodes), but MUST be benchmarked on Supabase Cloud with RLS enabled. PITFALLS research warns that local dev performance differs from Cloud.
- **Content hash staleness detection:** The pattern (compare graph node source_content_hash against current source document hash) is described in research but not yet implemented anywhere in the existing codebase. Needs design during Phase 2.

---

## Sources

### Primary (HIGH confidence)
- [Supabase Extensions List](https://supabase.com/docs/guides/database/extensions) -- AGE not available
- [Supabase Discussion #40285](https://github.com/orgs/supabase/discussions/40285) -- AGE install blocked, confirmed not possible
- [Supabase Discussion #13263](https://github.com/orgs/supabase/discussions/13263) -- AGE not supported, workarounds discussed
- [Apache AGE Discussion #2150](https://github.com/apache/age/discussions/2150) -- core R&D team dismissed Oct 2024
- [Apache AGE Issue #2111](https://github.com/apache/age/issues/2111) -- PG17 support delayed
- [GDELT: LLM Entity Extraction Hallucination](https://blog.gdeltproject.org/experiments-in-entity-extraction-using-llms-hallucination-how-a-single-apostrophe-can-change-the-results/) -- non-determinism evidence
- [GDELT: LLM Infinite Loops & Failure Modes](https://blog.gdeltproject.org/llm-infinite-loops-failure-modes-the-current-state-of-llm-entity-extraction/) -- extraction failure modes
- [Redis: Context Window Overflow](https://redis.io/blog/context-window-overflow/) -- prompt stuffing risks
- [Pinecone: Less is More](https://www.pinecone.io/blog/why-use-retrieval-instead-of-larger-context/) -- retrieval vs. context size
- [Bytebase: PostgreSQL RLS Limitations](https://www.bytebase.com/blog/postgres-row-level-security-limitations-and-alternatives/) -- RLS performance
- [Scott Pierce: Optimizing Postgres RLS](https://scottpierce.dev/posts/optimizing-postgres-rls/) -- SECURITY DEFINER pattern
- [postgres-graph-rag library](https://github.com/h4gen/postgres-graph-rag) -- pure PG graph RAG approach validated
- [Recursive CTEs for graph traversal](https://www.sheshbabu.com/posts/graph-retrieval-using-postgres-recursive-ctes/) -- SQL traversal patterns
- [Microsoft GraphRAG Methods](https://microsoft.github.io/graphrag/index/methods/) -- entity extraction pipeline architecture
- [Supabase pgrouting blog](https://supabase.com/blog/pgrouting-postgres-graph-database) -- Supabase's own approach to graph in Postgres

### Secondary (MEDIUM confidence)
- [GraphRAG.com: Graph-Enhanced Vector Search](https://graphrag.com/reference/graphrag/graph-enhanced-vector-search/) -- hybrid retrieval patterns
- [Neo4j: Knowledge Graph from Slack Archive](https://medium.com/neo4j/how-to-create-a-knowledge-graph-from-your-slack-archive-with-neo4j-6a1a1d59a535) -- Slack extraction patterns
- [Datagrid: Knowledge Graphs from Slack](https://datagrid.com/blog/build-knowledge-graphs-slack-conversations-ai-agents-d16d8) -- Slack filtering, decision extraction
- [Entity Resolution Techniques](https://www.puppygraph.com/blog/entity-resolution) -- deterministic, probabilistic, ML-based approaches
- [Memgraph: Model a Knowledge Graph](https://memgraph.com/docs/data-modeling/modeling-guides/model-a-knowledge-graph) -- schema design principles
- [FalkorDB: How to Build a Knowledge Graph](https://www.falkordb.com/blog/how-to-build-a-knowledge-graph/) -- iterative schema approach
- [NetApp: Hybrid RAG in the Real World](https://community.netapp.com/t5/Tech-ONTAP-Blogs/Hybrid-RAG-in-the-Real-World-Graphs-BM25-and-the-End-of-Black-Box-Retrieval/ba-p/464834) -- score blending challenges
- [Bitext: Why LLMs Are Wrong for Enterprise Entity Extraction](https://www.bitext.com/blog/why-llms-are-the-wrong-tool-for-enterprise-grade-entity-extraction/) -- production reliability
- [freeCodeCamp: 5 Common RAG Failures with Knowledge Graphs](https://www.freecodecamp.org/news/how-to-solve-5-common-rag-failures-with-knowledge-graphs/) -- RAG failure taxonomy
- [Knowledge Graphs with PostgreSQL](https://app.readytensor.ai/publications/knowledge-graphs-with-postgresql-eQyINuo4ojwW) -- nodes/edges table approach

### Tertiary (LOW confidence)
- [source{d} Identity Matching](https://github.com/src-d/identity-matching) -- archived project, approach reference only
- [iText2KG: Incremental KG Construction](https://arxiv.org/html/2409.03284v1) -- incremental update patterns
- [postgres-graph-rag v0.1.2](https://github.com/h4gen/postgres-graph-rag) -- early-stage, interesting pattern reference but not production-hardened

---
*Research completed: 2026-03-06*
*Ready for roadmap: yes*
