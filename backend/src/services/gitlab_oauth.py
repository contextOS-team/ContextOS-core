"""GitLab OAuth2 lifecycle service.

Handles GitLab OAuth2 authorization code flow: connect URL generation,
callback handling (code exchange, token storage), disconnect, and status.

GitLab uses standard OAuth2 authorization code flow (not GitHub App JWT):
1. User redirected to GitLab /oauth/authorize
2. GitLab redirects back to callback with authorization code
3. Backend exchanges code for access_token + refresh_token
4. Tokens stored encrypted in Supabase Vault
5. Access tokens expire after 2 hours, refreshed via refresh_token

Uses httpx for all GitLab API calls (consistent with project pattern).
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import OAuthToken, Provider, WorkspaceIntegration
from src.models.user import WorkspaceMember
from src.services.gitlab_common import (
    GITLAB_API_BASE,
    GITLAB_AUTH_URL,
    GITLAB_TOKEN_URL,
    GitLabOAuthError,
)
from src.services.oauth_common import (
    disconnect_provider,
    upsert_oauth_token,
    upsert_workspace_integration,
    verify_state_or_raise,
)
from src.services.vault import delete_token, store_token, token_name

logger = logging.getLogger(__name__)


def build_auth_url(state: str, settings: Settings) -> str:
    """Construct the GitLab OAuth2 authorization URL.

    Uses standard OAuth2 authorization code flow with read_api scope.

    Args:
        state: Pre-signed state parameter (use sign_oauth_state to create).
        settings: Application settings with GitLab OAuth config.

    Returns:
        Full authorization URL to redirect the user to.
    """
    redirect_uri = settings.gitlab_redirect_uri
    return (
        f"{GITLAB_AUTH_URL}"
        f"?client_id={settings.GITLAB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&state={state}"
        f"&scope=read_api"
    )


async def _exchange_code(code: str, settings: Settings) -> dict:
    """Exchange an authorization code for OAuth2 tokens.

    POST to GitLab token endpoint with authorization_code grant type.

    Args:
        code: Authorization code from GitLab callback.
        settings: Application settings with GitLab OAuth config.

    Returns:
        Token response dict with access_token, refresh_token, expires_in.

    Raises:
        GitLabOAuthError: If the token exchange fails.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GITLAB_TOKEN_URL,
            data={
                "client_id": settings.GITLAB_CLIENT_ID,
                "client_secret": settings.GITLAB_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.gitlab_redirect_uri,
            },
        )

    if response.status_code != 200:
        raise GitLabOAuthError(
            f"Failed to exchange code for token: {response.status_code} {response.text}"
        )

    return response.json()


async def handle_callback(
    code: str,
    state: str,
    session: AsyncSession,
    settings: Settings,
) -> dict:
    """Handle GitLab OAuth2 callback.

    After the user authorizes, GitLab redirects to our callback URL
    with an authorization code. We exchange it for tokens and store
    them in Vault.

    Args:
        code: Authorization code from GitLab.
        state: Signed state parameter with workspace_id.
        session: Async database session.
        settings: Application settings.

    Returns:
        Dict with account info: {"account": username, "workspace_id": str}

    Raises:
        GitLabOAuthError: If state is invalid or token exchange fails.
    """
    # Verify state and extract workspace_id
    workspace_id = verify_state_or_raise(
        state, settings.GITLAB_CLIENT_SECRET, GitLabOAuthError
    )

    # Look up workspace owner for user_id
    stmt = select(WorkspaceMember.user_id).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    user_id = result.scalar_one_or_none()

    if user_id is None:
        raise GitLabOAuthError("Workspace not found")

    # Exchange code for tokens
    token_data = await _exchange_code(code, settings)

    access_token_value = token_data["access_token"]
    refresh_token_value = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 7200)  # Default 2 hours

    token_expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(seconds=expires_in)
    )

    # Fetch current user info from GitLab
    username = ""
    gitlab_user_id = ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{GITLAB_API_BASE}/user",
                headers={"Authorization": f"Bearer {access_token_value}"},
            )
            if resp.status_code == 200:
                user_data = resp.json()
                username = user_data.get("username", "")
                gitlab_user_id = str(user_data.get("id", ""))
    except httpx.HTTPError:
        pass  # Non-critical -- we can proceed without user info

    # Store tokens in Vault
    access_name = token_name(Provider.GITLAB, workspace_id, "access_token")
    refresh_name = token_name(Provider.GITLAB, workspace_id, "refresh_token")
    await store_token(session, access_name, access_token_value)
    if refresh_token_value:
        await store_token(session, refresh_name, refresh_token_value)

    # Upsert OAuthToken record
    await upsert_oauth_token(
        session,
        workspace_id,
        user_id,
        Provider.GITLAB,
        access_token_name=access_name,
        refresh_token_name=refresh_name if refresh_token_value else None,
        token_expires_at=token_expires_at,
        scopes=["read_api"],
        metadata={"username": username, "name": username, "gitlab_user_id": gitlab_user_id},
    )

    # Upsert WorkspaceIntegration record
    await upsert_workspace_integration(
        session,
        workspace_id,
        Provider.GITLAB,
        external_id=gitlab_user_id or username,
        config={"username": username, "gitlab_user_id": gitlab_user_id},
    )

    await session.commit()

    return {
        "account": username,
        "workspace_id": str(workspace_id),
    }


async def disconnect(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: Settings | None = None,
) -> None:
    """Disconnect GitLab integration.

    Soft-deletes OAuthToken, deletes Vault secrets, and marks
    WorkspaceIntegration as disconnected. Existing MR data is preserved.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
        user_id: User who initiated the disconnect.
        settings: Application settings (unused for GitLab, kept for API parity).
    """
    access_name = token_name(Provider.GITLAB, workspace_id, "access_token")
    refresh_name = token_name(Provider.GITLAB, workspace_id, "refresh_token")

    await disconnect_provider(
        session,
        workspace_id,
        user_id,
        Provider.GITLAB,
        vault_token_names=[access_name, refresh_name],
    )


async def get_status(
    workspace_id: UUID,
    session: AsyncSession,
) -> dict:
    """Get the current GitLab integration status.

    Args:
        workspace_id: Workspace to check status for.
        session: Async database session.

    Returns:
        Dict with connection state, account info, and connected_at.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.GITLAB,
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status == "disconnected":
        return {
            "connected": False,
            "account": None,
            "status": "disconnected",
        }

    config = integration.config or {}
    return {
        "connected": integration.status == "connected",
        "account": config.get("username", integration.external_id),
        "status": integration.status,
        "connected_at": str(integration.connected_at) if integration.connected_at else None,
    }
