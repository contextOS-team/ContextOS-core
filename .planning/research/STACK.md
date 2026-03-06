# Technology Stack: GraphRAG Additions for ContextOS v1.2

**Project:** ContextOS -- GraphRAG Knowledge Graph Layer
**Researched:** 2026-03-06
**Scope:** NEW dependencies only. Existing stack (FastAPI, Next.js 15, Supabase, Redis, pgvector, LangGraph, tree-sitter, OpenAI SDK, SQLAlchemy async + asyncpg, Pydantic) is validated and not covered.

---

## Critical Infrastructure Decision: Apache AGE Deployment

**Apache AGE is NOT available as a Supabase managed extension.** AGE is a C extension, not a Trusted Language Extension, so it cannot be installed on Supabase Cloud. This is the single most important constraint for the v1.2 milestone.

### Recommended Approach: Dedicated AGE Postgres Container

Deploy a separate PostgreSQL 16 instance with AGE pre-installed as a Docker container alongside the existing infrastructure. The backend connects to TWO databases: Supabase for relational data/auth/RLS, and the AGE instance for graph operations.

**Why not alternative approaches:**

| Alternative | Why Not |
|---|---|
| Pure SQL recursive CTEs (no AGE) | Cypher is dramatically more expressive for graph traversal. CTEs become unreadable at 3+ hops and cannot express variable-length path patterns. The team chose AGE for good reason. |
| Supabase fork with AGE compiled in | Requires maintaining a Nix build fork of supabase/postgres. Fragile, version-lock risk, unsupported by Supabase. |
| postgres_fdw between Supabase and AGE | Adds latency per query, complicates transactions, FDW does not support AGE's `cypher()` function across boundaries. |
| Neo4j or separate graph DB | New infrastructure category, new ops burden, no pgvector co-location benefit. AGE keeps everything in Postgres. |
| postgres-graph-rag library | v0.1.2, early-stage, "interface can evolve quickly" per README. Not production-ready. |

**Confidence:** HIGH -- verified via Supabase GitHub Discussion #40285, Docker Hub apache/age image, and community reports.

---

## Recommended Stack Additions

### 1. Graph Database Layer

| Technology | Version | Purpose | Why |
|---|---|---|---|
| Apache AGE | 1.5.0+ (PG16) | Graph extension for Postgres | Cypher query language, stays in Postgres ecosystem. Team decision already made. |
| `apache/age` Docker image | PG16 tag | Graph DB container | Official image, supports PG 11-18. Use PG16 for stability (PG15 had string type issues with AGE per community reports). |

**Integration pattern:** The backend already uses SQLAlchemy async with asyncpg. AGE Cypher queries execute as raw SQL wrapping Cypher via `ag_catalog.cypher()`. Create a dedicated async engine/session factory pointing at the AGE database, mirroring the existing `src/db.py` pattern.

```python
# graph_db.py -- second engine for AGE database
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

graph_engine = create_async_engine(
    settings.GRAPH_DATABASE_URL,  # postgresql+asyncpg://...@age-host:5433/context_graph
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

graph_session = async_sessionmaker(graph_engine, class_=AsyncSession, expire_on_commit=False)
```

```python
# Example: raw Cypher via asyncpg/SQLAlchemy
from sqlalchemy import text

query = text("""
    SELECT * FROM ag_catalog.cypher('context_graph', $$
        MATCH (p:Person)-[:MADE]->(d:Decision)-[:AFFECTS]->(t:Ticket {external_id: :ticket_id})
        RETURN p, d, t
    $$) AS (person agtype, decision agtype, ticket agtype)
""")
result = await graph_session.execute(query, {"ticket_id": ticket_id})
```

**Do NOT use these Python libraries for AGE integration:**

| Library | Why Not |
|---|---|
| `apache-age-python` (PyPI v0.0.7) | Last updated Sep 2023. Uses psycopg2 (synchronous). Incompatible with the async architecture. Dead project. |
| `langchain-community` AGEGraph class | Wraps `psycopg2.connect()` synchronously. Cannot integrate with the existing async SQLAlchemy engine. Would require running sync code in thread executors. |

**Confidence:** HIGH -- verified via Apache AGE docs, asyncpg compatibility analysis, existing codebase inspection (`src/db.py` uses `create_async_engine` with asyncpg).

---

### 2. AGType Parsing

| Technology | Version | Purpose | Why |
|---|---|---|---|
| Custom agtype parser | N/A (in-house, ~100 LOC) | Parse AGE's agtype query results into typed Python objects | agtype is a JSON superset. Parse with `json.loads()` for simple cases. Build thin Pydantic models (Vertex, Edge, Path) for type safety. Avoids pulling in antlr4-python3-runtime dependency. |

**Rationale:** The official `apache-age-python` package's main value is its ANTLR-based agtype parser. But agtype is effectively JSON with graph metadata wrapping. A custom parser using Python's `json` module + Pydantic models is simpler, async-compatible, and has zero dependencies. The parser needs to handle three shapes:
- **Vertex:** `{"id": N, "label": "X", "properties": {...}}`
- **Edge:** `{"id": N, "label": "X", "start_id": N, "end_id": N, "properties": {...}}`
- **Path:** ordered list of vertices and edges

Additionally, register a custom type codec with asyncpg using `connection.set_type_codec()` for the `agtype` OID so results are automatically deserialized.

**Confidence:** MEDIUM -- agtype is documented as JSON-superset in AGE docs. Edge cases in complex nested paths or NULL handling may require iteration. The custom codec registration with asyncpg is documented but needs testing with AGE-specific OIDs.

---

### 3. Entity Extraction

| Technology | Version | Purpose | Why |
|---|---|---|---|
| Existing OpenAI SDK (async) | Already in deps | LLM-based semantic entity extraction via structured output | Already in the stack as `openai` package. The LLM client (`src/services/llm_client.py`) uses `AsyncOpenAI`. Extend it with a structured output method using `response_format={"type": "json_schema", ...}` to extract entities. Works with both OpenAI models and Gemini (via OpenAI-compatible endpoint). |
| Regex extractors | N/A (in-house) | Rule-based structured entity extraction | Regex patterns for ticket IDs (`[A-Z]+-\d+`), @mentions (`<@U[A-Z0-9]+>`), PR numbers (`#\d+`), file paths, URLs. Zero-cost, deterministic, handles 80% of linking signals. |

**Entity extraction strategy (two-tier):**

1. **Rule-based first (zero cost, deterministic):** Regex patterns extract ticket refs, @mentions, PR numbers, file paths, and URLs from all source content. These produce high-confidence entity references with zero LLM cost.

2. **LLM second (for semantic entities):** For each source document (Slack thread, meeting transcript, ticket description), call the LLM with a JSON schema to extract:
   - Decisions made (what was decided, who decided, when, rationale)
   - People mentioned with role context (not just names but "reviewer", "requester", etc.)
   - Semantic relationships between entities that regex cannot capture

```python
# Extend LLMClient with structured extraction
ENTITY_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "entity_extraction",
        "schema": {
            "type": "object",
            "properties": {
                "decisions": {"type": "array", "items": {...}},
                "people": {"type": "array", "items": {...}},
                "relationships": {"type": "array", "items": {...}},
            },
            "required": ["decisions", "people", "relationships"]
        }
    }
}
```

**Do NOT use these for entity extraction:**

| Library | Why Not |
|---|---|
| spaCy | Heavyweight NLP (300MB+ models). ContextOS needs domain-specific entities (ticket IDs, decisions, code references), not generic PERSON/ORG/GPE NER. Pre-trained models would not help. |
| GLiNER (v0.2.25) | Zero-shot NER model. Interesting but adds model inference dependency. Entity types in ContextOS are either trivially regex-extractable (ticket IDs) or require LLM-level reasoning (decisions). No middle ground where GLiNER wins over the existing LLM. |
| LangChain `LLMGraphTransformer` | Known bug with Gemini (GitHub Issue #26624, closed NOT_PLANNED). Returns strings instead of lists when using Gemini's structured output. The `ignore_tool_usage=True` workaround is fragile. Build extraction prompts directly using existing SDK structured output instead. |

**Confidence:** HIGH -- OpenAI SDK structured output (`response_format`) is well-documented. Rule-based extraction is standard practice. LLMGraphTransformer Gemini incompatibility verified via GitHub issue.

---

### 4. Identity Resolution

| Technology | Version | Purpose | Why |
|---|---|---|---|
| Custom resolution logic | N/A (in-house) | Cross-source person matching | ContextOS has a bounded, small identity space (team members across Linear, Slack, GitHub, Fathom). This is NOT a million-record deduplication problem. Simple heuristic matching on email + display name + known aliases suffices. |

**Do NOT use:**

| Library | Why Not |
|---|---|
| Splink (v4.0.7) | Designed for probabilistic linkage across millions of records (census-scale). Adds DuckDB dependency. Massive overkill for matching ~10-50 team members across 4 integrations. |
| dedupe (v3.0.2) | Requires manual training by labeling record pairs. Interactive workflow incompatible with automated pipeline. |
| recordlinkage | Same category of census-scale deduplication. Wrong tool for the problem size. |

**Identity resolution strategy:**

Each integration already stores user identifiers (Linear user ID, Slack user ID, GitHub username, etc.). Build a `person_identities` mapping table:

```
person_id (graph node UUID) <-> [(source: "linear", external_id: "abc123"),
                                  (source: "slack", external_id: "U01234"),
                                  (source: "github", external_id: "username")]
```

Resolution rules (in priority order):
1. **Exact email match** across sources (highest confidence, handles most cases)
2. **Display name normalization + token overlap** for ambiguous cases
3. **Admin manual linking** via settings UI for remaining edge cases

Store in the AGE graph as `Person` nodes with `HAS_IDENTITY` edges pointing to source-specific identity nodes. A `SAME_AS` edge is not needed when the canonical Person node is the merge target.

**Confidence:** HIGH -- bounded problem space (small teams), well-understood matching rules.

---

### 5. Graph-Enhanced Retrieval

| Technology | Version | Purpose | Why |
|---|---|---|---|
| No new dependencies | N/A | Blend graph signal with existing hybrid search | Graph traversal via Cypher queries produces relationship paths. Score and rank alongside existing pgvector similarity + full-text search. Implement as a scoring function in Python. |

**Retrieval blending strategy:**

```python
# Pseudo-code for blended retrieval
async def enhanced_retrieve(query: str, ticket_id: str) -> list[ScoredResult]:
    # 1. Existing: vector similarity from Supabase pgvector
    vector_results = await vector_search(query, workspace_id)

    # 2. Existing: full-text search from Supabase
    fts_results = await fulltext_search(query, workspace_id)

    # 3. NEW: graph neighborhood from AGE
    graph_results = await graph_neighborhood(ticket_id, max_hops=3)

    # 4. Blend scores
    combined = merge_and_score(
        vector_results,   weight=0.4,
        fts_results,      weight=0.3,
        graph_results,    weight=0.3,
    )
    return sorted(combined, key=lambda r: r.score, reverse=True)
```

Where `graph_proximity_score` is derived from:
- Shortest path length (closer = higher score)
- Relationship type relevance (MADE_DECISION > MENTIONED_IN)
- Number of distinct paths connecting entities (more paths = stronger signal)

Weights start at `0.4 / 0.3 / 0.3` and are tuned empirically. The graph weight should be adjustable via config without code changes.

**Confidence:** MEDIUM -- scoring weights need empirical tuning. The architecture pattern is well-established in GraphRAG literature.

---

### 6. Graph Explorer UI (Stretch Goal)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| react-force-graph-2d | ^1.48 | Interactive graph visualization | Canvas-based rendering, handles hundreds of nodes performantly. More React-native than D3 direct manipulation. 2D sufficient for entity-relationship explorer. |

**Integration with Next.js 15:**

Must use dynamic import with `ssr: false` due to ESM/Canvas incompatibility with server-side rendering (verified via GitHub Issue #352):

```tsx
import dynamic from 'next/dynamic'

const ForceGraph = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => <GraphSkeleton />,
})
```

**Do NOT use:**

| Library | Why Not |
|---|---|
| Cytoscape.js | More powerful but heavier API surface. Overkill for "explore connections around a ticket" use case. |
| D3.js directly | DOM manipulation conflicts with React's virtual DOM. react-force-graph already wraps D3's force simulation. |
| react-force-graph (3D variant) | 3D adds WebGL/Three.js dependency and visual complexity without UX benefit for this use case. |

**Confidence:** HIGH -- react-force-graph-2d v1.48.2 actively maintained (updated Feb 2026). Next.js SSR workaround verified.

---

## Docker Compose Addition

```yaml
# Addition to docker-compose.yml for local development
services:
  age:
    image: apache/age:PG16_latest
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: contextos_graph
      POSTGRES_PASSWORD: ${AGE_DB_PASSWORD}
      POSTGRES_DB: context_graph
    volumes:
      - age_data:/var/lib/postgresql/data
      - ./graph/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U contextos_graph"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  age_data:
```

```sql
-- graph/init.sql -- run once on container creation
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT create_graph('context_graph');
```

For production: deploy the AGE container as a separate Railway service using a custom Dockerfile, or use a VPS with docker-compose. Railway supports custom Docker image deployments (pattern documented in their PostgreSQL extension templates like PostGIS+H3).

---

## Backend Dependency Changes

### pyproject.toml additions

```toml
dependencies = [
    # ... existing deps unchanged ...
    # ZERO new PyPI packages needed for core GraphRAG.
    # AGE queries go through existing asyncpg/SQLAlchemy.
    # Entity extraction uses existing OpenAI SDK structured output.
    # Identity resolution is custom code.
    # agtype parsing is custom code (~100 LOC).
]
```

**The key finding: zero new Python backend dependencies are needed for core GraphRAG.** The existing stack (asyncpg, SQLAlchemy async, OpenAI SDK, Pydantic) handles everything. The only infrastructure addition is the AGE Postgres container.

### Frontend dependency (stretch goal only)

```bash
pnpm add react-force-graph-2d --filter @contextos/web
```

---

## Environment Variables to Add

```env
# Graph database (AGE container)
GRAPH_DATABASE_URL=postgresql+asyncpg://contextos_graph:${AGE_DB_PASSWORD}@localhost:5433/context_graph
AGE_DB_PASSWORD=<secure-password>

# For production (Railway AGE service)
# GRAPH_DATABASE_URL=postgresql+asyncpg://contextos_graph:${AGE_DB_PASSWORD}@age-service.railway.internal:5432/context_graph
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|---|---|---|---|
| Graph DB hosting | Separate AGE container | Same Supabase instance | AGE cannot be installed on Supabase Cloud (C extension, not TLE) |
| Graph DB hosting | Separate AGE container | Neo4j | New infra category, separate query language, no pgvector co-location |
| AGE Python driver | Raw SQL via asyncpg | apache-age-python 0.0.7 | Dead project (Sep 2023), synchronous psycopg2, conflicts with async arch |
| AGE Python driver | Raw SQL via asyncpg | LangChain AGEGraph | Synchronous psycopg2, cannot use existing async session factory |
| Entity extraction | OpenAI SDK structured output | LLMGraphTransformer | Gemini incompatibility (Issue #26624, NOT_PLANNED) |
| Entity extraction | Regex + LLM | spaCy NER | 300MB models for generic entities ContextOS does not need |
| Identity resolution | Custom heuristics | Splink / dedupe | Census-scale tools for a ~10-person team. Massive dependency overkill. |
| Graph viz | react-force-graph-2d | Cytoscape.js | Heavier API, overkill for entity explorer |
| Graph storage | Cypher via AGE | Pure SQL recursive CTEs | Unreadable at 3+ hops, no variable-length path patterns |

---

## Integration Architecture Summary

```
                    Supabase Cloud (Postgres 15)
                    +-- Auth, RLS, relational tables
                    +-- pgvector embeddings
                    +-- Full-text search
                    |
FastAPI Backend ----+---- Redis (caching, existing)
                    |
                    AGE Container (Postgres 16 + AGE)
                    +-- Knowledge graph (Cypher queries)
                    +-- Entity nodes, relationship edges
                    +-- Graph traversal for retrieval
```

**Two database connections in the backend:**
1. `engine` (existing, `src/db.py`) -> Supabase for relational data, auth, embeddings, search
2. `graph_engine` (new, `src/graph_db.py`) -> AGE container for graph operations

**Data flow:**
1. Content ingested -> stored in Supabase tables (existing flow, unchanged)
2. Entity extraction pipeline (new) -> regex + LLM extract entities and relationships from ingested content
3. Graph upsert (new) -> creates/updates nodes and edges in AGE via Cypher `MERGE` statements
4. Retrieval (enhanced) -> queries both Supabase (vector + FTS) and AGE (graph traversal), blends scores
5. Synthesis (enhanced) -> context pages include decision trails, relationship paths, cross-referenced people

---

## Production Deployment Considerations

| Concern | Local Dev | Production |
|---|---|---|
| AGE database | Docker Compose service on port 5433 | Railway custom Docker service or dedicated VPS |
| Backups | Docker volume (dev only) | `pg_dump` cron job, same as any Postgres |
| Connection pooling | Direct asyncpg (5 connections) | Consider PgBouncer if connection exhaustion occurs |
| Schema migration | Init script in Docker entrypoint | Version-controlled SQL migration files (separate from Supabase migrations) |
| Monitoring | Health check in docker-compose | Sentry + structured logging (existing infra covers this) |
| Data consistency | N/A (dev) | Graph updates are eventually consistent with Supabase -- entity extraction runs async after ingestion |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|---|---|---|
| `apache-age-python` | Dead project (v0.0.7, Sep 2023), synchronous psycopg2, would conflict with async architecture | Raw SQL via existing asyncpg + custom agtype parser |
| `langchain-community` (for AGEGraph) | Synchronous psycopg2.connect(), adds large dependency tree for one class | Raw SQL via existing asyncpg |
| `langchain-experimental` (for LLMGraphTransformer) | Gemini incompatibility (Issue #26624). Would require adding a separate OpenAI model just for extraction. | OpenAI SDK structured output (already in stack) |
| `langchain-google-genai` | Adds abstraction layer over google-genai SDK without clear benefit for entity extraction use case | Existing OpenAI SDK or raw google-genai (already in deps) |
| `spacy` | 300MB+ models for generic NER. ContextOS needs domain-specific entities. | Regex for structured, LLM for semantic |
| `gliner` | Model inference dependency for entity types either trivially regex-extractable or requiring full LLM reasoning | Regex + LLM two-tier extraction |
| `splink` / `dedupe` / `recordlinkage` | Census-scale identity resolution for a ~10-50 person problem | Custom email + name matching heuristics |
| `neo4j` driver | Would require a separate Neo4j server, new infrastructure category | Apache AGE on Postgres |
| `networkx` | In-memory graph library. Graph state belongs in AGE database, not in Python process memory. | AGE Cypher queries for traversal |
| `react-force-graph` (3D) | WebGL/Three.js dependency, visual complexity without UX benefit | `react-force-graph-2d` |
| `cytoscape` / `cytoscape.js` | Heavy API surface for a stretch-goal feature | `react-force-graph-2d` |

---

## Version Compatibility Matrix

| Component | Compatible With | Notes |
|---|---|---|
| Apache AGE (PG16 image) | asyncpg (existing) | Cypher queries sent as raw SQL text. asyncpg handles `agtype` as text by default; register custom codec for automatic parsing. |
| Apache AGE (PG16 image) | SQLAlchemy 2.0 async (existing) | Execute via `session.execute(text(...))`. No ORM mapping needed for graph queries. |
| OpenAI SDK structured output | GPT-4o-mini (current model) | `response_format={"type": "json_schema", ...}` supported since SDK v1.0. |
| OpenAI SDK structured output | Gemini Flash (via OpenAI-compat endpoint) | If/when the team switches to Gemini, structured output works via `response_schema` in google-genai SDK. |
| react-force-graph-2d ^1.48 | Next.js 15, React 19 | Requires `dynamic(() => import(...), { ssr: false })`. Canvas rendering, no SSR. |
| Docker `apache/age:PG16_latest` | Docker Compose (existing) | Add as service alongside Redis. Port 5433 to avoid conflict with Supabase local (5432). |

---

## Sources

- [Apache AGE Official Site](https://age.apache.org/) -- extension overview, Cypher syntax, PG version support
- [Apache AGE Docker Image](https://hub.docker.com/r/apache/age) -- official container, PG16 support
- [Supabase Discussion #40285](https://github.com/orgs/supabase/discussions/40285) -- confirms AGE cannot be installed on Supabase Cloud
- [AGE Cypher Query Format](https://age.apache.org/age-manual/master/intro/cypher.html) -- `ag_catalog.cypher()` function syntax, agtype return format
- [postgres-age-pgvector on GitHub](https://github.com/sohamthakurdesai/postgres-age-pgvector) -- confirms AGE + pgvector co-location in single container
- [apache-age-python on PyPI](https://pypi.org/project/apache-age-python/) -- v0.0.7, last updated Sep 2023
- [LangChain AGEGraph](https://python.langchain.com/api_reference/community/graphs/langchain_community.graphs.age_graph.AGEGraph.html) -- uses psycopg2 (sync)
- [LLMGraphTransformer Gemini Issue #26624](https://github.com/langchain-ai/langchain/issues/26624) -- known incompatibility, closed NOT_PLANNED
- [Gemini Structured Output Docs](https://ai.google.dev/gemini-api/docs/structured-output) -- Pydantic response_schema support
- [react-force-graph GitHub](https://github.com/vasturiano/react-force-graph) -- v1.48.2, updated Feb 2026
- [react-force-graph Next.js Issue #352](https://github.com/vasturiano/react-force-graph/issues/352) -- SSR workaround with dynamic import
- [asyncpg Custom Type Codecs](https://magicstack.github.io/asyncpg/current/usage.html) -- `set_type_codec()` for custom types
- [Railway PostgreSQL Docs](https://docs.railway.com/databases/postgresql) -- custom Docker image deployment
- [postgres-graph-rag](https://github.com/h4gen/postgres-graph-rag) -- v0.1.2, early-stage, interesting pattern reference
- [Splink](https://moj-analytical-services.github.io/splink/index.html) -- v4.0.7, census-scale probabilistic linkage
- [GLiNER on PyPI](https://pypi.org/project/gliner/) -- v0.2.25, zero-shot NER framework

---
*Stack research for: ContextOS v1.2 GraphRAG milestone (knowledge graph, entity extraction, identity resolution, graph-enhanced retrieval)*
*Researched: 2026-03-06*
