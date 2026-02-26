"""GitHub App OAuth lifecycle service.

Handles GitHub App installation URL generation, installation callback handling,
installation access token generation/refresh, disconnect, and status. All
token values are stored encrypted in Supabase Vault -- never in plain text.

GitHub App installation flow:
1. User is redirected to https://github.com/apps/{slug}/installations/new
2. After installation, GitHub redirects to callback with installation_id + setup_action
3. Backend generates an installation access token via JWT-signed request to GitHub API
4. Installation access tokens expire after 1 hour, refreshed via App JWT on demand

Uses PyJWT with RS256 for App JWT signing (GitHub requires RS256-signed JWTs).
Uses httpx for all GitHub API calls (consistent with project pattern).
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import jwt as pyjwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.integration import OAuthToken, WorkspaceIntegration
from src.services.oauth_common import OAuthStateError, sign_oauth_state, verify_oauth_state
from src.services.vault import delete_token, read_token, store_token, token_name

logger = logging.getLogger(__name__)

# GitHub API endpoints
GITHUB_API_BASE = "https://api.github.com"


class GitHubOAuthError(Exception):
    """Raised when a GitHub OAuth operation fails."""


def _sign_state(workspace_id: UUID, secret: str) -> str:
    """Create a signed state parameter. Delegates to shared utility."""
    return sign_oauth_state(workspace_id, secret)


def _verify_state(state: str, secret: str) -> UUID:
    """Verify a signed state parameter. Wraps shared utility with provider error."""
    try:
        return verify_oauth_state(state, secret)
    except OAuthStateError as e:
        raise GitHubOAuthError(str(e)) from e


def _create_app_jwt(settings: Settings) -> str:
    """Create a JWT signed with the GitHub App private key.

    GitHub requires JWTs signed with RS256. The JWT is used to
    authenticate as the GitHub App for API calls like generating
    installation access tokens.

    The JWT:
    - iss: GitHub App ID
    - iat: Issued at (60 seconds in the past to account for clock drift)
    - exp: Expires in 10 minutes (GitHub maximum)
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,  # 60 seconds in the past for clock drift
        "exp": now + (10 * 60),  # 10 minutes maximum
        "iss": settings.GITHUB_APP_ID,
    }
    return pyjwt.encode(payload, settings.GITHUB_APP_PRIVATE_KEY, algorithm="RS256")


def build_install_url(state: str, settings: Settings) -> str:
    """Construct the GitHub App installation URL.

    Uses the GitHub App install flow with redirect URI so GitHub redirects
    back to our callback after the user installs or authorizes the app.

    Args:
        state: Pre-signed state parameter (use _sign_state to create).
        settings: Application settings with GitHub App config.

    Returns:
        Full installation URL to redirect the user to.
    """
    redirect_uri = settings.github_redirect_uri
    return (
        f"https://github.com/apps/{settings.GITHUB_APP_SLUG}"
        f"/installations/new?state={state}&redirect_uri={redirect_uri}"
    )


async def handle_callback(
    installation_id: int,
    setup_action: str,
    state: str,
    session: AsyncSession,
    settings: Settings,
) -> dict:
    """Handle GitHub App installation callback.

    After the user installs the GitHub App, GitHub redirects to our callback
    URL with an installation_id. We generate an installation access token
    and store it in Vault.

    Args:
        installation_id: GitHub App installation ID.
        setup_action: The setup action (install, update, etc.).
        state: Signed state parameter with workspace_id.
        session: Async database session.
        settings: Application settings.

    Returns:
        Dict with installation info: {"installation_id": int, "account": str}

    Raises:
        GitHubOAuthError: If state is invalid or token generation fails.
    """
    # Verify state and extract workspace_id
    workspace_id = _verify_state(state, settings.GITHUB_CLIENT_SECRET)

    # Look up workspace owner for user_id
    from src.models.user import WorkspaceMember

    stmt = select(WorkspaceMember.user_id).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    user_id = result.scalar_one_or_none()

    if user_id is None:
        raise GitHubOAuthError("Workspace not found")

    # Generate installation access token via GitHub API
    app_jwt = _create_app_jwt(settings)
    token_data = await _create_installation_token(installation_id, app_jwt)

    access_token_value = token_data["token"]
    expires_at_str = token_data.get("expires_at", "")

    # Parse expiry (GitHub returns ISO 8601 format)
    token_expires_at = None
    if expires_at_str:
        # GitHub returns "2024-01-01T00:00:00Z" format
        try:
            token_expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            # Convert to naive UTC for DB consistency (project convention)
            token_expires_at = token_expires_at.replace(tzinfo=None)
        except (ValueError, AttributeError):
            # Default to 1 hour from now if parsing fails
            token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)

    # Store installation access token in Vault
    access_name = token_name("github", workspace_id, "access_token")
    await store_token(session, access_name, access_token_value)

    # Upsert OAuthToken record (stores Vault secret name, NOT actual token)
    # Query WITHOUT deleted_at filter to reuse soft-deleted rows on reconnect
    oauth_stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "github",
    )
    oauth_result = await session.execute(oauth_stmt)
    oauth_token = oauth_result.scalar_one_or_none()

    if oauth_token:
        oauth_token.access_token = access_name
        oauth_token.refresh_token = None  # No refresh token -- we re-generate via App JWT
        oauth_token.token_expires_at = token_expires_at
        oauth_token.metadata_ = {"installation_id": installation_id}
        oauth_token.deleted_at = None  # un-soft-delete on reconnect
    else:
        oauth_token = OAuthToken(
            workspace_id=workspace_id,
            user_id=user_id,
            provider="github",
            access_token=access_name,
            refresh_token=None,
            token_expires_at=token_expires_at,
            metadata_={"installation_id": installation_id},
        )
        session.add(oauth_token)

    # Get installation account info
    account_login = ""
    permissions = token_data.get("permissions", {})
    # Fetch installation details for account info
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if resp.status_code == 200:
                inst_data = resp.json()
                account_login = inst_data.get("account", {}).get("login", "")
    except httpx.HTTPError:
        pass  # Non-critical -- we can proceed without the account name

    # Upsert WorkspaceIntegration
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "connected"
        integration.external_id = account_login or str(installation_id)
        integration.connected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        integration.config = {
            "installation_id": installation_id,
            "account_login": account_login,
        }
        integration.deleted_at = None
    else:
        integration = WorkspaceIntegration(
            workspace_id=workspace_id,
            provider="github",
            status="connected",
            external_id=account_login or str(installation_id),
            connected_at=datetime.now(timezone.utc).replace(tzinfo=None),
            config={
                "installation_id": installation_id,
                "account_login": account_login,
            },
        )
        session.add(integration)

    await session.commit()

    return {
        "installation_id": installation_id,
        "account": account_login,
    }


async def _create_installation_token(installation_id: int, app_jwt: str) -> dict:
    """Generate an installation access token via the GitHub API.

    POST /app/installations/{installation_id}/access_tokens
    Authenticated with the App JWT.

    Args:
        installation_id: GitHub App installation ID.
        app_jwt: JWT signed with the App private key.

    Returns:
        Dict with token data: {"token": str, "expires_at": str, "permissions": dict}

    Raises:
        GitHubOAuthError: If the API call fails.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    if response.status_code != 201:
        raise GitHubOAuthError(
            f"Failed to create installation token: {response.status_code} {response.text}"
        )

    return response.json()


async def get_installation_token(
    workspace_id: UUID,
    session: AsyncSession,
    settings: Settings,
) -> str:
    """Get a valid installation access token, refreshing if expired.

    Installation access tokens expire after 1 hour. This function reads
    the current token from Vault, checks expiry, and generates a new one
    if needed using the App JWT.

    Args:
        workspace_id: Workspace to get the token for.
        session: Async database session.
        settings: Application settings.

    Returns:
        A valid installation access token string.

    Raises:
        GitHubOAuthError: If no token exists or refresh fails.
    """
    # Find the OAuthToken record
    stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.provider == "github",
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    oauth_token = result.scalar_one_or_none()

    if oauth_token is None:
        raise GitHubOAuthError("No GitHub integration found for this workspace")

    # Check if token is still valid (with 5 min buffer)
    if oauth_token.token_expires_at:
        buffer = timedelta(minutes=5)
        # Ensure both sides are naive UTC for comparison
        expires_at = oauth_token.token_expires_at
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        if expires_at > (datetime.now(timezone.utc).replace(tzinfo=None) + buffer):
            # Token still valid, read from Vault
            access_name = token_name("github", workspace_id, "access_token")
            current_token = await read_token(session, access_name)
            if current_token:
                return current_token

    # Token expired or expiring soon -- generate new one
    installation_id = (oauth_token.metadata_ or {}).get("installation_id")
    if not installation_id:
        raise GitHubOAuthError("No installation_id found in token metadata")

    # Generate new installation access token
    app_jwt = _create_app_jwt(settings)
    token_data = await _create_installation_token(installation_id, app_jwt)

    new_token = token_data["token"]
    expires_at_str = token_data.get("expires_at", "")

    # Parse expiry
    token_expires_at = None
    if expires_at_str:
        try:
            token_expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            token_expires_at = token_expires_at.replace(tzinfo=None)
        except (ValueError, AttributeError):
            token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)

    # Store new token in Vault
    access_name = token_name("github", workspace_id, "access_token")
    await store_token(session, access_name, new_token)

    # Update expiry in DB
    oauth_token.token_expires_at = token_expires_at
    await session.commit()

    return new_token


async def disconnect(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    settings: Settings | None = None,
) -> None:
    """Disconnect GitHub integration and uninstall the GitHub App.

    Calls DELETE /app/installations/{id} to remove the app from the
    user's GitHub account/org, then soft-deletes the OAuthToken, deletes
    Vault secrets, and marks WorkspaceIntegration as disconnected.
    Existing PR data is preserved.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
        user_id: User who initiated the disconnect.
        settings: Application settings (needed for App JWT to uninstall).
    """
    # Get installation_id before we soft-delete everything
    installation_id = None
    oauth_stmt = select(OAuthToken).where(
        OAuthToken.workspace_id == workspace_id,
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "github",
        OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    oauth_result = await session.execute(oauth_stmt)
    oauth_token = oauth_result.scalar_one_or_none()

    if oauth_token:
        installation_id = (oauth_token.metadata_ or {}).get("installation_id")
        oauth_token.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Uninstall the GitHub App from the user's account/org
    if installation_id and settings:
        try:
            app_jwt = _create_app_jwt(settings)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(
                    f"{GITHUB_API_BASE}/app/installations/{installation_id}",
                    headers={
                        "Authorization": f"Bearer {app_jwt}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                if resp.status_code == 204:
                    logger.info(
                        "Uninstalled GitHub App installation %s", installation_id
                    )
                else:
                    logger.warning(
                        "Failed to uninstall GitHub App installation %s: %s %s",
                        installation_id, resp.status_code, resp.text,
                    )
        except httpx.HTTPError as e:
            logger.warning(
                "HTTP error uninstalling GitHub App: %s", e
            )

    # Delete Vault secret
    access_name = token_name("github", workspace_id, "access_token")
    await delete_token(session, access_name)

    # Mark integration as disconnected
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        integration.status = "disconnected"

    await session.commit()


async def get_status(
    workspace_id: UUID,
    session: AsyncSession,
) -> dict:
    """Get the current GitHub integration status.

    Args:
        workspace_id: Workspace to check status for.
        session: Async database session.

    Returns:
        Dict with connection state and account info.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration is None or integration.status == "disconnected":
        return {
            "connected": False,
            "account": None,
            "status": "disconnected",
        }

    return {
        "connected": integration.status == "connected",
        "account": integration.external_id,
        "status": integration.status,
    }
