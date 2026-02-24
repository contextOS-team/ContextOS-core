"""Base SQLModel class with common fields."""

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    """Mixin providing created_at, updated_at, and deleted_at fields.

    Timestamps are managed by the database (default now(), moddatetime trigger).
    Python-side defaults are not set to avoid naive datetime issues.
    """

    created_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
    updated_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
    deleted_at: datetime | None = Field(default=None)


class BaseModel(TimestampMixin):
    """Base model with UUID primary key and timestamp fields."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
