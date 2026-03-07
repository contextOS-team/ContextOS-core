# Phase 23: Identity Resolution - Research

**Researched:** 2026-03-07
**Domain:** Cross-platform identity matching, graph entity linking, roster API integration
**Confidence:** HIGH

## Summary

Phase 23 unifies person identities across Linear, Slack, GitHub, and Fathom into single canonical Person nodes in the knowledge graph. The implementation follows a three-layer approach: (1) a new `identity_mappings` Postgres table as the source of truth for email-to-person mapping, (2) roster seeding from platform APIs during integration setup with weekly refresh, and (3) inline identity resolution in the graph extraction pipeline that creates `same_as` edges from platform Person nodes to canonical Person nodes.

The main technical challenges are: the Slack API requires an additional OAuth scope (`users:read.email`) not currently configured, the GitHub API does not return emails from the collaborators endpoint and requires per-user API calls, and fuzzy name matching needs a carefully chosen threshold to avoid false positives. The recommended fuzzy matching library is `rapidfuzz` (MIT license, C++ backend, 5-100x faster than thefuzz, API-compatible).

**Primary recommendation:** Use `rapidfuzz` for fuzzy name matching with `token_sort_ratio` at threshold 80, store all mappings in a dedicated `identity_mappings` table with workspace-scoped RLS, and hook identity resolution inline in `extract_and_populate_graph()` after Person node creation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- New `identity_mappings` table (not graph_nodes properties) -- dedicated table with (workspace_id, email, platform, platform_user_id, display_name)
- One row per platform identity -- normalized design: (email, 'slack', 'U12345', 'Daulet') with multiple rows per person
- Mapping table is the source of truth -- look up platform_user_id -> mapping row -> canonical Person node. Mapping table has FK to graph_nodes. Person node doesn't store platform IDs
- `canonical_person_id` column for multi-email support -- multiple emails can map to the same person. Supports work + personal email scenarios
- Seed during first sync + periodic weekly refresh -- pull team rosters from Linear (GraphQL team members), Slack (users.list), GitHub (org members / repo collaborators). Weekly refresh catches new team members
- Skip Fathom roster -- Fathom attendees extracted from meeting transcripts, not from a dedicated roster API
- Auto-resolve after seeding -- after pulling rosters, immediately run email matching and create canonical Person nodes + same_as edges. Fully automatic pipeline
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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| IDENT-01 | Person identities are unified across Linear, Slack, GitHub, and Fathom via email-based deterministic matching | identity_mappings table with email column, canonical_person_id FK, and inline resolution in extract_and_populate_graph() creating same_as edges |
| IDENT-02 | Identity mapping table is seeded from team roster APIs during integration setup | Roster pull functions for Linear (GraphQL `users` query), Slack (`users.list` with `users:read.email` scope), GitHub (collaborators + per-user email lookup); triggered after first sync with weekly refresh |
| IDENT-03 | Fuzzy name matches create candidate same_as edges with confidence scores without auto-merging | rapidfuzz library with `token_sort_ratio`, threshold 80, confidence score stored in same_as edge properties, candidate edges have `status: 'candidate'` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rapidfuzz | >=3.0 | Fuzzy string matching for name comparison | MIT license (vs thefuzz GPL), C++ backend (5-100x faster), API-compatible with thefuzz, widely adopted |
| sqlmodel | >=0.0.22 | IdentityMapping model definition | Already used for all models in the project |
| sqlalchemy[asyncio] | >=2.0 | Async DB operations for roster seeding and resolution | Already the project ORM |
| httpx[http2] | - | API calls to Linear/Slack/GitHub for roster data | Already used for all external API calls |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | - | Async PostgreSQL driver | Already installed, used for all DB operations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rapidfuzz | thefuzz (fuzzywuzzy) | thefuzz is GPL licensed, 5-100x slower, same API surface |
| rapidfuzz | jellyfish | Lower-level (individual metrics only), no token_sort_ratio convenience |
| Dedicated identity_mappings table | JSONB properties on graph_nodes | Locked decision: separate table provides relational integrity, queryable indexes, multi-email support |

**Installation:**
```bash
cd backend && pip install rapidfuzz
```

Add to `pyproject.toml` dependencies:
```toml
"rapidfuzz>=3.0",
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/
  models/
    identity_mapping.py     # IdentityMapping SQLModel
  services/
    identity_resolution.py  # Core resolution logic + roster seeding
    graph_extractor.py      # Modified: hook identity resolution after Person node creation
supabase/migrations/
  00019_identity_mappings.sql  # New table + RLS + indexes
```

### Pattern 1: Identity Mapping Table Schema
**What:** Dedicated table linking platform user IDs to canonical persons via email
**When to use:** All identity resolution lookups

```sql
-- Migration: 00019_identity_mappings.sql
CREATE TABLE public.identity_mappings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  email text NOT NULL,
  platform text NOT NULL CHECK (platform IN ('linear', 'slack', 'github', 'fathom')),
  platform_user_id text NOT NULL,
  display_name text,
  canonical_person_id uuid REFERENCES public.graph_nodes(id) ON DELETE SET NULL,
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT identity_mappings_workspace_platform_user_key
    UNIQUE (workspace_id, platform, platform_user_id)
);

-- Lookup by platform user ID (primary resolution path)
CREATE INDEX idx_identity_mappings_platform_lookup
  ON public.identity_mappings (workspace_id, platform, platform_user_id);

-- Lookup by email (for cross-platform matching)
CREATE INDEX idx_identity_mappings_email
  ON public.identity_mappings (workspace_id, email);

-- Lookup by canonical person (for listing all identities of a person)
CREATE INDEX idx_identity_mappings_canonical
  ON public.identity_mappings (canonical_person_id)
  WHERE canonical_person_id IS NOT NULL;

-- RLS
ALTER TABLE public.identity_mappings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "workspace_data" ON public.identity_mappings
  FOR ALL USING (
    workspace_id IN (
      SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
    )
  );

-- Moddatetime trigger
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.identity_mappings
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
```

### Pattern 2: Canonical Person Node Creation
**What:** Create one canonical Person node per unique real person, linked via same_as edges
**When to use:** After roster seeding matches emails across platforms

```python
# Canonical node fingerprint: hash('Person:canonical:{UUID}')
# The UUID is the canonical_person_id from identity_mappings
import uuid
from src.services.graph_ops import compute_fingerprint, upsert_node, upsert_edge

async def create_canonical_person(
    session, workspace_id, canonical_id: uuid.UUID, name: str
) -> uuid.UUID:
    """Create or update a canonical Person node."""
    return await upsert_node(
        session=session,
        workspace_id=workspace_id,
        entity_type="Person",
        external_id=f"canonical:{canonical_id}",
        name=name,
        properties={"canonical": True, "canonical_person_id": str(canonical_id)},
    )
```

### Pattern 3: Inline Identity Resolution Hook
**What:** After Person node creation in extract_and_populate_graph, check identity_mappings for a canonical match
**When to use:** Every time a Person entity is extracted from content

```python
# In graph_extractor.py, after entity node creation for Person entities:
async def resolve_identity(
    session, workspace_id, entity: ExtractedEntity, entity_node_id: uuid.UUID
) -> None:
    """Check if a platform Person node maps to a canonical person."""
    if entity.entity_type != "Person":
        return

    platform_user_id = entity.properties.get("platform_user_id") or entity.properties.get("username")
    platform = entity.properties.get("platform", "")

    if not platform_user_id or not platform:
        return

    # Look up identity_mappings for this platform user
    mapping = await lookup_mapping(session, workspace_id, platform, platform_user_id)
    if mapping and mapping.canonical_person_id:
        # Create same_as edge from platform node to canonical node
        await upsert_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=entity_node_id,
            target_node_id=mapping.canonical_person_id,  # FK to graph_nodes
            relationship_type="same_as",
        )
```

### Pattern 4: Roster Seeding Flow
**What:** Pull team members from platform APIs, populate identity_mappings, then run email-based matching
**When to use:** After integration connect (first sync) and weekly refresh

```python
async def seed_roster(session, workspace_id, platform: str) -> int:
    """Seed identity_mappings from a platform's roster API."""
    # 1. Fetch roster from platform API
    members = await fetch_platform_roster(session, workspace_id, platform)

    # 2. Upsert each member into identity_mappings
    count = 0
    for member in members:
        await upsert_identity_mapping(
            session, workspace_id,
            email=member["email"],
            platform=platform,
            platform_user_id=member["platform_user_id"],
            display_name=member["display_name"],
        )
        count += 1

    # 3. Run email-based resolution to create canonical persons
    await resolve_by_email(session, workspace_id)

    return count
```

### Anti-Patterns to Avoid
- **Storing platform IDs on the canonical Person node:** The canonical node must remain platform-agnostic. Platform IDs belong in identity_mappings only.
- **Auto-merging on name alone:** Names are not unique identifiers. Two "John Smith" entries from different platforms should never be auto-merged. Create candidate same_as edges with confidence scores instead.
- **Modifying existing edges when linking identities:** Existing edges (mentions, references) stay on platform Person nodes. The same_as edge provides the bridge to the canonical node. Zero migration of existing data.
- **Blocking content ingestion on identity resolution failure:** Identity resolution is additive, like graph extraction. Failures must be logged but never block the webhook handler pipeline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein implementation | rapidfuzz `token_sort_ratio` | Handles name order variation ("John Smith" vs "Smith, John"), Unicode normalization, optimized C++ core |
| Email normalization | Regex email cleanup | Lowercase + strip + split on `+` (for Gmail aliases) | Simple but must be consistent everywhere. Centralize in one function |
| Slack user list pagination | Manual cursor tracking | Reuse Slack cursor-based pagination pattern | Slack uses `next_cursor` in response_metadata, consistent pattern |
| Linear GraphQL pagination | Custom pagination | Reuse `LinearGraphQLClient.fetch_all_pages()` | Already handles cursor-based pagination with retry/backoff |
| GitHub API pagination | Custom Link header parsing | Reuse `parse_link_next()` from github_common | Already handles RFC 5988 Link headers |

**Key insight:** The project already has pagination, rate limiting, and API client patterns for all three platforms. Roster seeding should reuse these existing patterns rather than building new ones.

## Common Pitfalls

### Pitfall 1: Slack users:read.email Scope Missing
**What goes wrong:** Slack `users.list` returns user objects WITHOUT the email field, making email-based identity resolution impossible for Slack users.
**Why it happens:** The current `SLACK_BOT_SCOPES` in `slack_oauth.py` only includes `users:read`, not `users:read.email`. Apps created after Jan 2017 must explicitly request `users:read.email` to access email data.
**How to avoid:** Add `users:read.email` to `SLACK_BOT_SCOPES` constant. Existing Slack integrations will need to be re-authorized (disconnect + reconnect) to pick up the new scope. Include a migration note.
**Warning signs:** Empty email fields in Slack roster data. The profile object will have all other fields but email will be null/missing.

### Pitfall 2: GitHub Collaborators Endpoint Has No Email
**What goes wrong:** `GET /repos/{owner}/{repo}/collaborators` returns login, id, avatar_url, permissions -- but NOT email. Building roster seeding assuming this endpoint returns email will fail silently.
**Why it happens:** GitHub's collaborators endpoint is a lightweight listing. Email is on the separate `/users/{login}` endpoint and only if the user has a public email set.
**How to avoid:** For GitHub, store `login` as the primary identifier in identity_mappings. Use `GET /users/{login}` for each collaborator to attempt email lookup. Accept that many GitHub users will have no public email -- store mapping with null email and match by username instead.
**Warning signs:** identity_mappings rows with null email for GitHub platform entries.

### Pitfall 3: Canonical Person ID Collision on Multi-Email
**What goes wrong:** The same real person uses different emails across platforms (work email on Slack, personal on GitHub). Two separate canonical_person_id values get created.
**Why it happens:** Email-based matching can only link identities that share the same email address.
**How to avoid:** The `canonical_person_id` column allows manual or fuzzy-match-assisted merging. When fuzzy name matching detects a potential match across different emails, create a candidate same_as edge. An admin can later confirm and unify the canonical_person_id values.
**Warning signs:** Multiple canonical Person nodes with similar names but different emails.

### Pitfall 4: Fuzzy Match False Positives
**What goes wrong:** Common names like "John Smith" match across unrelated people, creating incorrect candidate same_as edges that pollute the graph.
**Why it happens:** Token sort ratio scores similar short names very highly.
**How to avoid:** Set threshold at 80 (not lower). Require at least one additional signal (same workspace role, overlapping team membership) before creating candidate edge. Store confidence score in edge properties for filtering. Never auto-merge on name alone.
**Warning signs:** High volume of candidate same_as edges with no confirmed merges.

### Pitfall 5: Race Condition in Inline Resolution
**What goes wrong:** A Person node is created by the graph extractor before the roster has been seeded, so no identity_mapping exists yet. The same_as edge is never created.
**Why it happens:** Content arrives via webhooks before the roster seeding has completed for a newly connected integration.
**How to avoid:** After roster seeding completes, run a backfill pass that checks all existing Person nodes against the newly populated identity_mappings. This catches any nodes created before the roster was available.
**Warning signs:** Person nodes with platform identifiers but no same_as edge to any canonical node.

### Pitfall 6: N+1 Query in Inline Resolution
**What goes wrong:** Every Person node extraction triggers an individual SELECT against identity_mappings, causing one query per mention in a message.
**Why it happens:** Naive implementation of the inline resolution hook.
**How to avoid:** Batch the resolution: after all entities are extracted from a piece of content, collect all Person entities and resolve them in a single query (WHERE platform_user_id IN (...)). Cache recently resolved mappings in-memory during a single extraction run.
**Warning signs:** Slow graph extraction times when content has many @mentions.

## Code Examples

### Example 1: IdentityMapping SQLModel
```python
# backend/src/models/identity_mapping.py
"""IdentityMapping model mapping to public.identity_mappings table."""

import uuid
from sqlalchemy import UniqueConstraint
from sqlmodel import Field
from src.models.base import BaseModel


class IdentityMapping(BaseModel, table=True):
    """Maps a platform user identity to a canonical person.

    Each row represents one platform identity (e.g., one Slack user).
    Multiple rows with the same canonical_person_id represent the
    same real person across platforms.
    """

    __tablename__ = "identity_mappings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "platform", "platform_user_id",
            name="identity_mappings_workspace_platform_user_key",
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    email: str | None = Field(default=None)
    platform: str = Field(nullable=False)
    platform_user_id: str = Field(nullable=False)
    display_name: str | None = Field(default=None)
    canonical_person_id: uuid.UUID | None = Field(
        default=None, foreign_key="graph_nodes.id"
    )
```

### Example 2: Email-Based Resolution Logic
```python
# Core resolution: group by email, create canonical person per email cluster
async def resolve_by_email(session, workspace_id) -> int:
    """Match identity_mappings rows by email and create canonical Person nodes.

    Groups mappings by (workspace_id, email), creates one canonical Person
    per unique email, and links all platform nodes via same_as edges.
    """
    from sqlmodel import select, func
    from src.models.identity_mapping import IdentityMapping

    # Find all emails that appear in mappings for this workspace
    stmt = (
        select(IdentityMapping.email, func.count())
        .where(
            IdentityMapping.workspace_id == workspace_id,
            IdentityMapping.email.isnot(None),
            IdentityMapping.deleted_at.is_(None),
        )
        .group_by(IdentityMapping.email)
    )
    # ... group by email, create canonical nodes, update canonical_person_id
```

### Example 3: Fuzzy Name Matching
```python
from rapidfuzz import fuzz

FUZZY_THRESHOLD = 80  # Minimum score to create candidate same_as edge

def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Compute fuzzy similarity between two person names.

    Uses token_sort_ratio which handles name order variations:
    "John Smith" vs "Smith, John" -> 100.0

    Returns a score from 0.0 to 100.0.
    """
    return fuzz.token_sort_ratio(
        name_a.lower().strip(),
        name_b.lower().strip(),
        score_cutoff=FUZZY_THRESHOLD,
    )


def build_confidence_score(name_score: float, shared_workspace: bool = True) -> float:
    """Convert fuzzy match score to a 0.0-1.0 confidence score.

    Higher confidence when:
    - Name similarity is higher (80-100 range mapped to 0.5-0.9)
    - Users share the same workspace (always true in our case)
    """
    # Normalize 80-100 range to 0.5-0.9
    normalized = 0.5 + (name_score - FUZZY_THRESHOLD) / (100 - FUZZY_THRESHOLD) * 0.4
    return round(min(normalized, 0.9), 2)  # Cap at 0.9 -- never 1.0 for name-only
```

### Example 4: Slack Roster Fetch
```python
# Reuses existing bot token retrieval and httpx patterns
async def fetch_slack_roster(session, workspace_id) -> list[dict]:
    """Fetch all Slack workspace members with email addresses.

    Requires users:read and users:read.email scopes.
    Uses cursor-based pagination (200 members per page).
    """
    from src.services.slack_oauth import get_bot_token

    bot_token = await get_bot_token(session, workspace_id)
    members = []
    cursor = None

    async with httpx.AsyncClient() as client:
        while True:
            params = {"limit": 200}
            if cursor:
                params["cursor"] = cursor

            response = await client.get(
                "https://slack.com/api/users.list",
                headers={"Authorization": f"Bearer {bot_token}"},
                params=params,
            )
            data = response.json()
            if not data.get("ok"):
                break

            for member in data.get("members", []):
                # Skip bots and deactivated users
                if member.get("is_bot") or member.get("deleted"):
                    continue
                profile = member.get("profile", {})
                email = profile.get("email")
                members.append({
                    "platform_user_id": member["id"],
                    "display_name": profile.get("real_name") or member.get("name", ""),
                    "email": email,  # May be None if scope not granted
                })

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    return members
```

### Example 5: Linear Roster Fetch
```python
# Linear GraphQL query for organization users
LINEAR_USERS_QUERY = """
query($after: String) {
    users(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
            id
            name
            displayName
            email
            active
        }
    }
}
"""

async def fetch_linear_roster(session, workspace_id, user_id, settings) -> list[dict]:
    """Fetch all Linear organization users via GraphQL.

    Reuses LinearGraphQLClient.fetch_all_pages() for pagination.
    """
    from src.services.linear_graphql import LinearGraphQLClient
    from src.services.linear_oauth import get_valid_access_token

    access_token = await get_valid_access_token(session, workspace_id, user_id, settings)
    client = LinearGraphQLClient(access_token)
    try:
        users = await client.fetch_all_pages(
            LINEAR_USERS_QUERY, {}, ["users"]
        )
        return [
            {
                "platform_user_id": user["id"],
                "display_name": user.get("displayName") or user.get("name", ""),
                "email": user.get("email"),
            }
            for user in users
            if user.get("active", True)  # Skip deactivated users
        ]
    finally:
        await client.close()
```

### Example 6: GitHub Roster Fetch
```python
async def fetch_github_roster(session, workspace_id, settings) -> list[dict]:
    """Fetch collaborators from all selected GitHub repos.

    GitHub collaborators endpoint does NOT return email.
    For each collaborator, attempt GET /users/{login} for public email.
    Many users will have no public email -- store with null email.
    """
    from src.services.github_common import (
        GITHUB_API_BASE, create_github_client, github_headers,
        check_rate_limit, parse_link_next,
    )
    from src.services.github_oauth import get_installation_token
    from src.services.github_repos import get_selected_repos

    token = await get_installation_token(workspace_id, session, settings)
    selected_repos = await get_selected_repos(workspace_id, session)
    seen_logins: set[str] = set()
    members = []

    async with create_github_client() as client:
        for repo in selected_repos:
            url = f"{GITHUB_API_BASE}/repos/{repo}/collaborators?per_page=100"
            while url:
                response = await client.get(url, headers=github_headers(token))
                if response.status_code != 200:
                    break
                await check_rate_limit(response)

                for collab in response.json():
                    login = collab.get("login", "")
                    if login in seen_logins or not login:
                        continue
                    seen_logins.add(login)

                    # Attempt email lookup via /users/{login}
                    email = await _fetch_user_email(client, token, login)
                    members.append({
                        "platform_user_id": login,
                        "display_name": login,  # GitHub login as display name
                        "email": email,  # May be None
                    })

                url = parse_link_next(response.headers.get("link"))

    return members
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| thefuzz (fuzzywuzzy) for fuzzy matching | rapidfuzz (MIT, C++ backend) | 2021+ | 5-100x faster, MIT license, drop-in replacement API |
| Storing identity mappings in JSONB properties | Dedicated relational table | Project decision | Enables SQL joins, proper indexes, multi-email FK relationships |
| Auto-merging on name match | Candidate edges with confidence scores | Industry standard | Prevents false merges, enables human-in-the-loop confirmation |

**Deprecated/outdated:**
- fuzzywuzzy: Renamed to thefuzz, but GPL license makes it unsuitable for commercial projects. Use rapidfuzz instead.

## Open Questions

1. **Linear `users` Query Scope**
   - What we know: Linear's GraphQL API has a `users` query that returns organization members with email, name, displayName, active fields. The `fetch_all_pages` pattern already handles Linear pagination.
   - What's unclear: Whether the OAuth token scope obtained during integration setup has access to the `users` query, or if it requires additional permissions.
   - Recommendation: Test the `users` query with the existing access token during implementation. Linear's API is permissive -- organization-level queries typically work with any authenticated token within the organization. LOW risk.

2. **GitHub Email Availability**
   - What we know: GitHub collaborators endpoint returns login only. The `/users/{login}` endpoint may return email if the user has set a public email.
   - What's unclear: What percentage of GitHub users have public emails set. In enterprise environments, this is often 0%.
   - Recommendation: Accept that GitHub identity resolution may rely heavily on username matching rather than email. Store the login as `platform_user_id` and use fuzzy name matching as the fallback. Consider matching GitHub login against Linear/Slack display names as an additional signal.

3. **Slack Scope Re-authorization**
   - What we know: Adding `users:read.email` to bot scopes requires existing Slack integrations to disconnect and reconnect.
   - What's unclear: Whether the scope change can be applied automatically or requires user action in the Slack App dashboard.
   - Recommendation: Update the scope constant. New integrations will get the scope automatically. For existing integrations, document the re-authorization step. Consider detecting the missing scope and displaying a warning in the UI (future enhancement, not this phase).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_identity_resolution.py -x` |
| Full suite command | `cd backend && python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IDENT-01 | Email-based deterministic matching creates canonical Person + same_as edges | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestEmailResolution -x` | No -- Wave 0 |
| IDENT-01 | Inline resolution hook creates same_as edge after Person node extraction | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestInlineResolution -x` | No -- Wave 0 |
| IDENT-02 | Slack roster seeding populates identity_mappings correctly | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestSlackRoster -x` | No -- Wave 0 |
| IDENT-02 | Linear roster seeding populates identity_mappings correctly | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestLinearRoster -x` | No -- Wave 0 |
| IDENT-02 | GitHub roster seeding populates identity_mappings correctly | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestGitHubRoster -x` | No -- Wave 0 |
| IDENT-03 | Fuzzy name matching creates candidate same_as edge with confidence score | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestFuzzyMatching -x` | No -- Wave 0 |
| IDENT-03 | Names below threshold do NOT create candidate edges | unit | `cd backend && python -m pytest tests/test_identity_resolution.py::TestFuzzyMatching::test_below_threshold -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_identity_resolution.py -x`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_identity_resolution.py` -- covers IDENT-01, IDENT-02, IDENT-03
- [ ] `rapidfuzz>=3.0` in pyproject.toml dependencies -- required for IDENT-03 fuzzy matching

## Sources

### Primary (HIGH confidence)
- Codebase: `backend/src/services/graph_ops.py` -- fingerprint computation and upsert patterns
- Codebase: `backend/src/services/graph_extractor.py` -- extract_and_populate_graph orchestrator, MentionExtractor Person node creation pattern
- Codebase: `backend/src/models/graph_node.py` -- GraphNode model with fingerprint-based dedup
- Codebase: `backend/src/models/graph_edge.py` -- GraphEdge model with composite key dedup
- Codebase: `backend/src/services/slack_oauth.py` -- Current SLACK_BOT_SCOPES (missing users:read.email)
- Codebase: `backend/src/services/linear_sync.py` -- TEAMS_QUERY and pagination patterns
- Codebase: `backend/src/services/linear_graphql.py` -- LinearGraphQLClient with fetch_all_pages
- Codebase: `backend/src/services/github_sync.py` -- GitHub collaborator sync patterns
- Codebase: `backend/src/services/github_common.py` -- GitHub API helpers (headers, pagination, rate limits)
- Codebase: `supabase/migrations/00017_graph_tables.sql` -- Graph table DDL with same_as in relationship_type CHECK constraint

### Secondary (MEDIUM confidence)
- [Slack users.list API documentation](https://docs.slack.dev/reference/methods/users.list/) -- Response fields, pagination, scope requirements
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz) -- MIT license, API surface, version info
- [RapidFuzz fuzz module docs](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) -- token_sort_ratio, score_cutoff parameter
- [GitHub REST API collaborators](https://docs.github.com/en/rest/collaborators/collaborators) -- Response schema (no email field)

### Tertiary (LOW confidence)
- Linear `users` GraphQL query field availability -- verified from schema.graphql reference on GitHub but unable to load full schema due to rate limiting. The query structure (id, name, displayName, email, active) is consistent with Linear's documented patterns but should be validated during implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- rapidfuzz is well-established, MIT licensed, and is the clear choice over thefuzz
- Architecture: HIGH -- All patterns directly derived from locked user decisions and existing codebase patterns (fingerprint dedup, upsert_node/upsert_edge, extract_and_populate_graph hook)
- Pitfalls: HIGH -- Slack scope issue verified directly in codebase (SLACK_BOT_SCOPES missing users:read.email), GitHub email limitation confirmed via official docs
- Roster APIs: MEDIUM -- Linear users query structure inferred from schema reference; Slack and GitHub APIs verified via official docs

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable domain -- identity resolution patterns are well-established)
