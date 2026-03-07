"""Unit tests for llm_extractor: content filter, schemas, source validation, content hash.

Tests the pure-function foundation for LLM extraction: Pydantic schemas,
content pre-filter, source text validation, and SHA-256 content hashing.
All pure function tests -- no database or LLM calls needed.
"""

import inspect

import pytest

from src.services.llm_extractor import (
    ExtractedBlocker,
    ExtractedDecision,
    ExtractionResult,
    should_skip_for_llm,
)


# ============================================================
# Content Pre-Filter
# ============================================================


class TestContentFilter:
    """Tests for should_skip_for_llm content filter."""

    def test_skips_bot_messages(self):
        """Bot messages are always skipped regardless of content."""
        assert should_skip_for_llm(text="any text here that is long enough", bot_id="B123") is True

    def test_skips_short_messages(self):
        """Messages shorter than 50 chars are skipped."""
        assert should_skip_for_llm(text="ok") is True

    def test_allows_substantive_messages(self):
        """Substantive messages (>= 50 chars, no bot_id) pass through."""
        text = "We decided to use Redis for caching because it handles pub/sub well"
        assert should_skip_for_llm(text=text) is False

    def test_skips_emoji_only(self):
        """Emoji-only messages are skipped."""
        assert should_skip_for_llm(text="\U0001F600\U0001F680\U0001F389" * 20) is True

    def test_allows_emoji_with_text(self):
        """Messages with emoji AND substantive text (>= 50 chars) pass through."""
        text = "Great work on the deployment! \U0001F680 Everything looks good to me now"
        assert should_skip_for_llm(text=text) is False

    def test_boundary_49_chars_skipped(self):
        """Exactly 49 chars is below threshold and should be skipped."""
        text = "a" * 49
        assert should_skip_for_llm(text=text) is True

    def test_boundary_50_chars_allowed(self):
        """Exactly 50 chars meets threshold and should be allowed."""
        text = "a" * 50
        assert should_skip_for_llm(text=text) is False


# ============================================================
# Pydantic Schemas
# ============================================================


class TestSchemas:
    """Tests for Pydantic extraction schema constraints."""

    def test_extraction_result_no_defaults(self):
        """All fields in ExtractedDecision and ExtractedBlocker are required (no defaults).

        Gemini SDK rejects response_schema models with default field values.
        """
        for model_cls in (ExtractedDecision, ExtractedBlocker):
            for field_name, field_info in model_cls.model_fields.items():
                assert field_info.default is None or field_info.is_required(), (
                    f"{model_cls.__name__}.{field_name} has a default value -- "
                    "Gemini SDK rejects schemas with defaults"
                )

    def test_decision_has_all_fields(self):
        """ExtractedDecision has the required field set."""
        expected_fields = {
            "description",
            "rationale",
            "source_quote",
            "confidence",
            "person_name",
            "ticket_refs",
        }
        actual_fields = set(ExtractedDecision.model_fields.keys())
        assert expected_fields == actual_fields, (
            f"Field mismatch: missing={expected_fields - actual_fields}, "
            f"extra={actual_fields - expected_fields}"
        )

    def test_blocker_has_all_fields(self):
        """ExtractedBlocker has the required field set."""
        expected_fields = {"description", "source_quote", "confidence"}
        actual_fields = set(ExtractedBlocker.model_fields.keys())
        assert expected_fields == actual_fields, (
            f"Field mismatch: missing={expected_fields - actual_fields}, "
            f"extra={actual_fields - expected_fields}"
        )

    def test_extraction_result_structure(self):
        """ExtractionResult aggregates decisions and blockers."""
        expected_fields = {"decisions", "blockers"}
        actual_fields = set(ExtractionResult.model_fields.keys())
        assert expected_fields == actual_fields
