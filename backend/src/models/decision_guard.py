"""Decision Guard models: exceptions and advisory verdicts."""

import uuid
from datetime import datetime

from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.types import String
from sqlmodel import Column, Field, SQLModel

from src.models.base import BaseModel

GUARD_STATUSES = {"no_known_conflict", "potential_conflict", "requires_review"}


class DecisionException(BaseModel, table=True):
    """A sanctioned deviation from a decision (so it isn't flagged as drift)."""

    __tablename__ = "decision_exceptions"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    decision_id: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    scope: str = Field(nullable=False)
    reason: str | None = Field(default=None)
    approved_by: uuid.UUID | None = Field(default=None, foreign_key="profiles.id")
    valid_from: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    expires_at: datetime | None = Field(default=None)
    evidence: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "evidence", JSONB, nullable=False, server_default=sa_text("'{}'")
        ),
    )


class GuardVerdict(SQLModel, table=True):
    """A persisted advisory check_action verdict (Guard eval-set input)."""

    __tablename__ = "guard_verdicts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    proposed_action: str = Field(nullable=False)
    scope: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "scope", JSONB, nullable=False, server_default=sa_text("'{}'")
        ),
    )
    status: str = Field(nullable=False)
    rationale: str | None = Field(default=None)
    confidence: float | None = Field(default=None)
    considered_decision_ids: list[uuid.UUID] = Field(
        default_factory=list,
        sa_column=Column(
            "considered_decision_ids",
            ARRAY(String),
            nullable=False,
            server_default=sa_text("ARRAY[]::uuid[]"),
        ),
    )
    actor: str = Field(nullable=False)
    latency_ms: int | None = Field(default=None)
    feedback_correct: bool | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
