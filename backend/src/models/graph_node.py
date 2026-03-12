"""GraphNode model mapping to public.graph_nodes table."""

import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class GraphNode(BaseModel, table=True):
    """Knowledge graph node representing an entity (Person, Ticket, etc.).

    Fingerprint-based deduplication: hash(entity_type + external_id) ensures
    the same real-world entity maps to exactly one row per workspace.
    """

    __tablename__ = "graph_nodes"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "fingerprint", name="graph_nodes_workspace_fingerprint_key"
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    entity_type: str = Field(nullable=False)
    name: str = Field(nullable=False)
    fingerprint: str = Field(nullable=False)
    source_type: str | None = Field(default=None)
    source_id: uuid.UUID | None = Field(default=None)
    properties: dict = Field(
        default_factory=dict,
        sa_column=Column("properties", JSONB, nullable=True, server_default=sa_text("'{}'")),
    )
