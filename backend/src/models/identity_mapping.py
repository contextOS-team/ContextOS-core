"""IdentityMapping model for cross-platform person identity unification.

Maps platform-specific user identities (Slack UID, GitHub username, etc.)
to canonical Person graph nodes via email-based deterministic matching.
One row per (workspace, platform, platform_user_id).
"""

import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from src.models.base import BaseModel


class IdentityMapping(BaseModel, table=True):
    """A platform-specific user identity linked to a canonical Person node.

    Attributes:
        workspace_id: Workspace this mapping belongs to.
        email: User's email address (nullable for GitHub users without public email).
        platform: Source platform ('linear', 'slack', 'github', 'fathom').
        platform_user_id: Platform-specific user identifier.
        display_name: Human-readable display name from the platform.
        canonical_person_id: FK to graph_nodes for the canonical Person node.
    """

    __tablename__ = "identity_mappings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "platform",
            "platform_user_id",
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
