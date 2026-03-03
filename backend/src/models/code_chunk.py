"""CodeChunk model mapping to public.code_chunks table.

Stores parsed code symbols (functions, classes, methods, types, interfaces)
extracted by tree-sitter from repos selected for GitHub PR monitoring.
Content-hash deduplication prevents redundant storage on re-index.
"""

import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from src.models.base import BaseModel


class CodeChunk(BaseModel, table=True):
    """Parsed code symbol record mapping to public.code_chunks table.

    Each row represents a single extracted symbol (function, class, method,
    type, interface, decorator, or module) from a source file in a monitored
    GitHub repository. Tree-sitter extracts the symbol boundaries, and the
    content_hash enables content-based deduplication on re-index.

    Inherits from BaseModel: id (UUID PK), created_at, updated_at, deleted_at.
    """

    __tablename__ = "code_chunks"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "repo_full_name",
            "file_path",
            "symbol_name",
            "symbol_type",
            name="idx_code_chunks_dedup",
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    repo_full_name: str = Field(nullable=False)
    file_path: str = Field(nullable=False)
    symbol_name: str = Field(nullable=False)
    symbol_type: str = Field(nullable=False)
    language: str = Field(nullable=False)
    content: str = Field(nullable=False)
    content_hash: str = Field(nullable=False)
    start_line: int = Field(nullable=False)
    end_line: int = Field(nullable=False)
    metadata_: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False, server_default=sa_text("'{}'")),
    )
