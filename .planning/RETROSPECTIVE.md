# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.2 — GraphRAG

**Shipped:** 2026-03-08
**Phases:** 6 | **Plans:** 13

### What Was Built
- Knowledge graph schema (graph_nodes, graph_edges) with recursive CTE traversal, RLS, fingerprint deduplication
- Five regex extractors running inline in all 4 webhook handlers at zero LLM cost
- Cross-source identity resolution via email-based matching with roster seeding from Linear/Slack/GitHub
- Gemini Flash LLM extraction pipeline with decision/blocker persistence, source validation, content hash dedup
- Graph-enhanced retrieval as 3rd signal in linking engine with depth-decay scoring and token budget trimming
- Enriched synthesis template with conditional decision trails, relationship paths, people cross-references, code provenance
- Graph Explorer API endpoint (GET /api/graph/{ticket_identifier})

### What Worked
- **Two-tier extraction architecture** (regex inline + LLM batch) kept costs zero for structured data while enabling semantic extraction
- **Fail-silent pattern** across all graph features -- graph never breaks core ingestion, established in Phase 22 and consistently applied through Phase 27
- **Phase dependency design** -- parallelizable phases (23+24 after 22, 26+27 after 25) made efficient use of dev time
- **TDD approach** -- failing tests first in every plan, 547 tests passing at milestone end with zero regressions
- **Fingerprint deduplication** -- SHA-256 of entity_type:external_id prevented duplicates elegantly
- **SECURITY DEFINER traversal** -- validated workspace once, avoided per-row RLS overhead in recursive CTE

### What Was Inefficient
- **traverse_graph() missing source columns** -- discovered in integration check that source_type/source_id weren't projected, causing empty snippets. Could have been caught earlier if integration testing happened before Phase 25
- **Decision node property key mismatch** -- linking.py reads different property keys than what persist_decision() stores. The two phases (24, 25) used different naming conventions for the same data
- **Duplicated _compute_fingerprint()** in llm_extractor.py instead of importing from graph_ops -- introduced during Phase 24 to avoid import chain issues with test mocking, but created a maintenance risk
- **Nyquist validation left in draft** for all 6 phases -- validation strategy files created but wave-0 tests never run

### Patterns Established
- **Fail-silent graph pattern**: All graph operations wrapped in try/except with logger.warning, never raising to callers
- **Registry pattern with auto-registration**: Extractors auto-register at module import for zero-config loading
- **Lazy import pattern for cross-service dependencies**: Avoids circular imports and enables clean test mocking
- **Fingerprint-based upsert**: ON CONFLICT on (workspace_id, fingerprint) with update set for idempotent graph operations
- **Conditional synthesis instructions**: Template enrichments gated on "If the Graph Connections section contains..." to prevent LLM hallucination with empty data

### Key Lessons
1. **Cross-phase integration testing should happen earlier** -- the traverse_graph() column gap would have been caught immediately if Phase 25 tested against Phase 22's actual SQL output shape
2. **Property naming conventions need explicit contracts** -- when Phase 24 stores data and Phase 25 reads it, the property keys must be explicitly documented in a shared schema, not assumed
3. **Two-tier extraction is a proven pattern** -- regex for structured data (ticket refs, @mentions) and LLM for semantic data (decisions, rationale) is the right cost/quality tradeoff
4. **Recursive CTEs with SECURITY DEFINER work well** -- no need for graph extensions on Supabase Cloud, plain PG is sufficient for entity graph traversal
5. **Token budget trimming with signal diversity** prevents any single retrieval signal from dominating context pages

### Cost Observations
- Model mix: Quality profile -- opus for orchestration, sonnet for integration checking
- 6 phases completed in 2 days
- Notable: Phases 23+24 parallelized, Phases 26+27 parallelized -- effective phase dependency design

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 Dogfood | 14 | 16 | Foundation -- established core architecture and integrations |
| v1.1 Dashboard & Onboarding | 7 | 14 | UX polish -- dark theme, onboarding wizard, dashboard pages |
| v1.2 GraphRAG | 6 | 13 | Intelligence layer -- knowledge graph, entity extraction, enhanced synthesis |

### Cumulative Quality

| Milestone | Tests | Key Addition |
|-----------|-------|-------------|
| v1.0 | ~200 | Core backend tests |
| v1.1 | ~350 | Frontend + schema tests |
| v1.2 | 547 | Graph, extraction, identity, linking, synthesis tests |

### Top Lessons (Verified Across Milestones)

1. **Fail-silent patterns prevent feature work from breaking core functionality** (v1.0 webhooks, v1.2 graph extraction)
2. **TDD with failing tests first catches interface mismatches early** (all milestones)
3. **Phase dependency planning enables parallelization** (v1.2 achieved 2-day timeline with 6 phases)
