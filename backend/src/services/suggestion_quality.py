"""Shared quality contracts for source-grounded suggestions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator


class SuggestionFamily(StrEnum):
    """Supported suggestion families."""

    MISSING_SOURCE = "missing_source_coverage"
    MISSED_DECISION = "missed_decision"
    ACTION_PROMPT = "action_prompt"


PROMPT_INJECTION_PHRASES = (
    "ignore previous instructions",
    "ignore above",
    "disregard previous instructions",
    "system prompt",
    "developer message",
    "you are now",
    "run this command",
)

FAMILY_POLICIES: dict[SuggestionFamily, str] = {
    SuggestionFamily.MISSING_SOURCE: "missing_source_requires_concrete_decision",
    SuggestionFamily.MISSED_DECISION: "missed_decision_requires_exact_quote",
    SuggestionFamily.ACTION_PROMPT: "action_prompt_requires_source_backing_no_write",
}

NO_WRITE_BOUNDARY = "phase_46_metadata_only"


class SuggestionGroundingTrace(BaseModel):
    """Source evidence used to show or suppress a suggestion."""

    source_type: str | None = None
    source_id: str | None = None
    source_link: str | None = None
    source_quote: str | None = None
    retrieval_signals: list[str] = Field(default_factory=list)
    action_hints: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_source_ref(self) -> bool:
        return bool(self.source_type and self.source_id)

    @property
    def has_valid_source_link(self) -> bool:
        if not self.source_link:
            return False
        parsed = urlparse(self.source_link)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return True
        return parsed.path == "/dashboard/source-reference"

    @property
    def has_prompt_injection_text(self) -> bool:
        text = " ".join(
            value
            for value in [
                self.source_quote,
                str(self.metadata.get("source_text") or ""),
            ]
            if value
        ).lower()
        return any(phrase in text for phrase in PROMPT_INJECTION_PHRASES)

    @property
    def has_source_quote(self) -> bool:
        return bool((self.source_quote or "").strip())

    @property
    def has_source_backed_action_hints(self) -> bool:
        if not self.action_hints:
            return False
        return (
            self.has_source_ref
            and self.has_valid_source_link
            and self.has_source_quote
        )

    def grounding_state(
        self,
        *,
        should_surface: bool,
        suppress_reason: str | None = None,
    ) -> str:
        """Return a compact state for UI explanations and evals."""
        if not should_surface:
            return "suppressed" if suppress_reason else "not_grounded"
        if self.has_source_ref:
            return "source_backed"
        return "not_grounded"

    def action_hint_grounding(self) -> list[dict[str, Any]]:
        """Attach source and no-write metadata to generated action hints."""
        grounded = self.has_source_backed_action_hints
        return [
            {
                **hint,
                "grounding_state": "source_backed" if grounded else "not_grounded",
                "source_type": self.source_type,
                "source_id": self.source_id,
                "source_quote": self.source_quote,
                "source_link": self.source_link,
                "no_write_boundary": NO_WRITE_BOUNDARY,
            }
            for hint in self.action_hints
        ]


class SuggestionFamilyAssessment(BaseModel):
    """Structured quality verdict shared by suggestion families."""

    should_surface: bool
    reason: str
    confidence: float
    family: SuggestionFamily
    policy: str
    required_evidence: list[str]
    validators: list[str]
    grounding: SuggestionGroundingTrace = Field(
        default_factory=SuggestionGroundingTrace
    )
    suppress_reason: str | None = None

    @model_validator(mode="after")
    def _validate_reason_shape(self) -> SuggestionFamilyAssessment:
        if self.family not in FAMILY_POLICIES:
            raise ValueError("unknown suggestion family")
        if self.policy != FAMILY_POLICIES[self.family]:
            raise ValueError("policy does not match suggestion family")
        if self.should_surface and self.suppress_reason:
            raise ValueError("surfaced suggestion cannot include suppress_reason")
        if not self.should_surface and not self.suppress_reason:
            raise ValueError("suppressed suggestion requires suppress_reason")
        if self.grounding.has_prompt_injection_text and self.should_surface:
            raise ValueError("prompt-injection-like source text cannot surface")
        return self

    def explanation(self) -> dict[str, Any]:
        """JSONB-safe explanation payload."""
        payload: dict[str, Any] = {
            "selected_because": self.reason if self.should_surface else None,
            "suppressed_because": self.suppress_reason,
            "grounding_state": self.grounding.grounding_state(
                should_surface=self.should_surface,
                suppress_reason=self.suppress_reason,
            ),
            "grounding_family": self.family.value,
            "policy": self.policy,
            "required_evidence": self.required_evidence,
            "confidence": self.confidence,
            "retrieval_signals": self.grounding.retrieval_signals,
        }
        if self.grounding.source_type and self.grounding.source_id:
            payload["source_ref"] = {
                "type": self.grounding.source_type,
                "id": self.grounding.source_id,
                "link": self.grounding.source_link,
            }
        if self.grounding.action_hints:
            payload["action_hint_grounding"] = self.grounding.action_hint_grounding()
            payload["no_write_boundary"] = NO_WRITE_BOUNDARY
        return {key: value for key, value in payload.items() if value is not None}

    def quality_gate(self) -> dict[str, Any]:
        """JSONB-safe validator payload."""
        return {
            "family": self.family.value,
            "policy": self.policy,
            "required_evidence": self.required_evidence,
            "validators": self.validators,
            "passed": self.should_surface,
            "confidence": self.confidence,
            "grounding_state": self.grounding.grounding_state(
                should_surface=self.should_surface,
                suppress_reason=self.suppress_reason,
            ),
            "retrieval_signals": self.grounding.retrieval_signals,
            "suppress_reason": self.suppress_reason,
        }


def assess_suggestion_family(
    *,
    family: SuggestionFamily,
    grounding: SuggestionGroundingTrace,
    reason: str,
    confidence: float,
    required_evidence: list[str] | None = None,
) -> SuggestionFamilyAssessment:
    """Build a deterministic family-level assessment."""
    validators: list[str] = []
    suppress_reason: str | None = None
    required = required_evidence or []

    if grounding.has_prompt_injection_text:
        validators.append("prompt_injection_rejected")
        suppress_reason = "prompt_injection_source_text"

    if "source_ref" in required:
        validators.append("exact_source_ref")
        if not grounding.has_source_ref:
            suppress_reason = suppress_reason or "missing_source_ref"

    if "source_link" in required:
        validators.append("valid_source_link")
        if not grounding.has_valid_source_link:
            suppress_reason = suppress_reason or "missing_source_link"

    if "source_quote" in required:
        validators.append("required_quote")
        if not (grounding.source_quote or "").strip():
            suppress_reason = suppress_reason or "missing_source_quote"

    if "action_hint_grounding" in required:
        validators.append("action_hint_grounding")
        if not grounding.action_hints:
            suppress_reason = suppress_reason or "missing_action_hint"
        elif not grounding.has_source_backed_action_hints:
            suppress_reason = suppress_reason or "ungrounded_action_hint"

    validators.append("family_policy")
    should_surface = suppress_reason is None
    return SuggestionFamilyAssessment(
        should_surface=should_surface,
        reason=reason,
        confidence=confidence,
        family=family,
        policy=FAMILY_POLICIES[family],
        required_evidence=required,
        validators=validators,
        grounding=grounding,
        suppress_reason=suppress_reason,
    )
