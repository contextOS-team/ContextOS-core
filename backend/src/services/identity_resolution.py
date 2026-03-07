"""Identity resolution: email-based deterministic matching for person unification.

Provides:
  - create_canonical_person: Create a canonical Person graph node
  - lookup_mapping: Find an identity mapping by platform + user ID
  - resolve_by_email: Group mappings by email and create canonical nodes
  - resolve_identity_inline: Hook for real-time resolution during extraction

Canonical Person nodes use fingerprint hash('Person:canonical:{UUID}') and
are linked to platform-specific Person nodes via same_as edges.
"""

import logging
import uuid
from uuid import UUID

from sqlalchemy import select
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
    # Step 1: Get distinct emails with non-deleted mappings
    email_stmt = (
        select(IdentityMapping.email)
        .where(
            IdentityMapping.workspace_id == workspace_id,
            IdentityMapping.email.isnot(None),
            IdentityMapping.deleted_at.is_(None),
        )
        .group_by(IdentityMapping.email)
    )
    email_result = await session.execute(email_stmt)
    email_rows = email_result.all()

    created_count = 0

    for (email,) in email_rows:
        # Step 2: Fetch all mappings for this email
        mappings_stmt = (
            select(IdentityMapping)
            .where(
                IdentityMapping.workspace_id == workspace_id,
                IdentityMapping.email == email,
                IdentityMapping.deleted_at.is_(None),
            )
        )
        mappings_result = await session.execute(mappings_stmt)
        mappings = mappings_result.scalars().all()

        if not mappings:
            continue

        # Step 3: Check if any mapping already has a canonical_person_id
        existing_canonical = None
        for m in mappings:
            if m.canonical_person_id is not None:
                existing_canonical = m.canonical_person_id
                break

        if existing_canonical is None:
            # No canonical yet -- create one
            canonical_id = uuid.uuid4()
            # Use first mapping's display_name as the canonical name
            display_name = mappings[0].display_name or email
            canonical_node_id = await create_canonical_person(
                session, workspace_id, canonical_id, display_name
            )

            # Assign canonical_person_id to all mappings in the group
            for m in mappings:
                m.canonical_person_id = canonical_node_id

            created_count += 1

            # Create same_as edges from platform Person nodes to canonical
            for m in mappings:
                await _create_same_as_edge(
                    session, workspace_id, m, canonical_node_id
                )
        else:
            # Already resolved -- ensure same_as edges exist for any new mappings
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
