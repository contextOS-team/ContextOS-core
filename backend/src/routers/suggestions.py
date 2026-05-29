"""Suggestion endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.services.suggestions import (
    SuggestionNotFoundError,
    dismiss_suggestion,
    list_all_suggestions,
    list_visible_suggestions,
    reopen_suggestion,
    resolve_suggestion,
    serialize_suggestion,
    snooze_suggestion,
)

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


class SnoozeSuggestionRequest(BaseModel):
    """Request body for snoozing a suggestion."""

    snoozed_until: datetime | None = None


async def _not_found_as_404(coro):
    try:
        return await coro
    except SuggestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        ) from exc


@router.get("")
async def suggestions(
    limit: int = Query(default=3, ge=1, le=20),
    exclude_type: list[str] = Query(default=[]),
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List visible dashboard suggestions."""
    rows = await list_visible_suggestions(
        session,
        user.workspace_id,
        limit=limit,
        exclude_types=tuple(exclude_type),
    )
    return [serialize_suggestion(row) for row in rows]


@router.get("/all")
async def all_suggestions(
    limit: int = Query(default=100, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List all suggestions for lifecycle recovery."""
    rows = await list_all_suggestions(session, user.workspace_id, limit=limit)
    return [serialize_suggestion(row) for row in rows]


@router.post("/{suggestion_id}/dismiss")
async def dismiss(
    suggestion_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Dismiss an exact suggestion instance."""
    suggestion = await _not_found_as_404(
        dismiss_suggestion(session, user.workspace_id, user.user_id, suggestion_id)
    )
    await session.commit()
    return serialize_suggestion(suggestion)


@router.post("/{suggestion_id}/snooze")
async def snooze(
    suggestion_id: UUID,
    body: SnoozeSuggestionRequest | None = None,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Snooze a suggestion until a timestamp."""
    suggestion = await _not_found_as_404(
        snooze_suggestion(
            session,
            user.workspace_id,
            user.user_id,
            suggestion_id,
            body.snoozed_until if body else None,
        )
    )
    await session.commit()
    return serialize_suggestion(suggestion)


@router.post("/{suggestion_id}/resolve")
async def resolve(
    suggestion_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mark a suggestion resolved."""
    suggestion = await _not_found_as_404(
        resolve_suggestion(session, user.workspace_id, user.user_id, suggestion_id)
    )
    await session.commit()
    return serialize_suggestion(suggestion)


@router.post("/{suggestion_id}/reopen")
async def reopen(
    suggestion_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reopen a dismissed, resolved, or snoozed suggestion."""
    suggestion = await _not_found_as_404(
        reopen_suggestion(session, user.workspace_id, user.user_id, suggestion_id)
    )
    await session.commit()
    return serialize_suggestion(suggestion)
