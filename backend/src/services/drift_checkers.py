"""Artifact checkers: test an expected consequence against observed reality.

v1 checker = hybrid retrieval (embeddings + FTS across all ingested sources,
scoped by target_type) + one LLM consistency evaluation over the retrieved
artifacts. Persists an ArtifactObservation with frozen evidence refs.

ponytail: one generic checker parameterized by target_type; split into true
per-provider modules when a provider needs bespoke logic (e.g. cycle dates).
"""

import logging

from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.decision import Decision
from src.models.decision_drift import ArtifactObservation, ExpectedConsequence
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

RETRIEVAL_LIMIT = 8

# target_type -> embeddings.source_type filter (None = search everything)
_SOURCE_FILTERS: dict[str, list[str] | None] = {
    "linear": ["linear_ticket", "linear_comment"],
    "jira": ["jira_issue", "jira_comment"],
    "github": ["github_pull_request", "github_review", "code_chunk"],
    "docs": ["notion_page"],
    "release": None,
    "other": None,
}

_CONSISTENCY_SYSTEM = (
    "You check whether an engineering organization's artifacts reflect an "
    "expected consequence of a decision. Given the decision, the expectation, "
    "and excerpts of the most relevant artifacts, judge: does observed reality "
    "match the expected state? consistent=true when artifacts match or nothing "
    "contradicts the expectation; consistent=false ONLY when an artifact "
    "actively shows the expectation was not carried out. Summarize what the "
    "artifacts actually show in observed_state. If the retrieved artifacts are "
    "irrelevant to the expectation, set relevant=false."
)


class ConsistencyVerdict(BaseModel):
    consistent: bool
    relevant: bool
    observed_state: str
    reasoning: str


async def _retrieve_artifacts(
    session: AsyncSession,
    consequence: ExpectedConsequence,
) -> list[dict]:
    """Hybrid search for artifacts relevant to the consequence's target query."""
    from src.services.embedding import generate_embedding

    query_embedding = await generate_embedding(consequence.target_query)
    source_types = _SOURCE_FILTERS.get(consequence.target_type)

    artifacts: list[dict] = []
    for source_type in source_types or [None]:
        result = await session.execute(
            sa_text(
                """
                SELECT id, source_type, source_id, combined_score
                FROM hybrid_search(
                    CAST(:query_embedding AS vector), :query_text,
                    CAST(:workspace_id AS uuid), :source_type,
                    0.7, 0.3, 0.5, :limit
                )
                """
            ),
            {
                "query_embedding": str(query_embedding),
                "query_text": consequence.target_query,
                "workspace_id": str(consequence.workspace_id),
                "source_type": source_type,
                "limit": RETRIEVAL_LIMIT,
            },
        )
        for row in result.fetchall():
            artifacts.append(
                {
                    "embedding_id": str(row[0]),
                    "source_type": row[1],
                    "source_id": str(row[2]),
                    "score": float(row[3]),
                }
            )

    artifacts.sort(key=lambda a: a["score"], reverse=True)
    artifacts = artifacts[:RETRIEVAL_LIMIT]

    if artifacts:
        content_rows = await session.execute(
            sa_text(
                "SELECT id, left(search_content, 600) FROM embeddings"
                " WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": "{" + ",".join(a["embedding_id"] for a in artifacts) + "}"},
        )
        content_by_id = {str(r[0]): r[1] for r in content_rows.fetchall()}
        for a in artifacts:
            a["excerpt"] = content_by_id.get(a["embedding_id"], "")
    return artifacts


async def check_consequence(
    session: AsyncSession,
    decision: Decision,
    consequence: ExpectedConsequence,
) -> ArtifactObservation | None:
    """Run one checker pass; persists and returns the observation."""
    try:
        artifacts = await _retrieve_artifacts(session, consequence)
    except Exception:
        logger.exception("artifact retrieval failed for %s", consequence.id)
        return None

    if not artifacts:
        observation = ArtifactObservation(
            workspace_id=consequence.workspace_id,
            expected_consequence_id=consequence.id,
            checker=consequence.target_type,
            observed_state="no relevant artifacts found",
            consistent=None,  # absence of evidence is not drift evidence
            evidence=[],
        )
        session.add(observation)
        await session.flush()
        return observation

    excerpts = "\n\n".join(
        f"[{a['source_type']} {a['source_id']}]\n{a['excerpt']}" for a in artifacts
    )
    prompt = (
        f"Decision:\n{decision.statement}\n\n"
        f"Expected consequence ({consequence.target_type}):\n"
        f"{consequence.expected_state}\n\n"
        f"Most relevant artifacts:\n{excerpts}\n\n"
        "Does observed reality match the expectation?"
    )
    try:
        client = get_llm_client()
        verdict = await client.generate_json(
            prompt,
            ConsistencyVerdict,
            system_prompt=_CONSISTENCY_SYSTEM,
            workspace_id=consequence.workspace_id,
        )
    except Exception:
        logger.exception("consistency evaluation failed for %s", consequence.id)
        return None

    observation = ArtifactObservation(
        workspace_id=consequence.workspace_id,
        expected_consequence_id=consequence.id,
        checker=consequence.target_type,
        observed_state=verdict.observed_state,
        consistent=None if not verdict.relevant else verdict.consistent,
        evidence=[
            {
                "source_type": a["source_type"],
                "source_id": a["source_id"],
                "excerpt": a["excerpt"][:300],
                "score": a["score"],
            }
            for a in artifacts
        ],
    )
    session.add(observation)
    consequence.status = "checked"
    await session.flush()
    return observation
