# Domain Pitfalls

**Domain:** GraphRAG knowledge graph layer added to existing RAG application (ContextOS v1.2)
**Researched:** 2026-03-06
**Overall confidence:** HIGH (infrastructure blocker verified with official sources; extraction and retrieval pitfalls verified across multiple independent sources)

---

## Critical Pitfalls

Mistakes that cause rewrites, blocked deployments, or major quality regressions.

---

### Pitfall 1: Apache AGE Is Not Available on Supabase Cloud

**What goes wrong:** The team plans the entire graph layer around Apache AGE's Cypher query language and graph storage, then discovers it cannot be installed on Supabase Cloud. Apache AGE is not in Supabase's supported extension list (only ~64 extensions are available on Cloud), it is a C extension (not a Trusted Language Extension), and the Nix-based Supabase Postgres images reject manually compiled `.so` files due to ABI mismatches.

**Why it happens:** Apache AGE markets itself as "just a Postgres extension" which implies drop-in compatibility. The PROJECT.md decision says "Apache AGE (Postgres) for knowledge graph -- stays in Supabase, no new infrastructure." This assumption is wrong for Supabase Cloud.

**Consequences:**
- Entire milestone is blocked at day 1 if not caught
- Workarounds (dual databases with `postgres_fdw`, custom Docker forks of Supabase Postgres, or self-hosting) all violate the project's "Hosting: Supabase Cloud" constraint and add massive operational complexity
- If the team pivots mid-milestone to a different approach, all Cypher queries, graph schema, and traversal code must be rewritten

**Prevention:**
1. **Do not use Apache AGE.** Design the graph layer using plain PostgreSQL tables (nodes + edges) with recursive CTEs for traversal. This works on Supabase Cloud with zero extension requirements.
2. Use two tables: `graph_nodes` (id, workspace_id, entity_type, name, properties JSONB, source_type, source_id) and `graph_edges` (id, workspace_id, source_node_id, target_node_id, relationship_type, properties JSONB, source_type, source_id). Add composite indexes on (workspace_id, entity_type) and (workspace_id, relationship_type).
3. Write traversal as PostgreSQL recursive CTEs with depth limits (max 3-4 hops for this domain). This is sufficient for engineering context graphs where relationships are shallow.
4. If Cypher syntax is desired later, consider migrating to a self-hosted Postgres with AGE -- but only after validating the plain-SQL approach is a bottleneck.

**Detection:** Test `CREATE EXTENSION age;` on your Supabase Cloud project. It will fail immediately.

**Affected phase:** Graph Schema (must be addressed before any other work begins)

**Confidence:** HIGH -- verified via Supabase extensions docs, GitHub Discussion #40285, and the Supabase Cloud extension list which does not include Apache AGE.

**Sources:**
- [Supabase Extensions List](https://supabase.com/docs/guides/database/extensions) -- AGE not listed
- [Supabase Discussion #40285: How to Install Apache AGE Extension?](https://github.com/orgs/supabase/discussions/40285) -- confirmed not possible, dual-DB workaround described
- [Apache AGE PG17 Issue #2111](https://github.com/apache/age/issues/2111) -- core R&D team eliminated Oct 2024
- [Apache AGE Status Discussion #2150](https://github.com/apache/age/discussions/2150) -- project maintenance slowed significantly

---

### Pitfall 2: Apache AGE Project Health Risk (Even If Self-Hosted)

**What goes wrong:** Even if the team bypasses Supabase Cloud and self-hosts Postgres with AGE, the project depends on an extension whose core R&D team was fired in October 2024. Development has slowed to volunteer pace. PostgreSQL 17 support (AGE 1.6.0) was only released in late 2025 after months of delay. Future PostgreSQL version compatibility is uncertain.

**Why it happens:** Apache AGE graduated to a Top-Level ASF project in 2022 during active corporate sponsorship from Bitnine/AGEDB. That sponsorship ended abruptly, and the remaining volunteer contributors cannot match the previous development velocity.

**Consequences:**
- When Supabase upgrades its Postgres version, there may be no compatible AGE release for months or ever
- Security patches and bug fixes are slower
- Building a production dependency on an extension with uncertain maintenance is a long-term liability

**Prevention:**
- Use plain PostgreSQL tables for the graph layer (see Pitfall 1 prevention). This has zero external extension dependencies and will work on every PostgreSQL version.
- If graph query complexity grows beyond what recursive CTEs can handle, evaluate SQL/PGQ (the SQL:2023 standard for property graphs) when PostgreSQL natively supports it, rather than depending on AGE.

**Detection:** Monitor the AGE GitHub repository activity. If release cadence drops below one release per 6 months, consider it a red flag.

**Affected phase:** Graph Schema (architecture decision)

**Confidence:** HIGH -- the R&D team dismissal is confirmed by AGE project leadership in GitHub Discussion #2150.

**Sources:**
- [Apache AGE Status Discussion #2150](https://github.com/apache/age/discussions/2150)
- [Apache AGE PG17 Issue #2111](https://github.com/apache/age/issues/2111)

---

### Pitfall 3: LLM Entity Extraction Is Non-Deterministic and Hallucinates

**What goes wrong:** The team uses LLM calls (Gemini Flash) for semantic entity extraction (decisions, people identity resolution) and discovers that: (a) the same input text produces different entities across runs, (b) the LLM hallucinates entities not present in the source text, (c) minor text variations (a single apostrophe, a reordered sentence) cause unrelated entities to appear or disappear, and (d) output format violations (broken JSON, inconsistent field names) corrupt the extraction pipeline.

**Why it happens:** LLMs are probabilistic. Even at temperature 0, they exhibit non-deterministic behavior across runs. GDELT Project research demonstrated that correcting "NATOs" to "NATO's" caused Latvia and China to disappear from entity lists while hallucinated entries like "Eastern_Flank_of_NATO" appeared. Enterprise systems require deterministic, auditable extraction.

**Consequences:**
- Graph nodes accumulate hallucinated entities that don't exist in source data
- Duplicate entities proliferate (e.g., "Daulet", "Daulet Ashikbayev", "daulet", "DA" all as separate nodes)
- Identity resolution becomes impossible when the extraction layer is already producing inconsistent entity names
- Silent data corruption: bad entities in the graph produce bad context pages, and nobody notices until users lose trust

**Prevention:**
1. **Rule-based first, LLM second, always.** The PROJECT.md decision ("rule-based + LLM entity extraction") is correct but the ordering and boundary must be strict:
   - Rule-based extractors handle: @mentions, ticket IDs (ENG-123), PR numbers (#456), file paths, channel names, URLs, email addresses. These are deterministic and cheap.
   - LLM extractors handle ONLY: decision identification from natural language, and semantic classification of ambiguous entities. Never use LLM for structured data extraction.
2. **Validate LLM output against source text.** Every entity the LLM extracts must have a span match (exact or fuzzy) in the source text. If the entity string is not present in the input, discard it.
3. **Use structured output (JSON mode) with strict schema validation.** Define a Pydantic schema for extraction output. Parse with error handling. Retry once on parse failure, then skip the source document and log the failure.
4. **Batch and deduplicate before graph insertion.** Extract entities from a document, normalize names (lowercase, trim whitespace, canonical forms), deduplicate within the batch, THEN insert. Never insert raw LLM output directly into the graph.
5. **Temperature 0 + seed parameter** if the model supports it (Gemini does not guarantee determinism even at temp 0, but it reduces variance).

**Detection:**
- Run the same extraction prompt on the same input 5 times. If entity lists differ, the pipeline is non-deterministic -- add validation.
- Monitor the `graph_nodes` table for entity count growth rate. If it grows faster than source document ingestion rate, hallucinated entities are accumulating.
- Sample 10 random LLM-extracted entities per week and verify they exist in source text.

**Affected phase:** Entity Extraction Pipeline

**Confidence:** HIGH -- GDELT Project experiments and Bitext analysis of LLM entity extraction reliability are peer-reviewed quality research.

**Sources:**
- [GDELT: LLM Entity Extraction Hallucination](https://blog.gdeltproject.org/experiments-in-entity-extraction-using-llms-hallucination-how-a-single-apostrophe-can-change-the-results/)
- [GDELT: LLM Infinite Loops & Failure Modes](https://blog.gdeltproject.org/llm-infinite-loops-failure-modes-the-current-state-of-llm-entity-extraction/)
- [Bitext: Why LLMs Are Wrong for Enterprise Entity Extraction](https://www.bitext.com/blog/why-llms-are-the-wrong-tool-for-enterprise-grade-entity-extraction/)

---

### Pitfall 4: Graph Retrieval Floods the Synthesis Prompt with Noise

**What goes wrong:** The graph-enhanced retrieval step finds many related entities and traverses multiple relationship paths, then dumps all of this context into the synthesis prompt alongside the existing vector + full-text search results. The LLM receives 15,000+ tokens of context, much of it low-relevance graph data, and synthesis quality drops instead of improving. Studies show a ~20% accuracy drop when context grows from 5 to 30 documents.

**Why it happens:** Graph traversal is expansive by nature. A person node connects to tickets, Slack messages, meetings, and code. Each of those connects to more entities. Without aggressive filtering, a 2-hop traversal from a single ticket can return hundreds of related items. The team, excited about the graph data, includes everything.

**Consequences:**
- Context pages become worse, not better, after adding GraphRAG
- LLM synthesis costs increase (more tokens = more money and latency)
- The "lost in the middle" effect: important information buried in the middle of a long context is ignored by the LLM
- Users see irrelevant relationship paths and decision trails that add noise

**Prevention:**
1. **Budget graph context tokens.** Allocate a fixed token budget for graph-derived context (e.g., 2,000 tokens max out of the total synthesis context). If graph data exceeds the budget, rank and truncate.
2. **Score graph paths by relevance.** Not all graph relationships are equal. A decision directly linked to the ticket is high-value; a person who once commented on a related ticket is low-value. Assign weights: direct edges = 1.0, 2-hop = 0.5, 3-hop = 0.25. Filter by minimum score threshold.
3. **Separate graph context from retrieval context in the prompt.** Structure the synthesis prompt with clear sections: "## Retrieved Context" (vector + FTS results) and "## Relationship Context" (graph paths). This lets the LLM treat them as different signal types.
4. **Summarize graph paths, don't enumerate them.** Instead of listing every node and edge, pre-summarize: "Decision: Use Redis for caching (decided in #eng-backend, 2026-02-15, by @daulet) -> affects ticket ENG-456". One sentence per relationship path.
5. **A/B test graph inclusion.** Generate context pages with and without graph data for the same tickets. Compare quality before shipping graph-enhanced synthesis to users.

**Detection:**
- Track synthesis prompt token count before and after graph integration. If it more than doubles, the graph context is too large.
- Compare context page quality scores (if evaluation exists) before and after graph integration.
- Check if context pages mention entities or decisions that users find irrelevant.

**Affected phase:** Graph-Enhanced Retrieval, Updated Synthesis Prompts

**Confidence:** HIGH -- context window overflow and "lost in the middle" effects are well-documented across multiple LLM research papers and practitioner reports.

**Sources:**
- [Redis: Context Window Overflow](https://redis.io/blog/context-window-overflow/)
- [Pinecone: Less is More - Why Use Retrieval](https://www.pinecone.io/blog/why-use-retrieval-instead-of-larger-context/)
- [freeCodeCamp: 5 Common RAG Failures with Knowledge Graphs](https://www.freecodecamp.org/news/how-to-solve-5-common-rag-failures-with-knowledge-graphs/)

---

## Moderate Pitfalls

Mistakes that cause significant rework or quality issues but don't block the entire milestone.

---

### Pitfall 5: Cross-Source Identity Resolution Produces False Merges

**What goes wrong:** The identity resolution system merges two different people into a single graph node because they share a first name ("Alex" on Slack = "Alex" on Linear, but they are different people). Or it creates dozens of separate nodes for the same person because their display names differ across platforms ("Daulet" on Slack, "Daulet Ashikbayev" on Linear, "daulet@company.com" in meeting transcripts, "DA" in code review shorthand).

**Why it happens:** Engineering tool ecosystems have no universal identity standard. Slack user IDs, Linear user IDs, GitHub usernames, and meeting participant names are all different identifier systems with no guaranteed overlap. Simple string matching on display names fails because: (a) names are ambiguous, (b) display names change, (c) some platforms only show first names, (d) nicknames and abbreviations are common in casual contexts.

**Consequences:**
- False merges: Context pages attribute decisions or comments to the wrong person. This destroys user trust immediately.
- False splits: The same person appears as multiple entities, fragmenting their activity graph. Graph traversal misses connections because the identity link doesn't exist.
- Over time, the graph accumulates identity errors that compound -- each new merge or split decision builds on potentially wrong earlier decisions.

**Prevention:**
1. **Anchor on platform user IDs, not display names.** Each integration (Linear, Slack, GitHub, Fathom) has a stable user ID. Store these as properties on the person node: `{linear_id: "xxx", slack_id: "yyy", github_username: "zzz"}`. Match on IDs first, names second.
2. **Build an explicit identity mapping table.** Create `identity_mappings (workspace_id, canonical_person_id, provider, external_id, display_name)`. Populate this during OAuth connection when the workspace connects Linear/Slack/GitHub -- the APIs provide team member lists with user IDs.
3. **Never auto-merge on name alone.** If two platform identities share a display name but have no ID-based match, flag them for manual review rather than auto-merging. For a 3-person founding team this is trivial; for larger teams this prevents catastrophic false merges.
4. **Start with workspace team roster, not extraction.** Pull team members from Linear and Slack APIs during integration setup. Create person nodes from this roster. Then, during entity extraction, match extracted names against the known roster rather than creating new person nodes from scratch.

**Detection:**
- Query `graph_nodes WHERE entity_type = 'person'` and count. If the count significantly exceeds the workspace team size, you have false splits.
- Sample person nodes and check if their platform IDs point to the same actual human across sources.

**Affected phase:** Cross-Source Identity Resolution

**Confidence:** HIGH -- identity resolution is a well-studied problem in data engineering. The specific challenge of cross-platform identity in engineering tools is confirmed by platform-specific API documentation showing different ID systems.

---

### Pitfall 6: Recursive CTE Graph Traversal Hits Performance Walls with RLS

**What goes wrong:** PostgreSQL recursive CTEs for graph traversal interact badly with Row Level Security policies. Every row visited during recursion triggers the RLS check (`workspace_id IN (SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid())`), and this subquery executes per-row, turning a simple 3-hop traversal into thousands of RLS evaluations. Query time goes from milliseconds to seconds.

**Why it happens:** The existing ContextOS schema uses subquery-based RLS policies on every table. These policies are evaluated per-row. In a recursive CTE that visits many nodes and edges, the RLS subquery fires on every iteration of the recursion. PostgreSQL cannot cache the RLS result efficiently when it's a subquery referencing another RLS-protected table (`workspace_members`).

**Consequences:**
- Graph queries are unacceptably slow (seconds instead of milliseconds)
- The team either disables RLS on graph tables (security risk) or accepts poor performance
- Worse: the team doesn't notice until production because local dev (Supabase local) may have different RLS behavior than Cloud

**Prevention:**
1. **Use SECURITY DEFINER functions for graph traversal.** Create a `traverse_graph(workspace_id, start_node_id, max_depth)` function with `SECURITY DEFINER`. Inside the function, the RLS check is bypassed (runs as the function owner). Validate the workspace_id parameter against the calling user's membership ONCE at the function entry point, then traverse without per-row RLS overhead.
2. **Add workspace_id as a direct column on both graph_nodes and graph_edges.** Filter by `WHERE workspace_id = $1` in every recursive step. This is a simple equality check on an indexed column, far cheaper than the RLS subquery.
3. **Benchmark graph queries with RLS enabled on Supabase Cloud** before shipping. Don't rely on local dev performance.

**Detection:**
- Run `EXPLAIN ANALYZE` on graph traversal queries with RLS enabled. Look for "SubPlan" entries inside the recursive CTE. If present, the RLS subquery is firing per-row.
- Compare query time with and without `SET LOCAL role = 'service_role'` (bypasses RLS). If there's a 10x+ difference, RLS is the bottleneck.

**Affected phase:** Graph Schema, Graph-Enhanced Retrieval

**Confidence:** MEDIUM -- the RLS + recursive CTE interaction is well-documented generically, but the specific performance impact in this schema needs benchmarking.

**Sources:**
- [Bytebase: PostgreSQL RLS Limitations and Alternatives](https://www.bytebase.com/blog/postgres-row-level-security-limitations-and-alternatives/)
- [Scott Pierce: Optimizing Postgres RLS for Performance](https://scottpierce.dev/posts/optimizing-postgres-rls/)
- [Bytebase: Common Postgres RLS Footguns](https://www.bytebase.com/blog/postgres-row-level-security-footguns/)

---

### Pitfall 7: Entity Extraction from Slack Messages Produces Garbage

**What goes wrong:** Slack messages are short, informal, full of abbreviations, emoji reactions, bot notifications, and lack grammatical structure. Running entity extraction (rule-based or LLM) on raw Slack messages produces massive amounts of noise: emoji-only messages create empty extractions, bot messages produce false entities, single-word replies like "lgtm" or "thanks" waste extraction budget, and thread context is lost when messages are processed individually.

**Why it happens:** The entity extraction pipeline treats all source documents equally. But a Slack message like "sounds good :thumbsup:" is fundamentally different from a Linear ticket description with structured fields. Without source-type-aware preprocessing, the pipeline wastes compute and pollutes the graph.

**Consequences:**
- Graph fills with low-value nodes extracted from trivial messages
- LLM extraction costs balloon (paying per-token to extract entities from "ok" and ":fire:")
- Signal-to-noise ratio in the graph drops, making graph-enhanced retrieval worse

**Prevention:**
1. **Filter before extracting.** Skip messages that are: under 20 characters, emoji-only, bot-generated, or thread replies that are just acknowledgments. This can eliminate 40-60% of Slack message volume without losing knowledge.
2. **Process Slack threads as units, not individual messages.** Concatenate thread messages into a single document with speaker attribution. Extract entities from the thread, not from each reply. This preserves conversational context and dramatically reduces extraction calls.
3. **Use different extraction strategies per source type:**
   - Linear tickets: rule-based extraction for ticket fields + LLM for decision identification in comments
   - Slack threads: rule-based extraction for @mentions/links + LLM only on threads with 3+ substantive messages
   - Meeting transcripts: LLM extraction (longer form, structured by speaker, higher entity density)
   - Code chunks: rule-based only (file paths, function names, imports -- no LLM needed)
4. **Track extraction yield per source type.** If Slack messages produce <0.5 entities per extraction call on average, the filtering is too loose.

**Detection:**
- Monitor entities-per-extraction-call by source type. Low yield = too many low-value documents are being processed.
- Sample graph nodes by source and check if Slack-sourced entities are meaningful.

**Affected phase:** Entity Extraction Pipeline

**Confidence:** HIGH -- Slack-to-knowledge-graph challenges are documented in multiple GraphRAG practitioner guides.

**Sources:**
- [Neo4j: Knowledge Graph from Slack Archive](https://medium.com/neo4j/how-to-create-a-knowledge-graph-from-your-slack-archive-with-neo4j-6a1a1d59a535)
- [Datagrid: Build Knowledge Graphs from Slack Conversations](https://datagrid.com/blog/build-knowledge-graphs-slack-conversations-ai-agents-d16d8)

---

### Pitfall 8: Graph Schema Over-Engineering with Too Many Entity and Relationship Types

**What goes wrong:** The team designs an elaborate graph schema with 15 entity types (Person, Decision, Ticket, SlackMessage, SlackThread, SlackChannel, Meeting, MeetingSegment, CodeFile, CodeFunction, PRReview, NotionPage, Team, Project, Label) and 25 relationship types (AUTHORED, MENTIONED_IN, DECIDED_IN, BLOCKS, RELATED_TO, REVIEWED, APPROVED, DISCUSSED_IN, ASSIGNED_TO, etc.). The schema is "complete" but impossible to populate accurately, query efficiently, or maintain as requirements change.

**Why it happens:** Graph modeling is seductive. Every relationship in the domain can be modeled as an edge type. The team tries to capture the full richness of engineering workflows in the graph schema upfront, before they know which relationships actually improve context pages.

**Consequences:**
- Entity extraction becomes harder (more types = more classification errors)
- Query complexity grows (every query must handle many relationship types)
- Schema migrations become painful (adding/changing types requires re-extraction)
- Most relationship types go unused in retrieval because only a few actually improve synthesis

**Prevention:**
1. **Start with exactly 4 entity types:** Person, Ticket, Decision, CodeEntity. These are the entities that actually improve context pages. Everything else (Slack messages, meetings, PR reviews) is already stored in relational tables and doesn't need to be duplicated as graph nodes.
2. **Start with exactly 5 relationship types:** MENTIONED_IN (person -> ticket/message), DECIDED_IN (decision -> message/meeting), AFFECTS (decision -> ticket), AUTHORED_BY (code -> person), RELATED_TO (ticket -> ticket). Add more ONLY when you have evidence a specific relationship type improves retrieval.
3. **Graph nodes should reference relational data, not duplicate it.** A Decision node has `{source_type: 'slack_message', source_id: uuid, summary: 'Use Redis for caching'}`. The full Slack message lives in the `slack_messages` table. The graph stores the relationship structure, the relational tables store the content.
4. **Schema versioning.** Add a `schema_version` column to graph tables. When you add new entity/relationship types, increment the version. Only nodes/edges at the current schema version participate in extraction and retrieval. This enables gradual migration without re-processing everything.

**Detection:**
- Count distinct entity_type and relationship_type values in the graph tables. If either exceeds 8 in the first milestone iteration, the schema is probably over-engineered.
- Check which relationship types are actually used in retrieval queries. Unused types are dead weight.

**Affected phase:** Graph Schema

**Confidence:** HIGH -- graph schema over-engineering is the most commonly cited mistake in knowledge graph practitioner literature.

**Sources:**
- [Memgraph: Model a Knowledge Graph](https://memgraph.com/docs/data-modeling/modeling-guides/model-a-knowledge-graph)
- [FalkorDB: How to Build a Knowledge Graph](https://www.falkordb.com/blog/how-to-build-a-knowledge-graph/)

---

### Pitfall 9: Graph Data Goes Stale When Source Documents Are Updated

**What goes wrong:** A Slack message is edited or a Linear ticket description is updated. The entity extraction was done on the original text. The graph now contains entities and relationships that no longer reflect the source data. Decisions that were reversed, people assignments that changed, and ticket statuses that evolved are all frozen in the graph at extraction time.

**Why it happens:** The existing ContextOS pipeline has webhook listeners for ticket updates and Slack events. But the entity extraction pipeline is designed as a one-time process: ingest source -> extract entities -> insert into graph. There's no mechanism to re-extract entities when source documents change, or to mark old graph data as stale.

**Consequences:**
- Context pages reference outdated decisions and relationships
- The graph accumulates historical cruft that contradicts current reality
- Users see "Decision: Use Celery for job queue" in the context page when the team already switched to FastAPI background tasks

**Prevention:**
1. **Tie graph nodes/edges to source document content hashes.** The existing `embeddings` table already has a `content_hash` column. Use the same pattern for graph data. When a source document's hash changes, mark its extracted graph nodes/edges for re-extraction.
2. **Implement graph garbage collection.** Periodically (or on source document update), compare graph nodes' source_id content hashes against current source documents. Delete or re-extract stale nodes.
3. **Add `extracted_at` and `source_content_hash` columns to graph tables.** This makes staleness queryable: `SELECT * FROM graph_nodes WHERE source_content_hash != (SELECT content_hash FROM embeddings WHERE source_id = graph_nodes.source_id)`.
4. **Scope re-extraction to changed documents only.** Don't re-extract the entire graph. When webhook receives a ticket update, re-extract entities ONLY from that ticket and its directly related sources. Use the same idempotency patterns as the existing embedding pipeline.

**Detection:**
- Query for graph nodes whose `extracted_at` is older than their source document's `updated_at`. These are candidates for re-extraction.
- Monitor the ratio of stale-to-current graph nodes over time. If stale nodes exceed 20%, the re-extraction pipeline is not keeping up.

**Affected phase:** Entity Extraction Pipeline (must be designed with update hooks from the start, not bolted on later)

**Confidence:** MEDIUM -- the staleness problem is well-understood in knowledge graph literature, but the specific interaction with ContextOS's webhook pipeline needs implementation-time validation.

**Sources:**
- [iText2KG: Incremental Knowledge Graph Construction](https://arxiv.org/html/2409.03284v1)
- [CocoIndex: Knowledge Graph from Meeting Notes that Auto-Updates](https://cocoindex.io/blogs/meeting-notes-graph)

---

## Minor Pitfalls

Issues that cause friction or minor quality problems but can be fixed without major rework.

---

### Pitfall 10: Blending Graph Scores with Vector + FTS Scores Is a Black Box

**What goes wrong:** The existing `hybrid_search()` function combines vector similarity (0.7 weight) and keyword rank (0.3 weight) into a `combined_score`. Adding a third signal (graph relevance) creates a three-way blending problem where the weights are arbitrary, the score scales are incomparable (cosine similarity is 0-1, graph hop distance is 1-4, FTS rank is 0-infinity), and debugging "why did this result appear?" becomes impossible.

**Why it happens:** The team adds `+ graph_weight * graph_score` to the existing scoring formula without normalizing score scales or establishing how graph relevance should be measured.

**Prevention:**
1. **Don't blend scores numerically at first.** Instead, use graph traversal as a separate retrieval channel. Run existing hybrid_search for top-20 results. Run graph traversal from the target ticket for related entities. Combine the two result sets by union (deduplicate), not by score arithmetic.
2. **If you must score, normalize each signal to 0-1 first.** Vector similarity is already 0-1. Graph relevance: 1/hop_count normalized. FTS rank: normalize by dividing by max rank in the result set.
3. **Log all three scores separately** for every retrieval. This lets you debug why certain results appeared and tune weights based on evidence, not intuition.

**Affected phase:** Graph-Enhanced Retrieval

**Confidence:** MEDIUM -- the general principle is well-documented, but the specific interaction with the existing `hybrid_search()` function needs experimentation.

**Sources:**
- [GraphRAG.com: Graph-Enhanced Vector Search](https://graphrag.com/reference/graphrag/graph-enhanced-vector-search/)
- [NetApp: Hybrid RAG in the Real World](https://community.netapp.com/t5/Tech-ONTAP-Blogs/Hybrid-RAG-in-the-Real-World-Graphs-BM25-and-the-End-of-Black-Box-Retrieval/ba-p/464834)

---

### Pitfall 11: Embeddings Table CHECK Constraint Blocks New Source Types

**What goes wrong:** The existing `embeddings.source_type` column has a CHECK constraint (currently: 'slack_message', 'linear_ticket', 'linear_comment', 'notion_page', 'meeting_transcript', 'meeting_segment', 'context_page', 'github_pull_request', 'github_review'). If graph-related content needs embeddings (e.g., decision summaries, graph-derived context snippets), adding new source types requires a migration to alter the CHECK constraint. This has already happened once (migration 00005 added GitHub types).

**Why it happens:** CHECK constraints are rigid. Every new source type requires a schema migration.

**Prevention:**
1. **If graph nodes need embeddings**, add the source types ('graph_decision', 'graph_entity', etc.) in the same migration that creates the graph tables. Don't discover this need mid-development.
2. **Consider replacing the CHECK constraint with a reference table** (`source_types` table with a foreign key) for future extensibility. This is a minor schema change but prevents future migration churn.

**Affected phase:** Graph Schema (migration planning)

**Confidence:** HIGH -- this is directly observable in the existing codebase (migrations 00001 and 00005).

---

### Pitfall 12: Decision Extraction Without Temporal Context Produces Conflicting Decisions

**What goes wrong:** The LLM extracts "Decision: Use Celery for job queue" from a February Slack thread and "Decision: Use FastAPI background tasks instead of Celery" from a March thread. Both are stored as Decision nodes in the graph. The synthesis prompt receives both and either presents contradictory information or picks the wrong (older) decision.

**Why it happens:** Decisions evolve over time. The graph stores decisions as nodes without temporal ordering or supersession relationships.

**Prevention:**
1. **Store `decided_at` timestamp on every Decision node.** Extract the date from the source message/meeting.
2. **Add a SUPERSEDES edge type.** When a new decision on the same topic is extracted, create a SUPERSEDES edge from the new decision to the old one.
3. **During retrieval, filter decisions by recency.** For any topic, return only the most recent decision (the one with no incoming SUPERSEDES edges). Optionally include the superseded decision with a "previously" label for context.
4. **Topic clustering for decisions.** Decisions about the same topic (e.g., "job queue technology") should be grouped. Use the decision summary embedding similarity to detect topically related decisions, then apply temporal ordering within the cluster.

**Affected phase:** Decision Extraction, Graph-Enhanced Retrieval

**Confidence:** MEDIUM -- the temporal decision problem is described in knowledge graph literature, but the specific implementation in this domain needs design-time validation.

---

### Pitfall 13: Code-to-Discussion Linking Creates Too Many Weak Edges

**What goes wrong:** The code-to-discussion linking feature connects code chunks to the conversations and tickets that motivated them. But the linking heuristic is too aggressive: any Slack message that mentions a file name, function name, or similar keyword gets linked. A code file with a common name like `utils.py` or `index.ts` gets linked to dozens of unrelated conversations.

**Why it happens:** Keyword matching on code identifiers has low precision. Function names like `handleSubmit`, `fetchData`, or `process` appear in many conversations without referring to the specific code entity.

**Prevention:**
1. **Require co-occurrence of multiple signals** for code-to-discussion links. A link requires: (a) the file path or a unique function name appears in the message, AND (b) the message is in a channel/thread related to the code's repository or team, AND (c) the message timestamp is within a reasonable window of the code change.
2. **Use PR-to-ticket links as the primary code-to-discussion bridge.** GitHub PRs already reference Linear tickets (via branch names like `eng-123-feature` or PR descriptions). These are high-confidence links. Use them as anchors, then extend to Slack only through threads that explicitly discuss those PRs or tickets.
3. **Weight code-to-discussion edges by confidence.** PR-based links: confidence 0.9. Explicit file path mention in related channel: confidence 0.6. Keyword match only: confidence 0.3. During retrieval, only traverse edges above a minimum confidence threshold.

**Affected phase:** Code-to-Discussion Linking

**Confidence:** MEDIUM -- the precision problem with keyword-based linking is well-known, but the specific false-positive rate depends on the team's repository and Slack usage patterns.

---

## Integration Gotchas

Common mistakes when the GraphRAG features connect to the existing ContextOS system.

| Integration Point | Common Mistake | Correct Approach |
|-------------------|----------------|------------------|
| Graph tables + existing RLS pattern | Copying the subquery-based RLS policy pattern from existing tables to graph tables, causing per-row evaluation during recursive traversal | Use SECURITY DEFINER function for traversal. Validate workspace membership once at entry, traverse without RLS overhead |
| Graph data + existing `hybrid_search()` | Modifying the existing hybrid_search function to include graph scores, breaking the current retrieval for non-graph queries | Create a new `graph_enhanced_search()` function that calls `hybrid_search()` internally and unions with graph results. Don't modify the working function |
| Entity extraction + existing webhook pipeline | Running entity extraction synchronously in webhook handlers, causing timeout on Slack/Linear webhook responses (must respond <3 seconds) | Queue entity extraction as a background task triggered by webhooks. The webhook handler saves the source document and returns immediately |
| Graph nodes + existing embeddings table | Trying to embed graph nodes using the same 768-dim embedding model and process as source documents | Graph nodes are metadata (entity names, relationship types), not content. Embed decision summaries if needed, but don't embed entity names -- they are for exact-match lookup, not semantic search |
| New graph tables + existing Supabase migrations | Creating graph migrations that depend on Apache AGE extension (which won't exist on Cloud) | All graph migrations must use only standard PostgreSQL DDL. Test migrations on a fresh Supabase project before merging |
| Context page synthesis + graph data | Passing raw graph query results (JSON arrays of nodes and edges) directly into the synthesis prompt | Transform graph results into natural language sentences before including in the prompt. The LLM processes prose better than structured data |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Graph Schema | AGE not available on Supabase Cloud (#1, #2) | **CRITICAL** | Use plain Postgres tables (nodes + edges) with recursive CTEs. No extension dependency. |
| Graph Schema | Over-engineered schema with too many types (#8) | Moderate | Start with 4 entity types, 5 relationship types. Add more only with evidence. |
| Graph Schema | Embeddings CHECK constraint blocks new types (#11) | Minor | Add graph source types in the graph schema migration. |
| Entity Extraction | LLM extraction hallucination and non-determinism (#3) | **CRITICAL** | Rule-based first, LLM second. Validate all LLM output against source text. |
| Entity Extraction | Slack message noise overwhelms extraction (#7) | Moderate | Filter bot messages, short messages, emoji-only. Process threads as units. |
| Entity Extraction | Stale graph data when sources update (#9) | Moderate | Content-hash-based change detection, incremental re-extraction. |
| Identity Resolution | False merges and false splits (#5) | Moderate | Anchor on platform user IDs, build explicit identity mapping table from team roster. |
| Decision Extraction | Conflicting temporal decisions (#12) | Minor | Store decided_at, add SUPERSEDES edges, filter by recency during retrieval. |
| Code-to-Discussion | Too many weak edges from keyword matching (#13) | Minor | Require multi-signal co-occurrence, PR-based links as primary bridge. |
| Graph-Enhanced Retrieval | Context overflow from graph data (#4) | **CRITICAL** | Fixed token budget for graph context, rank and truncate, summarize paths. |
| Graph-Enhanced Retrieval | Black-box score blending (#10) | Minor | Separate retrieval channels first, normalize scores if blending. |
| Graph-Enhanced Retrieval | RLS performance with recursive CTEs (#6) | Moderate | SECURITY DEFINER functions, validate workspace_id once at entry point. |
| Updated Synthesis | Prompt stuffing from graph + vector + FTS (#4) | **CRITICAL** | Structured prompt sections, token budgets, A/B test quality impact. |

---

## Aggregate Risk Assessment

| Risk Category | Count | Highest Severity |
|---------------|-------|-----------------|
| Infrastructure / Extension | 2 | CRITICAL (blocks entire milestone) |
| Data Quality / Extraction | 3 | CRITICAL (silent corruption) |
| Performance / Scalability | 2 | Moderate (fixable with SECURITY DEFINER) |
| Schema Design | 2 | Moderate (rework if caught late) |
| Retrieval / Synthesis | 3 | CRITICAL (quality regression) |
| Identity Resolution | 1 | Moderate (user trust risk) |

**The #1 risk to this milestone is the Apache AGE assumption.** If the team proceeds with AGE as the graph backend, they will be blocked on day 1. The plain PostgreSQL alternative (nodes + edges tables with recursive CTEs) is strictly better for this project: zero extension dependencies, works on Supabase Cloud, sufficient for 3-4 hop traversals in an engineering context graph, and easier to debug with standard SQL tooling.

**The #2 risk is LLM extraction quality.** The rule-based-first approach in the PROJECT.md is correct, but the boundary between "rule-based" and "LLM" must be strict and the LLM output must be validated. Without validation, the graph will accumulate garbage.

**The #3 risk is context overflow in synthesis.** The value of GraphRAG is zero if the additional context makes synthesis worse. Token budgets and quality comparison testing must be built into the retrieval pipeline, not added as an afterthought.

---

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Built on Apache AGE, can't deploy (#1) | HIGH | Rewrite all Cypher queries as recursive CTEs, create new migrations for plain tables, re-process all existing graph data. 1-2 week delay. |
| Graph full of hallucinated entities (#3) | MEDIUM | Truncate graph tables. Add validation pipeline. Re-extract from all sources with validation. 2-3 days. |
| Context pages worse after graph integration (#4) | LOW | Disable graph context in synthesis prompt (feature flag). Investigate which graph data is noise. Add token budget. 1 day. |
| Identity resolution produced false merges (#5) | HIGH | Manual audit of all person nodes. Split incorrectly merged identities. Rebuild affected context pages. 3-5 days depending on data volume. |
| Graph queries slow due to RLS (#6) | LOW | Wrap traversal in SECURITY DEFINER function. Test on Cloud. 4-6 hours. |
| Schema too complex, extraction failing on type classification (#8) | MEDIUM | Reduce to core 4 types. Drop extra types. Simplify extraction prompts. Re-extract. 2-3 days. |
| Stale graph data discovered (#9) | MEDIUM | Build content-hash comparison query. Identify stale nodes. Re-extract changed sources. Add webhook triggers. 2-3 days. |

---

## Sources

### Infrastructure & Extension
- [Supabase Extensions Documentation](https://supabase.com/docs/guides/database/extensions) -- verified AGE not listed (HIGH confidence)
- [Supabase Discussion #40285: Apache AGE Extension](https://github.com/orgs/supabase/discussions/40285) -- confirmed not installable (HIGH confidence)
- [Apache AGE GitHub Discussion #2150: Project Status](https://github.com/apache/age/discussions/2150) -- core team dismissed (HIGH confidence)
- [Apache AGE Issue #2111: PG17 Support](https://github.com/apache/age/issues/2111) -- delayed, now available in 1.6.0 (HIGH confidence)
- [Dylan Paulus: Postgres is a Graph Database](https://www.dylanpaulus.com/posts/postgres-is-a-graph-database) -- plain SQL graph patterns (MEDIUM confidence)

### Entity Extraction Quality
- [GDELT: LLM Entity Extraction Hallucination](https://blog.gdeltproject.org/experiments-in-entity-extraction-using-llms-hallucination-how-a-single-apostrophe-can-change-the-results/) -- hallucination evidence (HIGH confidence)
- [GDELT: LLM Infinite Loops & Failure Modes](https://blog.gdeltproject.org/llm-infinite-loops-failure-modes-the-current-state-of-llm-entity-extraction/) -- failure modes (HIGH confidence)
- [Bitext: Why LLMs Are Wrong for Enterprise Entity Extraction](https://www.bitext.com/blog/why-llms-are-the-wrong-tool-for-enterprise-grade-entity-extraction/) -- production reliability (HIGH confidence)

### GraphRAG & Retrieval
- [freeCodeCamp: 5 Common RAG Failures with Knowledge Graphs](https://www.freecodecamp.org/news/how-to-solve-5-common-rag-failures-with-knowledge-graphs/) -- RAG failure taxonomy (HIGH confidence)
- [Redis: Context Window Overflow](https://redis.io/blog/context-window-overflow/) -- prompt stuffing risks (HIGH confidence)
- [Pinecone: Less is More](https://www.pinecone.io/blog/why-use-retrieval-instead-of-larger-context/) -- retrieval vs. context size (HIGH confidence)
- [GraphRAG.com: Graph-Enhanced Vector Search](https://graphrag.com/reference/graphrag/graph-enhanced-vector-search/) -- hybrid retrieval patterns (MEDIUM confidence)
- [NetApp: Hybrid RAG in the Real World](https://community.netapp.com/t5/Tech-ONTAP-Blogs/Hybrid-RAG-in-the-Real-World-Graphs-BM25-and-the-End-of-Black-Box-Retrieval/ba-p/464834) -- score blending challenges (MEDIUM confidence)

### Performance & RLS
- [Bytebase: PostgreSQL RLS Limitations](https://www.bytebase.com/blog/postgres-row-level-security-limitations-and-alternatives/) -- RLS performance (HIGH confidence)
- [Scott Pierce: Optimizing Postgres RLS](https://scottpierce.dev/posts/optimizing-postgres-rls/) -- SECURITY DEFINER pattern (HIGH confidence)
- [Cybertec: Speeding Up Recursive Queries](https://www.cybertec-postgresql.com/en/postgresql-speeding-up-recursive-queries-and-hierarchic-data/) -- CTE optimization (HIGH confidence)
- [Bytebase: Common Postgres RLS Footguns](https://www.bytebase.com/blog/postgres-row-level-security-footguns/) -- circular dependency risks (HIGH confidence)

### Knowledge Graph Design
- [Memgraph: Model a Knowledge Graph](https://memgraph.com/docs/data-modeling/modeling-guides/model-a-knowledge-graph) -- schema design (MEDIUM confidence)
- [FalkorDB: How to Build a Knowledge Graph](https://www.falkordb.com/blog/how-to-build-a-knowledge-graph/) -- iterative schema (MEDIUM confidence)
- [Neo4j: Knowledge Graph from Slack Archive](https://medium.com/neo4j/how-to-create-a-knowledge-graph-from-your-slack-archive-with-neo4j-6a1a1d59a535) -- Slack extraction patterns (MEDIUM confidence)
- [Datagrid: Build Knowledge Graphs from Slack](https://datagrid.com/blog/build-knowledge-graphs-slack-conversations-ai-agents-d16d8) -- Slack filtering (MEDIUM confidence)

### Incremental Updates & Staleness
- [iText2KG: Incremental KG Construction](https://arxiv.org/html/2409.03284v1) -- incremental update patterns (MEDIUM confidence)
- [CocoIndex: Knowledge Graph Auto-Updates](https://cocoindex.io/blogs/meeting-notes-graph) -- change detection (MEDIUM confidence)

---

*Pitfalls research for: ContextOS v1.2 GraphRAG milestone (knowledge graph, entity extraction, identity resolution, graph-enhanced retrieval)*
*Researched: 2026-03-06*
