"""GraphEdge model mapping to public.graph_edges table."""

import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class GraphEdge(BaseModel, table=True):
    """Knowledge graph edge representing a relationship between two nodes.

    Deduplication: (workspace_id, source_node_id, target_node_id, relationship_type)
    uniqueness prevents duplicate edges for the same relationship.
    """

    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_node_id",
            "target_node_id",
            "relationship_type",
            name="graph_edges_workspace_source_target_type_key",
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    source_node_id: uuid.UUID = Field(foreign_key="graph_nodes.id", nullable=False)
    target_node_id: uuid.UUID = Field(foreign_key="graph_nodes.id", nullable=False)
    relationship_type: str = Field(nullable=False)
    properties: dict = Field(
        default_factory=dict,
        sa_column=Column("properties", JSONB, nullable=True, server_default=sa_text("'{}'")),
    )
