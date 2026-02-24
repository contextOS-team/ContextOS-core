"""Meeting transcript and segment models mapping to DB tables.

MeetingTranscript maps to public.meeting_transcripts and stores full
transcript records with metadata (source, title, participants, duration).

MeetingSegment maps to public.meeting_segments and stores individual
speaker turns with timestamps, linked to a parent transcript.

Both tables lack updated_at columns, so these models do NOT inherit
from BaseModel (which includes TimestampMixin with updated_at).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel


class MeetingTranscript(SQLModel, table=True):
    """Meeting transcript record mapping to public.meeting_transcripts.

    Stores full transcripts from meeting recording services (Fathom, Zoom, etc.)
    with metadata including participants, duration, and source-specific raw data.

    The fathom_id for deduplication is stored in raw_data["fathom_id"]
    since the DB schema does not have a dedicated column.
    """

    __tablename__ = "meeting_transcripts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    source: str = Field(nullable=False)  # "fathom", "google_meet", "zoom", etc.
    title: str | None = Field(default=None)
    transcript: str = Field(nullable=False)
    summary: str | None = Field(default=None)
    participants: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String), nullable=True),
    )
    meeting_date: datetime | None = Field(default=None)
    duration_minutes: int | None = Field(default=None)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=sa_text("'{}'")),
    )
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )


class MeetingSegment(SQLModel, table=True):
    """Speaker turn segment within a meeting transcript.

    Maps to public.meeting_segments. Each segment represents a single
    speaker turn with start/end timestamps and the spoken text.

    Linked to a parent MeetingTranscript via transcript_id FK.
    """

    __tablename__ = "meeting_segments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    transcript_id: uuid.UUID = Field(
        foreign_key="meeting_transcripts.id", nullable=False
    )
    speaker_name: str | None = Field(default=None)
    text: str = Field(nullable=False)
    start_time_seconds: int | None = Field(default=None)
    end_time_seconds: int | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": sa_text("now()")},
    )
