"""Backfill existing Decision graph nodes into the typed decisions tables.

Imports every graph_nodes row with entity_type='Decision' that is not yet
mirrored by a decisions row, routing each through the canonical writer with
producer='import' and gate_mode='report' (consequentiality is scored but never
rejects — nothing silently disappears). Duplicate collapse stays ON, so the
existing polluted list deduplicates during import: repeated decisions merge as
evidence on one row.

Usage:
    cd backend
    uv run python scripts/migrate_decisions.py                # dry run, all workspaces
    uv run python scripts/migrate_decisions.py --apply
    uv run python scripts/migrate_decisions.py --workspace-id <uuid> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text  # noqa: E402
from sqlmodel import select  # noqa: E402

from src.db import async_session  # noqa: E402
from src.models.decision import Decision  # noqa: E402
from src.models.graph_node import GraphNode  # noqa: E402
from src.services.decision_writer import (  # noqa: E402
    DecisionDraft,
    EvidenceRef,
    WriteOutcome,
    create_decision,
)

logger = logging.getLogger("migrate_decisions")


def _draft_from_node(node: GraphNode) -> DecisionDraft:
    props = node.properties or {}
    statement = props.get("description") or node.name or ""
    quote = props.get("source_quote")
    evidence: list[EvidenceRef] = []
    if node.source_type and node.source_id and quote:
        evidence.append(
            EvidenceRef(
                source_type=node.source_type,
                source_id=node.source_id,
                quote=quote,
                source_link=props.get("source_link"),
            )
        )
    confidence = props.get("confidence")
    candidate_id = props.get("candidate_id")
    return DecisionDraft(
        statement=statement,
        rationale=props.get("rationale"),
        producer="import",
        evidence=evidence,
        confidence=confidence if isinstance(confidence, (int, float)) else None,
        candidate_id=UUID(candidate_id) if candidate_id else None,
    )


async def migrate(workspace_id: UUID | None, apply: bool) -> None:
    async with async_session() as session:
        already = set(
            (
                await session.execute(
                    sa_text(
                        "SELECT graph_node_id FROM decisions"
                        " WHERE graph_node_id IS NOT NULL"
                    )
                )
            ).scalars()
        )
        query = select(GraphNode).where(
            GraphNode.entity_type == "Decision",
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        if workspace_id is not None:
            query = query.where(GraphNode.workspace_id == workspace_id)
        nodes = (await session.execute(query)).scalars().all()

        pending = [n for n in nodes if n.id not in already]
        print(f"decision nodes: {len(nodes)}, not yet migrated: {len(pending)}")
        if not apply:
            for n in pending:
                stmt = (n.properties or {}).get("description") or n.name
                print(f"  would import: {str(stmt)[:90]}")
            print("dry run — pass --apply to import")
            return

        created = merged = skipped = 0
        for node in pending:
            draft = _draft_from_node(node)
            if not draft.statement.strip():
                skipped += 1
                continue
            result = await create_decision(
                session,
                node.workspace_id,
                draft,
                actor="system:migrate_decisions",
                gate_mode="report",
                mirror_properties=None,
            )
            if result.outcome is WriteOutcome.CREATED and result.decision_id:
                # Point the decision at the ORIGINAL node (which owns the
                # discussed_in/authored_by/evidenced_by edges) and drop the
                # writer's freshly minted mirror to avoid duplicate nodes.
                imported = await session.get(Decision, result.decision_id)
                if imported is not None and result.graph_node_id:
                    await session.execute(
                        sa_text(
                            "UPDATE graph_nodes SET deleted_at = now()"
                            " WHERE id = :mirror AND workspace_id = :ws"
                        ),
                        {"mirror": str(result.graph_node_id), "ws": str(node.workspace_id)},
                    )
                    imported.graph_node_id = node.id
                    # Stamp the typed-row linkage onto the original node so the
                    # graph-based UI can reach /api/decisions endpoints.
                    await session.execute(
                        sa_text(
                            "UPDATE graph_nodes SET properties = properties ||"
                            " jsonb_build_object('decision_id', CAST(:d AS TEXT))"
                            " WHERE id = :n AND workspace_id = :ws"
                        ),
                        {
                            "d": str(result.decision_id),
                            "n": str(node.id),
                            "ws": str(node.workspace_id),
                        },
                    )
                created += 1
            elif result.outcome is WriteOutcome.MERGED_AS_EVIDENCE:
                merged += 1
            await session.flush()

        await session.commit()
        print(f"imported: {created}, merged as duplicates: {merged}, skipped: {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=UUID, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(migrate(args.workspace_id, args.apply))


if __name__ == "__main__":
    main()
