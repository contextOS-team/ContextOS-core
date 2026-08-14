"""Coverage Audit report endpoint (human dashboard, JWT auth)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.coverage_report import compute_coverage

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/coverage")
async def coverage_audit(
    window_days: int = Query(default=90, ge=1, le=365),
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Decision Coverage Audit: reconstructed / aligned / uncertain / drifted
    decisions and drift outcomes over the window."""
    return await compute_coverage(session, user.workspace_id, window_days)
