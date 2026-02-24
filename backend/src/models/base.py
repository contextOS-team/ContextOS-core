"""Base SQLModel class with common fields."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    """Mixin providing created_at, updated_at, and deleted_at fields."""

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    deleted_at: datetime | None = Field(default=None)


class BaseModel(TimestampMixin):
    """Base model with UUID primary key and timestamp fields."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
