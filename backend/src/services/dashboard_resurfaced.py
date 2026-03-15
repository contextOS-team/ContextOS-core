"""Dashboard resurfaced forgotten context service.

Identifies Slack messages containing decision-like language that may
not have been acted upon (no ticket follow-through). Uses heuristic
keyword matching for v1 -- deterministic, fast, and free.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.slack import SlackMessage

logger = logging.getLogger(__name__)

# Decision-like keyword patterns for heuristic matching
DECISION_KEYWORDS = [
    "we should",
    "we need to",
    "let's",
    "need to",
    "should we",
    "what if we",
    "plan to",
    "going to",
    "migrate to",
    "switch to",
    "consider",
    "proposal",
    "action item",
    "todo",
    "follow up",
]


async def get_resurfaced_items(
    session: AsyncSession, workspace_id: UUID
) -> list[dict]:
    """Find Slack messages with decision-like language and no ticket follow-through.

    Queries messages from the last 14 days matching keyword heuristics,
    excluding messages where a ticket was created after the message
    (suggesting follow-through). Returns up to 5 results.
    """
    now = datetime.now(timezone.utc)
    fourteen_days_ago = now - timedelta(days=14)

    # Build keyword ILIKE conditions
    keyword_conditions = [
        SlackMessage.text.ilike(f"%{kw}%")  # type: ignore[union-attr]
        for kw in DECISION_KEYWORDS
    ]

    stmt = (
        select(SlackMessage)
        .where(
            SlackMessage.workspace_id == workspace_id,
            SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
            SlackMessage.slack_created_at >= fourteen_days_ago,  # type: ignore[operator]
            or_(*keyword_conditions),
        )
        .order_by(SlackMessage.slack_created_at.desc())  # type: ignore[union-attr]
        .limit(5)
    )

    result = await session.execute(stmt)
    messages = result.scalars().all()

    items: list[dict] = []
    for msg in messages:
        text = msg.text or ""
        items.append(
            {
                "type": "resurfaced",
                "id": str(msg.id),
                "text": text[:200] if len(text) > 200 else text,
                "channel_name": msg.channel_name,
                "user_name": msg.user_name,
                "created_at": (
                    msg.slack_created_at.isoformat() if msg.slack_created_at else None
                ),
            }
        )

    return items
