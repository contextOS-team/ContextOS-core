# Phase 26: Synthesis + Code-to-Discussion Linking - Research

**Researched:** 2026-03-08
**Domain:** LLM synthesis prompt engineering, graph-to-content linking, code provenance
**Confidence:** HIGH

## Summary

Phase 26 is the user-facing payoff of the entire GraphRAG layer. It has two distinct workstreams: (1) enhancing the synthesis prompt so the LLM produces richer context pages with decision trails, relationship narratives, and cross-referenced people when graph data is available; and (2) creating graph edges that link Slack-mentioned file paths/function names to actual code_chunks, plus adding code-to-discussion provenance annotations in context pages.

The codebase is well-prepared for both workstreams. The synthesis template (`SYNTHESIS_TEMPLATE` in `synthesis.py`) already has 7 numbered sections with a `{graph_section}` placeholder, and the `_format_graph_section()` function already renders graph items as structured data blocks. The change for SYNTH-01/02/03 is primarily in the prompt *instructions* -- telling the LLM how to weave graph data into its narrative output. For CODE-01/02/03, the `FilePathExtractor` in `graph_extractor.py` already creates CodeChunk graph nodes from file path mentions, but does not yet create edges to actual code_chunks table records. The `GithubPullRequest` model has `raw_data` JSONB that may contain changed files data, and PRs are already linked to Linear tickets via `linear_ticket_id` FK.

**Primary recommendation:** Split into two plans: Plan 01 for synthesis prompt enrichment (SYNTH-01/02/03) with graceful degradation verification (SYNTH-04), and Plan 02 for code-to-discussion edge creation and provenance display (CODE-01/02/03).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Decision Trail Rendering (SYNTH-01):** Enriched narrative style -- LLM weaves decisions into prose with full attribution, not flat lists or timelines. Show ALL decision nodes regardless of confidence with confidence indicator. Always cite source with where it came from.
- **Relationship Path Narratives (SYNTH-02):** Human-readable narratives, NOT raw path notation. Inline in existing sections, not separate "Connections" section. Key hops only. Graph Connections section kept as structured data block in prompt input; add synthesis instructions telling LLM to weave graph insights into other sections.
- **People Cross-Referencing (SYNTH-03):** Enhance existing "Key People" section (#7) with graph data showing per-person involvement across sources. Graph traversal already follows same_as edges transparently.
- **Code-to-Discussion Provenance (CODE-01/02/03):** CODE-01: Slack messages mentioning file paths/function names create graph edges to matching code_chunks. CODE-02: PRs implementing tickets create transitive links between changed code and related discussions. CODE-03: Context pages show code-to-discussion provenance in "Relevant Code" section.

### Claude's Discretion
- Exact synthesis prompt wording for the new instructions (how to tell the LLM to weave graph data into sections)
- Matching algorithm for Slack-mentioned file paths/function names to code_chunks (exact match, fuzzy, or pattern-based)
- Whether to add new fields to LinkedItem or annotate existing ones for code-to-discussion edges
- Test fixture design for synthesis prompt changes
- How to handle code_chunks that match multiple discussions (show most recent? most relevant?)
- Exact format of code provenance annotations in the "Relevant Code" section

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SYNTH-01 | Context pages include decision trails showing what was decided, by whom, where discussed, and which tickets affected | Synthesis prompt instruction updates to section 2 (Background & Decisions); `_format_decision_node()` already provides structured input; LLM told to weave into narrative prose |
| SYNTH-02 | Context pages include relationship paths explaining why things are connected | Synthesis prompt instruction updates to sections 2 and 4; graph provenance strings from `graph:EntityType(relationship,d=N)` already in LinkedItem signals; LLM told to translate to natural sentences |
| SYNTH-03 | Context pages include cross-referenced people showing involvement across sources | Synthesis prompt instruction updates to section 7 (Key People); Person nodes with same_as edges aggregate platform identities; LLM told to show per-person cross-source involvement |
| SYNTH-04 | Synthesis gracefully degrades when no graph data exists for a ticket | Already complete (Phase 25); `_format_graph_section()` returns empty string for empty items; verify no regression with new prompt instructions |
| CODE-01 | Slack messages mentioning file paths/function names create edges to matching code_chunks | Extend `FilePathExtractor` or add post-extraction step in `extract_and_populate_graph()` to match extracted `path:` CodeChunk nodes against actual code_chunks table records by file_path |
| CODE-02 | PRs implementing tickets create transitive links between changed code and related discussions | Use PR `raw_data` for changed files list; PR already linked to ticket via `linear_ticket_id` FK; create edges from code_chunk nodes (matched by file_path) through PR to ticket discussions |
| CODE-03 | Context pages show code-to-discussion provenance in relevant code section | Enhance `_format_related_content()` for code_chunk items to include discussion annotations; query graph edges for code_chunk nodes to find connected discussion nodes |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Project standard |
| SQLAlchemy | 2.x (async) | Database ORM | Project standard, async session pattern |
| SQLModel | 0.x | Model definitions | Project standard, combines Pydantic + SQLAlchemy |
| pytest | latest | Testing | Project standard, asyncio_mode="auto" |
| pytest-asyncio | latest | Async test support | Project standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-genai | latest | LLM synthesis | Gemini API for context page generation |
| unittest.mock | stdlib | Test mocking | All unit tests use MagicMock/AsyncMock pattern |

### Alternatives Considered
None -- this phase modifies existing files with no new dependencies.

## Architecture Patterns

### Recommended Project Structure
No new files are needed for SYNTH-01/02/03 -- these are prompt instruction changes in existing `synthesis.py`. For CODE-01/02, new logic goes into `graph_extractor.py` (or a new function in `graph_ops.py`). For CODE-03, changes go into `synthesis.py` and possibly `linking.py`.

```
backend/src/services/
├── synthesis.py          # SYNTH-01/02/03: Update SYNTHESIS_TEMPLATE section instructions
│                         # CODE-03: Enhance _format_related_content() for code provenance
├── linking.py            # CODE-03: Annotate code_chunk LinkedItems with discussion provenance
├── graph_extractor.py    # CODE-01: Match FilePathExtractor CodeChunk nodes to actual code_chunks
└── graph_ops.py          # CODE-02: Helper to find graph edges by file_path match (if needed)

backend/tests/
├── test_synthesis_prompt.py  # SYNTH-01/02/03: Verify updated template instructions
├── test_synthesis_graph.py   # SYNTH-01/02/03: Verify LLM prompt includes new instructions
├── test_code_discussion.py   # CODE-01/02/03: New test file for code-to-discussion linking
└── test_synthesis.py         # SYNTH-04: Verify graceful degradation still works
```

### Pattern 1: Prompt Engineering for Enriched Synthesis
**What:** Update the numbered section instructions in `SYNTHESIS_TEMPLATE` to tell the LLM how to use graph data
**When to use:** SYNTH-01/02/03
**Example:**
```python
# Current section 2:
# 2. **Background & Decisions** — Key decisions, discussions, and context from Slack, meetings, and comments

# Updated section 2 (adds decision trail instruction):
# 2. **Background & Decisions** — Key decisions, discussions, and context from Slack, meetings, and comments.
#    If the Graph Connections section contains [DECISION] items, weave them into a decision trail narrative:
#    state what was decided, who decided it, where it was discussed, and which tickets it affects.
#    Include the confidence level so readers can judge certainty (e.g., "likely decided" vs "confirmed").
#    Always cite the source (e.g., "decided by @alex in #backend-chat, Jan 15").
```

### Pattern 2: Graph Edge Creation for Code Matching (CODE-01)
**What:** After `FilePathExtractor` creates a CodeChunk graph node for a mentioned file path, look up matching code_chunks records in the database and create `mentions` edges
**When to use:** CODE-01
**Key insight:** The `FilePathExtractor` creates graph nodes with `external_id=path:{filepath}` but these are "dangling" references. CODE-01 needs to match against actual `code_chunks` table entries where `code_chunks.file_path LIKE '%{extracted_path}'` (suffix match, because extracted paths may be relative while code_chunks have full paths).

### Pattern 3: Fail-Silent Graph Operations
**What:** All graph operations wrap in try/except, log warnings, never raise
**When to use:** Every graph operation in this phase
**Source:** Established in Phase 22-03, consistently applied through Phases 23-25

### Anti-Patterns to Avoid
- **Separate "Graph Connections" output section:** User explicitly decided against this -- graph insights must be woven into existing sections (Background & Decisions, Related Work, Key People, Relevant Code), not echoed as a separate block
- **Raw graph path notation in output:** User decided on human-readable narratives, not `Ticket->discussed_in->SlackThread` format
- **Auto-merging graph insights without LLM reasoning:** The graph section stays as structured input; the LLM decides how to incorporate insights
- **Breaking graceful degradation:** SYNTH-04 is already complete; new prompt instructions must be conditional ("If the Graph Connections section contains...")

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File path matching | Custom fuzzy matcher | SQL LIKE suffix match (`file_path LIKE '%' || :path`) | code_chunks have full paths from repo root; extracted paths are often relative. Suffix match handles both `src/auth.py` matching `backend/src/auth.py` |
| Graph node dedup | Manual INSERT/SELECT | `graph_ops.upsert_node()` with fingerprint | Already handles ON CONFLICT, soft-delete restoration |
| Graph edge dedup | Manual INSERT/SELECT | `graph_ops.upsert_edge()` | Already handles composite key ON CONFLICT |
| Person identity aggregation | Manual identity mapping | same_as edges + transparent traversal (Phase 23/25) | Already works -- canonical Person nodes aggregate platform identities |

**Key insight:** Most infrastructure is already built. This phase is primarily prompt engineering and edge creation logic, not new infrastructure.

## Common Pitfalls

### Pitfall 1: Prompt Instruction Regression Breaking No-Graph Path
**What goes wrong:** New prompt instructions reference graph data unconditionally, causing the LLM to hallucinate graph connections when no graph data exists
**Why it happens:** Template instructions like "Include the decision trail from Graph Connections" fail when `{graph_section}` is empty
**How to avoid:** All new instructions MUST be conditional: "If the Graph Connections section above contains [DECISION] items, then weave them into..."
**Warning signs:** Tests with empty graph_section producing output mentioning decisions or connections

### Pitfall 2: Code Path Matching False Positives
**What goes wrong:** Generic file paths like `config.py` or `index.ts` match dozens of code_chunks across repos
**Why it happens:** Short or common file names are not unique identifiers
**How to avoid:** Require minimum path depth (at least one directory segment, e.g., `src/config.py` not just `config.py`). When multiple matches exist, prefer same-repo matches. Consider matching symbol_name for function references.
**Warning signs:** A single Slack message creating 20+ graph edges to code_chunks

### Pitfall 3: Synthesis Template Section Count Change
**What goes wrong:** Tests assert `SYNTHESIS_TEMPLATE` has exactly 7 sections (test_synthesis_prompt.py line 28); adding a new section or renumbering breaks tests
**Why it happens:** Phase adds instructions TO existing sections, not new sections
**How to avoid:** Keep exactly 7 numbered sections. Add instructions within the existing section descriptions, not as new numbered sections
**Warning signs:** `test_template_has_seven_sections` failing

### Pitfall 4: Entity Type CHECK Constraint Violations
**What goes wrong:** Creating graph nodes with entity types not in the database CHECK constraint
**Why it happens:** The migration `00017_graph_tables.sql` restricts entity_type to 11 values: Person, Ticket, SlackThread, PR, CodeChunk, NotionPage, Meeting, Decision, Blocker, Feature, Component
**How to avoid:** Only use existing entity types. CodeChunk is already in the list. No new entity types needed for this phase
**Warning signs:** IntegrityError from database on INSERT

### Pitfall 5: Relationship Type CHECK Constraint Violations
**What goes wrong:** Creating graph edges with relationship types not in the database CHECK constraint
**Why it happens:** The migration restricts relationship_type to 11 values: mentions, references, authored_by, assigned_to, discussed_in, implements, reviews, decided_in, blocks, same_as, parent_of
**How to avoid:** Use existing relationship types. `mentions` fits for CODE-01 (Slack mentions code). `implements` fits for CODE-02 (PR implements ticket). No new relationship types needed
**Warning signs:** IntegrityError from database on edge INSERT

### Pitfall 6: Raw Data Availability for PR Changed Files
**What goes wrong:** Assuming `raw_data` always contains file change information
**Why it happens:** GitHub webhook payloads for `pull_request` events do NOT include `files` array by default -- that requires a separate API call to `/pulls/{number}/files`
**How to avoid:** For CODE-02, consider using existing graph edges: PR nodes already have `references` edges to CodeChunk nodes (from FilePathExtractor running on PR title/description). For the transitive link, traverse: PR --(implements)--> Ticket <--(discussed_in)-- Discussion. The key is that code_chunks sharing the same file_path as files mentioned in the PR description/title already have CodeChunk graph nodes.
**Warning signs:** `raw_data.get('files', [])` always returning empty list

## Code Examples

### Example 1: Updated SYNTHESIS_TEMPLATE Section Instructions
```python
# Source: synthesis.py SYNTHESIS_TEMPLATE (current lines 46-54)
# The update adds conditional instructions referencing graph data

SYNTHESIS_TEMPLATE = """\
## Ticket: {identifier}
...
{graph_section}
---

Based on the ticket and all related content above, produce a context page with these sections:

1. **Summary** — 2-3 sentence overview of what this ticket is about and why it matters
2. **Background & Decisions** — Key decisions, discussions, and context from Slack, meetings, and comments. If the Graph Connections section above contains [DECISION] items, weave each into the narrative as a decision trail: state what was decided, who decided it (citing the person), where it was discussed (citing the source), and which tickets it affects. Include the confidence level (e.g., "confirmed" for high confidence, "likely decided" for lower). Always cite the source so engineers can verify.
3. **Requirements** — What needs to be built or fixed, extracted from the ticket and discussions
4. **Related Work** — PRs, linked tickets, and other relevant engineering artifacts. If the Graph Connections section shows relationships between items, explain WHY they are connected in natural language (e.g., "This PR was discussed in Slack thread #deploy-v2 by @alex, who also authored the spec in Notion") rather than listing raw connections. Focus on the most important relationship paths.
5. **Relevant Code** — Code snippets from across the codebase that are relevant to this ticket. Include function signatures, class definitions, and route handlers with file paths and repo names. If any code snippets have associated discussion provenance (noted as "Discussed in:" annotations), include that context so engineers know where this code was talked about.
6. **Open Questions** — Unresolved questions or ambiguities that need clarification
7. **Key People** — Who is involved and their roles. If graph data shows a person's involvement across multiple sources (e.g., authored ticket, discussed in Slack, reviewed PR), list their cross-source involvement to show the full picture of their engagement."""
```

### Example 2: Code-to-Discussion Edge Creation (CODE-01)
```python
# After FilePathExtractor creates CodeChunk nodes for file paths mentioned in Slack,
# match them against actual code_chunks table records

async def link_code_mentions_to_chunks(
    session: AsyncSession,
    workspace_id: UUID,
    source_node_id: UUID,  # The SlackThread/source node
    extracted_entities: list[ExtractedEntity],
) -> None:
    """For CodeChunk entities extracted from content, find matching
    code_chunks table records and create 'mentions' edges."""
    from src.services import graph_ops

    for entity in extracted_entities:
        if entity.entity_type != "CodeChunk":
            continue

        file_path = entity.properties.get("file_path", "")
        if not file_path or file_path.count("/") < 1:
            continue  # Skip bare filenames to avoid false positives

        # Find matching code_chunks by suffix match
        stmt = select(CodeChunk).where(
            CodeChunk.workspace_id == workspace_id,
            CodeChunk.file_path.endswith(file_path),
            CodeChunk.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        chunks = result.scalars().all()

        for chunk in chunks:
            # Create/get the CodeChunk graph node for the actual code_chunk record
            chunk_node_id = await graph_ops.upsert_node(
                session=session,
                workspace_id=workspace_id,
                entity_type="CodeChunk",
                external_id=f"chunk:{chunk.id}",
                name=f"{chunk.symbol_type}: {chunk.symbol_name}",
                source_type="code_chunk",
                source_id=chunk.id,
            )
            # Create edge: SourceNode --(mentions)--> CodeChunkNode
            await graph_ops.upsert_edge(
                session=session,
                workspace_id=workspace_id,
                source_node_id=source_node_id,
                target_node_id=chunk_node_id,
                relationship_type="mentions",
                properties={"matched_path": file_path},
            )
```

### Example 3: Code Provenance Annotation in _format_related_content (CODE-03)
```python
# Extend the code_chunk rendering to include discussion provenance

def _format_related_content(items: list, code_provenance: dict | None = None) -> str:
    """Format linked items into structured text. code_provenance maps
    source_id -> list of discussion annotations."""
    if not items:
        return "No related content found."

    sections = []
    for item in items:
        if item.source_type == "code_chunk":
            annotation = ""
            if code_provenance and item.source_id in code_provenance:
                discussions = code_provenance[item.source_id]
                annotation = "\nDiscussed in: " + "; ".join(discussions)
            section = (
                f"#### [{item.source_type}] {item.title}\n"
                f"**Relevance:** {item.relevance_score:.2f} | **Signals:** {', '.join(item.signals)}\n\n"
                f"```\n{item.snippet}\n```{annotation}"
            )
        else:
            section = (
                f"#### [{item.source_type}] {item.title}\n"
                f"**Relevance:** {item.relevance_score:.2f} | **Signals:** {', '.join(item.signals)}\n\n"
                f"{item.snippet}"
            )
        sections.append(section)

    return "\n\n---\n\n".join(sections)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Graph section echoed verbatim in output | Graph data woven into narrative sections by LLM | Phase 26 (this phase) | Context pages read naturally with decision trails and relationship explanations |
| Code chunks shown without context | Code chunks annotated with discussion provenance | Phase 26 (this phase) | Engineers see where code was discussed, not just what the code is |
| File path graph nodes are dangling references | File path nodes linked to actual code_chunks records | Phase 26 (this phase) | Graph traversal discovers code through discussion mentions |

## Open Questions

1. **PR Changed Files Data Availability**
   - What we know: GitHub PR webhook payloads do NOT include the files changed list. The `raw_data` JSONB stores the payload as received. PR title and description may mention file paths which the FilePathExtractor already processes.
   - What's unclear: Whether we need a separate GitHub API call to get changed files for CODE-02, or if the existing graph edges from PR description/title extraction are sufficient.
   - Recommendation: For CODE-02, leverage existing graph structure rather than making API calls. PRs already have `references` edges to CodeChunk nodes (from FilePathExtractor on PR content). PRs are linked to tickets via `linear_ticket_id` FK. Tickets have `discussed_in` edges to SlackThread nodes. The transitive path already exists: CodeChunk <--(references)-- PR --(linear_ticket_id)--> Ticket <--(discussed_in)-- SlackThread. Enhance the graph traversal or add explicit transitive edges from CodeChunk to discussions via tickets.

2. **Function Name Matching for CODE-01**
   - What we know: code_chunks has `symbol_name` column. Slack messages may mention function names like `generate_context_page()` or `handleWebhook`.
   - What's unclear: Whether to add function name extraction beyond the existing FilePathExtractor (which only catches file paths, not bare function names).
   - Recommendation: Start with file path matching only (already extracted by FilePathExtractor). Function name matching is harder (high false positive rate for common names like `init`, `main`, `handle`). Can be added later as an enhancement.

3. **Code Provenance Query Performance for CODE-03**
   - What we know: For each code_chunk LinkedItem, CODE-03 needs to find connected discussion nodes via graph edges. This adds N queries per code_chunk in the synthesis flow.
   - What's unclear: Whether to batch this into a single graph query or do per-item lookups.
   - Recommendation: Batch query -- after identifying code_chunk items in the LinkedItems list, do a single query to find all graph edges connecting those code_chunk node IDs to discussion-type nodes (SlackThread, Meeting). This avoids N+1 queries.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | backend/pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `cd backend && python -m pytest tests/test_synthesis_prompt.py tests/test_synthesis_graph.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYNTH-01 | Decision trail instructions in SYNTHESIS_TEMPLATE section 2 | unit | `cd backend && python -m pytest tests/test_synthesis_prompt.py -x -q` | Exists, needs new tests |
| SYNTH-02 | Relationship path narrative instructions in sections 2, 4 | unit | `cd backend && python -m pytest tests/test_synthesis_prompt.py -x -q` | Exists, needs new tests |
| SYNTH-03 | People cross-reference instructions in section 7 | unit | `cd backend && python -m pytest tests/test_synthesis_prompt.py -x -q` | Exists, needs new tests |
| SYNTH-04 | Graceful degradation with no graph data (regression) | unit | `cd backend && python -m pytest tests/test_synthesis_graph.py -x -q` | Exists, may need regression test |
| CODE-01 | Slack file path mentions create edges to code_chunks | unit | `cd backend && python -m pytest tests/test_code_discussion.py -x -q` | Wave 0 |
| CODE-02 | PR-to-ticket transitive code-discussion links | unit | `cd backend && python -m pytest tests/test_code_discussion.py -x -q` | Wave 0 |
| CODE-03 | Code provenance annotations in synthesis output | unit | `cd backend && python -m pytest tests/test_code_discussion.py -x -q` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_synthesis_prompt.py tests/test_synthesis_graph.py tests/test_code_discussion.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_code_discussion.py` -- covers CODE-01, CODE-02, CODE-03 (new file)
- [ ] New test cases in `backend/tests/test_synthesis_prompt.py` for SYNTH-01/02/03 instruction verification
- [ ] New test case in `backend/tests/test_synthesis_graph.py` for SYNTH-04 regression with new prompt

## Implementation Analysis

### SYNTH-01/02/03: Synthesis Prompt Enrichment

**Files to modify:**
- `backend/src/services/synthesis.py`: Update SYNTHESIS_TEMPLATE section instruction text (lines 46-54)

**What changes:**
1. Section 2 (Background & Decisions) instruction text gains conditional decision trail synthesis instructions
2. Section 4 (Related Work) instruction text gains conditional relationship path narrative instructions
3. Section 7 (Key People) instruction text gains cross-source involvement instructions
4. All instructions are phrased conditionally: "If the Graph Connections section above contains..."

**What does NOT change:**
- The 7-section structure (still exactly 7 numbered sections)
- The `{graph_section}` placeholder behavior
- The `_format_graph_section()` function
- The `_format_decision_node()` function
- The `_format_related_content()` function (for SYNTH-* requirements)
- The `generate_context_page()` flow

**Key constraint:** `test_template_has_seven_sections` asserts exactly 7 sections. The instructions are text changes WITHIN existing sections, not new sections.

### CODE-01: Slack File Path -> code_chunks Edge Creation

**Approach:** Extend `extract_and_populate_graph()` in `graph_extractor.py` to add a post-extraction step. After creating CodeChunk graph nodes from FilePathExtractor, query the `code_chunks` table for matching file paths and create `mentions` edges from the source node (SlackThread) to the matched code_chunk graph nodes.

**Matching strategy:** SQL suffix match (`file_path LIKE '%' || :path`). Require minimum 1 directory segment in path to avoid false positives. The `code_chunks` table has a dedup constraint on `(workspace_id, repo_full_name, file_path, symbol_name, symbol_type)`, so matching by file_path may return multiple symbols from the same file -- this is correct behavior (a file path mention relates to all symbols in that file).

**Integration point:** Add the matching call inside `extract_and_populate_graph()` after the entity extraction loop, or as a separate function called from the same orchestrator.

### CODE-02: PR -> Ticket -> Discussion Transitive Links

**Approach:** When a PR is linked to a ticket (via `linear_ticket_id` FK), and that PR has CodeChunk graph nodes (from FilePathExtractor on PR title/description), create transitive edges linking those CodeChunk nodes to the discussion nodes connected to the ticket.

**Implementation options:**
- **Option A (recommended):** Add a post-processing step in `handle_pull_request_event()` in `github_webhook.py` -- after `link_pr_to_ticket()` succeeds and `extract_and_populate_graph()` creates CodeChunk nodes, query for discussion nodes connected to the ticket's graph node and create `discussed_in` edges from CodeChunk nodes to those discussion nodes.
- **Option B:** Do this lazily at synthesis time by following the graph path PR -> Ticket -> Discussions and presenting the transitive relationship.

Option A creates explicit edges (better for graph traversal at query time). Option B is simpler but relies on multi-hop traversal depth being sufficient.

**Recommendation:** Option A -- create explicit edges at ingestion time so graph traversal at synthesis time works with depth-2 limit.

### CODE-03: Code Provenance Annotations in Context Pages

**Approach:** In `generate_context_page()`, after separating graph and non-graph items, query graph edges for code_chunk items to find connected discussion nodes. Pass this provenance information to `_format_related_content()` so it can annotate code blocks with "Discussed in: ..." text.

**Key detail:** The provenance annotation goes into the prompt input (the Related Content section), not the LLM instructions. The LLM is already told in section 5 to "include discussion provenance (noted as 'Discussed in:' annotations)".

### Database Considerations

**No new migrations needed.** All entity types (CodeChunk) and relationship types (mentions, references, discussed_in) already exist in the CHECK constraints. No new tables or columns required.

## Sources

### Primary (HIGH confidence)
- `backend/src/services/synthesis.py` -- SYNTHESIS_TEMPLATE, _format_graph_section, _format_decision_node, _format_related_content, generate_context_page (full source read)
- `backend/src/services/linking.py` -- LinkedItem, LinkingResult, _find_graph_results, find_related_content, _apply_token_budget (full source read)
- `backend/src/services/graph_extractor.py` -- FilePathExtractor, extract_and_populate_graph, ExtractedEntity, run_extractors (full source read)
- `backend/src/services/graph_ops.py` -- compute_fingerprint, upsert_node, upsert_edge (full source read)
- `backend/src/models/code_chunk.py` -- CodeChunk model with file_path, symbol_name columns (full source read)
- `backend/src/models/github.py` -- GithubPullRequest with linear_ticket_id FK, raw_data JSONB (full source read)
- `supabase/migrations/00017_graph_tables.sql` -- entity_type CHECK (11 types), relationship_type CHECK (11 types) (full source read)
- `backend/tests/test_synthesis_graph.py` -- existing graph synthesis tests (full source read)
- `backend/tests/test_synthesis_prompt.py` -- template structure tests including 7-section assertion (full source read)
- `backend/tests/test_linking_graph.py` -- graph traversal and merge tests (full source read)
- `backend/tests/test_linking_code.py` -- code_chunk integration tests (full source read)

### Secondary (MEDIUM confidence)
- `backend/src/services/github_webhook.py` -- handle_pull_request_event flow showing graph extraction integration point (full source read)
- `backend/src/services/llm_extractor.py` -- persist_decision/persist_blocker pattern for graph edge creation (full source read)
- `backend/src/services/github_linking.py` -- link_pr_to_ticket pattern showing PR-to-ticket FK assignment (full source read)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all modifications to existing well-understood codebase
- Architecture: HIGH -- all integration points inspected in source code; patterns well-established from Phases 22-25
- Pitfalls: HIGH -- verified CHECK constraints from migration, test assertions from test files, webhook payload structure from handler code
- Code examples: MEDIUM -- prompt wording is Claude's discretion; code patterns follow established project conventions but exact implementation details will vary

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable -- no external dependencies changing)
