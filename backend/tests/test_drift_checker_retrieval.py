"""Regression tests for drift_checkers._retrieve_artifacts SQL binding.

The content-fetch query binds a uuid[] parameter; asyncpg requires a Python
list, not a Postgres array literal string. Passing a string raised DataError
in production (2026-08-13), silently blanking every checker's evidence.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.decision_drift import ExpectedConsequence
from src.services import drift_checkers as dc

WS = uuid.uuid4()


def _consequence() -> ExpectedConsequence:
    return ExpectedConsequence(
        id=uuid.uuid4(),
        workspace_id=WS,
        decision_id=uuid.uuid4(),
        target_type="docs",
        target_query="registry config",
        expected_state="npmrc points at the group registry",
        importance="high",
        status="pending",
    )


@pytest.mark.asyncio
async def test_retrieve_binds_ids_as_list_not_array_string():
    emb_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    hybrid_result = MagicMock()
    hybrid_result.fetchall.return_value = [
        (emb_ids[0], "notion_page", str(uuid.uuid4()), 0.9),
        (emb_ids[1], "notion_page", str(uuid.uuid4()), 0.8),
    ]
    content_result = MagicMock()
    content_result.fetchall.return_value = [
        (emb_ids[0], "excerpt one"),
        (emb_ids[1], "excerpt two"),
    ]

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[hybrid_result, content_result])

    with patch(
        "src.services.embedding.generate_embedding",
        AsyncMock(return_value=[0.1, 0.2]),
    ):
        # docs -> single source_type filter -> one hybrid call + one content call
        with patch.dict(dc._SOURCE_FILTERS, {"docs": ["notion_page"]}):
            artifacts = await dc._retrieve_artifacts(session, _consequence())

    # The content-fetch (second execute) must bind :ids as a list of strings.
    content_call = session.execute.call_args_list[1]
    ids_param = content_call.args[1]["ids"]
    assert isinstance(ids_param, list)
    assert all(isinstance(x, str) for x in ids_param)
    assert set(ids_param) == set(emb_ids)

    # Excerpts get stitched back onto the artifacts.
    assert {a["excerpt"] for a in artifacts} == {"excerpt one", "excerpt two"}
