# Phase 23: Identity Resolution - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Unify person identities across Linear, Slack, GitHub, and Fathom into single canonical Person nodes in the knowledge graph. Email-based deterministic matching resolves known identities. Fuzzy name matching creates candidate same_as edges with confidence scores without auto-merging. Context pages will correctly attribute who said and decided what across tools.

</domain>

<decisions>
## Implementation Decisions

### Identity Mapping Table
- New `identity_mappings` table (not graph_nodes properties) -- dedicated table with (workspace_id, email, platform, platform_user_id, display_name)
- One row per platform identity -- normalized design: (email, 'slack', 'U12345', 'Daulet') with multiple rows per person
- Mapping table is the source of truth -- look up platform_user_id -> mapping row -> canonical Person node. Mapping table has FK to graph_nodes. Person node doesn't store platform IDs
- `canonical_person_id` column for multi-email support -- multiple emails can map to the same person. Supports work + personal email scenarios

### Roster Seeding Flow
- Seed during first sync + periodic weekly refresh -- pull team rosters from Linear (GraphQL team members), Slack (users.list), GitHub (org members / repo collaborators). Weekly refresh catches new team members
- Skip Fathom roster -- Fathom attendees extracted from meeting transcripts, not from a dedicated roster API
- Auto-resolve after seeding -- after pulling rosters, immediately run email matching and create canonical Person nodes + same_as edges. Fully automatic pipeline

### Merge vs Link Strategy
- Canonical node + same_as edges -- create one canonical Person node per real person. Keep platform-specific Person nodes (slack:U123, username:alice). Link them with same_as edges to canonical node
- Canonical Person fingerprint based on canonical_person_id from mapping table -- hash('Person:canonical:UUID'). Tied to the mapping table's person ID, stable if email changes
- Follow same_as transparently -- keep edges on platform nodes. Traversal follows same_as links to reach canonical. Existing edges untouched. Zero migration risk for existing graph data
- Inline resolution at extraction time -- after creating a platform Person node, check identity_mappings for a canonical match. If found, auto-create same_as edge. Real-time resolution for new content

### Claude's Discretion
- Fuzzy name matching algorithm, threshold, and confidence scoring model (IDENT-03)
- Exact migration file structure and ordering
- Roster API pagination and error handling
- How to handle platform users with no email returned by API
- Test fixture design for identity resolution

</decisions>

<specifics>
## Specific Ideas

- Phase 22 MentionExtractor already creates Person nodes with external_id like `slack:U12345` and `username:alice` -- identity resolution links these to canonical nodes
- `same_as` relationship type already defined in the graph edge taxonomy from Phase 22
- Registry pattern: identity resolution lookup could hook into extract_and_populate_graph() after entity creation, checking mapping table inline
- Linear GraphQL `users` query returns email + displayName + id; Slack `users.list` returns profile.email + real_name + id; GitHub REST `/orgs/{org}/members` or `/repos/{owner}/{repo}/collaborators` returns login (email via separate user endpoint)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `graph_ops.upsert_node()`: Fingerprint-based upsert for creating canonical Person nodes
- `graph_ops.upsert_edge()`: Create same_as edges between platform and canonical nodes
- `graph_extractor.extract_and_populate_graph()`: Hook point for inline identity resolution after entity creation
- `graph_extractor.MentionExtractor`: Already creates Person nodes from @mentions -- these become resolution targets
- `models/integration.py.OAuthToken`: OAuth tokens already stored per workspace/provider -- reuse for roster API calls

### Established Patterns
- Fingerprint deduplication: `hash(entity_type:external_id)` -- canonical nodes use `hash('Person:canonical:UUID')`
- Workspace-scoped RLS: All tables use workspace_id FK with RLS policy
- Polymorphic source_type + source_id: Same pattern for identity_mappings.platform column
- Soft deletes with deleted_at column
- Migration files: `NNNNN_description.sql` with idempotent DDL
- Background tasks in webhook handlers: Pattern for inline resolution calls

### Integration Points
- `backend/src/services/linear_sync.py`: Add roster pull during initial sync
- `backend/src/services/slack_oauth.py`: After OAuth connect, can trigger first roster pull
- `backend/src/services/github_sync.py`: Add roster pull during initial sync
- `backend/src/services/graph_extractor.py`: Hook identity lookup after Person node creation
- `supabase/migrations/`: Next migration for identity_mappings table
- `backend/src/models/`: New identity_mapping.py model file
- `backend/src/services/`: New identity_resolution.py service

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 23-identity-resolution*
*Context gathered: 2026-03-07*
