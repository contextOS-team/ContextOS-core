"""Tests for synthesis template structure and code formatting.

Covers:
1. SYNTHESIS_TEMPLATE has exactly 7 sections
2. _format_related_content renders code_chunk with fenced code block
3. _format_related_content renders non-code items as plain text
4. _format_related_content returns fallback for empty items
5. Golden snapshot: code_chunk formatting matches expected output
"""

from unittest.mock import MagicMock

import pytest

from src.services.synthesis import SYNTHESIS_TEMPLATE, _format_related_content


class TestSynthesisTemplateSections:
    """Verify the synthesis template has the expected section structure."""

    def test_template_has_seven_sections(self):
        """SYNTHESIS_TEMPLATE must define exactly 7 numbered sections."""
        # Count numbered section headers (1. **Summary**, 2. **Background**, etc.)
        section_lines = [
            line for line in SYNTHESIS_TEMPLATE.splitlines()
            if line.strip() and line.strip()[0].isdigit() and "**" in line
        ]
        assert len(section_lines) == 7, (
            f"Expected 7 sections, found {len(section_lines)}: "
            f"{[l.strip()[:40] for l in section_lines]}"
        )

    def test_template_includes_relevant_code_section(self):
        """SYNTHESIS_TEMPLATE must include a 'Relevant Code' section."""
        assert "Relevant Code" in SYNTHESIS_TEMPLATE

    def test_relevant_code_is_section_five(self):
        """Relevant Code must be section 5 in the template."""
        for line in SYNTHESIS_TEMPLATE.splitlines():
            if "Relevant Code" in line:
                assert line.strip().startswith("5."), (
                    f"Relevant Code should be section 5, got: {line.strip()[:50]}"
                )
                break
        else:
            pytest.fail("Relevant Code section not found")

    def test_template_section_order(self):
        """Sections must appear in correct order: Summary, Background, Requirements, Related Work, Relevant Code, Open Questions, Key People."""
        expected_keywords = [
            "Summary", "Background", "Requirements", "Related Work",
            "Relevant Code", "Open Questions", "Key People",
        ]
        found_order = []
        for line in SYNTHESIS_TEMPLATE.splitlines():
            for kw in expected_keywords:
                if kw in line and line.strip()[0].isdigit():
                    found_order.append(kw)
        assert found_order == expected_keywords


class TestFormatRelatedContent:
    """Verify _format_related_content produces correct output for different source types."""

    def _make_item(self, source_type: str, title: str, snippet: str, score: float = 0.8):
        item = MagicMock()
        item.source_type = source_type
        item.title = title
        item.snippet = snippet
        item.relevance_score = score
        item.signals = ["hybrid_search"]
        return item

    def test_empty_items_returns_no_content_message(self):
        result = _format_related_content([])
        assert result == "No related content found."

    def test_code_chunk_uses_fenced_code_block(self):
        """code_chunk items should be rendered with triple-backtick fenced code blocks."""
        item = self._make_item(
            "code_chunk",
            "function: auth (acme/backend:src/auth.py)",
            "def auth(token): pass",
        )
        result = _format_related_content([item])
        assert "```" in result
        assert "def auth(token): pass" in result

    def test_non_code_item_uses_plain_text(self):
        """Non-code items should NOT use fenced code blocks."""
        item = self._make_item(
            "slack_message",
            "Slack by alice in #dev",
            "Let's ship this today",
        )
        result = _format_related_content([item])
        assert "```" not in result
        assert "Let's ship this today" in result

    def test_mixed_items_correct_formatting(self):
        """Mixed code and non-code items should each use their correct format."""
        code = self._make_item(
            "code_chunk", "fn: foo", "def foo(): pass"
        )
        slack = self._make_item(
            "slack_message", "Slack msg", "hello world"
        )
        result = _format_related_content([code, slack])

        # Code section has fences
        sections = result.split("---")
        code_section = sections[0]
        slack_section = sections[1]
        assert "```" in code_section
        assert "```" not in slack_section

    def test_golden_snapshot_code_chunk(self):
        """Golden snapshot: code_chunk formatting matches expected structure."""
        item = self._make_item(
            "code_chunk",
            "function: calculate_score (acme/backend:src/scoring.py)",
            "def calculate_score(items):\n    return sum(i.score for i in items)",
            score=0.75,
        )
        result = _format_related_content([item])

        # Verify structure: header, relevance line, code block
        lines = result.strip().splitlines()
        assert lines[0].startswith("#### [code_chunk]")
        assert "0.75" in lines[1]
        assert "hybrid_search" in lines[1]
        assert "```" in lines[2] or "```" in lines[3]
        assert "calculate_score" in result
