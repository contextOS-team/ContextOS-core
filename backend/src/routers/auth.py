"""Auth-related API endpoints."""

from fastapi import APIRouter, Depends

from src.dependencies import UserContext, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: UserContext = Depends(get_current_user)) -> dict:
    """Return current authenticated user info.

    Validates the JWT and returns user_id, email, and workspace_id.
    Used by the frontend to verify the session is valid.
    """
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "workspace_id": str(user.workspace_id),
    }
