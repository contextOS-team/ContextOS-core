"""Test stubs for graph section in synthesis prompt.

These tests are intentionally failing placeholders for Plan 02 scope.
They establish the test scaffolding for graph-enhanced synthesis features:
- Graph section formatting in the synthesis prompt
- Decision node highlighting format
- End-to-end graph inclusion in generate_context
"""

import pytest


@pytest.mark.asyncio
async def test_format_graph_section() -> None:
    """Graph connections should be formatted as a separate section
    in the synthesis prompt with path + snippet per result."""
    assert False, "Not yet implemented -- Plan 02"


@pytest.mark.asyncio
async def test_decision_node_format() -> None:
    """Decision nodes should render with special highlighting:
    [DECISION] description | By: person | In: source | Affects: tickets | Confidence: X.X"""
    assert False, "Not yet implemented -- Plan 02"


@pytest.mark.asyncio
async def test_generate_includes_graph() -> None:
    """generate_context should include graph results in the synthesis
    prompt when graph data is available for the ticket."""
    assert False, "Not yet implemented -- Plan 02"
