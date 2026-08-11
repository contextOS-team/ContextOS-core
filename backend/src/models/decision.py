"""Decision State v1 models.

`decisions` is the source of truth for organizational decisions; graph_nodes
holds a mirror node per decision for the linking layer. All writes go through
src.services.decision_writer — no other code may touch these tables.

decision_versions / decision_evidence / decision_edges / decision_feedback are
append-only by service discipline (INSERT only, never UPDATE).
"""

import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from src.models.base import BaseModel


class Decision(BaseModel, table=True):
    """A first-class temporal decision (status + validity window)."""

    __tablename__ = "decisions"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    statement: str = Field(nullable=False)
    rationale: str | None = Field(default=None)
    status: str = Field(default="active", nullable=False)
    valid_from: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    valid_until: datetime | None = Field(default=None)
    owner_node_id: uuid.UUID | None = Field(default=None, foreign_key="graph_nodes.id")
    confidence: float | None = Field(default=None)
    consequentiality_score: float | None = Field(default=None)
    producer: str = Field(nullable=False)
    created_from_candidate_id: uuid.UUID | None = Field(
        default=None, foreign_key="missed_decision_candidates.id"
    )
    graph_node_id: uuid.UUID | None = Field(default=None, foreign_key="graph_nodes.id")


class DecisionVersion(SQLModel, table=True):
    """Append-only snapshot of a decision row at each change."""

    __tablename__ = "decision_versions"
    __table_args__ = (
        UniqueConstraint(
            "decision_id", "version", name="decision_versions_decision_version_key"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    decision_id: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    version: int = Field(nullable=False)
    snapshot: dict = Field(
        default_factory=dict,
        sa_column=Column("snapshot", JSONB, nullable=False),
    )
    change_type: str = Field(nullable=False)
    change_reason: str | None = Field(default=None)
    actor: str = Field(nullable=False)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )


class DecisionEvidence(SQLModel, table=True):
    """Evidence link with the quote frozen at capture time."""

    __tablename__ = "decision_evidence"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    decision_id: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    source_type: str = Field(nullable=False)
    source_id: uuid.UUID = Field(nullable=False)
    quote: str = Field(nullable=False)
    source_link: str | None = Field(default=None)
    captured_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    added_by: str = Field(nullable=False)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )


class DecisionEdge(SQLModel, table=True):
    """Decision-to-decision relationship (supersedes/contradicts/refines)."""

    __tablename__ = "decision_edges"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "from_decision",
            "to_decision",
            "edge_type",
            name="decision_edges_unique_key",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    from_decision: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    to_decision: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    edge_type: str = Field(nullable=False)
    rationale: str | None = Field(default=None)
    actor: str = Field(nullable=False)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )


class DecisionFeedback(SQLModel, table=True):
    """Append-only human verdict with enum reason code."""

    __tablename__ = "decision_feedback"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    decision_id: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    user_id: uuid.UUID = Field(foreign_key="profiles.id", nullable=False)
    verdict: str = Field(nullable=False)
    note: str | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )


DECISION_STATUSES = {"active", "superseded", "tentative", "reversed", "unknown"}
DECISION_PRODUCERS = {"missed_decision", "llm_extractor", "digest", "manual", "import"}
DECISION_EDGE_TYPES = {"supersedes", "contradicts", "refines", "relates_to"}
DECISION_FEEDBACK_VERDICTS = {
    "correct",
    "wrong",
    "superseded",
    "minor",
    "missing_evidence",
    "duplicate",
    "not_important",
}
VERSION_CHANGE_TYPES = {
    "created",
    "status_changed",
    "evidence_added",
    "statement_edited",
    "superseded",
    "imported",
}
