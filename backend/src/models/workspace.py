"""Workspace model mapping to public.workspaces table."""

from src.models.base import BaseModel
from sqlmodel import Field


class Workspace(BaseModel, table=True):
    """Workspace -- multi-tenant root entity."""

    __tablename__ = "workspaces"

    name: str = Field(nullable=False)
    slug: str = Field(nullable=False, unique=True)
