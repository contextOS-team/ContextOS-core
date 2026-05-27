import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class MissedDecisionScanState(BaseModel, table=True):
    """Per-workspace/source checkpoint for successful missed-decision scans."""

    __tablename__ = "missed_decision_scan_state"
    __table_args__ = (
        Index(
            "uq_missed_decision_scan_state_workspace_source_global",
            "workspace_id",
            "source_type",
            unique=True,
            postgresql_where=sa_text(
                "source_resource_id IS NULL AND deleted_at IS NULL"
            ),
        ),
        Index(
            "uq_missed_decision_scan_state_workspace_source_resource",
            "workspace_id",
            "source_type",
            "source_resource_id",
            unique=True,
            postgresql_where=sa_text(
                "source_resource_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    source_type: str = Field(nullable=False)
    source_resource_id: str | None = Field(default=None)
    last_missed_decision_scan_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class MissedDecisionScanRun(BaseModel, table=True):
    """A queued or completed missed-decision scan attempt."""

    __tablename__ = "missed_decision_scan_runs"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    source_type: str = Field(nullable=False)
    source_resource_id: str | None = Field(default=None)
    status: str = Field(default="queued", nullable=False)
    source_window_start: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    source_window_end: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    sources_scanned: int = Field(default=0, nullable=False)
    candidates_created: int = Field(default=0, nullable=False)
    attempts: int = Field(default=0, nullable=False)
    error_message: str | None = Field(default=None)
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class MissedDecisionCandidate(BaseModel, table=True):
    """Source-backed missed-decision candidate before or after review."""

    __tablename__ = "missed_decision_candidates"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    scan_run_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="missed_decision_scan_runs.id",
    )
    suggestion_id: uuid.UUID | None = Field(default=None, foreign_key="suggestions.id")
    source_type: str = Field(nullable=False)
    source_id: uuid.UUID = Field(nullable=False)
    source_resource_id: str | None = Field(default=None)
    source_quote: str = Field(nullable=False)
    inferred_decision: str = Field(nullable=False)
    inferred_rationale: str = Field(nullable=False)
    source_link: str = Field(nullable=False)
    confidence: str = Field(nullable=False)
    lifecycle_status: str = Field(default="detected", nullable=False)
    quote_fingerprint: str = Field(nullable=False)
    decision_fingerprint: str = Field(nullable=False)
    match_status: str | None = Field(default=None)
    matched_entity_type: str | None = Field(default=None)
    matched_entity_id: uuid.UUID | None = Field(default=None)
    suppression_reason: str | None = Field(default=None)
    evidence: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "evidence",
            JSONB,
            nullable=False,
            server_default=sa_text("'{}'"),
        ),
    )
    people: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "people",
            JSONB,
            nullable=False,
            server_default=sa_text("'[]'"),
        ),
    )
    affected_systems: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "affected_systems",
            JSONB,
            nullable=False,
            server_default=sa_text("'[]'"),
        ),
    )
    action_hints: list[dict] = Field(
        default_factory=list,
        sa_column=Column(
            "action_hints",
            JSONB,
            nullable=False,
            server_default=sa_text("'[]'"),
        ),
    )
    detected_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=sa_text("now()"),
        ),
    )
    surfaced_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    resolved_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
