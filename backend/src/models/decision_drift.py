"""Decision Drift models: expected consequences, observations, drifts."""

import uuid
from datetime import datetime

from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from src.models.base import BaseModel


class ExpectedConsequence(BaseModel, table=True):
    """What should have changed because of a decision (impact inference)."""

    __tablename__ = "expected_consequences"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    decision_id: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    target_type: str = Field(nullable=False)
    target_query: str = Field(nullable=False)
    expected_state: str = Field(nullable=False)
    rationale: str | None = Field(default=None)
    importance: str = Field(default="medium", nullable=False)
    confidence: float | None = Field(default=None)
    status: str = Field(default="pending", nullable=False)


class ArtifactObservation(SQLModel, table=True):
    """A checker's snapshot of what the artifacts actually show."""

    __tablename__ = "artifact_observations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    expected_consequence_id: uuid.UUID = Field(
        foreign_key="expected_consequences.id", nullable=False
    )
    checker: str = Field(nullable=False)
    observed_state: str = Field(nullable=False)
    consistent: bool | None = Field(default=None)
    evidence: list = Field(
        default_factory=list,
        sa_column=Column(
            "evidence", JSONB, nullable=False, server_default=sa_text("'[]'")
        ),
    )
    checked_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )


class Drift(BaseModel, table=True):
    """A verified decision/execution inconsistency with lifecycle + outcome."""

    __tablename__ = "drifts"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    decision_id: uuid.UUID = Field(foreign_key="decisions.id", nullable=False)
    expected_consequence_id: uuid.UUID | None = Field(
        default=None, foreign_key="expected_consequences.id"
    )
    summary: str = Field(nullable=False)
    severity: str = Field(default="medium", nullable=False)
    verifier_verdict: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "verifier_verdict", JSONB, nullable=False, server_default=sa_text("'{}'")
        ),
    )
    detected_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
    confirmed_at: datetime | None = Field(default=None)
    owner_user_id: uuid.UUID | None = Field(default=None, foreign_key="profiles.id")
    owner_assigned_at: datetime | None = Field(default=None)
    resolved_at: datetime | None = Field(default=None)
    verified_at: datetime | None = Field(default=None)
    resolution_type: str | None = Field(default=None)
    feedback_verdict: str | None = Field(default=None)
    suggestion_id: uuid.UUID | None = Field(default=None, foreign_key="suggestions.id")


CONSEQUENCE_TARGET_TYPES = {"linear", "jira", "github", "docs", "release", "other"}
DRIFT_RESOLUTION_TYPES = {
    "jira_updated",
    "linear_updated",
    "doc_updated",
    "implementation_changed",
    "work_cancelled",
    "timeline_changed",
    "intentional_exception",
    "other",
}
DRIFT_FEEDBACK_VERDICTS = {
    "confirmed",
    "false_positive",
    "intentional_exception",
    "decision_superseded",
    "wrong_artifact",
    "not_important",
}
