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
    compute_content_hash,
    should_skip_for_llm,
    validate_extraction,
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


# ============================================================
# Source Text Validation (Anti-Hallucination)
# ============================================================


def _make_decision(**overrides) -> ExtractedDecision:
    """Helper to create an ExtractedDecision with sensible defaults for tests."""
    defaults = {
        "description": "Use Redis for caching",
        "rationale": "It handles pub/sub well",
        "source_quote": "we decided to use Redis for caching",
        "confidence": 0.9,
        "person_name": "alice",
        "ticket_refs": ["ENG-123"],
    }
    defaults.update(overrides)
    return ExtractedDecision(**defaults)


def _make_blocker(**overrides) -> ExtractedBlocker:
    """Helper to create an ExtractedBlocker with sensible defaults for tests."""
    defaults = {
        "description": "CI pipeline broken",
        "source_quote": "CI pipeline is currently broken",
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return ExtractedBlocker(**defaults)


class TestSourceValidation:
    """Tests for validate_extraction source quote verification."""

    ORIGINAL_CONTENT = (
        "In today's standup, we decided to use Redis for caching because it handles "
        "pub/sub well. Also, the CI pipeline is currently broken and blocking deploys."
    )

    def test_keeps_valid_entities(self):
        """Entities whose source_quote is found in original content are kept."""
        result = ExtractionResult(
            decisions=[_make_decision(source_quote="we decided to use Redis for caching")],
            blockers=[_make_blocker(source_quote="CI pipeline is currently broken")],
        )
        validated = validate_extraction(result, self.ORIGINAL_CONTENT)
        assert len(validated.decisions) == 1
        assert len(validated.blockers) == 1

    def test_drops_hallucinated_decisions(self):
        """Decisions whose source_quote is NOT in original content are dropped."""
        result = ExtractionResult(
            decisions=[_make_decision(source_quote="we switched to Memcached for performance")],
            blockers=[],
        )
        validated = validate_extraction(result, self.ORIGINAL_CONTENT)
        assert len(validated.decisions) == 0

    def test_drops_hallucinated_blockers(self):
        """Blockers whose source_quote is NOT in original content are dropped."""
        result = ExtractionResult(
            decisions=[],
            blockers=[_make_blocker(source_quote="database migration is failing")],
        )
        validated = validate_extraction(result, self.ORIGINAL_CONTENT)
        assert len(validated.blockers) == 0

    def test_mixed_valid_and_invalid(self):
        """Given 3 decisions (2 valid, 1 hallucinated), only the 2 valid ones survive."""
        result = ExtractionResult(
            decisions=[
                _make_decision(source_quote="we decided to use Redis for caching"),
                _make_decision(
                    description="Also handles pub/sub",
                    source_quote="it handles pub/sub well",
                ),
                _make_decision(
                    description="Switch to MongoDB",
                    source_quote="we are migrating to MongoDB",
                ),
            ],
            blockers=[],
        )
        validated = validate_extraction(result, self.ORIGINAL_CONTENT)
        assert len(validated.decisions) == 2
        assert validated.decisions[0].source_quote == "we decided to use Redis for caching"
        assert validated.decisions[1].source_quote == "it handles pub/sub well"

    def test_empty_result_passthrough(self):
        """Empty extraction results pass through unchanged."""
        result = ExtractionResult(decisions=[], blockers=[])
        validated = validate_extraction(result, self.ORIGINAL_CONTENT)
        assert len(validated.decisions) == 0
        assert len(validated.blockers) == 0

    def test_case_insensitive_matching(self):
        """Source quote matching is case-insensitive."""
        result = ExtractionResult(
            decisions=[_make_decision(source_quote="We Decided To Use Redis For Caching")],
            blockers=[],
        )
        validated = validate_extraction(result, self.ORIGINAL_CONTENT)
        assert len(validated.decisions) == 1


# ============================================================
# Content Hash Deduplication
# ============================================================


class TestContentHashDedup:
    """Tests for compute_content_hash SHA-256 content hashing."""

    def test_deterministic_hash(self):
        """Same input always produces the same hash."""
        hash1 = compute_content_hash("hello world")
        hash2 = compute_content_hash("hello world")
        assert hash1 == hash2

    def test_whitespace_normalization(self):
        """Multiple spaces are normalized to single space before hashing."""
        hash1 = compute_content_hash("hello  world")
        hash2 = compute_content_hash("hello world")
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content produces different hashes."""
        hash1 = compute_content_hash("hello")
        hash2 = compute_content_hash("world")
        assert hash1 != hash2

    def test_case_preservation(self):
        """Case is preserved -- 'Hello' and 'hello' produce different hashes."""
        hash1 = compute_content_hash("Hello")
        hash2 = compute_content_hash("hello")
        assert hash1 != hash2

    def test_returns_hex_string(self):
        """Hash is a 64-character hex string (SHA-256)."""
        result = compute_content_hash("test content")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_leading_trailing_whitespace_stripped(self):
        """Leading and trailing whitespace is stripped before hashing."""
        hash1 = compute_content_hash("  hello world  ")
        hash2 = compute_content_hash("hello world")
        assert hash1 == hash2
