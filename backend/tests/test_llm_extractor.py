"""Unit tests for llm_extractor: content filter, schemas, source validation, content hash,
Gemini extraction service, and decision/blocker persistence.

Tests the pure-function foundation, mocked Gemini extraction, and graph persistence.
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.services.llm_extractor import (
    EXTRACTION_SYSTEM_PROMPT,
    ExtractedBlocker,
    ExtractedDecision,
    ExtractionResult,
    compute_content_hash,
    extract_entities,
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


# ============================================================
# Gemini Extraction Service (mocked)
# ============================================================


def _mock_gemini_response(parsed: ExtractionResult) -> MagicMock:
    """Create a mock Gemini response with a parsed attribute."""
    response = MagicMock()
    response.parsed = parsed
    return response


class TestLLMExtraction:
    """Tests for extract_entities with mocked Gemini client."""

    CONTENT = (
        "In today's standup, we decided to use Redis for caching because it handles "
        "pub/sub well. Also, the CI pipeline is currently broken and blocking deploys."
    )

    @pytest.mark.asyncio
    async def test_extracts_decisions_from_slack(self):
        """extract_entities with mocked Gemini response containing a decision returns
        ExtractionResult with 1 decision."""
        decision = _make_decision(source_quote="we decided to use Redis for caching")
        mock_result = ExtractionResult(decisions=[decision], blockers=[])

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        result = await extract_entities(client, self.CONTENT, "slack_message")
        assert len(result.decisions) == 1
        assert result.decisions[0].description == "Use Redis for caching"

    @pytest.mark.asyncio
    async def test_extracts_blockers(self):
        """extract_entities with mocked Gemini response containing a blocker returns
        ExtractionResult with 1 blocker."""
        blocker = _make_blocker(source_quote="CI pipeline is currently broken")
        mock_result = ExtractionResult(decisions=[], blockers=[blocker])

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        result = await extract_entities(client, self.CONTENT, "slack_message")
        assert len(result.blockers) == 1
        assert result.blockers[0].description == "CI pipeline broken"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_entities(self):
        """extract_entities with mocked Gemini returning empty lists returns
        ExtractionResult with empty decisions and blockers lists."""
        mock_result = ExtractionResult(decisions=[], blockers=[])

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        result = await extract_entities(client, self.CONTENT, "slack_message")
        assert len(result.decisions) == 0
        assert len(result.blockers) == 0

    @pytest.mark.asyncio
    async def test_validates_against_source_text(self):
        """extract_entities calls validate_extraction on the raw Gemini output
        before returning -- hallucinated quotes are dropped."""
        hallucinated = _make_decision(source_quote="we switched to Memcached")
        mock_result = ExtractionResult(decisions=[hallucinated], blockers=[])

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        result = await extract_entities(client, self.CONTENT, "slack_message")
        # Hallucinated quote not in CONTENT, so should be filtered out
        assert len(result.decisions) == 0

    @pytest.mark.asyncio
    async def test_uses_temperature_zero(self):
        """The GenerateContentConfig passed to Gemini has temperature=0."""
        mock_result = ExtractionResult(decisions=[], blockers=[])

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        await extract_entities(client, self.CONTENT, "slack_message")

        call_kwargs = client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config.temperature == 0

    @pytest.mark.asyncio
    async def test_uses_structured_output(self):
        """The GenerateContentConfig uses response_schema=ExtractionResult
        and response_mime_type='application/json'."""
        mock_result = ExtractionResult(decisions=[], blockers=[])

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        await extract_entities(client, self.CONTENT, "slack_message")

        call_kwargs = client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config.response_schema == ExtractionResult
        assert config.response_mime_type == "application/json"


class TestDecisionExtraction:
    """Tests for extraction system prompt and source_type inclusion."""

    def test_system_prompt_targets_decision_language(self):
        """EXTRACTION_SYSTEM_PROMPT contains keywords: 'decided', 'agreed', 'going with'."""
        prompt_lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "decided" in prompt_lower
        assert "agreed" in prompt_lower
        assert "going with" in prompt_lower

    @pytest.mark.asyncio
    async def test_extraction_includes_source_type_in_prompt(self):
        """The content string passed to Gemini includes the source_type parameter."""
        mock_result = ExtractionResult(decisions=[], blockers=[])

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        content = "We agreed to deploy on Friday after the review is complete and all tests pass."
        await extract_entities(client, content, "meeting_transcript")

        call_args = client.aio.models.generate_content.call_args
        contents_arg = call_args.kwargs.get("contents") or call_args[0][1]
        assert "meeting_transcript" in contents_arg
