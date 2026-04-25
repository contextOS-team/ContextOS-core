"""GraphCommunity model mapping to public.graph_communities table."""

import uuid
from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlmodel import Field

from src.models.base import BaseModel


class GraphCommunity(BaseModel, table=True):
    """A Louvain community snapshot: per-workspace, per-rebuild cluster metadata.

    Community IDs are not stable across rebuilds — each nightly run wipes the
    previous snapshot for the workspace and reassigns fresh integer IDs.
    """

    __tablename__ = "graph_communities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "community_id", name="graph_communities_workspace_id_key"
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    community_id: int = Field(nullable=False)
    label: str | None = Field(default=None)
    summary: str | None = Field(default=None)
    member_count: int = Field(nullable=False)
    person_count: int = Field(nullable=False)
    ticket_count: int = Field(nullable=False)
    top_member_names: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "top_member_names",
            ARRAY(TEXT),
            nullable=True,
            server_default=sa_text("'{}'"),
        ),
    )
    computed_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
