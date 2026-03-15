"""Dashboard intelligence widget endpoints.

Provides pre-aggregated data for the dashboard homepage widgets:
- Attention items (stale contexts + open PRs/MRs)
- Weekly summary (activity counts by day)
- Sprint progress (Linear active cycle)
- Resurfaced forgotten context (decision-like Slack messages)
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.dashboard_attention import get_attention_items
from src.services.dashboard_sprint import get_active_sprint
from src.services.dashboard_resurfaced import get_resurfaced_items
from src.services.dashboard_summary import get_weekly_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/attention")
async def attention(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Get attention items: stale contexts and open PRs/MRs awaiting review."""
    return await get_attention_items(session, user.workspace_id)


@router.get("/weekly-summary")
async def weekly_summary(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Get activity counts grouped by day for the last 7 days."""
    return await get_weekly_summary(session, user.workspace_id)


@router.get("/sprint")
async def sprint(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict | None:
    """Get Linear active cycle progress, or null if not connected."""
    return await get_active_sprint(session, user.workspace_id, user.user_id)


@router.get("/resurfaced")
async def resurfaced(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Get forgotten context candidates from Slack messages."""
    return await get_resurfaced_items(session, user.workspace_id)
