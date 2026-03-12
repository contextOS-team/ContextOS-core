"""Graph operations: fingerprint computation and upsert functions.

Provides deterministic fingerprinting for entity deduplication and
async upsert operations using PostgreSQL ON CONFLICT for both
graph nodes and edges.
"""

import hashlib
import logging
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.graph_edge import GraphEdge
from src.models.graph_node import GraphNode

logger = logging.getLogger(__name__)


def compute_fingerprint(entity_type: str, external_id: str) -> str:
    """Compute a deterministic SHA-256 fingerprint for an entity.

    Args:
        entity_type: The type of entity (e.g. 'Ticket', 'Person').
        external_id: The external identifier (e.g. 'ENG-123', 'slack:U12345').

    Returns:
        64-character hex digest uniquely identifying this entity.
    """
    return hashlib.sha256(f"{entity_type}:{external_id}".encode()).hexdigest()


async def upsert_node(
    session: AsyncSession,
    workspace_id: UUID,
    entity_type: str,
    external_id: str,
    name: str,
    source_type: str | None = None,
    source_id: UUID | None = None,
    properties: dict | None = None,
) -> UUID:
    """Insert or update a graph node using fingerprint deduplication.

    On conflict (same workspace + fingerprint), updates name, source_type,
    source_id, properties, and clears deleted_at (restores soft-deleted).

    Args:
        session: Async database session.
        workspace_id: Workspace the node belongs to.
        entity_type: Entity type (e.g. 'Ticket', 'Person').
        external_id: External identifier for fingerprint computation.
        name: Human-readable name for the node.
        source_type: Optional source type (e.g. 'linear_ticket').
        source_id: Optional source record UUID.
        properties: Optional JSONB properties dict.

    Returns:
        UUID of the inserted or updated node.
    """
    fingerprint = compute_fingerprint(entity_type, external_id)

    values = {
        "workspace_id": workspace_id,
        "entity_type": entity_type,
        "name": name,
        "fingerprint": fingerprint,
        "source_type": source_type,
        "source_id": source_id,
        "properties": properties or {},
    }

    stmt = pg_insert(GraphNode).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="graph_nodes_workspace_fingerprint_key",
        set_={
            "name": stmt.excluded.name,
            "source_type": stmt.excluded.source_type,
            "source_id": stmt.excluded.source_id,
            "properties": stmt.excluded.properties,
            "deleted_at": None,
        },
    )
    stmt = stmt.returning(GraphNode.__table__.c.id)

    result = await session.execute(stmt)
    node_id = result.scalar_one()
    logger.info(
        "Upserted graph node %s (%s: %s, fingerprint=%s...)",
        node_id, entity_type, name, fingerprint[:12],
    )
    return node_id


async def upsert_edge(
    session: AsyncSession,
    workspace_id: UUID,
    source_node_id: UUID,
    target_node_id: UUID,
    relationship_type: str,
    properties: dict | None = None,
) -> UUID:
    """Insert or update a graph edge using composite key deduplication.

    On conflict (same workspace + source + target + type), merges
    properties and clears deleted_at (restores soft-deleted).

    Args:
        session: Async database session.
        workspace_id: Workspace the edge belongs to.
        source_node_id: Source node UUID.
        target_node_id: Target node UUID.
        relationship_type: Relationship type (e.g. 'mentions', 'authored_by').
        properties: Optional JSONB properties dict.

    Returns:
        UUID of the inserted or updated edge.
    """
    values = {
        "workspace_id": workspace_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "relationship_type": relationship_type,
        "properties": properties or {},
    }

    stmt = pg_insert(GraphEdge).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="graph_edges_workspace_source_target_type_key",
        set_={
            "properties": stmt.excluded.properties,
            "deleted_at": None,
        },
    )
    stmt = stmt.returning(GraphEdge.__table__.c.id)

    result = await session.execute(stmt)
    edge_id = result.scalar_one()
    logger.info(
        "Upserted graph edge %s (%s: %s -> %s)",
        edge_id, relationship_type, source_node_id, target_node_id,
    )
    return edge_id
