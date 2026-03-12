# Milestones

## v1.2 GraphRAG (Shipped: 2026-03-08)

**Phases:** 22-27 (6 phases, 13 plans)
**Commits:** 82 | **Files:** 88 changed (+19,642 / -108)
**Timeline:** 2 days (2026-03-07 → 2026-03-08)
**Requirements:** 26/26 satisfied
**Audit:** tech_debt (4 items, no blockers)

**Key accomplishments:**
- Knowledge graph schema (graph_nodes, graph_edges) with recursive CTE traversal, workspace-scoped RLS, and fingerprint deduplication
- Five regex extractors (ticket refs, PRs, @mentions, file paths, URLs) running inline in all webhook handlers at zero LLM cost
- Cross-source identity resolution via email-based matching with roster seeding from Linear/Slack/GitHub and rapidfuzz fuzzy candidate flagging
- Gemini Flash LLM extraction with decision/blocker persistence, source validation, and content hash deduplication
- Graph-enhanced retrieval as 3rd signal in find_related_content() with depth-decay scoring and token budget trimming
- Context pages enriched with decision trails, relationship paths, cross-referenced people, and code-to-discussion provenance
- Graph Explorer API endpoint (GET /api/graph/{ticket_identifier}) for structured subgraph JSON

**Tech debt accepted:**
- traverse_graph() missing source_type/source_id columns (graph results have empty snippets)
- Decision node snippet reads wrong property keys (shows "Unknown" for author/source/affects)
- Duplicated _compute_fingerprint() in llm_extractor.py
- Nyquist validation incomplete (6 phases draft status)

---

