"""Tests for synthesis template structure and code formatting.

Covers:
1. SYNTHESIS_TEMPLATE has exactly 7 sections
2. _format_related_content renders code_chunk with fenced code block
3. _format_related_content renders non-code items as plain text
4. _format_related_content returns fallback for empty items
5. Golden snapshot: code_chunk formatting matches expected output
6. Enriched section instructions for graph data integration (SYNTH-01/02/03)
"""

import re
from unittest.mock import MagicMock

from src.services.synthesis import SYNTHESIS_TEMPLATE, _format_related_content

EXPECTED_SECTIONS = [
    "Summary",
    "Background & Decisions",
    "Requirements",
    "Related Work",
    "Relevant Code",
    "Open Questions",
    "Key People",
]


def _extract_section_text(template: str, section_number: int) -> str:
    """Extract the instruction text for a specific numbered section.

    Splits SYNTHESIS_TEMPLATE by numbered section markers (e.g. '2. **')
    and returns the text belonging to the requested section number.
    """
    lines = template.splitlines()
    section_start = None
    section_end = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and stripped[0].isdigit() and ". **" in stripped:
            num = int(stripped.split(".")[0])
            if num == section_number:
                section_start = i
            elif section_start is not None:
                section_end = i
                break

    if section_start is None:
        raise ValueError(f"Section {section_number} not found in template")

    if section_end is None:
        section_end = len(lines)

    return "\n".join(lines[section_start:section_end])


class TestSynthesisTemplateSections:
    """Verify the synthesis template has the expected section structure."""

    def test_template_has_seven_sections(self):
        """SYNTHESIS_TEMPLATE must define exactly 7 numbered section headers."""
        section_lines = [
            line for line in SYNTHESIS_TEMPLATE.splitlines()
            if line.strip() and line.strip()[0].isdigit() and ". **" in line
        ]
        assert len(section_lines) == 7, (
            f"Expected 7 sections, found {len(section_lines)}: "
            f"{[line.strip()[:40] for line in section_lines]}"
        )

    def test_template_includes_relevant_code_section(self):
        """SYNTHESIS_TEMPLATE must include a 'Relevant Code' section."""
        assert "Relevant Code" in SYNTHESIS_TEMPLATE

    def test_relevant_code_is_section_five(self):
        """Relevant Code must be the 5th numbered section in the template."""
        section_lines = [
            line for line in SYNTHESIS_TEMPLATE.splitlines()
            if line.strip() and line.strip()[0].isdigit() and ". **" in line
        ]
        assert len(section_lines) >= 5
        assert "Relevant Code" in section_lines[4], (
            f"Relevant Code should be section 5, got: {section_lines[4].strip()[:50]}"
        )

    def test_template_section_order(self):
        """Sections must appear in correct order."""
        found_order = []
        for line in SYNTHESIS_TEMPLATE.splitlines():
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and ". **" in stripped:
                # Extract name between ** markers: e.g. '1. **Summary** —' -> 'Summary'
                match = re.search(r"\*\*(.+?)\*\*", stripped)
                if match:
                    section_name = match.group(1).strip()
                    if section_name in EXPECTED_SECTIONS:
                        found_order.append(section_name)
        assert found_order == EXPECTED_SECTIONS


class TestFormatRelatedContent:
    """Verify related-content formatting for different source types."""

    def _make_item(
        self,
        source_type: str,
        title: str,
        snippet: str,
        score: float = 0.8,
    ):
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
        """code_chunk items should render with fenced code blocks."""
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
        assert result.index("```text") < result.index("**Retrieval metadata:**")
        assert "calculate_score" in result


class TestEnrichedSectionInstructions:
    """Verify conditional graph enrichment prompt instructions.

    These tests verify SYNTH-01/02/03 requirements: the synthesis prompt
    tells the LLM how to weave graph data into narrative sections.
    """

    def test_section_two_includes_decision_trail(self):
        """Section 2 (Background & Decisions) must contain conditional
        decision trail instruction referencing [DECISION] items from
        Graph Connections, mentioning weaving into narrative, citing
        confidence level, and citing source."""
        section = _extract_section_text(SYNTHESIS_TEMPLATE, 2)

        assert "[DECISION]" in section, (
            "Section 2 must reference [DECISION] items from Graph Connections"
        )
        assert "confidence" in section.lower(), (
            "Section 2 must mention confidence level for decisions"
        )
        assert "source" in section.lower(), (
            "Section 2 must instruct citing the source of decisions"
        )

    def test_section_four_includes_relationship_paths(self):
        """Section 4 (Related Work) must contain conditional relationship
        path instruction mentioning natural language explanation of
        connections, NOT raw path notation."""
        section = _extract_section_text(SYNTHESIS_TEMPLATE, 4)

        assert "natural language" in section.lower() or "explain" in section.lower(), (
            "Section 4 must instruct natural language explanation of relationships"
        )
        # Must NOT tell the LLM to use raw path notation
        assert "raw" in section.lower() or "rather than" in section.lower(), (
            "Section 4 must discourage raw path notation"
        )

    def test_section_five_includes_discussion_provenance(self):
        """Section 5 (Relevant Code) must contain instruction about
        discussion provenance annotations ('Discussed in:')."""
        section = _extract_section_text(SYNTHESIS_TEMPLATE, 5)

        has_discussion_provenance = (
            "Discussed in" in section
            or "discussion provenance" in section.lower()
        )
        assert has_discussion_provenance, (
            "Section 5 must mention discussion provenance annotations"
        )

    def test_section_seven_includes_cross_source_involvement(self):
        """Section 7 (Key People) must contain cross-source involvement
        instruction mentioning graph data for multi-source engagement."""
        section = _extract_section_text(SYNTHESIS_TEMPLATE, 7)

        mentions_cross_source = (
            "cross-source" in section.lower()
            or "multiple sources" in section.lower()
        )
        assert mentions_cross_source, (
            "Section 7 must instruct cross-source involvement display"
        )

    def test_all_new_instructions_are_conditional(self):
        """All new graph-referencing instructions must be conditional,
        containing 'If' referring to Graph Connections section or graph data,
        so empty graph_section produces no hallucinated content."""
        # Check sections 2, 4, 7 have conditional phrasing
        for section_num in [2, 4, 7]:
            section = _extract_section_text(SYNTHESIS_TEMPLATE, section_num)
            has_conditional = (
                "If the Graph Connections" in section
                or "If graph data" in section
            )
            assert has_conditional, (
                f"Section {section_num} must contain conditional phrasing "
                f"('If the Graph Connections...' or 'If graph data...')"
            )

    def test_template_still_has_seven_sections(self):
        """Regression: enriched instructions do NOT add new sections."""
        section_lines = [
            line for line in SYNTHESIS_TEMPLATE.splitlines()
            if line.strip() and line.strip()[0].isdigit() and "**" in line
        ]
        assert len(section_lines) == 7, (
            f"Expected 7 sections, found {len(section_lines)}: "
            f"{[line.strip()[:40] for line in section_lines]}"
        )
