# Phase 26: Synthesis + Code-to-Discussion Linking - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Context pages visibly improve with decision trails, relationship paths, cross-referenced people, and code-to-discussion provenance. This phase modifies the synthesis prompt and formatting functions so the LLM produces richer context pages when graph data is available. For tickets with no graph data, context pages render identically to pre-graph behavior (SYNTH-04 graceful degradation already works). This phase also creates graph edges linking Slack-mentioned file paths and PR-changed files to code_chunks and their related discussions.

</domain>

<decisions>
## Implementation Decisions

### Decision Trail Rendering (SYNTH-01)
- Enriched narrative style -- LLM weaves decisions into prose with full attribution, not flat lists or timelines
- Example output: "The team decided to use Redis for caching (decided by @alex in #backend-chat, Jan 15). This affects CON-42 and CON-45."
- Grouping: LLM decides whether to group by topic or keep chronological based on the content -- no fixed rule
- Show ALL decision nodes regardless of confidence -- include confidence indicator so reader can judge ("likely decided" vs "confirmed")
- Always cite source -- every decision attribution includes where it came from (Slack thread name, meeting title, etc.) so engineers can verify

### Relationship Path Narratives (SYNTH-02)
- Human-readable narratives, NOT raw path notation -- translate graph paths into natural sentences
- Example: "This PR was discussed in Slack thread #deploy-v2 by @alex, who also authored the spec in Notion" instead of "Ticket->discussed_in->SlackThread->authored_by->Person"
- Inline in existing sections -- relationship context woven into Background & Decisions, Related Work, Key People sections, not in a separate "Connections" section
- Key hops only -- mention important intermediaries, skip mechanical hops. LLM picks what matters for conciseness
- Graph Connections section from Phase 25 kept as structured data block in the prompt input. Add synthesis instructions telling the LLM to weave graph insights into the other output sections rather than echoing the graph section verbatim

### People Cross-Referencing (SYNTH-03)
- Enhance existing "Key People" section (#7 in synthesis template) with graph data showing per-person involvement across sources
- Example: "@alex: authored ticket, discussed in #backend-chat, reviewed PR #42"
- Graph traversal already follows same_as edges transparently (Phase 23/25) -- canonical Person nodes aggregate all platform identities

### Code-to-Discussion Provenance (CODE-01, CODE-02, CODE-03)
- CODE-01: When Slack messages mention file paths or function names that match existing code_chunks, create graph edges (mentions relationship) from the SlackThread/message node to the matching CodeChunk node
- CODE-02: When PRs implement tickets, create transitive edges linking changed code files to the discussions about those tickets
- CODE-03: In context pages, code snippets in the "Relevant Code" section show discussion provenance -- e.g., "Discussed in: #backend-chat by @alex (Jan 15)" annotation on code blocks that have graph connections to discussions

### Claude's Discretion
- Exact synthesis prompt wording for the new instructions (how to tell the LLM to weave graph data into sections)
- Matching algorithm for Slack-mentioned file paths/function names to code_chunks (exact match, fuzzy, or pattern-based)
- Whether to add new fields to LinkedItem or annotate existing ones for code-to-discussion edges
- Test fixture design for synthesis prompt changes
- How to handle code_chunks that match multiple discussions (show most recent? most relevant?)
- Exact format of code provenance annotations in the "Relevant Code" section

</decisions>

<specifics>
## Specific Ideas

- The existing `_format_decision_node()` in synthesis.py (line 57) already produces `[DECISION] desc | By: person | In: source | Affects: tickets | Confidence: X.X` -- this feeds the LLM prompt input. The change is in the prompt *instructions* telling the LLM to weave these into narrative prose with citations
- The existing `_format_graph_section()` (line 88) renders graph items as a data block -- keep this as input but add prompt instructions for the LLM to use it as source material for enriching other sections
- SYNTHESIS_TEMPLATE section instructions (lines 29-54) need updating: "Background & Decisions" should mention decision trail synthesis, "Related Work" should mention relationship narratives, "Key People" should mention cross-source involvement, "Relevant Code" should mention discussion provenance
- FilePathExtractor (graph_extractor.py line 295) already creates CodeChunk entities with `external_id=path:{filepath}` -- CODE-01 needs to match these against actual code_chunks table entries and create edges
- code_chunks table has `file_path` and `symbol_name` columns that can be matched against Slack message content for CODE-01

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `synthesis.py:_format_decision_node()` (line 57): Already formats decision nodes with person/source/tickets/confidence -- input format for LLM
- `synthesis.py:_format_graph_section()` (line 88): Renders graph items as structured data block -- keep as prompt input
- `synthesis.py:SYNTHESIS_TEMPLATE` (line 29): 7-section template with `{graph_section}` placeholder -- needs instruction updates
- `synthesis.py:_format_related_content()` (line 117): Handles code_chunks with fenced code blocks -- extend for provenance annotations
- `linking.py:LinkedItem` (line 58): Shared result type with signals list -- graph provenance paths available via `graph:` prefix signals
- `linking.py:find_related_content()` (line ~329): 3-signal retrieval already includes graph results with provenance
- `graph_extractor.py:FilePathExtractor` (line 295): Creates CodeChunk entities from file path mentions -- extend for edge creation to actual code_chunks
- `code_chunk.py:CodeChunk` model: Has file_path, symbol_name, symbol_type, content, repo_full_name for matching

### Established Patterns
- Graph section renders empty string when no graph data (graceful degradation, Phase 25)
- Signal diversity first trimming under 2,000 token unified budget (Phase 25)
- Decision nodes get `[DECISION]` highlighting in graph section (Phase 25)
- Fail-silent graph operations -- errors logged but never raised (Phase 22)
- same_as edges followed transparently for identity resolution (Phase 23/25)

### Integration Points
- `backend/src/services/synthesis.py`: Update SYNTHESIS_TEMPLATE instructions, possibly enhance _format_related_content() for code provenance
- `backend/src/services/linking.py`: May need to annotate code_chunk LinkedItems with discussion provenance from graph edges
- `backend/src/services/graph_extractor.py`: Add logic to FilePathExtractor (or new extractor) to create edges from Slack messages to matching code_chunks
- `backend/src/services/graph_ops.py`: May need helper to find code_chunk graph nodes by file_path match

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 26-synthesis-code-to-discussion-linking*
*Context gathered: 2026-03-08*
