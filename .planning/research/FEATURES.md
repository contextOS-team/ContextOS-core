# Feature Landscape

**Domain:** GraphRAG knowledge graph layer for developer context tool
**Researched:** 2026-03-06
**Milestone:** v1.2 GraphRAG (subsequent milestone -- adds graph layer to existing ContextOS)

---

## Context: What Exists vs. What's New

ContextOS already has a mature retrieval pipeline: hybrid search (pgvector cosine similarity + full-text via tsvector), multi-signal linking (explicit references at weight 1.0 + hybrid search at weight 0.8), and LLM synthesis producing 7-section context pages. The existing `find_related_content()` function in `linking.py` merges scored results from explicit refs and hybrid search, feeding ranked items into Gemini Flash for synthesis.

The GraphRAG layer adds a THIRD retrieval signal: relationship-aware graph traversal via Apache AGE. It does NOT replace existing retrieval -- it extends it with multi-hop connections that similarity search cannot find ("Who discussed the decision that affects this ticket?" requires traversal, not embedding distance).

---

## Table Stakes

Features the GraphRAG layer must have to justify its existence. Without these, the graph layer adds complexity with no payoff.

| Feature | Why Expected | Complexity | Dependencies on Existing | Notes |
|---------|--------------|------------|--------------------------|-------|
| Knowledge graph schema (Apache AGE) | Foundation for everything else. Without nodes and edges in the DB, there is no graph. | Medium | Supabase Postgres (existing), requires AGE extension install | AGE uses openCypher syntax. Runs inside Postgres -- no new infrastructure. Must define entity types (Person, Decision, Ticket, PullRequest, CodeChunk, SlackThread, NotionPage, Meeting) and relationship types (AUTHORED, DISCUSSED_IN, DECIDED_BY, AFFECTS, MENTIONS, IMPLEMENTS, etc.) |
| Rule-based entity extraction for structured data | Ticket IDs (CON-16), @mentions, PR numbers (#142), file paths, channel references -- these are deterministic patterns that regex handles perfectly. LLM extraction for these is wasteful and less accurate. | Low | Linear tickets, Slack messages, GitHub PRs, Notion pages (all existing tables) | Regex/pattern matching is 100% deterministic, zero-cost, auditable. Run on every ingested record during webhook/sync processing. Produces graph edges immediately. The rule-based vs LLM split is well-established: deterministic NLP for structure, LLMs for reasoning. |
| LLM-based entity extraction for semantic entities | Decisions, rationale, blockers, requirements, architectural choices -- these can only be identified by understanding natural language context. | High | LLM client (existing Gemini Flash via llm_client.py), source content from all integrations | The expensive part. Must batch efficiently. Use Gemini Flash (cheap, fast). Extract structured JSON with entities + relationships. Research shows 60-85% accuracy is typical for LLM entity extraction -- accept imperfection. Microsoft GraphRAG uses multi-turn "gleanings" to improve recall but this adds cost. |
| Cross-source identity resolution | Unify "Daulet" in Slack, "daulet-ash" on GitHub, "Daulet Ashikbayev" in Linear, and "Daulet" in meeting transcripts into ONE Person node. Without this, person references in the graph are fragmented and useless. | Medium | All integration data (existing), user profile metadata from each service's API | Start deterministic: email matching across platforms (Slack users.lookupByEmail API, GitHub user profile emails, Linear member emails). Fall back to fuzzy display name matching with LLM confirmation only for ambiguous cases. Build a `person_identities` mapping table linking platform-specific IDs to canonical Person nodes. |
| Graph-enhanced retrieval (blend with hybrid search) | The entire point of the milestone: find multi-hop connections that vector + full-text search misses. "Who discussed this decision?" or "What other tickets does this architectural choice affect?" require traversal, not cosine similarity. | High | Existing `hybrid_search()` SQL function, existing `find_related_content()` in linking.py, embeddings table | Must be ADDITIVE, not a replacement. Graph results become a new signal (WEIGHT_GRAPH = 0.6) blended into the existing weighted scoring in linking.py. Graph traversal via AGE Cypher queries returns scored results merged alongside explicit refs (1.0) and hybrid search (0.8). |
| Updated synthesis prompts | Context pages must visibly improve. If the graph exists but context pages look identical, the feature failed. | Medium | Existing synthesis.py, existing SYNTHESIS_TEMPLATE (7 sections) | Add decision trail data, relationship paths, and cross-referenced people to the prompt input. Modify `_format_related_content()` to format graph traversal results distinctly (show relationship paths: "Decision -> discussed in -> Slack thread -> mentioned by -> Person"). The LLM synthesizes graph context alongside existing signals. |

---

## Differentiators

Features that make the GraphRAG layer genuinely valuable beyond basic graph infrastructure. Not strictly required for MVP, but these are what justify the milestone investment.

| Feature | Value Proposition | Complexity | Dependencies on Existing | Notes |
|---------|-------------------|------------|--------------------------|-------|
| Decision extraction and linking | "The decision to use Apache AGE was made by Dulat in #arch-decisions on Feb 28, then referenced in ticket CON-32 and documented in the Architecture Notion page." Decisions are the single most valuable semantic entity for engineering context. No competing tool tracks decision provenance across Slack + meetings + tickets. | High | Slack messages, meeting transcripts, Linear comments (all existing tables) | Extract: what was decided, who decided, where discussed, what ticket/feature it affects. Link decisions bidirectionally to tickets. This IS the differentiator for ContextOS -- cross-tool decision trails that no other product does. |
| Code-to-discussion linking | Connect code chunks to the Slack conversations and tickets that motivated them. "This function was discussed in #backend on Feb 15 and implemented in PR #87 for CON-21." | High | code_chunks table (existing from Phase 12), GitHub PRs (existing), Slack messages (existing) | Requires matching: PR descriptions mentioning tickets, Slack messages mentioning file paths or function names, commit messages referencing issues. The multi-signal linking pattern already exists in linking.py -- extend it with graph edges. |
| Multi-hop relationship traversal for context | Answer queries impossible with vector search: "What other tickets are affected by the same decision?" or "Who else worked on code related to this feature?" or "What was discussed about this API before it was implemented?" | High | Knowledge graph schema (this milestone), populated graph data | 2-3 hop traversals via Cypher: Ticket->Decision->OtherTickets, Person->PRs->RelatedTickets, Code->Discussion->Requirements. Results feed into context page generation as "Related Context" signals with relationship path explanations. |
| Person-centric context aggregation | "Daulet has been involved in 12 tickets, authored 3 architectural decisions, and submitted 47 PR reviews this month." Person nodes become a lens for understanding team knowledge distribution and expertise. | Medium | Identity resolution (this milestone), all existing source data | Emerges naturally from identity resolution + graph edges. Simple Cypher: MATCH (p:Person)-[r]->(n) RETURN type(r), count(r). Surface in context pages under the "Key People" section with cross-reference counts. |
| Graph explorer UI | Visual graph view in the dashboard where users explore entity connections. Click a ticket node, see connected decisions, people, PRs, Slack threads radiating outward. | High | Frontend (Next.js/React, existing), graph data API endpoint (this milestone) | Stretch goal per PROJECT.md. Use reagraph (WebGL, React-native, maintained) or react-force-graph. Start with a simple force-directed node-link diagram. Backend: GET /api/graph/neighborhood/{entity_type}/{entity_id} returns subgraph JSON (nodes + edges). Do NOT build a full graph visualization product. |

---

## Anti-Features

Features to explicitly NOT build. These are tempting distractions that would derail the milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full Microsoft GraphRAG pipeline (community detection + Leiden clustering + community reports) | Massive overkill. Microsoft GraphRAG is designed for corpus-scale summarization of thousands of unstructured documents. ContextOS has structured data from known sources (tickets, messages, PRs) -- not a raw document corpus. Community detection via Leiden adds weeks of work for negligible value at this data scale (hundreds to low-thousands of entities). | Build a simpler property graph with typed entities and relationships. Skip Leiden clustering entirely. The graph value comes from entity linking and relationship traversal, not from community summarization. |
| Replace existing hybrid search with graph-only retrieval | The existing hybrid_search() function works well for semantic similarity. Graph retrieval has different strengths (relationships, multi-hop) but worse recall for fuzzy semantic matching. Replacing would regress context page quality for queries that work fine today. | Blend graph as a THIRD signal alongside vector + full-text. Add WEIGHT_GRAPH constant in linking.py (start at 0.6) and merge graph results into the existing find_related_content() pipeline. Graph supplements, never replaces. |
| Real-time graph updates on every webhook event | Processing every Slack message through LLM entity extraction in real-time would burn API budget and add latency to webhook handlers that must respond quickly. | Two-tier extraction: rule-based extraction (regex for structured patterns) runs inline during ingestion (zero cost, instant). LLM semantic extraction queues records for batch processing via Redis Streams (same pattern as existing embedding pipeline). |
| Neo4j or separate graph database | Adding a separate database doubles operational complexity, requires bidirectional data sync between Postgres and the graph DB, and contradicts the "stay in Supabase Postgres" constraint. Neo4j is purpose-built for graphs but is a different infrastructure dependency. | Apache AGE extension on existing Postgres. Single database, single backup, single connection pool. AGE supports openCypher queries natively. Performance is more than sufficient at this scale (~thousands of nodes, not millions). |
| LLM entity extraction for structured references | Using Gemini/Claude to extract ticket IDs, PR numbers, @mentions from messages is wasteful. These are deterministic patterns with known formats. LLMs produce variable outputs for identical inputs -- unacceptable for pattern matching. | Regex extractors: `CON-\d+` for ticket IDs, `#\d+` for PR numbers, `<@[A-Z0-9]+>` for Slack mentions, file path patterns for code references. 100% accurate, zero cost, instant. Reserve LLM budget exclusively for semantic entities (decisions, rationale, blockers). |
| Entity deduplication via ML/embedding similarity | Building an ML model or using embedding distance to detect duplicate entities is premature. The entity space is small (dozens of people, hundreds of decisions at most) and well-bounded by the platforms. | Deterministic dedup first: email matching for people, ticket identifier matching for issues, URL/number matching for PRs. LLM confirmation only for the small number of genuinely ambiguous fuzzy matches. |
| Full NLP pipeline (SpaCy, Stanza, coreference resolution) | Academic-grade NLP pipelines are heavy dependencies (hundreds of MB) that solve problems the LLM handles better in a single structured output call. Adding SpaCy for NER when Gemini Flash already does it is duplicate work. | Use LLM structured output for semantic extraction. One prompt extracts entities + relationships + resolves coreferences. The LLM handles "he said the decision was..." -> "Daulet said the decision was..." naturally in context. |
| Graph versioning / temporal graph | Tracking how the graph changes over time (edge creation/deletion timestamps, graph snapshots, bitemporal queries) adds significant schema complexity for minimal v1 value. | Timestamp edges with `created_at`. Query "relationships created before date X" with simple WHERE clauses if needed later. Full temporal graph semantics are a research project, not a product feature. |
| LazyGraphRAG (defer extraction to query time) | Microsoft's LazyGraphRAG (June 2025) defers community summarization to query time, reducing indexing cost by 99%. Interesting for massive corpora but adds query latency and complexity. ContextOS processes structured data from known integrations -- indexing cost is already bounded. | Pre-extract at ingestion time (rule-based) and in batches (LLM). The data volume is manageable. Query-time extraction adds latency to context page generation, which users experience directly. |

---

## Feature Dependencies

```
Rule-based extraction -----> Knowledge graph schema (AGE)
                                    |
LLM entity extraction ------------>|
                                    |
Cross-source identity resolution -->|
                                    |
                                    v
                        Graph populated with nodes + edges
                                    |
                    +---------------+---------------+
                    |               |               |
                    v               v               v
        Decision extraction   Code-to-discussion   Multi-hop traversal
                    |               |               |
                    +---------------+---------------+
                                    |
                                    v
                        Graph-enhanced retrieval
                        (blend into find_related_content)
                                    |
                                    v
                        Updated synthesis prompts
                        (context pages improve)
                                    |
                                    v
                        Graph explorer UI (stretch)
```

**Critical path:** Schema -> Extraction (rule-based + LLM) + Identity Resolution -> Graph-enhanced retrieval -> Updated synthesis. Everything else is additive.

**Parallelizable work:**
- Rule-based extraction and LLM extraction can be developed in parallel (different code paths, same destination graph)
- Identity resolution can be developed alongside extraction (writes to same graph, independent logic)
- Decision extraction and code-to-discussion linking are independent differentiators that can be built in any order after the graph is populated

**Key integration points with existing code:**
- `linking.py:find_related_content()` -- add graph results as third signal alongside explicit refs and hybrid search
- `embedding.py:SOURCE_TYPE_MAP` -- no changes needed (graph reads from same source tables)
- `synthesis.py:SYNTHESIS_TEMPLATE` -- modify to accept and format graph context data
- `synthesis.py:_format_related_content()` -- extend to format graph relationship paths distinctly
- Webhook handlers (linear_webhook.py, slack_events.py, github_webhook.py, notion_webhook.py) -- add inline rule-based extraction calls during ingestion

---

## Entity Type Taxonomy

Based on the domain (engineering team context across Linear, Slack, GitHub, Notion, Fathom), these are the entity types for the knowledge graph.

### Node Types

| Node Type | Source(s) | Extraction Method | Graph Mapping |
|-----------|-----------|-------------------|---------------|
| Person | Linear members, Slack users, GitHub users, Fathom speakers | Identity resolution (email + fuzzy name) | Canonical identity. One node per real person, with `identities` property listing platform-specific IDs |
| Decision | Slack messages, meeting transcripts, Linear comments | LLM extraction | Extracted semantic entity. Properties: what_decided, rationale, date, confidence_score |
| Ticket | Linear tickets table | Direct mapping (1:1 from linear_tickets) | Already-existing structured data, promoted to graph node |
| PullRequest | GitHub PRs table | Direct mapping (1:1 from github_pull_requests) | Already-existing structured data, promoted to graph node |
| CodeChunk | code_chunks table (Phase 12) | Direct mapping (1:1 from code_chunks) | Already-existing structured data, promoted to graph node |
| SlackThread | Slack messages grouped by thread_ts | Grouping rule (same channel + thread_ts) | Aggregation of individual messages into conversation units |
| NotionPage | Notion pages table | Direct mapping (1:1 from notion_pages) | Already-existing structured data, promoted to graph node |
| Meeting | Meeting transcripts table | Direct mapping (1:1 from meeting_transcripts) | Already-existing structured data, promoted to graph node |

### Edge Types

| Edge Type | From -> To | Extraction Method | Description |
|-----------|-----------|-------------------|-------------|
| AUTHORED | Person -> Ticket, PR, SlackThread, NotionPage | Rule-based (author/creator fields in source tables) | Person created or owns the artifact |
| REVIEWED | Person -> PullRequest | Rule-based (review.author field) | Person reviewed the PR |
| DISCUSSED_IN | Decision -> SlackThread, Meeting | LLM extraction | Decision was discussed in this conversation |
| DECIDED_BY | Decision -> Person | LLM extraction | Person made or drove the decision |
| AFFECTS | Decision -> Ticket | LLM extraction | Decision impacts this ticket/feature |
| MENTIONS | SlackThread -> Ticket, PR, CodeChunk | Rule-based (regex: CON-\d+, #\d+, file paths) | Message explicitly references the artifact |
| IMPLEMENTS | PullRequest -> Ticket | Rule-based (PR description/branch name containing ticket ID) | PR implements this ticket |
| REFERENCES | NotionPage -> Ticket, Decision | Rule-based + LLM | Documentation references the entity |
| PARTICIPATED_IN | Person -> Meeting | Rule-based (transcript speaker names) | Person spoke in this meeting |
| MODIFIES | PullRequest -> CodeChunk | Rule-based (diff file paths matching code_chunks) | PR changes this code |
| ASSIGNED_TO | Ticket -> Person | Rule-based (ticket.assignee field) | Ticket is assigned to this person |
| RELATED_TO | Ticket -> Ticket | Rule-based (Linear relations API) + LLM | Tickets are related (blocks, blocked-by, related) |

---

## How Each Feature Actually Works

### 1. Knowledge Graph Schema (AGE)

Apache AGE adds graph capabilities to PostgreSQL via an extension. It stores graph data in dedicated catalog tables but queries are run through SQL with embedded Cypher via the `ag_catalog.cypher()` function.

**Expected behavior:**
- Install AGE extension in Supabase Postgres (requires `CREATE EXTENSION age`)
- Create a graph: `SELECT ag_catalog.create_graph('contextos')`
- Create vertex labels (node types): `SELECT ag_catalog.create_vlabel('contextos', 'Person')`
- Create edge labels: `SELECT ag_catalog.create_elabel('contextos', 'AUTHORED')`
- Insert nodes: `SELECT * FROM ag_catalog.cypher('contextos', $$ CREATE (p:Person {name: 'Daulet', email: 'daulet@...', canonical_id: '...'}) $$) AS (v ag_catalog.agtype)`
- Query: `SELECT * FROM ag_catalog.cypher('contextos', $$ MATCH (t:Ticket {identifier: 'CON-16'})<-[:AFFECTS]-(d:Decision)-[:DISCUSSED_IN]->(s:SlackThread) RETURN d, s $$) AS (d ag_catalog.agtype, s ag_catalog.agtype)`
- All existing Postgres RLS, backups, connections continue to work unchanged

### 2. Rule-Based Entity Extraction

Runs inline during webhook/sync ingestion. Zero latency impact beyond regex matching.

**Expected behavior:**
- When a Slack message is ingested, extract: ticket references (CON-\d+), PR references (#\d+ in context of repo discussion), @mentions (map to Person nodes via identity resolution), file paths, URLs
- When a PR is ingested, extract: ticket references from title/description/branch name, file paths modified (link to CodeChunks), reviewer assignments
- When a meeting transcript segment is ingested, extract: speaker names (map to Person nodes), ticket references mentioned in speech
- Each extraction creates graph edges immediately (e.g., SlackThread --MENTIONS--> Ticket)
- Extraction is idempotent: re-processing a message does not create duplicate edges

### 3. LLM Entity Extraction

Batch processing via Redis Streams. Processes queued content in background workers.

**Expected behavior:**
- Source content (Slack threads, meeting transcript segments, ticket descriptions with comments) is queued for extraction when ingested
- Worker pulls batch, constructs prompt: "Extract entities (decisions, requirements, blockers, people) and relationships from this content. Return structured JSON."
- Prompt includes domain-specific examples (few-shot) tuned for engineering context
- LLM returns structured JSON: `{entities: [{type: "Decision", description: "Use AGE instead of Neo4j", confidence: 0.85}], relationships: [{from: "Decision:use-age", to: "Ticket:CON-32", type: "AFFECTS"}]}`
- Worker writes entities and relationships to AGE graph
- Extraction runs with Gemini Flash (cheapest option, ~$0.075/1M input tokens)
- Content hash deduplication prevents re-extracting unchanged content (same pattern as embedding service)

### 4. Cross-Source Identity Resolution

Maps platform-specific user identities to canonical Person nodes.

**Expected behavior:**
- On first run (backfill): fetch user lists from Linear, Slack, GitHub, Fathom APIs
- Match by email (deterministic, highest confidence): Slack users.list provides email, Linear members API provides email, GitHub users API provides email
- For matches without email overlap: fuzzy match on display name + LLM confirmation ("Is 'daulet-ash' on GitHub likely the same person as 'Daulet Ashikbayev' on Linear?")
- Store in `person_identities` table: canonical_person_id, platform, platform_user_id, display_name, email, confidence
- On subsequent ingestion: when a Slack message arrives with user_id U12345, look up the canonical Person node and create edges accordingly
- When a new platform user appears (new team member, external collaborator), attempt automatic resolution, flag unresolved for manual confirmation

### 5. Graph-Enhanced Retrieval

Cypher queries retrieve graph-connected content, scored and blended with existing signals.

**Expected behavior:**
- When `find_related_content()` runs for a ticket, additionally execute graph neighborhood queries:
  - 1-hop: Direct connections (Person who authored, Decision that affects, PR that implements)
  - 2-hop: "Decisions affecting this ticket -> other tickets affected by those same decisions"
  - 2-hop: "People who worked on this ticket -> other tickets they worked on recently"
  - 2-hop: "Code modified by PRs for this ticket -> Slack discussions mentioning that code"
- Graph results scored by hop distance (1-hop = 1.0, 2-hop = 0.7, 3-hop = 0.4) and relationship type relevance
- Scored graph results merged into linking.py's merged dictionary with WEIGHT_GRAPH multiplier (start at 0.6, tune empirically)
- Graph retrieval adds ~50-200ms for 2-hop queries at this data scale (thousands of nodes) -- acceptable

### 6. Updated Synthesis Prompts

Context pages include decision trails, relationship paths, and cross-referenced people.

**Expected behavior:**
- `_format_related_content()` extended with a new section for graph-derived context
- Graph results formatted distinctly: show relationship paths, not just content snippets
  - "Decision: 'Use Apache AGE for knowledge graph' (made by Dulat, discussed in #architecture on Feb 28, affects tickets CON-32, CON-35)"
  - "Related via shared decision: CON-35 (also affected by the AGE decision)"
- Synthesis template updated to instruct LLM: "Use the relationship paths to explain WHY things are connected, not just THAT they are connected"
- Context pages gain: decision trails in "Background & Decisions" section, cross-referenced people in "Key People" section with platform links, relationship-based related work in "Related Work" section

### 7. Decision Extraction (Differentiator)

Identifies and links decisions from unstructured communication.

**Expected behavior:**
- LLM prompt specifically targets decision language: "we decided", "the plan is", "let's go with", "after discussing, we'll", consensus statements, action items with rationale
- Each Decision node stores: description (what was decided), rationale (why), source_message_id (where it was stated), date, confidence_score, status (proposed/accepted/superseded)
- Decision nodes linked to: Person (DECIDED_BY), SlackThread/Meeting (DISCUSSED_IN), Ticket (AFFECTS)
- Decisions surface prominently in context pages: "This ticket is affected by 2 decisions: [decision 1 with provenance], [decision 2 with provenance]"
- This is ContextOS's unique differentiator. No competing tool (Linear, Notion, Confluence, Glean) traces decision provenance across communication channels to tickets.

### 8. Code-to-Discussion Linking (Differentiator)

Connects code artifacts to the conversations and decisions that motivated them.

**Expected behavior:**
- When a Slack message mentions a file path (`src/services/linking.py`) or function name (`find_related_content`), create MENTIONS edge to matching CodeChunk
- When a PR implements a ticket (IMPLEMENTS edge), and that ticket was discussed in Slack threads (MENTIONED_IN edges), transitively link the PR's changed code to those discussions
- In context pages, "Relevant Code" section enriched: "This function was discussed in #backend thread [link] before being implemented in PR #87 [link]"
- Uses existing code_chunks from Phase 12 -- no re-parsing needed

---

## Complexity Estimates

| Feature | Backend (Python/SQL) | Frontend (React) | LLM Calls | Total Effort |
|---------|---------------------|-------------------|-----------|-------------|
| AGE schema + migration | 2-3 days | None | None | 2-3 days |
| Rule-based extractors | 2-3 days | None | None | 2-3 days |
| Identity resolution | 3-4 days | None | Minimal (fuzzy confirmation only) | 3-4 days |
| LLM entity extraction pipeline | 4-5 days | None | Heavy (batch, Gemini Flash) | 4-5 days |
| Decision extraction | 2-3 days (built on LLM pipeline) | None | Included in extraction | 2-3 days |
| Code-to-discussion linking | 2-3 days | None | Minimal | 2-3 days |
| Graph-enhanced retrieval | 3-4 days | None | None | 3-4 days |
| Updated synthesis prompts | 1-2 days | None | Included in generation | 1-2 days |
| Graph explorer UI | 1 day (API endpoint) | 4-5 days (visualization) | None | 5-6 days |
| **Total MVP (items 1-8)** | **~19-25 days** | **0 days** | **Moderate** | **~19-25 days** |
| **Total with stretch (add UI)** | **~20-26 days** | **4-5 days** | **Moderate** | **~24-31 days** |

---

## MVP Recommendation

### Must Ship (table stakes -- graph layer fails without these)

1. **Knowledge graph schema** -- AGE extension, entity/relationship labels, Cypher query wrapper functions. Foundation for everything else.
2. **Rule-based entity extraction** -- Regex extractors for ticket IDs, PR numbers, @mentions, file paths, channel names. Run inline during ingestion. Cheap, immediate graph population.
3. **Cross-source identity resolution** -- Deterministic email-based matching across Linear, Slack, GitHub, Fathom. Person nodes unify identities. Without this, person references fragment uselessly.
4. **LLM entity extraction** -- Gemini Flash extracting decisions, rationale, requirements, blockers from Slack messages and meeting transcripts. Batch processing via Redis Streams. Accept 70-80% accuracy.
5. **Graph-enhanced retrieval** -- Cypher traversal queries blended as third signal into existing find_related_content(). Start with 1-2 hop neighborhood queries for a given ticket.
6. **Updated synthesis prompts** -- Pass graph context (decision trails, relationship paths, key people with cross-references) into the LLM prompt. Context pages must visibly improve.

### Should Ship (differentiators that justify the milestone)

7. **Decision extraction and linking** -- The highest-value semantic entity. Decisions traced from Slack thread to meeting transcript to ticket. This is ContextOS's unique value proposition and should be prioritized.
8. **Code-to-discussion linking** -- Connect existing code_chunks to conversations and tickets. Extends Phase 12 investment and completes the cross-tool story.

### Defer

9. **Graph explorer UI** -- Backend-first. The API endpoint for subgraph retrieval should ship, but the React visualization component is stretch. Use reagraph if built. Do not block the milestone on UI work.
10. **Person-centric aggregation views** -- Emerges from graph data naturally, but dedicated UI/API can wait. The value shows up organically in context pages via updated synthesis prompts.
11. **Community detection / clustering** -- Not needed at ContextOS's data scale. Revisit only if graph grows past 100K nodes (unlikely in the medium term).

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Risk | Priority |
|---------|------------|---------------------|------|----------|
| Knowledge graph schema (AGE) | FOUNDATIONAL | LOW-MEDIUM | Medium (AGE in Supabase) | P0 |
| Rule-based entity extraction | HIGH | LOW | Low | P0 |
| Cross-source identity resolution | HIGH | MEDIUM | Low | P0 |
| LLM entity extraction pipeline | HIGH | HIGH | Medium (accuracy) | P1 |
| Graph-enhanced retrieval | HIGH | HIGH | Medium (scoring tuning) | P1 |
| Updated synthesis prompts | HIGH | LOW-MEDIUM | Low | P1 |
| Decision extraction + linking | VERY HIGH | MEDIUM | Medium (LLM accuracy) | P1 |
| Code-to-discussion linking | MEDIUM-HIGH | MEDIUM | Low | P2 |
| Graph explorer UI (API endpoint) | MEDIUM | LOW | Low | P2 |
| Graph explorer UI (frontend) | MEDIUM | HIGH | Medium (UX scope creep) | P3 (stretch) |

---

## Sources

- [Microsoft GraphRAG Methods](https://microsoft.github.io/graphrag/index/methods/) -- Entity extraction pipeline architecture, prompt structure, gleanings (HIGH confidence)
- [Microsoft GraphRAG Dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/) -- 6-stage indexing pipeline: TextUnits -> Extraction -> Summarization -> Community Detection -> Reports -> Embeddings (HIGH confidence)
- [Apache AGE Project](https://age.apache.org/) -- PostgreSQL graph extension, openCypher support, ACID compliance (HIGH confidence)
- [Apache AGE GitHub](https://github.com/apache/age) -- Production maturity, Apache Top-Level Project since May 2022 (HIGH confidence)
- [Azure AGE Extension](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-age-overview) -- Cloud PostgreSQL AGE support confirmed (HIGH confidence)
- [Building Knowledge Graphs with Apache AGE](https://pub.towardsai.net/building-knowledge-graphs-with-apache-age-621b787f6926) -- Practical implementation patterns (MEDIUM confidence)
- [GraphRAG Overview - Meilisearch](https://www.meilisearch.com/blog/graph-rag) -- GraphRAG concepts, entity extraction cost (3-5x more LLM calls), accuracy ranges (MEDIUM confidence)
- [Graph-enhanced RAG - Elastic](https://www.elastic.co/search-labs/blog/rag-graph-traversal) -- Hybrid retrieval blending: vector first for broad recall, graph for structured reasoning (MEDIUM confidence)
- [GraphRAG vs Vector RAG](https://www.meilisearch.com/blog/graph-rag-vs-vector-rag) -- When graph adds value (multi-hop, relationships) vs when vector suffices (semantic similarity) (MEDIUM confidence)
- [Neo4j Multi-hop Reasoning](https://neo4j.com/blog/genai/knowledge-graph-llm-multi-hop-reasoning/) -- Multi-hop query patterns, graph traversal vs LLM chaining (MEDIUM confidence)
- [Entity Resolution Techniques](https://www.puppygraph.com/blog/entity-resolution) -- Deterministic, probabilistic, and ML-based identity resolution approaches (MEDIUM confidence)
- [Slack users.identity API](https://docs.slack.dev/reference/methods/users.identity/) -- Cross-platform identity via email lookup (HIGH confidence)
- [Why LLMs Wrong for Enterprise Entity Extraction](https://www.bitext.com/blog/why-llms-are-the-wrong-tool-for-enterprise-grade-entity-extraction/) -- Rule-based vs LLM tradeoffs: deterministic for structure, LLM for reasoning (MEDIUM confidence)
- [Datagrid: Knowledge Graphs from Slack](https://datagrid.com/blog/build-knowledge-graphs-slack-conversations-ai-agents-d16d8) -- Practical Slack-to-KG patterns, decision extraction from conversations (MEDIUM confidence)
- [reagraph - WebGL Graph for React](https://github.com/reaviz/reagraph) -- Graph visualization library for React (MEDIUM confidence)
- [Microsoft GraphRAG Auto-tuning](https://www.microsoft.com/en-us/research/blog/graphrag-auto-tuning-provides-rapid-adaptation-to-new-domains/) -- Domain-specific prompt generation for entity extraction (MEDIUM confidence)
- [Scribd find-slack-user-action](https://github.com/scribd/find-slack-user-action) -- Email-based cross-platform identity matching (Slack/GitHub) (MEDIUM confidence)

---

*Feature research for: ContextOS v1.2 GraphRAG knowledge graph layer*
*Researched: 2026-03-06*
