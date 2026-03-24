"""Identity resolution: email-based deterministic matching for person unification.

Provides:
  - create_canonical_person: Create a canonical Person graph node
  - lookup_mapping: Find an identity mapping by platform + user ID
  - resolve_by_email: Group mappings by email and create canonical nodes
  - resolve_identity_inline: Hook for real-time resolution during extraction
  - fetch_linear_roster: Fetch team members from Linear GraphQL API
  - fetch_slack_roster: Fetch workspace members from Slack users.list API
  - fetch_github_roster: Fetch collaborators from GitHub repos API
  - upsert_identity_mapping: Upsert a single identity mapping row
  - seed_roster: Orchestrate roster upsert + resolve + fuzzy matching
  - compute_name_similarity: Fuzzy name comparison with rapidfuzz
  - find_fuzzy_candidates: Create candidate same_as edges for similar names
  - backfill_identity_resolution: Link pre-existing Person nodes retroactively

Canonical Person nodes use fingerprint hash('Person:canonical:{UUID}') and
are linked to platform-specific Person nodes via same_as edges.
"""

import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

import httpx
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.identity_mapping import IdentityMapping
from src.services.graph_ops import upsert_edge, upsert_node

logger = logging.getLogger(__name__)


async def create_canonical_person(
    session: AsyncSession,
    workspace_id: UUID,
    canonical_id: UUID,
    name: str,
) -> UUID:
    """Create a canonical Person graph node.

    Uses external_id='canonical:{UUID}' so the fingerprint is
    hash('Person:canonical:{UUID}') -- stable and deterministic.

    Args:
        session: Async database session.
        workspace_id: Workspace the node belongs to.
        canonical_id: UUID identifying this canonical person (from mapping table).
        name: Display name for the canonical Person node.

    Returns:
        UUID of the created/updated graph node.
    """
    node_id = await upsert_node(
        session=session,
        workspace_id=workspace_id,
        entity_type="Person",
        external_id=f"canonical:{canonical_id}",
        name=name,
        properties={
            "canonical": True,
            "canonical_person_id": str(canonical_id),
        },
    )
    logger.info(
        "Created canonical Person node %s for canonical_id=%s",
        node_id,
        canonical_id,
    )
    return node_id


async def lookup_mapping(
    session: AsyncSession,
    workspace_id: UUID,
    platform: str,
    platform_user_id: str,
) -> IdentityMapping | None:
    """Look up an identity mapping by workspace + platform + platform_user_id.

    Args:
        session: Async database session.
        workspace_id: Workspace to search in.
        platform: Platform name ('slack', 'github', 'linear', 'fathom').
        platform_user_id: Platform-specific user identifier.

    Returns:
        The matching IdentityMapping or None if not found.
    """
    stmt = (
        select(IdentityMapping)
        .where(
            IdentityMapping.workspace_id == workspace_id,
            IdentityMapping.platform == platform,
            IdentityMapping.platform_user_id == platform_user_id,
            IdentityMapping.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def resolve_by_email(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Resolve identities by grouping mappings with the same email.

    For each unique email in identity_mappings (within the workspace):
    - If no mapping in the group has a canonical_person_id yet, create a
      new canonical Person node and assign it to all mappings in the group.
    - If mappings already have a canonical_person_id, skip (idempotent).
    - For each mapping with a canonical_person_id, create a same_as edge
      from its platform Person node to the canonical node.

    Args:
        session: Async database session.
        workspace_id: Workspace to process.

    Returns:
        Number of new canonical persons created.
    """
    from collections import defaultdict

    # Bulk fetch ALL mappings with email in one query
    all_stmt = (
        select(IdentityMapping)
        .where(
            IdentityMapping.workspace_id == workspace_id,
            IdentityMapping.email.isnot(None),
            IdentityMapping.deleted_at.is_(None),
        )
        .order_by(IdentityMapping.email)
    )
    all_result = await session.execute(all_stmt)
    all_mappings = all_result.scalars().all()

    if not all_mappings:
        return 0

    # Group by email in Python
    email_groups: dict[str, list[IdentityMapping]] = defaultdict(list)
    for m in all_mappings:
        if m.email:
            email_groups[m.email].append(m)

    created_count = 0

    for email, mappings in email_groups.items():
        # Check if any mapping already has a canonical_person_id
        existing_canonical = None
        for m in mappings:
            if m.canonical_person_id is not None:
                existing_canonical = m.canonical_person_id
                break

        if existing_canonical is None:
            canonical_id = uuid.uuid4()
            display_name = mappings[0].display_name or email
            canonical_node_id = await create_canonical_person(
                session, workspace_id, canonical_id, display_name
            )
            for m in mappings:
                m.canonical_person_id = canonical_node_id
            created_count += 1
            for m in mappings:
                await _create_same_as_edge(
                    session, workspace_id, m, canonical_node_id
                )
        else:
            for m in mappings:
                if m.canonical_person_id is None:
                    m.canonical_person_id = existing_canonical
                await _create_same_as_edge(
                    session, workspace_id, m, existing_canonical
                )

    return created_count


async def _create_same_as_edge(
    session: AsyncSession,
    workspace_id: UUID,
    mapping: IdentityMapping,
    canonical_node_id: UUID,
) -> None:
    """Create a same_as edge from a platform Person node to its canonical node.

    Looks up the platform Person node by computing its expected fingerprint
    from entity_type='Person' and the platform external_id.
    """
    from src.services.graph_ops import compute_fingerprint

    # Determine the external_id used by the platform Person node
    platform_external_id = f"{mapping.platform}:{mapping.platform_user_id}"
    expected_fingerprint = compute_fingerprint("Person", platform_external_id)

    # Try to find the platform Person node
    from src.models.graph_node import GraphNode

    stmt = (
        select(GraphNode.id)
        .where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.fingerprint == expected_fingerprint,
            GraphNode.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    platform_node_id = result.scalar_one_or_none()

    if platform_node_id is not None:
        await upsert_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=platform_node_id,
            target_node_id=canonical_node_id,
            relationship_type="same_as",
        )
        logger.info(
            "Created same_as edge: %s -> %s (platform=%s, user=%s)",
            platform_node_id,
            canonical_node_id,
            mapping.platform,
            mapping.platform_user_id,
        )


async def resolve_identity_inline(
    session: AsyncSession,
    workspace_id: UUID,
    entity: "ExtractedEntity",
    entity_node_id: UUID,
) -> None:
    """Inline identity resolution: link a Person entity to its canonical node.

    Called after each Person entity node is created during graph extraction.
    Extracts platform and platform_user_id from the entity's properties or
    external_id, then looks up the identity mapping. If a mapping with a
    canonical_person_id exists, creates a same_as edge.

    Non-blocking: logs and returns on any error (fail-silent pattern).

    Args:
        session: Async database session.
        workspace_id: Workspace the entity belongs to.
        entity: The extracted entity (only acts on Person entities).
        entity_node_id: UUID of the entity's graph node.
    """
    from src.services.graph_extractor import ExtractedEntity

    try:
        # Only act on Person entities
        if entity.entity_type != "Person":
            return

        # Extract platform and platform_user_id from entity properties
        platform = entity.properties.get("platform")
        platform_user_id = entity.properties.get("platform_user_id")

        # Fallback: parse from external_id (e.g. "slack:U12345")
        if not platform or not platform_user_id:
            if ":" in entity.external_id:
                parts = entity.external_id.split(":", 1)
                platform = platform or parts[0]
                platform_user_id = platform_user_id or parts[1]

        if not platform or not platform_user_id:
            logger.debug(
                "Cannot resolve identity for entity %s: missing platform or user_id",
                entity.external_id,
            )
            return

        mapping = await lookup_mapping(session, workspace_id, platform, platform_user_id)

        if mapping is None:
            logger.debug(
                "No identity mapping for %s:%s in workspace %s",
                platform,
                platform_user_id,
                workspace_id,
            )
            return

        if mapping.canonical_person_id is None:
            logger.debug(
                "Mapping exists for %s:%s but no canonical_person_id yet",
                platform,
                platform_user_id,
            )
            return

        # Create same_as edge from entity node to canonical node
        await upsert_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=entity_node_id,
            target_node_id=mapping.canonical_person_id,
            relationship_type="same_as",
        )
        logger.info(
            "Inline identity resolution: %s -> canonical %s",
            entity_node_id,
            mapping.canonical_person_id,
        )

    except Exception:
        logger.warning(
            "Inline identity resolution failed for entity %s (workspace=%s)",
            entity.external_id,
            workspace_id,
            exc_info=True,
        )


# ============================================================
# Roster fetch functions
# ============================================================

# Linear users GraphQL query
LINEAR_USERS_QUERY = """
query($after: String) {
    users(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { id name displayName email active }
    }
}
"""


async def fetch_linear_roster(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: "Settings",
) -> list[dict]:
    """Fetch active team members from Linear via GraphQL.

    Uses the LinearGraphQLClient with cursor-based pagination to fetch
    all active users in the Linear organization.

    Args:
        session: Async database session.
        workspace_id: Workspace to fetch roster for.
        user_id: User who initiated the action (for token lookup).
        settings: Application settings.

    Returns:
        List of dicts with platform_user_id, display_name, email.
    """
    from src.services.linear_graphql import LinearGraphQLClient
    from src.services.linear_oauth import get_valid_access_token

    access_token = await get_valid_access_token(session, workspace_id, user_id, settings)
    client = LinearGraphQLClient(access_token)

    try:
        all_users = await client.fetch_all_pages(
            LINEAR_USERS_QUERY, {}, ["users"]
        )
    finally:
        await client.close()

    members: list[dict] = []
    for user in all_users:
        if not user.get("active", True):
            continue
        members.append({
            "platform_user_id": user["id"],
            "display_name": user.get("name") or user.get("displayName") or user.get("email", ""),
            "email": user.get("email"),
        })

    logger.info(
        "Fetched %d active Linear users for workspace %s",
        len(members),
        workspace_id,
    )
    return members


async def fetch_slack_roster(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[dict]:
    """Fetch non-bot workspace members from Slack users.list API.

    Uses cursor-based pagination with the Slack bot token.
    Skips bot accounts and deleted users.

    Args:
        session: Async database session.
        workspace_id: Workspace to fetch roster for.

    Returns:
        List of dicts with platform_user_id, display_name, email.
    """
    from src.services.slack_oauth import get_bot_token

    bot_token = await get_bot_token(session, workspace_id)

    members: list[dict] = []
    cursor: str | None = None

    async with httpx.AsyncClient() as client:
        while True:
            params: dict = {
                "limit": 200,
            }
            if cursor:
                params["cursor"] = cursor

            response = await client.get(
                "https://slack.com/api/users.list",
                params=params,
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            data = response.json()

            for member in data.get("members", []):
                # Skip bots and deleted users
                if member.get("is_bot", False):
                    continue
                if member.get("deleted", False):
                    continue

                profile = member.get("profile", {})
                display_name = profile.get("real_name") or member.get("name", "")
                email = profile.get("email")

                members.append({
                    "platform_user_id": member["id"],
                    "display_name": display_name,
                    "email": email,
                })

            # Check for next page
            next_cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not next_cursor:
                break
            cursor = next_cursor

    logger.info(
        "Fetched %d Slack members for workspace %s",
        len(members),
        workspace_id,
    )
    return members


async def fetch_jira_roster(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[dict]:
    """Extract unique people (assignees + reporters) from synced Jira issues.

    Unlike Linear/Slack/GitHub which have dedicated user-list APIs, Jira Cloud
    restricts user enumeration. Instead we extract unique users from the
    raw_data JSONB of already-synced issues — no extra API calls needed.

    Returns:
        List of dicts with platform_user_id, display_name, email.
    """
    from src.models.jira import JiraIssue

    stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    issues = result.scalars().all()

    seen: set[str] = set()
    members: list[dict] = []

    for issue in issues:
        raw = issue.raw_data or {}
        fields = raw.get("fields", {})

        for role in ("assignee", "reporter"):
            person = fields.get(role)
            if not person or not isinstance(person, dict):
                continue
            account_id = person.get("accountId")
            if not account_id or account_id in seen:
                continue
            seen.add(account_id)
            members.append({
                "platform_user_id": account_id,
                "display_name": person.get("displayName") or "",
                "email": person.get("emailAddress"),
            })

    logger.info(
        "Extracted %d unique Jira users from %d issues for workspace %s",
        len(members), len(issues), workspace_id,
    )
    return members


async def fetch_github_roster(
    session: AsyncSession,
    workspace_id: UUID,
    settings: "Settings",
) -> list[dict]:
    """Fetch collaborators from GitHub repos with per-user email lookup.

    For each selected repo, fetches collaborators via the GitHub API.
    Deduplicates by login across repos. Attempts per-user email lookup
    via GET /users/{login}.

    Args:
        session: Async database session.
        workspace_id: Workspace to fetch roster for.
        settings: Application settings.

    Returns:
        List of dicts with platform_user_id, display_name, email.
    """
    from src.services.github_common import (
        GITHUB_API_BASE,
        check_rate_limit,
        create_github_client,
        github_headers,
        parse_link_next,
    )
    from src.services.github_oauth import get_installation_token
    from src.services.github_repos import get_cached_repos

    token = await get_installation_token(workspace_id, session, settings)
    repos = await get_cached_repos(workspace_id, session)

    seen_logins: set[str] = set()
    unique_logins: list[str] = []

    async with create_github_client() as client:
        # Step 1: Collect unique collaborator logins across all repos
        for repo in repos:
            full_name = repo.get("full_name", "")
            url: str | None = (
                f"{GITHUB_API_BASE}/repos/{full_name}/collaborators?per_page=100"
            )

            while url:
                response = await client.get(url, headers=github_headers(token))
                if response.status_code != 200:
                    logger.warning(
                        "Failed to fetch collaborators for %s: %d",
                        full_name,
                        response.status_code,
                    )
                    break

                await check_rate_limit(response)

                collaborators = response.json()
                for collab in collaborators:
                    login = collab.get("login", "")
                    if login and login not in seen_logins:
                        seen_logins.add(login)
                        unique_logins.append(login)

                url = parse_link_next(response.headers.get("link"))

        # Step 2: Per-user email lookup
        members: list[dict] = []
        for login in unique_logins:
            email = None
            display_name = login
            try:
                user_response = await client.get(
                    f"{GITHUB_API_BASE}/users/{login}",
                    headers=github_headers(token),
                )
                if user_response.status_code == 200:
                    await check_rate_limit(user_response)
                    user_data = user_response.json()
                    email = user_data.get("email")
                    display_name = user_data.get("name") or login
            except httpx.HTTPError:
                logger.debug("Failed to fetch user details for %s", login)

            members.append({
                "platform_user_id": login,
                "display_name": display_name,
                "email": email,
            })

    logger.info(
        "Fetched %d GitHub collaborators for workspace %s",
        len(members),
        workspace_id,
    )
    return members


# ============================================================
# Identity mapping upsert
# ============================================================


async def upsert_identity_mapping(
    session: AsyncSession,
    workspace_id: UUID,
    email: str | None,
    platform: str,
    platform_user_id: str,
    display_name: str | None,
) -> IdentityMapping:
    """Insert or update an identity mapping row.

    Uses ON CONFLICT (workspace_id, platform, platform_user_id) DO UPDATE
    to upsert email, display_name, clear deleted_at, and update updated_at.

    Args:
        session: Async database session.
        workspace_id: Workspace the mapping belongs to.
        email: User's email address (may be None).
        platform: Platform name ('linear', 'slack', 'github').
        platform_user_id: Platform-specific user identifier.
        display_name: Human-readable display name.

    Returns:
        The upserted IdentityMapping.
    """
    stmt = pg_insert(IdentityMapping).values(
        workspace_id=workspace_id,
        email=email,
        platform=platform,
        platform_user_id=platform_user_id,
        display_name=display_name,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="identity_mappings_workspace_platform_user_key",
        set_={
            "email": stmt.excluded.email,
            "display_name": stmt.excluded.display_name,
            "deleted_at": None,
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        },
    )
    stmt = stmt.returning(IdentityMapping.__table__.c.id)

    result = await session.execute(stmt)
    mapping_id = result.scalar_one()
    await session.flush()

    # Use session.get() which checks identity map first (no extra query if cached)
    mapping = await session.get(IdentityMapping, mapping_id)
    if mapping is None:
        raise RuntimeError(f"Failed to fetch upserted mapping {mapping_id}")
    return mapping


# ============================================================
# Roster seeding orchestrator
# ============================================================


async def seed_roster(
    session: AsyncSession,
    workspace_id: UUID,
    platform: str,
    members: list[dict],
) -> int:
    """Seed identity mappings from a platform roster and run resolution.

    For each member in the roster:
    1. Upserts an identity_mapping row
    2. After all members upserted, runs email-based resolution
    3. Runs fuzzy name matching for candidate links
    4. Backfills existing Person nodes

    Args:
        session: Async database session.
        workspace_id: Workspace to seed.
        platform: Platform name ('linear', 'slack', 'github').
        members: List of member dicts with platform_user_id, display_name, email.

    Returns:
        Number of members seeded.
    """
    count = 0
    for member in members:
        await upsert_identity_mapping(
            session=session,
            workspace_id=workspace_id,
            email=member.get("email"),
            platform=platform,
            platform_user_id=member["platform_user_id"],
            display_name=member.get("display_name"),
        )
        count += 1

    # Run email-based resolution
    resolved = await resolve_by_email(session, workspace_id)
    logger.info(
        "Email resolution created %d canonical persons for workspace %s",
        resolved,
        workspace_id,
    )

    # Run fuzzy name matching
    fuzzy_count = await find_fuzzy_candidates(session, workspace_id)
    logger.info(
        "Fuzzy matching found %d candidates for workspace %s",
        fuzzy_count,
        workspace_id,
    )

    # Backfill existing Person nodes
    backfilled = await backfill_identity_resolution(session, workspace_id)
    logger.info(
        "Backfilled %d person nodes for workspace %s",
        backfilled,
        workspace_id,
    )

    logger.info(
        "Seeded %d %s members for workspace %s",
        count,
        platform,
        workspace_id,
    )
    return count


# ============================================================
# Fuzzy name matching
# ============================================================


def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Compute similarity between two names using token sort ratio.

    Uses rapidfuzz.fuzz.token_sort_ratio with a cutoff of 80.
    Normalizes names to lowercase and strips whitespace before comparison.

    Args:
        name_a: First name string.
        name_b: Second name string.

    Returns:
        Score from 0.0-100.0, or 0.0 if below threshold 80.
    """
    a = name_a.strip().lower()
    b = name_b.strip().lower()
    score = fuzz.token_sort_ratio(a, b, score_cutoff=80)
    return score


def build_confidence_score(name_score: float) -> float:
    """Convert a name similarity score (80-100) to a confidence score (0.5-0.9).

    Never returns 1.0 for name-only matching to reflect inherent uncertainty.

    Args:
        name_score: Score from compute_name_similarity (80-100).

    Returns:
        Confidence score between 0.5 and 0.9.
    """
    # Normalize 80-100 range to 0.5-0.9
    normalized = (name_score - 80) / 20  # 0.0 to 1.0
    confidence = 0.5 + (normalized * 0.4)  # 0.5 to 0.9
    return min(confidence, 0.9)


def _fuzzy_compare_sync(canonical_nodes: list) -> list[tuple]:
    """CPU-bound pairwise comparison -- runs in thread pool."""
    candidates = []
    for i in range(len(canonical_nodes)):
        for j in range(i + 1, len(canonical_nodes)):
            node_a = canonical_nodes[i]
            node_b = canonical_nodes[j]
            cpid_a = node_a["canonical_person_id"]
            cpid_b = node_b["canonical_person_id"]
            if cpid_a and cpid_b and cpid_a == cpid_b:
                continue
            score = compute_name_similarity(node_a["name"], node_b["name"])
            if score >= 80:
                confidence = build_confidence_score(score)
                candidates.append((node_a["id"], node_b["id"], node_a["name"], node_b["name"], score, confidence))
    return candidates


async def find_fuzzy_candidates(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Find candidate same_as edges between canonical Person nodes with similar names.

    For each pair of canonical Person nodes in the workspace with different
    canonical_person_ids, compares display names. If similarity >= 80,
    creates a candidate same_as edge with confidence score.

    IMPORTANT: Never auto-merges. Only creates candidate edges.

    Args:
        session: Async database session.
        workspace_id: Workspace to process.

    Returns:
        Number of candidate edges created.
    """
    import asyncio

    from src.models.graph_node import GraphNode

    # Query all canonical Person nodes
    stmt = (
        select(GraphNode)
        .where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.entity_type == "Person",
            GraphNode.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    all_person_nodes = result.scalars().all()

    # Extract data for thread-safe comparison (no ORM objects cross-thread)
    canonical_nodes = [
        {
            "id": n.id,
            "name": n.name,
            "canonical_person_id": (n.properties or {}).get("canonical_person_id"),
        }
        for n in all_person_nodes
        if n.properties and n.properties.get("canonical") is True
    ]

    # Run CPU-bound comparison in thread pool
    candidates = await asyncio.to_thread(_fuzzy_compare_sync, canonical_nodes)

    candidate_count = 0
    for src_id, tgt_id, name_a, name_b, score, confidence in candidates:
        await upsert_edge(
            session=session,
            workspace_id=workspace_id,
            source_node_id=src_id,
            target_node_id=tgt_id,
            relationship_type="same_as",
            properties={
                "status": "candidate",
                "confidence": confidence,
                "match_type": "fuzzy_name",
            },
        )
        candidate_count += 1
        logger.info(
            "Fuzzy candidate: %s <-> %s (score=%.1f, confidence=%.2f)",
            name_a,
            name_b,
            score,
            confidence,
        )

    return candidate_count


# ============================================================
# Backfill: link pre-existing Person nodes to canonical nodes
# ============================================================


async def backfill_identity_resolution(
    session: AsyncSession,
    workspace_id: UUID,
) -> int:
    """Backfill existing Person nodes by linking them to canonical nodes.

    Finds Person nodes in graph_nodes that have no same_as edge to any
    canonical Person node. For each unlinked Person node, extracts platform
    and platform_user_id from its external_id, looks up the identity mapping,
    and creates a same_as edge if a canonical_person_id exists.

    Handles the race condition where Person nodes were created before
    roster seeding ran.

    Args:
        session: Async database session.
        workspace_id: Workspace to backfill.

    Returns:
        Number of newly linked Person nodes.
    """
    from src.models.graph_edge import GraphEdge
    from src.models.graph_node import GraphNode

    # Find all Person nodes
    person_stmt = (
        select(GraphNode)
        .where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.entity_type == "Person",
            GraphNode.deleted_at.is_(None),
        )
    )
    person_result = await session.execute(person_stmt)
    person_nodes = person_result.scalars().all()

    if not person_nodes:
        return 0

    # Bulk prefetch: all same_as edges from Person nodes in this workspace
    person_node_ids = [n.id for n in person_nodes]
    edge_stmt = (
        select(GraphEdge.source_node_id)
        .where(
            GraphEdge.workspace_id == workspace_id,
            GraphEdge.source_node_id.in_(person_node_ids),
            GraphEdge.relationship_type == "same_as",
            GraphEdge.deleted_at.is_(None),
        )
    )
    edge_result = await session.execute(edge_stmt)
    already_linked = {str(row[0]) for row in edge_result}

    # Bulk prefetch: all identity mappings for this workspace
    mapping_stmt = (
        select(IdentityMapping)
        .where(
            IdentityMapping.workspace_id == workspace_id,
            IdentityMapping.deleted_at.is_(None),
        )
    )
    mapping_result = await session.execute(mapping_stmt)
    all_mappings = mapping_result.scalars().all()

    # Build lookup: (platform, platform_user_id) -> mapping
    mapping_lookup: dict[tuple[str, str], IdentityMapping] = {}
    for m in all_mappings:
        mapping_lookup[(m.platform, m.platform_user_id)] = m

    linked_count = 0

    for node in person_nodes:
        # Skip canonical nodes
        if node.properties and node.properties.get("canonical") is True:
            continue

        # Skip already linked
        if str(node.id) in already_linked:
            continue

        # Parse external_id from properties
        props = node.properties or {}
        external_id = props.get("external_id", "")
        if not external_id or external_id.startswith("canonical:"):
            continue
        if ":" not in external_id:
            logger.debug(
                "Cannot parse external_id for Person node %s: %s",
                node.id,
                external_id,
            )
            continue

        platform, platform_user_id = external_id.split(":", 1)
        if not platform or not platform_user_id:
            continue

        # Lookup from prefetched mappings
        mapping = mapping_lookup.get((platform, platform_user_id))
        if mapping and mapping.canonical_person_id:
            await upsert_edge(
                session=session,
                workspace_id=workspace_id,
                source_node_id=node.id,
                target_node_id=mapping.canonical_person_id,
                relationship_type="same_as",
            )
            linked_count += 1
            logger.info(
                "Backfill: linked Person node %s to canonical %s",
                node.id,
                mapping.canonical_person_id,
            )

    return linked_count
