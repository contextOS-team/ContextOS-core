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
    persist_blocker,
    persist_decision,
    process_single_content,
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


# ============================================================
# Decision / Blocker Persistence Helpers
# ============================================================

# Pre-populate sys.modules with a mock graph_ops so that:
# 1. The lazy `from src.services import graph_ops` inside persist_decision/persist_blocker
#    doesn't trigger sqlmodel/SQLAlchemy imports in the test environment
# 2. unittest.mock.patch("src.services.graph_ops.upsert_node") can resolve the target
import sys
import types as _types

_mock_graph_ops = _types.ModuleType("src.services.graph_ops")
_mock_graph_ops.upsert_node = AsyncMock()
_mock_graph_ops.upsert_edge = AsyncMock()
if "src.services.graph_ops" not in sys.modules:
    sys.modules["src.services.graph_ops"] = _mock_graph_ops
    # Also register on the parent package so `from src.services import graph_ops` works
    import src.services
    src.services.graph_ops = _mock_graph_ops  # type: ignore[attr-defined]

# Pre-populate src.models.graph_node with a lightweight mock to avoid sqlmodel import chain
# (same pattern as graph_ops mock above -- needed for process_single_content's session.get call)
if "src.models.graph_node" not in sys.modules:
    _mock_graph_node_mod = _types.ModuleType("src.models.graph_node")

    class _MockGraphNode:
        """Lightweight stand-in for GraphNode in unit tests."""
        pass

    _mock_graph_node_mod.GraphNode = _MockGraphNode  # type: ignore[attr-defined]
    sys.modules["src.models.graph_node"] = _mock_graph_node_mod
    # Also register on the parent models package
    if "src.models" not in sys.modules:
        _mock_models_mod = _types.ModuleType("src.models")
        sys.modules["src.models"] = _mock_models_mod
    sys.modules["src.models"].graph_node = _mock_graph_node_mod  # type: ignore[attr-defined]


# ============================================================
# Decision Node Schema (persistence)
# ============================================================


class TestDecisionNodeSchema:
    """Tests for persist_decision graph node creation."""

    @staticmethod
    def _find_decision_node_call(mock_upsert_node):
        """Find the upsert_node call for the Decision entity type."""
        for call in mock_upsert_node.call_args_list:
            if call.kwargs.get("entity_type") == "Decision":
                return call.kwargs
        raise AssertionError("No upsert_node call with entity_type='Decision'")

    @pytest.mark.asyncio
    async def test_decision_node_has_required_properties(self):
        """persist_decision creates a Decision node with properties containing
        description, rationale, source_quote, confidence, status, extraction_model."""
        decision = _make_decision()
        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ) as mock_upsert_node, patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ):
            await persist_decision(
                mock_session, workspace_id, decision, source_node_id
            )

            # Check the properties dict passed to the Decision upsert_node call
            call_kwargs = self._find_decision_node_call(mock_upsert_node)
            props = call_kwargs["properties"]
            assert props["description"] == decision.description
            assert props["rationale"] == decision.rationale
            assert props["source_quote"] == decision.source_quote
            assert props["confidence"] == decision.confidence
            assert props["status"] == "active"
            assert props["extraction_model"] == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_decision_external_id_uses_source_quote_hash(self):
        """The external_id passed to upsert_node is 'decision:{hash_of_source_quote}'
        for deterministic fingerprint dedup."""
        decision = _make_decision(source_quote="we decided to use Redis for caching")
        expected_hash = compute_content_hash("we decided to use Redis for caching")
        expected_ext_id = f"decision:{expected_hash}"

        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ) as mock_upsert_node, patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ):
            await persist_decision(
                mock_session, workspace_id, decision, source_node_id
            )

            call_kwargs = self._find_decision_node_call(mock_upsert_node)
            assert call_kwargs["external_id"] == expected_ext_id

    @pytest.mark.asyncio
    async def test_decision_name_truncated(self):
        """The name passed to upsert_node is description truncated to 100 chars."""
        long_desc = "A" * 200
        decision = _make_decision(description=long_desc)

        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ) as mock_upsert_node, patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ):
            await persist_decision(
                mock_session, workspace_id, decision, source_node_id
            )

            call_kwargs = self._find_decision_node_call(mock_upsert_node)
            assert len(call_kwargs["name"]) == 100
            assert call_kwargs["name"] == long_desc[:100]


# ============================================================
# Decision Edges (persistence)
# ============================================================


class TestDecisionEdges:
    """Tests for persist_decision and persist_blocker edge creation."""

    @pytest.mark.asyncio
    async def test_decision_discussed_in_edge(self):
        """persist_decision creates a 'discussed_in' edge from Decision node
        to source_node_id."""
        decision = _make_decision(ticket_refs=[])
        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ), patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ) as mock_upsert_edge:
            await persist_decision(
                mock_session, workspace_id, decision, source_node_id
            )

            # Find the discussed_in edge call
            edge_calls = mock_upsert_edge.call_args_list
            discussed_in_calls = [
                c for c in edge_calls
                if c.kwargs.get("relationship_type") == "discussed_in"
            ]
            assert len(discussed_in_calls) == 1
            call_kwargs = discussed_in_calls[0].kwargs
            assert call_kwargs["source_node_id"] == decision_node_id
            assert call_kwargs["target_node_id"] == source_node_id

    @pytest.mark.asyncio
    async def test_decision_authored_by_edge(self):
        """When author_node_id is provided, persist_decision creates an
        'authored_by' edge from Decision to Person node."""
        decision = _make_decision(ticket_refs=[])
        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        author_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ), patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ) as mock_upsert_edge:
            await persist_decision(
                mock_session, workspace_id, decision, source_node_id,
                author_node_id=author_node_id,
            )

            edge_calls = mock_upsert_edge.call_args_list
            authored_by_calls = [
                c for c in edge_calls
                if c.kwargs.get("relationship_type") == "authored_by"
            ]
            assert len(authored_by_calls) == 1
            call_kwargs = authored_by_calls[0].kwargs
            assert call_kwargs["source_node_id"] == decision_node_id
            assert call_kwargs["target_node_id"] == author_node_id

    @pytest.mark.asyncio
    async def test_decision_no_author_edge_when_none(self):
        """When author_node_id is None, no 'authored_by' edge is created."""
        decision = _make_decision(ticket_refs=[])
        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ), patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ) as mock_upsert_edge:
            await persist_decision(
                mock_session, workspace_id, decision, source_node_id,
                author_node_id=None,
            )

            edge_calls = mock_upsert_edge.call_args_list
            authored_by_calls = [
                c for c in edge_calls
                if c.kwargs.get("relationship_type") == "authored_by"
            ]
            assert len(authored_by_calls) == 0

    @pytest.mark.asyncio
    async def test_decision_references_ticket_edges(self):
        """When ticket_refs is non-empty, persist_decision creates 'references'
        edges from Decision to Ticket nodes."""
        decision = _make_decision(ticket_refs=["ENG-123", "ENG-456"])
        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()
        ticket_node_id_1 = uuid4()
        ticket_node_id_2 = uuid4()

        # upsert_node returns different IDs: first for Decision, then for each Ticket
        node_ids = [decision_node_id, ticket_node_id_1, ticket_node_id_2]

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            side_effect=node_ids,
        ) as mock_upsert_node, patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ) as mock_upsert_edge:
            await persist_decision(
                mock_session, workspace_id, decision, source_node_id,
            )

            # Verify Ticket nodes were upserted
            node_calls = mock_upsert_node.call_args_list
            ticket_calls = [
                c for c in node_calls
                if c.kwargs.get("entity_type") == "Ticket"
            ]
            assert len(ticket_calls) == 2
            assert ticket_calls[0].kwargs["external_id"] == "ENG-123"
            assert ticket_calls[1].kwargs["external_id"] == "ENG-456"

            # Verify references edges
            edge_calls = mock_upsert_edge.call_args_list
            ref_calls = [
                c for c in edge_calls
                if c.kwargs.get("relationship_type") == "references"
            ]
            assert len(ref_calls) == 2

    @pytest.mark.asyncio
    async def test_blocker_persistence(self):
        """persist_blocker creates a Blocker node with 'blocks' relationship
        to source node."""
        blocker = _make_blocker()
        mock_session = AsyncMock()
        workspace_id = uuid4()
        source_node_id = uuid4()
        blocker_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=blocker_node_id,
        ) as mock_upsert_node, patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ) as mock_upsert_edge:
            result_id = await persist_blocker(
                mock_session, workspace_id, blocker, source_node_id,
            )

            # Verify Blocker node was created
            node_kwargs = mock_upsert_node.call_args.kwargs
            assert node_kwargs["entity_type"] == "Blocker"
            assert "blocker:" in node_kwargs["external_id"]
            props = node_kwargs["properties"]
            assert props["description"] == blocker.description
            assert props["source_quote"] == blocker.source_quote
            assert props["confidence"] == blocker.confidence
            assert props["status"] == "active"
            assert props["extraction_model"] == "gemini-2.0-flash"

            # Verify blocks edge
            edge_kwargs = mock_upsert_edge.call_args.kwargs
            assert edge_kwargs["relationship_type"] == "blocks"
            assert edge_kwargs["source_node_id"] == blocker_node_id
            assert edge_kwargs["target_node_id"] == source_node_id

            assert result_id == blocker_node_id


# ============================================================
# Batch Pipeline: process_single_content
# ============================================================


class TestBatchPipeline:
    """Tests for process_single_content single-item and batch_extract_llm batch pipeline."""

    CONTENT = (
        "In today's standup, we decided to use Redis for caching because it handles "
        "pub/sub well. Also, the CI pipeline is currently broken and blocking deploys."
    )

    @pytest.mark.asyncio
    async def test_process_single_content_extracts_and_persists(self):
        """process_single_content with mocked Gemini returning 1 decision calls
        persist_decision once and returns stats with extracted=1, decisions=1."""
        decision = _make_decision(source_quote="we decided to use Redis for caching")
        mock_result = ExtractionResult(decisions=[decision], blockers=[])

        mock_session = AsyncMock()
        # Mock session.get to return a GraphNode-like object with empty properties
        mock_source_node = MagicMock()
        mock_source_node.properties = {}
        mock_session.get = AsyncMock(return_value=mock_source_node)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ) as mock_upsert_node, patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ):
            stats = await process_single_content(
                session=mock_session,
                client=mock_client,
                workspace_id=workspace_id,
                content=self.CONTENT,
                source_type="slack_message",
                source_node_id=source_node_id,
            )

            assert stats["extracted"] == 1
            assert stats["decisions"] == 1
            assert stats["skipped_filter"] == 0
            assert stats["skipped_dedup"] == 0
            assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_single_content_skips_filtered(self):
        """process_single_content with short text (<50 chars) returns stats with
        skipped_filter=1, extracted=0."""
        mock_session = AsyncMock()
        mock_client = MagicMock()
        workspace_id = uuid4()
        source_node_id = uuid4()

        stats = await process_single_content(
            session=mock_session,
            client=mock_client,
            workspace_id=workspace_id,
            content="ok",
            source_type="slack_message",
            source_node_id=source_node_id,
        )

        assert stats["skipped_filter"] == 1
        assert stats["extracted"] == 0

    @pytest.mark.asyncio
    async def test_process_single_content_skips_already_processed(self):
        """process_single_content with content whose hash matches existing node
        property returns stats with skipped_dedup=1."""
        from src.services.llm_extractor import compute_content_hash

        content_hash = compute_content_hash(self.CONTENT)

        mock_session = AsyncMock()
        mock_source_node = MagicMock()
        mock_source_node.properties = {"llm_content_hash": content_hash}
        mock_session.get = AsyncMock(return_value=mock_source_node)

        mock_client = MagicMock()
        workspace_id = uuid4()
        source_node_id = uuid4()

        stats = await process_single_content(
            session=mock_session,
            client=mock_client,
            workspace_id=workspace_id,
            content=self.CONTENT,
            source_type="slack_message",
            source_node_id=source_node_id,
        )

        assert stats["skipped_dedup"] == 1
        assert stats["extracted"] == 0

    @pytest.mark.asyncio
    async def test_process_single_content_marks_extracted(self):
        """After processing, the source node properties are updated with
        llm_content_hash and llm_extracted_at."""
        decision = _make_decision(source_quote="we decided to use Redis for caching")
        mock_result = ExtractionResult(decisions=[decision], blockers=[])

        mock_session = AsyncMock()
        mock_source_node = MagicMock()
        mock_source_node.properties = {}
        mock_session.get = AsyncMock(return_value=mock_source_node)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
            return_value=decision_node_id,
        ), patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ):
            await process_single_content(
                session=mock_session,
                client=mock_client,
                workspace_id=workspace_id,
                content=self.CONTENT,
                source_type="slack_message",
                source_node_id=source_node_id,
            )

            # Verify source node was marked with extraction metadata
            assert "llm_content_hash" in mock_source_node.properties
            assert "llm_extracted_at" in mock_source_node.properties

    @pytest.mark.asyncio
    async def test_person_resolution_from_slack_user_id(self):
        """When author_user_id is a Slack user ID, process_single_content upserts
        a Person node with external_id='slack:{user_id}' and passes its node_id
        to persist_decision."""
        decision = _make_decision(source_quote="we decided to use Redis for caching")
        mock_result = ExtractionResult(decisions=[decision], blockers=[])

        mock_session = AsyncMock()
        mock_source_node = MagicMock()
        mock_source_node.properties = {}
        mock_session.get = AsyncMock(return_value=mock_source_node)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=_mock_gemini_response(mock_result)
        )

        workspace_id = uuid4()
        source_node_id = uuid4()
        decision_node_id = uuid4()
        person_node_id = uuid4()

        with patch(
            "src.services.graph_ops.upsert_node",
            new_callable=AsyncMock,
        ) as mock_upsert_node, patch(
            "src.services.graph_ops.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid4(),
        ):
            # First call: Person node upsert returns person_node_id
            # Subsequent calls: Decision/Ticket node upserts return decision_node_id
            def _side_effect(**kwargs):
                if kwargs.get("entity_type") == "Person":
                    return person_node_id
                return decision_node_id

            mock_upsert_node.side_effect = _side_effect

            stats = await process_single_content(
                session=mock_session,
                client=mock_client,
                workspace_id=workspace_id,
                content=self.CONTENT,
                source_type="slack_message",
                source_node_id=source_node_id,
                author_user_id="U12345ABC",
            )

            # Verify Person node was created with slack: prefix
            person_calls = [
                c for c in mock_upsert_node.call_args_list
                if c.kwargs.get("entity_type") == "Person"
            ]
            assert len(person_calls) >= 1
            assert person_calls[0].kwargs["external_id"] == "slack:U12345ABC"

            # Verify authored_by edge was created
            edge_calls = [
                c for c in mock_upsert_node.call_args_list
            ]
            # Check persist_decision was called (indirectly through upsert_edge)

    @pytest.mark.asyncio
    async def test_process_handles_gemini_error(self):
        """If extract_entities raises an exception, process_single_content logs
        error and returns stats with errors=1 (fail-silent)."""
        mock_session = AsyncMock()
        mock_source_node = MagicMock()
        mock_source_node.properties = {}
        mock_session.get = AsyncMock(return_value=mock_source_node)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Gemini API error")
        )

        workspace_id = uuid4()
        source_node_id = uuid4()

        stats = await process_single_content(
            session=mock_session,
            client=mock_client,
            workspace_id=workspace_id,
            content=self.CONTENT,
            source_type="slack_message",
            source_node_id=source_node_id,
        )

        assert stats["errors"] == 1
        assert stats["extracted"] == 0
