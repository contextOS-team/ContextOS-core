"""Shared Graph RAG retrieval contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalTarget(StrEnum):
    """Supported retrieval target families."""

    DECISION_RECEIPTS = "decision_receipts"
    SOURCE_EVIDENCE = "source_evidence"
    GRAPH_NEIGHBORHOOD = "graph_neighborhood"
    RELATED_WORK = "related_work"


class FreshnessState(StrEnum):
    """Freshness classification used by ranking and explanation payloads."""

    FRESH = "fresh"
    STALE = "stale"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class VerificationState(StrEnum):
    """Evidence verification classification."""

    CONFIRMED_DECISION = "confirmed_decision"
    SOURCE_BACKED_CANDIDATE = "source_backed_candidate"
    SOURCE_EVIDENCE = "source_evidence"
    GENERATED_CONTEXT = "generated_context"
    UNKNOWN = "unknown"


class GraphPathStep(BaseModel):
    """One bounded graph-hop explanation."""

    node_id: str
    entity_type: str
    title: str
    relationship: str | None = None


class RetrievalFeatures(BaseModel):
    """Inspectable features attached to a retrieval candidate."""

    workspace_match: bool = True
    freshness_state: FreshnessState = FreshnessState.UNKNOWN
    verification_state: VerificationState = VerificationState.UNKNOWN
    source_timestamp: datetime | None = None
    freshness_age_days: float | None = None
    source_originality: str | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    graph_depth: int | None = None
    graph_path: list[GraphPathStep] = Field(default_factory=list)


class RetrievalTraceItem(BaseModel):
    """Selected or dropped retrieval evidence with provenance."""

    source_type: str
    source_id: str
    title: str
    snippet: str | None = None
    source_link: str | None = None
    targets: list[RetrievalTarget]
    signals: list[str]
    features: RetrievalFeatures = Field(default_factory=RetrievalFeatures)
    selected: bool = True
    why_selected: str | None = None
    suppress_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_trace_contract(self) -> "RetrievalTraceItem":
        if not self.targets:
            raise ValueError("retrieval trace requires at least one target")
        if not self.signals:
            raise ValueError("retrieval trace requires at least one signal")
        if self.selected and self.suppress_reason:
            raise ValueError("selected retrieval trace cannot include suppress_reason")
        if not self.selected and not self.suppress_reason:
            raise ValueError("dropped retrieval trace requires suppress_reason")
        return self


class GraphRagResult(BaseModel):
    """A deterministic retrieval result used by evals and context explanations."""

    query_id: str
    trace: list[RetrievalTraceItem]
    answer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def selected_items(self) -> list[RetrievalTraceItem]:
        return [item for item in self.trace if item.selected]

    @property
    def dropped_items(self) -> list[RetrievalTraceItem]:
        return [item for item in self.trace if not item.selected]
