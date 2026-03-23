"""Data retention service for privacy compliance.

Scrubs raw source content after embedding and graph extraction are complete,
keeping only:
- Embeddings (vector + search_content + metadata with title/snippet/url)
- Context pages (generated summaries)
- Graph nodes and edges (extracted relationships)

Raw content (message text, PR descriptions, code, meeting transcripts) and
API response payloads (raw_data JSONB) are nullified, not deleted — the
records remain for FK integrity but contain no sensitive content.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Minimum age before raw content is eligible for scrubbing.
# Ensures content is fully processed (embedded, graph-extracted) before removal.
RETENTION_HOURS = 24


async def scrub_workspace_raw_content(
    session: AsyncSession,
    workspace_id: UUID,
    retention_hours: int = RETENTION_HOURS,
) -> dict[str, int]:
    """Scrub raw content from all source tables for a workspace.

    Only scrubs records that:
    1. Have a corresponding embedding (proof of processing)
    2. Are older than retention_hours

    Returns a dict of {source_type: records_scrubbed}.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    stats: dict[str, int] = {}

    # Tables to scrub: (table_name, text_columns_to_null, has_raw_data)
    scrub_targets = [
        ("slack_messages", ["text"], True),
        ("github_pull_requests", ["description"], True),
        ("github_reviews", ["body"], True),
        ("gitlab_merge_requests", ["description"], True),
        ("gitlab_reviews", ["body"], True),
        ("notion_pages", ["content"], True),
        ("meeting_transcripts", ["transcript"], True),
        ("meeting_segments", ["text"], True),
        ("linear_comments", ["body"], True),
        ("jira_comments", ["body"], True),
        ("telegram_messages", ["text"], True),
        ("code_chunks", ["content"], False),
    ]

    for table, text_cols, has_raw_data in scrub_targets:
        try:
            # Build SET clause: null out text columns and raw_data
            set_parts = [f"{col} = '[scrubbed]'" for col in text_cols]
            if has_raw_data:
                set_parts.append("raw_data = '{}'::jsonb")

            set_clause = ", ".join(set_parts)

            # Determine source_type from table name
            source_type = _table_to_source_type(table)

            stmt = text(f"""
                UPDATE {table} t
                SET {set_clause}
                WHERE t.workspace_id = :workspace_id
                  AND t.created_at < :cutoff
                  AND t.{text_cols[0]} != '[scrubbed]'
                  AND EXISTS (
                    SELECT 1 FROM embeddings e
                    WHERE e.source_type = :source_type
                      AND e.source_id = t.id
                      AND e.deleted_at IS NULL
                  )
            """)

            result = await session.execute(stmt, {
                "workspace_id": str(workspace_id),
                "cutoff": cutoff,
                "source_type": source_type,
            })

            if result.rowcount > 0:
                stats[table] = result.rowcount
                logger.info(
                    "Scrubbed %d records from %s for workspace %s",
                    result.rowcount, table, workspace_id,
                )
        except Exception:
            logger.exception("Failed to scrub %s for workspace %s", table, workspace_id)

    await session.commit()
    return stats


def _table_to_source_type(table: str) -> str:
    """Map table name to embedding source_type."""
    mapping = {
        "slack_messages": "slack_message",
        "github_pull_requests": "github_pull_request",
        "github_reviews": "github_review",
        "gitlab_merge_requests": "gitlab_merge_request",
        "gitlab_reviews": "gitlab_review",
        "notion_pages": "notion_page",
        "meeting_transcripts": "meeting_transcript",
        "meeting_segments": "meeting_segment",
        "linear_comments": "linear_comment",
        "jira_comments": "jira_comment",
        "telegram_messages": "telegram_message",
        "code_chunks": "code_chunk",
    }
    return mapping.get(table, table.rstrip("s"))
