"""Regression tests for FastAPI lifespan background task wiring."""

from __future__ import annotations

import ast
from pathlib import Path


def test_community_backfill_is_not_restart_supervised() -> None:
    """The startup-only community backfill must not run in the forever supervisor."""
    source = (Path(__file__).parents[1] / "src/main.py").read_text()
    tree = ast.parse(source)

    supervised_backfill_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_supervised":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if (
            isinstance(first_arg, ast.Constant)
            and first_arg.value == "community_backfill"
        ):
            supervised_backfill_calls.append(node)

    assert supervised_backfill_calls == []
